#define AppName "CT-BAYES Desktop"
#define AppVersion "1.0.0"
#define AppPublisher "CT-BAYES"
#define AppExeName "CTBayesDesktop.exe"

[Setup]
AppId={{A17B34DD-56A4-4860-A6E7-8A6E7CBA0001}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={localappdata}\Programs\CT-BAYES
DefaultGroupName={#AppName}
PrivilegesRequired=lowest
OutputDir=installer_output
OutputBaseFilename=CTBayesDesktopSetup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#AppExeName}

[Files]
Source: "dist\CTBayesDesktop\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: ".env.example"; DestDir: "{app}"; DestName: ".env.example"; Flags: ignoreversion onlyifdoesntexist

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Launch CT-BAYES Desktop"; Flags: postinstall nowait skipifsilent
