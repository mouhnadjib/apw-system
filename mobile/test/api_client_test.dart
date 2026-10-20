import 'dart:convert';

import 'package:apw_deputies/core/api.dart';
import 'package:apw_deputies/core/storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

http.Response jsonResponse(Object body, [int code = 200]) => http.Response.bytes(
      utf8.encode(jsonEncode(body)),
      code,
      headers: {'content-type': 'application/json; charset=utf-8'},
    );

void main() {
  test('يجدد الجلسة عند 401 ويعيد الطلب مرة واحدة', () async {
    final store = MemoryTokenStore(refreshToken: 'rt-1');
    var refreshCalls = 0;
    var dataCalls = 0;
    final client = MockClient((req) async {
      if (req.url.path == '/auth/refresh') {
        refreshCalls++;
        return jsonResponse({
          'access_token': 'at-$refreshCalls',
          'refresh_token': 'rt-${refreshCalls + 1}',
          'expires_in': 1800,
        });
      }
      dataCalls++;
      // يقبل الرمز الثاني فقط، ليُجبر على 401 ثم التجديد
      if (req.headers['Authorization'] != 'Bearer at-2') return jsonResponse({'detail': 'x'}, 401);
      return jsonResponse({'ok': true});
    });
    final api = ApiClient(baseUrl: 'https://x.test', store: store, client: client);

    final r = await api.getJson('/me/questions') as Map<String, dynamic>;

    expect(r['ok'], true);
    expect(refreshCalls, 2);
    expect(dataCalls, 2);
    expect(store.refreshToken, 'rt-3');
  });

  test('طلبان متوازيان يشتركان في تجديد واحد (الخادم يدوّر الرمز)', () async {
    final store = MemoryTokenStore(refreshToken: 'rt-1');
    var refreshCalls = 0;
    final client = MockClient((req) async {
      if (req.url.path == '/auth/refresh') {
        refreshCalls++;
        return jsonResponse({'access_token': 'at-1', 'refresh_token': 'rt-2', 'expires_in': 1800});
      }
      return jsonResponse({'path': req.url.path});
    });
    final api = ApiClient(baseUrl: 'https://x.test', store: store, client: client);

    final results = await Future.wait([api.getJson('/a'), api.getJson('/b')]);

    expect(refreshCalls, 1);
    expect((results[0] as Map)['path'], '/a');
    expect((results[1] as Map)['path'], '/b');
  });

  test('رفض التجديد بـ 401 يمسح الجلسة وينبّه', () async {
    final store = MemoryTokenStore(refreshToken: 'rt-dead');
    final client = MockClient((req) async => jsonResponse({'detail': 'no'}, 401));
    final api = ApiClient(baseUrl: 'https://x.test', store: store, client: client);
    var invalidated = false;
    api.onSessionInvalid = () => invalidated = true;

    await expectLater(api.getJson('/me/profile'), throwsA(isA<ApiException>()));

    expect(invalidated, isTrue);
    expect(await store.readRefreshToken(), isNull);
  });

  test('فشل الشبكة يُترجم إلى ApiException بحالة 0 ولا يمسح الجلسة', () async {
    final store = MemoryTokenStore(refreshToken: 'rt-1');
    final client = MockClient((req) async => throw http.ClientException('no route'));
    final api = ApiClient(baseUrl: 'https://x.test', store: store, client: client);

    try {
      await api.getJson('/me/profile');
      fail('كان يجب أن يرمي');
    } on ApiException catch (e) {
      expect(e.isNetwork, isTrue);
    }
    expect(await store.readRefreshToken(), 'rt-1');
  });

  test('يستخرج رسالة الخطأ العربية من detail', () async {
    final store = MemoryTokenStore();
    final client = MockClient((req) async => jsonResponse({'detail': 'بيانات التفعيل غير صحيحة أو منتهية'}, 400));
    final api = ApiClient(baseUrl: 'https://x.test/', store: store, client: client); // شرطة نهائية تُزال

    try {
      await api.postJson('/auth/activate', auth: false, body: {'x': 1});
      fail('كان يجب أن يرمي');
    } on ApiException catch (e) {
      expect(e.status, 400);
      expect(e.message, 'بيانات التفعيل غير صحيحة أو منتهية');
    }
  });

  test('generateDeviceUid: 32 خانة سداسية وعشوائي', () {
    final a = generateDeviceUid();
    final b = generateDeviceUid();
    expect(a, matches(RegExp(r'^[0-9a-f]{32}$')));
    expect(a, isNot(b));
  });
}
