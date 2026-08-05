; VoxSlide AI — Inno Setup script
; Keep MyAppVersion in sync with version.py (see RELEASE.md).

#define MyAppVersion "1.0.0"
#define MyAppName "VoxSlide AI"
#define MyAppPublisher "Mohammad Ahmad"
#define MyAppExeName "VoxSlide AI.exe"

[Setup]
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
OutputDir=installer_output
OutputBaseFilename=VoxSlideAI_Setup
Compression=lzma2
SolidCompression=yes
SetupIconFile=icon.ico
; Allow upgrading over a previous install without prompting for a new folder
DisableDirPage=auto
PrivilegesRequired=admin
CloseApplications=yes
RestartApplications=no

[Files]
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
