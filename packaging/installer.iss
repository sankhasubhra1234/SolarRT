; Inno Setup script for the SolarRT Windows installer.
; Build after PyInstaller:  ISCC packaging\installer.iss   (or run packaging\build.ps1)

#define AppName "SolarRT"
#define AppVersion "2.0.0"
#define AppPublisher "S. Debnath"
#define AppExe "SolarRT.exe"

[Setup]
AppId={{6C2E1B7A-4F3D-4C8E-9A51-5B0D3E7F2A91}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL=https://www.linkedin.com/in/sankha-debnath/
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
; Per-user install by default (no admin prompt); users can choose "all users" instead.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist\installer
OutputBaseFilename=SolarRT-Setup-{#AppVersion}
SetupIconFile=solarrt.ico
UninstallDisplayIcon={app}\{#AppExe}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
VersionInfoVersion={#AppVersion}
VersionInfoDescription={#AppName} installer

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\SolarRT\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Logs and saved settings live in %LOCALAPPDATA%\SolarRT
Type: filesandordirs; Name: "{localappdata}\{#AppName}"

[Code]
// The app's window needs Microsoft Edge WebView2 (preinstalled on Windows 10/11 in most cases).
function WebView2Installed(): Boolean;
var v: String;
begin
  Result :=
    RegQueryStringValue(HKLM, 'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', v) or
    RegQueryStringValue(HKCU, 'Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', v);
  Result := Result and (v <> '') and (v <> '0.0.0.0');
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if (CurStep = ssPostInstall) and (not WebView2Installed()) then
    MsgBox('SolarRT works best with the Microsoft Edge WebView2 Runtime, which was not found.' + #13#10 +
           'Without it, SolarRT opens in your web browser instead.' + #13#10#13#10 +
           'Get it free from: https://developer.microsoft.com/microsoft-edge/webview2/',
           mbInformation, MB_OK);
end;
