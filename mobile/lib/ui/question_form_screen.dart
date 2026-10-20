import 'package:flutter/material.dart';

import '../core/api.dart';
import '../models/models.dart';
import '../services.dart';
import 'widgets.dart';

/// إنشاء سؤال كتابي جديد، أو تعديل سؤال أعاده الديوان (`editing`).
class QuestionFormScreen extends StatefulWidget {
  const QuestionFormScreen({super.key, this.editing});

  final QuestionDetail? editing;

  @override
  State<QuestionFormScreen> createState() => _QuestionFormScreenState();
}

class _QuestionFormScreenState extends State<QuestionFormScreen> {
  static const subjectMax = 200;
  static const textMax = 8000;

  final _form = GlobalKey<FormState>();
  late final TextEditingController _subject;
  late final TextEditingController _text;
  bool _busy = false;
  String? _error;

  bool get _isEdit => widget.editing != null;

  @override
  void initState() {
    super.initState();
    _subject = TextEditingController(text: widget.editing?.subject ?? '');
    _text = TextEditingController(text: widget.editing?.text ?? '');
  }

  @override
  void dispose() {
    _subject.dispose();
    _text.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!(_form.currentState?.validate() ?? false)) return;
    final ok = await confirmDialog(
      context,
      title: _isEdit ? 'إعادة إرسال السؤال' : 'إرسال السؤال',
      message: _isEdit
          ? 'سيُرسل السؤال المعدَّل إلى ديوان رئيس المجلس للمراجعة.'
          : 'سيُرسل سؤالك إلى ديوان رئيس المجلس. لا يمكنك تعديله بعد الإرسال إلا إذا أعاده إليك الديوان.',
      confirmLabel: 'إرسال',
    );
    if (!ok || !mounted) return;
    final repo = ServicesScope.of(context).repo;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final subject = _subject.text.trim();
      final text = _text.text.trim();
      if (_isEdit) {
        await repo.editQuestion(widget.editing!.id, subject: subject, text: text);
      } else {
        await repo.createQuestion(subject: subject, text: text);
      }
      if (!mounted) return;
      showSnack(context, _isEdit ? 'أُعيد إرسال السؤال' : 'أُرسل السؤال إلى ديوان المجلس');
      Navigator.of(context).pop(true);
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final note = widget.editing?.returnNote;
    return Scaffold(
      appBar: AppBar(title: Text(_isEdit ? 'تعديل السؤال' : 'سؤال كتابي جديد')),
      body: SafeArea(
        child: Form(
          key: _form,
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              if (note != null) ...[
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(color: scheme.errorContainer, borderRadius: BorderRadius.circular(10)),
                  child: Text('ملاحظة الديوان: $note', style: TextStyle(color: scheme.onErrorContainer)),
                ),
                const SizedBox(height: 16),
              ],
              TextFormField(
                controller: _subject,
                enabled: !_busy,
                maxLength: subjectMax,
                textInputAction: TextInputAction.next,
                decoration: const InputDecoration(labelText: 'موضوع السؤال', border: OutlineInputBorder()),
                validator: (v) => (v ?? '').trim().length < 3 ? 'اكتب موضوعاً من 3 أحرف على الأقل' : null,
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: _text,
                enabled: !_busy,
                maxLength: textMax,
                minLines: 8,
                maxLines: 16,
                keyboardType: TextInputType.multiline,
                decoration: const InputDecoration(
                  labelText: 'نص السؤال الموجّه إلى الجهاز التنفيذي',
                  alignLabelWithHint: true,
                  border: OutlineInputBorder(),
                ),
                validator: (v) => (v ?? '').trim().length < 10 ? 'اكتب نص السؤال (10 أحرف على الأقل)' : null,
              ),
              if (_error != null) ...[
                const SizedBox(height: 12),
                Text(_error!, style: TextStyle(color: scheme.error)),
              ],
              const SizedBox(height: 16),
              FilledButton.icon(
                onPressed: _busy ? null : _submit,
                icon: _busy
                    ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
                    : const Icon(Icons.send),
                label: Text(_isEdit ? 'إعادة الإرسال' : 'إرسال'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
