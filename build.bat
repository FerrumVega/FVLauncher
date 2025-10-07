@echo off
setlocal enabledelayedexpansion

for /f %%v in ('git describe --tags') do set TAG=%%v

>installer_tmp.iss (
  for /f "usebackq delims=" %%l in ("installer.iss") do (
    set "line=%%l"
    echo !line! | findstr /b "AppVersion=" >nul
    if !errorlevel! == 0 (
      echo AppVersion=!TAG!
    ) else (
      echo !line!
    )
  )
)

type LICENSE > ALL_LICENSES
echo. >> ALL_LICENSES
type THIRD_PARTY_LICENSES >> ALL_LICENSES

move /Y installer_tmp.iss installer.iss >nul

pyinstaller --windowed --icon=assets\minecraft_title.ico --distpath dist main.py
if %ERRORLEVEL% neq 0 exit /b 1
iscc installer.iss

if %ERRORLEVEL% neq 0 exit /b 1

endlocal
