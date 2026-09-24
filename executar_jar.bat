@echo off
setlocal
cd /d "%~dp0"

if exist "dist\ValidadorLaboratorios-portatil\ValidadorLaboratorios.exe" (
    "dist\ValidadorLaboratorios-portatil\ValidadorLaboratorios.exe"
    goto :fim
)
if exist "ValidadorLaboratorios-portatil\ValidadorLaboratorios.exe" (
    "ValidadorLaboratorios-portatil\ValidadorLaboratorios.exe"
    goto :fim
)

where java >nul 2>&1
if errorlevel 1 (
    echo ERRO: Java 17 ou superior nao encontrado neste computador.
    pause
    exit /b 1
)

if exist "dist\ValidadorLaboratorios.jar" (
    java -jar "dist\ValidadorLaboratorios.jar"
) else if exist "ValidadorLaboratorios.jar" (
    java -jar "ValidadorLaboratorios.jar"
) else (
    echo ERRO: Programa nao encontrado. Execute gerar_portatil.bat ou gerar_jar.bat na pasta do projeto.
    pause
    exit /b 1
)

:fim
if errorlevel 1 (
    echo O programa terminou com erro.
    pause
    exit /b 1
)
endlocal
