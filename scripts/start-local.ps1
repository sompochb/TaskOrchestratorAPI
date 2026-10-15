$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
if (-not (Test-Path ".venv/Scripts/python.exe")) { py -3 -m venv .venv }
$python = Join-Path (Get-Location) ".venv/Scripts/python.exe"
& $python -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed" }
& $python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
