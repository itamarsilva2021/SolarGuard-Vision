; ==============================================================================
; Inno Setup Script para Criação do Instalador Windows do SolarGuard Vision
; Produz o executável final: Setup_SolarGuard_Vision_v1.0.0.exe
; ==============================================================================

#define MyAppName "SolarGuard Vision"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "SolarGuard Vision Solutions"
#define MyAppURL "https://www.solarguard.vision"
#define MyAppExeName "SolarGuard_Vision.exe"

[Setup]
; Identificador único de instalação gerado para a aplicação
AppId={{D37E84B1-2F10-48C6-A587-99E746F9E10A}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} v{#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DisableProgramGroupPage=yes
DefaultGroupName={#MyAppName}
OutputDir=..\dist\installer
OutputBaseFilename=Setup_SolarGuard_Vision_v{#MyAppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Copia todos os arquivos da pasta gerada pelo PyInstaller (dist\SolarGuard_Vision)
Source: "..\dist\SolarGuard_Vision\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
