param([string]$OutputPath = (Join-Path $PSScriptRoot '../acceptance-output/application-discovery.json'))
$ErrorActionPreference = 'Stop'
$entries = [System.Collections.Generic.List[object]]::new()
$shell = New-Object -ComObject WScript.Shell
$menuRoots = @("$env:APPDATA/Microsoft/Windows/Start Menu/Programs", "$env:ProgramData/Microsoft/Windows/Start Menu/Programs")
foreach ($menu in $menuRoots) {
    foreach ($link in (Get-ChildItem -LiteralPath $menu -Filter *.lnk -Recurse -ErrorAction SilentlyContinue)) {
        try {
            $shortcut = $shell.CreateShortcut($link.FullName)
            $entries.Add([PSCustomObject]@{name=$link.BaseName; source='Start Menu'; path=$shortcut.TargetPath; arguments=$shortcut.Arguments; shortcut=$link.FullName; app_id=''; executable=''; install_location=''})
        } catch { }
    }
}
foreach ($root in @('HKCU:\Software\Microsoft\Windows\CurrentVersion\App Paths','HKLM:\Software\Microsoft\Windows\CurrentVersion\App Paths','HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths')) {
    foreach ($key in (Get-ChildItem -LiteralPath $root -ErrorAction SilentlyContinue)) {
        $value = (Get-Item -LiteralPath $key.PSPath).GetValue('')
        if ($value) { $entries.Add([PSCustomObject]@{name=$key.PSChildName; source='App Paths'; path=[Environment]::ExpandEnvironmentVariables($value).Trim('"'); arguments=''; shortcut=''; app_id=''; executable=''; install_location=''}) }
    }
}
$packages = @{}
foreach ($package in (Get-AppxPackage -ErrorAction SilentlyContinue)) { $packages[$package.PackageFamilyName] = $package }
foreach ($app in (Get-StartApps)) {
    $executable = ''; $location = ''
    if ($app.AppID.Contains('!')) {
        $parts = $app.AppID.Split('!',2)
        if ($packages.ContainsKey($parts[0])) {
            $package = $packages[$parts[0]]; $location = $package.InstallLocation
            try {
                $manifest = Get-AppxPackageManifest -Package $package.PackageFullName
                $application = $manifest.Package.Applications.Application | Where-Object { $_.Id -eq $parts[1] } | Select-Object -First 1
                if ($application.Executable -and -not $application.Executable.Contains('$')) { $executable = Join-Path $location $application.Executable }
            } catch { }
        }
    }
    $entries.Add([PSCustomObject]@{name=$app.Name; source='Registered Start application'; path=''; arguments=''; shortcut=''; app_id=$app.AppID; executable=$executable; install_location=$location})
}
foreach ($root in @('HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall','HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall','HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall')) {
    foreach ($key in (Get-ChildItem -LiteralPath $root -ErrorAction SilentlyContinue)) {
        $app = Get-ItemProperty -LiteralPath $key.PSPath -ErrorAction SilentlyContinue
        if ($app.DisplayName) { $entries.Add([PSCustomObject]@{name=$app.DisplayName; source='Installed software registry'; path=''; arguments=''; shortcut=''; app_id=''; executable=''; install_location=$app.InstallLocation}) }
    }
}
$entries | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $OutputPath -Encoding utf8
Write-Output "Inventoried $($entries.Count) registration records. No applications launched."
