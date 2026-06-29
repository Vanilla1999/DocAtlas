import 'package:freezed_annotation/freezed_annotation.dart';
import 'package:nbo/modules/permission/data/models/permission_info.dart';

part 'permission_state.freezed.dart';

@freezed
class PermissionState with _$PermissionState {
  const factory PermissionState.loading() = _Loading;

  const factory PermissionState.complete() = _Complete;
  const factory PermissionState.error(
      {required List<PermissionInfo> neededPermissions}) = _Error;
}
