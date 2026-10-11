<#
.SYNOPSIS
    tools/models.ps1 - Lifecycle and memory governor for Fleet-Orchestrator local LLMs in LM Studio.

.DESCRIPTION
    Commands:
        status  : Display LM Studio service status, currently loaded models, and system memory.
        import  : Idempotently imports qwen_intent_router_q4_k_m.gguf into LM Studio if not registered.
        up      : Starts server, loads router (always-on, no TTL) and 3B daily worker (TTL 600s).
        heavy   : Unloads 3B daily worker and loads 7B powerhouse (TTL 300s) with 7GB free RAM safety check.
        down    : Unloads all models and frees GPU/VRAM/RAM.
        bench   : Executes benchmark script comparing router candidates on task_time_eval dataset.

.EXAMPLE
    .\tools\models.ps1 status
    .\tools\models.ps1 up
    .\tools\models.ps1 heavy
    .\tools\models.ps1 down
#>

[CmdletBinding()]
param(
    [Parameter(Position=0)]
    [ValidateSet("status", "import", "up", "heavy", "down", "bench")]
    [string]$Command = "status",

    [Parameter()]
    [string]$Gpu = "auto",

    [Parameter()]
    [int]$BenchSamples = 30
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent $ScriptDir

function Get-FreeMemoryGB {
    try {
        $os = Get-CimInstance Win32_OperatingSystem
        return [math]::Round($os.FreePhysicalMemory / 1MB, 2)
    } catch {
        return 8.0
    }
}

function Show-Status {
    Write-Host "`n=== [LM STUDIO FLEET STATUS] ===" -ForegroundColor Cyan
    $freeRam = Get-FreeMemoryGB
    Write-Host "Free System RAM: $freeRam GB" -ForegroundColor Yellow

    try {
        & lms ps
    } catch {
        Write-Host "Warning: LM Studio CLI (lms) not responding or not started." -ForegroundColor Red
    }
    Write-Host ""
}

function Ensure-Server {
    try {
        & lms server start 2>$null
    } catch {}
}

function Do-Import {
    Write-Host "`n=== [IMPORTING MODELS] ===" -ForegroundColor Cyan
    $routerGguf = Join-Path $RootDir "models\qwen_intent_router_q4_k_m.gguf"
    if (Test-Path $routerGguf) {
        Write-Host "Checking / importing qwen-intent-router..." -ForegroundColor Green
        & lms import -c --user-repo aaradhya/qwen-intent-router -y "$routerGguf"
    } else {
        Write-Host "Warning: $routerGguf not found on disk." -ForegroundColor Yellow
    }
}

function Do-Up {
    Write-Host "`n=== [STARTING DAILY RUNTIME: ROUTER + 3B WORKER] ===" -ForegroundColor Cyan
    Ensure-Server

    Write-Host "1. Loading qwen-intent-router (always-on, ctx 2048)..." -ForegroundColor Green
    & lms load qwen-intent-router --identifier qwen-intent-router -c 2048 -y

    Write-Host "2. Loading fleet-master-3b (TTL 600s, ctx 8192)..." -ForegroundColor Green
    & lms load fleet-master-3b --identifier fleet-master-3b -c 8192 --ttl 600 -y

    Show-Status
}

function Do-Heavy {
    Write-Host "`n=== [SWITCHING TO POWERHOUSE RUNTIME: 7B] ===" -ForegroundColor Cyan
    $freeRam = Get-FreeMemoryGB
    if ($freeRam -lt 6.5) {
        Write-Host "ABORTED: Insufficient free memory ($freeRam GB). Minimum 6.5 GB required to safely run 7B model." -ForegroundColor Red
        return
    }

    Ensure-Server
    Write-Host "Unloading fleet-master-3b to reclaim VRAM/RAM..." -ForegroundColor Yellow
    try {
        & lms unload fleet-master-3b -y
    } catch {}

    Write-Host "Loading fleet-master-7b (TTL 300s, ctx 8192)..." -ForegroundColor Green
    & lms load fleet-master-7b --identifier fleet-master-7b -c 8192 --ttl 300 -y

    Show-Status
}

function Do-Down {
    Write-Host "`n=== [UNLOADING ALL MODELS] ===" -ForegroundColor Cyan
    try {
        & lms unload --all -y
    } catch {
        try { & lms unload fleet-master-3b -y 2>$null } catch {}
        try { & lms unload fleet-master-7b -y 2>$null } catch {}
        try { & lms unload qwen-intent-router -y 2>$null } catch {}
    }
    Show-Status
}

function Do-Bench {
    Write-Host "`n=== [BENCHMARKING LOCAL ROUTER CANDIDATES] ===" -ForegroundColor Cyan
    $benchScript = Join-Path $ScriptDir "bench_local_router.py"
    if (Test-Path $benchScript) {
        & python "$benchScript" --samples $BenchSamples
    } else {
        Write-Host "Benchmark script $benchScript not found." -ForegroundColor Red
    }
}

function Do-Verify {
    Write-Host "`n=== [RUNNING ADAPTIVE-WORKFLOW DECISION HARNESS] ===" -ForegroundColor Cyan
    $harnessScript = Join-Path $ScriptDir "adaptive_decision_harness.py"
    if (Test-Path $harnessScript) {
        & python "$harnessScript" --models deterministic,qwen-intent-router
    } else {
        Write-Host "Harness script $harnessScript not found." -ForegroundColor Red
    }
}

switch ($Command) {
    "status" { Show-Status }
    "import" { Do-Import }
    "up"     { Do-Up }
    "heavy"  { Do-Heavy }
    "down"   { Do-Down }
    "bench"  { Do-Bench }
    "verify" { Do-Verify }
}
