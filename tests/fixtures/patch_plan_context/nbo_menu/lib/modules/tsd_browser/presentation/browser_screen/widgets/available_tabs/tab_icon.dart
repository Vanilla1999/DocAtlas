class TabIcon extends StatelessWidget {
  void openTabs() {}

  Widget build(BuildContext context) {
    return IconButton(onPressed: openTabs, icon: const Icon(Icons.tab));
  }
}
