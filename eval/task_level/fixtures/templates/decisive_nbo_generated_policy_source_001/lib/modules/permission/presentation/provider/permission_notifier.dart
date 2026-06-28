import 'package:nbo/app/helpers/device_info.dart';
import 'package:nbo/modules/permission/data/models/permission_info.dart';
import 'package:nbo/modules/permission/domain/services/permission_service.dart';
import 'package:nbo/modules/permission/presentation/provider/permission_state.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

part 'permission_notifier.g.dart';

@riverpod
Future<PermissionState> requestPermission(RequestPermissionRef ref) async {
  // ignore: avoid_manual_providers_as_generated_provider_dependency
  final DeviceInfo deviceInfo = ref.watch(deviceInfoProvider.notifier);
  final isPCH = await deviceInfo.isPCH();
  final isSmartWatch = deviceInfo.isSmartWatch();
  if (isPCH || isSmartWatch) {
    return const PermissionState.complete();
  }
  final PermissionService permissionService =
      ref.read(permissionServiceProvider.notifier);
  final List<PermissionInfo> deniedPermissions =
      await permissionService.checkAndRequestPermissions();

  if (deniedPermissions.isEmpty) {
    return const PermissionState.complete();
  }
  return PermissionState.error(neededPermissions: deniedPermissions);
}
