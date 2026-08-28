param(
    [Parameter(Mandatory=$true)][string]$NodePath,
    [Parameter(Mandatory=$true)][string]$PackagesPath
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path -LiteralPath $NodePath -PathType Leaf)) { throw 'No se encontró Node.' }
if (-not (Test-Path -LiteralPath (Join-Path $PackagesPath '@oai\artifact-tool') -PathType Container)) { throw 'No se encontró artifact-tool en la ruta proporcionada.' }
$linkPath = Join-Path $projectRoot 'node_modules'
if (Test-Path -LiteralPath $linkPath) {
    $existing = Get-Item -LiteralPath $linkPath
    if ($existing.LinkType -ne 'Junction' -or $existing.Target -ne $PackagesPath) { throw 'node_modules ya existe y no corresponde al runtime. No se modificó.' }
} else {
    New-Item -ItemType Junction -Path $linkPath -Target $PackagesPath | Out-Null
}
$runtimeDir = Join-Path $projectRoot '.runtime'
New-Item -ItemType Directory -Path $runtimeDir -Force | Out-Null
@{node=$NodePath;packages=$PackagesPath} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $runtimeDir 'excel.json') -Encoding utf8
Write-Output 'Motor Excel configurado para esta computadora.'
