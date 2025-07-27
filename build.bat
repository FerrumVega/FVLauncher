@echo off
setlocal enabledelayedexpansion

for /f %%v in ('git describe --tags') do set TAG=%%v

>installer_tmp.iss (
  for /f "usebackq delims=" %%l in ("installer.iss") do (
    set "line=%%l"
    echo !line:MyAppVersion = "1.0.0"=MyAppVersion = "%TAG%"!
  )
)
move /Y installer_tmp.iss installer.iss >nul

python -m nuitka ^
    --onefile ^
    --windows-icon-from-ico=minecraft_title.ico ^
    --output-dir=dist ^
    main.py

if %ERRORLEVEL% neq 0 exit /b 1

iscc installer.iss

if %ERRORLEVEL% neq 0 exit /b 1

endlocal
