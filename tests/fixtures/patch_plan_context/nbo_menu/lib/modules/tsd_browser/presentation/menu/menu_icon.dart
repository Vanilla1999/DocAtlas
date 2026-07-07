import 'provider/menu_notifier.dart';

class MenuIcon extends StatelessWidget {
  const MenuIcon({super.key, required this.notifier});

  final MenuNotifier notifier;

  void openMenu() {
    notifier.openMenu();
  }

  void closeMenu() {
    notifier.closeMenu();
  }

  Widget build(BuildContext context) {
    return IconButton(onPressed: openMenu, icon: const Icon(Icons.menu));
  }
}
