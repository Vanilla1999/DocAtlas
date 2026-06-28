import '../domain/permission_result.dart';

class PermissionService {
  PermissionDecision evaluateFlowEntry(
    PermissionResult result, {
    bool allowOfflineFallback = false,
  }) {
    if (result.hasMissingImmediatePermission) {
      // BUG: offline fallback was meant only for network availability, not for
      // missing critical permissions. Returning deferFollowUp lets browser/sync
      // proceed on partial permission results.
      return allowOfflineFallback
          ? PermissionDecision.deferFollowUp
          : PermissionDecision.block;
    }
    return PermissionDecision.allow;
  }

  PermissionDecision evaluateReview(PermissionResult result) {
    if (result.hasMissingImmediatePermission) {
      return PermissionDecision.block;
    }
    if (result.hasDeferredBackgroundLocation) {
      return PermissionDecision.deferFollowUp;
    }
    return PermissionDecision.allow;
  }
}
