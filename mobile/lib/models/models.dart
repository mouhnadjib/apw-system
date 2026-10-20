import '../core/format.dart';

enum QStatus {
  submitted('submitted', 'مُرسل'),
  underReview('under_review', 'قيد المراجعة'),
  returned('returned', 'أُعيد إليك للتعديل'),
  confirmed('confirmed', 'مؤكَّد'),
  referred('referred', 'أُحيل إلى الوالي'),
  answered('answered', 'تم الرد');

  const QStatus(this.code, this.label);
  final String code;
  final String label;

  static QStatus parse(String code) =>
      QStatus.values.firstWhere((s) => s.code == code, orElse: () => QStatus.submitted);

  /// موضع الحالة في شريط التقدم (0..4).
  int get step => switch (this) {
        QStatus.submitted => 0,
        QStatus.underReview => 1,
        QStatus.returned => 1,
        QStatus.confirmed => 2,
        QStatus.referred => 3,
        QStatus.answered => 4,
      };
}

enum NotifKind {
  meeting('meeting', 'دعوة اجتماع'),
  targeted('targeted', 'دعوة مخصصة'),
  info('info', 'معلومة مهمة');

  const NotifKind(this.code, this.label);
  final String code;
  final String label;

  static NotifKind parse(String code) =>
      NotifKind.values.firstWhere((k) => k.code == code, orElse: () => NotifKind.info);
}

class PublicInfo {
  PublicInfo({this.wilayaName});
  final String? wilayaName;

  factory PublicInfo.fromJson(Map<String, dynamic> j) {
    final raw = (j['wilaya_name'] as String?)?.trim();
    return PublicInfo(wilayaName: (raw == null || raw.isEmpty) ? null : raw);
  }
}

class Profile {
  Profile({
    required this.id,
    required this.fullName,
    this.title,
    required this.hasPhoto,
    required this.committees,
    required this.mandateLabel,
    this.wilayaName,
  });

  final int id;
  final String fullName;
  final String? title;
  final bool hasPhoto;
  final List<String> committees;
  final String mandateLabel;
  final String? wilayaName;

  factory Profile.fromJson(Map<String, dynamic> j) => Profile(
        id: j['id'] as int,
        fullName: j['full_name'] as String,
        title: j['title'] as String?,
        hasPhoto: j['has_photo'] as bool,
        committees: (j['committees'] as List).cast<String>(),
        mandateLabel: j['mandate_label'] as String,
        wilayaName: j['wilaya_name'] as String?,
      );
}

class DeputyPublic {
  DeputyPublic({
    required this.id,
    required this.fullName,
    this.title,
    required this.hasPhoto,
    required this.committees,
  });

  final int id;
  final String fullName;
  final String? title;
  final bool hasPhoto;
  final List<String> committees;

  factory DeputyPublic.fromJson(Map<String, dynamic> j) => DeputyPublic(
        id: j['id'] as int,
        fullName: j['full_name'] as String,
        title: j['title'] as String?,
        hasPhoto: j['has_photo'] as bool,
        committees: (j['committees'] as List).cast<String>(),
      );
}

class AppNotification {
  AppNotification({
    required this.id,
    required this.kind,
    required this.title,
    required this.body,
    this.meetingAt,
    required this.createdAt,
    required this.read,
  });

  final int id;
  final NotifKind kind;
  final String title;
  final String body;
  final DateTime? meetingAt;
  final DateTime createdAt;
  final bool read;

  AppNotification copyWith({bool? read}) => AppNotification(
        id: id,
        kind: kind,
        title: title,
        body: body,
        meetingAt: meetingAt,
        createdAt: createdAt,
        read: read ?? this.read,
      );

  factory AppNotification.fromJson(Map<String, dynamic> j) => AppNotification(
        id: j['id'] as int,
        kind: NotifKind.parse(j['kind'] as String),
        title: j['title'] as String,
        body: j['body'] as String,
        meetingAt: j['meeting_at'] == null ? null : parseServerDate(j['meeting_at'] as String),
        createdAt: parseServerDate(j['created_at'] as String),
        read: j['read'] as bool,
      );
}

class QuestionRow {
  QuestionRow({
    required this.id,
    required this.subject,
    required this.status,
    required this.createdAt,
    required this.updatedAt,
  });

  final int id;
  final String subject;
  final QStatus status;
  final DateTime createdAt;
  final DateTime updatedAt;

  factory QuestionRow.fromJson(Map<String, dynamic> j) => QuestionRow(
        id: j['id'] as int,
        subject: j['subject'] as String,
        status: QStatus.parse(j['status'] as String),
        createdAt: parseServerDate(j['created_at'] as String),
        updatedAt: parseServerDate(j['updated_at'] as String),
      );
}

class QuestionEvent {
  QuestionEvent({required this.status, this.note, required this.createdAt});

  final QStatus status;
  final String? note;
  final DateTime createdAt;

  factory QuestionEvent.fromJson(Map<String, dynamic> j) => QuestionEvent(
        status: QStatus.parse(j['status'] as String),
        note: j['note'] as String?,
        createdAt: parseServerDate(j['created_at'] as String),
      );
}

class QuestionDetail {
  QuestionDetail({
    required this.id,
    required this.subject,
    required this.text,
    required this.status,
    this.returnNote,
    required this.hasReply,
    required this.createdAt,
    required this.updatedAt,
    required this.events,
  });

  final int id;
  final String subject;
  final String text;
  final QStatus status;
  final String? returnNote;
  final bool hasReply;
  final DateTime createdAt;
  final DateTime updatedAt;
  final List<QuestionEvent> events;

  factory QuestionDetail.fromJson(Map<String, dynamic> j) => QuestionDetail(
        id: j['id'] as int,
        subject: j['subject'] as String,
        text: j['text'] as String,
        status: QStatus.parse(j['status'] as String),
        returnNote: j['return_note'] as String?,
        hasReply: j['has_reply'] as bool,
        createdAt: parseServerDate(j['created_at'] as String),
        updatedAt: parseServerDate(j['updated_at'] as String),
        events: (j['events'] as List)
            .map((e) => QuestionEvent.fromJson(e as Map<String, dynamic>))
            .toList(),
      );
}
