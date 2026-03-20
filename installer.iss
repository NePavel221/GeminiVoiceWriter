; Inno Setup Script for Gemini Voice Writer
; Portable установщик - все данные хранятся в папке установки

#define MyAppName "Gemini Voice Writer"
#define MyAppVersion "2.0.0"
#define MyAppPublisher "Gemini Voice Writer"
#define MyAppExeName "GeminiVoiceWriter.exe"

[Setup]
; Уникальный ID приложения
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
; По умолчанию в Program Files (x86)
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
; Выходной файл установщика
OutputDir=.
OutputBaseFilename=GeminiVoiceWriter_Setup
; Сжатие
Compression=lzma2
SolidCompression=yes
; Иконка установщика
SetupIconFile=icon.ico
; Установка только для текущего пользователя (без прав админа)
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=
; Wizard style
WizardStyle=modern
; Разрешить пользователю выбрать папку
DisableDirPage=no
; Информация о приложении
AppComments=Голосовой ввод текста с помощью Gemini AI
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
; Ярлык на рабочем столе включен по умолчанию
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Dirs]
; Создаём папку data для хранения всех данных приложения
Name: "{app}\data"; Permissions: users-full
Name: "{app}\data\recordings"; Permissions: users-full
Name: "{app}\data\logs"; Permissions: users-full

[Files]
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Открыть папку данных"; Filename: "{app}\data"
Name: "{group}\Удалить {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; При удалении спрашиваем про данные (логи, записи, настройки)
Type: dirifempty; Name: "{app}\data\logs"
Type: dirifempty; Name: "{app}\data\recordings"
Type: dirifempty; Name: "{app}\data"
Type: dirifempty; Name: "{app}"
