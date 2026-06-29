enum PermissionDecision {
  allow,
  block,
  deferFollowUp,
}

class PermissionResult {
  const PermissionResult({
    required this.cameraGranted,
    required this.locationGranted,
    required this.nearbyGranted,
    required this.notificationGranted,
    required this.backgroundLocationGranted,
    this.source = 'unknown',
  });

  final bool cameraGranted;
  final bool locationGranted;
  final bool nearbyGranted;
  final bool notificationGranted;
  final bool backgroundLocationGranted;
  final String source;

  bool get hasMissingImmediatePermission =>
      !cameraGranted || !locationGranted || !nearbyGranted || !notificationGranted;

  bool get hasDeferredBackgroundLocation => !backgroundLocationGranted;

  bool get hasPartialImmediateGrant =>
      (cameraGranted || locationGranted || nearbyGranted || notificationGranted) &&
      hasMissingImmediatePermission;
}
