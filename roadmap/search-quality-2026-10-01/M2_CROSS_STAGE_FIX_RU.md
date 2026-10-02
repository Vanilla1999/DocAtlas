# M2: исправление discovery/admission стыка

Пользователь разрешил ограниченный сквозной разбор discovery/delivery.
Это не закрытие M3/M4 и не multilingual quality claim.

## Причина и исправление

1. Перед per-source quota original retrieval уже содержит required абзац
   httpx-07 (четвёртый candidate, score 0.9). После body reranking первые два
   места занимают children одной fine-tuning секции. Абзац другого parent
   отсекается quota. Бюджет, фильтры и candidate limit не увеличены.
   `_rank_project_bodies_within_source` теперь распределяет первые места между
   различными indexed parents внутри исходной source очереди. Exact identity
   tier остаётся приоритетным; отсутствующие parent metadata сохраняют прежний
   порядок. Per-source quota, bounded shared-parent overflow и inter-source
   positions не менялись. Ranking preference не является proof.
2. Lexical token `behavior:` ошибочно включает sentence colon, а `deployment.`
   — sentence period. Только неquoted lexical terms очищаются от terminal
   `.`/`:`, без NL decomposition. Quotes, shaped identifiers, slash paths, namespace `::` и raw
   question сохраняются; typed exact constraints не меняются.
3. Literal anchors проверялись в собственных retrieval lanes, но не против
   candidates из original lane. `_qualify_candidate_lookups` теперь cross-checks
   existing exact anchors на уже найденных bytes только при отсутствии
   independently qualified public candidates. Иначе literal rescue не должен
   конкурировать с уже квалифицированным packet. Новых запросов/aliases/needs
   нет. Source/reference guards и native qualification остаются. Literal child
   не создаёт original coverage: `derived_parent_trace` допускает только
   audited rewrite, не exact_anchor.

Изменение ranking включено в fusion config hash отдельным version key:
`literal-terms-parent-diversity-v2`. Это изменение runtime нельзя считать
повторным запуском прежнего fixed retrieval protocol.

## Causal ablation

`m2_httpx_cross_stage_ablation.json`: original request/corpus/assertions не менялись.
С тремя fixes required claim supported, exact default paragraph visible,
private claim needs_review, answer_supported=False, edit_ready=False.
При независимом отключении каждого из трёх fixes required снова needs_review,
default paragraph отсутствует. Monkeypatch ablations не являются production.

## Контроли

- `m2_cross_stage_controls.log`: **247 passed**, включая исходный httpx-07,
  typer-01, новые lexical/parent/anchor counterexamples, существующие diversity
  caps, hard identity, CLI, qualification и systemic candidate tests.
  Дополнительно включены исходные exact-document fallback и joint invariant
  controls; их assertions и seed fixtures не менялись.
- `m2_cross_stage_retrieval_guards.log`: **82 passed** — metadata eligibility,
  SQLite ranking/phrase, retrieval fusion и public vector tests.
- Наборы не складываются в acceptance score; exposed cases не holdout.
- Required-fact regression не заменён lookup variant и не ослаблен.
- Universal grammar/ratio policy, security/certification и edit permissions
  не изменялись. Structural metadata не объявлена semantic equivalence.

Первый полный trial (`m2_cross_stage_full_docs.log`): 3346 passed / 115 failed.
Он выявил восемь новых failures: четыре original attribution в exact-document
fallback и четыре joint seed/completion expectations. Причины — слишком широкая
очистка shaped tokens и конкуренция anchor rescue с qualified packet. Исправлены
production restrictions, не tests. Эти восемь cases теперь проходят в focused
контролях; 247 PASS выше относятся уже к исправленной версии.

Повторный полный `tests/docs`: `m2_cross_stage_stable_docs.log`, **3355 passed /
108 failed**, 160.94 s. Новых failing test IDs относительно
`m2_serious_stable_docs.log` нет. Исправлены httpx-07 и один private-plan case.
Восемь побочных failures trial устранены production fixes, исходные controls
проходят. `m2_cross_stage_final_safety.log`: **66 passed**, включая size/catalog,
patch, admission guard composition и runtime freeze.

С checkpoint 5a732198 остаются 26 common failures и 82 current-only.
Source/delivery regressions `mkdocs-05`, `pydantic-07`, `ruff-07` всё ещё падают
на native required-claim assertions; их нельзя считать obsolete fixture только
по имени module. Для pydantic/ruff original questions не содержат technical
locators, так что этот literal-anchor fix не решает их delivery автоматически.
Нужно отдельно проверить discovery/ranking и qualification для этих requests.
Остальные fixtures с ожиданием generated rows тоже не мигрированы полностью.
M2 gate остаётся открытым; снятие httpx-07 не является полной приёмкой.
