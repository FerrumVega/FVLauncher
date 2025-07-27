@echo off
setlocal enabledelayedexpansion

for /f %%v in ('git describe --tags') do set TAG=%%v

powershell -Command "(Get-Content installer.iss) -replace 'MyAppVersion \"[^\"]+\"', 'MyAppVersion \"%TAG%\"' | Set-Content installer.iss"

python -m nuitka ^
    --onefile ^
    --windows-icon-from-ico=minecraft_title.ico ^
    --output-dir=dist ^
    main.py

if %ERRORLEVEL% neq 0 exit /b 1

iscc installer.iss

if %ERRORLEVEL% neq 0 exit /b 1

endlocal
