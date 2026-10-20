import 'package:apw_deputies/core/format.dart';
import 'package:apw_deputies/models/models.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('parseServerDate', () {
    test('القيمة بلا منطقة زمنية تُعتبر UTC', () {
      expect(parseServerDate('2026-10-18T12:00:00').toUtc(), DateTime.utc(2026, 10, 18, 12));
    });

    test('يحترم Z والإزاحة والكسور', () {
      expect(parseServerDate('2026-10-18T12:00:00Z').toUtc(), DateTime.utc(2026, 10, 18, 12));
      expect(parseServerDate('2026-10-18T13:00:00+01:00').toUtc(), DateTime.utc(2026, 10, 18, 12));
      expect(parseServerDate('2026-10-18T12:00:00.123456+00:00').toUtc().hour, 12);
    });
  });

  group('normalizeArabic', () {
    test('يوحّد الهمزات والياء والتاء المربوطة ويزيل التشكيل', () {
      expect(normalizeArabic('إبراهيم'), normalizeArabic('ابراهيم'));
      expect(normalizeArabic('مَدرَسة'), normalizeArabic('مدرسه'));
      expect(normalizeArabic('على'), normalizeArabic('علي'));
    });

    test('يتجاهل الفراغات الطرفية وحالة الأحرف اللاتينية', () {
      expect(normalizeArabic('  Ahmed '), 'ahmed');
    });
  });

  group('formatRelative', () {
    final now = DateTime(2026, 10, 18, 12, 0);
    test('الآن ودقائق وساعات وأيام', () {
      expect(formatRelative(now, now: now), 'الآن');
      expect(formatRelative(now.subtract(const Duration(minutes: 5)), now: now), 'قبل 5 دقيقة');
      expect(formatRelative(now.subtract(const Duration(hours: 3)), now: now), 'قبل 3 ساعة');
      expect(formatRelative(now.subtract(const Duration(days: 2)), now: now), 'قبل 2 يوم');
    });
  });

  group('QStatus', () {
    test('parse يعيد الحالة الصحيحة ويتسامح مع المجهول', () {
      expect(QStatus.parse('under_review'), QStatus.underReview);
      expect(QStatus.parse('answered'), QStatus.answered);
      expect(QStatus.parse('???'), QStatus.submitted);
    });

    test('مراحل شريط التقدم', () {
      expect(QStatus.submitted.step, 0);
      expect(QStatus.underReview.step, 1);
      expect(QStatus.returned.step, 1);
      expect(QStatus.confirmed.step, 2);
      expect(QStatus.referred.step, 3);
      expect(QStatus.answered.step, 4);
    });
  });
}
