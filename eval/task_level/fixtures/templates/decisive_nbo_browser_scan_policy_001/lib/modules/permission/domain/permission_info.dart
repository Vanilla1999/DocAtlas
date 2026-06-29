enum Permission {
  camera,
  location,
  locationAlways,
  notification,
}

enum PermissionFlow {
  browser,
  scan,
}

class PermissionInfo {
  const PermissionInfo({
    required this.name,
    required this.permission,
  });

  final String name;
  final Permission permission;
}
