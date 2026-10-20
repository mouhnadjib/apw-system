import 'package:flutter/services.dart';
import 'package:local_auth/local_auth.dart';

/// التحقق من هوية صاحب الهاتف (بصمة/وجه/PIN) قبل فتح التطبيق.
abstract class DeviceAuth {
  /// هل للهاتف قفل شاشة أو بصمة مسجّلة؟
  Future<bool> isAvailable();
  Future<bool> authenticate(String reason);
}

class LocalDeviceAuth implements DeviceAuth {
  final LocalAuthentication _auth = LocalAuthentication();

  @override
  Future<bool> isAvailable() async {
    try {
      return await _auth.isDeviceSupported();
    } catch (_) {
      return false;
    }
  }

  @override
  Future<bool> authenticate(String reason) async {
    try {
      return await _auth.authenticate(
        localizedReason: reason,
        options: const AuthenticationOptions(biometricOnly: false, stickyAuth: true),
      );
    } on PlatformException {
      return false;
    }
  }
}

/// للاختبارات والتطوير بلا قفل.
class FakeDeviceAuth implements DeviceAuth {
  FakeDeviceAuth({this.available = true, this.result = true});
  final bool available;
  final bool result;

  @override
  Future<bool> isAvailable() async => available;

  @override
  Future<bool> authenticate(String reason) async => result;
}
