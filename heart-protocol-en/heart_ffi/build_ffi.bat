@echo off
REM ============================================================
REM build_ffi.bat - build the Heart Protocol C-ABI shared library heart_core.dll
REM Auto-detects an available C compiler on this machine: MSVC(cl) / gcc / clang / tcc
REM Output: heart_ffi\build\heart_core.dll
REM ============================================================
setlocal
cd /d "%~dp0"
if not exist build mkdir build

where cl >nul 2>nul
if %errorlevel%==0 goto :msvc
where gcc >nul 2>nul
if %errorlevel%==0 goto :gcc
where clang >nul 2>nul
if %errorlevel%==0 goto :clang

echo [heart-ffi] No C compiler found (cl/gcc/clang).
echo Install any one of the following and retry:
echo   1. winget install BrechtSanders.WinLibs.POSIX.UCRT   (gcc)
echo   2. Visual Studio Build Tools                         (cl)
echo   3. winget install LLVM.LLVM                          (clang)
exit /b 1

:msvc
echo [heart-ffi] Building with MSVC (cl)...
cl /nologo /utf-8 /O2 /LD heart_core.c /Fe:build\heart_core.dll
goto :verify

:gcc
echo [heart-ffi] Building with gcc...
gcc -O2 -shared -finput-charset=UTF-8 -o build\heart_core.dll heart_core.c
goto :verify

:clang
echo [heart-ffi] Building with clang...
clang -O2 -shared -finput-charset=UTF-8 -o build\heart_core.dll heart_core.c
goto :verify

:verify
if exist build\heart_core.dll (
    echo [heart-ffi] Build succeeded: %cd%\build\heart_core.dll
    exit /b 0
) else (
    echo [heart-ffi] Build failed.
    exit /b 1
)
