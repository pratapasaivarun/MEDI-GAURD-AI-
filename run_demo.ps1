param(
    [int]$Port = 8506
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $root ".venv\Scripts\python.exe"
$ollama = Get-Command "ollama" -ErrorAction SilentlyContinue
$model = if ($env:OLLAMA_MODEL) { $env:OLLAMA_MODEL } else { "ibm/granite4.1:8b" }
$hostUrl = if ($env:OLLAMA_HOST) { $env:OLLAMA_HOST.TrimEnd("/") } else { "http://127.0.0.1:11434" }
$ollamaProcess = $null
$appProcess = $null
$ollamaStarted = $false

if (-not (Test-Path $python)) {
    throw "Project virtual environment is missing. Create it and install requirements before running this demo."
}
if (-not $ollama) {
    throw "Ollama is not installed or not available on PATH."
}

$ollamaReady = $false
try {
    $tags = Invoke-RestMethod -Uri "$hostUrl/api/tags" -TimeoutSec 2
    $ollamaReady = $true
} catch {
    $tags = $null
}

try {
    if (-not $ollamaReady) {
        $ollamaLog = Join-Path $root "data\final_demo\ollama.log"
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $ollamaLog) | Out-Null
        $ollamaProcess = Start-Process -FilePath $ollama.Source -ArgumentList "serve" `
            -WorkingDirectory $root -WindowStyle Hidden -RedirectStandardOutput $ollamaLog `
            -RedirectStandardError (Join-Path $root "data\final_demo\ollama-error.log") -PassThru
        $ollamaStarted = $true
        for ($attempt = 0; $attempt -lt 60; $attempt++) {
            if ($ollamaProcess.HasExited) {
                throw "Ollama exited before its API became ready. Check $ollamaLog"
            }
            try {
                $tags = Invoke-RestMethod -Uri "$hostUrl/api/tags" -TimeoutSec 2
                $ollamaReady = $true
                break
            } catch {
                Start-Sleep -Seconds 1
            }
        }
        if (-not $ollamaReady) {
            throw "Ollama did not become ready at $hostUrl within 60 seconds."
        }
    }

    if (-not ($tags.models | Where-Object { $_.name -eq $model })) {
        throw "Ollama model '$model' is not installed. Install it with: ollama pull $model"
    }

    $storage = Join-Path $root "data\final_demo"
    New-Item -ItemType Directory -Force -Path $storage | Out-Null
    $env:MEDIGUARD_DB_PATH = Join-Path $storage "mediguard.db"
    $env:MEDIGUARD_STORAGE_DIR = $storage
    $env:CHROMA_DIR = Join-Path $storage "chroma"
    $env:MEDIGUARD_CORE_DEMO = "true"
    $env:MEDIGUARD_TRUSTED_FIXTURES = "true"
    $env:APP_ENV = "development"
    $env:MEDIGUARD_ADMIN_EMAIL = ""
    $env:MEDIGUARD_DEMO_PORT = "$Port"
    $env:OLLAMA_HOST = $hostUrl
    $env:OLLAMA_MODEL = $model

    $portInUse = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if ($portInUse) {
        throw "Port $Port is already in use. Stop that specific app process or choose another port with -Port."
    }

    $appLog = Join-Path $storage "streamlit.log"
    $appProcess = Start-Process -FilePath $python -ArgumentList @(
        "-m", "streamlit", "run", (Join-Path $root "app.py"),
        "--server.port", "$Port", "--server.address", "127.0.0.1"
    ) -WorkingDirectory $root -WindowStyle Hidden -RedirectStandardOutput $appLog `
      -RedirectStandardError (Join-Path $storage "streamlit-error.log") -PassThru

    $appUrl = "http://127.0.0.1:$Port"
    $healthy = $false
    for ($attempt = 0; $attempt -lt 90; $attempt++) {
        if ($appProcess.HasExited) {
            throw "Streamlit exited before becoming ready. Check $appLog"
        }
        try {
            $health = Invoke-WebRequest -Uri "$appUrl/_stcore/health" -TimeoutSec 2
            if ($health.StatusCode -eq 200) {
                $healthy = $true
                break
            }
        } catch {
            Start-Sleep -Seconds 1
        }
    }
    if (-not $healthy) {
        throw "Streamlit did not become healthy within 90 seconds. Check $appLog"
    }

    $caseRoot = Join-Path $root "samples\demo_cases"
    $cards = foreach ($caseName in @("a_match", "b_wrongful_deduction", "c_manual_review")) {
        $caseDir = Join-Path $caseRoot $caseName
        $manifest = Get-Content (Join-Path $caseDir "case.json") -Raw | ConvertFrom-Json
        $links = foreach ($file in @("bill.pdf", "policy.pdf", "settlement.pdf")) {
            $fileUri = ([System.Uri](Join-Path $caseDir $file)).AbsoluteUri
            "<a href=`"$fileUri`">$file</a>"
        }
        "<section><h2>$caseName</h2><p>$($manifest.expected.expected_status)</p><p>$($links -join ' · ')</p></section>"
    }
    $catalog = Join-Path $env:TEMP "mediguard-demo-cases.html"
    $html = @"
<!doctype html>
<html lang="en">
<meta charset="utf-8">
<title>MediGuard AI fictional demo cases</title>
<style>body{font:16px system-ui;max-width:850px;margin:3rem auto;padding:0 1rem;color:#163b35}section{border:1px solid #b7d8d0;border-radius:12px;padding:1rem;margin:1rem 0}a{margin-right:1rem}</style>
<h1>MediGuard AI — fictional demo cases</h1>
<p>Synthetic fictional data only. Use the app to upload each case's bill, policy, and settlement letter.</p>
<p><a href="$appUrl">Open the MediGuard app</a></p>
$($cards -join "`n")
</html>
"@
    Set-Content -Path $catalog -Value $html -Encoding UTF8
    Start-Process $appUrl
    Start-Process ([System.Uri]$catalog).AbsoluteUri
    Write-Host "MediGuard app: $appUrl"
    Write-Host "Demo case catalog: $catalog"
    Write-Host "Synthetic demo data is stored in $storage"
    Write-Host "Close the Streamlit process (PID $($appProcess.Id)) when finished."
} catch {
    if ($appProcess -and -not $appProcess.HasExited) {
        Stop-Process -Id $appProcess.Id
    }
    if ($ollamaStarted -and $ollamaProcess -and -not $ollamaProcess.HasExited) {
        Stop-Process -Id $ollamaProcess.Id
    }
    throw
}
