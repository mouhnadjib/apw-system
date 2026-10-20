import 'package:apw_deputies/models/models.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('Profile.fromJson', () {
    final p = Profile.fromJson({
      'id': 7,
      'full_name': 'بن عيسى عبد القادر',
      'title': null,
      'has_photo': true,
      'committees': ['لجنة المالية'],
      'mandate_label': '2026-2031',
      'wilaya_name': null,
    });
    expect(p.id, 7);
    expect(p.title, isNull);
    expect(p.committees, ['لجنة المالية']);
    expect(p.wilayaName, isNull);
  });

  test('PublicInfo: اسم الولاية اختياري ويُهمل الفارغ', () {
    expect(PublicInfo.fromJson({'wilaya_name': null}).wilayaName, isNull);
    expect(PublicInfo.fromJson({'wilaya_name': '   '}).wilayaName, isNull);
    expect(PublicInfo.fromJson({'wilaya_name': ' ولاية الجلفة '}).wilayaName, 'ولاية الجلفة');
  });

  test('AppNotification.fromJson و copyWith', () {
    final n = AppNotification.fromJson({
      'id': 1,
      'kind': 'meeting',
      'title': 'اجتماع',
      'body': 'نص',
      'meeting_at': '2026-11-01T09:00:00Z',
      'created_at': '2026-10-18T12:00:00Z',
      'read': false,
    });
    expect(n.kind, NotifKind.meeting);
    expect(n.meetingAt!.toUtc(), DateTime.utc(2026, 11, 1, 9));
    expect(n.copyWith(read: true).read, isTrue);
    expect(n.read, isFalse);
  });

  test('QuestionDetail.fromJson بأحداثه', () {
    final q = QuestionDetail.fromJson({
      'id': 3,
      'subject': 'موضوع',
      'text': 'نص السؤال الطويل',
      'status': 'returned',
      'return_note': 'حدّد الطريق',
      'has_reply': false,
      'created_at': '2026-10-18T10:00:00Z',
      'updated_at': '2026-10-18T11:00:00Z',
      'events': [
        {'status': 'submitted', 'note': null, 'created_at': '2026-10-18T10:00:00Z'},
        {'status': 'returned', 'note': 'حدّد الطريق', 'created_at': '2026-10-18T11:00:00Z'},
      ],
    });
    expect(q.status, QStatus.returned);
    expect(q.events.length, 2);
    expect(q.events.last.note, 'حدّد الطريق');
  });
}
