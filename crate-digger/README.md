# Crate Digger

Jeu de collection de vinyles underground, inspiré de Wikizz : on ouvre des bacs de disques
issus de Discogs, et la rareté vient des stats communautaires (peu possédé + très recherché = rare).

## Import des données (Python 3, aucune dépendance)

1. Mets ton jeton Discogs dans `.env` : `DISCOGS_TOKEN=...` (le fichier n'est pas versionné).
2. Le segment (genre, styles, années, format) se règle dans `config.json`.
3. Importer un échantillon :

   ```bash
   python3 scripts/import_discogs.py --styles Minimal --from 2000 --to 2005
   ```

   Sans option, tout le segment de `config.json` est importé (compter quelques heures,
   l'API limite à 60 requêtes/minute). Le script reprend là où il s'est arrêté.

4. Analyser et produire le pool de cartes :

   ```bash
   python3 scripts/analyze.py
   ```

   Affiche la répartition have/want, les paliers de rareté avec des exemples,
   et écrit `data/pool.json`.
