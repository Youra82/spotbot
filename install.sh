#!/bin/bash
# spotbot - Installations-Skript
echo "=== spotbot Installation ==="
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
mkdir -p logs artifacts
chmod +x *.sh
if [ ! -f "secret.json" ]; then
    cp secret.json.example secret.json
    echo "WARNUNG: secret.json aus Vorlage erstellt - bitte Bitget-API-Keys (nur SPOT-Handel, KEINE Auszahlung) + Telegram eintragen."
fi
echo ""
echo "Naechste Schritte:"
echo "  1. secret.json befuellen"
echo "  2. Trockenlauf:  .venv/bin/python3 src/spotbot/strategy/run.py --force   (dry_run=true in settings.json)"
echo "  3. Scharf schalten: cp settings.local.json.example settings.local.json  (dry_run=false)"
echo "  4. Cronjob:  */15 * * * * cd $(pwd) && .venv/bin/python3 master_runner.py >> logs/cron.log 2>&1"
