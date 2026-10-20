import 'dart:async';

import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';

/// إشعارات FCM اختيارية: إن لم يُضبط Firebase يعمل التطبيق بالاستطلاع الدوري.
/// الإشعار نفسه عام لا يحمل محتوى؛ يجلب التطبيق التفاصيل من الخادم بعد المصادقة.
class PushService {
  String? token;
  final List<StreamSubscription<dynamic>> _subs = [];
  bool _started = false;

  Future<void> start({
    required Future<void> Function(String token) onToken,
    required VoidCallback onMessage,
  }) async {
    if (_started) return;
    _started = true;
    try {
      if (Firebase.apps.isEmpty) await Firebase.initializeApp();
      final messaging = FirebaseMessaging.instance;
      await messaging.requestPermission();
      final t = await messaging.getToken();
      if (t != null) {
        token = t;
        await onToken(t);
      }
      _subs.add(messaging.onTokenRefresh.listen((t) {
        token = t;
        onToken(t);
      }));
      _subs.add(FirebaseMessaging.onMessage.listen((_) => onMessage()));
      _subs.add(FirebaseMessaging.onMessageOpenedApp.listen((_) => onMessage()));
    } catch (e) {
      debugPrint('FCM غير مفعّل: $e');
    }
  }

  Future<void> stop() async {
    for (final s in _subs) {
      await s.cancel();
    }
    _subs.clear();
    token = null;
    _started = false;
  }
}
