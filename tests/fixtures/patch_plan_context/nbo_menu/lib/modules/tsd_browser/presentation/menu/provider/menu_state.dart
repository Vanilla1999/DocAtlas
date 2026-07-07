class MenuState {
  const MenuState({
    required this.needFlashLight,
    required this.needBT,
    required this.isEmulator,
    required this.isOpen,
  });

  final bool needFlashLight;
  final bool needBT;
  final bool isEmulator;
  final bool isOpen;

  MenuState copyWith({bool? needFlashLight, bool? needBT, bool? isEmulator, bool? isOpen}) {
    return MenuState(
      needFlashLight: needFlashLight ?? this.needFlashLight,
      needBT: needBT ?? this.needBT,
      isEmulator: isEmulator ?? this.isEmulator,
      isOpen: isOpen ?? this.isOpen,
    );
  }
}
