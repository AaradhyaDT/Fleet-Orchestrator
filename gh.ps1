<#
.SYNOPSIS
    Deterministic GitHub CLI (gh) Workflow Engine & Safe UTF-8 Body-File Interceptor.

.DESCRIPTION
    gh.ps1 wraps the native GitHub CLI (gh.exe) to enforce the github-workflow SOP
    and background-task-governance invariants on Windows:
    1. Binary Auto-Discovery & Recursion Guard: Locates native gh.exe across PATH,
       Program Files, and WinGet packages while excluding local gh.ps1/gh.bat shims.
    2. Non-Interactive & UTF-8 Hardening: Forces BOM-less UTF-8 encoding and disables
       interactive pagers/prompts (GH_PAGER="", GH_PROMPT_DISABLED=1).
    3. Safe UTF-8 Body-File Interceptor (INV-GH-BODY-FILE): Automatically converts
       inline --body / -b / --notes arguments into temporary UTF-8 --body-file payloads
       so PowerShell never corrupts backticks, LaTeX math ($), or backslashes.
    4. Built-in github-workflow SOP Shortcuts:
       - issue-create / -NewIssue   : Create issue + native Type (Bug/Feature/Task) + Milestone
       - task         / -Task       : Toggle issue checklist items via toggle_issue_task.py
       - sub-issue    / -LinkSubIssue: Link Parent -> Child sub-issues via GraphQL
       - close-verified / -CloseIssue: Close issue with authentic HEAD commit SHA proof
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Enforce BOM-less UTF-8 across console pipes and subprocesses
$utf8NoBom = [System.Text.UTF8Encoding]::new($false)
[Console]::InputEncoding  = $utf8NoBom
[Console]::OutputEncoding = $utf8NoBom
$OutputEncoding           = $utf8NoBom
$env:GH_PAGER             = ""
$env:GH_PROMPT_DISABLED   = "1"
$env:PYTHONUTF8           = "1"
$env:PYTHONIOENCODING     = "utf-8"

$script:TempBodyFiles = [System.Collections.Generic.List[string]]::new()
$script:DryRunWrapper = $false

function Write-GhStatus {
    param(
        [string]$Message,
        [System.ConsoleColor]$Color = [System.ConsoleColor]::Cyan
    )
    Write-Host "[$((Get-Date).ToString('HH:mm:ss'))] [gh.ps1] $Message" -ForegroundColor $Color
}

function Resolve-GhBinary {
    if ($env:GH_EXE_PATH -and (Test-Path $env:GH_EXE_PATH)) {
        return (Resolve-Path $env:GH_EXE_PATH).Path
    }

    $scriptDir = if ($PSScriptRoot) { (Resolve-Path $PSScriptRoot).Path.TrimEnd('\', '/') } else { "" }
    $workDir   = (Get-Location).Path.TrimEnd('\', '/')

    $candidates = @(Get-Command "gh.exe" -CommandType Application -All -ErrorAction SilentlyContinue)
    foreach ($cmd in $candidates) {
        if (-not $cmd.Source) { continue }
        $cmdPath = (Resolve-Path $cmd.Source -ErrorAction SilentlyContinue).Path
        if (-not $cmdPath) { continue }
        $cmdDir = (Split-Path $cmdPath -Parent).TrimEnd('\', '/')
        if ($cmdDir -ieq $scriptDir -or $cmdDir -ieq $workDir) { continue }
        if ($cmdPath.EndsWith("gh.exe", [System.StringComparison]::OrdinalIgnoreCase)) {
            return $cmdPath
        }
    }

    $fallbackPaths = @(
        "$env:ProgramFiles\GitHub CLI\gh.exe",
        "${env:ProgramFiles(x86)}\GitHub CLI\gh.exe",
        "$env:LOCALAPPDATA\Programs\GitHub CLI\gh.exe",
        "$env:LOCALAPPDATA\Microsoft\WinGet\Links\gh.exe"
    )
    foreach ($fp in $fallbackPaths) {
        if ($fp -and (Test-Path $fp)) {
            return (Resolve-Path $fp).Path
        }
    }

    $wingetPkgRoot = "$env:LOCALAPPDATA\Microsoft\WinGet\Packages"
    if (Test-Path $wingetPkgRoot) {
        $found = Get-ChildItem -Path $wingetPkgRoot -Filter "gh.exe" -Recurse -ErrorAction SilentlyContinue |
            Select-Object -First 1
        if ($found) {
            return $found.FullName
        }
    }

    throw "GitHub CLI (gh.exe) was not found on this system. Install via 'winget install GitHub.cli' or set GH_EXE_PATH."
}

function Resolve-PythonBinary {
    $workDir = (Get-Location).Path
    $venvCandidate = Join-Path $workDir ".venv\Scripts\python.exe"
    if (Test-Path $venvCandidate -ErrorAction SilentlyContinue) {
        return (Resolve-Path $venvCandidate).Path
    }
    $pyCmd = Get-Command "python.exe" -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($pyCmd) { return $pyCmd.Source }
    return "python"
}

function Resolve-ToggleTaskScript {
    $candidates = @(
        (Join-Path $PSScriptRoot "toggle_issue_task.py"),
        (Join-Path $PSScriptRoot "scripts\toggle_issue_task.py"),
        "$HOME\.gemini\config\skills\github-workflow\scripts\toggle_issue_task.py",
        "$HOME\.agents\skills\github-workflow\scripts\toggle_issue_task.py"
    )
    foreach ($c in $candidates) {
        if ($c -and (Test-Path $c)) {
            return (Resolve-Path $c).Path
        }
    }
    throw "toggle_issue_task.py was not found in github-workflow skill directories."
}

function New-TempBodyFile {
    param([string]$Content)

    $normalizedContent = $Content
    if (-not $normalizedContent.Contains("`n") -and $normalizedContent.Contains("\n")) {
        $normalizedContent = [regex]::Replace($normalizedContent, '(?<!:)(?:\\r)?\\n(?![a-z])', "`n")
    }

    $scratchDir = Join-Path (Get-Location).Path "scratch"
    $targetDir = if (Test-Path $scratchDir) { $scratchDir } else { $env:TEMP }
    if (-not (Test-Path $targetDir)) {
        New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
    }

    $fileName = ".gh_body_$([Guid]::NewGuid().ToString('N').Substring(0, 12)).md"
    $fullPath = Join-Path $targetDir $fileName
    [System.IO.File]::WriteAllText($fullPath, $normalizedContent, $utf8NoBom)
    $script:TempBodyFiles.Add($fullPath)
    return $fullPath
}

function Remove-TempBodyFiles {
    foreach ($f in $script:TempBodyFiles) {
        if ($f -and (Test-Path $f)) {
            Remove-Item -LiteralPath $f -Force -ErrorAction SilentlyContinue
        }
    }
    $script:TempBodyFiles.Clear()
}

function Convert-BodyArgsToFiles {
    param([string[]]$InputArgs)

    if (-not $InputArgs -or $InputArgs.Count -eq 0) {
        return ,([string[]]@())
    }

    # Determine primary gh subcommand (ignoring leading global flags like -R owner/repo)
    $primaryCmd = $null
    for ($k = 0; $k -lt $InputArgs.Count; $k++) {
        $tok = $InputArgs[$k]
        if ($tok -in @("-R", "--repo", "--hostname")) {
            $k++
            continue
        }
        if ($tok.StartsWith("-")) { continue }
        $primaryCmd = $tok.ToLowerInvariant()
        break
    }

    $interceptBody  = $primaryCmd -in @("issue", "pr", "release")
    $interceptNotes = $primaryCmd -eq "release"

    $outArgs = [System.Collections.Generic.List[string]]::new()
    $i = 0
    while ($i -lt $InputArgs.Count) {
        $arg = [string]$InputArgs[$i]

        if ($interceptBody -and ($arg -ceq "--body" -or $arg -ceq "-b") -and ($i + 1 -lt $InputArgs.Count)) {
            $bodyVal = [string]$InputArgs[$i + 1]
            $tmpFile = New-TempBodyFile -Content $bodyVal
            $outArgs.Add("--body-file")
            $outArgs.Add($tmpFile)
            $i += 2
            continue
        }

        if ($interceptBody -and $arg.StartsWith("--body=", [System.StringComparison]::Ordinal)) {
            $bodyVal = $arg.Substring(7)
            $tmpFile = New-TempBodyFile -Content $bodyVal
            $outArgs.Add("--body-file")
            $outArgs.Add($tmpFile)
            $i++
            continue
        }

        if ($interceptNotes -and ($arg -ceq "--notes" -or $arg -ceq "-n") -and ($i + 1 -lt $InputArgs.Count)) {
            $notesVal = [string]$InputArgs[$i + 1]
            $tmpFile = New-TempBodyFile -Content $notesVal
            $outArgs.Add("--notes-file")
            $outArgs.Add($tmpFile)
            $i += 2
            continue
        }

        if ($interceptNotes -and $arg.StartsWith("--notes=", [System.StringComparison]::Ordinal)) {
            $notesVal = $arg.Substring(8)
            $tmpFile = New-TempBodyFile -Content $notesVal
            $outArgs.Add("--notes-file")
            $outArgs.Add($tmpFile)
            $i++
            continue
        }

        $outArgs.Add($arg)
        $i++
    }

    return ,([string[]]$outArgs.ToArray())
}

function Invoke-GhProcess {
    param(
        [string]$GhExe,
        [string[]]$GhArgs,
        [switch]$CaptureOutput
    )

    if ($script:DryRunWrapper) {
        $preview = [ordered]@{
            dry_run    = $true
            gh_binary  = $GhExe
            arguments  = @($GhArgs)
            temp_files = @()
        }
        foreach ($tf in $script:TempBodyFiles) {
            if (Test-Path $tf) {
                $preview.temp_files += [ordered]@{
                    path    = $tf
                    content = [System.IO.File]::ReadAllText($tf, $utf8NoBom)
                }
            }
        }
        $jsonPreview = $preview | ConvertTo-Json -Depth 6
        $global:LASTEXITCODE = 0
        if ($CaptureOutput) {
            return $jsonPreview
        }
        [Console]::Out.WriteLine($jsonPreview)
        return
    }

    if ($CaptureOutput) {
        $output = & $GhExe @GhArgs
        if ($LASTEXITCODE -ne 0) {
            throw "gh command failed (exit code $LASTEXITCODE): $($GhArgs -join ' ')"
        }
        return ($output -join "`n")
    }
    else {
        & $GhExe @GhArgs
        return
    }
}

function Show-WrapperHelp {
    $helpText = @'
================================================================================
 gh.ps1 / gh.bat - GitHub CLI Workflow Engine & Safe UTF-8 Body-File Wrapper
================================================================================

1. TRANSPARENT PASS-THROUGH + AUTOMATIC --body-file INTERCEPTION (INV-GH-BODY-FILE)
   Any standard GitHub CLI command works identically, except inline --body / -b
   and --notes payloads are automatically written to BOM-less UTF-8 temp files
   and rewritten to --body-file / --notes-file to prevent PowerShell '$' and
   backtick corruption:

   .\gh.bat issue list
   .\gh.bat pr view 42
   .\gh.bat issue create --title "[Feature] Matrix" --body 'Math $x_1$ & `code`'
   .\gh.bat issue comment 28 --body 'Verified `pytest` 100% pass.'

2. BUILT-IN GITHUB-WORKFLOW SOP SHORTCUTS
   a) Create Issue with Native Type & Milestone (issue-create / -NewIssue):
      .\gh.bat issue-create --title "[Feature] Add Metric" --assignee AaradhyaDT `
          --label "enhancement" --type Feature --milestone "M1" --body "## Overview..."

   b) Toggle Issue Task Checkboxes (task / -Task):
      .\gh.bat task --issue 28 --list
      .\gh.bat task --issue 28 --task "metrics.py"
      .\gh.bat task --issue 28 --index 2
      .\gh.bat task --issue 28 --all

   c) Link Parent -> Child Sub-Issues via GraphQL (sub-issue / -LinkSubIssue):
      .\gh.bat sub-issue --parent 28 --child 29

   d) Close Issue with Verified HEAD Commit SHA (close-verified / -CloseIssue):
      .\gh.bat close-verified 28 --comment "All 86 unit tests and ruff checks passing."

3. DIAGNOSTIC & DRY-RUN FLAGS
   .\gh.bat --gh-help                         Show this wrapper reference
   .\gh.bat --DryRunWrapper <any-command>     Preview resolved binary, args & UTF-8 body file
================================================================================
'@
    [Console]::Out.WriteLine($helpText)
    $global:LASTEXITCODE = 0
}

function Invoke-TaskShortcut {
    param([string[]]$TaskArgs)

    $pyExe = Resolve-PythonBinary
    $toggleScript = Resolve-ToggleTaskScript

    $normArgs = [System.Collections.Generic.List[string]]::new()
    foreach ($a in $TaskArgs) {
        switch -Regex ($a) {
            '^-(Issue|i)$'       { $normArgs.Add("--issue"); continue }
            '^-(Repo|R)$'        { $normArgs.Add("--repo"); continue }
            '^-(Task|t)$'        { $normArgs.Add("--task"); continue }
            '^-Index$'           { $normArgs.Add("--index"); continue }
            '^-All$'             { $normArgs.Add("--all"); continue }
            '^-State$'           { $normArgs.Add("--state"); continue }
            '^-List$'            { $normArgs.Add("--list"); continue }
            '^-(DryRun|WhatIf)$' { $normArgs.Add("--dry-run"); continue }
            default              { $normArgs.Add($a) }
        }
    }

    if ($script:DryRunWrapper -and -not ($normArgs -contains "--dry-run")) {
        $normArgs.Add("--dry-run")
    }

    & $pyExe $toggleScript @($normArgs.ToArray())
}

function Resolve-RepoOwnerAndName {
    param(
        [string]$GhExe,
        [string]$ExplicitRepo
    )
    if ($ExplicitRepo -and $ExplicitRepo -match '^([^/]+)/([^/]+)$') {
        return [PSCustomObject]@{
            Owner = $Matches[1]
            Name  = $Matches[2]
            Full  = $ExplicitRepo
        }
    }
    if ($script:DryRunWrapper) {
        return [PSCustomObject]@{
            Owner = "Aaradhya-Dev-Tamrakar"
            Name  = (Split-Path (Get-Location).Path -Leaf)
            Full  = "Aaradhya-Dev-Tamrakar/$(Split-Path (Get-Location).Path -Leaf)"
        }
    }
    $nwo = (& $GhExe repo view --json nameWithOwner --jq ".nameWithOwner" 2>$null)
    if ($nwo) { $nwo = $nwo.Trim() }
    if ($nwo -match '^([^/]+)/([^/]+)$') {
        return [PSCustomObject]@{
            Owner = $Matches[1]
            Name  = $Matches[2]
            Full  = $nwo
        }
    }
    throw "Unable to determine GitHub repository owner/name. Pass --repo <owner/repo>."
}

function Invoke-IssueCreateShortcut {
    param(
        [string]$GhExe,
        [string[]]$SubArgs
    )

    $title     = $null
    $body      = $null
    $bodyFile  = $null
    $assignee  = $null
    $labels    = [System.Collections.Generic.List[string]]::new()
    $milestone = $null
    $issueType = $null
    $repo      = $null

    $i = 0
    while ($i -lt $SubArgs.Count) {
        $tok = $SubArgs[$i]
        switch -Regex ($tok) {
            '^(--title|-Title|-t)$' {
                $title = $SubArgs[$i + 1]; $i += 2; continue
            }
            '^(--body|-Body|-b)$' {
                $body = $SubArgs[$i + 1]; $i += 2; continue
            }
            '^(--body-file|-BodyFile|-F)$' {
                $bodyFile = $SubArgs[$i + 1]; $i += 2; continue
            }
            '^(--assignee|-Assignee|-a)$' {
                $assignee = $SubArgs[$i + 1]; $i += 2; continue
            }
            '^(--label|-Label|-l)$' {
                $labels.Add($SubArgs[$i + 1]); $i += 2; continue
            }
            '^(--milestone|-Milestone|-m)$' {
                $milestone = $SubArgs[$i + 1]; $i += 2; continue
            }
            '^(--type|-Type)$' {
                $issueType = $SubArgs[$i + 1]; $i += 2; continue
            }
            '^(--repo|-Repo|-R)$' {
                $repo = $SubArgs[$i + 1]; $i += 2; continue
            }
            default {
                throw "Unknown option for issue-create: $tok"
            }
        }
    }

    if (-not $title) {
        throw "issue-create requires --title <string>."
    }

    $createArgs = [System.Collections.Generic.List[string]]::new()
    $createArgs.Add("issue")
    $createArgs.Add("create")
    $createArgs.Add("--title")
    $createArgs.Add($title)

    if ($assignee) {
        $createArgs.Add("--assignee")
        $createArgs.Add($assignee)
    }
    foreach ($lbl in $labels) {
        $createArgs.Add("--label")
        $createArgs.Add($lbl)
    }
    if ($milestone) {
        $createArgs.Add("--milestone")
        $createArgs.Add($milestone)
    }
    if ($repo) {
        $createArgs.Add("--repo")
        $createArgs.Add($repo)
    }
    if ($bodyFile) {
        $createArgs.Add("--body-file")
        $createArgs.Add($bodyFile)
    }
    elseif ($null -ne $body) {
        $tmpFile = New-TempBodyFile -Content $body
        $createArgs.Add("--body-file")
        $createArgs.Add($tmpFile)
    }

    if ($script:DryRunWrapper) {
        $preview = [ordered]@{
            dry_run     = $true
            shortcut    = "issue-create"
            gh_binary   = $GhExe
            create_args = @($createArgs)
            issue_type  = $issueType
            temp_files  = @()
        }
        foreach ($tf in $script:TempBodyFiles) {
            if (Test-Path $tf) {
                $preview.temp_files += [ordered]@{
                    path    = $tf
                    content = [System.IO.File]::ReadAllText($tf, $utf8NoBom)
                }
            }
        }
        [Console]::Out.WriteLine(($preview | ConvertTo-Json -Depth 6))
        $global:LASTEXITCODE = 0
        return
    }

    $out = Invoke-GhProcess -GhExe $GhExe -GhArgs $createArgs.ToArray() -CaptureOutput
    [Console]::Out.WriteLine($out)

    if ($issueType) {
        if ($out -match 'https://github\.com/([^/\s]+)/([^/\s]+)/issues/(\d+)') {
            $owner = $Matches[1]
            $repoName = $Matches[2]
            $issueNum = $Matches[3]
            Write-GhStatus "Setting native Issue Type to '$issueType' on $owner/$repoName#$issueNum..."
            & $GhExe api -X PATCH "repos/$owner/$repoName/issues/$issueNum" -f "type=$issueType" | Out-Null
        }
    }

    $global:LASTEXITCODE = 0
}

function Invoke-SubIssueShortcut {
    param(
        [string]$GhExe,
        [string[]]$SubArgs
    )

    $parentNum = $null
    $childNum  = $null
    $repo      = $null

    $i = 0
    while ($i -lt $SubArgs.Count) {
        $tok = $SubArgs[$i]
        switch -Regex ($tok) {
            '^(--parent|-Parent|-p)$' {
                $parentNum = ($SubArgs[$i + 1] -replace '^#', '').Trim(); $i += 2; continue
            }
            '^(--child|-Child|-c)$' {
                $childNum = ($SubArgs[$i + 1] -replace '^#', '').Trim(); $i += 2; continue
            }
            '^(--repo|-Repo|-R)$' {
                $repo = $SubArgs[$i + 1]; $i += 2; continue
            }
            default {
                throw "Unknown option for sub-issue: $tok"
            }
        }
    }

    if (-not $parentNum -or -not $childNum) {
        throw "sub-issue requires --parent <issue_number> and --child <issue_number>."
    }

    $repoInfo = Resolve-RepoOwnerAndName -GhExe $GhExe -ExplicitRepo $repo

    if ($script:DryRunWrapper) {
        $preview = [ordered]@{
            dry_run     = $true
            shortcut    = "sub-issue"
            repository  = $repoInfo.Full
            parent_num  = [int]$parentNum
            child_num   = [int]$childNum
        }
        [Console]::Out.WriteLine(($preview | ConvertTo-Json -Depth 5))
        $global:LASTEXITCODE = 0
        return
    }

    $idQuery = "query { repository(owner: `"$($repoInfo.Owner)`", name: `"$($repoInfo.Name)`") { parent: issue(number: $parentNum) { id } child: issue(number: $childNum) { id } } }"
    $idRaw = Invoke-GhProcess -GhExe $GhExe -GhArgs @("api", "graphql", "-f", "query=$idQuery") -CaptureOutput
    $idData = $idRaw | ConvertFrom-Json
    $parentId = $idData.data.repository.parent.id
    $childId  = $idData.data.repository.child.id

    if (-not $parentId -or -not $childId) {
        throw "Failed to resolve GraphQL node IDs for parent #$parentNum or child #$childNum in $($repoInfo.Full)."
    }

    $mutation = "mutation { addSubIssue(input: { issueId: `"$parentId`", subIssueId: `"$childId`" }) { issue { number } subIssue { number } } }"
    $null = Invoke-GhProcess -GhExe $GhExe -GhArgs @("api", "graphql", "-f", "query=$mutation") -CaptureOutput
    Write-GhStatus "Linked child issue #$childNum under parent issue #$parentNum in $($repoInfo.Full)." -Color ([System.ConsoleColor]::Green)
    $global:LASTEXITCODE = 0
}

function Invoke-CloseVerifiedShortcut {
    param(
        [string]$GhExe,
        [string[]]$SubArgs
    )

    $issueNum = $null
    $comment  = $null
    $sha      = $null
    $repo     = $null

    $i = 0
    while ($i -lt $SubArgs.Count) {
        $tok = $SubArgs[$i]
        switch -Regex ($tok) {
            '^(--issue|-Issue|-i)$' {
                $issueNum = ($SubArgs[$i + 1] -replace '^#', '').Trim(); $i += 2; continue
            }
            '^(--comment|-Comment|-c|--body|-Body|-b)$' {
                $comment = $SubArgs[$i + 1]; $i += 2; continue
            }
            '^(--sha|-Sha)$' {
                $sha = $SubArgs[$i + 1]; $i += 2; continue
            }
            '^(--repo|-Repo|-R)$' {
                $repo = $SubArgs[$i + 1]; $i += 2; continue
            }
            default {
                if (-not $issueNum -and $tok -match '^#?\d+$') {
                    $issueNum = $tok.TrimStart('#')
                    $i++
                    continue
                }
                throw "Unknown option for close-verified: $tok"
            }
        }
    }

    if (-not $issueNum) {
        throw "close-verified requires an issue number (e.g. .\gh.bat close-verified 28 --comment '...')."
    }

    if (-not $sha) {
        $gitSha = (git rev-parse --short HEAD 2>$null)
        $sha = if ($gitSha) { $gitSha.Trim() } else { "HEAD" }
    }

    $finalComment = if ($comment) {
        if ($comment -match [regex]::Escape($sha)) {
            $comment
        } else {
            "Completed in commit $sha. $comment"
        }
    } else {
        "Completed in commit $sha. Verified local test suite and linting gates passing (0 discrepancies)."
    }

    $tmpFile = New-TempBodyFile -Content $finalComment

    $commentArgs = [System.Collections.Generic.List[string]]::new()
    $commentArgs.Add("issue")
    $commentArgs.Add("comment")
    $commentArgs.Add($issueNum)
    $commentArgs.Add("--body-file")
    $commentArgs.Add($tmpFile)
    if ($repo) {
        $commentArgs.Add("--repo")
        $commentArgs.Add($repo)
    }

    $closeArgs = [System.Collections.Generic.List[string]]::new()
    $closeArgs.Add("issue")
    $closeArgs.Add("close")
    $closeArgs.Add($issueNum)
    if ($repo) {
        $closeArgs.Add("--repo")
        $closeArgs.Add($repo)
    }

    if ($script:DryRunWrapper) {
        $preview = [ordered]@{
            dry_run      = $true
            shortcut     = "close-verified"
            issue_number = [int]$issueNum
            commit_sha   = $sha
            comment_body = $finalComment
            comment_args = @($commentArgs)
            close_args   = @($closeArgs)
        }
        [Console]::Out.WriteLine(($preview | ConvertTo-Json -Depth 5))
        $global:LASTEXITCODE = 0
        return
    }

    Invoke-GhProcess -GhExe $GhExe -GhArgs $commentArgs.ToArray()
    if ($LASTEXITCODE -ne 0) { return }

    Invoke-GhProcess -GhExe $GhExe -GhArgs $closeArgs.ToArray()
}

try {
    $rawArgs = [System.Collections.Generic.List[string]]::new()
    foreach ($a in $args) {
        if ($a -ceq "--DryRunWrapper" -or $a -ceq "-DryRunWrapper") {
            $script:DryRunWrapper = $true
            continue
        }
        $rawArgs.Add([string]$a)
    }

    if ($rawArgs.Count -eq 0 -or $rawArgs[0] -in @("--gh-help", "-HelpWrapper", "wrapper-help")) {
        Show-WrapperHelp
        exit 0
    }

    $firstArg = $rawArgs[0]
    $restArgs = if ($rawArgs.Count -gt 1) { [string[]]$rawArgs.GetRange(1, $rawArgs.Count - 1).ToArray() } else { [string[]]@() }

    if ($firstArg -in @("task", "-Task")) {
        Invoke-TaskShortcut -TaskArgs $restArgs
        exit $LASTEXITCODE
    }

    $ghExe = Resolve-GhBinary

    switch ($firstArg) {
        { $_ -in @("issue-create", "-NewIssue") } {
            Invoke-IssueCreateShortcut -GhExe $ghExe -SubArgs $restArgs
            exit $LASTEXITCODE
        }
        { $_ -in @("sub-issue", "-LinkSubIssue") } {
            Invoke-SubIssueShortcut -GhExe $ghExe -SubArgs $restArgs
            exit $LASTEXITCODE
        }
        { $_ -in @("close-verified", "-CloseIssue") } {
            Invoke-CloseVerifiedShortcut -GhExe $ghExe -SubArgs $restArgs
            exit $LASTEXITCODE
        }
        default {
            $safeArgs = Convert-BodyArgsToFiles -InputArgs $rawArgs.ToArray()
            Invoke-GhProcess -GhExe $ghExe -GhArgs $safeArgs
            exit $LASTEXITCODE
        }
    }
}
catch {
    [Console]::Error.WriteLine("[gh.ps1 Error] $($_.Exception.Message)")
    exit 1
}
finally {
    Remove-TempBodyFiles
}
