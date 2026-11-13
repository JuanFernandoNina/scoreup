$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { throw 'No se encontro .venv. Instala las dependencias antes de iniciar.' }
$port = 5000
if ($env:PORT) { $port = [int]$env:PORT }
if (Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue) {
    Write-Host "El puerto $port ya esta ocupado. Cierra el servidor anterior antes de iniciar esta version."
    exit 1
}
if (-not $env:PUBLIC_BASE_URL) {
    $physical = @(Get-NetAdapter -Physical | Where-Object { $_.Status -eq 'Up' } | Select-Object -ExpandProperty ifIndex)
    $route = Get-NetRoute -DestinationPrefix '0.0.0.0/0' -ErrorAction SilentlyContinue |
        Where-Object { $_.NextHop -ne '0.0.0.0' -and $physical -contains $_.InterfaceIndex } |
        Sort-Object RouteMetric |
        Select-Object -First 1
    if ($route) {
        $ip = Get-NetIPAddress -InterfaceIndex $route.InterfaceIndex -AddressFamily IPv4 |
            Where-Object { $_.AddressState -eq 'Preferred' -and $_.IPAddress -notlike '169.254.*' } |
            Select-Object -First 1 -ExpandProperty IPAddress
        if ($ip) { $env:PUBLIC_BASE_URL = "http://${ip}:$port" }
    }
}
Write-Host "ScoreUp - PC: http://localhost:$port"
if ($env:PUBLIC_BASE_URL) {
    Write-Host "Celular y QR: $env:PUBLIC_BASE_URL"
    Write-Host 'Ambos dispositivos deben estar en la misma red. Con VPN, revisa la IP en la tarjeta QR.'
} else {
    Write-Host 'Sin direccion de red detectada. Puedes ajustarla en Clubes > QR del club.'
}
Write-Host 'Permite Python solo en redes privadas si Windows lo solicita. Ctrl+C para detener.'
& $python app.py
