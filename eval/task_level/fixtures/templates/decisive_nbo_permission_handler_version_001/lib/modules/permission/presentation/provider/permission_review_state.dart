import '../../domain/services/permission_status_mapper.dart';

class PermissionReviewCardState {
  const PermissionReviewCardState({required this.action, required this.message});

  final PermissionReviewAction action;
  final String message;
}

String messageFor(PermissionReviewAction action) {
  return switch (action) {
    PermissionReviewAction.allowed => 'Allowed',
    PermissionReviewAction.retryRequest => 'Request again',
    PermissionReviewAction.openAppSettings => 'Open app settings',
    PermissionReviewAction.blockedBySystem => 'Blocked by system policy',
    PermissionReviewAction.allowedWithLimits => 'Allowed with limited access',
    PermissionReviewAction.allowedWithFollowUp => 'Allowed; ask for full access later',
  };
}
