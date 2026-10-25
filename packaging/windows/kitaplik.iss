; Kitaplık Windows kurulumu (Inno Setup 6)
; AppId sabittir: güncellemeler aynı kurulumun üzerine yazar,
; Başlat menüsü kısayolu ve dosya ilişkilendirmeleri korunur.
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{6F1C2A7E-4B8D-4C3A-9E51-2D7B8F0A1C64}
AppName=Kitaplık
AppVersion={#AppVersion}
AppVerName=Kitaplık {#AppVersion}
AppPublisher=cafercan
AppPublisherURL=https://github.com/cafercan/kitaplik
DefaultDirName={autopf}\Kitaplik
DefaultGroupName=Kitaplık
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\..\dist
OutputBaseFilename=kitaplik-{#AppVersion}-windows-x64-setup
SetupIconFile=..\icons\kitaplik.ico
UninstallDisplayIcon={app}\Kitaplik.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\..\dist\Kitaplik\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Kitaplık"; Filename: "{app}\Kitaplik.exe"
Name: "{autodesktop}\Kitaplık"; Filename: "{app}\Kitaplik.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Kitaplik.exe"; Description: "{cm:LaunchProgram,Kitaplık}"; Flags: nowait postinstall skipifsilent
