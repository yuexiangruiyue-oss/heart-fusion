@echo off
REM ============================================================
REM build_ffi.bat - 编译心灵协议 C-ABI 动态库 heart_core.dll
REM 自动探测本机可用的 C 编译器: MSVC(cl) / gcc / clang / tcc
REM 产物: heart_ffi\build\heart_core.dll
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

echo [heart-ffi] 未找到任何 C 编译器(cl/gcc/clang)。
echo 可任选其一安装后重试:
echo   1. winget install BrechtSanders.WinLibs.POSIX.UCRT   (gcc)
echo   2. Visual Studio Build Tools                         (cl)
echo   3. winget install LLVM.LLVM                          (clang)
exit /b 1

:msvc
echo [heart-ffi] 使用 MSVC (cl) 编译...
cl /nologo /utf-8 /O2 /LD heart_core.c /Fe:build\heart_core.dll
goto :verify

:gcc
echo [heart-ffi] 使用 gcc 编译...
gcc -O2 -shared -finput-charset=UTF-8 -o build\heart_core.dll heart_core.c
goto :verify

:clang
echo [heart-ffi] 使用 clang 编译...
clang -O2 -shared -finput-charset=UTF-8 -o build\heart_core.dll heart_core.c
goto :verify

:verify
if exist build\heart_core.dll (
    echo [heart-ffi] 构建成功: %cd%\build\heart_core.dll
    exit /b 0
) else (
    echo [heart-ffi] 构建失败。
    exit /b 1
)
