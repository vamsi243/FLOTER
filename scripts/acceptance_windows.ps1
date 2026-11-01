param([Parameter(Mandatory=$true)][string]$Installer, [string]$PreviousInstaller)
# Run only in a disposable Windows Sandbox or VM: installs and uninstalls FLOTER.
$ErrorActionPreference = 'Stop'
$target = Join-Path $env:LOCALAPPDATA 'Programs\FLOTER'
function Install-TestBuild([string]$Path) {
    $process = Start-Process -FilePath (Resolve-Path -LiteralPath $Path).Path -ArgumentList '/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART' -WindowStyle Hidden -Wait -PassThru
    if ($process.ExitCode -ne 0) { throw "Installer failed: $($process.ExitCode)" }
}
if (Test-Path 'HKCU:\Software\Floter') { throw 'Use a clean VM without existing Floter.' }
if ($PreviousInstaller) { Install-TestBuild $PreviousInstaller }
Install-TestBuild $Installer
$registration = Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\{9FBFAE65-0882-4B08-B99E-8F46C2D20B87}_is1'
$target = $registration.InstallLocation
$version = (Get-ItemProperty 'HKCU:\Software\Floter').Version
$exe = Join-Path $target "versions\$version\FLOTER.exe"
if (!(Test-Path -LiteralPath $exe)) { throw 'Installed executable missing' }
$process = Start-Process -FilePath $exe -ArgumentList '--smoke-test' -WorkingDirectory $env:TEMP -WindowStyle Hidden -Wait -PassThru
if ($process.ExitCode -ne 0) { throw 'Installed startup failed' }
Install-TestBuild $Installer
$uninstaller = Join-Path $target 'unins000.exe'
$process = Start-Process -FilePath $uninstaller -ArgumentList '/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART' -WindowStyle Hidden -Wait -PassThru
if ($process.ExitCode -ne 0) { throw 'Uninstall failed' }
if (Test-Path -LiteralPath $exe) { throw 'Executable remains after uninstall' }
if (Test-Path 'HKCU:\Software\Floter') {
    if ((Get-ItemProperty 'HKCU:\Software\Floter' -ErrorAction SilentlyContinue).Version) { throw 'Version registration remains' }
}
Write-Output 'Install, startup, reinstall/upgrade and uninstall passed.'
