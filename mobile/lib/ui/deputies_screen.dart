import 'package:flutter/material.dart';

import '../core/format.dart';
import '../models/models.dart';
import '../services.dart';
import 'widgets.dart';

class DeputiesScreen extends StatefulWidget {
  const DeputiesScreen({super.key});

  @override
  State<DeputiesScreen> createState() => _DeputiesScreenState();
}

class _DeputiesScreenState extends State<DeputiesScreen> {
  final _search = TextEditingController();
  String _query = '';

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  List<DeputyPublic> _filter(List<DeputyPublic> all) {
    final q = normalizeArabic(_query);
    if (q.isEmpty) return all;
    return all
        .where((d) =>
            normalizeArabic(d.fullName).contains(q) ||
            normalizeArabic(d.title ?? '').contains(q) ||
            d.committees.any((c) => normalizeArabic(c).contains(q)))
        .toList();
  }

  void _showDetails(DeputyPublic d) {
    showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      builder: (ctx) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(24, 0, 24, 28),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              DeputyAvatar(id: d.id, hasPhoto: d.hasPhoto, name: d.fullName, radius: 64),
              const SizedBox(height: 14),
              Text(d.fullName, textAlign: TextAlign.center, style: Theme.of(ctx).textTheme.titleLarge),
              if (d.title != null) ...[
                const SizedBox(height: 2),
                Text(d.title!, style: TextStyle(color: Theme.of(ctx).colorScheme.outline)),
              ],
              if (d.committees.isNotEmpty) ...[
                const SizedBox(height: 14),
                Wrap(
                  spacing: 8,
                  runSpacing: 4,
                  alignment: WrapAlignment.center,
                  children: [for (final c in d.committees) Chip(label: Text(c))],
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final c = ServicesScope.of(context).deputies;
    return ListenableBuilder(
      listenable: c,
      builder: (context, _) {
        if (!c.loadedOnce && c.error == null) return const LoadingView();
        if (c.error != null && c.items.isEmpty) {
          return ErrorView(message: c.error!, onRetry: () => c.load());
        }
        final shown = _filter(c.items);
        return Column(
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(12, 12, 12, 4),
              child: TextField(
                controller: _search,
                onChanged: (v) => setState(() => _query = v),
                decoration: InputDecoration(
                  hintText: 'ابحث بالاسم أو اللجنة',
                  prefixIcon: const Icon(Icons.search),
                  suffixIcon: _query.isEmpty
                      ? null
                      : IconButton(
                          icon: const Icon(Icons.clear),
                          onPressed: () {
                            _search.clear();
                            setState(() => _query = '');
                          },
                        ),
                  border: const OutlineInputBorder(),
                  isDense: true,
                ),
              ),
            ),
            Expanded(
              child: RefreshIndicator(
                onRefresh: () => c.load(),
                child: shown.isEmpty
                    ? ListView(
                        physics: const AlwaysScrollableScrollPhysics(),
                        children: const [
                          SizedBox(height: 80),
                          EmptyView(icon: Icons.groups_outlined, message: 'لا يوجد نواب مطابقون'),
                        ],
                      )
                    : ListView.separated(
                        physics: const AlwaysScrollableScrollPhysics(),
                        itemCount: shown.length,
                        separatorBuilder: (_, __) => const Divider(height: 1),
                        itemBuilder: (context, i) {
                          final d = shown[i];
                          return ListTile(
                            leading: DeputyAvatar(id: d.id, hasPhoto: d.hasPhoto, name: d.fullName, radius: 26),
                            title: Text(d.fullName),
                            subtitle: Text(
                              [if (d.title != null) d.title!, ...d.committees].join(' · '),
                              maxLines: 2,
                              overflow: TextOverflow.ellipsis,
                            ),
                            onTap: () => _showDetails(d),
                          );
                        },
                      ),
              ),
            ),
          ],
        );
      },
    );
  }
}
