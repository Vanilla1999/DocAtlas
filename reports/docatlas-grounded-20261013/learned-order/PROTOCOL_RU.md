# Один learned reranker, без новых ручных эвристик

Разрешение владельца: «давай, только без эвристик, если не получится, ищи
исследования на тему». Не выполнять commit/push/merge/deploy.

## Зафиксированный метод

Одна готовая модель `cross-encoder/ms-marco-MiniLM-L6-v2`, upstream revision
`233902d25c440f23af6f7d6e94d2946bac0bee0a`, Apache2.0. English MS MARCO passage
ranking model, выбран до экспериментальных model calls как небольшая доступная
CPU-модель для English исходных вопросов. Официальный nonquantized ONNX graph;
файлы/hash pinning вне corpus, без remote code/download во время query.

Модель видит только неизменённый исходный вопрос и полный текст native окна.
Все unique source-admitted окна ранжируются по одному raw logit descending.
Точные равенства сохраняют исходный ordinal (детерминизм, не semantic bonus).
Никаких top-k, score thresholds, abstention heuristics, соседства, keyword/synonym
правил, score/cost ratios, новых группировок/дедупликации, ручных boosts, oracle
spans, labels, paths/titles или ответов в model input. Полная permutation pool.
Никакой обрезки question/window. Если pair длиннее model max positions512 —
explicit FAIL/stop, без fallback, не делать успешный claim на обрезанном тексте.
Batch8, CPU intra4/inter1, padding0, FP32 scores; no warmup forwards.

Host callback вызывается только после настоящего admission; получает immutable
strings, возвращает только complete integer index permutation. Source/window
объекты и metadata не выдаются callback. Default callback=None сохраняет native
order. Terminal whole-row first-fit budgeting и все source/authority validators
остаются неизменными: модель не получает права/ответную authority.
Предыдущий first-fit — неизменённая baseline policy, не новый learned sufficiency
метод. Пользовательский запрет эвристик означает отсутствие новых ручных
семантических правил; не объявлять всю систему математически без эвристик.

## Парный дизайн и gate

Один installed wheel обеих arms, Python -I, public `get_docs_context`, real member
SQLite. Native=callbackNone; Learned=одна модель. Shared root/generation каждого
pair, fixed questions/corpus/gold/evaluator. Ordered admitted pool должен быть
точно равен между arms. Alternating order, trace одинаково включена в обеих arms.
Full public MCP JSON cap12000=max(o200k_base,ceil(UTF8/4)), включая metadata;
не source-only cap, не saved pretty-JSON tokens и не provider billing.

Pilot: только P03/E01,2 prepares и4 context calls. Pilot gate: обе задачи должны
полностью покрыть исходный positive witness в learned конечном публичном DTO,
без source/budget/state/fairness violations и без model-input truncation.
При неуспехе — остановка, исследования; НЕ подгонять модель/inputs/rules на pilot.

После pilot PASS: ровно одна серия полного открытого V40,5 prepares,80 contexts
(40x2). Pilot — development повтор, не fresh holdout. Full comparison adoption
gate: strict positive total выше native; НИ ОДИН documented claim, покрытый native,
не должен теряться в learned на24 positive+8 partial. Source/state/fairness/budget
все должны пройти.8 negatives считаются отдельно по старому empty-source критерию;
их неизменный FAIL не переводится в PASS и не именуется галлюцинацией генератора.
Нет score threshold: reranker не реализует abstention/sufficiency; answers0.
При full gate FAIL — research, не внедрять candidate как default, не повторять
весь V40 и не выбирать другой model на тех же открытых результатах.

Runtime ceilings: pilot wall600s, full wall1800s; context120s including inline
rerank (явно выше прежних60s), prepare180s, load120s, no automatic retries.
Фактические preparations/context attempts, forwards/batches/pairs/time — receipts.
Source invalidity/model errors/read-only mutations останавливают серию.
Зависимости/assets/product/runner/oracle freeze до первого model/product call;
installed файлы сравниваются с wheel. Oracle только offline после серии.

## Границы выводов

English модель не доказывает multilingual поведение. ONNX pinned export не
объявлять доказанно эквивалентным PyTorch: parity отдельно не проверялась.
Этот эксперимент доказывает поведение именно экспортированного графа.
Открытый V40 — development comparison, не generalization или blind holdout.
Provenance, exact witness delivery, semantic sufficiency, answer/citation quality
и abstention — разные свойства. Последние без сгенерированных ответов не оценивать.
После результата дать decision отдельно: experimental useful/default unchanged.
