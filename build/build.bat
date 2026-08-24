@echo off
setlocal enabledelayedexpansion
REM ---------------------------------------------------------------------------
REM  Psi Upsilon Digital Museum - rebuild the website on Windows.
REM
REM  Double-click this file after editing data\founders.xlsx or data\timeline.xlsx.
REM  It reads the spreadsheets, regenerates every page, and rebuilds the search
REM  index. Takes a couple of minutes.
REM
REM  It needs two free programs installed:
REM     Python   from python.org   (tick "Add python.exe to PATH" when installing)
REM     Node.js  from nodejs.org   (the LTS version, all defaults)
REM
REM  It does NOT download any PDFs, so it does not need poppler. Adding new
REM  scanned volumes still has to be done with build.sh - see the README.
REM ---------------------------------------------------------------------------
cd /d "%~dp0.."
echo.
echo   Psi Upsilon Digital Museum - rebuilding
echo   ---------------------------------------
echo.

where python >nul 2>&1
if errorlevel 1 (
  echo   STOP: Python is not installed, or was installed without "Add to PATH".
  echo   Install it from https://www.python.org/downloads/ and tick that box.
  echo.
  pause
  exit /b 1
)
where npx >nul 2>&1
if errorlevel 1 (
  echo   STOP: Node.js is not installed.
  echo   Install the LTS version from https://nodejs.org/ and try again.
  echo.
  pause
  exit /b 1
)

for %%P in ("data\founders.xlsx" "data\timeline.xlsx") do (
  if exist %%P (
    2>nul (>>%%P (call )) || (
      echo   STOP: %%P is still open in Excel. Close it and run this again.
      echo.
      pause
      exit /b 1
    )
  )
)

echo   [1/5] reading the spreadsheets
python build\import_sheets.py || goto :failed

echo   [2/5] assembling the timeline
python build\build_timeline.py || goto :failed

echo   [3/5] working out who and what is mentioned where
python build\build_mentions.py || goto :failed

echo   [4/5] generating pages
python build\gen_site.py || goto :failed

echo   [5/5] building the search index
call npx --yes pagefind@1 --site build\index_html --output-path "%CD%\site\pagefind" --root-selector main || goto :failed

echo.
echo   Done. The website in the "site" folder is up to date.
echo.
echo   To look at it before publishing, run  build\preview.bat
echo   To publish it, open GitHub Desktop, write a sentence in the
echo   summary box, click "Commit to main", then "Push origin".
echo.
pause
exit /b 0

:failed
echo.
echo   Something went wrong - the message above says what. Nothing was published;
echo   the website is exactly as it was. If it mentions a category, fix that row
echo   in the spreadsheet. If it mentions permission, close Excel.
echo.
pause
exit /b 1
