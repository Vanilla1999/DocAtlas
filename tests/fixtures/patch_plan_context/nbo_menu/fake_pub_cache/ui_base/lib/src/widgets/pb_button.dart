class PBButton extends StatelessWidget {
  const PBButton({super.key, required this.onPressed, required this.child});

  final VoidCallback onPressed;
  final Widget child;
}
