import 'dart:async';

import 'package:flutter/widgets.dart';

import 'core/api.dart';
import 'core/config.dart';
import 'core/storage.dart';
import 'data/repository.dart';
import 'state/controllers.dart';
import 'state/device_auth.dart';
import 'state/push.dart';
import 'state/session.dart';

/// حاوي الخدمات المشتركة (بلا مكتبات حقن خارجية).
class AppServices {
  AppServices._({
    required this.api,
    required this.repo,
    required this.session,
    required this.notifications,
    required this.questions,
    required this.photos,
    required this.push,
  });

  final ApiClient api;
  final Repository repo;
  final SessionController session;
  final NotificationsController notifications;
  final QuestionsController questions;
  final PhotoCache photos;
  final PushService push;

  Timer? _poller;

  factory AppServices.create({TokenStore? store, DeviceAuth? auth, String? baseUrl}) {
    final tokenStore = store ?? SecureTokenStore();
    final api = ApiClient(baseUrl: baseUrl ?? AppConfig.apiBaseUrl, store: tokenStore);
    final repo = Repository(api: api, store: tokenStore);
    final push = PushService();
    final session = SessionController(
      repo: repo,
      api: api,
      store: tokenStore,
      auth: auth ?? LocalDeviceAuth(),
    );
    final services = AppServices._(
      api: api,
      repo: repo,
      session: session,
      notifications: NotificationsController(repo),
      questions: QuestionsController(repo),
      photos: PhotoCache(repo),
      push: push,
    );
    api.fcmTokenProvider = () => push.token;
    session.fcmToken = () => push.token;
    session.onReady = services._start;
    session.onResume = services.refreshAll;
    session.onStop = services._stop;
    return services;
  }

  void refreshAll({bool silent = true}) {
    notifications.load(silent: silent);
    questions.load(silent: silent);
  }

  void _start() {
    refreshAll(silent: false);
    _poller?.cancel();
    _poller = Timer.periodic(AppConfig.pollInterval, (_) => refreshAll());
    push.start(
      onToken: (t) async {
        try {
          await repo.setFcmToken(t);
        } on ApiException {
          // يُعاد الإرسال مع أول تجديد للجلسة
        }
      },
      onMessage: refreshAll,
    );
  }

  void _stop(bool wipe) {
    _poller?.cancel();
    _poller = null;
    // المحتوى لا يبقى في الذاكرة بعد القفل أو الخروج
    notifications.clear();
    questions.clear();
    photos.clear();
    if (wipe) push.stop();
  }
}

class ServicesScope extends InheritedWidget {
  const ServicesScope({super.key, required this.services, required super.child});

  final AppServices services;

  static AppServices of(BuildContext context) {
    final scope = context.getInheritedWidgetOfExactType<ServicesScope>();
    assert(scope != null, 'ServicesScope غير موجود في الشجرة');
    return scope!.services;
  }

  @override
  bool updateShouldNotify(ServicesScope oldWidget) => services != oldWidget.services;
}
