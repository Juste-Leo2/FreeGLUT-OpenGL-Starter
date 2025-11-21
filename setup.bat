@echo off
setlocal enabledelayedexpansion

echo ==========================================================
echo    INITIALISATION ENVIRONNEMENT (FIX COMPILATION)
echo ==========================================================
echo.

REM --- Configuration des chemins ---
set "UV_EXE=%USERPROFILE%\.local\bin\uv.exe"

REM --- Etape 1: Installation de 'uv' ---
if exist "!UV_EXE!" (
    echo [1/8] 'uv' est deja installe.
) else (
    echo [1/8] Installation de 'uv'...
    powershell -ExecutionPolicy ByPass -Command "irm https://astral.sh/uv/install.ps1 | iex" > nul
    if !errorlevel! neq 0 (echo ECHEC: Impossible d'installer uv.& goto:error)
)

REM --- Etape 2: Creation de l'environnement Python ---
if exist ".venv" (
    echo [2/8] Environnement Python deja existant.
) else (
    echo [2/8] Creation de l'environnement Python...
    "!UV_EXE!" venv -p 3.11 > nul
    if !errorlevel! neq 0 (echo ECHEC: Impossible de creer l'environnement Python.& goto:error)
)

REM --- Etape 3: Installation des dependances Python ---
if exist ".venv\Lib\site-packages\PyQt6" (
    echo [3/8] Dependances Python deja installees.
) else (
    echo [3/8] Installation des dependances Python ^(PyQt6^)...
    call .\.venv\Scripts\activate.bat
    "!UV_EXE!" pip install -r requirements.txt > nul
    if !errorlevel! neq 0 (
        echo ECHEC: Impossible d'installer les dependances Python.
        call .\.venv\Scripts\deactivate.bat & goto:error
    )
    call .\.venv\Scripts\deactivate.bat
)

REM --- Etape 4: Telechargement du compilateur C++ (MinGW) ---
if not exist "vendor" mkdir vendor
cd vendor

if exist "mingw64\bin\g++.exe" (
    echo [4/8] Compilateur MinGW deja present.
) else (
    echo [4/8] Telechargement du compilateur C++...
    if exist "mingw64" rmdir /s /q "mingw64"
    if exist "mingw.7z" del mingw.7z
    if exist "7zr.exe" del 7zr.exe

    curl -L -o mingw.7z "https://github.com/niXman/mingw-builds-binaries/releases/download/13.2.0-rt_v11-rev1/x86_64-13.2.0-release-posix-seh-ucrt-rt_v11-rev1.7z"
    if !errorlevel! neq 0 (echo ECHEC: Telechargement de MinGW impossible.& cd .. & goto:error)

    echo       Recuperation de l'outil d'extraction 7-Zip...
    curl -L -o 7zr.exe "https://www.7-zip.org/a/7zr.exe"
    if !errorlevel! neq 0 (echo ECHEC: Impossible de telecharger 7zr.exe.& cd .. & goto:error)

    echo       Extraction de MinGW avec 7-Zip ^(patience^)...
    7zr.exe x mingw.7z -y > nul
    if !errorlevel! neq 0 (echo ECHEC: Extraction echouee.& del 7zr.exe & cd .. & goto:error)
    
    if not exist "mingw64\bin\g++.exe" (echo ECHEC: MinGW introuvable.& cd .. & goto:error)

    del mingw.7z
    del 7zr.exe
)
cd ..

REM --- Etape 5: Telechargement de CMake ---
cd vendor
if exist "cmake\bin\cmake.exe" (
    echo [5/8] CMake deja present.
) else (
    echo [5/8] Telechargement de CMake...
    if exist "cmake" rmdir /s /q "cmake"
    curl -L -o cmake.zip "https://github.com/Kitware/CMake/releases/download/v3.29.3/cmake-3.29.3-windows-x86_64.zip"
    if !errorlevel! neq 0 (echo ECHEC: Telechargement de CMake impossible.& cd .. & goto:error)
    powershell -ExecutionPolicy ByPass -Command "Expand-Archive -Path 'cmake.zip' -DestinationPath '.\cmake_temp' -Force" > nul
    for /d %%i in (.\cmake_temp\*) do move "%%i" ".\cmake" > nul
    rmdir cmake_temp
    del cmake.zip
)
cd ..

REM --- Etape 6: Conan CLI ---
cd vendor
if exist "conan_cli\conan.exe" (
    echo [6/8] Conan CLI deja present.
) else (
    echo [6/8] Telechargement de Conan CLI...
    if exist "conan_cli" rmdir /s /q "conan_cli"
    mkdir conan_cli
    curl -L -o conan.zip "https://github.com/conan-io/conan/releases/download/2.4.1/conan-2.4.1-windows-x86_64.zip"
    if !errorlevel! neq 0 (echo ECHEC: Telechargement de Conan impossible.& cd .. & goto:error)
    powershell -ExecutionPolicy ByPass -Command "Expand-Archive -Path 'conan.zip' -DestinationPath '.\conan_cli' -Force" > nul
    del conan.zip
)
cd ..

REM --- Etape 7: Preparation de l'environnement de compilation ---
echo [7/8] Preparation de l'environnement de compilation...

set "CONAN_HOME=%cd%\vendor\conan_home"
if not exist "%CONAN_HOME%" mkdir "%CONAN_HOME%"

set "MINGW_BIN=%cd%\vendor\mingw64\bin"
set "CMAKE_BIN=%cd%\vendor\cmake\bin"
set "CONAN_EXE=%cd%\vendor\conan_cli\conan.exe"
set "C_COMPILER=!MINGW_BIN!\gcc.exe"
set "CXX_COMPILER=!MINGW_BIN!\g++.exe"

if not exist "!CXX_COMPILER!" (
    echo ERREUR FATALE: MinGW est corrompu. Supprimez le dossier vendor\mingw64.
    goto:error
)

REM --- FIX CRITIQUE 1 : Creation de make.exe ---
REM On copie mingw32-make.exe vers make.exe pour que CMake le trouve automatiquement.
if exist "!MINGW_BIN!\mingw32-make.exe" (
    if not exist "!MINGW_BIN!\make.exe" (
        echo    [FIX] Creation de l'alias make.exe...
        copy /y "!MINGW_BIN!\mingw32-make.exe" "!MINGW_BIN!\make.exe" > nul
    )
) else (
    echo ERREUR FATALE: mingw32-make.exe introuvable dans !MINGW_BIN!
    goto:error
)

set "PATH=!MINGW_BIN!;!CMAKE_BIN!;%PATH%"

set "C_COMPILER_FWD=!C_COMPILER:\=/!"
set "CXX_COMPILER_FWD=!CXX_COMPILER:\=/!"

REM --- FIX CRITIQUE 2 : Simplification du Profil ---
REM On ne force plus CMAKE_MAKE_PROGRAM via JSON (source d'erreurs).
REM CMake trouvera 'make.exe' dans le PATH grace au FIX 1.
(
    echo [settings]
    echo arch=x86_64
    echo os=Windows
    echo compiler=gcc
    echo compiler.version=13
    echo compiler.libcxx=libstdc++11
    echo build_type=Release
    echo [conf]
    echo tools.build:compiler_executables={"c": "!C_COMPILER_FWD!", "cpp": "!CXX_COMPILER_FWD!"}
    echo tools.cmake.cmaketoolchain:generator=MinGW Makefiles
    echo tools.cmake.cmaketoolchain:extra_variables={"CMAKE_SH": "CMAKE_SH-NOTFOUND"}
) > mingw_profile
echo    [OK] Profil Conan configure.

REM --- Etape 8: Installation de freeglut ---
echo [8/8] Installation de freeglut via Conan...
if not exist "build" mkdir build
if exist "build\conan_info.json" del build\conan_info.json

"!CONAN_EXE!" install . --output-folder=build --profile:host=.\mingw_profile --profile:build=.\mingw_profile --build=missing --format=json > build\conan_info.json
if !errorlevel! neq 0 (
    echo.
    echo ECHEC CRITIQUE: Conan a echoue.
    goto:error
)

echo    [OK] Dependances C++ installees.
echo.
echo ==========================================================
echo               INSTALLATION TERMINEE !
echo ==========================================================
echo.
pause
goto:eof

:error
echo.
echo !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
echo    UNE ERREUR EST SURVENUE.
echo !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
echo.
pause
exit /b 1

:eof