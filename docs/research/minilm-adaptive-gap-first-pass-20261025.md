# MiniLM Adaptive-k: first, source-grounded experiment (2026-10-25)

## Identity and scope

DocAtlas's already-pinned model is [cross-encoder/ms-marco-MiniLM-L6-v2](https://huggingface.co/cross-encoder/ms-marco-MiniLM-L6-v2), revision `233902d25c440f23af6f7d6e94d2946bac0bee0a`. Weights are provisioned explicitly, checksum verified and served via local CPU ONNX; DocAtlas did not train the model.

Experimental script: `eval/experimental_adaptive_k_replay.py`. No changes to production selection, installed MCP behavior, default TOP_K=5, source/authority contracts, weights, tokenizer or V40 questions/gold.

Independent source research: [Taguchi et al., EMNLP 2025](https://aclanthology.org/2025.emnlp-main.1017/). **This is NOT the paper's validated Adaptive-k implementation.** The paper uses cosine embedding similarities, searches the first 90% of candidates and uses B=5. This experiment only borrows largest-gap logic, using raw MiniLM cross-encoder logits, buffer 0/1 and a five-group cap. It also studies a top-five-window variant. Scores are not probabilities and are not calibrated for sufficiency.

## Verified offline replay

All 40 original V40 input questions were scored by the real installed MiniLM in previous offline CPU stdio runs on exact head `a19bb7525943bfc10da075d0ed15cb424c626bc2`. This experiment reuses actual ranked section receipts and independently checks per-rank scoring-text hashes against the archived k1/k2/k3 runs. Different independent preparations yield different response-bound evidence IDs, so replay matches scoring-text hashes rather than capability IDs.

The cutoff is calculated *before* consulting the archived witness assessments. Existing known V40 is regression only, not independent unseen acceptance. Cases with k=4 inherit documented-fact coverage from a *passed* original k3 response; exact token size for k4 is bounded by archived k3 and k5 responses, not freshly measured. All other k sizes use their exact earlier client text measurements.

| Policy, raw MiniLM scores | Mean selected groups | Positive facts | Partial facts | Mean model tokens, lower–upper bound |
|---|---:|---:|---:|---:|
| Existing fixed k5 | 5.00 | 24/24 | 8/8 | 2478 |
| Full distribution largest gap, B0, cap5 | 2.55 | 24/24 | 8/8 | 1313–1344 |
| Full distribution largest gap, B1, cap5 | 3.25 | 24/24 | 8/8 | 1661–1722 |
| First-five-window gap, B0 | 1.75 | 23/24 | 8/8 | 840–951 |
| First-five-window gap, B1 | 2.70 | 24/24 | 8/8 | 1361–1422 |

The first-five-window B0 arm **lost V40-B01**. All four arms still return irrelevant context for unanswerable questions (strict-empty 0/8). The apparent success of the full-distribution arms is exploratory only and does not prove generalization, optimal relevance cutoff, semantic abstention or correctness of final LLM answers.

## Reproduce and next gate

[GitHub Actions run](https://github.com/Vanilla1999/DocAtlas/actions/runs/40133630208) confirmed the script on SHA-256-verified original archived artifacts without any new model or hosted-LLM requests. Original files are in CI artifacts 12573704617 (k5), 12573940504 (k1), 12573039268 (k2), 12573369784 (k3). New replay artifact 12576126655 includes `REPLAY.json` and `CASES.csv`.

Next acceptance is **real new installed-MCP inference against independent documentation and questions unseen by the selector/evaluator**, with declared documentation-language handling, complete source-native witness verification and the same fixed cap5 baseline. Freeze the B and gap policy before looking at new gold; record chosen k, all scores, exact model-visible tokens, complete supported and partial witnesses, and unanswerable behavior separately. Test the main strong answering agent's correctness later, but **do not charge it with choosing k**. Keep fail-closed operational boundaries, exact source citations, <=1GB memory and a switchable experimental mode; do not enable this from the paper/V40 replay alone.
