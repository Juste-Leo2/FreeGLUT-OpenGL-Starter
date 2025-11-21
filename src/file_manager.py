import os
from PyQt6.QtWidgets import QFileDialog, QMessageBox
from . import config

class FileManager:
    def __init__(self, app):
        self.app = app
        self.open_tabs = {} # Clé: Tab Name, Valeur: dict info

    def on_text_changed_proxy(self):
        tab_name = self.app.get_current_tab_name()
        if not tab_name or tab_name not in self.open_tabs: return
        
        info = self.open_tabs[tab_name]
        if not info["is_dirty"]:
            info["is_dirty"] = True
            new_name = f"{tab_name}*"
            self._rename_tab_data(tab_name, new_name)

    def _rename_tab_data(self, old_name, new_name):
        self.app.set_tab_name(old_name, new_name)
        info = self.open_tabs.pop(old_name)
        self.open_tabs[new_name] = info

    def add_tab(self, filepath=None, content=""):
        base_name = os.path.basename(filepath) if filepath else "Nouveau"
        tab_name = base_name
        i = 1
        existing = list(self.open_tabs.keys())
        while tab_name in existing or f"{tab_name}*" in existing:
            name, ext = os.path.splitext(base_name)
            tab_name = f"{name}_{i}{ext}"
            i += 1
        
        editor = self.app.add_editor_tab(tab_name, content)
        self.open_tabs[tab_name] = {
            "editor": editor, 
            "filepath": filepath, 
            "is_dirty": False
        }
        
        # Si nouveau fichier, on force la détection 'modifié' si l'utilisateur tape
        if filepath is None:
            # Petite astuce pour ne pas marquer "dirty" immédiatement à l'ouverture
            pass 

    def new_file(self):
        self.add_tab(filepath=None, content=config.DEFAULT_CPP_CODE)

    def open_file(self, filepath):
        # Vérifier si déjà ouvert
        for name, info in self.open_tabs.items():
            if info["filepath"] == filepath or info["filepath"] == os.path.abspath(filepath):
                self.app.set_active_tab(name)
                return
        
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            self.add_tab(filepath, content)
        except Exception as e:
            self.app.append_output(f"Erreur ouverture {filepath}: {e}\n")

    def open_file_dialog(self):
        files, _ = QFileDialog.getOpenFileNames(
            self.app, 
            "Importer", 
            "", 
            "C++ Files (*.cpp *.h);;All Files (*)"
        )
        if files:
            for f in files:
                self.open_file(f)

    def save_current_file(self):
        tab_name = self.app.get_current_tab_name()
        if not tab_name: return None
        info = self.open_tabs.get(tab_name)
        
        if info["filepath"] is None:
            return self.save_current_file_as()
        
        content = info["editor"].toPlainText()
        try:
            with open(info["filepath"], "w", encoding="utf-8") as f:
                f.write(content)
            
            if info["is_dirty"]:
                info["is_dirty"] = False
                clean_name = tab_name.rstrip('*')
                if tab_name != clean_name:
                    self._rename_tab_data(tab_name, clean_name)
            
            self.app.append_output(f"Enregistré: {os.path.basename(info['filepath'])}\n")
            return info["filepath"]
        except Exception as e:
            self.app.append_output(f"Erreur sauvegarde: {e}\n")
            return None

    def save_current_file_as(self):
        tab_name = self.app.get_current_tab_name()
        if not tab_name: return None
        info = self.open_tabs.get(tab_name)

        path, _ = QFileDialog.getSaveFileName(
            self.app, 
            "Enregistrer sous", 
            config.SAVE_DIR, 
            "C++ Files (*.cpp);;All Files (*)"
        )
        
        if not path: return None
        
        info["filepath"] = path
        info["is_dirty"] = True # Pour forcer le renommage dans save_current_file
        return self.save_current_file()

    def close_current_tab(self):
        idx = self.app.tab_widget.currentIndex()
        if idx != -1:
            self.close_tab_by_index(idx)

    def close_tab_by_index(self, index):
        tab_name = self.app.tab_widget.tabText(index)
        info = self.open_tabs.get(tab_name)
        
        if info and info["is_dirty"]:
            reply = QMessageBox.question(
                self.app, "Sauvegarder ?", 
                f"Sauvegarder les modifications de {tab_name} ?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                if not self.save_current_file(): return # Annulé ou échec
            elif reply == QMessageBox.StandardButton.Cancel:
                return

        self.app.tab_widget.removeTab(index)
        if tab_name in self.open_tabs:
            del self.open_tabs[tab_name]

    def get_current_tab_info(self):
        name = self.app.get_current_tab_name()
        return self.open_tabs.get(name)

    def get_open_filepaths_in_order(self):
        paths = []
        for i in range(self.app.tab_widget.count()):
            name = self.app.tab_widget.tabText(i)
            info = self.open_tabs.get(name)
            if info and info["filepath"]:
                paths.append(info["filepath"])
        return paths

    def has_dirty_files(self):
        return any(i["is_dirty"] for i in self.open_tabs.values())