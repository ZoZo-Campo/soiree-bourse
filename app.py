#!/usr/bin/env python3
"""Lancer avec Python 3.11+ et Tkinter. Aucun réseau au lancement."""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def project_python():
    candidates = (
        ROOT / '.venv' / 'bin' / 'python',
        ROOT / '.venv' / 'Scripts' / 'python.exe',
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return candidates[0]


def runtime_ready(interpreter):
    if not interpreter.is_file():
        return False
    try:
        result = subprocess.run(
            [str(interpreter), '-c', 'import tkinter, pymysql'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except OSError:
        return False
    return result.returncode == 0


def ensure_project_runtime():
    """Install the local MySQL runtime once, then always use it."""
    interpreter = project_python()
    if not runtime_ready(interpreter):
        installer = ROOT / 'installer.sh'
        if not installer.is_file():
            raise RuntimeError('Installation automatique impossible : installer.sh est absent.')
        print('Installation automatique du pilote MySQL…', flush=True)
        subprocess.run([str(installer), '--install-only'], cwd=ROOT, check=True)
        interpreter = project_python()
        if not runtime_ready(interpreter):
            raise RuntimeError('Le pilote MySQL n’a pas pu être installé.')

    try:
        already_using_venv = Path(sys.executable).resolve() == interpreter.resolve()
    except OSError:
        already_using_venv = False
    if not already_using_venv:
        os.execv(str(interpreter), [str(interpreter), str(ROOT / 'app.py'), *sys.argv[1:]])


def restart_in_project_venv():
    """Backward-compatible alias used by older integrations."""
    interpreter = project_python()
    if interpreter.is_file():
        try:
            already_using_venv = Path(sys.executable).resolve() == interpreter.resolve()
        except OSError:
            already_using_venv = False
        if not already_using_venv:
            os.execv(str(interpreter), [str(interpreter), str(ROOT / 'app.py'), *sys.argv[1:]])


def main():
    import tkinter as tk
    from tkinter import messagebox
    root = tk.Tk()
    root.withdraw()
    config_path = ROOT / 'config.ini'
    template_path = ROOT / 'config.example.ini'
    if not config_path.exists() and template_path.exists():
        try:
            # Création exclusive : ne jamais écraser les identifiants existants.
            fd = os.open(config_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(fd, 'w', encoding='utf-8') as config_file:
                config_file.write(template_path.read_text(encoding='utf-8'))
    (ROOT / 'data').mkdir(exist_ok=True)
    # Deux régies dans le même dossier ne doivent pas piloter les mêmes prix.
    lock = (ROOT / 'data' / 'application.lock').open('a+')
    try:
        if os.name == 'nt':
            import msvcrt
            lock.write('0')
            lock.flush()
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        messagebox.showerror('Soirée Bourse', 'L’application est déjà ouverte depuis ce dossier.')
        root.destroy()
        return 1
    from bourse.ui import App
    App(root, ROOT)
    root.deiconify()
    root.mainloop()
    lock.close()
    return 0


if __name__ == '__main__':
    try:
        ensure_project_runtime()
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f'Erreur : {exc}', file=sys.stderr)
        sys.exit(1)
    sys.exit(main())
