param(
    [Parameter(Mandatory = $true)]
    [string]$Project,

    [Parameter(Mandatory = $true)]
    [string]$Target,

    [string]$Uv4Path = (Join-Path $env:LOCALAPPDATA 'Keil_v5\UV4\UV4.exe'),

    [ValidateSet("rebuild", "build")]
    [string]$Mode = "rebuild",

    [string]$LogPath = "",

    [switch]$GitPull,
    [switch]$GitPush
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $Project)) {
    throw "Project not found: $Project"
}

if (-not (Test-Path $Uv4Path)) {
    throw "UV4.exe not found: $Uv4Path"
}

$projectDir = Split-Path -Parent $Project
if ([string]::IsNullOrWhiteSpace($LogPath)) {
    $LogPath = Join-Path $projectDir "build.log"
}

$modeArg = if ($Mode -eq "rebuild") { "-r" } else { "-b" }

$repoRoot = ""
try {
    $repoRoot = (git -C $projectDir rev-parse --show-toplevel).Trim()
} catch {
    $repoRoot = ""
}

if ($GitPull) {
    if ([string]::IsNullOrWhiteSpace($repoRoot)) {
        throw "Git pull requested, but repo root was not found from: $projectDir"
    }
    Write-Host "[git] pull --rebase in $repoRoot"
    git -C $repoRoot pull --rebase
}

if (Test-Path $LogPath) {
    Remove-Item $LogPath -Force
}

$args = @($modeArg, $Project, "-t", $Target, "-o", $LogPath)
Write-Host "[keil] $Uv4Path $($args -join ' ')"
$proc = Start-Process -FilePath $Uv4Path -ArgumentList $args -PassThru -Wait
Write-Host "[keil] exit code: $($proc.ExitCode)"

if (-not (Test-Path $LogPath)) {
    throw "Build log not generated: $LogPath"
}

Write-Host "[log] $LogPath"
$summary = Select-String -Path $LogPath -Pattern "Error\(s\)|Warning\(s\)|Target not created" | Select-Object -Last 1
$issues = Select-String -Path $LogPath -Pattern "error:|warning:|Error\(s\)|Warning\(s\)" | Select-Object -First 80

if ($issues) {
    Write-Host "[issues]"
    $issues | ForEach-Object { Write-Host $_.Line }
}

$buildOk = $false
if ($summary -and $summary.Line -match "0 Error\(s\)") {
    $buildOk = $true
}

if ($GitPush) {
    if (-not $buildOk) {
        throw "Git push requested, but build is not clean."
    }
    if ([string]::IsNullOrWhiteSpace($repoRoot)) {
        throw "Git push requested, but repo root was not found from: $projectDir"
    }
    Write-Host "[git] push in $repoRoot"
    git -C $repoRoot push
}

if ($buildOk) {
    Write-Host "[result] build clean"
    exit 0
}

Write-Host "[result] build has errors/warnings, check log"
exit 1
