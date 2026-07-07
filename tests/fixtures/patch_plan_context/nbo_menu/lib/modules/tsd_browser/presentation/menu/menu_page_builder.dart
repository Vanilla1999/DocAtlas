class MenuPageBuilder extends StatelessWidget {
  const MenuPageBuilder({
    super.key,
    required this.showScreenshot,
    required this.showCamera,
    required this.showTabs,
    required this.showScanDoc,
    required this.showRating,
    required this.showInfo,
    required this.showLogout,
    required this.showAdmin,
    required this.needFlashLight,
    required this.needBT,
    required this.isEmulator,
  });

  final bool showScreenshot;
  final bool showCamera;
  final bool showTabs;
  final bool showScanDoc;
  final bool showRating;
  final bool showInfo;
  final bool showLogout;
  final bool showAdmin;
  final bool needFlashLight;
  final bool needBT;
  final bool isEmulator;
}
