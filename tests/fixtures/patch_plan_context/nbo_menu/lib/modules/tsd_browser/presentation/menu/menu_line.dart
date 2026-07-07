import 'menu_page_builder.dart';
import 'provider/menu_state.dart';

class MenuLine extends StatelessWidget {
  const MenuLine({super.key, required this.state});

  final MenuState state;

  Widget build(BuildContext context) {
    return Row(
      children: [
        MenuPageBuilder(
          showScreenshot: true,
          showCamera: true,
          showTabs: true,
          showScanDoc: true,
          showRating: true,
          showInfo: true,
          showLogout: true,
          showAdmin: true,
          needFlashLight: state.needFlashLight,
          needBT: state.needBT,
          isEmulator: state.isEmulator,
        ),
        if (state.needBT) _showRT40QRDialog(context),
        if (state.needBT) _showMS300QRDialog(context),
      ],
    );
  }

  Widget _showRT40QRDialog(BuildContext context) {
    return const Text('RT40 legacy Bluetooth QR');
  }

  Widget _showMS300QRDialog(BuildContext context) {
    return const Text('MS300 legacy Bluetooth QR');
  }
}
