import 'package:flutter/material.dart';

import '../core/api.dart';
import '../core/format.dart';
import '../models/models.dart';
import '../services.dart';
import 'question_form_screen.dart';
import 'reply_viewer_screen.dart';
import 'widgets.dart';

class QuestionDetailScreen extends StatefulWidget {
  const QuestionDetailScreen({super.key, required this.questionId});

  final int questionId;

  @override
  State<QuestionDetailScreen> createState() => _QuestionDetailScreenState();
}

class _QuestionDetailScreenState extends State<QuestionDetailScreen> {
  QuestionDetail? _q;
  String? _error;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final q = await ServicesScope.of(context).repo.question(widget.questionId);
      if (!mounted) return;
      setState(() => _q = q);
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _edit(QuestionDetail q) async {
    final changed = await Navigator.of(context).push<bool>(
      MaterialPageRoute(builder: (_) => QuestionFormScreen(editing: q)),
    );
    if (changed == true) _load();
  }

  @override
  Widget build(BuildContext context) {
    final q = _q;
    return Scaffold(
      appBar: AppBar(title: Text('السؤال #${widget.questionId}')),
      body: q == null
          ? (_loading ? const LoadingView() : ErrorView(message: _error ?? 'تعذّر التحميل', onRetry: _load))
          : RefreshIndicator(
              onRefresh: _load,
              child: _Body(q: q, onEdit: () => _edit(q)),
            ),
    );
  }
}

class _Body extends StatelessWidget {
  const _Body({required this.q, required this.onEdit});

  final QuestionDetail q;
  final VoidCallback onEdit;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;
    return ListView(
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.all(16),
      children: [
        Text(q.subject, style: textTheme.titleLarge?.copyWith(fontWeight: FontWeight.bold)),
        const SizedBox(height: 8),
        Row(
          children: [
            StatusChip(q.status),
            const SizedBox(width: 10),
            Text('أُرسل ${formatDateTime(q.createdAt)}', style: TextStyle(fontSize: 12, color: scheme.outline)),
          ],
        ),
        const SizedBox(height: 16),
        StatusStepper(status: q.status),
        const SizedBox(height: 16),
        if (q.status == QStatus.returned) ...[
          Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(color: scheme.errorContainer, borderRadius: BorderRadius.circular(12)),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'أعاد الديوان سؤالك لتعديله',
                  style: TextStyle(color: scheme.onErrorContainer, fontWeight: FontWeight.bold),
                ),
                if (q.returnNote != null) ...[
                  const SizedBox(height: 6),
                  Text(q.returnNote!, style: TextStyle(color: scheme.onErrorContainer)),
                ],
                const SizedBox(height: 12),
                FilledButton.icon(
                  onPressed: onEdit,
                  icon: const Icon(Icons.edit),
                  label: const Text('تعديل السؤال وإعادة إرساله'),
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),
        ],
        if (q.status == QStatus.answered && q.hasReply) ...[
          FilledButton.icon(
            onPressed: () => Navigator.of(context).push<void>(
              MaterialPageRoute(builder: (_) => ReplyViewerScreen(questionId: q.id)),
            ),
            icon: const Icon(Icons.description_outlined),
            label: const Text('عرض رد الجهاز التنفيذي'),
          ),
          const SizedBox(height: 16),
        ],
        Text('نص السؤال', style: textTheme.titleSmall?.copyWith(color: scheme.outline)),
        const SizedBox(height: 6),
        Container(
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            color: scheme.surfaceContainerHighest,
            borderRadius: BorderRadius.circular(12),
          ),
          child: SelectableText(q.text, style: textTheme.bodyLarge?.copyWith(height: 1.7)),
        ),
        const SizedBox(height: 24),
        Text('مسار السؤال', style: textTheme.titleSmall?.copyWith(color: scheme.outline)),
        const SizedBox(height: 8),
        for (final e in q.events.reversed) _EventRow(event: e),
      ],
    );
  }
}

class _EventRow extends StatelessWidget {
  const _EventRow({required this.event});

  final QuestionEvent event;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.only(bottom: 14),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.only(top: 6),
            child: Icon(Icons.circle, size: 12, color: scheme.primary),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    StatusChip(event.status),
                    const SizedBox(width: 8),
                    Flexible(
                      child: Text(
                        formatDateTime(event.createdAt),
                        style: TextStyle(fontSize: 12, color: scheme.outline),
                      ),
                    ),
                  ],
                ),
                if (event.note != null) ...[
                  const SizedBox(height: 4),
                  Text(event.note!),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// شريط تقدم من خمس مراحل. الحالة «أُعيد للتعديل» تُعلَّم عند مرحلة المراجعة.
class StatusStepper extends StatelessWidget {
  const StatusStepper({super.key, required this.status});

  final QStatus status;

  static const labels = ['مُرسل', 'المراجعة', 'التأكيد', 'الإحالة', 'الرد'];

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final current = status.step;
    final returned = status == QStatus.returned;
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (var i = 0; i < labels.length; i++)
          Expanded(
            child: Column(
              children: [
                CircleAvatar(
                  radius: 13,
                  backgroundColor: (returned && i == current)
                      ? scheme.error
                      : (i <= current ? scheme.primary : scheme.surfaceContainerHighest),
                  child: (returned && i == current)
                      ? Icon(Icons.undo, size: 14, color: scheme.onError)
                      : (i <= current ? Icon(Icons.check, size: 14, color: scheme.onPrimary) : null),
                ),
                const SizedBox(height: 4),
                Text(
                  labels[i],
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    fontSize: 11,
                    fontWeight: i == current ? FontWeight.bold : FontWeight.normal,
                    color: i <= current ? scheme.onSurface : scheme.outline,
                  ),
                ),
              ],
            ),
          ),
      ],
    );
  }
}
