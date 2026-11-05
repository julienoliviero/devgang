#!/bin/bash
# Enregistre le jeton Discogs dans .env (saisie masquée).
cd "$(dirname "$0")/.." || exit 1
printf 'Colle ton jeton Discogs puis appuie sur Entrée (rien ne s’affiche, c’est normal) : '
read -rs TOKEN
echo
# retire les marqueurs de collage du terminal et les espaces
TOKEN="${TOKEN//$'\e[200~'/}"
TOKEN="${TOKEN//$'\e[201~'/}"
TOKEN="$(printf '%s' "$TOKEN" | tr -d '[:space:]')"
if [ -z "$TOKEN" ]; then
  echo "Aucun jeton saisi, rien n'a été modifié."
  exit 1
fi
if ! [[ "$TOKEN" =~ ^[A-Za-z0-9]{20,80}$ ]]; then
  echo "Ce qui a été collé ne ressemble pas à un jeton Discogs (${#TOKEN} caractères)."
  echo "Un jeton ne contient que des lettres et des chiffres, environ 40 caractères."
  echo "Recopie-le depuis https://www.discogs.com/settings/developers puis relance. Rien n'a été modifié."
  exit 1
fi
rm -f .env
printf '# Jeton personnel Discogs : https://www.discogs.com/settings/developers\nDISCOGS_TOKEN=%s\n' "$TOKEN" > .env
chmod 600 .env
echo "Jeton enregistré dans .env (${#TOKEN} caractères). Tu peux revenir sur Claude."
