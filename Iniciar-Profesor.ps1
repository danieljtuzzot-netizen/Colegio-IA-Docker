param([ValidateSet('Base','Vllm15')][string]$Modo='Base')
$ErrorActionPreference='Stop'
Set-Location -LiteralPath $PSScriptRoot
function Invoke-DockerChecked {
    param([string[]]$DockerArgs)
    & docker @DockerArgs
    if ($LASTEXITCODE -ne 0) { throw ('Docker fallo. Codigo: ' + $LASTEXITCODE + '. Conservar la salida anterior.') }
}
try {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw 'Instalar Docker Desktop y abrirlo antes de continuar.' }
    $engineLines = & docker info --format '{{json .}}'
    if ($LASTEXITCODE -ne 0) { throw 'Docker no esta listo. Abrir Docker Desktop y esperar Engine running.' }
    $engine = ($engineLines -join "`n") | ConvertFrom-Json
    if ($engine.OSType -ne 'linux') { throw 'Se requieren contenedores Linux.' }
    if ($engine.Architecture -notin @('x86_64','amd64')) { throw 'Esta entrega esta preparada para CPU x86-64.' }
    if ($Modo -eq 'Vllm15' -and [double]$engine.MemTotal -lt (19GB)) {
        throw 'vLLM 1.5B requiere revisar la memoria efectiva de Docker. Referencia probada: PC de 32 GB con WSL en 20 GB. No se cambia memoria automaticamente.'
    }
    Write-Host ('Modo: ' + $Modo + '. Memoria efectiva Docker: ' + [math]::Round($engine.MemTotal/1GB,1) + ' GiB')
    & (Join-Path $PSScriptRoot 'VERIFICAR_ARCHIVOS.ps1')
    if ($LASTEXITCODE -ne 0) { throw 'La verificacion del paquete fallo.' }
    Invoke-DockerChecked -DockerArgs @('compose','-f','compose.ia.yaml','config','--quiet')
    if ($Modo -eq 'Vllm15') {
        Invoke-DockerChecked -DockerArgs @('compose','-f','VLLM_15B_PC/compose.vllm.15b.yaml','config','--quiet')
        Invoke-DockerChecked -DockerArgs @('compose','-f','compose.ia.yaml','-f','compose.vllm.15b.integracion.yaml','config','--quiet')
    }
    Invoke-DockerChecked -DockerArgs @('compose','-f','compose.ia.yaml','build','demo')
    if ($Modo -eq 'Vllm15') {
        Invoke-DockerChecked -DockerArgs @('compose','-f','VLLM_15B_PC/compose.vllm.15b.yaml','up','-d','--wait','--wait-timeout','1800')
        Invoke-DockerChecked -DockerArgs @('compose','-f','compose.ia.yaml','-f','compose.vllm.15b.integracion.yaml','up','-d','--wait','--wait-timeout','600')
    } else {
        Invoke-DockerChecked -DockerArgs @('compose','-f','compose.ia.yaml','up','-d','--wait','--wait-timeout','600')
    }
    Write-Host 'Demo disponible en http://127.0.0.1:8766/dashboard'
    Write-Host 'Ejecutar la prueba del apartado correspondiente de LEEME_PROFESOR.txt.'
    exit 0
} catch {
    Write-Host ('ARRANQUE DETENIDO: ' + $_.Exception.Message)
    Write-Host 'No se eliminan imagenes ni volumenes. Revisar LEEME_PROFESOR.txt.'
    exit 1
}
