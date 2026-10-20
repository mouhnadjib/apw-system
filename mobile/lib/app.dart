import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';

import 'services.dart';
import 'state/session.dart';
import 'ui/activation_screen.dart';
import 'ui/home_screen.dart';
import 'ui/lock_screen.dart';
import 'ui/theme.dart';

class ApwApp extends StatelessWidget {
  const ApwApp({super.key, required this.services});

  final AppServices services;

  @override
  Widget build(BuildContext context) {
    return ServicesScope(
      services: services,
      child: MaterialApp(
        title: 'المجلس الشعبي الولائي',
        debugShowCheckedModeBanner: false,
        theme: buildTheme(),
        locale: const Locale('ar'),
        supportedLocales: const [Locale('ar')],
        localizationsDelegates: const [
          GlobalMaterialLocalizations.delegate,
          GlobalWidgetsLocalizations.delegate,
          GlobalCupertinoLocalizations.delegate,
        ],
        home: const RootGate(),
      ),
    );
  }
}

/// يختار الشاشة بحسب حالة الجلسة. عند القفل أو الخروج يغلق كل الشاشات المفتوحة.
class RootGate extends StatefulWidget {
  const RootGate({super.key});

  @override
  State<RootGate> createState() => _RootGateState();
}

class _RootGateState extends State<RootGate> {
  SessionController? _session;
  SessionState? _last;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final s = ServicesScope.of(context).session;
    if (!identical(s, _session)) {
      _session?.removeListener(_onChange);
      _session = s..addListener(_onChange);
    }
  }

  void _onChange() {
    final s = _session!;
    if (_last == SessionState.ready && s.state != SessionState.ready) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) Navigator.of(context).popUntil((r) => r.isFirst);
      });
    }
    _last = s.state;
  }

  @override
  void dispose() {
    _session?.removeListener(_onChange);
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final session = ServicesScope.of(context).session;
    return ListenableBuilder(
      listenable: session,
      builder: (context, _) {
        switch (session.state) {
          case SessionState.booting:
            return const Scaffold(body: Center(child: CircularProgressIndicator()));
          case SessionState.needsActivation:
            return const ActivationScreen();
          case SessionState.locked:
            return const LockScreen();
          case SessionState.blocked:
            return const BlockedScreen();
          case SessionState.ready:
            return const HomeScreen();
        }
      },
    );
  }
}

class ConfigErrorApp extends StatelessWidget {
  const ConfigErrorApp({super.key, required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      locale: const Locale('ar'),
      supportedLocales: const [Locale('ar')],
      localizationsDelegates: const [
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
      home: Scaffold(
        body: Center(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Text(message, textAlign: TextAlign.center),
          ),
        ),
      ),
    );
  }
}
