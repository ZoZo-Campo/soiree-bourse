#!/usr/bin/env python3
"""Lancer avec Python 3.11+ et Tkinter. Aucun réseau au lancement."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def restart_in_project_venv():
    """Use the project environment even when app.py is started with python3."""
    candidates = (
        ROOT / '.venv' / 'bin' / 'python',
        ROOT / '.venv' / 'Scripts' / 'python.exe',
    )
    for candidate in candidates:
        if not candidate.is_file():
            continue
        try:
            already_using_venv = Path(sys.executable).resolve() == candidate.resolve()
        except OSError:
            already_using_venv = False
        if not already_using_venv:
            os.execv(str(candidate), [str(candidate), str(ROOT / 'app.py'), *sys.argv[1:]])
        return


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
    restart_in_project_venv()
    sys.exit(main())
