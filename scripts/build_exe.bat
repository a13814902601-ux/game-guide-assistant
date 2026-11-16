@echo off
cd /d "%~dp0.."
set PYTHONUTF8=1
if not exist ".venv\Scripts\python.exe" (
  echo [!] 没有找到 .venv，请先运行：
  echo     python -m venv .venv
  echo     .venv\Scripts\pip install -r requirements-overlay.txt -r requirements-build.txt
  exit /b 1
)
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onefile --windowed --name GameGuideOverlay --icon "overlay\assets\icon.ico" --paths "%CD%" --collect-submodules markdown --add-data "%CD%\skills;skills" --add-data "%CD%\overlay\assets;overlay\assets" --specpath build --workpath build --distpath dist "%CD%\overlay\main.py"
echo.
echo [OK] 产物：dist\GameGuideOverlay.exe
echo      exe 不包含 output/，运行时请把 output 放在 exe 旁边，或在设置里选择目录。
pause
