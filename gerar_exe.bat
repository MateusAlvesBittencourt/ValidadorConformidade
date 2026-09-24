@echo off
setlocal
cd /d "%~dp0"

if not exist "validador_conformidade.py" (
    echo ERRO: Coloque este arquivo na pasta do projeto, junto de validador_conformidade.py.
    pause
    exit /b 1
)
if not exist "configuracoes\*.json" (
    echo ERRO: Nenhum JSON encontrado na pasta configuracoes.
    pause
    exit /b 1
)
if not exist "requirements.txt" (
    echo ERRO: requirements.txt nao encontrado.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    where py >nul 2>&1
    if errorlevel 1 (
        echo ERRO: Instale o Python no computador usado para gerar o EXE.
        pause
        exit /b 1
    )
    py -3 -m venv .venv
    if errorlevel 1 goto :falha
)

".venv\Scripts\python.exe" -m pip install -r requirements.txt pyinstaller
if errorlevel 1 goto :falha

".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onefile --windowed --name ValidadorLaboratorios --add-data "configuracoes;configuracoes" validador_conformidade.py
if errorlevel 1 goto :falha

echo.
echo EXE gerado em: "%~dp0dist\ValidadorLaboratorios.exe"
echo Na maquina cliente, copie apenas esse EXE. Python nao e necessario.
pause
exit /b 0

:falha
echo.
echo Falha ao gerar o EXE. Confira as mensagens acima.
pause
exit /b 1
