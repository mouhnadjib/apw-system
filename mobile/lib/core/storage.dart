import 'dart:math';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// تخزين رمز التحديث ومعرّف الجهاز. التنفيذ الحقيقي يستعمل Keystore/Keychain.
abstract class TokenStore {
  Future<String?> readRefreshToken();
  Future<void> writeRefreshToken(String value);

  /// يمسح الجلسة (رمز التحديث) ويُبقي معرّف الجهاز.
  Future<void> clearSession();

  /// معرّف عشوائي ثابت للجهاز، يُنشأ عند أول طلب.
  Future<String> deviceUid();
}

String generateDeviceUid([Random? random]) {
  final r = random ?? Random.secure();
  final bytes = List<int>.generate(16, (_) => r.nextInt(256));
  return bytes.map((b) => b.toRadixString(16).padLeft(2, '0')).join();
}

class SecureTokenStore implements TokenStore {
  SecureTokenStore()
      : _s = const FlutterSecureStorage(
          aOptions: AndroidOptions(encryptedSharedPreferences: true),
        );

  final FlutterSecureStorage _s;
  static const _kRefresh = 'apw_refresh_token';
  static const _kUid = 'apw_device_uid';

  @override
  Future<String?> readRefreshToken() => _s.read(key: _kRefresh);

  @override
  Future<void> writeRefreshToken(String value) => _s.write(key: _kRefresh, value: value);

  @override
  Future<void> clearSession() => _s.delete(key: _kRefresh);

  @override
  Future<String> deviceUid() async {
    final existing = await _s.read(key: _kUid);
    if (existing != null && existing.length >= 8) return existing;
    final created = generateDeviceUid();
    await _s.write(key: _kUid, value: created);
    return created;
  }
}

/// للاختبارات.
class MemoryTokenStore implements TokenStore {
  MemoryTokenStore({String? refreshToken, String uid = 'test-device-uid-0001'})
      : _refresh = refreshToken,
        _uid = uid;

  String? _refresh;
  final String _uid;

  String? get refreshToken => _refresh;

  @override
  Future<String?> readRefreshToken() async => _refresh;

  @override
  Future<void> writeRefreshToken(String value) async => _refresh = value;

  @override
  Future<void> clearSession() async => _refresh = null;

  @override
  Future<String> deviceUid() async => _uid;
}
