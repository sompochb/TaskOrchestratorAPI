$ErrorActionPreference = "Stop"
$base = "http://127.0.0.1:8000"
$health = Invoke-RestMethod "$base/health" -TimeoutSec 10
Write-Host "Health:" ($health | ConvertTo-Json -Compress)
$agents = Invoke-RestMethod "$base/agents" -TimeoutSec 10
Write-Host "Agents:" ($agents | ConvertTo-Json -Compress)
Write-Host "Smoke test completed. This does not verify autonomous worker execution or production security."
