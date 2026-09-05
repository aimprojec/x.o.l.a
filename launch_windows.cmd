@echo off
cd /d "%~dp0"
python --version >nul 2>&1
if errorlevel 1 (
  echo Python 3.10 or newer is required. Install Python and enable its PATH option.
  pause
  exit /b 1
)
python xola.py --doctor
start "Xola daemon" cmd /k python xola.py --daemon
start "Xola dashboard" cmd /k python server.py
if /I "%~1"=="voice" start "Xola voice listener" cmd /k python xola.py --listen
echo Dashboard: http://127.0.0.1:8101/
echo Add the argument voice to also start the microphone listener.
echo Close each Xola window or press Ctrl+C in it to stop that component.
