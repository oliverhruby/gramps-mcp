<#
.LOCAL-ONLY: runs the live integration suite against the real backend and
writes a report containing real user data to ./reports (optionally validates
identities from tests/e2e/.local.e2e.json). It must never run in public CI or
on a machine whose output could be published.

Requirements: GRAMPS_MCP_USERNAME, GRAMPS_MCP_PASSWORD, GRAMPS_MCP_INSTANCES
set in the current shell.
#>
$ErrorActionPreference = "Stop"

$Required = @("GRAMPS_MCP_USERNAME", "GRAMPS_MCP_PASSWORD", "GRAMPS_MCP_INSTANCES")
$Missing = @($Required | Where-Object { -not [Environment]::GetEnvironmentVariable($_) })
if ($Missing) {
    Write-Error "Missing env var(s): $($Missing -join ', '). Set them (e.g. from .env) then re-run."
    exit 1
}

$env:GRAMPS_MCP_E2E = "1"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$Py = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Py)) { $Py = "python" }
if (-not (& $Py -m pytest --version 2>$null)) {
    Write-Error "pytest not available for $Py. Install it (e.g. python -m pip install pytest)."
    exit 1
}

& $Py -m pytest -m e2e -v tests/e2e
$Code = $LASTEXITCODE
Write-Host ""
Write-Host "e2e report: $Root\reports\e2e-report.json  (gitignored - contains real user data)"
exit $Code