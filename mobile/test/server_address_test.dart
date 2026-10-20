import 'package:apw_deputies/core/server_address.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('يضيف http ويزيل الشرطة النهائية', () {
    expect(normalizeServerAddress('192.168.1.5:8000'), 'http://192.168.1.5:8000');
    expect(normalizeServerAddress(' http://mac.local:8000/ '), 'http://mac.local:8000');
    expect(normalizeServerAddress('https://x.example.com'), 'https://x.example.com');
  });

  test('يرفض المدخلات الفارغة وغير الصالحة', () {
    expect(normalizeServerAddress(''), isNull);
    expect(normalizeServerAddress('   '), isNull);
    expect(normalizeServerAddress('ftp://x.test'), isNull);
    expect(normalizeServerAddress('http://'), isNull);
  });
}
