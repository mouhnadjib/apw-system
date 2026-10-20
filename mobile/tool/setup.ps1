# إعداد مشروع Flutter لأول مرة (يُشغَّل من مجلد mobile):
#   powershell -ExecutionPolicy Bypass -File tool\setup.ps1
# يولّد مجلدي android/ios إن لم يوجدا، ثم يطبّق ملفات Android الأصلية الخاصة بالتطبيق.
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)

if (-not (Get-Command flutter -ErrorAction SilentlyContinue)) {
    throw 'Flutter غير مثبّت أو غير موجود في PATH. ثبّته من https://docs.flutter.dev/get-started/install'
}

if (-not (Test-Path 'android')) {
    flutter create --org dz.apw --project-name apw_deputies --platforms android,ios .
    if ($LASTEXITCODE -ne 0) { throw 'فشل flutter create' }
}
if (Test-Path 'test\widget_test.dart') { Remove-Item 'test\widget_test.dart' -Force }

# نسخ ملفات Android الأصلية (MainActivity مع FLAG_SECURE، السمات، بيان التطوير)
Copy-Item -Path 'native_overlay\android\*' -Destination 'android' -Recurse -Force

# حذف MainActivity الافتراضية إن كانت في مسار آخر (ملف واحد فقط يجب أن يبقى)
Get-ChildItem 'android\app\src\main' -Recurse -Include 'MainActivity.kt','MainActivity.java' |
    Where-Object { $_.FullName -notmatch 'dz[\\/]apw[\\/]apw_deputies[\\/]MainActivity\.kt$' } |
    Remove-Item -Force

# تعديل البيان الرئيسي
$manifest = 'android\app\src\main\AndroidManifest.xml'
$xml = [System.IO.File]::ReadAllText((Resolve-Path $manifest), [System.Text.Encoding]::UTF8)

$perms = @(
    'android.permission.INTERNET',
    'android.permission.USE_BIOMETRIC',
    'android.permission.POST_NOTIFICATIONS'
)
foreach ($p in $perms) {
    if ($xml -notmatch [regex]::Escape($p)) {
        $line = "    <uses-permission android:name=`"$p`"/>`r`n    "
        $xml = $xml -replace '(<application)', ($line + '$1')
    }
}
$xml = $xml -replace 'android:label="[^"]*"', 'android:label="المجلس الشعبي الولائي"'
if ($xml -notmatch 'android:allowBackup') {
    $xml = $xml -replace '(<application)', '$1 android:allowBackup="false"'
}
[System.IO.File]::WriteAllText((Resolve-Path $manifest), $xml, (New-Object System.Text.UTF8Encoding($false)))

flutter pub get
if ($LASTEXITCODE -ne 0) { throw 'فشل flutter pub get' }

Write-Host ''
Write-Host 'تم الإعداد. الخطوات التالية:' -ForegroundColor Green
Write-Host '  flutter analyze'
Write-Host '  flutter test'
Write-Host '  flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000 --dart-define=REQUIRE_DEVICE_LOCK=false'
