[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[a-z0-9][a-z0-9_-]{1,38}$')]
    [string]$Namespace,
    [ValidatePattern('^[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}$')]
    [string]$Tag = '0.1.0',
    [switch]$Push
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$previousNamespace = $env:DOCKERHUB_NAMESPACE
$previousTag = $env:IMAGE_TAG
Push-Location $projectRoot
try {
    $env:DOCKERHUB_NAMESPACE = $Namespace
    $env:IMAGE_TAG = $Tag
    docker compose config --quiet
    if ($LASTEXITCODE -ne 0) { throw 'Compose validation failed. Create .env from .env.example first.' }
    docker compose build backend frontend
    if ($LASTEXITCODE -ne 0) { throw 'Docker build failed; nothing was published.' }
    $pythonCommand = if (Test-Path -LiteralPath '.venv/Scripts/python.exe') { '.venv/Scripts/python.exe' } else { 'python' }
    & $pythonCommand scripts/docker-smoke.py --namespace $Namespace --tag $Tag
    if ($LASTEXITCODE -ne 0) { throw 'Container smoke test failed; nothing was published.' }
    if ($Push) {
        docker compose push backend frontend
        if ($LASTEXITCODE -ne 0) { throw 'Push failed. Check docker login and repository permissions; one image may already have uploaded.' }
        Write-Output "Published docker.io/$Namespace/qubettera-backend`:$Tag and docker.io/$Namespace/qubettera-frontend`:$Tag"
    } else {
        Write-Output 'Build and smoke checks passed. Add -Push to publish after docker login.'
    }
} finally {
    $env:DOCKERHUB_NAMESPACE = $previousNamespace
    $env:IMAGE_TAG = $previousTag
    Pop-Location
}
