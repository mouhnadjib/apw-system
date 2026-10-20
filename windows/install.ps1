#Requires -RunAsAdministrator
# تثبيت خادم المجلس على Windows 11 (بلا Docker).
# المتطلبات المسبقة: Python 3.12+ (مع py launcher)، PostgreSQL 16+، 7-Zip، cloudflared.
# يمكن إعادة تشغيله لتحديث الكود دون المساس بالإعدادات والبيانات.
$ErrorActionPreference = 'Stop'
$Root = 'C:\apw'
$Project = Split-Path -Parent $PSScriptRoot

function New-RandomSecret([int]$bytes = 24) {
    $b = New-Object byte[] $bytes
    [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b)
    ([Convert]::ToBase64String($b) -replace '[^A-Za-z0-9]', '')
}
function Lock-File([string]$path) {
    icacls $path /inheritance:r /grant:r "SYSTEM:(F)" "Administrators:(F)" | Out-Null
}

# ---- فحص المتطلبات ----
if (-not (Get-Command py -ErrorAction SilentlyContinue)) { throw 'Python غير مثبّت (يلزم py launcher). نزّله من python.org.' }
$okPy = & py -3 -c "import sys;print(int(sys.version_info>=(3,11)))"
if ($okPy -ne '1') { throw 'يلزم Python 3.11 أو أحدث.' }
$psql = Get-ChildItem 'C:\Program Files\PostgreSQL\*\bin\psql.exe' -ErrorAction SilentlyContinue | Sort-Object FullName -Descending | Select-Object -First 1
if (-not $psql) { throw 'PostgreSQL غير مثبّت. نزّل المثبّت من postgresql.org.' }
if (-not (Test-Path 'C:\Program Files\7-Zip\7z.exe')) { throw '7-Zip غير مثبّت (يلزم للنسخ الاحتياطي المشفّر).' }

# ---- المجلدات ونسخ الكود ----
foreach ($d in 'app', 'data', 'logs', 'secrets') { New-Item -ItemType Directory -Force "$Root\$d" | Out-Null }
robocopy "$Project\app" "$Root\app\app" /MIR /XD __pycache__ /NFL /NDL /NJH /NJS | Out-Null
Copy-Item "$Project\requirements.txt" "$Root\app\requirements.txt" -Force
Copy-Item "$PSScriptRoot\start.ps1" "$Root\start.ps1" -Force
Copy-Item "$PSScriptRoot\backup.ps1" "$Root\backup.ps1" -Force

if (-not (Test-Path "$Root\app\venv")) { & py -3 -m venv "$Root\app\venv" }
& "$Root\app\venv\Scripts\python.exe" -m pip install --upgrade pip -q
& "$Root\app\venv\Scripts\python.exe" -m pip install -r "$Root\app\requirements.txt" -q
if ($LASTEXITCODE) { throw 'فشل تثبيت مكتبات Python' }

# ---- قاعدة البيانات والمفاتيح (أول تثبيت فقط) ----
$envFile = "$Root\app\.env"
if (-not (Test-Path $envFile)) {
    $sec = Read-Host 'كلمة مرور مستخدم postgres (التي حددتها عند تثبيت PostgreSQL)' -AsSecureString
    $super = [Net.NetworkCredential]::new('', $sec).Password
    $pgPass = New-RandomSecret
    $env:PGPASSWORD = $super
    & $psql.FullName -U postgres -h localhost -v ON_ERROR_STOP=1 -c "CREATE ROLE apw LOGIN PASSWORD '$pgPass'"
    if ($LASTEXITCODE) { throw 'فشل إنشاء مستخدم القاعدة (أهو موجود مسبقاً؟)' }
    & $psql.FullName -U postgres -h localhost -v ON_ERROR_STOP=1 -c "CREATE DATABASE apw OWNER apw"
    if ($LASTEXITCODE) { throw 'فشل إنشاء القاعدة' }
    # القاعدة تستمع للجهاز المحلي فقط
    & $psql.FullName -U postgres -h localhost -c "ALTER SYSTEM SET listen_addresses = 'localhost'" | Out-Null
    Get-Service 'postgresql*' | Restart-Service
    Remove-Item Env:PGPASSWORD

    Push-Location "$Root\app"   # app.cli يُستورد من هذا المجلد فقط
    $keys = @(& "$Root\app\venv\Scripts\python.exe" -m app.cli gen-keys)
    Pop-Location
    if ($keys.Count -lt 3) { throw 'فشل توليد مفاتيح التشفير' }
    $lines = @(
        "PG_PASSWORD=$pgPass",
        "APW_DATABASE_URL=postgresql+psycopg://apw:$pgPass@localhost:5432/apw",
        "APW_DATA_DIR=C:/apw/data",
        "APW_FCM_CREDENTIALS=C:/apw/secrets/fcm.json"
    ) + $keys
    # UTF-8 بلا BOM (وجود BOM يفسد قراءة أول مفتاح)
    [IO.File]::WriteAllText($envFile, ($lines -join "`n") + "`n", (New-Object Text.UTF8Encoding($false)))
    Lock-File $envFile

    $bp = "$Root\secrets\backup-pass.txt"
    [IO.File]::WriteAllText($bp, (New-RandomSecret 32), (New-Object Text.UTF8Encoding($false)))
    Lock-File $bp
    Write-Host "`n!! انسخ الملفين التاليين إلى وسيط خارجي (فلاشة) وخبّئه في مكان آمن:" -ForegroundColor Yellow
    Write-Host "   $envFile   (مفاتيح التشفير)"
    Write-Host "   $bp   (عبارة مرور النسخ الاحتياطي)"
    Write-Host "   ضياعهما = ضياع البيانات المشفّرة نهائياً.`n" -ForegroundColor Yellow
}

# ---- الخدمة (مهمة مجدولة تعمل عند الإقلاع بلا تسجيل دخول) ----
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument '-NoProfile -ExecutionPolicy Bypass -File C:\apw\start.ps1' -WorkingDirectory "$Root\app"
$trigger = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName 'APW-Server' -Action $action -Trigger $trigger -Settings $settings -User 'SYSTEM' -RunLevel Highest -Force | Out-Null

# ---- النسخ الاحتياطي اليومي ----
$dest = if (Test-Path 'D:\') { 'D:\apw-backup' } else { 'C:\apw\backup' }
$bAction = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -ExecutionPolicy Bypass -File C:\apw\backup.ps1 -Dest `"$dest`""
Register-ScheduledTask -TaskName 'APW-Backup' -Action $bAction -Trigger (New-ScheduledTaskTrigger -Daily -At 2am) -User 'SYSTEM' -RunLevel Highest -Force | Out-Null
if ($dest -like 'C:*') { Write-Host 'تنبيه: النسخ على نفس القرص. وجّهها إلى قرص خارجي أو مسار شبكي (عدّل مهمة APW-Backup).' -ForegroundColor Yellow }

# ---- الطاقة: لا سبات ولا إسبات (الخادم يعمل دائماً) ----
powercfg /change standby-timeout-ac 0
powercfg /h off

Start-ScheduledTask -TaskName 'APW-Server'
Start-Sleep -Seconds 8
try {
    $r = Invoke-RestMethod http://127.0.0.1:8000/health
    Write-Host "الخادم يعمل: $($r | ConvertTo-Json -Compress)" -ForegroundColor Green
} catch {
    Write-Host 'لم يستجب الخادم بعد. راجع C:\apw\logs\api.log' -ForegroundColor Red
}
Write-Host @"

الخطوات التالية:
  1) أنشئ الأدمن:  cd C:\apw\app ; .\venv\Scripts\python.exe -m app.cli create-admin admin "الاسم الكامل"
  2) النفق:  cloudflared service install <TOKEN>   (الرمز من لوحة Cloudflare، الوجهة http://localhost:8000)
  3) ضع ملف FCM في C:\apw\secrets\fcm.json ثم أعد تشغيل المهمة APW-Server
"@
