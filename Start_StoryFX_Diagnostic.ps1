$ErrorActionPreference = 'Stop'
$storyRoot = $PSScriptRoot
$storyPython = Join-Path $storyRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $storyPython)) {
    throw 'Créer .venv puis installer server\requirements-dev.txt avant le démarrage.'
}
& $storyPython (Join-Path $storyRoot 'server\tools\initialize_local.py')
if ($LASTEXITCODE -ne 0) { throw 'Initialisation privée StoryFX refusée.' }
Push-Location -LiteralPath $storyRoot
try {
    & $storyPython -m uvicorn storyfx_server.main:app_factory --factory --app-dir server `
        --host 127.0.0.1 --port 18743 --no-access-log
} finally {
    Pop-Location
}
