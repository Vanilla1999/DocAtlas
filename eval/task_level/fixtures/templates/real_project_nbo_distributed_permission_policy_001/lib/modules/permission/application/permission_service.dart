import '../domain/permission_info.dart';

class PermissionService {
  static const PermissionInfo cameraPermission = PermissionInfo(
    name: 'Camera',
    permission: Permission.camera,
  );

  static const PermissionInfo foregroundLocationPermission = PermissionInfo(
    name: 'Location',
    permission: Permission.location,
  );

  static const PermissionInfo backgroundLocationPermission = PermissionInfo(
    name: 'Background location',
    permission: Permission.locationAlways,
  );

  List<PermissionInfo> requiredForPreflight(PermissionFlow flow, int sdkInt) {
    return <PermissionInfo>[
      cameraPermission,
      foregroundLocationPermission,
    ];
  }

  bool isDeferredDuringPreflight(Permission permission) {
    return permission == Permission.locationAlways;
  }
}
