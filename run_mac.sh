#!/bin/bash

# Se place dans le dossier du script (important sur mac si lancé via Finder)
cd "$(dirname "$0")"

# Arrête le script si une commande échoue
set -e

# Vérifie si le dossier de l'environnement virtuel existe.
if [ ! -d ".venv" ]; then
    echo "Erreur: L'environnement Python n'a pas été trouvé."
    echo "Veuillez d'abord exécuter './setup.sh' pour effectuer l'installation."
    # Sur mac, le terminal peut se fermer tout de suite, on ajoute une pause
    read -p "Appuyez sur [Entrée] pour quitter..."
    exit 1
fi

# Détection de uv (local ou global)
if [ -f "$HOME/.local/bin/uv" ]; then
    UV_EXE="$HOME/.local/bin/uv"
elif command -v uv &> /dev/null; then
    UV_EXE=$(command -v uv)
else
    echo "Erreur: Exécutable 'uv' non trouvé."
    read -p "Appuyez sur [Entrée] pour quitter..."
    exit 1
fi

echo "Activation de l'environnement Python..."
source ./.venv/bin/activate

echo "Lancement de l'application..."
# Utilisation de 'python' direct ou via 'uv run'
"$UV_EXE" run main.py

echo "Fermeture de l'environnement..."
deactivate

# Optionnel : Pause à la fin pour voir les erreurs si lancé depuis le Finder
# read -p "Appuyez sur [Entrée] pour fermer..."