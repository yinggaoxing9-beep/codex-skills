[CmdletBinding()]
param(
    [string]$DataRoot,
    [string]$Python = 'python',
    [switch]$Login,
    [ValidateSet('msedge','chrome','chromium')][string]$Channel = 'msedge'
)
$ErrorActionPreference = 'Stop'
$archiveScript = Join-Path $PSScriptRoot 'archive.py'
if (-not $DataRoot) {
    $diagnostic = & $Python -X utf8 -B $archiveScript doctor | ConvertFrom-Json
    if ($LASTEXITCODE -ne 0) { throw '数据目录自检失败' }
    $DataRoot = $diagnostic.data_root
}
$diagnostic = & $Python -X utf8 -B $archiveScript --data-root $DataRoot doctor | ConvertFrom-Json
if ($LASTEXITCODE -ne 0) { throw ('数据目录自检失败：' + $diagnostic.status + ' ' + $diagnostic.message) }
$DataRoot = $diagnostic.data_root
# Restrict this dedicated data directory. Never run this against an unrelated folder.
$owner = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
& icacls.exe $DataRoot /inheritance:r /grant:r "${owner}:(OI)(CI)F" '*S-1-5-18:(OI)(CI)F' | Out-Null
if ($LASTEXITCODE -ne 0) { throw '数据目录 ACL 设置失败；未继续安装' }
$venvPath = Join-Path $DataRoot '.venv'
$browserPython = Join-Path $venvPath 'Scripts\python.exe'
if (-not (Test-Path -LiteralPath $browserPython)) {
    & $Python -m venv $venvPath
    if ($LASTEXITCODE -ne 0) { throw '独立 Python 环境创建失败' }
}
& $browserPython -B -c "import importlib.metadata; assert importlib.metadata.version('playwright') == '1.56.0'" 2>$null
if ($LASTEXITCODE -ne 0) {
    & $browserPython -m pip install --disable-pip-version-check 'playwright==1.56.0'
    if ($LASTEXITCODE -ne 0) { throw '浏览器依赖安装失败' }
}
if ($Channel -eq 'chromium') {
    & $browserPython -m playwright install chromium
    if ($LASTEXITCODE -ne 0) { throw '独立 Chromium 安装失败' }
}
Write-Host "浏览器依赖已就绪：$browserPython"
if ($Login) {
    & $browserPython -X utf8 -B $archiveScript --data-root $DataRoot login --channel $Channel
    if ($LASTEXITCODE -ne 0) { throw '登录未完成；凭据不会输出到终端' }
}
