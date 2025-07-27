@echo off
setlocal enabledelayedexpansion

rem Получаем тег из git
for /f %%v in ('git describe --tags') do set TAG=%%v

rem Обновляем версию в инсталляторе
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
move /Y installer_tmp.iss installer.iss >nul

rem Собираем с PyInstaller
pyinstaller --onefile --windowed --icon=assets\minecraft_title.ico --distpath dist main.py

if %ERRORLEVEL% neq 0 exit /b 1

rem Компиляция инсталлятора Inno Setup
iscc installer.iss

if %ERRORLEVEL% neq 0 exit /b 1

endlocal
