<# :
@echo off
setlocal
chcp 65001 > nul 2>&1
echo.
echo  ============================================================
echo   COLETA AUTOMATICA DE BP Central TI
echo  ============================================================
echo.
echo  Coletando dados do sistema...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Invoke-Expression $([System.IO.File]::ReadAllText('%~f0'))"
if errorlevel 1 (
    echo.
    echo  [ERRO] Ocorreu um problema na execucao.
    pause
    goto :EOF
)
echo.
echo  Aperte qualquer tecla para fechar...
pause > nul
goto :EOF
#>

# ====================================================================
# SCRIPT POWERSHELL
# ====================================================================

function Limpar([string]$s) {
    if ([string]::IsNullOrWhiteSpace($s)) { return '' }
    return ($s -replace '[^\x20-\xFF]', '').Trim()
}

try {
    $desktop = [Environment]::GetFolderPath('Desktop')
    $hostname = Limpar($env:COMPUTERNAME)
    $dateStr = Get-Date -Format 'yyyyMMdd'
    $OutFile = "$desktop\inventario_${hostname}_${dateStr}.txt"

    $cs     = Get-CimInstance Win32_ComputerSystem
    $bios   = Get-CimInstance Win32_BIOS
    $cpu    = Get-CimInstance Win32_Processor
    $os     = Get-CimInstance Win32_OperatingSystem
    $mem = Get-CimInstance Win32_PhysicalMemory
    $ramTotal = 0
    foreach ($m in $mem) { $ramTotal += $m.Capacity }
    $ramGB = [math]::Round($ramTotal / 1GB, 0)
    $ramStr = "$ramGB" + "GB"

    $drives = Get-CimInstance Win32_DiskDrive
    $diskTotal = 0
    foreach ($drive in $drives) { $diskTotal += $drive.Size }
    # Usa divisao decimal (1000^3) para espelhar a capacidade comercial real (ex: 256GB, 512GB)
    $diskGB = [math]::Round($diskTotal / 1000000000, 0)
    $diskStr = "$diskGB" + "GB"

    $adapters = Get-CimInstance Win32_NetworkAdapterConfiguration | Where-Object {
        $_.IPEnabled -eq $true -and $_.IPAddress -ne $null
    }
    $ip = ''; $mac = ''
    foreach ($a in $adapters) {
        if ($a.IPAddress[0] -notmatch '^169') {
            $ip  = Limpar($a.IPAddress[0])
            $mac = Limpar($a.MACAddress)
            break
        }
    }

    $userFull = (Get-WmiObject -Class Win32_ComputerSystem).UserName
    $user = if ($userFull) { Limpar(($userFull -split '\\')[-1]) } else { '' }

    $tipo = if ($cs.PCSystemType -eq 2) { 'Notebook' } else { 'Desktop' }

    $serial = Limpar($bios.SerialNumber)
    if (-not $serial -or $serial -match 'Default|O\.E\.M\.|To be filled|Not Specified|None|^0+$') {
        $serial = Limpar($cs.Name)
    }

    $verSO = (Limpar $os.Version) + " Build " + (Limpar $os.BuildNumber)
    $marca  = Limpar $cs.Manufacturer
    $modelo = Limpar $cs.Model
    $proc   = Limpar $cpu.Name
    $soName = Limpar $os.Caption

    $out = @(
        '[hardware]',
        "tipo=$tipo",
        "marca=$marca",
        "modelo=$modelo",
        "num_serie=$serial",
        "processador=$proc",
        "memoria_ram=$ramStr",
        "armazenamento=$diskStr",
        "sistema_operacional=$soName",
        "versao_so=$verSO",
        "ip_rede=$ip",
        "mac_address=$mac",
        "usuario=$user"
    )

    [IO.File]::WriteAllLines($OutFile, $out, [System.Text.Encoding]::UTF8)

    Write-Host " ============================================================"
    Write-Host "  DADOS COLETADOS:"
    Write-Host " ============================================================"
    Get-Content $OutFile | ForEach-Object { Write-Host "  $_" }
    Write-Host ""
    Write-Host " ============================================================"
    Write-Host "  Arquivo gerado com sucesso!"
    Write-Host "  Local: $OutFile"
    Write-Host " ============================================================"
    Write-Host ""
    Write-Host "  Importe no Sistema de BP Central TI:"
    Write-Host "  Aba 'Notebooks / PCs' -> botao 'Importar Coleta'"
    Write-Host ""
} catch {
    Write-Error "Erro durante a coleta: $_"
    exit 1
}
