import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:http/http.dart' as http;

import 'config.dart';
import 'storage.dart';

class ApiException implements Exception {
  ApiException(this.status, this.message);

  /// 0 = فشل اتصال (لا استجابة من الخادم).
  final int status;
  final String message;

  bool get isNetwork => status == 0;

  @override
  String toString() => message;
}

class BinaryResponse {
  BinaryResponse(this.bytes, this.contentType);
  final Uint8List bytes;
  final String contentType;
}

/// عميل HTTP مع إدارة الجلسة:
///  - رمز الوصول في الذاكرة فقط، ورمز التحديث في التخزين الآمن.
///  - تجديد واحد في آن واحد (single-flight): الخادم يدوّر رمز التحديث،
///    فتجديدان متوازيان يُبطلان أحدهما.
///  - عند 401 يجدد مرة واحدة ثم يعيد الطلب.
class ApiClient {
  ApiClient({
    required String baseUrl,
    required this.store,
    http.Client? client,
    this.timeout = AppConfig.requestTimeout,
  })  : baseUrl = baseUrl.endsWith('/') ? baseUrl.substring(0, baseUrl.length - 1) : baseUrl,
        _http = client ?? http.Client();

  /// قابل للتغيير وقت التشغيل لنسخة العرض التجريبي فقط (انظر AppConfig.demoMode).
  String baseUrl;
  final TokenStore store;
  final Duration timeout;
  final http.Client _http;

  /// يُستدعى عندما يرفض الخادم رمز التحديث (جهاز مفصول، دورة منتهية...).
  void Function()? onSessionInvalid;

  /// رمز FCM الحالي ليُرسل مع التجديد إن وُجد.
  String? Function()? fcmTokenProvider;

  String? _access;
  DateTime? _accessExpiry;
  Future<void>? _refreshing;

  bool get hasAccessToken => _access != null;

  void clearAccess() {
    _access = null;
    _accessExpiry = null;
  }

  void _setAccess(String token, int expiresInSeconds) {
    _access = token;
    _accessExpiry = DateTime.now().add(Duration(seconds: expiresInSeconds));
  }

  /// يحفظ رموز الجلسة بعد التفعيل.
  Future<void> adoptTokens({
    required String accessToken,
    required String refreshToken,
    required int expiresIn,
  }) async {
    await store.writeRefreshToken(refreshToken);
    _setAccess(accessToken, expiresIn);
  }

  /// يفرض تجديد الجلسة الآن (عند فتح التطبيق).
  Future<void> refreshNow() => _refresh();

  Future<void> logoutRemote() async {
    final rt = await store.readRefreshToken();
    if (rt != null) {
      try {
        await _dispatch('POST', '/auth/logout', body: {'refresh_token': rt}, auth: false);
      } catch (_) {
        // لا يمنع الخروج المحلي
      }
    }
    await store.clearSession();
    clearAccess();
  }

  // ---------- واجهة عامة ----------
  Future<dynamic> getJson(String path, {bool auth = true}) async =>
      _decode(await _send('GET', path, auth: auth));

  Future<dynamic> postJson(String path, {Object? body, bool auth = true}) async =>
      _decode(await _send('POST', path, body: body, auth: auth));

  Future<dynamic> putJson(String path, Object body) async =>
      _decode(await _send('PUT', path, body: body));

  Future<BinaryResponse> getBytes(String path) async {
    final res = await _send('GET', path);
    return BinaryResponse(res.bodyBytes, res.headers['content-type'] ?? 'application/octet-stream');
  }

  // ---------- الداخل ----------
  dynamic _decode(http.Response res) {
    if (res.statusCode == 204 || res.bodyBytes.isEmpty) return null;
    return jsonDecode(utf8.decode(res.bodyBytes));
  }

  Future<http.Response> _send(
    String method,
    String path, {
    Object? body,
    bool auth = true,
    bool retried = false,
  }) async {
    if (auth) {
      final exp = _accessExpiry;
      if (_access == null || exp == null || DateTime.now().isAfter(exp.subtract(const Duration(seconds: 20)))) {
        await _refresh();
      }
    }
    final res = await _dispatch(method, path, body: body, auth: auth);
    if (res.statusCode == 401 && auth && !retried) {
      await _refresh();
      return _send(method, path, body: body, auth: auth, retried: true);
    }
    if (res.statusCode >= 400) throw _error(res);
    return res;
  }

  Future<http.Response> _dispatch(String method, String path, {Object? body, required bool auth}) async {
    final uri = Uri.parse('$baseUrl$path');
    final headers = <String, String>{'Accept': 'application/json'};
    List<int>? payload;
    if (body != null) {
      headers['Content-Type'] = 'application/json; charset=utf-8';
      payload = utf8.encode(jsonEncode(body));
    }
    if (auth && _access != null) headers['Authorization'] = 'Bearer $_access';
    try {
      final Future<http.Response> call;
      switch (method) {
        case 'GET':
          call = _http.get(uri, headers: headers);
        case 'POST':
          call = _http.post(uri, headers: headers, body: payload);
        case 'PUT':
          call = _http.put(uri, headers: headers, body: payload);
        default:
          throw ArgumentError('طريقة غير مدعومة: $method');
      }
      return await call.timeout(timeout);
    } on TimeoutException {
      throw ApiException(0, 'انتهت مهلة الاتصال بالخادم');
    } on ArgumentError {
      rethrow;
    } catch (_) {
      throw ApiException(0, 'تعذّر الاتصال بالخادم. تحقق من الإنترنت.');
    }
  }

  Future<void> _refresh() {
    return _refreshing ??= _doRefresh().whenComplete(() => _refreshing = null);
  }

  Future<void> _doRefresh() async {
    final rt = await store.readRefreshToken();
    if (rt == null) {
      await _invalidate();
      throw ApiException(401, 'لا توجد جلسة. فعّل التطبيق برمز الدعوة.');
    }
    final payload = <String, dynamic>{
      'refresh_token': rt,
      'device_uid': await store.deviceUid(),
    };
    final fcm = fcmTokenProvider?.call();
    if (fcm != null) payload['fcm_token'] = fcm;

    final res = await _dispatch('POST', '/auth/refresh', body: payload, auth: false);
    if (res.statusCode == 401) {
      await _invalidate();
      throw ApiException(401, 'انتهت الجلسة أو فُصل الجهاز. فعّل التطبيق من جديد.');
    }
    if (res.statusCode >= 400) throw _error(res);
    final data = _decode(res) as Map<String, dynamic>;
    await store.writeRefreshToken(data['refresh_token'] as String);
    _setAccess(data['access_token'] as String, (data['expires_in'] as num).toInt());
  }

  Future<void> _invalidate() async {
    clearAccess();
    await store.clearSession();
    onSessionInvalid?.call();
  }

  ApiException _error(http.Response res) {
    var message = res.statusCode >= 500 ? 'خطأ داخلي في الخادم' : 'تعذّر تنفيذ العملية';
    try {
      final data = jsonDecode(utf8.decode(res.bodyBytes));
      if (data is Map) {
        final d = data['detail'];
        if (d is String) {
          message = d;
        } else if (d is List) {
          message = 'بيانات غير صالحة، راجع الحقول المدخلة';
        }
      }
    } catch (_) {
      // جسم غير JSON
    }
    return ApiException(res.statusCode, message);
  }
}
