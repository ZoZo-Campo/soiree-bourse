#!/bin/zsh
cd "${0:A:h}" || exit 1
./installer.sh --install-only || exit 1
print 'Installation terminée. Renseigner config.ini avant d’utiliser le mode Fouaille.'
read '?Appuyer sur Entrée pour fermer.'
