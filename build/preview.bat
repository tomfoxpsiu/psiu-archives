@echo off
REM Look at the website on this computer before publishing it.
cd /d "%~dp0.."
echo.
echo   Opening http://localhost:8000 in your browser.
echo   Leave this black window open while you look around;
echo   close it (or press Ctrl-C) when you are finished.
echo.
start "" http://localhost:8000
python -m http.server 8000 --directory site
