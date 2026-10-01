# Historical roadmap snapshots

The active roadmap was reset after the final infrastructure-hardening stack through PR #109.

The exact pre-reset roadmap is preserved by Git identity:

```text
commit: d565d8e75af2cbc56bc00fdc9df19dd1ae66863a
path:   roadmap/README.md
```

To inspect the historical roadmap without reintroducing stale statuses into the active file:

```bash
git show d565d8e75af2cbc56bc00fdc9df19dd1ae66863a:roadmap/README.md
```

That snapshot remains the audit trail for Tasks 01–43 and the infrastructure-construction stages. The current [`../README.md`](../README.md) is intentionally shorter and owns only the forward product-validation sequence.

Do not copy historical `In progress`, `Partial`, paused-stage, or residual-work statuses back into the active roadmap unless a new audit demonstrates they are still current.
