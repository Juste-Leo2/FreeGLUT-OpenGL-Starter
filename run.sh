#!/bin/bash

# Arrête le script si une commande échoue
set -e

# Vérifie si le dossier de l'environnement virtuel existe.
if [ ! -d ".venv" ]; then
    echo "Erreur: L'environnement Python n'a pas été trouvé."
    echo "Veuillez d'abord exécuter './setup.sh' pour effectuer l'installation."
    read -p "Appuyez sur [Entrée] pour quitter..."
    exit 1
fi

# Chemin vers l'exécutable uv
UV_EXE="$HOME/.local/bin/uv"

echo "Activation de l'environnement Python..."
source ./.venv/bin/activate

echo "Lancement de l'éditeur de code..."
"$UV_EXE" run main.py

echo "Fermeture de l'environnement..."
deactivate