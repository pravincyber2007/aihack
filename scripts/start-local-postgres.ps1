$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$envPath = Join-Path $repoRoot ".env"
$dataDir = Join-Path $env:LOCALAPPDATA "StaffPortalPostgres\data"
$logPath = Join-Path $env:LOCALAPPDATA "StaffPortalPostgres\postgres.log"
$postgresBin = Join-Path $env:ProgramFiles "PostgreSQL\18\bin"
$initdb = Join-Path $postgresBin "initdb.exe"
$pgCtl = Join-Path $postgresBin "pg_ctl.exe"
$psql = Join-Path $postgresBin "psql.exe"
$maintenancePasswordPath = Join-Path (Split-Path -Parent $dataDir) "maintenance-password.txt"
$port = 5433

function New-RandomPassword {
    $bytes = [byte[]]::new(32)
    $generator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $generator.GetBytes($bytes)
    } finally {
        $generator.Dispose()
    }
    return [Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+', '-').Replace('/', '_')
}

foreach ($tool in @($initdb, $pgCtl, $psql)) {
    if (-not (Test-Path $tool)) {
        throw "Required PostgreSQL tool was not found: $tool"
    }
}

if (-not (Test-Path $envPath)) {
    throw "Copy .env.example to .env in the repository root before starting PostgreSQL."
}

$envLines = [System.Collections.Generic.List[string]]::new()
$envLines.AddRange([string[]](Get-Content $envPath))
$databaseUrlLine = $envLines | Where-Object { $_ -match '^DATABASE_URL=' } | Select-Object -First 1
$databaseUrl = if ($databaseUrlLine) { $databaseUrlLine -replace '^DATABASE_URL=', '' } else { "" }
$databaseUri = $null
if ($databaseUrl -and $databaseUrl -notmatch 'SET_YOUR_PASSWORD|YOUR_PASSWORD|<your-password>') {
    $databaseUri = [Uri]($databaseUrl -replace '^postgresql\+psycopg', 'postgresql')
}

if (Test-Path (Join-Path $dataDir "PG_VERSION")) {
    if (-not $databaseUri -or $databaseUri.Port -ne $port) {
        throw "The dedicated database already exists. Set DATABASE_URL in .env to its existing credentials before restarting it."
    }
    $appPassword = [Uri]::UnescapeDataString($databaseUri.UserInfo.Split(':', 2)[1])
    $initializedNewCluster = $false
} else {
    $existingPort = Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue
    if ($existingPort) {
        throw "Port $port is already in use. The dedicated PostgreSQL instance was not started."
    }

    $currentPassword = ""
    $passwordLine = $envLines | Where-Object { $_ -match '^POSTGRES_PASSWORD=' } | Select-Object -First 1
    if ($passwordLine) {
        $currentPassword = $passwordLine -replace '^POSTGRES_PASSWORD=', ''
    }
    if ($currentPassword -and $currentPassword -notmatch 'SET_YOUR_PASSWORD|YOUR_PASSWORD') {
        $appPassword = $currentPassword.Trim('"')
    } else {
        $appPassword = New-RandomPassword
    }

    $databaseUrl = "postgresql+psycopg://staff_portal:$appPassword@127.0.0.1:$port/staff_portal"
    $environmentValues = @{
        DATABASE_URL      = $databaseUrl
        POSTGRES_DB       = "staff_portal"
        POSTGRES_USER     = "staff_portal"
        POSTGRES_PASSWORD = $appPassword
    }
    $updatedLines = foreach ($line in $envLines) {
        if ($line -match '^(DATABASE_URL|POSTGRES_DB|POSTGRES_USER|POSTGRES_PASSWORD)=') {
            $key = $matches[1]
            "$key=$($environmentValues[$key])"
        } else {
            $line
        }
    }
    [System.IO.File]::WriteAllLines($envPath, [string[]]$updatedLines, [System.Text.UTF8Encoding]::new($false))

    $dataParent = Split-Path -Parent $dataDir
    if (-not (Test-Path $dataParent)) {
        New-Item -ItemType Directory -Path $dataParent | Out-Null
    }
    $maintenancePassword = New-RandomPassword
    [System.IO.File]::WriteAllText(
        $maintenancePasswordPath,
        $maintenancePassword,
        [System.Text.UTF8Encoding]::new($false)
    )
    if (Test-Path $dataDir) {
        if ((Get-ChildItem -Force $dataDir | Measure-Object).Count -ne 0) {
            throw "The database data directory exists and is not empty; refusing to overwrite it."
        }
    } else {
        New-Item -ItemType Directory -Path $dataDir | Out-Null
    }

    $passwordFile = Join-Path $env:TEMP "staff-portal-postgres-password-$([Guid]::NewGuid().ToString('N')).txt"
    try {
        [System.IO.File]::WriteAllText(
            $passwordFile,
            $maintenancePassword + [Environment]::NewLine,
            [System.Text.UTF8Encoding]::new($false)
        )
        & $initdb --username=staff_portal_maintenance --pwfile=$passwordFile --auth-local=scram-sha-256 --auth-host=scram-sha-256 --encoding=UTF8 --no-locale --pgdata=$dataDir
        if ($LASTEXITCODE -ne 0) {
            throw "PostgreSQL initialization failed with exit code $LASTEXITCODE."
        }
    } finally {
        Remove-Item $passwordFile -Force -ErrorAction SilentlyContinue
    }
    $initializedNewCluster = $true
}

$listener = Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue
if (-not $listener) {
    & $pgCtl start --pgdata=$dataDir --log=$logPath --options="-h 127.0.0.1 -p $port" --wait
    if ($LASTEXITCODE -ne 0) {
        throw "PostgreSQL failed to start. Check the local log at $logPath."
    }
}

if ($initializedNewCluster) {
    $maintenancePassword = [System.IO.File]::ReadAllText($maintenancePasswordPath).Trim()
    $env:PGPASSWORD = $maintenancePassword
    & $psql --host=127.0.0.1 --port=$port --username=staff_portal_maintenance --dbname=postgres --no-password --set=ON_ERROR_STOP=1 --command="CREATE ROLE staff_portal LOGIN PASSWORD '$appPassword' NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION"
    if ($LASTEXITCODE -ne 0) {
        Remove-Item Env:\PGPASSWORD -ErrorAction SilentlyContinue
        throw "Could not create the limited-privilege application role."
    }
    & $psql --host=127.0.0.1 --port=$port --username=staff_portal_maintenance --dbname=postgres --no-password --set=ON_ERROR_STOP=1 --command="CREATE DATABASE staff_portal OWNER staff_portal"
    if ($LASTEXITCODE -ne 0) {
        Remove-Item Env:\PGPASSWORD -ErrorAction SilentlyContinue
        throw "Could not create the application database."
    }
    Remove-Item Env:\PGPASSWORD -ErrorAction SilentlyContinue
} else {
    $env:PGPASSWORD = $appPassword
}

$env:PGPASSWORD = $appPassword
$connectionCheck = & $psql --host=127.0.0.1 --port=$port --username=staff_portal --dbname=staff_portal --no-password --tuples-only --no-align --set=ON_ERROR_STOP=1 --command="SELECT 1"
if ($LASTEXITCODE -ne 0 -or ($connectionCheck -join "").Trim() -ne "1") {
    Remove-Item Env:\PGPASSWORD -ErrorAction SilentlyContinue
    throw "Could not verify the limited-privilege application database connection."
}
Remove-Item Env:\PGPASSWORD -ErrorAction SilentlyContinue

Write-Output "Dedicated PostgreSQL is ready at 127.0.0.1:$port (database staff_portal)."
