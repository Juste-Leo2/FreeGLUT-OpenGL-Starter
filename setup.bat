@echo off
setlocal

echo ==========================================================
echo       INITIALISATION DE L'ENVIRONNEMENT (GCC 13 + QT)
echo ==========================================================
echo.

REM --- Etape 1: Installation de 'uv' ---
echo [1/8] Installation de 'uv'...
powershell -ExecutionPolicy ByPass -Command "irm https://astral.sh/uv/install.ps1 | iex" > nul
if %errorlevel% neq 0 (echo ECHEC: Impossible d'installer uv.& goto:error)
set "UV_EXE=%USERPROFILE%\.local\bin\uv.exe"
if not exist "%UV_EXE%" (echo ECHEC: uv.exe non trouve.& goto:error)
echo    [OK] uv installe.

REM --- Etape 2: Creation de l'environnement Python ---
echo [2/8] Creation de l'environnement Python...
"%UV_EXE%" venv -p 3.11 > nul
if %errorlevel% neq 0 (echo ECHEC: Impossible de creer l'environnement Python.& goto:error)
echo    [OK] Environnement Python cree.

REM --- Etape 3: Installation des dependances Python ---
echo [3/8] Installation des dependances Python (PyQt6)...
call .\.venv\Scripts\activate.bat
"%UV_EXE%" pip install -r requirements.txt > nul
if %errorlevel% neq 0 (
    echo ECHEC: Impossible d'installer les dependances Python.
    call .\.venv\Scripts\deactivate.bat & goto:error
)
echo    [OK] Dependances Python installees.

REM --- Etape 4: Telechargement du compilateur C++ (MinGW GCC 13.2.0) ---
echo [4/8] Telechargement du compilateur C++ (MinGW GCC 13.2.0)...
if not exist "vendor" mkdir vendor
cd vendor
if not exist "mingw64" (
    REM URL mise a jour vers GCC 13.2.0
    curl -L -o mingw.7z "https://github.com/niXman/mingw-builds-binaries/releases/download/13.2.0-rt_v11-rev1/x86_64-13.2.0-release-posix-seh-ucrt-rt_v11-rev1.7z"
    if %errorlevel% neq 0 (echo ECHEC: Telechargement de MinGW impossible.& cd .. & goto:error)
    tar -xf mingw.7z
    del mingw.7z
)
cd ..
echo    [OK] Compilateur C++ configure.

REM --- Etape 5: Telechargement de CMake ---
echo [5/8] Telechargement de CMake...
cd vendor
if not exist "cmake" (
    echo    Telechargement de l'archive CMake...
    curl -L -o cmake.zip "https://github.com/Kitware/CMake/releases/download/v3.29.3/cmake-3.29.3-windows-x86_64.zip"
    if %errorlevel% neq 0 (echo ECHEC: Telechargement de CMake impossible.& cd .. & goto:error)
    
    echo    Extraction de l'archive...
    powershell -ExecutionPolicy ByPass -Command "Expand-Archive -Path 'cmake.zip' -DestinationPath '.\cmake_temp' -Force" > nul
    for /d %%i in (.\cmake_temp\*) do move "%%i" ".\cmake"
    rmdir cmake_temp
    del cmake.zip
)
cd ..
echo    [OK] CMake configure.

REM --- Etape 6: Telechargement de Conan CLI ---
echo [6/8] Telechargement de Conan CLI...
cd vendor
if not exist "conan_cli" (
    echo    Telechargement de l'executable Conan...
    curl -L -o conan.zip "https://github.com/conan-io/conan/releases/download/2.4.1/conan-2.4.1-windows-x86_64.zip"
    if %errorlevel% neq 0 (echo ECHEC: Telechargement de Conan impossible.& cd .. & goto:error)
    
    echo    Creation du dossier de destination...
    mkdir conan_cli
    powershell -ExecutionPolicy ByPass -Command "Expand-Archive -Path 'conan.zip' -DestinationPath '.\conan_cli' -Force" > nul
    del conan.zip
)
cd ..
echo    [OK] Conan CLI configure.

REM --- Etape 7: Preparation de l'environnement de compilation ---
echo [7/8] Preparation de l'environnement de compilation...
set "MINGW_BIN_PATH=%cd%\vendor\mingw64\bin"
set "CMAKE_BIN_PATH=%cd%\vendor\cmake\bin"
set "PATH=%MINGW_BIN_PATH%;%CMAKE_BIN_PATH%;%PATH%"
set "C_COMPILER=%cd%\vendor\mingw64\bin\gcc.exe"
set "CXX_COMPILER=%cd%\vendor\mingw64\bin\g++.exe"
set "C_COMPILER=%C_COMPILER:\=\\%"
set "CXX_COMPILER=%CXX_COMPILER:\=\\%"

(
    echo [settings]
    echo arch=x86_64
    echo os=Windows
    echo compiler=gcc
    REM Mise a jour de la version du compilateur dans le profil
    echo compiler.version=13
    echo compiler.libcxx=libstdc++11
    echo build_type=Release
    echo [conf]
    echo tools.build:compiler_executables={"c": "%C_COMPILER%", "cpp": "%CXX_COMPILER%"}
) > mingw_profile
echo    [OK] Profil Conan 'mingw_profile' (v13) et PATH configures.

REM --- Etape 8: Installation de freeglut et generation des infos ---
echo [8/8] Installation de freeglut via Conan...
if not exist "build" mkdir build

set "CONAN_EXE=%cd%\vendor\conan_cli\conan.exe"

if not exist "%CONAN_EXE%" (echo ECHEC: conan.exe non trouve!& goto:error)

"%CONAN_EXE%" install . --output-folder=build --profile:host=.\mingw_profile --profile:build=.\mingw_profile --build=missing --format=json > build\conan_info.json
if %errorlevel% neq 0 (
    echo ECHEC: Conan a echoue.
    call .\.venv\Scripts\deactivate.bat & goto:error
)

call .\.venv\Scripts\deactivate.bat
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