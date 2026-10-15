# C1/C2 closure — независимый bounded rereview C

2026-10-07. Primary `/home/viadmin/StudioProjects/hermes/docmancer`, branch
`integration/stage3-v2-identity-pr1`, baseline
`6e94d6ab926f23c39c2bdbb7b926f6a1593ec68f`.

## Вердикт: bounded source EXIT YES

**C1 и C2 закрыты физическим удалением vocabulary/semantic branches.**
В узком examined source scope первого review конкретных оставшихся NL dictionary
blockers не обнаружено. Дополнительных production fixes не требуется.
Это не full-product/release/quality/full-security acceptance; external artifacts,
installed wheel/packs/deployed SDK и current runtime index остаются **UNKNOWN**.

Предыдущий `NL_DICTIONARY_REMOVAL_FINAL_REVIEW_RU.md` неизменён: его BLOCKED verdict
относится к предыдущим source hashes, а этот документ — к corrected pins.

## C1: actual helpers без ручного word omission/topic inference

`docmancer/docs/_patch_plan_context_part01.py`:

- `_ordered_terms`: English vocabulary-dependent `continue` branch больше
  не присутствует; сохранены length/identifier shape/deduplication checks.
- `_looks_like_symbol`: ручной English exclusion set удалён; length, uppercase/
  qualified identifier shape и `.pen/.fig` design-artifact restriction сохранены.
- `_nearest_dependency_alternatives`: bottom-sheet semantic reason branch удалён;
  literal identifier-token overlap и generic attribution сохранены.
- `_probable_symbol_terms`/actual discovery caller используют исправленные helpers;
  экспорты существуют, нового shim/renamed classifier нет.

New actual calls подтверждают `PLAN/CHANGE/MARBLE` одинаково по identifier shape,
`x`/`design.fig` по-прежнему не принимаются; `BottomSheet/BottomPanel` получает
только `Similar resolved dependency API found.`

## C2: actual outline без topic classification

`docmancer/docs/application/project_answer_outline.py`:

- Definitions `compute_coverage` и `reason_for_source` физически удалены;
  production references/imports к ним отсутствуют.
- `build_project_answer_outline` сохраняет literal source attribution, порядок
  входных sources, normalized-path deduplication и максимум **5** записей.
- Reason статический; `coverage={}` означает unknown, не семь inferred `False`
  и не promoted topic facts. `warnings=[]`; прежняя topic warning branch удалена.
- Actual caller `_project_context_service_part01.py:620` остаётся согласованным
  с контрактом. Цитаты не отбрасываются и не заменяются all-unsupported результатом.

Прямой новый in-memory вызов на семи sources плюс duplicate вернул первые пять
distinct paths в исходном порядке, `coverage={}`, `warnings=[]`; original prose
`overview layout install added` осталась неизменной. Новый node также проверяет
`docs/myarchitecturefiction.md`/heading `mcp`: semantic reason больше не возникает.

## Pins: точное supersession без скрытого изменения prior payload

`/tmp/opencode/nl-removal-corrected-pins.json`: **39/39 MATCH**.
Сравнение с prior integrated manifest (**38** paths):

- **35/38 hashes unchanged**.
- Ровно **3** prior entries superseded: patch shard, NEW literal test,
  его NEW diagnostic-label shard.
- Ровно **1** added entry: `project_answer_outline.py`; removed entries **0**.
  Этот второй production-файл прежде не входил в 38 pins, но его предыдущий hash
  был явно зафиксирован в первом review: `c90e9e1bbe154ee0a7e17519258392dc714446bcfdfcc644a8ad7f2c9a6c4ef5`.

Следовательно, изменены ровно два reviewed production payloads и один NEW test/
shard; остальные prior integrated payloads совпадают. Documentation/manifest
обновления вне этих payload pins не выдаются за production изменения.
Первые **163 строки** NEW literal module побайтно дают прежний SHA256: исходные
23 cases сохранены, добавлены только два новых nodes. Packet/consumer modules
и их diagnostic shards совпадают с prior pins. Старый review не перезаписан.

Corrected SHA256:

```text
96ffb7b40275289bdba06f47c60236b3505705a4c870113063dac884f7414f4e docmancer/docs/_patch_plan_context_part01.py
3993c0c6428777390f765dc5c183168a43cc0388f665ba9d8f7247c127ee5383 docmancer/docs/application/project_answer_outline.py
5e4fe0b7d65c3687c07da81b3a6107e5e4bd850448750889ff5f87b90c52ba3a tests/test_nl_dictionary_removal_literal_contract.py
6022551f4e2dbbbdc5c488a706a337c24dd830b3455a95c1b3d3271c19a40b1c tests/diagnostic_labels.nl_dictionary_removal_literal_contract.json
```

## Проверки

Только три NEW modules, normal conftest/offline:

```text
PYTHONDONTWRITEBYTECODE=1 DOCATLAS_OFFLINE=1
PYTHONPATH=/home/viadmin/StudioProjects/hermes/docmancer
.venv/bin/python -m pytest -p no:cacheprovider -q
  --basetemp=/tmp/opencode/nl-removal-c-closure
  tests/test_nl_dictionary_removal_packet_contract.py
  tests/test_nl_dictionary_removal_consumer_contract.py
  tests/test_nl_dictionary_removal_literal_contract.py
45 passed in 0.64s (12 + 8 + 25)
```

Все прежние **43 NEW cases** сохранены и проходят: arbitrary prose bytes, display/
snapshot hash, child/parent/span/version, actual selector/ActionPacket/SDK/public MCP
и projector, root/freshness checks, non-authorizing caller risk/issuer/consent,
workflow/edit denial и 800-token checks. Они не являются legacy compatibility gate.

- Preservation snapshot: **1487/1487 SHA256 MATCH**.
- Frozen approved manifest: **13/13 SHA256 MATCH**, независимо rehashed owner,
  reference/review, seven inputs, two references и ledger; historical acceptance
  не переинтерпретируется.
- In-memory production compile: **385 modules PASS**.
- Corrected production imports и declared exports: **31 modules PASS**.
- `git diff --check`: PASS.
- Один bounded AST/source inventory по `docmancer/`: removed detector/C2 symbol
  definitions/import references отсутствуют; suspicious NL regex hits отсутствуют.
  Проверены найденные literal-table candidates: schema keys/registry attribution,
  explicit DTO severity enums, постоянный unresolved profile и literal history-path
  negative guards, а не prose modality/topic classifiers. API syntax, identifier
  grammar, technical paths и artifact exclusions не объявлены NL dictionaries.
  Scope/config/template exemptions первого review не расширялись.

## Budget debt и ограничения

`_compact_failure_packet` и `_fit_packet` снова AST-equal baseline `6e94d6ab`.
Actual empty-source packet при `max_tokens=128` по-прежнему имеет **231 tokens**;
validator с explicit 128 отклоняет его:
`estimated_tokens mismatch or hard limit exceeded`.
Это прежний structural minimum-schema budget debt, не C1/C2 regression и не новый
NL-removal blocker. Full budget correctness/quality/release остаются **UNKNOWN**.

Reviewer не выполнял old tests/full CI/95-failure triage, network/provider calls,
index mutations, reinstall или delegation. Source/tests/config/historical reports
не редактировались; единственная запись reviewer — этот новый closure report.
**YES ограничен examined integrated source и закрытием C1/C2; внешняя runtime parity
и общая product/security acceptance не утверждаются.**
