import 'dart:io';

import 'package:device_info_plus/device_info_plus.dart';
import 'package:easy_localization/easy_localization.dart';
import 'package:nbo/localization_keys/locale_keys.g.dart';
import 'package:nbo/modules/permission/data/models/permission_info.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

part 'permission_service.g.dart';

@riverpod
class PermissionService extends _$PermissionService {
  @override
  FutureOr<void> build() {}

  // Add every required permission here and in AndroidManifest.
  List<PermissionInfo> permissionsToRequest = <PermissionInfo>[
    PermissionInfo(
      name: LocaleKeys.permissionModule_camera.tr(),
      permission: Permission.camera,
    ),
    PermissionInfo(
      name: LocaleKeys.permissionModule_phone.tr(),
      permission: Permission.phone,
    ),
    PermissionInfo(
      name: LocaleKeys.permissionModule_location.tr(),
      permission: Permission.location,
    )
  ];

  PermissionInfo permissionStorage = PermissionInfo(
    name: LocaleKeys.permissionModule_storage.tr(),
    permission: Permission.storage,
  );

  PermissionInfo permissionManageExternalStorage = PermissionInfo(
    name: LocaleKeys.permissionModule_storage.tr(),
    permission: Permission.manageExternalStorage,
  );

  PermissionInfo permissionManageBluethoothScan = PermissionInfo(
    name: LocaleKeys.permissionModule_storage.tr(),
    permission: Permission.bluetoothScan,
  );

  PermissionInfo permissionManageBluethoothConnect = PermissionInfo(
    name: LocaleKeys.permissionModule_storage.tr(),
    permission: Permission.bluetoothConnect,
  );

  PermissionInfo permissionLocationAlways = PermissionInfo(
    name: LocaleKeys.permissionModule_location.tr(),
    permission: Permission.locationAlways,
  );

  Future<List<PermissionInfo>> checkAndRequestPermissions() async {
    final List<PermissionInfo> permissionsToRequestAgain = <PermissionInfo>[];

    if (Platform.isAndroid) {
      await addPermissionsNotAw();
    }

    // Request every permission except locationAlways first.
    final List<Permission> permsToRequestFirst = permissionsToRequest
        .where((p) => p.permission != Permission.locationAlways)
        .map((p) => p.permission)
        .toList();

    final Map<Permission, PermissionStatus> statuses =
        await permsToRequestFirst.request();

    for (final PermissionInfo permissionInfo in permissionsToRequest) {
      if (permissionInfo.permission == Permission.locationAlways) continue;
      final PermissionStatus? status = statuses[permissionInfo.permission];
      if (status != PermissionStatus.granted) {
        permissionsToRequestAgain.add(permissionInfo);
      }
    }

    PermissionInfo? locationAlwaysInfo;
    for (final p in permissionsToRequest) {
      if (p.permission == Permission.locationAlways) {
        locationAlwaysInfo = p;
        break;
      }
    }

    if (locationAlwaysInfo != null && Platform.isAndroid) {
      final PermissionStatus locationStatus = await Permission.location.status;
      if (locationStatus.isGranted) {
        final PermissionStatus alwaysStatus = await Permission.locationAlways.request();

        if (!alwaysStatus.isGranted) {
          permissionsToRequestAgain.add(locationAlwaysInfo);
        }
      } else {
        permissionsToRequestAgain.add(locationAlwaysInfo);
      }
    }

    return permissionsToRequestAgain;
  }

  Future<void> addPermissionsNotAw() async {
    final DeviceInfoPlugin deviceInfo = DeviceInfoPlugin();
    final AndroidDeviceInfo androidInfo = await deviceInfo.androidInfo;

    if (androidInfo.version.sdkInt >= 33) {
    } else if (!permissionsToRequest.any((p) => p.permission == permissionStorage.permission)) {
      permissionsToRequest.add(permissionStorage);
    }
    if (androidInfo.version.sdkInt >= 32) {
      if (!permissionsToRequest.any((p) => p.permission == permissionManageBluethoothScan.permission)) {
        permissionsToRequest.add(permissionManageBluethoothScan);
      }
      if (!permissionsToRequest.any((p) => p.permission == permissionManageBluethoothConnect.permission)) {
        permissionsToRequest.add(permissionManageBluethoothConnect);
      }
    }
    if (androidInfo.version.sdkInt >= 29) {
      if (!permissionsToRequest.any((p) => p.permission == permissionLocationAlways.permission)) {
        permissionsToRequest.add(permissionLocationAlways);
      }
    }
  }
}
