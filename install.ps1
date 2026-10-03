# Copies the plugin into ~/.nuke and hooks it into menu.py (idempotent).
$dst = Join-Path $env:USERPROFILE ".nuke"
New-Item -ItemType Directory -Force $dst | Out-Null
Copy-Item -Recurse -Force "$PSScriptRoot\nuke_discord_rpc" $dst
$menu = Join-Path $dst "menu.py"
$line = "import nuke_discord_rpc; nuke_discord_rpc.start()"
if (-not (Test-Path $menu) -or -not (Select-String -Path $menu -SimpleMatch $line -Quiet)) {
    Add-Content $menu "`n$line"
}
Write-Host "Installed to $dst. Restart Nuke."
