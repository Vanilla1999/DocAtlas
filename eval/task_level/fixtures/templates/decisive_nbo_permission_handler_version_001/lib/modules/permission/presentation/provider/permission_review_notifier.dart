import 'package:permission_handler/permission_handler.dart';

import '../../domain/services/permission_status_mapper.dart';

class PermissionReviewState {
  const PermissionReviewState({required this.actions});

  final Map<Permission, PermissionReviewAction> actions;
}

class PermissionReviewNotifier {
  PermissionReviewNotifier({PermissionStatusMapper mapper = const PermissionStatusMapper()}) : _mapper = mapper;

  final PermissionStatusMapper _mapper;

  PermissionReviewState buildReview(Map<Permission, PermissionStatus> statuses) {
    return PermissionReviewState(
      actions: statuses.map((permission, status) => MapEntry(permission, _mapper.actionFor(status))),
    );
  }
}
