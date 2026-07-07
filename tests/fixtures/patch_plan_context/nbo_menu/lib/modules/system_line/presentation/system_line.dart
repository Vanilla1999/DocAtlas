import '../../tsd_browser/presentation/menu/menu_icon.dart';

class SystemLine extends StatelessWidget {
  Widget build(BuildContext context) {
    return Row(children: [MenuIcon(notifier: menuNotifier)]);
  }
}
