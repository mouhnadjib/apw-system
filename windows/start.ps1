# يُشغَّل بواسطة المهمة المجدولة APW-Server عند إقلاع الجهاز.
Set-Location C:\apw\app
# ترميز UTF-8 للمخرجات العربية (وإلا ينهار الطباعة عند التحويل إلى ملف)
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
$log = 'C:\apw\logs\api.log'
if ((Test-Path $log) -and ((Get-Item $log).Length -gt 20MB)) { Move-Item $log "$log.1" -Force }
& cmd.exe /c "venv\Scripts\python.exe -m app.cli init-db >> $log 2>&1"
if ($LASTEXITCODE) { exit $LASTEXITCODE }   # القاعدة لم تجهز بعد -> تعيد المهمة المحاولة بعد دقيقة
# الربط بالعنوان المحلي فقط: الوصول الوحيد من الخارج عبر النفق
& cmd.exe /c "venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --proxy-headers >> $log 2>&1"
exit $LASTEXITCODE
