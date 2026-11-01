#ifndef AppVersion
#define AppVersion "4.0.0"
#endif
#ifndef Publisher
#define Publisher "FLOTER"
#endif
#ifndef BundleDir
#define BundleDir "..\dist\FLOTER"
#endif
[Setup]
SetupIconFile=..\assets\branding\floter.ico
AppId={{9FBFAE65-0882-4B08-B99E-8F46C2D20B87}
AppName=FLOTER
AppVersion={#AppVersion}
AppPublisher={#Publisher}
DefaultDirName={localappdata}\Programs\FLOTER
DefaultGroupName=FLOTER
; Keep the existing installation directory on upgrade, but refresh its brand.
UsePreviousAppDir=yes
UsePreviousGroup=no
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.19041
OutputDir=..\dist\installer
OutputBaseFilename=FLOTER-{#AppVersion}-Setup
Compression=lzma2/fast
SolidCompression=yes
CloseApplications=yes
RestartApplications=no
UninstallDisplayIcon={app}\versions\{#AppVersion}\FLOTER.exe
VersionInfoVersion={#AppVersion}
SetupLogging=yes
LicenseFile=..\LICENSE
#ifdef SignRelease
SignTool=floter
SignedUninstaller=yes
#endif
[Files]
Source: "{#BundleDir}\*"; DestDir: "{app}\versions\{#AppVersion}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{group}\FLOTER"; Filename: "{app}\versions\{#AppVersion}\FLOTER.exe"; WorkingDir: "{app}\versions\{#AppVersion}"; IconFilename: "{app}\versions\{#AppVersion}\FLOTER.exe"; AppUserModelID: "FLOTER.Desktop"
Name: "{group}\Uninstall FLOTER"; Filename: "{uninstallexe}"
[Registry]
Root: HKCU; Subkey: "Software\Floter"; ValueType: string; ValueName: "Version"; ValueData: "{#AppVersion}"; Flags: uninsdeletevalue
[Run]
Filename: "{app}\versions\{#AppVersion}\FLOTER.exe"; Description: "Launch FLOTER"; Flags: nowait postinstall skipifsilent
[Code]
function InitializeSetup(): Boolean;
var Existing: String; OldVersion, NewVersion: Int64;
begin
  Result := True;
  if RegQueryStringValue(HKCU, 'Software\Floter', 'Version', Existing) then
    if StrToVersion(Existing, OldVersion) and StrToVersion('{#AppVersion}', NewVersion) then
    if ComparePackedVersion(OldVersion, NewVersion) > 0 then
    begin
      MsgBox('A newer FLOTER version is installed. Uninstall it before downgrading.', mbError, MB_OK);
      Result := False;
    end;
end;
