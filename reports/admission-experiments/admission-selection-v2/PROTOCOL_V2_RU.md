# Frozen pre-inference protocol V2

## Граница
Public synchronous get_docs_context → реальные SQLite retrieval/reference preparation/qualification → новый host-only experimental selector перед selected/retained packing в _project_docs_service_part03.py → прежние ranking/projection/source validators → один frozen host.
Native окна означают фактические acquired raw-bound окна. Upstream lexical acquisition может делать expand=page во втором authoritative read; это прежняя acquisition, не отменяется. Отбор проводится до downstream snippet/section expansion и packing, не до существующей upstream SQLite expansion. Эта явная граница одинакова для всех arms; эффект изменения retrieval не исследуется.
Pool: deduplicated source/chunk windows с same-call native original binding и существующим qualified либо literal admission. Исключения сохраняются. B1-control оставляет весь допустимый pool и прочие исходные candidates для прежнего downstream veto; бюджетные arms отбирают только pool. Callback выбирает индексы, не меняет тексты/metadata/authority. Final guards сохраняются, replay receipt не даёт admission.

## Arms / calibration
B1-control; Budget-control existing pool order top-k; Mini FP32 raw logits order top-k; k∈{1,2,4}. Stable ties by upstream index. Select minimal k retaining ALL B1-delivered required positive facts on six independent calibration cases; negatives не используются для scalar cutoff. If none sufficient, stop budget arms quality claim, don't tune holdout. Holdout eight cases on disjoint document groups. Q16/Q46/OtherAPI/unrelated diagnostic only.
One scoring pass/case, store scores. No clipping beyond model limit: oversize input = explicit blocker, no silent truncation. No probability/threshold, no abstention judge.

## Workload ceilings
Initial common-pool capture: 18 questions (6 calibration,8 holdout,4 diagnostic), **7 prepares**: four independent family projects plus three original diagnostic fixtures, as fixed in TRANSPORT_BINDING_RU.md. Same genuine project/service generation kept live in a driver while scoring occurs in separate CPU process and subsequent arms call public API. Actual complete candidate sequence plus selectable bytes/order/hash must match common capture on every variant request; fail closed otherwise. Per-case public calls: capture B1 + Budget + Mini =54 max; calibration budget exploration uses scores/data before public selected calls, and selected k is then confirmed on final public calibration outputs. No hidden public retries. If capture pool is empty, count the real empty request; generator still tested against empty context if relevant.
Host: ≤42 main requests (holdout8+diagnostic4 ×3=36; calibration at most6 B1 requests if needed), no readiness inference. XProvence conditional ≤12 forwards pool subset? Exact smaller bound fixed after first arm results; overall ceilings1000 forwards/60 host/80 public requests/8 prepares/2h runtime/4GiB artifacts. Selection forwards ≤500 in primary pass; stop before ceiling.
No unit/private-helper tests/AST/compile checks, retries, repair, provider change, downloads, CI, deployment, commit/push.

## Host/provenance
Existing alias openai/gpt-5.6-luna#medium, old HOST_PROMPT_RU.txt exact bytes. Single endpoint request, old transparent conversation-JSON transport wrapper. Source schema same across arms: ID/text plus actual public path/scope/version/line/source identity metadata; no gold spans/facts/scores. Old generations cannot serve as paired control due to metadata difference. Model receives final public snippets, not private pool. No citation adapter in primary experiment.
Semantic answer, fact delivery, owner/relation support, exact quote substring, source-policy and CURRENT_CONTRACT separately assessed. Expected all-irrelevant refusal doesn't green empty-source contract. Claim quality only after independent review.

## Costs / stop
Observe acquisition/qualification/packing wall, score-only resident inference + cold load, host endpoint wall; model/DTO/submitted prompt proxies distinct, billing UNKNOWN. No p95 or GPU claims. Persistent per-request receipts; state generation/rows/catalog/source hashes before/after. Source-policy mismatch => stop arm. Two failed public cycles on same defect => blocker, no heuristic repair loop.
If common-pool public boundary cannot be verified, report technical blocker; don't run offline scoring as substitute or spend host requests on a non-comparable experiment.
