# Launch the built app with this checkout's private local configuration.
$ErrorActionPreference = 'Stop'
$env:FLOTER_ENV_FILE = Join-Path $PSScriptRoot '.env'
& (Join-Path $PSScriptRoot 'dist\FLOTER\FLOTER.exe')
