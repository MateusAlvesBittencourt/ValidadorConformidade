@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"

rem Compilar e empacotar sempre com ferramentas do mesmo JDK (17 ou superior).
set "JDK_BIN="
if defined JAVA_HOME if exist "%JAVA_HOME%\bin\javac.exe" set "JDK_BIN=%JAVA_HOME%\bin\"
if not defined JDK_BIN for /f "delims=" %%I in ('where javac.exe 2^>nul') do if not defined JDK_BIN set "JDK_BIN=%%~dpI"
if not defined JDK_BIN goto :sem_jdk
for %%E in (java.exe javac.exe jpackage.exe) do if not exist "%JDK_BIN%%%E" goto :sem_jdk
for %%M in (java.base.jmod java.desktop.jmod) do if not exist "%JDK_BIN%..\jmods\%%M" goto :sem_jdk

if not exist "src\ValidadorLaboratorios.java" goto :sem_fontes
if not exist "configuracoes\*.json" goto :sem_fontes

rem As pastas build sao temporarias; o resultado fica em dist.
if exist "build\java\" rmdir /s /q "build\java"
if exist "build\pacote\" rmdir /s /q "build\pacote"
if exist "build\portatil\ValidadorLaboratorios\" rmdir /s /q "build\portatil\ValidadorLaboratorios"
if not exist "build\java\" mkdir "build\java"
if not exist "build\pacote\" mkdir "build\pacote"
if not exist "build\portatil\" mkdir "build\portatil"
if not exist "dist\" mkdir "dist"
if not exist "build\java\" goto :falha
if not exist "build\pacote\" goto :falha
if not exist "build\portatil\" goto :falha
if exist "build\portatil\ValidadorLaboratorios\" goto :falha

"%JDK_BIN%javac.exe" --release 17 -encoding UTF-8 -d "build\java" "src\ValidadorLaboratorios.java"
if errorlevel 1 goto :falha

"%JDK_BIN%java.exe" -m jdk.jartool/sun.tools.jar.Main --create --file "build\pacote\ValidadorLaboratorios.jar" --main-class ValidadorLaboratorios -C "build\java" . -C . configuracoes
if errorlevel 1 goto :falha
"%JDK_BIN%java.exe" -jar "build\pacote\ValidadorLaboratorios.jar" --check-config
if errorlevel 1 goto :falha

"%JDK_BIN%jpackage.exe" --type app-image --input "build\pacote" --dest "build\portatil" --name "ValidadorLaboratorios" --main-jar "ValidadorLaboratorios.jar" --main-class "ValidadorLaboratorios" --add-modules java.desktop --jlink-options "--strip-debug --no-man-pages --no-header-files"
if errorlevel 1 goto :falha
if not exist "build\portatil\ValidadorLaboratorios\ValidadorLaboratorios.exe" goto :falha
if not exist "build\portatil\ValidadorLaboratorios\runtime\release" goto :falha
if not exist "build\portatil\ValidadorLaboratorios\runtime\bin\javaw.exe" goto :falha
"build\portatil\ValidadorLaboratorios\runtime\bin\java.exe" -jar "build\portatil\ValidadorLaboratorios\app\ValidadorLaboratorios.jar" --check-config
if errorlevel 1 goto :falha
copy /Y "executar_portatil.bat" "build\portatil\ValidadorLaboratorios\executar_portatil.bat" >nul
if errorlevel 1 goto :falha

robocopy "build\portatil\ValidadorLaboratorios" "dist\ValidadorLaboratorios-portatil" /E /R:2 /W:1 /NFL /NDL /NJH /NJS
if errorlevel 8 goto :falha
if not exist "dist\ValidadorLaboratorios-portatil\ValidadorLaboratorios.exe" goto :falha
if not exist "dist\ValidadorLaboratorios-portatil\runtime\release" goto :falha
if not exist "dist\ValidadorLaboratorios-portatil\executar_portatil.bat" goto :falha

echo.
echo Versao portatil criada em: "%~dp0dist\ValidadorLaboratorios-portatil"
echo Nas maquinas clientes, abra ValidadorLaboratorios.exe DENTRO dessa pasta.
echo Tambem e possivel usar executar_portatil.bat na mesma pasta.
echo Copie a pasta inteira: o runtime Java fica na subpasta runtime.

set "DESTINO=J:\C\Certificação Imagem\Validador"
if exist "J:\" (
    if not exist "%DESTINO%\" mkdir "%DESTINO%"
    if exist "%DESTINO%\" (
        robocopy "dist\ValidadorLaboratorios-portatil" "%DESTINO%\ValidadorLaboratorios-portatil" /E /R:2 /W:1 /NFL /NDL /NJH /NJS
        if errorlevel 8 (echo AVISO: Copia incompleta na unidade J:. Use a versao em dist.) else (echo Copiado para: "%DESTINO%\ValidadorLaboratorios-portatil")
    ) else (
        echo AVISO: Nao foi possivel criar a pasta na unidade J:.
    )
) else (
    echo AVISO: A unidade J: nao esta acessivel. A versao portatil permanece em dist.
)
pause
exit /b 0

:sem_jdk
echo ERRO: Instale um JDK 17 ou superior completo, incluindo javac.exe, jpackage.exe e a pasta jmods, na maquina que gera o programa.
echo Confira JAVA_HOME ou coloque o bin do JDK no PATH.
goto :falha

:sem_fontes
echo ERRO: Fonte Java ou configuracoes JSON nao encontrados na pasta do projeto.
goto :falha

:falha
echo Falha ao gerar a versao portatil. Confira a mensagem acima.
pause
exit /b 1
