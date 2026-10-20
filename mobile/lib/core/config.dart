import 'package:flutter/foundation.dart';

/// إعدادات تُحقن وقت البناء:
///   flutter build apk --release --dart-define=API_BASE_URL=https://example.com
class AppConfig {
  static const String apiBaseUrl =
      String.fromEnvironment('API_BASE_URL', defaultValue: 'http://10.0.2.2:8000');

  /// يلزم قفل شاشة/بصمة على الهاتف. عطّله للتطوير على المحاكي فقط:
  ///   --dart-define=REQUIRE_DEVICE_LOCK=false
  static const bool requireDeviceLock =
      bool.fromEnvironment('REQUIRE_DEVICE_LOCK', defaultValue: true);

  static const Duration autoLockAfter = Duration(minutes: 2);
  static const Duration pollInterval = Duration(seconds: 60);
  static const Duration requestTimeout = Duration(seconds: 25);

  /// في نسخة الإنتاج لا نقبل إلا HTTPS.
  static String? validate() {
    final url = apiBaseUrl.trim();
    if (url.isEmpty) return 'لم يُضبط عنوان الخادم (API_BASE_URL).';
    if (kReleaseMode && !url.startsWith('https://')) {
      return 'نسخة الإنتاج تتطلب عنوان خادم يبدأ بـ https://';
    }
    return null;
  }
}
