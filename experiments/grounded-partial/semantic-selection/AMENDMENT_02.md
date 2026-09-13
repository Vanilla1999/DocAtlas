# Measurement corrections after the first top-k summary

No new model scoring or parameter selection. The original score outputs are retained.

1. Tokenizer offsets exclude trailing whitespace. The initial `seen_text != original_text` flag incorrectly called 692 candidates truncated. Comparing the omitted suffix shows all 692 contain only whitespace, with zero substantive truncations. Source-character coverage already ignored whitespace, so every score, order, top-k count and sufficiency result is unchanged. The scorer flag is corrected for reproduction, and the evaluator reports both raw flags and substantive truncations.
2. The no-network wrapper runs scripts through runpy without adding the script directory to sys.path. The native diagnostic initially failed at importing its sibling exporter, before any handler execution. Added the script directory for that import. There is no failed retrieval result to include or exclude.
3. H1's preregistered top-5 criterion was not met (44/48 to 44/48). The top-1 improvement (25 to 37) is secondary evidence, not a retroactive change of the primary metric. Run the already planned native downstream diagnostic; keep holdout20 unscored unless a separately justified future protocol uses it.
