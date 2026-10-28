# Resource accounting correction before the first question

Initial CI run 40715353455 stopped all groups before any MCP question: Linux
reported the page-aligned memory.max 1,499,996,160, not the requested decimal
1,500,000,000. The verifier now requires the exact lower page boundary computed
from SC_PAGESIZE and zero swap; the configured Docker limit has NOT increased.

The downloaded initial qwen-select artifact also exposed host page-cache charging:
mmap file pages can be resident in the server but charged to the downloading host
cgroup. Subsequent runs use --no-mmap, ensuring model weights are private allocations
inside the measured runtime group. Initial startup memory is NOT a fit result.

These are harness/runtime-accounting changes, not model/prompt/gold tuning.
Product selector bytes, fixture bytes and model choices remain unchanged. The
failed initial run and its diagnostics remain available for audit.
