# نسخة احتياطية مشفّرة (AES-256 عبر 7-Zip): قاعدة البيانات + الملفات المشفّرة.
param([string]$Dest = 'D:\apw-backup', [int]$Keep = 30)
$ErrorActionPreference = 'Stop'
$Root = 'C:\apw'
$sevenZip = 'C:\Program Files\7-Zip\7z.exe'
$pgDump = Get-ChildItem 'C:\Program Files\PostgreSQL\*\bin\pg_dump.exe' | Sort-Object FullName -Descending | Select-Object -First 1
$pgPass = ((Get-Content "$Root\app\.env" | Where-Object { $_ -like 'PG_PASSWORD=*' }) -replace '^PG_PASSWORD=', '').Trim()
$pass = (Get-Content "$Root\secrets\backup-pass.txt" -Raw).Trim()

New-Item -ItemType Directory -Force $Dest | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd-HHmm'
$tmp = Join-Path $env:TEMP "apw-$stamp.sql"
try {
    $env:PGPASSWORD = $pgPass
    & $pgDump.FullName -U apw -h localhost -f $tmp apw
    if ($LASTEXITCODE) { throw 'فشل pg_dump' }
    & $sevenZip a -t7z -mhe=on "-p$pass" "$Dest\db-$stamp.7z" $tmp | Out-Null
    if ($LASTEXITCODE) { throw 'فشل ضغط القاعدة' }
    & $sevenZip a -t7z -mhe=on -mx=1 "-p$pass" "$Dest\files-$stamp.7z" "$Root\data\files" | Out-Null
    if ($LASTEXITCODE) { throw 'فشل ضغط الملفات' }
} finally {
    Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
    Remove-Item $tmp -Force -ErrorAction SilentlyContinue
}
foreach ($prefix in 'db-', 'files-') {
    Get-ChildItem $Dest -Filter "$prefix*.7z" | Sort-Object LastWriteTime -Descending | Select-Object -Skip $Keep | Remove-Item -Force
}
