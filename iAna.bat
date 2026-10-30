@echo off
REM Abre a iAna no navegador. Na primeira vez, rode antes o instalar.bat
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo A iAna ainda nao foi instalada. Rode primeiro o instalar.bat
    pause
    exit /b 1
)
echo Abrindo a iAna em http://localhost:8501
echo Deixe esta janela aberta enquanto usa. Para sair, feche esta janela.
start "" /b powershell -NoProfile -WindowStyle Hidden -Command "for ($i = 0; $i -lt 120; $i++) { try { (New-Object Net.Sockets.TcpClient 'localhost', 8501).Close(); break } catch { Start-Sleep 1 } }; Start-Process 'http://localhost:8501'"
".venv\Scripts\python.exe" -m streamlit run app.py --server.headless true
