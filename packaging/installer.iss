; Kalpavriksha Founder Edition — Inno Setup installer.
; Build the app first:  pyinstaller packaging/kalpavriksha.spec --noconfirm
; Then compile this:    iscc packaging/installer.iss
;
; Produces a real Windows installer .exe: Start Menu shortcut, Desktop
; shortcut, application icon, version metadata, uninstaller. No admin
; privileges are required — the default install directory is per-user
; (%LOCALAPPDATA%), matching how this build environment itself has no
; elevated rights; a machine-wide install is a one-line change
; (PrivilegesRequired) for whoever ships this with admin available.

#define MyAppName "Kalpavriksha"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "Kalpavriksha"
#define MyAppExeName "Kalpavriksha.exe"
#define MyDistDir "..\dist\Kalpavriksha"

[Setup]
AppId={{B4E1F5C2-6A3D-4F8E-9C1A-3D2E7F8A9B10}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\dist\installer
OutputBaseFilename=KalpavrikshaSetup-{#MyAppVersion}
SetupIconFile=..\desktop_app\assets\kalpavriksha.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "{#MyDistDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent
