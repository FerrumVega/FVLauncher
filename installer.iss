#define MyAppName "FVLauncher"
#define MyAppVersion "1.0.0"   ; начальная версия, будет заменена в батнике
#define MyAppPublisher "FerrumVega"
#define MyAppURL "https://www.github.com/FerrumVega/FVLauncher"
#define MyAppExeName "main.exe"

[Setup]
AppId={{0E31B735-0AF6-46E0-A33D-701CFD1F9502}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DisableDirPage=yes
DisableProgramGroupPage=yes
LicenseFile=LICENSE
OutputBaseFilename=FVLauncher_Installer
SetupIconFile=minecraft_title.ico
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\main.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "background.png"; DestDir: "{app}"; Flags: ignoreversion
Source: "background1.png"; DestDir: "{app}"; Flags: ignoreversion
Source: "minecraft_title.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "minecraft_title.png"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: shellexec postinstall skipifsilent
