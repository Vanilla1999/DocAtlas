# CairnStore synchronization configuration

The synchronization worker copies accepted local changes to a remote replica.

## Interval

`storage.sync.interval` is a nonnegative integer measured in seconds.
Setting `storage.sync.interval=0` selects manual synchronization; the worker remains enabled and accepts an explicit `cairn sync` request.

## Enabled switch

Setting `storage.sync.enabled=false` disables the synchronization worker.
While disabled, the worker rejects an explicit `cairn sync` request rather than treating it as a manual run.
The enabled switch is independent of the interval value.

## Environment override

`CAIRN_STORAGE_SYNC_INTERVAL` overrides the interval stored in the configuration file.
This environment variable does not override `storage.sync.enabled`.

## Key maintenance

Do not rotate the encryption key identifier during a replica rebalance.
Key-rotation restrictions do not change the meaning of the two synchronization settings.

