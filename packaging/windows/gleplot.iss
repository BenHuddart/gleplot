; gleplot Windows Installer (Inno Setup 6)
;
; Build variables (passed via /D on the iscc command line):
;   AppVersion   — M.N.P version string (e.g. 1.2.0)
;   AppDir       — absolute path to PyInstaller onedir output (dist\gleplot)
;   IconFile     — absolute path to .ico
;   OutputDir    — directory to place the finished installer
;   OutputName   — (optional) installer base filename without extension;
;                  defaults to gleplot-{AppVersion}-windows-x64

#define AppName    "gleplot"
#define AppExeName "gleplot.exe"
#define Publisher  "gleplot contributors"
#define AppId      "io.github.benhuddart.gleplot"
#ifndef OutputName
  #define OutputName "gleplot-" + AppVersion + "-windows-x64"
#endif

[Setup]
AppId={#AppId}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#Publisher}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
OutputDir={#OutputDir}
OutputBaseFilename={#OutputName}
SetupIconFile={#IconFile}
UninstallDisplayIcon={app}\gleplot.ico
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
MinVersion=10.0
CloseApplications=yes
CloseApplicationsFilter=*.exe
RestartApplications=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "{#AppDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#IconFile}"; DestDir: "{app}"; DestName: "gleplot.ico"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\gleplot.ico"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\gleplot.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
