@echo off
:: ============================================================
::  COLETAR_PC.bat — Coleta automatica de informacoes do PC
::  Gera arquivo INI: inventario_HOSTNAME_YYYYMMDD.txt
::  Para uso com o Sistema de Inventario TI v3.0
::  Compativel: Windows 10 / 11
:: ============================================================
setlocal EnableDelayedExpansion
chcp 65001 > nul 2>&1

echo.
echo  ============================================================
echo   COLETA AUTOMATICA DE INVENTARIO TI
echo  ============================================================
echo.

:: ── Data e hora para o nome do arquivo ───────────────────────
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set DT=%%I
set YYYYMMDD=%DT:~0,8%

:: ── Define nome do arquivo ───────────────────────────────────
for /f "tokens=2 delims==" %%H in ('wmic computersystem get name /value') do set HOSTNAME_PC=%%H
set FILENAME=inventario_%HOSTNAME_PC%_%YYYYMMDD%.txt
set FILEPATH=%USERPROFILE%\Desktop\%FILENAME%

:: ── Coleta e Gera arquivo via PowerShell (Padrão ouro de compatibilidade) ──
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$cs=Get-CimInstance Win32_ComputerSystem; $bios=Get-CimInstance Win32_BIOS; $cpu=Get-CimInstance Win32_Processor; $os=Get-CimInstance Win32_OperatingSystem; $discos=Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3'; $ramGB=[math]::Round($cs.TotalPhysicalMemory/1GB,1); $diskGB=0; foreach($d in $discos){$diskGB+=[math]::Round($d.Size/1GB,0)}; $adapters=Get-CimInstance Win32_NetworkAdapterConfiguration | Where-Object {$_.IPEnabled -eq $true -and $_.IPAddress -ne $null}; $ip=''; $mac=''; foreach($a in $adapters){if($a.IPAddress[0] -notmatch '^169'){$ip=$a.IPAddress[0];$mac=$a.MACAddress;break}}; $user=(Get-WmiObject -Class Win32_ComputerSystem).UserName -replace '.*\\',''; $tipo='Desktop'; if($cs.PCSystemType -eq 2){$tipo='Notebook'}; $serial=$bios.SerialNumber.Trim(); if($serial -match 'Default' -or $serial -eq 'To be filled by O.E.M.'){$serial=$cs.Name}; $out=@(); $out += '[hardware]'; $out += 'tipo='+$tipo; $out += 'marca='+$cs.Manufacturer.Trim(); $out += 'modelo='+$cs.Model.Trim(); $out += 'num_serie='+$serial; $out += 'processador='+$cpu.Name.Trim(); $out += 'memoria_ram='+$ramGB+'GB'; $out += 'armazenamento='+$diskGB+'GB'; $out += 'sistema_operacional='+$os.Caption.Trim(); $out += 'versao_so='+$os.Version+' Build '+$os.BuildNumber; $out += 'usuario='+$user; $out | Set-Content -Path '%FILEPATH%' -Encoding UTF8"

:: ── Exibe resumo no console ───────────────────────────────────
echo.
echo  ============================================================
echo   DADOS COLETADOS:
echo  ============================================================
type "%FILEPATH%"
echo.

echo.
echo  ============================================================
echo   Arquivo gerado: %FILENAME%
echo   Local: %FILEPATH%
echo  ============================================================
echo.
echo  Envie este arquivo ao setor de TI ou
echo  importe diretamente no Sistema de Inventario.
echo.

pause
endlocal
