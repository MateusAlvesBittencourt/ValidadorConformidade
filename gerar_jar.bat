@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

where javac >nul 2>&1
if errorlevel 1 (
    echo ERRO: Instale um JDK 17 ou superior neste computador. O comando javac nao foi encontrado.
    pause
    exit /b 1
)

if not exist "configuracoes\*.json" (
    echo ERRO: JSONs nao encontrados em configuracoes.
    pause
    exit /b 1
)

if not exist "build\java" mkdir "build\java"
if not exist "dist" mkdir "dist"

javac --release 17 -encoding UTF-8 -d "build\java" "src\ValidadorLaboratorios.java"
if errorlevel 1 goto :falha

jar --create --file "dist\ValidadorLaboratorios.jar" --main-class ValidadorLaboratorios -C "build\java" . -C . configuracoes
if errorlevel 1 goto :falha

java -jar "dist\ValidadorLaboratorios.jar" --check-config
if errorlevel 1 goto :falha

echo.
echo JAR criado em: "%~dp0dist\ValidadorLaboratorios.jar"
echo Para abrir em outro computador, instale Java 17 ou superior e execute: java -jar ValidadorLaboratorios.jar

set "DESTINO=J:\C\Certificação Imagem\Validador"
if exist "J:\" (
    if not exist "%DESTINO%\" mkdir "%DESTINO%"
    if exist "%DESTINO%\" (
        copy /Y "dist\ValidadorLaboratorios.jar" "%DESTINO%\ValidadorLaboratorios.jar" >nul
        if errorlevel 1 (echo AVISO: Nao foi possivel copiar o JAR para a unidade J.) else (echo Copiado para: "%DESTINO%\ValidadorLaboratorios.jar")
    ) else (
        echo AVISO: Nao foi possivel criar a pasta de destino na unidade J.
    )
) else (
    echo AVISO: A unidade J: nao esta acessivel. O JAR permanece em dist.
)
pause
exit /b 0

:falha
echo Falha ao gerar ou validar o JAR.
pause
exit /b 1
