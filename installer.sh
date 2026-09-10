#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
INSTALL_ONLY=false

if [[ "${1:-}" == "--install-only" ]]; then
  INSTALL_ONLY=true
elif [[ $# -gt 0 ]]; then
  echo "Usage : ./installer.sh [--install-only]"
  exit 2
fi

find_python() {
  local candidate
  for candidate in python3 /opt/homebrew/bin/python3 /usr/local/bin/python3; do
    if command -v "$candidate" >/dev/null 2>&1 && "$candidate" - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if sys.version_info >= (3, 11) else 1)
PY
    then
      command -v "$candidate"
      return 0
    fi
  done
  return 1
}

PYTHON="$(find_python || true)"
if [[ -z "$PYTHON" ]]; then
  echo "Erreur : Python 3.11 ou plus récent est nécessaire."
  echo "Téléchargement officiel : https://www.python.org/downloads/"
  exit 1
fi

if ! "$PYTHON" -c 'import tkinter' >/dev/null 2>&1; then
  echo "Erreur : Tkinter est absent."
  if [[ "$(uname -s)" == "Darwin" ]]; then
    echo "Installe Python depuis https://www.python.org/downloads/ puis relance ce script."
  else
    echo "Sur Debian/Ubuntu : sudo apt install python3-tk python3-venv"
  fi
  exit 1
fi

cd "$ROOT"
echo "Création de l’environnement Python avec $PYTHON..."
if [[ ! -x .venv/bin/python ]]; then
  "$PYTHON" -m venv .venv
fi

echo "Installation des dépendances..."
.venv/bin/python -m pip install --disable-pip-version-check -r requirements.txt

if [[ ! -f config.ini ]]; then
  umask 077
  cp config.example.ini config.ini
  echo "Configuration locale créée : config.ini"
fi
chmod 600 config.ini
mkdir -p data exports
chmod 700 data exports
chmod +x Lancer.command Installer_MySQL.command installer.sh

echo "Vérification de l’installation..."
.venv/bin/python -c 'import tkinter, pymysql'
.venv/bin/python -m unittest discover -s tests -q

echo
echo "Installation terminée."
echo "Mode démonstration : aucune configuration supplémentaire n’est nécessaire."
echo "Mode Fouaille : renseigner d’abord la section [mysql] de config.ini."

if [[ "$INSTALL_ONLY" == false ]]; then
  echo "Lancement de Soirée Bourse..."
  exec .venv/bin/python app.py
fi
