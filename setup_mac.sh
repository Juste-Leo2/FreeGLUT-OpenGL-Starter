#!/bin/bash

# Se place dans le dossier du script (utile si lancé via le Finder)
cd "$(dirname "$0")"

# Arrête le script si une commande échoue
set -e

# --- Fonction pour gérer les erreurs ---
error_exit() {
    echo ""
    echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
    echo "   UNE ERREUR EST SURVENUE PENDANT L'INSTALLATION."
    echo "   Ligne $1: $2"
    echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
    echo ""
    exit 1
}

trap 'error_exit $LINENO "$BASH_COMMAND"' ERR

# --- Détection de l'architecture (Apple Silicon vs Intel) ---
ARCH_NAME=$(uname -m)
if [ "$ARCH_NAME" = "arm64" ]; then
    echo "   Architecture détectée : Apple Silicon (arm64)"
    CONAN_ARCH="armv8"
    MAC_ARCH="arm64"
else
    echo "   Architecture détectée : Intel (x86_64)"
    CONAN_ARCH="x86_64"
    MAC_ARCH="x86_64"
fi

# --- Fonction pour installer les dépendances système ---
install_system_dependencies() {
    echo "   Vérification des outils de développement..."

    # 1. Vérifier les Command Line Tools (clang, git, make)
    if ! xcode-select -p &> /dev/null; then
        echo "   Installation des Xcode Command Line Tools..."
        xcode-select --install
        echo "   Une fenêtre a dû s'ouvrir. Veuillez terminer l'installation avant de relancer ce script."
        exit 1
    fi

    # 2. Vérifier Homebrew (Standard sur macOS pour les paquets)
    if ! command -v brew &> /dev/null; then
        echo "ATTENTION: Homebrew n'est pas installé."
        echo "Il est recommandé d'installer Homebrew pour gérer pkg-config et autres libs."
        echo "Visitez https://brew.sh/ pour l'installer."
        read -p "Voulez-vous continuer sans Homebrew ? (risque d'échec) [o/N] " response
        if [[ ! "$response" =~ ^[oO] ]]; then
            exit 1
        fi
    else
        # Installation de pkg-config (souvent requis par Python/Qt build extensions)
        if ! command -v pkg-config &> /dev/null; then
            echo "   Installation de pkg-config via Homebrew..."
            brew install pkg-config
        fi
    fi

    echo "   [OK] Dépendances système vérifiées."
}


echo "=========================================================="
echo "      INITIALISATION DE L'ENVIRONNEMENT (MACOS)"
echo "=========================================================="
echo ""

# --- ETAPE 1: Vérification des dépendances système ---
echo "[1/8] Vérification des dépendances système..."
install_system_dependencies

# --- Etape 2: Installation de 'uv' ---
echo "[2/8] Installation de 'uv'..."
# Sur mac, uv s'installe aussi dans .local ou via brew. On garde le script curl pour l'uniformité.
if ! command -v uv &> /dev/null && [ ! -f "$HOME/.local/bin/uv" ]; then
    curl -LsSf https://astral.sh/uv/install.sh | sh > /dev/null
fi

# Définition du chemin vers uv
if [ -f "$HOME/.local/bin/uv" ]; then
    UV_EXE="$HOME/.local/bin/uv"
elif command -v uv &> /dev/null; then
    UV_EXE=$(command -v uv)
else
    echo "ECHEC: uv non trouvé après installation." >&2
    exit 1
fi
echo "   [OK] uv installé ($UV_EXE)."

# --- Etape 3: Création de l'environnement Python ---
echo "[3/8] Création de l'environnement Python..."
"$UV_EXE" venv -p 3.11 > /dev/null
echo "   [OK] Environnement Python créé."

# --- Etape 4: Installation des dépendances Python ---
echo "[4/8] Installation des dépendances Python (PyQt6)..."
source ./.venv/bin/activate
"$UV_EXE" pip install -r requirements.txt > /dev/null
deactivate
echo "   [OK] Dépendances Python installées."

# --- Etape 5: Téléchargement de CMake ---
echo "[5/8] Téléchargement de CMake..."
mkdir -p vendor
cd vendor
if [ ! -d "cmake" ]; then
    echo "   Téléchargement de l'archive CMake (Universal Mac)..."
    # URL pour macOS Universal (fonctionne sur Intel et M1/M2/M3)
    curl -L -o cmake.tar.gz "https://github.com/Kitware/CMake/releases/download/v3.29.3/cmake-3.29.3-macos-universal.tar.gz"
    
    echo "   Extraction de l'archive..."
    mkdir -p cmake
    tar --strip-components=1 -xzf cmake.tar.gz -C ./cmake
    rm cmake.tar.gz
fi
cd ..
echo "   [OK] CMake configuré."

# --- Etape 6: Téléchargement de Conan CLI ---
echo "[6/8] Téléchargement de Conan CLI..."
cd vendor
if [ ! -d "conan_cli" ]; then
    echo "   Téléchargement de l'exécutable Conan pour $MAC_ARCH..."
    # URL dynamique selon l'architecture mac
    CONAN_URL="https://github.com/conan-io/conan/releases/download/2.4.1/conan-2.4.1-macos-${MAC_ARCH}.tgz"
    
    curl -L -o conan.tgz "$CONAN_URL"
    
    echo "   Création du dossier de destination..."
    mkdir -p conan_cli
    
    echo "   Extraction de l'archive..."
    tar -xzf conan.tgz -C ./conan_cli
    rm conan.tgz
fi
cd ..
echo "   [OK] Conan CLI configuré."

# --- Etape 7: Préparation de l'environnement de compilation ---
echo "[7/8] Préparation de l'environnement de compilation..."

# ATTENTION: Sur Mac, CMake est dans un bundle .app
export CMAKE_BIN_PATH="$(pwd)/vendor/cmake/CMake.app/Contents/bin"
export PATH="$CMAKE_BIN_PATH:$PATH"

# Détection version Apple Clang
if ! command -v clang &> /dev/null; then
    echo "ERREUR: Clang non trouvé. Avez-vous installé Xcode Command Line Tools ?"
    exit 1
fi
CLANG_VERSION=$(clang --version | head -n1 | awk '{print $4}')
# On garde juste le Major.Minor (ex: 15.0.0 -> 15.0)
CLANG_VERSION_SHORT=$(echo $CLANG_VERSION | cut -d. -f1-2)

echo "   Compilateur détecté: Apple Clang $CLANG_VERSION"

(
    echo "[settings]"
    echo "os=Macos"
    echo "arch=$CONAN_ARCH"
    echo "compiler=apple-clang"
    echo "compiler.version=$CLANG_VERSION_SHORT"
    echo "compiler.libcxx=libc++" 
    echo "build_type=Release"
    echo "[conf]"
    # Sur Mac, pas besoin de tools.system.package_manager:mode=install de la même façon que Linux
    echo "tools.system.package_manager:tool=brew"
) > macos_profile
echo "   [OK] Profil Conan 'macos_profile' généré."

# --- Etape 8: Installation de freeglut et génération des infos ---
echo "[8/8] Installation des libs via Conan et génération du JSON..."
mkdir -p build
CONAN_EXE="$(pwd)/vendor/conan_cli/bin/conan"

if [ ! -f "$CONAN_EXE" ]; then
    echo "ECHEC: conan non trouvé à l'emplacement attendu!" >&2
    exit 1
fi

# On doit enlever la quarantaine macOS sur les binaires téléchargés sinon macOS bloque l'exécution
echo "   Déblocage de sécurité macOS pour les binaires téléchargés..."
xattr -d com.apple.quarantine "$CONAN_EXE" 2>/dev/null || true
xattr -d com.apple.quarantine "$CMAKE_BIN_PATH/cmake" 2>/dev/null || true

source ./.venv/bin/activate

# Installation Conan
"$CONAN_EXE" install . --output-folder=build --profile:host=./macos_profile --profile:build=./macos_profile --build=missing --format=json > build/conan_info.json

deactivate
echo "   [OK] Fichier d'information 'conan_info.json' généré."

echo ""
echo "=========================================================="
echo "              INSTALLATION TERMINEE !"
echo "=========================================================="
echo ""