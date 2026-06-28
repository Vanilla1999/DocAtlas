# Notification Permission Policy

Android 13 and newer require notification runtime permission before notification-dependent scan/browser flows are allowed to continue.

The pinned `permission_handler` dependency exposes this as `Permission.notification` in version `11.4.0`. Do not substitute Android media permissions such as `Permission.photos`, `Permission.videos`, or `Permission.audio`; those are unrelated to notification preflight in this module.

The notification permission belongs in the shared permission preflight policy so scan and browser flows remain consistent.
