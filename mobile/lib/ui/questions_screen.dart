import 'package:flutter/material.dart';

import '../core/format.dart';
import '../models/models.dart';
import '../services.dart';
import 'question_detail_screen.dart';
import 'widgets.dart';

class QuestionsScreen extends StatelessWidget {
  const QuestionsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final c = ServicesScope.of(context).questions;
    final scheme = Theme.of(context).colorScheme;
    return ListenableBuilder(
      listenable: c,
      builder: (context, _) {
        if (!c.loadedOnce && c.error == null) return const LoadingView();
        if (c.error != null && c.items.isEmpty) {
          return ErrorView(message: c.error!, onRetry: () => c.load());
        }
        return RefreshIndicator(
          onRefresh: () => c.load(),
          child: c.items.isEmpty
              ? ListView(
                  physics: const AlwaysScrollableScrollPhysics(),
                  children: const [
                    SizedBox(height: 120),
                    EmptyView(
                      icon: Icons.help_outline,
                      message: 'لم ترسل أي سؤال كتابي بعد.\nاضغط «سؤال جديد» لإرسال سؤالك إلى الجهاز التنفيذي عبر ديوان المجلس.',
                    ),
                  ],
                )
              : ListView(
                  physics: const AlwaysScrollableScrollPhysics(),
                  padding: const EdgeInsets.only(bottom: 88),
                  children: [
                    if (c.needsAttention > 0)
                      Container(
                        margin: const EdgeInsets.all(12),
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: scheme.errorContainer,
                          borderRadius: BorderRadius.circular(10),
                        ),
                        child: Row(
                          children: [
                            Icon(Icons.edit_note, color: scheme.onErrorContainer),
                            const SizedBox(width: 10),
                            Expanded(
                              child: Text(
                                'لديك ${c.needsAttention} سؤال أعاده الديوان لتعديله.',
                                style: TextStyle(color: scheme.onErrorContainer, fontWeight: FontWeight.w600),
                              ),
                            ),
                          ],
                        ),
                      ),
                    for (final q in c.items) ...[
                      _QuestionTile(q: q),
                      const Divider(height: 1),
                    ],
                  ],
                ),
        );
      },
    );
  }
}

class _QuestionTile extends StatelessWidget {
  const _QuestionTile({required this.q});

  final QuestionRow q;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      title: Text(q.subject, maxLines: 2, overflow: TextOverflow.ellipsis),
      subtitle: Padding(
        padding: const EdgeInsets.only(top: 6),
        child: Row(
          children: [
            StatusChip(q.status),
            const SizedBox(width: 10),
            Expanded(
              child: Text(
                formatRelative(q.updatedAt),
                style: TextStyle(fontSize: 12, color: Theme.of(context).colorScheme.outline),
              ),
            ),
          ],
        ),
      ),
      trailing: const Icon(Icons.chevron_left),
      onTap: () async {
        await Navigator.of(context).push<void>(
          MaterialPageRoute(builder: (_) => QuestionDetailScreen(questionId: q.id)),
        );
        if (context.mounted) ServicesScope.of(context).questions.load(silent: true);
      },
    );
  }
}
