# Resource accounting corrections before model measurements

Initial CI run 40715353455 stopped all groups before any MCP question: Linux
reported the page-aligned memory.max 1,499,996,160, not the requested decimal
1,500,000,000. The verifier now requires the exact lower page boundary computed
from SC_PAGESIZE and zero swap; the configured Docker limit has NOT increased.

The initial qwen-select artifact also exposed host page-cache charging: mmap file
pages can be resident in the server but charged to the downloading host cgroup.
Subsequent model runs disable mmap, making weights private resident allocations
inside the measured group. Initial startup memory is NOT a fit result.

The pinned llama.cpp 0.8.0 uses `--load-mode none` (documented in its server README),
not the legacy `--no-mmap` switch. Run 40715953536 completed no Qwen inference
because that old spelling was rejected at startup. Its unaffected baseline is
retained rather than cancelled or rerun. The runtime-only correction reruns only
the two affected model groups. Manual dispatch and normal product commits still
run all groups. Comparison requires identical product/fixture hashes.

These are harness/runtime-accounting changes, not model/prompt/gold tuning.
Product selector bytes, fixture bytes and model choices remain unchanged. The
failed initial runs and diagnostics remain available for audit.
