param(
    [string[]]$TaskIds,
    [int]$StartIndex = 0,
    [int]$Count = 0,
    [switch]$SkipReset,
    [string]$RunTag = "",
    [string]$ConfigPath = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$PackageRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$RepoRoot = (Resolve-Path (Join-Path $PackageRoot "..")).Path
$ConfigPath = if ($ConfigPath) { $ConfigPath } else { Join-Path $PackageRoot "configs\system.dualmode_mode2.local.json" }
$Config = Get-Content -Raw $ConfigPath | ConvertFrom-Json
$PythonExe = if ($Config.runtime.python_executable) { $Config.runtime.python_executable } else { "python" }
$Stamp = Get-Date -Format "yyyyMMdd_HHmm"
$Tag = if ($RunTag) { $RunTag } else { $Stamp }
$TrainRunName = "${Tag}_dualmode_mode2_train"
$EvalRunName = "${Tag}_dualmode_mode2_eval"

function Invoke-NlrlCli {
    param([string[]]$CliArgs)
    Write-Host ("`n>> " + $PythonExe + " " + ($CliArgs -join " "))
    & $PythonExe @CliArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code $LASTEXITCODE"
    }
}

$CommonArgs = @("-m", "project_skills.nlrl_skills.cli", "--config", $ConfigPath)
$SelectionArgs = @("--start-index", "$StartIndex")
if ($TaskIds) {
    $SelectionArgs += "--task-ids"
    $SelectionArgs += $TaskIds
}
if ($Count -gt 0) {
    $SelectionArgs += @("--count", "$Count")
}

Set-Location $RepoRoot

$TrainArgs = $CommonArgs + @("train-tasks", "--run-name", $TrainRunName) + $SelectionArgs
if (-not $SkipReset) {
    $TrainArgs += @("--reset-skill-library", "--reset-experience-buffer")
}
Invoke-NlrlCli -CliArgs $TrainArgs

$EvalArgs = $CommonArgs + @("evaluate-tasks", "--run-name", $EvalRunName) + $SelectionArgs
Invoke-NlrlCli -CliArgs $EvalArgs

Write-Host "`nMode2 train+eval command sequence completed."
