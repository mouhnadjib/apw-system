import 'package:flutter/material.dart';
import 'package:apw_deputies/app.dart';
import 'package:apw_deputies/core/storage.dart';
import 'package:apw_deputies/services.dart';
import 'package:apw_deputies/state/device_auth.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('شاشة التفعيل تتحقق من الحقول قبل الإرسال', (tester) async {
    final services = AppServices.create(store: MemoryTokenStore(), auth: FakeDeviceAuth());
    await tester.pumpWidget(ApwApp(services: services));
    await services.session.boot();
    await tester.pumpAndSettle();

    expect(find.text('تفعيل الحساب'), findsOneWidget);

    await tester.enterText(find.byType(TextFormField).first, '123');
    await tester.tap(find.text('تفعيل').last);
    await tester.pump();

    expect(find.text('رقم هاتف غير صالح'), findsOneWidget);
    expect(find.text('رمز الدعوة غير مكتمل'), findsOneWidget);
  });
}
