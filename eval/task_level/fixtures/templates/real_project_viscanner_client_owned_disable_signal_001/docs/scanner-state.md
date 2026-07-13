# Scanner state contract

The service owns scanner state and vendor beep. While disabled it suppresses barcode delivery and reports a disabled scan attempt to the same AAR client listener; the client owns any custom sound. Do not pass audio paths or play custom audio in the service. Pause and release restore normal vendor state before existing lifecycle behavior. Only Urovo standard-beep control is in scope. Do not add blockScanner.
