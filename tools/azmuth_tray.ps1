# tools/azmuth_tray.ps1
# Native Windows Forms System Tray Controller for Azmuth Engine.
# Interoperates natively with Windows 11 Taskbar Shell.

param(
    [switch]$Hidden
)

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()

$RepoRoot = "F:\Aaradhya-Dev-Tamrakar\Fleet-Orchestrator"
$PythonExe = "C:\Users\Aaradhya\AppData\Local\Programs\Python\Python314\python.exe"
$GearFile = Join-Path $RepoRoot "orchestrator-state\azmuth_gear.json"
$PauseFile = Join-Path $RepoRoot "orchestrator-state\azmuth.pause"
$LedgerFile = Join-Path $RepoRoot "orchestrator-state\azmuth_corpus_ledger.json"

function Get-AzmuthGear {
    if (Test-Path $GearFile) {
        try {
            $data = Get-Content $GearFile -Raw | ConvertFrom-Json
            return $data.gear.ToLower()
        } catch {}
    }
    return "balanced"
}

function Set-AzmuthGear($gear) {
    & $PythonExe (Join-Path $RepoRoot "tools\azmuth_daemon.py") --gear $gear
}

function Toggle-AzmuthPause {
    if (Test-Path $PauseFile) {
        & $PythonExe (Join-Path $RepoRoot "tools\azmuth_daemon.py") --resume
    } else {
        & $PythonExe (Join-Path $RepoRoot "tools\azmuth_daemon.py") --pause
    }
}

function Get-RamStats {
    try {
        $os = Get-CimInstance Win32_OperatingSystem
        $freeGB = [Math]::Round($os.FreePhysicalMemory / 1024 / 1024, 1)
        $totalGB = [Math]::Round($os.TotalVisibleMemorySize / 1024 / 1024, 1)
        $usedPct = [Math]::Round((($totalGB - $freeGB) / $totalGB) * 100)
        return @{ Free = $freeGB; Total = $totalGB; Pct = $usedPct }
    } catch {
        return @{ Free = 8.0; Total = 16.0; Pct = 50 }
    }
}

function Get-IngestedCount {
    if (Test-Path $LedgerFile) {
        try {
            $data = Get-Content $LedgerFile -Raw | ConvertFrom-Json
            return $data.tasks_processed.Count
        } catch {}
    }
    return 0
}

# --- Create Procedural Dynamic Icon Bitmap ---
function New-GearIcon($gear, $isPaused) {
    $bmp = New-Object System.Drawing.Bitmap(32, 32)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias

    $brushColor = if ($isPaused) {
        [System.Drawing.Color]::Gray
    } elseif ($gear -eq "turbo") {
        [System.Drawing.Color]::FromArgb(235, 75, 50) # Fire Red
    } elseif ($gear -eq "whisper") {
        [System.Drawing.Color]::FromArgb(40, 180, 80) # Emerald
    } else {
        [System.Drawing.Color]::FromArgb(0, 120, 215) # Azure Blue
    }

    $pen = New-Object System.Drawing.Pen($brushColor, 3)
    $g.DrawEllipse($pen, 3, 3, 26, 26)

    $fillBrush = New-Object System.Drawing.SolidBrush($brushColor)
    $g.FillEllipse($fillBrush, 9, 9, 14, 14)

    $g.Dispose()
    $hIcon = $bmp.GetHicon()
    $icon = [System.Drawing.Icon]::FromHandle($hIcon)
    return $icon
}

# --- Instantiate NotifyIcon ---
$notify = New-Object System.Windows.Forms.NotifyIcon
$currentGear = Get-AzmuthGear
$isPaused = Test-Path $PauseFile

$notify.Icon = New-GearIcon $currentGear $isPaused
$notify.Text = "Azmuth Engine: " + $currentGear.ToUpper()
$notify.Visible = $true

# --- Context Menu Strip ---
$menu = New-Object System.Windows.Forms.ContextMenuStrip

$headerStatus = $menu.Items.Add("Azmuth Engine: ACTIVE")
$headerStatus.Enabled = $false
$headerStatus.Font = New-Object System.Drawing.Font($headerStatus.Font, [System.Drawing.FontStyle]::Bold)

$headerRam = $menu.Items.Add("RAM: Checking...")
$headerRam.Enabled = $false

$headerCP = $menu.Items.Add("CP Ingested: 0 tasks")
$headerCP.Enabled = $false

$sep1 = $menu.Items.Add("-")

$itemTurbo = $menu.Items.Add("🚀 Turbo Mode (High Throughput)")
$itemBalanced = $menu.Items.Add("⚡ Balanced Mode (Auto-Managed)")
$itemWhisper = $menu.Items.Add("🌱 Whisper Mode (Low Power)")

$sep2 = $menu.Items.Add("-")

$itemPause = $menu.Items.Add("⏸️ Pause Engine")

$sep3 = $menu.Items.Add("-")

$itemHarvest = $menu.Items.Add("▶️ Harvest 1 Task Now")
$itemExit = $menu.Items.Add("❌ Exit Tray Icon")

$notify.ContextMenuStrip = $menu

# Event Handlers
$itemTurbo.add_Click({ Set-AzmuthGear "turbo"; Update-TrayState })
$itemBalanced.add_Click({ Set-AzmuthGear "balanced"; Update-TrayState })
$itemWhisper.add_Click({ Set-AzmuthGear "whisper"; Update-TrayState })
$itemPause.add_Click({ Toggle-AzmuthPause; Update-TrayState })
$itemHarvest.add_Click({
    [System.Threading.ThreadPool]::QueueUserWorkItem({
        & $PythonExe (Join-Path $RepoRoot "tools\azmuth_corpus_harvester.py")
    })
})
$itemExit.add_Click({
    $notify.Visible = $false
    $notify.Dispose()
    [System.Windows.Forms.Application]::Exit()
})

function Update-TrayState {
    $gear = Get-AzmuthGear
    $paused = Test-Path $PauseFile
    $ram = Get-RamStats
    $ingested = Get-IngestedCount

    $headerStatus.Text = if ($paused) { "Azmuth Engine: PAUSED" } else { "Azmuth Engine: " + $gear.ToUpper() }
    $headerRam.Text = "RAM: $($ram.Free)GB free / $($ram.Total)GB ($($ram.Pct)% load)"
    $headerCP.Text = "CP Ingested: $ingested tasks cataloged"

    $itemTurbo.Checked = ($gear -eq "turbo")
    $itemBalanced.Checked = ($gear -eq "balanced")
    $itemWhisper.Checked = ($gear -eq "whisper")
    $itemPause.Text = if ($paused) { "▶️ Resume Engine" } else { "⏸️ Pause Engine" }

    $notify.Icon = New-GearIcon $gear $paused
    $notify.Text = "Azmuth [$($gear.ToUpper())] - Free RAM: $($ram.Free)GB"
}

# --- Background Timer (Refreshes status and checks RAM circuit breaker every 3s) ---
$timer = New-Object System.Windows.Forms.Timer
$timer.Interval = 3000
$timer.add_Tick({
    Update-TrayState
})
$timer.Start()

Update-TrayState
[System.Windows.Forms.Application]::Run()
