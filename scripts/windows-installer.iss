#ifndef SourceDir
  #define SourceDir "..\build\windows\dist\PongWars"
#endif

[Setup]
AppId={{CF4C06F1-EE00-4E0B-AF45-52EF5CB84E9F}
AppName=PongWars
AppVersion={#AppVersion}
AppPublisher=PongWars
DefaultDirName={localappdata}\Programs\PongWars
DefaultGroupName=PongWars
UninstallDisplayIcon={app}\PongWars.exe
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=.
OutputBaseFilename=PongWars-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\PongWars"; Filename: "{app}\PongWars.exe"
Name: "{autodesktop}\PongWars"; Filename: "{app}\PongWars.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\PongWars.exe"; Description: "{cm:LaunchProgram,PongWars}"; Flags: postinstall nowait skipifsilent
