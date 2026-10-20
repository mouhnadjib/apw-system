import 'package:flutter/material.dart';

import '../core/config.dart';
import '../core/server_address.dart';
import '../services.dart';

class ActivationScreen extends StatefulWidget {
  const ActivationScreen({super.key});

  @override
  State<ActivationScreen> createState() => _ActivationScreenState();
}

class _ActivationScreenState extends State<ActivationScreen> {
  final _form = GlobalKey<FormState>();
  final _phone = TextEditingController();
  final _code = TextEditingController();

  @override
  void dispose() {
    _phone.dispose();
    _code.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!(_form.currentState?.validate() ?? false)) return;
    FocusScope.of(context).unfocus();
    await ServicesScope.of(context).session.activate(_phone.text.trim(), _code.text.trim());
  }

  Future<void> _editServer() async {
    final api = ServicesScope.of(context).api;
    final controller = TextEditingController(text: api.baseUrl);
    final result = await showDialog<String>(
      context: context,
      builder: (ctx) {
        String? error;
        return StatefulBuilder(
          builder: (ctx, setLocal) => AlertDialog(
            title: const Text('عنوان الخادم (نسخة العرض)'),
            content: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                TextField(
                  controller: controller,
                  autofocus: true,
                  textDirection: TextDirection.ltr,
                  keyboardType: TextInputType.url,
                  decoration: InputDecoration(
                    hintText: 'http://192.168.1.5:8000',
                    errorText: error,
                    border: const OutlineInputBorder(),
                  ),
                ),
              ],
            ),
            actions: [
              TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('إلغاء')),
              FilledButton(
                onPressed: () {
                  final normalized = normalizeServerAddress(controller.text);
                  if (normalized == null) {
                    setLocal(() => error = 'عنوان غير صالح');
                    return;
                  }
                  Navigator.pop(ctx, normalized);
                },
                child: const Text('حفظ'),
              ),
            ],
          ),
        );
      },
    );
    controller.dispose();
    if (result == null) return;
    await ServerAddressStore().write(result);
    api.baseUrl = result;
    if (mounted) setState(() {});
  }

  @override
  Widget build(BuildContext context) {
    final session = ServicesScope.of(context).session;
    final scheme = Theme.of(context).colorScheme;
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 420),
              child: ListenableBuilder(
                listenable: session,
                builder: (context, _) => Form(
                  key: _form,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      Icon(Icons.account_balance, size: 64, color: scheme.primary),
                      const SizedBox(height: 12),
                      Text(
                        'المجلس الشعبي الولائي',
                        textAlign: TextAlign.center,
                        style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.bold),
                      ),
                      if (session.wilayaName != null) ...[
                        const SizedBox(height: 4),
                        Text(
                          session.wilayaName!,
                          textAlign: TextAlign.center,
                          style: Theme.of(context).textTheme.titleMedium,
                        ),
                      ],
                      const SizedBox(height: 28),
                      Text('تفعيل الحساب', style: Theme.of(context).textTheme.titleMedium),
                      const SizedBox(height: 4),
                      Text(
                        'أدخل رقم هاتفك المسجّل لدى ديوان المجلس ورمز الدعوة الذي سلّمه لك الديوان.',
                        style: TextStyle(color: scheme.outline),
                      ),
                      const SizedBox(height: 20),
                      TextFormField(
                        controller: _phone,
                        keyboardType: TextInputType.phone,
                        textDirection: TextDirection.ltr,
                        autofillHints: const [AutofillHints.telephoneNumber],
                        decoration: const InputDecoration(
                          labelText: 'رقم الهاتف',
                          prefixIcon: Icon(Icons.phone),
                          border: OutlineInputBorder(),
                        ),
                        validator: (v) {
                          final digits = (v ?? '').replaceAll(RegExp(r'\D'), '');
                          return digits.length < 9 || digits.length > 14 ? 'رقم هاتف غير صالح' : null;
                        },
                      ),
                      const SizedBox(height: 16),
                      TextFormField(
                        controller: _code,
                        textDirection: TextDirection.ltr,
                        textCapitalization: TextCapitalization.characters,
                        autocorrect: false,
                        decoration: const InputDecoration(
                          labelText: 'رمز الدعوة',
                          hintText: 'XXXXX-XXXXX',
                          prefixIcon: Icon(Icons.vpn_key),
                          border: OutlineInputBorder(),
                        ),
                        validator: (v) {
                          final clean = (v ?? '').replaceAll(RegExp(r'[^A-Za-z0-9]'), '');
                          return clean.length < 8 ? 'رمز الدعوة غير مكتمل' : null;
                        },
                        onFieldSubmitted: (_) => _submit(),
                      ),
                      if (session.error != null) ...[
                        const SizedBox(height: 16),
                        Container(
                          padding: const EdgeInsets.all(12),
                          decoration: BoxDecoration(
                            color: scheme.errorContainer,
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: Text(session.error!, style: TextStyle(color: scheme.onErrorContainer)),
                        ),
                      ],
                      const SizedBox(height: 20),
                      FilledButton(
                        onPressed: session.busy ? null : _submit,
                        child: Padding(
                          padding: const EdgeInsets.symmetric(vertical: 12),
                          child: session.busy
                              ? const SizedBox(
                                  width: 20,
                                  height: 20,
                                  child: CircularProgressIndicator(strokeWidth: 2),
                                )
                              : const Text('تفعيل'),
                        ),
                      ),
                      if (AppConfig.demoMode) ...[
                        const SizedBox(height: 12),
                        TextButton.icon(
                          onPressed: session.busy ? null : _editServer,
                          icon: const Icon(Icons.dns_outlined),
                          label: Text(
                            'الخادم: ${ServicesScope.of(context).api.baseUrl}',
                            textDirection: TextDirection.ltr,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                      ],
                    ],
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
