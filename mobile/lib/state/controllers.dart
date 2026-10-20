import 'dart:async';
import 'dart:typed_data';

import 'package:flutter/foundation.dart';

import '../core/api.dart';
import '../data/repository.dart';
import '../models/models.dart';

/// نمط مشترك: قائمة تُحمَّل من الخادم مع حالة تحميل وخطأ، وتحديث صامت.
abstract class ListController<T> extends ChangeNotifier {
  List<T> items = <T>[];
  bool loading = false;
  String? error;
  bool _loadedOnce = false;
  bool get loadedOnce => _loadedOnce;
  int _generation = 0; // يُبطل الطلبات المتأخرة بعد clear()

  Future<List<T>> fetch();

  Future<void> load({bool silent = false}) async {
    if (loading) return;
    final gen = _generation;
    loading = true;
    if (!silent) error = null;
    notifyListeners();
    try {
      final result = await fetch();
      if (gen != _generation) return; // مُسحت القائمة أثناء الجلب (قفل/خروج)
      items = result;
      error = null;
      _loadedOnce = true;
    } on ApiException catch (e) {
      if (gen != _generation) return;
      // التحديث الصامت لا يُظهر خطأ إن كانت لدينا بيانات
      if (!silent || items.isEmpty) error = e.message;
    } finally {
      if (gen == _generation) {
        loading = false;
        notifyListeners();
      }
    }
  }

  void clear() {
    _generation++;
    items = <T>[];
    error = null;
    loading = false;
    _loadedOnce = false;
    notifyListeners();
  }
}

class NotificationsController extends ListController<AppNotification> {
  NotificationsController(this.repo);
  final Repository repo;

  int get unread => items.where((n) => !n.read).length;

  @override
  Future<List<AppNotification>> fetch() => repo.notifications();

  /// تحديث متفائل ثم إبلاغ الخادم.
  Future<void> markRead(AppNotification n) async {
    if (n.read) return;
    items = [for (final x in items) x.id == n.id ? x.copyWith(read: true) : x];
    notifyListeners();
    try {
      await repo.markNotificationRead(n.id);
    } on ApiException {
      // سيُصحَّح عند التحديث التالي
    }
  }
}

class QuestionsController extends ListController<QuestionRow> {
  QuestionsController(this.repo);
  final Repository repo;

  /// عدد الأسئلة التي أعادها الديوان وتنتظر تعديل النائب.
  int get needsAttention => items.where((q) => q.status == QStatus.returned).length;

  @override
  Future<List<QuestionRow>> fetch() => repo.questions();
}

class DeputiesController extends ListController<DeputyPublic> {
  DeputiesController(this.repo);
  final Repository repo;

  @override
  Future<List<DeputyPublic>> fetch() => repo.deputies();
}

/// ذاكرة مؤقتة لصور النواب (في الذاكرة فقط، وتُمسح عند القفل أو الخروج).
class PhotoCache {
  PhotoCache(this.repo);
  final Repository repo;
  final Map<int, Future<Uint8List?>> _cache = {};

  Future<Uint8List?> get(int deputyId) {
    return _cache.putIfAbsent(deputyId, () async {
      try {
        return await repo.deputyPhoto(deputyId);
      } on ApiException {
        _cache.remove(deputyId); // لإعادة المحاولة لاحقاً
        return null;
      }
    });
  }

  void clear() => _cache.clear();
}
