# TideGauge

TideGauge stores harbour water-level observations from fixed stations. These rules apply to live station feeds; survey imports are a different service.

## Components

Receivers authenticate station messages, a journal preserves arrival order, and an exporter publishes daily bundles. The journal and exporter can restart independently. The dashboard is a read-only consumer and cannot acknowledge observations.

## Navigation

Operational detail is in [Replay](operations.md#replay), [Storage](storage.md#retention), and [Display](dashboard.md#display). These links are a navigation index, not a request to execute every procedure.
