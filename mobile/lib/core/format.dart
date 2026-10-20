import 'package:intl/date_symbol_data_local.dart';
import 'package:intl/intl.dart';

/// 'ar_DZ' يعطي أرقاماً لاتينية (الشائعة في الجزائر)، مع رجوع إلى 'ar'.
String dateLocale = 'ar';

Future<void> initDateFormatting() async {
  try {
    await initializeDateFormatting('ar_DZ');
    dateLocale = 'ar_DZ';
  } catch (_) {
    await initializeDateFormatting('ar');
    dateLocale = 'ar';
  }
}

/// الخادم يُرجع UTC؛ قد يصل بلا لاحقة منطقة زمنية فنعتبره UTC.
DateTime parseServerDate(String s) {
  final hasZone = RegExp(r'(Z|[+-]\d\d:?\d\d)$').hasMatch(s);
  return DateTime.parse(hasZone ? s : '${s}Z').toLocal();
}

String formatDateTime(DateTime d) => DateFormat('d MMMM y، HH:mm', dateLocale).format(d);

String formatDate(DateTime d) => DateFormat('d MMMM y', dateLocale).format(d);

/// "قبل 5 دقائق" للقيم القريبة، وإلا التاريخ الكامل.
String formatRelative(DateTime d, {DateTime? now}) {
  final diff = (now ?? DateTime.now()).difference(d);
  if (diff.inMinutes < 1) return 'الآن';
  if (diff.inMinutes < 60) return 'قبل ${diff.inMinutes} دقيقة';
  if (diff.inHours < 24) return 'قبل ${diff.inHours} ساعة';
  if (diff.inDays < 7) return 'قبل ${diff.inDays} يوم';
  return formatDate(d);
}

/// توحيد النص العربي للبحث: بلا تشكيل ولا تطويل، وتوحيد الألف والياء والتاء المربوطة.
String normalizeArabic(String input) {
  var s = input.trim().toLowerCase();
  s = s.replaceAll(RegExp('[ً-ٰٟـ]'), '');
  s = s
      .replaceAll(RegExp('[آأإ]'), 'ا')
      .replaceAll('ى', 'ي')
      .replaceAll('ة', 'ه');
  return s;
}
