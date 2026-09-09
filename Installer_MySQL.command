#!/bin/zsh
cd "${0:A:h}" || exit 1
if [[ -x /opt/homebrew/bin/python3 ]]; then
  PYTHON=/opt/homebrew/bin/python3
else
  PYTHON=python3
fi
"$PYTHON" -m venv .venv || exit 1
.venv/bin/python -m pip install -r requirements.txt || exit 1
print 'Installation terminée. Renseigner config.ini avant d’utiliser le mode Fouaille.'
read '?Appuyer sur Entrée pour fermer.'
