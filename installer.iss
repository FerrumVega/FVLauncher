[Setup]
AppId={{0E31B735-0AF6-46E0-A33D-701CFD1F9502}}
AppName=FVLauncher
AppVersion=1.0.0
AppPublisher=FerrumVega
AppPublisherURL=https://www.github.com/FerrumVega/FVLauncher
AppSupportURL=https://www.github.com/FerrumVega/FVLauncher
AppUpdatesURL=https://www.github.com/FerrumVega/FVLauncher
DefaultDirName={autopf}\FVLauncher
DisableDirPage=yes
DisableProgramGroupPage=yes
LicenseFile=LICENSE
OutputBaseFilename=FVLauncher_Installer
SetupIconFile=assets\minecraft_title.ico
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\main.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "assets\background.png"; DestDir: "{app}\assets"; Flags: ignoreversion
Source: "assets\background1.png"; DestDir: "{app}\assets"; Flags: ignoreversion
Source: "assets\minecraft_title.ico"; DestDir: "{app}\assets"; Flags: ignoreversion
Source: "assets\minecraft_title.png"; DestDir: "{app}\assets"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\FVLauncher"; Filename: "{app}\main.exe"
Name: "{autodesktop}\FVLauncher"; Filename: "{app}\main.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\main.exe"; Description: "{cm:LaunchProgram,FVLauncher}"; Flags: shellexec postinstall skipifsilent
