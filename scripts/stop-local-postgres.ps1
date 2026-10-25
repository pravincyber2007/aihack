$ErrorActionPreference = "Stop"

$dataDir = Join-Path $env:LOCALAPPDATA "StaffPortalPostgres\data"
$pgCtl = Join-Path $env:ProgramFiles "PostgreSQL\18\bin\pg_ctl.exe"

if (-not (Test-Path (Join-Path $dataDir "PG_VERSION"))) {
    throw "The dedicated Staff Portal PostgreSQL data directory was not found."
}
if (-not (Test-Path $pgCtl)) {
    throw "PostgreSQL control tool was not found: $pgCtl"
}

& $pgCtl stop --pgdata=$dataDir --mode=fast --wait
if ($LASTEXITCODE -ne 0) {
    throw "The dedicated Staff Portal PostgreSQL instance could not be stopped."
}
