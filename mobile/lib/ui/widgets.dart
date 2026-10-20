import 'dart:typed_data';

import 'package:flutter/material.dart';

import '../models/models.dart';
import '../services.dart';

class LoadingView extends StatelessWidget {
  const LoadingView({super.key});

  @override
  Widget build(BuildContext context) => const Center(child: CircularProgressIndicator());
}

class ErrorView extends StatelessWidget {
  const ErrorView({super.key, required this.message, this.onRetry});

  final String message;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.cloud_off, size: 48, color: Theme.of(context).colorScheme.error),
            const SizedBox(height: 12),
            Text(message, textAlign: TextAlign.center),
            if (onRetry != null) ...[
              const SizedBox(height: 16),
              FilledButton.tonal(onPressed: onRetry, child: const Text('إعادة المحاولة')),
            ],
          ],
        ),
      ),
    );
  }
}

class EmptyView extends StatelessWidget {
  const EmptyView({super.key, required this.icon, required this.message});

  final IconData icon;
  final String message;

  @override
  Widget build(BuildContext context) {
    final muted = Theme.of(context).colorScheme.outline;
    return Padding(
      padding: const EdgeInsets.all(32),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 56, color: muted),
          const SizedBox(height: 12),
          Text(message, textAlign: TextAlign.center, style: TextStyle(color: muted)),
        ],
      ),
    );
  }
}

class StatusChip extends StatelessWidget {
  const StatusChip(this.status, {super.key});

  final QStatus status;

  @override
  Widget build(BuildContext context) {
    final c = Theme.of(context).colorScheme;
    final (bg, fg) = switch (status) {
      QStatus.returned => (c.errorContainer, c.onErrorContainer),
      QStatus.answered => (c.primary, c.onPrimary),
      QStatus.submitted || QStatus.underReview => (c.secondaryContainer, c.onSecondaryContainer),
      QStatus.confirmed || QStatus.referred => (c.primaryContainer, c.onPrimaryContainer),
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 3),
      decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(999)),
      child: Text(
        status.label,
        style: TextStyle(color: fg, fontSize: 12, fontWeight: FontWeight.w600),
      ),
    );
  }
}

/// صورة النائب من الخادم (بعد المصادقة)، وإلا الحرف الأول من الاسم.
class DeputyAvatar extends StatelessWidget {
  const DeputyAvatar({
    super.key,
    required this.id,
    required this.hasPhoto,
    required this.name,
    this.radius = 22,
  });

  final int id;
  final bool hasPhoto;
  final String name;
  final double radius;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final trimmed = name.trim();
    final fallback = CircleAvatar(
      radius: radius,
      backgroundColor: scheme.primaryContainer,
      child: Text(
        trimmed.isEmpty ? '؟' : trimmed.substring(0, 1),
        style: TextStyle(
          color: scheme.onPrimaryContainer,
          fontWeight: FontWeight.bold,
          fontSize: radius * 0.8,
        ),
      ),
    );
    if (!hasPhoto) return fallback;
    return FutureBuilder<Uint8List?>(
      future: ServicesScope.of(context).photos.get(id),
      builder: (context, snap) {
        final bytes = snap.data;
        if (bytes == null) return fallback;
        return CircleAvatar(radius: radius, backgroundImage: MemoryImage(bytes));
      },
    );
  }
}

Future<bool> confirmDialog(
  BuildContext context, {
  required String title,
  required String message,
  String confirmLabel = 'تأكيد',
}) async {
  final result = await showDialog<bool>(
    context: context,
    builder: (ctx) => AlertDialog(
      title: Text(title),
      content: Text(message),
      actions: [
        TextButton(onPressed: () => Navigator.of(ctx).pop(false), child: const Text('إلغاء')),
        FilledButton(onPressed: () => Navigator.of(ctx).pop(true), child: Text(confirmLabel)),
      ],
    ),
  );
  return result ?? false;
}

void showSnack(BuildContext context, String message) {
  ScaffoldMessenger.of(context)
    ..hideCurrentSnackBar()
    ..showSnackBar(SnackBar(content: Text(message)));
}
