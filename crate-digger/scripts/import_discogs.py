#!/usr/bin/env python3
"""Importe les releases Discogs d'un segment (genre / styles / années / format).

L'API de recherche plafonne à 10 000 résultats par requête : on découpe donc
par style x année. Chaque tranche est sauvegardée dans data/raw/<style>/<année>.json ;
une tranche déjà présente est sautée, on peut donc relancer le script après une coupure.

Exemples :
    python3 scripts/import_discogs.py --styles Minimal --from 2000 --to 2005
    python3 scripts/import_discogs.py            # tout le segment de config.json
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = "https://api.discogs.com/database/search"
USER_AGENT = "CrateDigger/0.1 +local-prototype"
PER_PAGE = 100
MAX_RESULTS = 10000  # limite de pagination de l'API de recherche


def load_token():
    token = os.environ.get("DISCOGS_TOKEN", "").strip()
    env_path = os.path.join(ROOT, ".env")
    if not token and os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith("DISCOGS_TOKEN="):
                    token = line.split("=", 1)[1].strip().strip('"').strip("'")
    if not token:
        sys.exit("DISCOGS_TOKEN manquant : renseigne-le dans le fichier .env")
    return token


def get(params, token):
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        "Authorization": "Discogs token=" + token,
        "User-Agent": USER_AGENT,
    })
    for attempt in range(6):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                remaining = int(resp.headers.get("X-Discogs-Ratelimit-Remaining", "60"))
                data = json.loads(resp.read().decode("utf-8"))
            # 60 requêtes/minute : on ralentit quand le quota glissant s'épuise
            time.sleep(1.1 if remaining > 5 else 15)
            return data
        except urllib.error.HTTPError as e:
            if e.code == 429:
                print("  quota atteint, pause 60 s", flush=True)
                time.sleep(60)
            elif e.code in (500, 502, 503, 504):
                time.sleep(5 * (attempt + 1))
            elif e.code == 401:
                sys.exit("Jeton Discogs refusé (401) : vérifie DISCOGS_TOKEN dans .env")
            else:
                raise
        except OSError:
            # coupure réseau, délai dépassé (socket.timeout sous Python 3.9)...
            print("  souci réseau, nouvel essai dans %d s" % (10 * (attempt + 1)), flush=True)
            time.sleep(10 * (attempt + 1))
    raise RuntimeError("Échec répété sur " + url)


def slim(r):
    community = r.get("community") or {}
    return {
        "id": r.get("id"),
        "title": r.get("title"),
        "year": r.get("year"),
        "country": r.get("country"),
        "label": r.get("label") or [],
        "catno": r.get("catno"),
        "genre": r.get("genre") or [],
        "style": r.get("style") or [],
        "format": r.get("format") or [],
        "have": community.get("have", 0),
        "want": community.get("want", 0),
        "thumb": r.get("thumb"),
        "cover_image": r.get("cover_image"),
        "master_id": r.get("master_id"),
        "uri": r.get("uri"),
    }


def fetch_all(base, token, max_pages=None):
    """Récupère les pages accessibles (10 000 résultats max) d'une requête."""
    limit = MAX_RESULTS // PER_PAGE if max_pages is None else max_pages
    releases, page, pages, total = [], 1, 1, 0
    while page <= pages and page <= limit:
        data = get(dict(base, page=page), token)
        pag = data.get("pagination", {})
        pages, total = pag.get("pages", 1), pag.get("items", 0)
        releases.extend(slim(r) for r in data.get("results", []))
        page += 1
    return releases, total


def import_slice(cfg, style, year, token, out_path):
    base = {
        "type": "release",
        "genre": cfg["genre"],
        "style": style,
        "year": year,
        "format": cfg["format"],
        "per_page": PER_PAGE,
    }
    releases, total = fetch_all(base, token, max_pages=1)
    if total > PER_PAGE and total <= MAX_RESULTS:
        releases, total = fetch_all(base, token)
    truncated = False
    if total > MAX_RESULTS:
        # Au-delà de 10 000 : on relit la tranche triée par nombre de possesseurs,
        # croissant puis décroissant, et on fusionne (couvre jusqu'à 20 000).
        print("  %s %d : %d releases, double lecture triée..." % (style, year, total), flush=True)
        by_id = {}
        asc, _ = fetch_all(dict(base, sort="have", sort_order="asc"), token)
        need = -(-(total - len(asc)) // PER_PAGE) + 5  # pages restantes + marge de recouvrement
        desc, _ = fetch_all(dict(base, sort="have", sort_order="desc"), token, max_pages=need)
        for r in releases + asc + desc:
            by_id[r["id"]] = r
        releases = list(by_id.values())
        truncated = len(releases) < total * 0.99
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    tmp = out_path + ".tmp"
    with open(tmp, "w") as f:
        json.dump({"style": style, "year": year, "total": total,
                   "truncated": truncated, "releases": releases}, f)
    os.replace(tmp, out_path)
    return total, len(releases), truncated


def main():
    with open(os.path.join(ROOT, "config.json")) as f:
        cfg = json.load(f)
    ap = argparse.ArgumentParser()
    ap.add_argument("--styles", nargs="+", default=cfg["styles"])
    ap.add_argument("--from", dest="year_from", type=int, default=cfg["year_from"])
    ap.add_argument("--to", dest="year_to", type=int, default=cfg["year_to"])
    ap.add_argument("--force", action="store_true", help="réimporter les tranches existantes")
    args = ap.parse_args()

    token = load_token()
    for style in args.styles:
        for year in range(args.year_from, args.year_to + 1):
            out = os.path.join(ROOT, "data", "raw", style.replace(" ", "_"), "%d.json" % year)
            if os.path.exists(out) and not args.force:
                with open(out) as f:
                    prev = json.load(f)
                if len(prev["releases"]) >= prev["total"] * 0.99:
                    print("= %s %d déjà importé" % (style, year))
                    continue
                print("~ %s %d incomplet (%d/%d), réimport" % (style, year, len(prev["releases"]), prev["total"]), flush=True)
            total, got, truncated = import_slice(cfg, style, year, token, out)
            flag = "  ⚠ incomplet (plus de 20 000 releases)" if truncated else ""
            print("+ %s %d : %d releases récupérées sur %d%s" % (style, year, got, total, flag), flush=True)


if __name__ == "__main__":
    main()
