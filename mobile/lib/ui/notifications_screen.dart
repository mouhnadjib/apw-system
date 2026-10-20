import 'package:flutter/material.dart';

import '../core/format.dart';
import '../models/models.dart';
import '../services.dart';
import 'widgets.dart';

IconData _kindIcon(NotifKind k) => switch (k) {
      NotifKind.meeting => Icons.event,
      NotifKind.targeted => Icons.campaign_outlined,
      NotifKind.info => Icons.info_outline,
    };

class NotificationsScreen extends StatelessWidget {
  const NotificationsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final c = ServicesScope.of(context).notifications;
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
                    EmptyView(icon: Icons.notifications_none, message: 'لا توجد إشعارات بعد'),
                  ],
                )
              : ListView.separated(
                  physics: const AlwaysScrollableScrollPhysics(),
                  itemCount: c.items.length,
                  separatorBuilder: (_, __) => const Divider(height: 1),
                  itemBuilder: (context, i) => _NotificationTile(n: c.items[i]),
                ),
        );
      },
    );
  }
}

class _NotificationTile extends StatelessWidget {
  const _NotificationTile({required this.n});

  final AppNotification n;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final firstLine = n.body.split('\n').first;
    return ListTile(
      leading: CircleAvatar(
        backgroundColor: n.read ? scheme.surfaceContainerHighest : scheme.primaryContainer,
        child: Icon(_kindIcon(n.kind), color: n.read ? scheme.outline : scheme.onPrimaryContainer),
      ),
      title: Text(
        n.title,
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
        style: TextStyle(fontWeight: n.read ? FontWeight.normal : FontWeight.bold),
      ),
      subtitle: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(firstLine, maxLines: 1, overflow: TextOverflow.ellipsis),
          const SizedBox(height: 2),
          Text(
            n.kind == NotifKind.meeting && n.meetingAt != null
                ? 'الاجتماع: ${formatDateTime(n.meetingAt!)}'
                : formatRelative(n.createdAt),
            style: TextStyle(fontSize: 12, color: scheme.outline),
          ),
        ],
      ),
      trailing: n.read ? null : Icon(Icons.circle, size: 10, color: scheme.primary),
      onTap: () => Navigator.of(context).push(
        MaterialPageRoute<void>(builder: (_) => NotificationDetailScreen(n: n)),
      ),
    );
  }
}

class NotificationDetailScreen extends StatefulWidget {
  const NotificationDetailScreen({super.key, required this.n});

  final AppNotification n;

  @override
  State<NotificationDetailScreen> createState() => _NotificationDetailScreenState();
}

class _NotificationDetailScreenState extends State<NotificationDetailScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) ServicesScope.of(context).notifications.markRead(widget.n);
    });
  }

  @override
  Widget build(BuildContext context) {
    final n = widget.n;
    final scheme = Theme.of(context).colorScheme;
    return Scaffold(
      appBar: AppBar(title: Text(n.kind.label)),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          Text(n.title, style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.bold)),
          const SizedBox(height: 6),
          Text('وصل ${formatDateTime(n.createdAt)}', style: TextStyle(color: scheme.outline, fontSize: 12)),
          if (n.meetingAt != null) ...[
            const SizedBox(height: 16),
            Container(
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: scheme.primaryContainer,
                borderRadius: BorderRadius.circular(12),
              ),
              child: Row(
                children: [
                  Icon(Icons.event, color: scheme.onPrimaryContainer),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      'موعد الاجتماع: ${formatDateTime(n.meetingAt!)}',
                      style: TextStyle(color: scheme.onPrimaryContainer, fontWeight: FontWeight.w600),
                    ),
                  ),
                ],
              ),
            ),
          ],
          const SizedBox(height: 20),
          SelectableText(n.body, style: Theme.of(context).textTheme.bodyLarge?.copyWith(height: 1.7)),
        ],
      ),
    );
  }
}
