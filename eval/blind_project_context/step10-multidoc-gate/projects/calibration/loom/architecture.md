# Rendering internals

Loom uses a manifest store, lease queue, raster workers and publication service.

## Raster pipeline

Workers decode tiles, apply transformations and encode derivatives. Tile parallelism reduces memory pressure but does not change the job's approval or embargo state. The pipeline supports several output formats whose encoder implementations are interchangeable.

## Legacy demonstration

The demonstration renderer guessed missing camera profiles and published immediately. It was used with disposable sample images and is not a production workflow.
