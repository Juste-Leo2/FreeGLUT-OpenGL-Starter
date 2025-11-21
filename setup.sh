#!/bin/bash

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

# Intercepte les erreurs et appelle la fonction error_exit
trap 'error_exit $LINENO "$BASH_COMMAND"' ERR

# --- Fonction pour installer les dépendances système ---
install_system_dependencies() {
    local needs_install=false
    # On vérifie les outils de base
    for cmd in g++ curl tar pkg-config; do
        if ! command -v "$cmd" &> /dev/null; then
            needs_install=true
            break
        fi
    done

    # Note: Sur Linux, Qt6 nécessite des libs XCB spécifiques souvent absentes
    # On force la vérification/installation pour s'assurer que Qt6 ne plante pas
    
    echo "   Vérification et installation des dépendances système..."
    echo "   (Outils de compilation, OpenGL et dépendances d'affichage pour Qt6)"
    echo "   Veuillez entrer votre mot de passe administrateur (sudo) si demandé."
    
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$ID
    else
        echo "ECHEC: Impossible de détecter la distribution Linux." >&2
        exit 1
    fi

    case $OS in
        ubuntu|debian|linuxmint|pop)
            sudo apt-get update
            # AJOUT: libxcb-cursor0 et libxkbcommon-x11-0 sont critiques pour PyQt6
            sudo apt-get install -y build-essential curl pkg-config \
                libgl1-mesa-dev libglu1-mesa-dev libx11-dev \
                libxrandr-dev libxinerama-dev libxcursor-dev \
                libxcb-cursor0 libxkbcommon-x11-0 libxcb-icccm4 \
                libxcb-image0 libxcb-keysyms1 libxcb-render-util0
            ;;
        fedora|centos|rhel)
            # AJOUT: Dependances XCB pour Fedora
            sudo dnf install -y @"Development Tools" curl pkg-config \
                mesa-libGL-devel mesa-libGLU-devel libX11-devel \
                libXrandr-devel libXinerama-devel libXcursor-devel \
                xcb-util-cursor libxkbcommon-x11-devel
            ;;
        arch|manjaro)
            # AJOUT: Dependances XCB pour Arch
            sudo pacman -Syu --noconfirm base-devel curl pkg-config \
                mesa libglu libx11 libxrandr libxinerama libxcursor \
                libxcb libxkbcommon-x11
            ;;
        *)
            echo "ATTENTION: Distribution '$OS' non reconnue." >&2
            echo "Assurez-vous d'avoir installé gcc, OpenGL et les libs 'xcb' pour Qt6." >&2
            ;;
    esac
    echo "   [OK] Dépendances système installées avec succès."
}


echo "=========================================================="
echo "      INITIALISATION DE L'ENVIRONNEMENT (LINUX)"
echo "=========================================================="
echo ""

# --- ETAPE 1: Vérification et installation des dépendances système ---
echo "[1/8] Vérification des dépendances système..."
install_system_dependencies

# --- Etape 2: Installation de 'uv' ---
echo "[2/8] Installation de 'uv'..."
if ! command -v "$HOME/.local/bin/uv" &> /dev/null; then
    curl -LsSf https://astral.sh/uv/install.sh | sh > /dev/null
fi
UV_EXE="$HOME/.local/bin/uv"
# Fallback si uv est dans le path global
if [ ! -f "$UV_EXE" ] && command -v uv &> /dev/null; then
    UV_EXE=$(command -v uv)
fi

if [ ! -f "$UV_EXE" ] && [ -z "$UV_EXE" ]; then
    echo "ECHEC: uv non trouvé." >&2
    exit 1
fi
echo "   [OK] uv installé."

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
    echo "   Téléchargement de l'archive CMake..."
    curl -L -o cmake.tar.gz "https://github.com/Kitware/CMake/releases/download/v3.29.3/cmake-3.29.3-linux-x86_64.tar.gz"
    
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
    echo "   Téléchargement de l'exécutable Conan..."
    curl -L -o conan.tgz "https://github.com/conan-io/conan/releases/download/2.4.1/conan-2.4.1-linux-x86_64.tgz"
    
    echo "   Création du dossier de destination..."
    mkdir -p conan_cli
    
    echo "   Extraction de l'archive dans le dossier dédié..."
    tar -xzf conan.tgz -C ./conan_cli
    rm conan.tgz
fi
cd ..
echo "   [OK] Conan CLI configuré."

# --- Etape 7: Préparation de l'environnement de compilation ---
echo "[7/8] Préparation de l'environnement de compilation..."
export CMAKE_BIN_PATH="$(pwd)/vendor/cmake/bin"
export PATH="$CMAKE_BIN_PATH:$PATH"
# Détection dynamique de la version GCC système
GCC_VERSION=$(g++ -dumpversion | cut -d. -f1)

echo "   Compilateur détecté: GCC $GCC_VERSION"

(
    echo "[settings]"
    echo "arch=x86_64"
    echo "os=Linux"
    echo "compiler=gcc"
    echo "compiler.version=$GCC_VERSION"
    echo "compiler.libcxx=libstdc++11"
    echo "build_type=Release"
    echo "[conf]"
    echo "tools.build:compiler_executables={'c': 'gcc', 'cpp': 'g++'}"
    # On permet à Conan d'installer des paquets système manquants si besoin
    echo "tools.system.package_manager:mode=install" 
    echo "tools.system.package_manager:sudo=true"
) > linux_profile
echo "   [OK] Profil Conan 'linux_profile' généré."

# --- Etape 8: Installation de freeglut et génération des infos ---
echo "[8/8] Installation de freeglut via Conan et génération du JSON..."
mkdir -p build
CONAN_EXE="$(pwd)/vendor/conan_cli/bin/conan"

if [ ! -f "$CONAN_EXE" ]; then
    echo "ECHEC: conan non trouvé à l'emplacement attendu!" >&2
    exit 1
fi
source ./.venv/bin/activate

# Force la reconstruction si libs système manquantes
"$CONAN_EXE" install . --output-folder=build --profile:host=./linux_profile --profile:build=./linux_profile --build=missing --format=json > build/conan_info.json

deactivate
echo "   [OK] Fichier d'information 'conan_info.json' généré."

echo ""
echo "=========================================================="
echo "              INSTALLATION TERMINEE !"
echo "=========================================================="
echo ""
# Sur Linux, pas besoin de 'pause' bloquant, mais read est utile si lancé depuis un explorateur
if [ -t 0 ]; then
    read -p "Appuyez sur [Entrée] pour quitter..."
fi