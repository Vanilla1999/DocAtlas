import 'package:freezed_annotation/freezed_annotation.dart';
import 'package:permission_handler/permission_handler.dart';

part 'permission_info.freezed.dart';

@freezed
class PermissionInfo with _$PermissionInfo {
  factory PermissionInfo({
    required String name,
    required Permission permission,
  }) = _PermissionInfo;
}
