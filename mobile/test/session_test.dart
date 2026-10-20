import 'dart:convert';

import 'package:apw_deputies/core/api.dart';
import 'package:apw_deputies/core/storage.dart';
import 'package:apw_deputies/data/repository.dart';
import 'package:apw_deputies/state/device_auth.dart';
import 'package:apw_deputies/state/session.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

http.Response jsonResponse(Object body, [int code = 200]) => http.Response.bytes(
      utf8.encode(jsonEncode(body)),
      code,
      headers: {'content-type': 'application/json; charset=utf-8'},
    );

const _profile = {
  'id': 1,
  'full_name': 'نائب تجريبي',
  'title': null,
  'has_photo': false,
  'committees': <String>[],
  'mandate_label': '2026-2031',
  'wilaya_name': 'ولاية الاختبار',
};

SessionController makeSession({
  required MockClient client,
  required TokenStore store,
  DeviceAuth? auth,
  bool requireLock = true,
}) {
  final api = ApiClient(baseUrl: 'https://x.test', store: store, client: client);
  final repo = Repository(api: api, store: store);
  return SessionController(
    repo: repo,
    api: api,
    store: store,
    auth: auth ?? FakeDeviceAuth(),
    requireLock: requireLock,
    platformName: 'android',
  );
}

MockClient happyServer() => MockClient((req) async {
      switch (req.url.path) {
        case '/public/info':
          return jsonResponse({'app_name': 'x', 'wilaya_name': 'ولاية الاختبار'});
        case '/auth/refresh':
          return jsonResponse({'access_token': 'at', 'refresh_token': 'rt-new', 'expires_in': 1800});
        case '/auth/activate':
          return jsonResponse({'access_token': 'at', 'refresh_token': 'rt-first', 'expires_in': 1800});
        case '/me/profile':
          return jsonResponse(_profile);
      }
      return jsonResponse({'detail': 'not found'}, 404);
    });

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('بلا جلسة محفوظة: شاشة التفعيل', () async {
    final s = makeSession(client: happyServer(), store: MemoryTokenStore());
    await s.boot();
    expect(s.state, SessionState.needsActivation);
    s.dispose();
  });

  test('جلسة محفوظة: قفل ثم فتح بالهوية يعطي الجاهزية ويدوّر الرمز', () async {
    final store = MemoryTokenStore(refreshToken: 'rt-old');
    final s = makeSession(client: happyServer(), store: store);
    await s.boot();
    expect(s.state, SessionState.locked);

    await s.unlock();

    expect(s.state, SessionState.ready);
    expect(s.profile?.fullName, 'نائب تجريبي');
    expect(store.refreshToken, 'rt-new');
    s.dispose();
  });

  test('فشل التحقق من الهوية يُبقي التطبيق مقفلاً', () async {
    final s = makeSession(
      client: happyServer(),
      store: MemoryTokenStore(refreshToken: 'rt-old'),
      auth: FakeDeviceAuth(result: false),
    );
    await s.boot();
    await s.unlock();
    expect(s.state, SessionState.locked);
    expect(s.error, isNotNull);
    expect(s.profile, isNull);
    s.dispose();
  });

  test('هاتف بلا قفل شاشة: يُحجب التطبيق', () async {
    final s = makeSession(
      client: happyServer(),
      store: MemoryTokenStore(refreshToken: 'rt-old'),
      auth: FakeDeviceAuth(available: false),
    );
    await s.boot();
    expect(s.state, SessionState.blocked);
    s.dispose();
  });

  test('جهاز مفصول (رفض التجديد): ينتقل إلى التفعيل برسالة', () async {
    final client = MockClient((req) async => jsonResponse({'detail': 'no'}, 401));
    final store = MemoryTokenStore(refreshToken: 'rt-dead');
    final s = makeSession(client: client, store: store);
    await s.boot();
    await s.unlock();
    expect(s.state, SessionState.needsActivation);
    expect(s.error, contains('فُصل'));
    expect(store.refreshToken, isNull);
    s.dispose();
  });

  test('التفعيل برمز الدعوة يحفظ الرمز ويفتح الجلسة', () async {
    final store = MemoryTokenStore();
    final s = makeSession(client: happyServer(), store: store);
    await s.boot();

    final ok = await s.activate('0550112233', 'ABCDE-FGHJK');

    expect(ok, isTrue);
    expect(s.state, SessionState.ready);
    expect(store.refreshToken, 'rt-first');
    s.dispose();
  });

  test('الخروج يمسح الجلسة ويعود إلى التفعيل', () async {
    final store = MemoryTokenStore(refreshToken: 'rt-old');
    final s = makeSession(client: happyServer(), store: store);
    await s.boot();
    await s.unlock();
    await s.logout();
    expect(s.state, SessionState.needsActivation);
    expect(store.refreshToken, isNull);
    expect(s.profile, isNull);
    s.dispose();
  });
}
