# src/app.py
import customtkinter as ctk
import tkinter as tk
import os
from tkinter import messagebox
from tkcode import CodeEditor

from . import config
from . import session_manager
from .file_manager import FileManager
from .build_manager import BuildManager

# Le widget pour les numéros de ligne est maintenant dans ce fichier
class LineNumbersWidget(tk.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.text_widget = None

    def attach(self, text_widget):
        self.text_widget = text_widget
        self.text_widget.bind("<<Modified>>", self._on_text_modified, add='+')
        self.text_widget.bind("<Configure>", self._on_text_modified, add='+')
        self.text_widget.bind("<MouseWheel>", self._on_text_scroll, add='+')
        self.text_widget.bind("<Button-4>", self._on_text_scroll, add='+')
        self.text_widget.bind("<Button-5>", self._on_text_scroll, add='+')
        self.configure(bg="#2B2B2B", highlightthickness=0)

    def _on_text_scroll(self, event=None):
        self.after(1, self.redraw)

    def _on_text_modified(self, event=None):
        self.text_widget.event_generate("<<Change>>", when="tail")
        self.after_idle(self.redraw)

    def redraw(self, *args):
        if not self.text_widget: return
        self.delete("all")
        i = self.text_widget.index("@0,0")
        while True:
            dline = self.text_widget.dlineinfo(i)
            if dline is None: break
            line_num_str = str(i).split(".")[0]
            y = dline[1]
            self.create_text(self.winfo_width() - 5, y, anchor="ne", text=line_num_str, fill="#606366", font=("Consolas", 12))
            i = self.text_widget.index(f"{i}+1line")
            if not i: break

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Éditeur C++ / OpenGL")
        self.geometry("1200x800")
        ctk.set_appearance_mode("dark")

        self._ensure_directories_exist()

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Les managers sont créés en premier
        self.file_manager = FileManager(self)
        self.build_manager = BuildManager(self)
        
        # L'UI est configurée directement ici
        self.setup_layout()
        self.connect_commands()
        self.show_output_panel()
        
        # Démarrage
        self._load_session_or_start_default()
        
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _ensure_directories_exist(self):
        for path in [config.SAVE_DIR, config.BUILD_DIR]:
            if not os.path.exists(path):
                os.makedirs(path)

    # --- MÉTHODES DE GESTION DE L'UI (ANCIENNEMENT DANS UIManager) ---

    def setup_layout(self):
        self._create_toolbar()
        self._create_main_panes()
        self._create_output_panel()

    def connect_commands(self):
        self.new_button.configure(command=self.file_manager.new_file)
        self.import_button.configure(command=self.file_manager.open_file_dialog)
        self.save_button.configure(command=self.file_manager.save_current_file)
        self.save_as_button.configure(command=self.file_manager.save_current_file_as)
        self.close_tab_button.configure(command=self.file_manager.close_current_tab)
        
        self.compile_button.configure(command=self.build_manager.compile_code)
        self.run_button.configure(command=self.build_manager.run_app)
        self.compile_run_button.configure(command=self.build_manager.compile_and_run_code)

    def _create_toolbar(self):
        self.toolbar = ctk.CTkFrame(self, height=40, fg_color="transparent")
        self.toolbar.grid(row=0, column=0, padx=10, pady=(10, 0), sticky="ew")
        
        self.new_button = ctk.CTkButton(self.toolbar, text="Nouveau")
        self.new_button.pack(side="left", padx=5)
        self.import_button = ctk.CTkButton(self.toolbar, text="Importer")
        self.import_button.pack(side="left", padx=5)
        self.save_button = ctk.CTkButton(self.toolbar, text="Enregistrer")
        self.save_button.pack(side="left", padx=5)
        self.save_as_button = ctk.CTkButton(self.toolbar, text="Enregistrer sous")
        self.save_as_button.pack(side="left", padx=5)
        self.close_tab_button = ctk.CTkButton(self.toolbar, text="Fermer l'onglet")
        self.close_tab_button.pack(side="left", padx=5)
        self.compile_button = ctk.CTkButton(self.toolbar, text="Compiler")
        self.compile_button.pack(side="left", padx=20)
        self.run_button = ctk.CTkButton(self.toolbar, text="Exécuter", state="disabled")
        self.run_button.pack(side="left", padx=5)
        self.compile_run_button = ctk.CTkButton(self.toolbar, text="Compiler & Exécuter")
        self.compile_run_button.pack(side="left", padx=5)
        
    def _create_main_panes(self):
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")
        self.main_frame.grid_rowconfigure(0, weight=1)
        self.main_frame.grid_columnconfigure(0, weight=1)
        
        self.tab_view = ctk.CTkTabview(self.main_frame, anchor="w")
        self.tab_view.grid(row=0, column=0, sticky="nsew")

    def _create_output_panel(self):
        self.output_frame = ctk.CTkFrame(self, height=200)
        self.output_textbox = ctk.CTkTextbox(self.output_frame, state="disabled", font=("Consolas", 11), wrap="word")
        self.output_textbox.pack(expand=True, fill="both", padx=5, pady=5)
    
    def show_output_panel(self):
        self.output_frame.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="ew")
        self.grid_rowconfigure(2, minsize=200)

    def add_editor_tab(self, tab_name, content):
        tab_frame = self.tab_view.add(tab_name)
        
        container_frame = ctk.CTkFrame(tab_frame, fg_color="transparent")
        container_frame.pack(expand=True, fill="both")
        container_frame.grid_columnconfigure(1, weight=1)
        container_frame.grid_rowconfigure(0, weight=1)
        
        linenumbers = LineNumbersWidget(container_frame, width=40)
        linenumbers.grid(row=0, column=0, sticky="ns")
        
        editor = CodeEditor(
            container_frame, language="cpp", background="#2B2B2B", 
            foreground="#A9B7C6", insertbackground="white", 
            font=("Consolas", 14), undo=True, autofocus=True
        )
        editor.grid(row=0, column=1, sticky="nsew")
        
        linenumbers.attach(editor)
        editor.insert("1.0", content)
        editor.bind("<KeyRelease>", self.file_manager.on_text_changed_proxy)

        def handle_shortcut(event, action):
            if action == "undo": editor.edit_undo()
            elif action == "redo": editor.edit_redo()
            return "break"
        editor.bind("<Control-z>", lambda e: handle_shortcut(e, "undo"))
        editor.bind("<Control-y>", lambda e: handle_shortcut(e, "redo"))
        
        return editor, linenumbers

    def get_current_tab_name(self):
        return self.tab_view.get()

    def set_active_tab(self, tab_name):
        try:
            self.tab_view.set(tab_name)
        except Exception:
            print(f"Avertissement : impossible de trouver l'onglet '{tab_name}'")

    def rename_tab(self, old_name, new_name):
        if old_name in self.tab_view._tab_dict:
            self.tab_view.rename(old_name, new_name)

    def delete_tab(self, tab_name):
        if tab_name in self.tab_view._tab_dict:
            self.tab_view.delete(tab_name)
    
    def get_all_tab_names(self):
        return list(self.tab_view._tab_dict.keys())

    def update_run_button_state(self):
        state = "normal" if os.path.exists(config.OUTPUT_EXECUTABLE) else "disabled"
        self.run_button.configure(state=state)

    # --- LOGIQUE DE DÉMARRAGE ET DE SESSION ---

    def _load_session_or_start_default(self):
        session_data = session_manager.load_session()
        
        if session_data and session_data.get("open_files"):
            filepaths = session_data.get("open_files", [])
            active_file = session_data.get("active_file")
            active_tab_name = None

            for path in filepaths:
                if os.path.exists(path):
                    self.file_manager.open_file(path)

            if active_file:
                for name, info in self.file_manager.open_tabs.items():
                    if info["filepath"] == active_file:
                        active_tab_name = name
                        break
            
            if active_tab_name:
                self.set_active_tab(active_tab_name)

            if not self.file_manager.open_tabs:
                self._open_start_file()
        else:
            self._open_start_file()
        
        # Mettre à jour l'état du bouton et forcer un rendu final
        self.update_run_button_state()
        self.update()

    def _open_start_file(self):
        if not os.path.exists(config.DEFAULT_START_FILE):
            with open(config.DEFAULT_START_FILE, "w", encoding="utf-8") as f: f.write(config.DEFAULT_CPP_CODE)
        self.file_manager.open_file(config.DEFAULT_START_FILE)
        self.set_active_tab(os.path.basename(config.DEFAULT_START_FILE))

    def on_closing(self):
        open_filepaths = self.file_manager.get_open_filepaths_in_order()
        current_info = self.file_manager.get_current_tab_info()
        active_filepath = current_info["filepath"] if current_info else None
        session_data = {"open_files": open_filepaths, "active_file": active_filepath}
        session_manager.save_session(session_data)
        if self.file_manager.has_dirty_files():
            response = messagebox.askokcancel("Quitter", "Des fichiers ont été modifiés mais non enregistrés.\nVoulez-vous vraiment quitter ?")
            if not response: return
        self.destroy()
    
    # --- MÉTHODES UTILITAIRES (PROXY) ---

    def update_output(self, message):
        self.output_textbox.configure(state="normal")
        self.output_textbox.delete("1.0", "end")
        self.output_textbox.insert("1.0", message)
        self.output_textbox.configure(state="disabled")

    def append_output(self, message):
        self.output_textbox.configure(state="normal")
        self.output_textbox.insert("end", message)
        self.output_textbox.yview_moveto(1.0)
        self.output_textbox.configure(state="disabled")

    def show_warning(self, title, message):
        messagebox.showwarning(title, message)