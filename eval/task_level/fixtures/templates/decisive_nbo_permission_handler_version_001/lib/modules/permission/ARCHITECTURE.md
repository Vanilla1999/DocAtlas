# Permission - Architecture Guide

Runtime permission checks for Android camera, location, phone, notifications, and platform-specific follow-up states are centralized in the permission module.

## Scope

```text
permission/
├── domain/
│   └── services/
│       ├── permission_service.dart
│       └── permission_status_mapper.dart   # converts permission_handler status to review action
├── presentation/
│   └── provider/
│       ├── permission_review_notifier.dart  # consumes PermissionStatusMapper
│       └── permission_review_state.dart
└── README.md
```

## Dependency boundary

`permission_handler` enum details belong in the domain service mapper. Presentation code receives `PermissionReviewAction` values and must not duplicate the raw `PermissionStatus` mapping table.

## Do NOT

- Change dependency versions for a permission status classification fix.
- Add new raw `PermissionStatus` mappings in presentation providers.
- Treat notification provisional access as an app-settings failure.
- Treat permanently denied permissions as retryable request prompts.
