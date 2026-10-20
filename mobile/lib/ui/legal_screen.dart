import 'package:flutter/material.dart';

/// تبويب النصوص القانونية: فارغ حالياً، ويُملأ لاحقاً.
class LegalScreen extends StatelessWidget {
  const LegalScreen({super.key});

  static const _pending = <String>[
    'القانون 12-07 المتعلق بالولاية',
    'المرسوم التنفيذي رقم 22-54 المؤرخ في 02 فبراير 2022',
  ];

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Text(
          'النصوص القانونية والتنظيمية',
          style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold),
        ),
        const SizedBox(height: 4),
        Text('ستُضاف النصوص إلى هذا التبويب لاحقاً.', style: TextStyle(color: scheme.outline)),
        const SizedBox(height: 16),
        for (final title in _pending)
          Card(
            child: ListTile(
              leading: Icon(Icons.menu_book_outlined, color: scheme.outline),
              title: Text(title),
              trailing: const Chip(label: Text('قريباً')),
              enabled: false,
            ),
          ),
      ],
    );
  }
}
