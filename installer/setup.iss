; Inno Setup Script for Ultimate Image Compressor
; This script expects a define 'AppRoot' passed from the command line.

#ifndef AppRoot
  #error "This script must be compiled via the build.bat script."
#endif

[Setup]
AppId={{C1A8A331-B6E7-4E8F-8E5A-A7E08249F278}}
AppName=Ultimate Image Compressor
AppVersion=2.0.0
AppPublisher=Pro-Coder-Boy
; Fix Issue #12: No admin needed — install per-user
PrivilegesRequired=lowest
DefaultDirName={localappdata}\UltimateImageCompressor
DefaultGroupName=Ultimate Image Compressor
DisableProgramGroupPage=yes
ArchitecturesAllowed=x64
Compression=lzma
SolidCompression=yes
WizardStyle=modern
; Use the defined AppRoot to create absolute paths
OutputDir={#AppRoot}\InstallerOutput
OutputBaseFilename=Setup-ImageCompressor-v2.0.0
SetupIconFile={#AppRoot}\icon.ico

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}";
Name: "sendtoicon"; Description: "Add shortcut to 'Send To' menu"; GroupDescription: "{cm:AdditionalIcons}";

[Files]
; Source path now uses the robust AppRoot define
Source: "{#AppRoot}\dist\compressor\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Ultimate Image Compressor"; Filename: "{app}\compressor.exe"
Name: "{group}\{cm:UninstallProgram,Ultimate Image Compressor}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Ultimate Image Compressor"; Filename: "{app}\compressor.exe"; Tasks: desktopicon
Name: "{userappdata}\Microsoft\Windows\SendTo\Image Compressor"; Filename: "{app}\compressor.exe"; Tasks: sendtoicon;

[Run]
Filename: "{app}\compressor.exe"; Description: "{cm:LaunchProgram,Ultimate Image Compressor}"; Flags: nowait postinstall skipifsilent

; Fix Issue #12: Use HKCU instead of HKCR — no admin required
[Registry]
Root: HKCU; Subkey: "Software\Classes\Applications\compressor.exe"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\Applications\compressor.exe\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\compressor.exe"" --shift ""%1"""
Root: HKCU; Subkey: "Software\Classes\.jpeg\OpenWithProgids"; ValueType: string; ValueName: "ImageCompressor.File"; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Classes\.jpg\OpenWithProgids"; ValueType: string; ValueName: "ImageCompressor.File"; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Classes\.png\OpenWithProgids"; ValueType: string; ValueName: "ImageCompressor.File"; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Classes\.webp\OpenWithProgids"; ValueType: string; ValueName: "ImageCompressor.File"; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Classes\ImageCompressor.File"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\ImageCompressor.File\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\compressor.exe,0"
Root: HKCU; Subkey: "Software\Classes\ImageCompressor.File\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\compressor.exe"" --shift ""%1"""
