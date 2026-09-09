; Inno Setup script for CAMCO Coordinator.
; Build the PyInstaller output first (scripts\build_exe.py), then compile
; this script with Inno Setup (ISCC.exe) to produce a Windows installer.
;
; ISCC.exe packaging\inno_setup.iss

#define MyAppName "CAMCO Coordinator"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "CAMCO Manufacturing"
#define MyAppExeName "CAMCO_Coordinator.exe"

[Setup]
AppId={{6C7E6C2C-6E6E-4B0B-9C1E-CAMCOCOORD01}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\dist\installer
OutputBaseFilename=CAMCO_Coordinator_Setup_{#MyAppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
; Per-user application data (database, logs, backups) lives under
; %LOCALAPPDATA%, so the app itself does not need admin rights to run -
; only the installer needs elevation to write to Program Files.
PrivilegesRequired=admin

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Files]
Source: "..\dist\CAMCO_Coordinator\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
