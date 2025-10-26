# src/config.py

import os
import platform
import shutil # <-- 1. Importer le module shutil

# --- Chemins de base ---
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENDOR_DIR = os.path.join(ROOT_DIR, "vendor")
BUILD_DIR = os.path.join(ROOT_DIR, "build")
SAVE_DIR = os.path.join(ROOT_DIR, "saves")

# --- Configuration du compilateur ---
if platform.system() == "Windows":
    COMPILER_PATH = os.path.join(VENDOR_DIR, "mingw64", "bin", "g++.exe")
    OUTPUT_EXECUTABLE = os.path.join(BUILD_DIR, "user_app.exe")
else: # Pour Linux, macOS, etc.
    # 2. Utiliser shutil.which() pour trouver le chemin absolu de g++
    COMPILER_PATH = shutil.which("g++")
    OUTPUT_EXECUTABLE = os.path.join(BUILD_DIR, "user_app")

# 3. Ajouter une vérification pour s'assurer que le compilateur a bien été trouvé
if not COMPILER_PATH or not os.path.exists(COMPILER_PATH):
    # Cette erreur s'affichera si shutil.which("g++") renvoie None
    raise FileNotFoundError(f"Le compilateur n'a pas pu être localisé. Vérifiez que 'g++' est bien installé et dans le PATH système. Chemin attendu: {COMPILER_PATH}")


# --- Configuration de l'éditeur ---
DEFAULT_START_FILE = os.path.join(SAVE_DIR, "main.cpp")
SESSION_FILE = os.path.join(ROOT_DIR, "session.json")

# --- Code C++ par défaut ---
DEFAULT_CPP_CODE = """#include <GL/freeglut.h>

void display() {
    glClear(GL_COLOR_BUFFER_BIT);
    // Vôtre code OpenGL ici
    
    glFlush();
}

int main(int argc, char** argv) {
    glutInit(&argc, argv);
    glutCreateWindow("Projet OpenGL");
    glutInitDisplayMode(GLUT_SINGLE | GLUT_RGB);
    glutInitWindowSize(500, 500);
    glutInitWindowPosition(100, 100);
    glClearColor(0.2f, 0.2f, 0.2f, 1.0f);
    glutDisplayFunc(display);
    glutMainLoop();
    return 0;
}
"""