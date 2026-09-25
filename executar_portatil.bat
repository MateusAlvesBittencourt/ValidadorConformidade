@echo off
setlocal
pushd "%~dp0" || (
    echo ERRO: Nao foi possivel acessar a pasta portatil.
    pause
    exit /b 1
)

if not exist "runtime\bin\javaw.exe" (
    echo ERRO: Runtime Java nao encontrado. Copie a pasta portatil inteira.
    pause
    exit /b 1
)
if not exist "app\ValidadorLaboratorios.jar" (
    echo ERRO: ValidadorLaboratorios.jar nao encontrado na pasta app.
    pause
    exit /b 1
)

"runtime\bin\javaw.exe" -jar "app\ValidadorLaboratorios.jar"
if errorlevel 1 (
    echo O programa terminou com erro.
    pause
    exit /b 1
)
popd
endlocal
