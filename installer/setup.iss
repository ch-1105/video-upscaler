; Video Upscaler 安装程序
; 使用 Inno Setup 6 编译

#define MyAppName "Video Upscaler"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Video Upscaler Team"
#define MyAppURL "https://github.com/ch-1105/video-upscaler"
#define MyAppExeName "VideoUpscaler.exe"

[Setup]
; 基本信息
AppId={{B1A3C2D4-E5F6-7890-1234-567890ABCDEF}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

; 默认安装路径
DefaultDirName={autopf}\{#MyAppName}
DisableProgramGroupPage=yes

; 许可协议
LicenseFile=..\LICENSE

; 输出设置
OutputDir=..\dist\installer
OutputBaseFilename=VideoUpscaler-{#MyAppVersion}-Setup

; 压缩设置
Compression=lzma2
SolidCompression=yes

; 界面设置
WizardStyle=modern
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}

; 权限设置
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog

; 版本信息
VersionInfoVersion={#MyAppVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName} Setup

[Languages]
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked; OnlyBelowVersion: 6.1; Check: not IsAdminInstallMode

[Files]
; 主程序
Source: "..\dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

; Python 运行时
Source: "..\dist\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; 模型文件 (如果已下载)
Source: "..\models\*"; DestDir: "{app}\models"; Flags: ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist

; FFmpeg (如果打包了)
Source: "..\ffmpeg\*"; DestDir: "{app}\ffmpeg"; Flags: ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist

; 文档
Source: "..\README.md"; DestDir: "{app}"; DestName: "README.txt"; Flags: isreadme
Source: "..\LICENSE"; DestDir: "{app}"; DestName: "LICENSE.txt"

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: quicklaunchicon

[Run]
; 首次运行提示
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\temp"
Type: filesandordirs; Name: "{app}\logs"

[Code]
// 检查系统要求
function InitializeSetup(): Boolean;
var
  Version: String;
begin
  // 检查 Windows 版本
  if not IsWindows10OrGreater() then
  begin
    MsgBox('{#MyAppName} 需要 Windows 10 或更高版本。', mbError, MB_OK);
    Result := false;
    exit;
  end;
  
  Result := true;
end;

// 检查是否已安装
function InitializeUninstall(): Boolean;
begin
  Result := true;
end;

// 安装完成后检查模型
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    // 可以在这里执行额外的安装后任务
  end;
end;
