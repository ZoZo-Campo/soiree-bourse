#!/bin/zsh
cd "${0:A:h}" || exit 1
if [[ -x .venv/bin/python ]]; then
  PYTHON=.venv/bin/python
elif [[ -x /opt/homebrew/bin/python3 ]]; then
  PYTHON=/opt/homebrew/bin/python3
else
  PYTHON=python3
fi
if ! "$PYTHON" -c 'import tkinter' >/dev/null 2>&1; then
  print 'Python avec Tkinter est nécessaire. Voir LISEZ_MOI.md.'
  read '?Appuyer sur Entrée pour fermer.'
  exit 1
fi
"$PYTHON" app.py
if [[ $? -ne 0 ]]; then
  read '?Erreur au lancement. Appuyer sur Entrée pour fermer.'
fi
