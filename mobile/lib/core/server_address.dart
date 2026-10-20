import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// يحوّل ما يكتبه المستخدم إلى عنوان خادم صالح، أو null إن لم يصلح.
///   192.168.1.5:8000      -> http://192.168.1.5:8000
///   http://mac.local:8000/ -> http://mac.local:8000
String? normalizeServerAddress(String input) {
  var s = input.trim();
  if (s.isEmpty) return null;
  if (!s.contains('://')) s = 'http://$s';
  final uri = Uri.tryParse(s);
  if (uri == null || (uri.scheme != 'http' && uri.scheme != 'https') || uri.host.isEmpty) {
    return null;
  }
  while (s.endsWith('/')) {
    s = s.substring(0, s.length - 1);
  }
  return s;
}

/// يحفظ عنوان الخادم المختار في نسخة العرض التجريبي فقط.
class ServerAddressStore {
  ServerAddressStore()
      : _s = const FlutterSecureStorage(
          aOptions: AndroidOptions(encryptedSharedPreferences: true),
        );

  final FlutterSecureStorage _s;
  static const _key = 'apw_demo_server_address';

  Future<String?> read() async {
    try {
      return await _s.read(key: _key);
    } catch (_) {
      return null;
    }
  }

  Future<void> write(String value) => _s.write(key: _key, value: value);
}
