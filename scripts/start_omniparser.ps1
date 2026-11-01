param([ValidateSet('cuda','cpu')][string]$Device = 'cuda')
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$python = Join-Path $root '.tools\omniparser-env\Scripts\python.exe'
$script = Join-Path $PSScriptRoot 'omniparser_service.py'
if (!(Test-Path -LiteralPath $python)) { throw 'Provision the separate OmniParser environment first; see GUI_NAVIGATION.md.' }
$logs = Join-Path $root 'acceptance-output'
New-Item -ItemType Directory -Path $logs -Force | Out-Null
$serviceArguments = @(('"' + $script + '"'), '--device', $Device)
Start-Process -FilePath $python -ArgumentList $serviceArguments -WorkingDirectory $root -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logs 'omniparser-service.log') -RedirectStandardError (Join-Path $logs 'omniparser-service-errors.log') -PassThru
