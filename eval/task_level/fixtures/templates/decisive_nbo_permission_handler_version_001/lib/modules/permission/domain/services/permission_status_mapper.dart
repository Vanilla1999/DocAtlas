import 'package:permission_handler/permission_handler.dart';

enum PermissionReviewAction {
  allowed,
  retryRequest,
  openAppSettings,
  blockedBySystem,
  allowedWithLimits,
  allowedWithFollowUp,
}

class PermissionStatusMapper {
  const PermissionStatusMapper();

  PermissionReviewAction actionFor(PermissionStatus status) {
    return switch (status) {
      PermissionStatus.granted => PermissionReviewAction.allowed,
      PermissionStatus.denied => PermissionReviewAction.retryRequest,
      // BUG: permanently denied permissions cannot be fixed by another request.
      PermissionStatus.permanentlyDenied => PermissionReviewAction.retryRequest,
      // BUG: restricted is controlled by the system, not by app settings.
      PermissionStatus.restricted => PermissionReviewAction.openAppSettings,
      PermissionStatus.limited => PermissionReviewAction.allowed,
      // BUG: provisional notification access should stay usable with a follow-up.
      PermissionStatus.provisional => PermissionReviewAction.openAppSettings,
    };
  }
}
