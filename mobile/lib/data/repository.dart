import 'dart:typed_data';

import '../core/api.dart';
import '../core/storage.dart';
import '../models/models.dart';

/// واجهة مطبوعة (typed) فوق ApiClient.
class Repository {
  Repository({required this.api, required this.store});

  final ApiClient api;
  final TokenStore store;

  List<Map<String, dynamic>> _list(dynamic data) => (data as List).cast<Map<String, dynamic>>();

  Future<PublicInfo> publicInfo() async =>
      PublicInfo.fromJson(await api.getJson('/public/info', auth: false) as Map<String, dynamic>);

  /// تفعيل الحساب برمز الدعوة وربط هذا الجهاز.
  Future<void> activate({
    required String phone,
    required String code,
    required String platform,
    String? fcmToken,
  }) async {
    final data = await api.postJson(
      '/auth/activate',
      auth: false,
      body: {
        'phone': phone,
        'code': code,
        'device_uid': await store.deviceUid(),
        'platform': platform,
        if (fcmToken != null) 'fcm_token': fcmToken,
      },
    ) as Map<String, dynamic>;
    await api.adoptTokens(
      accessToken: data['access_token'] as String,
      refreshToken: data['refresh_token'] as String,
      expiresIn: (data['expires_in'] as num).toInt(),
    );
  }

  Future<Profile> profile() async =>
      Profile.fromJson(await api.getJson('/me/profile') as Map<String, dynamic>);

  Future<void> setFcmToken(String? token) async {
    await api.postJson('/me/fcm-token', body: {'fcm_token': token});
  }

  // ---------- الإشعارات ----------
  Future<List<AppNotification>> notifications() async =>
      _list(await api.getJson('/me/notifications?limit=200')).map(AppNotification.fromJson).toList();

  Future<void> markNotificationRead(int id) async {
    await api.postJson('/me/notifications/$id/read');
  }

  // ---------- الأسئلة ----------
  Future<List<QuestionRow>> questions() async =>
      _list(await api.getJson('/me/questions')).map(QuestionRow.fromJson).toList();

  Future<QuestionDetail> question(int id) async =>
      QuestionDetail.fromJson(await api.getJson('/me/questions/$id') as Map<String, dynamic>);

  Future<QuestionDetail> createQuestion({required String subject, required String text}) async =>
      QuestionDetail.fromJson(
        await api.postJson('/me/questions', body: {'subject': subject, 'text': text}) as Map<String, dynamic>,
      );

  Future<QuestionDetail> editQuestion(int id, {required String subject, required String text}) async =>
      QuestionDetail.fromJson(
        await api.putJson('/me/questions/$id', {'subject': subject, 'text': text}) as Map<String, dynamic>,
      );

  Future<BinaryResponse> questionReply(int id) => api.getBytes('/me/questions/$id/reply');

  // ---------- النواب ----------
  Future<List<DeputyPublic>> deputies() async =>
      _list(await api.getJson('/me/deputies')).map(DeputyPublic.fromJson).toList();

  Future<Uint8List> deputyPhoto(int id) async => (await api.getBytes('/me/deputies/$id/photo')).bytes;
}
