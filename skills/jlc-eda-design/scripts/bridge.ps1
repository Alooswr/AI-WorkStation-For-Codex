[CmdletBinding()]
param(
    [ValidateSet('status', 'start', 'stop')]
    [string]$Action = 'status',

    [ValidateRange(1, 30)]
    [int]$WaitSeconds = 8
)

$ErrorActionPreference = 'Stop'
$easyEdaSkillRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\easyeda-api'))
$serverPath = Join-Path $easyEdaSkillRoot 'scripts\bridge-server.mjs'

function Get-EasyEdaBridge {
    foreach ($port in 49620..49629) {
        try {
            $health = Invoke-RestMethod -Uri "http://127.0.0.1:$port/health" -TimeoutSec 1
            if ($health.service -eq 'easyeda-bridge') {
                return [pscustomobject]@{
                    port = $port
                    health = $health
                }
            }
        }
        catch {
            continue
        }
    }

    return $null
}

function Write-BridgeResult {
    param([object]$Value)
    $Value | ConvertTo-Json -Depth 8
}

if ($Action -eq 'status') {
    $bridge = Get-EasyEdaBridge
    if ($null -eq $bridge) {
        Write-BridgeResult ([pscustomobject]@{ found = $false })
    }
    else {
        Write-BridgeResult ([pscustomobject]@{
            found = $true
            port = $bridge.port
            health = $bridge.health
        })
    }
    exit 0
}

if ($Action -eq 'start') {
    $bridge = Get-EasyEdaBridge
    if ($null -ne $bridge) {
        Write-BridgeResult ([pscustomobject]@{
            found = $true
            started = $false
            port = $bridge.port
            health = $bridge.health
        })
        exit 0
    }

    if (-not (Test-Path -LiteralPath $serverPath -PathType Leaf)) {
        throw "Official easyeda-api bridge server not found: $serverPath"
    }

    $nodePath = (Get-Command node -ErrorAction Stop).Source
    $runtimeDir = Join-Path ([System.IO.Path]::GetTempPath()) 'codex-jlc-eda-design'
    New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $stdoutPath = Join-Path $runtimeDir "bridge-$stamp.out.log"
    $stderrPath = Join-Path $runtimeDir "bridge-$stamp.err.log"

    $startArgs = @{
        FilePath = $nodePath
        ArgumentList = @($serverPath)
        WorkingDirectory = $easyEdaSkillRoot
        WindowStyle = 'Hidden'
        RedirectStandardOutput = $stdoutPath
        RedirectStandardError = $stderrPath
        PassThru = $true
    }
    $process = Start-Process @startArgs

    $deadline = (Get-Date).AddSeconds($WaitSeconds)
    do {
        Start-Sleep -Milliseconds 250
        $bridge = Get-EasyEdaBridge
        if ($null -ne $bridge) {
            Write-BridgeResult ([pscustomobject]@{
                found = $true
                started = $true
                processId = $process.Id
                port = $bridge.port
                health = $bridge.health
                stdoutLog = $stdoutPath
                stderrLog = $stderrPath
            })
            exit 0
        }
    } while ((Get-Date) -lt $deadline -and -not $process.HasExited)

    if ($process.HasExited) {
        throw "Bridge process exited with code $($process.ExitCode). See $stderrPath"
    }
    throw "Bridge did not become healthy within $WaitSeconds seconds. See $stderrPath"
}

$bridge = Get-EasyEdaBridge
if ($null -eq $bridge) {
    Write-BridgeResult ([pscustomobject]@{ found = $false; stopped = $false })
    exit 0
}

$listener = Get-NetTCPConnection -State Listen -LocalAddress '127.0.0.1' -LocalPort $bridge.port -ErrorAction SilentlyContinue | Select-Object -First 1
if ($null -eq $listener) {
    throw "Bridge responded on port $($bridge.port), but no loopback listener could be verified. Refusing to stop a process."
}

$ownerId = $listener.OwningProcess
$processInfo = Get-CimInstance Win32_Process -Filter "ProcessId = $ownerId"
if ($null -eq $processInfo -or $processInfo.Name -notmatch '^node(\.exe)?$' -or $processInfo.CommandLine -notmatch 'bridge-server\.mjs') {
    throw "Process $ownerId is not a verified EasyEDA bridge process. Refusing to stop it."
}

Stop-Process -Id $ownerId
Write-BridgeResult ([pscustomobject]@{
    found = $true
    stopped = $true
    processId = $ownerId
    port = $bridge.port
})
