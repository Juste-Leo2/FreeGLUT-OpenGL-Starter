# src/file_manager.py
import os
from tkinter import filedialog, messagebox
from . import config

class FileManager:
    def __init__(self, app):
        self.app = app
        self.open_tabs = {}

    def on_text_changed_proxy(self, event=None):
        tab_name = self.app.get_current_tab_name()
        if not tab_name or tab_name not in self.open_tabs: return
        
        info = self.open_tabs[tab_name]

        if not info["is_dirty"]:
            info["is_dirty"] = True
            new_name = f"{tab_name}*"
            self._rename_tab_data(tab_name, new_name)

    def _rename_tab_data(self, old_name, new_name):
        self.app.rename_tab(old_name, new_name)
        info = self.open_tabs.pop(old_name)
        self.open_tabs[new_name] = info
        self.app.set_active_tab(new_name)

    def add_tab(self, filepath=None, content=""):
        base_name = os.path.basename(filepath) if filepath else "Nouveau"
        tab_name = base_name
        i = 1
        existing_names = list(self.open_tabs.keys())
        while tab_name in existing_names or f"{tab_name}*" in existing_names:
            name, ext = os.path.splitext(base_name)
            tab_name = f"{name}_{i}{ext}"
            i += 1
        
        editor, linenumbers = self.app.add_editor_tab(tab_name, content)
        if not editor: return

        self.open_tabs[tab_name] = {
            "editor": editor, "linenumbers": linenumbers, 
            "filepath": filepath, "is_dirty": False
        }

        if filepath is None:
            self.on_text_changed_proxy()

    def new_file(self):
        info = self.get_current_tab_info()
        tab_name = self.app.get_current_tab_name()
        if info and info["is_dirty"]:
            response = messagebox.askyesnocancel("Sauvegarder ?", f"Voulez-vous enregistrer les modifications de {tab_name.rstrip('*')} ?")
            if response is True:
                if not self.save_current_file(): return
            elif response is None: return
        self.add_tab(filepath=None, content=config.DEFAULT_CPP_CODE)

    def open_file(self, filepath):
        for name, info in self.open_tabs.items():
            if info["filepath"] == filepath:
                self.app.set_active_tab(name)
                return
        try:
            with open(filepath, "r", encoding="utf-8") as f: content = f.read()
            self.add_tab(filepath, content)
        except Exception as e:
            self.app.show_warning("Erreur d'ouverture", f"Impossible d'ouvrir le fichier {filepath}:\n{e}")

    def open_file_dialog(self):
        filepaths = filedialog.askopenfilenames(title="Importer un fichier C++", filetypes=[("Fichiers C++", "*.cpp *.h"), ("Tous les fichiers", "*.*")])
        for filepath in filepaths:
            self.open_file(filepath)

    def get_current_tab_info(self):
        current_tab_name = self.app.get_current_tab_name()
        return self.open_tabs.get(current_tab_name)

    def get_open_filepaths_in_order(self):
        ordered_paths = []
        ordered_tab_names = self.app.get_all_tab_names()
        for tab_name in ordered_tab_names:
            info = self.open_tabs.get(tab_name)
            if info and info["filepath"]:
                ordered_paths.append(info["filepath"])
        return ordered_paths

    def save_current_file(self):
        current_tab_name = self.app.get_current_tab_name()
        info = self.open_tabs.get(current_tab_name)
        if info is None: return None
        
        # Si le fichier n'a pas de chemin, on délègue à "Enregistrer sous"
        if info["filepath"] is None:
            return self.save_current_file_as()
        
        # Logique de sauvegarde principale
        content = info["editor"].get("1.0", "end-1c")
        with open(info["filepath"], "w", encoding="utf-8") as f: f.write(content)
        
        # Mise à jour de l'état et de l'UI
        if info["is_dirty"]:
            info["is_dirty"] = False
            # Le nouveau nom est TOUJOURS basé sur le nom du fichier, c'est plus sûr
            new_name = os.path.basename(info["filepath"])
            if current_tab_name != new_name:
                self._rename_tab_data(current_tab_name, new_name)
        
        self.app.append_output(f"Fichier '{os.path.basename(info['filepath'])}' enregistré.\n")
        
        # Forcer le rafraîchissement de l'UI pour que tout soit visible
        self.app.update()
        
        return info["filepath"]

    def save_current_file_as(self):
        info = self.get_current_tab_info()
        if info is None: return None

        new_filepath = filedialog.asksaveasfilename(
            initialdir=config.SAVE_DIR, title="Enregistrer sous...", 
            defaultextension=".cpp", filetypes=[("Fichiers C++", "*.cpp"), ("Tous les fichiers", "*.*")]
        )
        if not new_filepath: return None

        # La seule chose que fait "Enregistrer sous", c'est assigner un nouveau chemin
        info["filepath"] = new_filepath
        info["is_dirty"] = True # On s'assure qu'il est marqué comme "modifié" pour forcer la mise à jour
        
        self.app.append_output(f"Fichier enregistré sous '{os.path.basename(new_filepath)}'.\n")
        
        # ...puis on appelle la fonction de sauvegarde standard qui fera tout le travail.
        return self.save_current_file()

    def close_current_tab(self):
        tab_name = self.app.get_current_tab_name()
        info = self.open_tabs.get(tab_name)
        if not info: return

        if info["is_dirty"]:
            response = messagebox.askyesnocancel("Sauvegarder ?", f"Voulez-vous enregistrer les modifications de {tab_name.rstrip('*')} ?")
            if response is True:
                if not self.save_current_file(): return
            elif response is None: return
        
        self.app.delete_tab(tab_name)
        self.open_tabs.pop(tab_name)

        if not self.open_tabs:
            self.add_tab(filepath=None, content=config.DEFAULT_CPP_CODE)
        
    def has_dirty_files(self):
        return any(info["is_dirty"] for info in self.open_tabs.values())