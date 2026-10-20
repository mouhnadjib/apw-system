import 'package:flutter/material.dart';

import 'app.dart';
import 'core/config.dart';
import 'core/format.dart';
import 'core/server_address.dart';
import 'services.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await initDateFormatting();

  final configError = AppConfig.validate();
  if (configError != null) {
    runApp(ConfigErrorApp(message: configError));
    return;
  }

  final savedAddress = AppConfig.demoMode ? await ServerAddressStore().read() : null;
  final services = AppServices.create(baseUrl: savedAddress);
  runApp(ApwApp(services: services));
  services.session.boot();
}
