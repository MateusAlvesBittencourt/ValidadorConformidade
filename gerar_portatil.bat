@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"

rem Compilar e empacotar sempre com ferramentas do mesmo JDK (17 ou superior).
set "JDK_BIN="
if defined JAVA_HOME call :tentar_jdk "%JAVA_HOME%\bin\"
rem O javapath da Oracle pode conter atalhos java/javac, sem jpackage ou jmods.
if not defined JDK_BIN for /f "delims=" %%I in ('where javac.exe 2^>nul') do if not defined JDK_BIN call :tentar_jdk "%%~dpI"
if not defined JDK_BIN for /d %%D in ("%ProgramFiles%\Java\jdk-*") do if not defined JDK_BIN call :tentar_jdk "%%~fD\bin\"
if not defined JDK_BIN for /d %%D in ("%ProgramFiles%\Eclipse Adoptium\jdk-*") do if not defined JDK_BIN call :tentar_jdk "%%~fD\bin\"
if not defined JDK_BIN for /f "tokens=1,* delims==" %%A in ('java -XshowSettings:properties -version 2^>^&1 ^| findstr /C:"java.home ="') do if not defined JDK_BIN for /f "tokens=* delims= " %%D in ("%%B") do call :tentar_jdk "%%D\bin\"
if not defined JDK_BIN goto :sem_jdk
echo JDK selecionado: "%JDK_BIN%.."
"%JDK_BIN%java.exe" -version

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

if not exist "build\portatil\ValidadorLaboratorios\app\" mkdir "build\portatil\ValidadorLaboratorios\app"
if not exist "build\portatil\ValidadorLaboratorios\app\" goto :falha
"%JDK_BIN%jlink.exe" --add-modules java.desktop --strip-debug --no-man-pages --no-header-files --output "build\portatil\ValidadorLaboratorios\runtime"
if errorlevel 1 goto :falha
if not exist "build\portatil\ValidadorLaboratorios\runtime\bin\javaw.exe" goto :falha
copy /Y "build\pacote\ValidadorLaboratorios.jar" "build\portatil\ValidadorLaboratorios\app\ValidadorLaboratorios.jar" >nul
if errorlevel 1 goto :falha
"build\portatil\ValidadorLaboratorios\runtime\bin\java.exe" -jar "build\portatil\ValidadorLaboratorios\app\ValidadorLaboratorios.jar" --check-config
if errorlevel 1 goto :falha
copy /Y "executar_portatil.bat" "build\portatil\ValidadorLaboratorios\executar_portatil.bat" >nul
if errorlevel 1 goto :falha

robocopy "build\portatil\ValidadorLaboratorios" "dist\ValidadorLaboratorios-portatil" /E /R:2 /W:1 /NFL /NDL /NJH /NJS
if errorlevel 8 goto :falha
if not exist "dist\ValidadorLaboratorios-portatil\app\ValidadorLaboratorios.jar" goto :falha
if exist "dist\ValidadorLaboratorios-portatil\ValidadorLaboratorios.exe" del /f /q "dist\ValidadorLaboratorios-portatil\ValidadorLaboratorios.exe"
if exist "dist\ValidadorLaboratorios-portatil\ValidadorLaboratorios.exe" goto :falha
if not exist "dist\ValidadorLaboratorios-portatil\runtime\release" goto :falha
if not exist "dist\ValidadorLaboratorios-portatil\executar_portatil.bat" goto :falha

echo.
echo Versao portatil criada em: "%~dp0dist\ValidadorLaboratorios-portatil"
echo Nas maquinas clientes, abra executar_portatil.bat DENTRO dessa pasta.
echo Copie a pasta inteira: o runtime Java fica na subpasta runtime.

set "DESTINO=\\10.40.48.8\software$\C\Certificação Imagem"
if exist "\\10.40.48.8\software$\C\" (
    if not exist "%DESTINO%\" mkdir "%DESTINO%"
    if exist "%DESTINO%\" (
        robocopy "dist\ValidadorLaboratorios-portatil" "%DESTINO%\ValidadorLaboratorios-portatil" /E /R:2 /W:1 /NFL /NDL /NJH /NJS
        if errorlevel 8 (echo AVISO: Copia incompleta no compartilhamento. Use a versao em dist.) else (
            if exist "%DESTINO%\ValidadorLaboratorios-portatil\ValidadorLaboratorios.exe" del /f /q "%DESTINO%\ValidadorLaboratorios-portatil\ValidadorLaboratorios.exe"
            if exist "%DESTINO%\ValidadorLaboratorios-portatil\ValidadorLaboratorios.exe" (echo AVISO: Nao foi possivel remover o launcher antigo.) else (echo Copiado para: "%DESTINO%\ValidadorLaboratorios-portatil")
        )
    ) else (
        echo AVISO: Nao foi possivel criar a pasta no compartilhamento.
    )
) else (
    echo AVISO: Compartilhamento inacessivel. A versao portatil permanece em dist.
)
pause
exit /b 0

:sem_jdk
echo ERRO: Java para executar JARs foi encontrado, mas nenhum JDK completo para gerar o pacote foi localizado.
echo Confira JAVA_HOME e se a instalacao inclui javac.exe, jlink.exe e jmods\java.desktop.jmod.
echo Caminhos detectados nesta maquina:
where java.exe 2>nul
where javac.exe 2>nul
where jlink.exe 2>nul
goto :falha

:sem_fontes
echo ERRO: Fonte Java ou configuracoes JSON nao encontrados na pasta do projeto.
goto :falha

:falha
echo Falha ao gerar a versao portatil. Confira a mensagem acima.
pause
exit /b 1

:tentar_jdk
if defined JDK_BIN exit /b 0
if not exist "%~1java.exe" exit /b 0
if not exist "%~1javac.exe" exit /b 0
if not exist "%~1jlink.exe" exit /b 0
if not exist "%~1..\jmods\java.base.jmod" exit /b 0
if not exist "%~1..\jmods\java.desktop.jmod" exit /b 0
set "JDK_BIN=%~1"
exit /b 0
