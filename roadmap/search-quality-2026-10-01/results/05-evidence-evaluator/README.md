# Шаг 05 — evidence evaluator, без настройки поиска

Baseline: `5672a16c`. Только eval logic, tests и отчёт. Правка и [саморевью](REVIEW_RU.md) включены в отдельный коммит шага 05 по запросу пользователя; push/merge не выполнялись. Frozen corpus/cases/protocol, вопросы, budgets, production runtime и official wires не менялись. Итоговые после ревью результаты: [review-final](review-final/summary.json), [69 passed](review-final-tests.log).

## Red → Green

[Red](red.log): **3 failed, 30 passed**. Воспроизведены требование одной contiguous цитаты вместо двух отдельно доставленных paragraphs, rendered list mismatch и ошибочное признание удаления значимого leading space в code literal как formatting-only.

Тот же baseline scorer replay сохранённых responses находится в `original` полях [финальных rows](replay-final/rows.json): MkDocs06 и uv06 — `needs_review`, без нового retrieval. Baseline scorer/mapping загружаются из Git `5672a16c`, не из переписанных архивных runners.

## Правки

- `eval/evidence_quality_v2/semantic.py`: complete prose paragraphs одного утверждённого witness допускают отдельные citation spans. Line constraints вычисляются отдельно; один ранее contiguous witness не склеивается из разных файлов. Fenced examples остаются atomic. Output содержит отдельные `citation_bindings`, а не новую contiguous quote. Explicit multipart witness contract сохранён.
- Matching нормализует только inline links/emphasis, bullet markers, существующие table/layout presentation; quoted/code literal whitespace защищён. Не добавлялись синонимы, stemming, case folding или general paraphrase matching. Public source snippets не редактируются.
- `eval/evidence_quality_v2/grounded.py`: formatting-only mapper использует ту же нормализацию; по-прежнему отображает только полностью видимый original paragraph и не выдумывает native verbatim citations.
- `eval/evidence_quality_v2/revised_gold.py`: **единственная gold correction — uv-06**. Удалено требование примера `uv pip install wheel && uv pip install --no-build-isolation biopython==1.77`, которого вопрос не просит. Default isolation, missing dependency advice и preinstall/`--no-build-isolation` остались. Это явный opt-in overlay `revised_case(case)`; original frozen `cases.json` и protocol hashes не переписаны. MkDocs gold не сокращался.
- `tests/evidence_quality_v2/test_measurement.py` и diagnostic hash: отдельные citations, rendered list, preserved literal whitespace, numbers/identifiers/polarity/conditions/version controls, frozen MkDocs06/uv06 positives и отдельные quote/path/hash/snapshot mutations.
- `observer.py` и `audit.py` прочитаны, но не менялись: existing one-call observer и canonical snapshot validator уже выполняют нужные отдельные проверки.

## Replay тех же outputs

[Runner](replay.py), [summary](replay-final/summary.json), [raw hashes/provenance](replay-final/provenance.json). **0 retrieval calls**. Все 80 DocAtlas packets и 80 Grounded packets на каждом сохранённом limit 3/5; limit 1 в этом архиве отсутствует. Initial replay сохранён отдельно в `replay/`; final учитывает явные citation bindings.

| Frozen within-budget panel, 48 вопросов | Original sufficient / needs_review / insufficient | Revised |
|---|---|---|
| DocAtlas | 45 / 2 / 1 | **47 / 0 / 1** |
| Grounded limit 3 | 32 / 16 / 0 | **41 / 7 / 0** |
| Grounded limit 5 | 32 / 16 / 0 | **42 / 6 / 0** |

Во всех 80 DocAtlas packets sufficient 45→47, needs_review 16→14, insufficient 19→19; changed cases только MkDocs06 и uv06. Grounded changed cases перечислены в summary. Это recognized evidence sufficiency, не answer correctness и не улучшение retrieval.

Review queues учитываются отдельно даже при recognized sufficient evidence: final DocAtlas 50/80 cases имеют unreviewed material, Grounded 80/80. Нераспознанное не становится pass или доказанным regression. Manual разрешения остальных Grounded cases из аудита не перенесены в автоматический pass; нет blanket paragraph/list reconstruction из невидимого текста.

## Integrity и tests

- [67 passed](targeted-green.log): measurement, frozen corpus identity/witness truth, experiments, cost/answer controls.
- [Full eval directory](eval-suite.log): **154 passed, 2 failed**. Оба failures — Pebble runtime delivery в `test_readme_neutral_context.py`; [baseline eval-module replay](baseline-controls.log) на неизменном runtime даёт те же 2 failures (13 passed). Это не зелёный full suite и не исправлено в eval шаге.
- [48 frozen instrumented projections](frozen-integrity.json): **0 violations**, проверены snapshot binding и verbatim path/line spans через existing canonical audit. [Integrity runner](check_frozen_integrity.py) не делает retrieval.
- `content_sha256` сопоставляется с evidence-material snapshot, не SHA256 всего файла. Grounded mapper использует raw file digest как eval mapping provenance, а не native evidence-material hash; он не отправлен в canonical DocAtlas snapshot audit. Semantic sufficiency и citation integrity не слиты в один показатель.

## Ограничения и остановка

Formatting equivalence — объявленная узкая annotation-driven policy, не semantic judge. Неизвестные альтернативы остаются reviewable; supported witness не доказывает отсутствие других противоречий. Frozen-80 остаётся exposed regression panel, не независимый success gate. Новый language recall, qualification, ranking, budgets и scorer thresholds не менялись. Архив audit не перезаписывался. Следующий шаг 06 не начат; после шага 05 остановка.
