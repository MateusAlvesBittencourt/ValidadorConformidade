@echo off
setlocal
cd /d "%~dp0"

if not exist "validador_conformidade.py" (
    echo ERRO: Coloque este arquivo na pasta do projeto, junto de validador_conformidade.py.
    pause
    exit /b 1
)

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" "validador_conformidade.py"
) else (
    where py >nul 2>&1
    if errorlevel 1 (
        echo ERRO: Python nao encontrado. Execute gerar_exe.bat para criar o ambiente.
        pause
        exit /b 1
    )
    py -3 "validador_conformidade.py"
)

if errorlevel 1 (
    echo.
    echo O programa terminou com erro.
    pause
    exit /b 1
)
endlocal
