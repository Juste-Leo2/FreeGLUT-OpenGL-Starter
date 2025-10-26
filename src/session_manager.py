# src/session_manager.py
import json
import os
from . import config

def save_session(data):
    """
    Sauvegarde les données de la session (fichiers ouverts, fichier actif) dans un fichier JSON.
    """
    try:
        with open(config.SESSION_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
    except IOError as e:
        print(f"Erreur lors de la sauvegarde de la session : {e}")

def load_session():
    """
    Charge les données de la session depuis le fichier JSON.
    Retourne None si le fichier n'existe pas ou est invalide.
    """
    if not os.path.exists(config.SESSION_FILE):
        return None
    try:
        with open(config.SESSION_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data
    except (json.JSONDecodeError, IOError) as e:
        print(f"Erreur lors du chargement de la session, le fichier est peut-être corrompu : {e}")
        return None