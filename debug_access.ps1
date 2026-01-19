
$dbPath = "D:\Program Files (x86)\HIPPremiumTime-2.0.4\db\Pm2014.mdb"
$password = "hippmforyou"

Write-Host "--- Environment Info ---"
Write-Host "Is 64-bit Process: $([Environment]::Is64BitProcess)"
Write-Host "OS Architecture: $((Get-WmiObject Win32_OperatingSystem).OSArchitecture)"

Write-Host "`n--- Installed ODBC Drivers (System) ---"
# Check registry for drivers
$drivers32 = Get-ItemProperty "HKLM:\SOFTWARE\WOW6432Node\ODBC\ODBCINST.INI\ODBC Drivers" -ErrorAction SilentlyContinue
$drivers64 = Get-ItemProperty "HKLM:\SOFTWARE\ODBC\ODBCINST.INI\ODBC Drivers" -ErrorAction SilentlyContinue

Write-Host "64-bit Drivers (if any):"
if ($drivers64) { $drivers64.PSObject.Properties | Where-Object { $_.Name -ne "PSPath" -and $_.Name -ne "PSParentPath" -and $_.Name -ne "PSChildName" -and $_.Name -ne "PSDrive" -and $_.Name -ne "PSProvider" } | ForEach-Object { Write-Host "  $($_.Name)" } }
else { Write-Host "  (None found or unable to access registry)" }

Write-Host "32-bit Drivers (if any):"
if ($drivers32) { $drivers32.PSObject.Properties | Where-Object { $_.Name -ne "PSPath" -and $_.Name -ne "PSParentPath" -and $_.Name -ne "PSChildName" -and $_.Name -ne "PSDrive" -and $_.Name -ne "PSProvider" } | ForEach-Object { Write-Host "  $($_.Name)" } }
else { Write-Host "  (None found or unable to access registry)" }

Write-Host "`n--- Testing Connection ---"
$connStr = "Driver={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=$dbPath;PWD=$password;"
Write-Host "ConnectionString: $connStr"

try {
    $conn = New-Object System.Data.Odbc.OdbcConnection($connStr)
    $conn.Open()
    Write-Host "SUCCESS: Connected to database!" -ForegroundColor Green
    $conn.Close()
} catch {
    Write-Host "FAILURE: Could not connect." -ForegroundColor Red
    Write-Host "Error: $($_.Exception.Message)"
    
    # Try alternate driver string for old MDB
    Write-Host "`nAttempting fallback driver string..."
    $connStr2 = "Driver={Microsoft Access Driver (*.mdb)};DBQ=$dbPath;PWD=$password;"
    try {
        $conn = New-Object System.Data.Odbc.OdbcConnection($connStr2)
        $conn.Open()
        Write-Host "SUCCESS: Connected with legacy driver string!" -ForegroundColor Green
        $conn.Close()
    } catch {
        Write-Host "FAILURE: Legacy driver also failed." -ForegroundColor Red
        Write-Host "Error: $($_.Exception.Message)"
    }
}
