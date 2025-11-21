import os
import subprocess
import threading
import json
from . import config

def parse_conan_info_json():
    """
    Analyse le fichier JSON généré par Conan pour extraire les chemins d'inclusion,
    les dossiers de bibliothèques et les flags de compilation.
    """
    json_file = os.path.join(config.BUILD_DIR, "conan_info.json")
    
    if not os.path.exists(json_file):
        print(f"DEBUG: Fichier introuvable: {json_file}")
        return None, None
    
    try:
        with open(json_file, 'r', encoding='utf-8') as f: 
            data = json.load(f)
    except Exception as e:
        print(f"DEBUG: Erreur de lecture JSON: {e}")
        return None, None

    include_dirs = set()
    lib_dirs = set()
    bin_paths = set()
    defines = set()
    libs = []
    system_libs = []

    # Parcours du graph Conan
    nodes = data.get("graph", {}).get("nodes", {})
    
    for node_id, node in nodes.items():
        if node_id == "0": continue # Skip le noeud racine

        cpp_info = node.get("cpp_info")
        if not cpp_info: continue
        
        configs_to_parse = []
        
        if isinstance(cpp_info, dict):
            # Si cpp_info contient directement des listes (cas simple)
            if "includedirs" in cpp_info:
                configs_to_parse.append(cpp_info)
            else:
                # Sinon c'est un dict de composants/configs (ex: "root", "my_component")
                configs_to_parse.extend(cpp_info.values())

        for info in configs_to_parse:
            if not info: continue

            # --- CORRECTION MAJEURE ICI : Utilisation de (get() or []) ---
            # Cela empêche le crash si la valeur dans le JSON est 'null'

            # Extraction des Chemins d'inclusion (-I)
            raw_includes = info.get("includedirs") or []
            for p in raw_includes:
                if p:
                    clean_path = os.path.normpath(p)
                    include_dirs.add(clean_path)

            # Extraction des Dossiers de librairie (-L)
            raw_libdirs = info.get("libdirs") or []
            for p in raw_libdirs:
                if p:
                    clean_path = os.path.normpath(p)
                    lib_dirs.add(clean_path)

            # Extraction des Dossiers binaires (DLLs)
            raw_bindirs = info.get("bindirs") or []
            for p in raw_bindirs:
                if p:
                    clean_path = os.path.normpath(p)
                    bin_paths.add(clean_path)

            # Extraction des Defines (-D)
            raw_defines = info.get("defines") or []
            for d in raw_defines: 
                if d: defines.add(d)
            
            # Extraction des Noms de librairies (-l)
            raw_libs = info.get("libs") or []
            for l in raw_libs: 
                if l and l not in libs: libs.append(l)
                
            # Extraction des Librairies système
            raw_sys_libs = info.get("system_libs") or []
            for l in raw_sys_libs:
                if l and l not in system_libs: system_libs.append(l)

    # Construction des flags
    final_flags = []
    
    for p in sorted(list(include_dirs)): 
        final_flags.append(f'-I{p}') 
    
    for p in sorted(list(lib_dirs)): 
        final_flags.append(f'-L{p}')
    
    for d in sorted(list(defines)): 
        final_flags.append(f'-D{d}')
    
    for l in libs: 
        final_flags.append(f'-l{l}')
    for l in system_libs: 
        final_flags.append(f'-l{l}')
    
    print(f"DEBUG: Flags Conan generes ({len(final_flags)} items)")
    
    return final_flags, sorted(list(bin_paths))

class BuildManager:
    def __init__(self, app):
        self.app = app
        # Premier chargement (peut échouer silencieusement au démarrage, ce n'est pas grave)
        try:
            self.conan_flags, self.conan_bin_paths = parse_conan_info_json()
        except Exception as e:
            print(f"Warning: Echec initial lecture Conan: {e}")
            self.conan_flags, self.conan_bin_paths = None, None

    def _compile_thread_target(self, source_to_compile, run_after=False):
        self.app.update_output("Compilation en cours...\n")
        
        # On tente de recharger proprement
        self.conan_flags, self.conan_bin_paths = parse_conan_info_json()

        if not self.conan_flags:
            self.app.append_output("ERREUR CRITIQUE: Impossible de lire les configurations Conan (build/conan_info.json).\n")
            return
        
        if not os.path.exists(config.COMPILER_PATH):
            self.app.append_output(f"ERREUR: Compilateur introuvable : {config.COMPILER_PATH}\n")
            return
        
        command = [config.COMPILER_PATH, "-o", config.OUTPUT_EXECUTABLE, source_to_compile] + \
                  self.conan_flags + ["-static-libgcc", "-static-libstdc++"]
        
        cmd_str = " ".join(command)
        self.app.append_output(f"COMMANDE:\n{cmd_str}\n\n")

        try:
            compile_env = os.environ.copy()
            mingw_bin = os.path.join(config.VENDOR_DIR, "mingw64", "bin")
            compile_env["PATH"] = f"{mingw_bin}{os.pathsep}{compile_env['PATH']}"

            process = subprocess.run(
                command, 
                capture_output=True, 
                text=True, 
                encoding='utf-8', 
                errors='replace', 
                env=compile_env,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            if process.returncode == 0:
                self.app.append_output("SUCCÈS : Compilation terminée.\n")
                if run_after:
                    self.app.log_signal.emit("Lancement...\n", False)
                    self.run_app()
            else:
                self.app.append_output(f"ERREUR DE COMPILATION :\n{process.stderr}\n{process.stdout}\n")
                
        except Exception as e:
            self.app.append_output(f"Exception système lors de la compilation: {e}\n")

    def start_compilation(self, run_after=False):
        filepath = self.app.file_manager.save_current_file()
        if not filepath: return
        
        t = threading.Thread(target=self._compile_thread_target, args=(filepath, run_after))
        t.daemon = True
        t.start()

    def compile_code(self):
        self.start_compilation(run_after=False)

    def compile_and_run_code(self):
        self.start_compilation(run_after=True)

    def run_app(self):
        if not os.path.exists(config.OUTPUT_EXECUTABLE):
            self.app.append_output("Erreur: Exécutable introuvable. Compilez d'abord.\n")
            return
            
        try:
            run_env = os.environ.copy()
            paths = self.conan_bin_paths if self.conan_bin_paths else []
            paths.append(os.path.join(config.VENDOR_DIR, "mingw64", "bin"))
            
            run_env["PATH"] = f"{os.pathsep.join(paths)}{os.pathsep}{run_env.get('PATH', '')}"
            
            subprocess.Popen(
                [config.OUTPUT_EXECUTABLE], 
                cwd=config.BUILD_DIR, 
                env=run_env,
                creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0
            )
        except Exception as e:
            self.app.append_output(f"Erreur au lancement: {e}\n")