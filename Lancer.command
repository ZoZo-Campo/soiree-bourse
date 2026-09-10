#!/bin/zsh
cd "${0:A:h}" || exit 1
if [[ ! -x .venv/bin/python ]] || ! .venv/bin/python -c 'import tkinter, pymysql' >/dev/null 2>&1; then
  print 'Préparation automatique du pilote MySQL…'
  ./installer.sh --install-only || {
    print 'Installation impossible. Voir le message ci-dessus.'
    read '?Appuyer sur Entrée pour fermer.'
    exit 1
  }
fi
if [[ ! -x .venv/bin/python ]]; then
  print 'Environnement Python du projet introuvable.'
  read '?Appuyer sur Entrée pour fermer.'
  exit 1
fi
exec .venv/bin/python app.py
