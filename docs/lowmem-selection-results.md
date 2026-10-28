# Measured continuation of the frozen low-memory experiment

See [the complete Russian review](../reports/lowmem-selection-20261028/RESULT_RU.md)
and [machine-readable results](../reports/lowmem-selection-20261028/SUMMARY.compact.json).
The earlier `lowmem-selection-experiment.md` remains the preregistered initial
contract, not the final decision or a recommendation of its original Q8 profile.

The shared runtime limit stays 1,500,000,000 bytes, zero swap and two CPUs.
All three main controls consumed at most 620,777,472 bytes. The original Q8
profile failed the memory gate in four of six cells. A separately documented
Q4 profile with prompt cache/checkpoints disabled passed all six cells, peaking
at 1,430,958,080 bytes; this is not a universal bound on arbitrary corpora.

Tiny planning preserved every main-delivered witness on 58 questions and
recovered two pilot requirements, but doubled V40 context size. Direct tiny
selection applied only once. Neither replaces the main default. Fixed-five
and raw gap selection also introduced losses on the smaller challenge sets.

An additional delivery-only comparison, with unchanged MiniLM selection,
verified the same source text/path/coordinates/provenance for 58 replies:
stock-like MCP text 84,228 -> managed model-view 51,920 tokens on 57 matched
successful requests. The existing error is not counted as savings. A compatible
host must preserve the private source packet and resolve source references;
this does not establish stock OpenCode behavior or actual billed GPT savings.

No default, product prompt, frozen question or gold was retuned after scoring.
The last report commit does not request new inference. Old startup/rounding/CLI
errors and genuine Q8 OOMs are disclosed, not silently replaced with PASS.
Paid usage, generated-answer accuracy, correct unknowns and autonomous
OpenCode end-to-end time remain NOT_TESTED. Keep PR #234 Draft.
