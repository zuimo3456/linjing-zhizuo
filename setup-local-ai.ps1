$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$taskPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
uv pip install --python $taskPython -r requirements-local-ai.txt
if ($LASTEXITCODE -ne 0) { throw 'Local AI dependency installation failed.' }
& $taskPython -X utf8 setup_onnx_model.py
if ($LASTEXITCODE -ne 0) { throw 'Model download failed. Rerun to resume download parts.' }
