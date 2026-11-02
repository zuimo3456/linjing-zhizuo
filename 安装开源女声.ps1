$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) { throw '请先安装 uv。' }
$taskVoicePython = Join-Path $PSScriptRoot '.tts-venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $taskVoicePython)) {
    uv venv --python 3.12 .tts-venv
    if ($LASTEXITCODE -ne 0) { throw '配音环境创建失败。' }
}
uv pip install --python $taskVoicePython torch==2.7.1 torchaudio==2.7.1 --index-url https://download.pytorch.org/whl/cu128
if ($LASTEXITCODE -ne 0) { throw 'CUDA运行库安装失败。' }
uv pip install --python $taskVoicePython qwen-tts==0.1.1
if ($LASTEXITCODE -ne 0) { throw 'Qwen配音依赖安装失败。' }
& $taskVoicePython -X utf8 setup_qwen_voice.py
if ($LASTEXITCODE -ne 0) { throw '模型下载或校验失败。' }
Write-Host '开源女声安装完毕。请重新启动网站，然后重新生成剪辑方案。'
