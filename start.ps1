$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$taskPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) {
    Write-Host '首次运行：创建项目专用环境并安装依赖。'
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) { throw '请先安装 uv，或使用 Python 3.12 创建 .venv 并安装 requirements.txt。' }
    uv venv --python 3.12 .venv
    if ($LASTEXITCODE -ne 0) { throw '环境创建失败。' }
    uv pip install --python $taskPython -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw '依赖安装失败。' }
}
Write-Host '浏览器打开 http://127.0.0.1:4180；关闭本窗口将停止服务。'
& $taskPython -X utf8 server.py
