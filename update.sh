#!/bin/bash
set -e
echo "--- Sicheres Update (spotbot) ---"
# secret.json, settings.local.json, artifacts/ und logs/ sind nicht versioniert (.gitignore)
# und werden von 'git reset --hard' NICHT angefasst. Backup von secret.json trotzdem zur Sicherheit.
cp secret.json secret.json.bak
git fetch origin
git reset --hard origin/main
cp secret.json.bak secret.json && rm secret.json.bak
find . -type d -name "__pycache__" -prune -exec rm -rf {} +
chmod +x *.sh
.venv/bin/pip install -r requirements.txt --quiet
echo "Update abgeschlossen."
