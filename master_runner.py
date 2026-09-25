# master_runner.py
"""spotbot Master Runner - per Cron alle 15 Minuten aufrufen.
Handelt nur einmal pro neuer UTC-Tageskerze (state.json), Lock verhindert Doppel-Laeufe."""
import os
import subprocess
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
LOCK = os.path.join(PROJECT_ROOT, 'spotbot.lock')
RUN = os.path.join(PROJECT_ROOT, 'src', 'spotbot', 'strategy', 'run.py')


def main():
    try:
        fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        # Verwaisten Lock (>2h) aufraeumen, sonst still beenden
        import time
        if time.time() - os.path.getmtime(LOCK) > 7200:
            os.remove(LOCK)
        return
    try:
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        subprocess.run([sys.executable, RUN] + sys.argv[1:], cwd=PROJECT_ROOT)
    finally:
        if os.path.exists(LOCK):
            os.remove(LOCK)


if __name__ == '__main__':
    main()
