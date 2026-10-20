import 'package:flutter/material.dart';

import 'app.dart';
import 'core/config.dart';
import 'core/format.dart';
import 'services.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await initDateFormatting();

  final configError = AppConfig.validate();
  if (configError != null) {
    runApp(ConfigErrorApp(message: configError));
    return;
  }

  final services = AppServices.create();
  runApp(ApwApp(services: services));
  services.session.boot();
}
