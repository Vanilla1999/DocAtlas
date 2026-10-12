# Checkpoint перед compaction: admission experiment завершён

> **Последующее уточнение по запросу владельца:** перечитан методический протокол, отчёты, runners и отдельные raw ответы; создан `RESEARCH_METHOD_AUDIT_RU.md`. Завершены запуски диагностической фазы, но сопоставимое end-to-end сравнение для выбора метода НЕ завершено. Разные candidate boundaries, отсутствующие neural→host arms, собственная LLML line-closure и короткий SWE smoke ограничивают выводы. Не делать вывод «модели не нужны / исследования опровергнуты». Новых runtime/model/test запусков при аудите нет; исходные результаты не переписаны.

## Задача и статус

Пользователь поручил выполнить MULTI_AGENT_ADMISSION_FULL_PROTOCOL_RU.md семью параллельными агентами, реально сравнить admission/host prompting/reranking/pruning без unit-тестов и дать финальный отчёт. Затем явно отменил лимит600M и разрешил необходимые изолированные установки/downloads/runtime: «забей на лимит 600 и продолжи, запускай и доделай, нужен финальный отчет».

**Работа завершена. Новые прогоны не запланированы.** Последний запрос: вывести ссылки и сохранить всё нужное перед compaction. Не начинать следующий продуктовый цикл без нового запроса. Никаких unit-тестов, изменений frozen questions/corpus/oracle, default deployment, merge/release/force-push. Снятие runtime/size ограничений относилось к этому эксперименту, не является бессрочным разрешением на произвольные модели/providers/расходы.

## Репозиторий и изменения

- Workdir: `/tmp/opencode/docatlas-compact-review`.
- Branch: `fix/main-flow-compact-evidence`.
- HEAD: `4849b8f796d9e3e25e2c49e58562ec6859978411`.
- Архивная продуктовая база: `d8af387de507007f2b8c83f04aac78feb9b6760c`; между ними только четыре review-документа.
- **Четыре наших незакоммиченных изменения сохраняются**, не откатывать:
  1. `docmancer/docs/domain/original_body_discovery.py`
  2. `docmancer/docs/domain/ordinary_body_context.py`
  3. `docmancer/docs/domain/literal_context_admission.py`
  4. `eval/main_flow_comparison/run_extra40.py`
- Opt-in flag: `DOCATLAS_EXPERIMENT_ADMISSION=policy_candidates_v1`. Default OFF; без флага parity подтверждена. B1 снимает topical witness только в constrained native original project read, не весь delivery/source-policy veto. Owner/native receipts/numeric/hard-exact остаются. Answer/edit authority false.
- Runner добавляет необязательный `EXTRA40_SELECTED_IDS` и persistence каждой завершённой call для recovery; исходные вопросы/факты не переписаны.
- Diff +88/-21, `git diff --check` чистый. Commit/push/нового CI/merge/release не было.
- `FINAL_EXPERIMENT.patch` SHA256: `28011c0ea70c0b96e6ca1250473979225bade1ecd1a4f5bf1fc0fd8b6752a9f8`.

## Сначала читать

Все относительные пути ниже от `/tmp/opencode/docatlas-review-evidence/admission-full-20261012/`:

1. **FINAL_REPORT_RU.md** — русский итог координатора.
2. **G_FINAL_REVIEW.md / G_FINAL_RESULTS.json** — независимый окончательный audit; при расхождении с ранними pending/self-evaluations опираться на raw evidence и этот review.
3. **STATE.md / RUNTIME_DECISIONS_RU.md** — история разрешений, ролей, запусков и ошибок.
4. **FINAL_COSTS.json** — измеренные proxy tokens/time и хеши21 endpoint receipts, не billing.
5. **FINAL_EXPERIMENT.patch** — точный итоговый diff; не применять повторно поверх уже изменённой рабочей копии.

Ранние NOT RUN/pending разделы A–F исторические; актуальные результаты — final reports и raw receipts. `B_FINAL_SUMMARY.md` фиксировал промежуточный этап12 later calls, не окончательные18; его старое число не переносить в финал.

## Главный результат и решение

- Default-off: old1010/10, direct4028/40, нормализованная выдача всех40 совпала с исходной; controls10 PASS.
- Opt-in B1: old1010/10, **direct4039/40**, все прежние28 сохранены, Q16/Q46 факты доставлены. Это **доставка фактов**, не39 правильных сгенерированных ответов.
- B1 нарушил **четыре CURRENT_CONTRACT negatives**: OtherAPI, compound identifiers, Setext topical heading, unrelated quantum question. JUnit8PASS/2FAIL items не равно двум нарушенным сценариям: один item содержит несколько negatives.
- Scope/hash/read-state/false authority наблюдаемо сохранены; arbitrary access/consent/wrong-version/все DB/cache состояния не доказаны.
- **Default deployment не рекомендован.** Нет доказанной необходимости новой модели. Следующее возможное направление — bounded semantic owner/relation selection и проверяемое exact citation extraction, но не выполнять автоматически.

## Реальные ответы и модели

- Existing host: `openai/gpt-5.6-luna#medium` через stateless OpenCode endpoint; **21 requests** = readiness1 + generation12 + sufficiency4 + ranking4. Одна попытка runner, без output repair. Provider HTTP retries, billing/tokens, immutable backend revision и effective sampling не раскрыты.
- B1/R1/LLML: Q46 semantic+exact citation PASS; Q16 смысл PASS, **exact citation FAIL** во всех трёх ветвях: newline/two spaces заменены одним пробелом. Не исправлять результаты и не ослаблять критерий.
- S1: sufficiency labels верны на2 positives/2 negatives; не oracle правильности ответа. R1: оба negatives useful=[]; уменьшает selected packet, но дополнительная call увеличила full-turn prompt/time на измеренном срезе.
- Mini117.6M FP32 / Qwen595.8M BF16 / XProvence567.8M FP32: полезные native windows rank1 Q16/Q46; **23 forwards/model** (native21+public negatives2).
- OtherAPI scores > полезногоQ16: Mini2.750>1.660; Qwen8.438>3.625; XProvence1.291>−0.995. Универсальный ascending scalar cutoff не разделит эти наблюдения. Это не доказательство невозможности иных representations/owner-aware/per-query selectors; public neural product integration не выполнена.
- CRAG738.7M фактически загружено: **19 forwards**; native17/21 scored,4 overflow без clipping; Q16 fact746tokens NOT SCORED, Q46 useful rank2; OtherAPI0.759 ошибочно CORRECT по paper/code threshold0.592. Full correction/web/refinement NOT RUN; project-scope web запрещён.
- LLML checkpoint558.9M: **20 forwards**, raw теряет identifiers/отрицания; exact-line closure сохраняет source facts, но увеличивает host input. Не выдавать raw token deletion за дословную цитату.
- SWE634.3M: **1 forward**, CPU FP32/eager **ADAPTED**, короткий отдельный Dart code-QA. Факты сохранены, но удалён видимый class TSDTabController; обе code-host ветви не подтвердили обязательную switchTo→current=type relation. Strict complete grounding FAIL; это не выполнение/редактирование кода/SWE-Bench.
- Итого **109 model forwards**. Все CPU, без training; модели между собой последовательны. Часть timing пересекалась с API-прогонами — не controlled inference benchmark.
- Все сравнительные варианты ADAPTED; полное reproduction paper metrics/host protocols не заявлялось. Installed stdio/client/production/holdout не запускались.

## Стоимость и ошибки исполнения

- Direct40 B0/B1 public DTO: **41047→275588 o200k proxy tokens (6.71×)**, snippets20896→184035.
- Median context202→4369ms; saved40 sums8.822→174.765s (~19.8×), без lost/interrupted work и model/provider costs.
- R1 Q16 full submitted proxies5496 против4794 без ranking; Q46 2510 против1351. Smaller selected view не значит дешевле весь ход.
- LLML exact host inputs +7.57%/+6.30%, raw−52% не безопасная экономия. SWE short-code host prompt−21.74%, но grounding/owner FAIL и доп. compression cost.
- Первый B1 timeout120s:29 starts/28completions, сохранены24; четыре completed35–38 outputs потеряны buffering,39 interrupted. Recovery только35..50, без повтора сохранённых24. **44 completed +1 interrupted context attempts,2 prepares**; `B1_COMBINED40.json` — assembly двух реальных generations, не один непрерывный run.
- Initial baseline controls:4PASS/6setupFAIL из-за group-writable /tmp/opencode storage ancestor. Guard не ослабляли. Private runtime перенесли под sticky `/tmp`; повторили только failed6, всеPASS. Логи сохранены.

## Q31 оставшийся blocker

`A_Q31_REMAINING.md`: полный факт union двух acquired windows, но null admission/empty downstream. Source spelling HumanEval/LeetCode не проходит сохранённый whole-term unresolved-name HumanEval guard. Не canonical hard-exact и не numeric denial; достаточная причина реконструирована по коду, exact internal branch/private receipt отсутствует. Не чинить под39→40 без отдельного решения.

## Raw evidence: где что искать

- Public delivery: `live-B0/`, `live-default-off/`, `live-B1/`, `live-B1-resume/`, `B1_COMBINED40.json`.
- Controls: `live-B0-controls/`, `live-B0-safety-fixed/`, `live-default-off-controls/`, `live-B1-controls/`; JUnit, public-call-ledger/state, family snapshot proof. Логи рядом `live-*.log`.
- Default parity: `DEFAULT_OFF_PARITY.json`, независимые `G_DEFAULT_OFF_AUDIT.json`, `G_RUNTIME_DATA_AUDIT.json`.
- Host: `B_B0_Q16/`, `B_B0_Q46/`, `B_host_readiness/`, `B_later_*/` — exact messages/request/answer/raw response/receipt.
- Mini/Qwen: `C_*SMOKE_RECEIPT.json`, `C_*NEGATIVE_RECEIPT.json`, `C_SMOKE_INPUT.json`, `ACTUAL_PUBLIC_NEGATIVE_POOL.json`.
- XProvence: `D_assets/R5_P1_receipt.json`, `D_assets/NEGATIVE_receipt.json`, `D_assets/MEASURED_SUMMARY.json`.
- CRAG: `E_evaluator_receipt.json`, `E_NEGATIVE_receipt.json`, `E_assets/acquisition.json` (received-byte hashes, не author immutable checksum).
- Compression: `F_assets/LLML_RESULTS.json`, `F_assets/SWE_RESULTS.json`, `CLIENT_EXCERPT_BINDINGS.json`, `LLML_Q16_model_input.json`, `LLML_Q46_model_input.json`, `SWE_CODE_model_input.json`.
- Code: `CODE_PUBLIC_CAPTURE.json`, `CODE_public_model_input.json`, `G_CODE_ORACLE.md`, `F_assets/F_CODE_REFERENCE.md`.
- Frozen independent docs oracle: `G_ORACLE.md`, `G_FROZEN_ORACLE.json`; additional probes не запускались, не выдавать за holdout PASS.
- Prompts/protocol: `HOST_PROMPT_RU.txt`, `B_S1_PROMPT.json`, `B_R1_PROMPT.json`, `B_PROTOCOL_PARAMS.json`, `COMPARISON_PROTOCOL_RU.md`.
- Environments: `runtime-product/bin/python`, `model-runtime/bin/python`; locks `product-packages.txt`, `MODEL_RUNTIME_FREEZE.txt`, `MODEL_RUNTIME_LOCK.txt`. Ранее downloaded weights/venvs сохраняются; не скачивать повторно и не удалять без запроса.
- Source workflow/inventory: `COORDINATOR_ENVIRONMENT.md`, `CURRENT_HEAD_RECEIPT.json`, `current-head-ci/`.

## Делегированные sessions — только если понадобится точечное продолжение

A `ses_ed0368deaffeImnCrbMPiJTyh3`; B `ses_ed0365c6cffe3VbuDteP6VKA2i`; C `ses_ed03631e9ffe88evJtZ74RaH2T`; D `ses_ed0360a03ffev8T9mjWoTa0YKV`; E `ses_ed035db72ffePG1LxXYcjJ130D`; F `ses_ed035af1bffeDa3ajmKlFtyWkD`; G `ses_ed035858effeSg9JaKG9vtYKek`.

Новых агентов/runtime не требуется для завершения текущего запроса. Следующее действие после compaction — ответить на новый запрос владельца, сначала прочитав этот checkpoint и окончательный независимый review; не выполнять прежний длинный промпт заново.
