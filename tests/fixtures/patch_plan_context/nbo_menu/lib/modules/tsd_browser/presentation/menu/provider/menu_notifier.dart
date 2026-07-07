import 'menu_state.dart';

class MenuNotifier {
  MenuState state = const MenuState(
    needFlashLight: false,
    needBT: false,
    isEmulator: false,
    isOpen: false,
  );

  void openMenu() {
    state = state.copyWith(isOpen: true);
  }

  void closeMenu() {
    state = state.copyWith(isOpen: false);
  }
}
