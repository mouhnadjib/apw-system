import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';

import '../core/api.dart';
import '../core/config.dart';
import '../core/storage.dart';
import '../data/repository.dart';
import '../models/models.dart';
import 'device_auth.dart';

enum SessionState { booting, needsActivation, locked, ready, blocked }

/// حالة الجلسة: تفعيل ← قفل ← جاهز. يقفل التطبيق تلقائياً بعد غياب قصير.
class SessionController extends ChangeNotifier with WidgetsBindingObserver {
  SessionController({
    required this.repo,
    required this.api,
    required this.store,
    required this.auth,
    this.requireLock = AppConfig.requireDeviceLock,
    this.autoLockAfter = AppConfig.autoLockAfter,
    this.platformName,
  });

  final Repository repo;
  final ApiClient api;
  final TokenStore store;
  final DeviceAuth auth;
  final bool requireLock;
  final Duration autoLockAfter;
  final String? platformName;

  SessionState state = SessionState.booting;
  Profile? profile;
  String? wilayaName;
  String? error;
  bool busy = false;

  /// تُستدعى عند الجاهزية (لبدء الاستطلاع وFCM).
  VoidCallback? onReady;

  /// تُستدعى عند القفل أو الخروج؛ wipe=true يعني مسح البيانات المخزّنة مؤقتاً.
  void Function(bool wipe)? onStop;

  /// عند العودة للتطبيق قبل انتهاء مهلة القفل.
  VoidCallback? onResume;

  /// يُضبط من PushService ليُرسل رمز FCM مع التفعيل.
  String? Function()? fcmToken;

  DateTime? _pausedAt;
  bool _authenticating = false;
  bool _observing = false;

  String get _platform =>
      platformName ?? (defaultTargetPlatform == TargetPlatform.iOS ? 'ios' : 'android');

  Future<void> boot() async {
    if (!_observing) {
      WidgetsBinding.instance.addObserver(this);
      _observing = true;
    }
    api.onSessionInvalid = _handleInvalid;
    _loadPublicInfo();
    error = null;
    final rt = await store.readRefreshToken();
    if (rt == null) {
      _set(SessionState.needsActivation);
      return;
    }
    if (requireLock && !await auth.isAvailable()) {
      error = 'لحماية بيانات المجلس يلزم تفعيل قفل الشاشة (PIN أو بصمة) في إعدادات الهاتف.';
      _set(SessionState.blocked);
      return;
    }
    _set(SessionState.locked);
  }

  Future<void> _loadPublicInfo() async {
    try {
      wilayaName = (await repo.publicInfo()).wilayaName;
      notifyListeners();
    } catch (_) {
      // اسم الولاية اختياري؛ لا نعطّل الشاشة إن تعذّر
    }
  }

  Future<bool> activate(String phone, String code) async {
    if (busy) return false;
    busy = true;
    error = null;
    notifyListeners();
    try {
      if (requireLock && !await auth.isAvailable()) {
        error = 'فعّل قفل الشاشة (PIN أو بصمة) في إعدادات الهاتف ثم أعد المحاولة.';
        return false;
      }
      await repo.activate(phone: phone, code: code, platform: _platform, fcmToken: fcmToken?.call());
      profile = await repo.profile();
      wilayaName = profile?.wilayaName ?? wilayaName;
      state = SessionState.ready;
      onReady?.call();
      return true;
    } on ApiException catch (e) {
      error = e.message;
      return false;
    } finally {
      busy = false;
      notifyListeners();
    }
  }

  Future<void> unlock() async {
    if (busy) return;
    busy = true;
    error = null;
    notifyListeners();
    try {
      if (requireLock) {
        _authenticating = true;
        final ok = await auth.authenticate('أكّد هويتك لفتح التطبيق');
        _authenticating = false;
        if (!ok) {
          error = 'لم يتم التحقق من الهوية. حاول مجدداً.';
          return;
        }
      }
      await api.refreshNow();
      profile = await repo.profile();
      wilayaName = profile?.wilayaName ?? wilayaName;
      state = SessionState.ready;
      onReady?.call();
    } on ApiException catch (e) {
      // إن أُبطلت الجلسة فقد انتقلنا إلى التفعيل وبقيت رسالته
      if (state != SessionState.needsActivation) error = e.message;
    } finally {
      _authenticating = false;
      busy = false;
      notifyListeners();
    }
  }

  void lock() {
    if (state != SessionState.ready) return;
    api.clearAccess();
    onStop?.call(true);
    _set(SessionState.locked);
  }

  Future<void> logout() async {
    await api.logoutRemote();
    _reset('تم تسجيل الخروج. أدخل رمز دعوة جديداً للتفعيل.');
  }

  void _handleInvalid() => _reset('انتهت الجلسة أو فُصل هذا الجهاز. اطلب رمز دعوة جديداً من ديوان المجلس.');

  void _reset(String message) {
    profile = null;
    error = message;
    onStop?.call(true);
    _set(SessionState.needsActivation);
  }

  void _set(SessionState s) {
    state = s;
    notifyListeners();
  }

  @override
  // ignore: avoid_renaming_method_parameters
  void didChangeAppLifecycleState(AppLifecycleState lifecycle) {
    if (state != SessionState.ready || _authenticating) return;
    if (lifecycle == AppLifecycleState.paused || lifecycle == AppLifecycleState.hidden) {
      _pausedAt ??= DateTime.now();
    } else if (lifecycle == AppLifecycleState.resumed) {
      final at = _pausedAt;
      _pausedAt = null;
      if (at != null && DateTime.now().difference(at) > autoLockAfter) {
        lock();
      } else if (at != null) {
        onResume?.call();
      }
    }
  }

  @override
  void dispose() {
    if (_observing) WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }
}
