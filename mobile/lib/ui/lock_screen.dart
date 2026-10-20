import 'package:flutter/material.dart';

import '../services.dart';
import 'widgets.dart';

class LockScreen extends StatefulWidget {
  const LockScreen({super.key});

  @override
  State<LockScreen> createState() => _LockScreenState();
}

class _LockScreenState extends State<LockScreen> {
  @override
  void initState() {
    super.initState();
    // نطلب التحقق تلقائياً عند ظهور الشاشة
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) ServicesScope.of(context).session.unlock();
    });
  }

  Future<void> _logout() async {
    final session = ServicesScope.of(context).session;
    final ok = await confirmDialog(
      context,
      title: 'تسجيل الخروج',
      message: 'سيُفصل هذا الجهاز عن حسابك، وتحتاج رمز دعوة جديداً من الديوان للعودة.',
      confirmLabel: 'خروج',
    );
    if (ok) await session.logout();
  }

  @override
  Widget build(BuildContext context) {
    final session = ServicesScope.of(context).session;
    final scheme = Theme.of(context).colorScheme;
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: ListenableBuilder(
              listenable: session,
              builder: (context, _) => Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(Icons.lock_outline, size: 72, color: scheme.primary),
                  const SizedBox(height: 16),
                  Text('التطبيق مقفل', style: Theme.of(context).textTheme.headlineSmall),
                  const SizedBox(height: 8),
                  Text(
                    'تحقق من هويتك لعرض إشعارات المجلس وأسئلتك.',
                    textAlign: TextAlign.center,
                    style: TextStyle(color: scheme.outline),
                  ),
                  if (session.error != null) ...[
                    const SizedBox(height: 16),
                    Text(session.error!, textAlign: TextAlign.center, style: TextStyle(color: scheme.error)),
                  ],
                  const SizedBox(height: 24),
                  FilledButton.icon(
                    onPressed: session.busy ? null : session.unlock,
                    icon: session.busy
                        ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
                        : const Icon(Icons.fingerprint),
                    label: const Text('فتح التطبيق'),
                  ),
                  const SizedBox(height: 12),
                  TextButton(onPressed: session.busy ? null : _logout, child: const Text('تسجيل الخروج من هذا الجهاز')),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// الهاتف بلا قفل شاشة: لا نفتح بيانات المجلس.
class BlockedScreen extends StatelessWidget {
  const BlockedScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final session = ServicesScope.of(context).session;
    return Scaffold(
      body: SafeArea(
        child: ErrorView(
          message: session.error ?? 'تعذّر فتح التطبيق.',
          onRetry: session.boot,
        ),
      ),
    );
  }
}
