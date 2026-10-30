@echo off
REM Prepara a iAna na primeira vez: cria o ambiente, instala as bibliotecas e baixa os modelos.
cd /d "%~dp0"
echo.
echo === iAna: instalando ===
where python >nul 2>nul
if errorlevel 1 (
    echo Python nao encontrado. Instale o Python 3.14 em python.org e marque "Add python.exe to PATH".
    pause
    exit /b 1
)
if not exist ".venv" (
    python -m venv .venv
)
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo Algo deu errado na instalacao. Veja a mensagem acima.
    pause
    exit /b 1
)
echo.
where ollama >nul 2>nul
if errorlevel 1 (
    echo Ollama nao encontrado. Instale em https://ollama.com e rode este arquivo de novo para baixar os modelos.
    pause
    exit /b 1
)
set /p MODELOS="Baixar agora os modelos de IA? Sao varios GB. (s/n) "
if /i not "%MODELOS%"=="s" goto fim
ollama pull gemma4:e4b
if errorlevel 1 goto erro_modelo
ollama pull minicpm-v
if errorlevel 1 goto erro_modelo
ollama pull bge-m3
if errorlevel 1 goto erro_modelo
:fim
echo.
echo Pronto! Abra a iAna pelo iAna.bat
pause
exit /b 0
:erro_modelo
echo Nao deu para baixar um dos modelos. Confira se o Ollama esta aberto e rode este arquivo de novo.
pause
exit /b 1
