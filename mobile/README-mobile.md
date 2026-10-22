# تطبيق النواب (Flutter)

تطبيق عربي (RTL) لنواب المجلس الشعبي الولائي: الإشعارات، الأسئلة الكتابية.
**أندرويد أولاً**؛ الشيفرة نفسها تعمل على iPhone (انظر آخر الوثيقة).

> **تنبيه صريح:** كُتبت هذه الشيفرة دون إمكانية تثبيت Flutter في بيئة التطوير، فلم تُترجَم ولم تُحلَّل ولم تُجرَّب على هاتف.
> مررت فقط بفحص صياغة (syntax) خالٍ من الأخطاء. توقّع أن يظهر عند أول `flutter analyze` عدد قليل من الملاحظات
> (استيراد ناقص، توقيع دالة...) وهي تُصلَح عادةً في دقائق. اتبع «قائمة أول بناء» أدناه.

## المتطلبات (على حاسوب المطوّر، Windows 11)
1. Flutter SDK (قناة stable، يتضمن Dart ≥ 3.4) وإضافة `flutter\bin` إلى PATH.
2. Android Studio (لـ Android SDK والمحاكي) ثم `flutter doctor --android-licenses` ثم `flutter doctor`.
3. هاتف أندرويد حقيقي لتجربة البصمة والإشعارات (المحاكي مقبول للبقية).

## الإعداد لأول مرة
من مجلد `mobile`:
```powershell
powershell -ExecutionPolicy Bypass -File tool\setup.ps1
```
يولّد السكربت مجلدي `android/` و`ios/`، ويطبّق ملفات `native_overlay` (منع لقطات الشاشة `FLAG_SECURE`،
`FlutterFragmentActivity` لازم للبصمة، سمات AppCompat، السماح باتصال http في نسخة التطوير فقط)،
ويضيف الأذونات (الإنترنت، البصمة، الإشعارات)، ويعطّل النسخ الاحتياطي التلقائي للتطبيق، ثم يشغّل `flutter pub get`.

## قائمة أول بناء
1. `flutter analyze` — أصلح أي ملاحظة (أرسلها لي إن شئت).
2. `flutter test` — اختبارات الصيغ والنماذج وعميل الشبكة وحالة الجلسة وشاشة التفعيل.
3. تشغيل الخادم محلياً ثم التطبيق على المحاكي:
   ```powershell
   flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000 --dart-define=REQUIRE_DEVICE_LOCK=false
   ```
   (`10.0.2.2` هو عنوان حاسوبك من داخل المحاكي. على هاتف حقيقي استخدم عنوان الحاسوب في الشبكة المحلية، أو نفق https.)
4. تجربة يدوية كاملة:
   - من اللوحة: أنشئ دورة ولجنة ونائباً، ثم «رمز دعوة».
   - في التطبيق: أدخل رقم الهاتف والرمز ← التفعيل ← (قفل الجهاز).
   - أرسل إشعاراً من اللوحة وتحقق أنه يظهر خلال دقيقة (التطبيق يستعلم كل 60 ثانية دون Firebase).
   - أرسل سؤالاً ← أعده من اللوحة بملاحظة ← عدّله في التطبيق ← أكّده وأحِله ← ارفع الرد (PDF/صورة) ← افتحه في التطبيق.
   - تبديل الجهاز: «فصل الجهاز» من اللوحة يقطع الجلسة ثم أنشئ رمز دعوة جديداً.
5. إن فشل عرض PDF على جهاز معيّن (مكتبة `pdfx`) فالبديل: استبدالها بـ `pdfrx` في `pubspec.yaml` وتعديل `reply_viewer_screen.dart` فقط.
6. الخط: يعتمد التطبيق خط النظام (يدعم العربية على أندرويد). لتوحيد المظهر يمكن إضافة خط عربي في `pubspec.yaml` (مثل Cairo أو Tajawal) وربطه في `lib/ui/theme.dart`.

## بناء نسخة الإصدار
1. أنشئ مفتاح توقيع (احفظه ونسخته الاحتياطية في مكان آمن، فضياعه يمنع تحديث التطبيق):
   ```powershell
   keytool -genkey -v -keystore apw-release.jks -keyalg RSA -keysize 2048 -validity 10000 -alias apw
   ```
2. أنشئ `android/key.properties` (لا يُرفع لأي مستودع):
   ```
   storePassword=...
   keyPassword=...
   keyAlias=apw
   storeFile=C:/path/to/apw-release.jks
   ```
   واربطه في `android/app/build.gradle(.kts)` وفق https://docs.flutter.dev/deployment/android#sign-the-app
3. البناء (العنوان **يجب** أن يكون https، وإلا يرفض التطبيق العمل في نسخة الإصدار):
   ```powershell
   flutter build apk --release --dart-define=API_BASE_URL=https://<نطاق-الخادم>
   ```
   الناتج: `build\app\outputs\flutter-apk\app-release.apk`.
4. التوزيع على النواب: إرسال ملف APK مباشرة (سماح «التثبيت من مصدر غير معروف» مرة واحدة)، أو Google Play بنشر «داخلي/مغلق» بلا مراجعة عامة.
   لأن الحساب لا يُفعَّل إلا برمز دعوة من الديوان، فالتوزيع المحدود آمن.

## الأمان في التطبيق
- الرموز في Keystore عبر `flutter_secure_storage`، ولا بيانات حساسة على القرص (عرض الرد في الذاكرة فقط).
- قفل بالبصمة/رمز الجهاز عند الفتح وبعد دقيقتين في الخلفية؛ إن لم يكن للجهاز قفل شاشة يُمنع التطبيق (إلا بـ `REQUIRE_DEVICE_LOCK=false` للتطوير).
- منع لقطات الشاشة وإخفاء المحتوى في قائمة التطبيقات الأخيرة.
- جهاز واحد نشط لكل نائب، وتجديد الرموز تلقائياً، وقطع الجلسة فور تعطيل النائب أو فصل جهازه.
- اتصال https إلزامي في الإصدار، وإشعارات FCM بمحتوى عام فقط («لديك إشعار جديد»)؛ النص الحقيقي يُجلب من الخادم بعد فتح التطبيق.

## إشعارات الدفع الفورية (FCM) — اختيارية
دون Firebase يعمل التطبيق ويستعلم كل 60 ثانية وهو مفتوح. للإشعار الفوري والتطبيق مغلق:
1. أنشئ مشروعاً في https://console.firebase.google.com وأضف تطبيق Android بالحزمة `dz.apw.apw_deputies`.
2. نزّل `google-services.json` وضعه في `android/app/`.
3. في `android/settings.gradle(.kts)` أضف إلى المكوّنات الإضافية: `id("com.google.gms.google-services") version "4.4.2" apply false`،
   وفي `android/app/build.gradle(.kts)` أضف `id("com.google.gms.google-services")` إلى `plugins`.
4. من إعدادات المشروع ← Service accounts ← «Generate new private key»، وضع الملف على الخادم في `C:\apw\secrets\fcm.json`
   (أو `secrets/fcm.json` على Linux) مع `APW_FCM_CREDENTIALS` في الإعدادات ثم أعد تشغيل الخادم.
5. إن لم يوجد `google-services.json` يتجاوز التطبيق Firebase بصمت ويبقى على الاستعلام الدوري.
ملاحظة: لم تُجرَّب إشعارات FCM فعلياً، فاختبرها على هاتف حقيقي.

## iPhone (لاحقاً)
الشيفرة مشتركة. يلزم جهاز Mac مع Xcode وحساب Apple Developer (99 دولاراً سنوياً) للتوقيع والتوزيع (TestFlight أو App Store الخاص)،
وإعداد APNs داخل Firebase للإشعارات. لم يُضبط ولم يُجرَّب شيء لـ iOS بعد.
