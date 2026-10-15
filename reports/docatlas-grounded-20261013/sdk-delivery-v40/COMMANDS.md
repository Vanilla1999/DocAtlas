# Execution commands

Working directory: `/tmp/opencode/docatlas-heuristic-removal-20261013`.
The committed product/wheel is `8605cbdb`; the results commit changes reports only.
`FROZEN_RUN.json` is the explicit 40x1 manifest, not the old 340-call freeze.

Executed once, no product retries:

```sh
timeout 1800 /tmp/opencode/docatlas-sdk-delivery-installed-20261013/bin/python -I eval/heuristic_removal/run.py --manifest reports/docatlas-grounded-20261013/sdk-delivery-v40/FROZEN_RUN.json --worker reports/docatlas-grounded-20261013/sdk-delivery-v40/WORKER.json --output reports/docatlas-grounded-20261013/sdk-delivery-v40/run/V0 --work /tmp/opencode/docatlas-sdk-delivery-v40-8605cbdb
```

stdout/stderr captured separately in `runner.stdout` / `runner.stderr`.

Offline assessment and aggregation, no product imports/calls:

```sh
/tmp/opencode/docatlas-sdk-delivery-installed-20261013/bin/python -I eval/heuristic_removal/assess.py --manifest reports/docatlas-grounded-20261013/sdk-delivery-v40/FROZEN_RUN.json --run-dir reports/docatlas-grounded-20261013/sdk-delivery-v40/run --output reports/docatlas-grounded-20261013/sdk-delivery-v40/assessment
/tmp/opencode/docatlas-sdk-delivery-installed-20261013/bin/python -I reports/docatlas-grounded-20261013/sdk-delivery-v40/summarize.py
```

For offline reading from the committed archive, extract `receipts.tar.xz` into
this report directory; its paths are `run/` and `assessment/`. Every raw file is
SHA-256 listed and losslessly verified in `RECEIPTS_ARCHIVE.json`.
The existing runtime/project temporary paths may no longer be live; assessment
uses recorded roots only for containment and independent pinned corpus bytes.

Do not rerun into existing work/output paths. A future product rerun requires a
new manifest and fresh paths, while keeping questions/oracle/source bytes intact.
Exact current wheel identity is in `run/V0/INSTALLED_ORIGIN.json` (archive),
and frozen source/config/tokenizer hashes are in `FROZEN_RUN.json`.
