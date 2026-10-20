import 'package:flutter/material.dart';

import '../models/models.dart';
import '../services.dart';
import 'deputies_screen.dart';
import 'legal_screen.dart';
import 'notifications_screen.dart';
import 'question_form_screen.dart';
import 'questions_screen.dart';
import 'widgets.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  int _index = 0;

  Future<void> _newQuestion() async {
    final created = await Navigator.of(context).push<bool>(
      MaterialPageRoute(builder: (_) => const QuestionFormScreen()),
    );
    if (created == true && mounted) ServicesScope.of(context).questions.load(silent: true);
  }

  void _showProfile(Profile p) {
    showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      builder: (ctx) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(24, 0, 24, 24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              DeputyAvatar(id: p.id, hasPhoto: p.hasPhoto, name: p.fullName, radius: 44),
              const SizedBox(height: 12),
              Text(p.fullName, style: Theme.of(ctx).textTheme.titleLarge, textAlign: TextAlign.center),
              if (p.title != null) Text(p.title!),
              const SizedBox(height: 4),
              Text(p.mandateLabel, style: TextStyle(color: Theme.of(ctx).colorScheme.outline)),
              if (p.committees.isNotEmpty) ...[
                const SizedBox(height: 12),
                Wrap(
                  spacing: 8,
                  runSpacing: 4,
                  alignment: WrapAlignment.center,
                  children: [for (final c in p.committees) Chip(label: Text(c))],
                ),
              ],
              const SizedBox(height: 20),
              FilledButton.tonalIcon(
                icon: const Icon(Icons.logout),
                label: const Text('تسجيل الخروج من هذا الجهاز'),
                onPressed: () async {
                  final session = ServicesScope.of(context).session;
                  final ok = await confirmDialog(
                    ctx,
                    title: 'تسجيل الخروج',
                    message: 'سيُفصل هذا الجهاز عن حسابك، وتحتاج رمز دعوة جديداً من الديوان للعودة.',
                    confirmLabel: 'خروج',
                  );
                  if (ok) {
                    if (ctx.mounted) Navigator.of(ctx).pop();
                    await session.logout();
                  }
                },
              ),
            ],
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final s = ServicesScope.of(context);
    final profile = s.session.profile;
    final wilaya = s.session.wilayaName;

    return Scaffold(
      appBar: AppBar(
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('المجلس الشعبي الولائي', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
            if (wilaya != null) Text(wilaya, style: const TextStyle(fontSize: 12)),
          ],
        ),
        actions: [
          if (profile != null)
            Padding(
              padding: const EdgeInsetsDirectional.only(end: 12),
              child: InkWell(
                customBorder: const CircleBorder(),
                onTap: () => _showProfile(profile),
                child: DeputyAvatar(id: profile.id, hasPhoto: profile.hasPhoto, name: profile.fullName, radius: 18),
              ),
            ),
        ],
      ),
      body: IndexedStack(
        index: _index,
        children: const [
          NotificationsScreen(),
          QuestionsScreen(),
          DeputiesScreen(),
          LegalScreen(),
        ],
      ),
      floatingActionButton: _index == 1
          ? FloatingActionButton.extended(
              onPressed: _newQuestion,
              icon: const Icon(Icons.edit_outlined),
              label: const Text('سؤال جديد'),
            )
          : null,
      bottomNavigationBar: ListenableBuilder(
        listenable: Listenable.merge([s.notifications, s.questions]),
        builder: (context, _) {
          final unread = s.notifications.unread;
          final attention = s.questions.needsAttention;
          return NavigationBar(
            selectedIndex: _index,
            onDestinationSelected: (i) => setState(() => _index = i),
            destinations: [
              NavigationDestination(
                icon: Badge(
                  isLabelVisible: unread > 0,
                  label: Text('$unread'),
                  child: const Icon(Icons.notifications_outlined),
                ),
                selectedIcon: Badge(
                  isLabelVisible: unread > 0,
                  label: Text('$unread'),
                  child: const Icon(Icons.notifications),
                ),
                label: 'الإشعارات',
              ),
              NavigationDestination(
                icon: Badge(
                  isLabelVisible: attention > 0,
                  label: Text('$attention'),
                  child: const Icon(Icons.help_outline),
                ),
                selectedIcon: Badge(
                  isLabelVisible: attention > 0,
                  label: Text('$attention'),
                  child: const Icon(Icons.help),
                ),
                label: 'الأسئلة',
              ),
              const NavigationDestination(
                icon: Icon(Icons.groups_outlined),
                selectedIcon: Icon(Icons.groups),
                label: 'النواب',
              ),
              const NavigationDestination(
                icon: Icon(Icons.gavel_outlined),
                selectedIcon: Icon(Icons.gavel),
                label: 'النصوص',
              ),
            ],
          );
        },
      ),
    );
  }
}
