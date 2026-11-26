$ErrorActionPreference = 'Stop'
$packageRoot = [IO.Path]::GetFullPath($PSScriptRoot)
$manifest = Get-Content -LiteralPath (Join-Path $packageRoot 'ENTREGA_MANIFEST.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$failures = 0
$checked = 0
foreach ($entry in $manifest.sha256_archivos.PSObject.Properties) {
    $target = [IO.Path]::GetFullPath((Join-Path $packageRoot $entry.Name))
    if (-not $target.StartsWith($packageRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Ruta fuera del paquete en el manifiesto.'
    }
    if (-not (Test-Path -LiteralPath $target -PathType Leaf)) {
        Write-Host ('FALTA: ' + $entry.Name)
        $failures++
        continue
    }
    $stream = [IO.File]::OpenRead($target)
    $algorithm = [Security.Cryptography.SHA256]::Create()
    try {
        $hash = [BitConverter]::ToString($algorithm.ComputeHash($stream)).Replace('-', '').ToLowerInvariant()
    } finally {
        $stream.Dispose()
        $algorithm.Dispose()
    }
    if ($hash -ne $entry.Value) {
        Write-Host ('DIFERENTE: ' + $entry.Name)
        $failures++
    }
    $checked++
}
Write-Host ('Archivos comprobados: ' + $checked + '; faltantes o diferentes: ' + $failures)
if ($failures -gt 0) { exit 1 }
Write-Host 'PAQUETE INTEGRO. Esta comprobacion no certifica el arranque ni la memoria de Docker.'
exit 0
