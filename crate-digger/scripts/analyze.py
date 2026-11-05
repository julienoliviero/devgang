#!/usr/bin/env python3
"""Fusionne les tranches importées, calcule la rareté et écrit data/pool.json.

Rareté = disque peu possédé ET recherché. Le score est volontairement simple
pour pouvoir l'ajuster après avoir vu les vrais chiffres (voir rarity_score).
Les paliers suivent la même répartition que Wikizz : une petite part du pool
en Legendary, la grande majorité en Common.

    python3 scripts/analyze.py
"""
import glob
import json
import math
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def rarity_score(have, want):
    # rapport want/have (obscur mais recherché), pondéré par le nombre de
    # personnes qui le cherchent pour éviter qu'un disque à 5 have / 6 want
    # passe devant une vraie pépite à 40 have / 400 want
    return (want + 1) / (have + 1) * math.log10(want + 10)


def pct(sorted_vals, p):
    if not sorted_vals:
        return 0
    return sorted_vals[min(len(sorted_vals) - 1, int(p * len(sorted_vals)))]


def main():
    with open(os.path.join(ROOT, "config.json")) as f:
        cfg = json.load(f)

    pool, slices, truncated = {}, 0, []
    for path in glob.glob(os.path.join(ROOT, "data", "raw", "*", "*.json")):
        with open(path) as f:
            s = json.load(f)
        slices += 1
        if s.get("truncated"):
            truncated.append("%s %s (%d)" % (s["style"], s["year"], s["total"]))
        for r in s["releases"]:
            pool[r["id"]] = r  # dédoublonnage : une release peut avoir plusieurs styles
    if not pool:
        print("Aucune donnée : lance d'abord scripts/import_discogs.py")
        return

    raw_count = len(pool)
    releases = [r for r in pool.values() if r["have"] >= cfg["min_have"]]
    for r in releases:
        r["score"] = round(rarity_score(r["have"], r["want"]), 4)
    releases.sort(key=lambda r: r["score"], reverse=True)

    # attribution des paliers par part du pool, du plus rare au plus commun
    i, n = 0, len(releases)
    tier_stats = []
    for t in cfg["tiers"]:
        size = n - i if t["share_of_pool"] is None else max(1, round(n * t["share_of_pool"]))
        chunk = releases[i:i + size]
        for r in chunk:
            r["tier"] = t["name"]
        tier_stats.append((t, chunk))
        i += size

    haves = sorted(r["have"] for r in releases)
    wants = sorted(r["want"] for r in releases)
    print("Tranches lues : %d" % slices)
    print("Releases uniques : %d  |  gardées (have >= %d) : %d" % (raw_count, cfg["min_have"], n))
    if truncated:
        print("⚠ Tranches tronquées à 10 000 (à redécouper) : " + ", ".join(truncated))
    print("\nhave  médiane %d | p10 %d | p90 %d | max %d" % (pct(haves, .5), pct(haves, .1), pct(haves, .9), haves[-1]))
    print("want  médiane %d | p10 %d | p90 %d | max %d" % (pct(wants, .5), pct(wants, .1), pct(wants, .9), wants[-1]))

    for t, chunk in tier_stats:
        if not chunk:
            continue
        h = sorted(r["have"] for r in chunk)
        w = sorted(r["want"] for r in chunk)
        print("\n== %s : %d disques (tirage %.1f %%) — have médian %d, want médian %d"
              % (t["name"], len(chunk), t["pack_odds"] * 100, pct(h, .5), pct(w, .5)))
        for r in chunk[:5]:
            print("   %-60.60s %s  have %d / want %d" % (r["title"], r.get("year") or "?", r["have"], r["want"]))

    out = os.path.join(ROOT, "data", "pool.json")
    with open(out, "w") as f:
        json.dump(releases, f)
    print("\nPool écrit : %s" % out)


if __name__ == "__main__":
    main()
