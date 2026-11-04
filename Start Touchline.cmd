@echo off
setlocal
cd /d "%~dp0"
if errorlevel 1 exit /b 1
title Touchline Studio
rem The launcher must stay with the extracted application, not be copied alone.
for %%F in (requirements.txt launch.py server.py football_engine.py training_workflow.py dist\index.html) do (
  if not exist "%%F" goto incomplete_package
)
rem Bound numerical-library startup threads on machines with limited memory.
set "OPENBLAS_NUM_THREADS=1"
set "OMP_NUM_THREADS=1"
set "MKL_NUM_THREADS=1"
if not exist "work" mkdir "work"
set "SETUP_LOG=%~dp0work\setup.log"
>"%SETUP_LOG%" echo Touchline dependency check and setup
echo.
echo  TOUCHLINE STUDIO
echo  Your match. Your perspective.
echo.
if exist "..\..\work\yolo-env\Scripts\python.exe" (
  "..\..\work\yolo-env\Scripts\python.exe" -c "import ultralytics, lap, gdown" >>"%SETUP_LOG%" 2>&1
  if not errorlevel 1 goto workspace_ready
  echo The workspace Python environment failed its dependency check.
  echo Details are saved in "%SETUP_LOG%". Trying the local environment.
)
where python >nul 2>nul
if errorlevel 1 (
  echo Python is required. Install Python 3.11, 3.12 or 3.13 from python.org.
  echo Choose Add Python to PATH during installation, then open this file again.
  pause
  exit /b 1
)
if not exist "work\tmp" mkdir "work\tmp"
set "TEMP=%~dp0work\tmp"
set "TMP=%~dp0work\tmp"
set "PIP_CACHE_DIR=%~dp0work\pip-cache"
if not exist ".venv\Scripts\python.exe" python -m venv .venv >>"%SETUP_LOG%" 2>&1
if not exist ".venv\Scripts\python.exe" goto setup_error
".venv\Scripts\python.exe" -c "import ultralytics, lap, gdown" >>"%SETUP_LOG%" 2>&1
if errorlevel 1 (
  echo Installing the tracking engine. First setup may take several minutes.
  ".venv\Scripts\python.exe" -m pip install -r "%~dp0requirements.txt" >>"%SETUP_LOG%" 2>&1
  if errorlevel 1 (
    python -m pip --python ".venv\Scripts\python.exe" install -r "%~dp0requirements.txt" >>"%SETUP_LOG%" 2>&1
    if errorlevel 1 goto setup_error
  )
)
".venv\Scripts\python.exe" -c "import ultralytics, lap, gdown" >>"%SETUP_LOG%" 2>&1
if errorlevel 1 goto setup_error
".venv\Scripts\python.exe" launch.py --lan %*
if errorlevel 1 pause
exit /b
:workspace_ready
"..\..\work\yolo-env\Scripts\python.exe" launch.py --lan %*
if errorlevel 1 pause
exit /b
:setup_error
echo.
echo Setup did not finish. The actual Python or installation error follows:
type "%SETUP_LOG%"
echo.
echo Error log: "%SETUP_LOG%"
echo Check the error above before reinstalling Python or downloading packages.
echo Your videos and projects have not been changed.
pause
exit /b 1
:incomplete_package
echo.
echo Touchline application files are missing from:
echo "%~dp0"
echo.
echo Extract ALL files from touchline-studio.zip first.
echo Right-click the ZIP, choose Extract All, then open the extracted folder.
echo Do not run the launcher inside the ZIP preview or its temporary folder.
echo Open the extracted Touchline Studio folder, then run Start Touchline.cmd there.
echo Keep this launcher beside requirements.txt, launch.py and the dist folder.
echo To launch from another location, create a shortcut instead of copying this file.
echo No packages were installed by this attempt.
pause
exit /b 1
