import '../../permission/application/permission_service.dart';
import '../../permission/domain/permission_result.dart';

class PermissionReviewPolicy {
  PermissionReviewPolicy(this._permissionService);

  final PermissionService _permissionService;

  String labelFor(PermissionResult result) {
    final decision = _permissionService.evaluateReview(result);
    switch (decision) {
      case PermissionDecision.allow:
        return 'ready';
      case PermissionDecision.block:
        return 'fix permissions';
      case PermissionDecision.deferFollowUp:
        return 'complete follow-up after entry';
    }
  }
}
