# src/build_manager.py
import os
import subprocess
import threading
import json
from . import config

def parse_conan_info_json():
    """ Lit le fichier conan_info.json et construit les flags de compilation. """
    json_file = os.path.join(config.BUILD_DIR, "conan_info.json")
    if not os.path.exists(json_file): return None, None
    with open(json_file, 'r', encoding='utf-8') as f: data = json.load(f)
    include_dirs, lib_dirs, bin_paths, defines, libs, system_libs = set(), set(), set(), set(), [], []
    for node in data.get("graph", {}).get("nodes", {}).values():
        cpp_info = node.get("cpp_info")
        if not cpp_info: continue
        for component_info in cpp_info.values():
            for path in component_info.get("includedirs") or []:
                if not os.path.isabs(path): path = os.path.join(config.ROOT_DIR, path)
                include_dirs.add(os.path.normpath(path))
            for path in component_info.get("libdirs") or []:
                if not os.path.isabs(path): path = os.path.join(config.ROOT_DIR, path)
                lib_dirs.add(os.path.normpath(path))
            for path in component_info.get("bindirs") or []:
                if not os.path.isabs(path): path = os.path.join(config.ROOT_DIR, path)
                bin_paths.add(os.path.normpath(path))
            for define in component_info.get("defines") or []: defines.add(define)
            for lib in component_info.get("libs") or []:
                if lib not in libs: libs.append(lib)
            for lib in component_info.get("system_libs") or []:
                if lib not in system_libs: system_libs.append(lib)
    final_flags = []
    for path in sorted(list(include_dirs)): final_flags.append(f'-I{path}') 
    for path in sorted(list(lib_dirs)): final_flags.append(f'-L{path}')
    for define in sorted(list(defines)): final_flags.append(f'-D{define}')
    for lib in libs: final_flags.append(f'-l{lib}')
    for lib in system_libs: final_flags.append(f'-l{lib}')
    return final_flags, sorted(list(bin_paths))

class BuildManager:
    def __init__(self, app):
        self.app = app
        self.conan_flags, self.conan_bin_paths = parse_conan_info_json()

    def _compile_thread_target(self, source_to_compile, run_after=False):
        self.app.update_output("Compilation en cours...\n\n")
        if self.conan_flags is None:
            self.app.append_output("ERREUR: Informations de Conan non trouvées.")
            return
        if not os.path.exists(config.COMPILER_PATH):
            self.app.append_output(f"ERREUR: Compilateur non trouvé: {config.COMPILER_PATH}")
            return
        
        command = [config.COMPILER_PATH, "-o", config.OUTPUT_EXECUTABLE, source_to_compile] + self.conan_flags + ["-static-libgcc", "-static-libstdc++"]
        self.app.append_output("Commande exécutée :\n" + " ".join(command) + "\n\n")
        try:
            compile_env = os.environ.copy()
            mingw_bin_path = os.path.join(config.VENDOR_DIR, "mingw64", "bin")
            compile_env["PATH"] = f"{mingw_bin_path}{os.pathsep}{compile_env['PATH']}"
            process = subprocess.run(command, capture_output=True, text=True, check=False, encoding='utf-8', errors='ignore', env=compile_env)
            if process.returncode == 0:
                self.app.append_output("Compilation réussie !\n")
                if run_after: self.run_app()
            else:
                self.app.append_output(f"ÉCHEC de la compilation:\n\n{process.stderr or process.stdout}")
        except Exception as e:
            self.app.append_output(f"Une erreur est survenue:\n{e}")
        finally:
            self.app.update_run_button_state()

    def start_compilation(self, run_after=False):
        # self.app.show_output_panel_if_hidden()  # <-- CETTE LIGNE EST SUPPRIMÉE
        filepath = self.app.file_manager.save_current_file()
        if not filepath:
            self.app.show_warning("Annulé", "La compilation a été annulée car le fichier n'a pas été enregistré.")
            return
        
        threading.Thread(target=self._compile_thread_target, args=(filepath, run_after)).start()

    def compile_code(self):
        self.start_compilation(run_after=False)

    def compile_and_run_code(self):
        self.start_compilation(run_after=True)

    def run_app(self):
        if not os.path.exists(config.OUTPUT_EXECUTABLE):
            self.app.update_output("Erreur: Exécutable non trouvé. Veuillez compiler.")
            return
        self.app.update_output(f"Lancement de {config.OUTPUT_EXECUTABLE}...")
        try:
            run_env = os.environ.copy()
            additional_paths = self.conan_bin_paths if self.conan_bin_paths else []
            additional_paths.append(os.path.join(config.VENDOR_DIR, "mingw64", "bin"))
            run_env["PATH"] = f"{os.pathsep.join(additional_paths)}{os.pathsep}{run_env.get('PATH', '')}"
            subprocess.Popen([config.OUTPUT_EXECUTABLE], cwd=config.BUILD_DIR, env=run_env)
        except Exception as e:
            self.app.update_output(f"Impossible de lancer l'application:\n{e}")