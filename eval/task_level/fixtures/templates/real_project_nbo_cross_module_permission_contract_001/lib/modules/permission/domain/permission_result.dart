enum PermissionDecision {
  allow,
  block,
}

class PermissionResult {
  const PermissionResult({
    required this.cameraGranted,
    required this.locationGranted,
    required this.notificationGranted,
  });

  final bool cameraGranted;
  final bool locationGranted;
  final bool notificationGranted;

  bool get hasAnyMissingPermission => !cameraGranted || !locationGranted || !notificationGranted;
}
