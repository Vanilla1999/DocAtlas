# Пункт 5: один изолированный read decision — результат

2026-10-03. Контракт до реализации: [UNIFIED_READ_CONTRACT_RU.md](UNIFIED_READ_CONTRACT_RU.md).
Исходный анализ: [ADMISSION_DIRECTION_REVIEW_RU.md](ADMISSION_DIRECTION_REVIEW_RU.md).

## Что выполнено

- `unified_read_admission.py`: один research read decision, без вызова
  `qualify_evidence` и без интерпретации его proof reasons.
- Existing source eligibility, prepared literal/verified-owner subject,
  native compiler/applicability и один existing locality predicate сохранены.
- Нет новой grammar, thresholds, aliases, relation/library rescue или fallback.
- Return только `ReadContextAdmission(allowed, reason)`. Proof/coverage/edit
  остаются вне read decision.
- В `AGENTS.md` закреплено обязательное правило: мы уже переусложнили; новая
  правка должна заменять решение, не добавлять очередную ветку.

**Ограничение:** это упрощение isolated read boundary, не миграция всех production
prefit/disposition/projector callers. Старые runtime consumers не удалены.
Existing lexical locality сохраняется как control policy; не объявлена научно
доказанным semantic detector. Её recall проблема не решена этим шагом.

## Проверки

Red: два первых behavioral tests отвергли допустимый partial context на stub.
Green: 28 новых controls, включая proof-call prohibition, exact source/request
mutations, clipping, heading/echo/scattered terms, отрицательный documented факт,
state match/wrong/missing, verified-owner subject vs body literal.

Общий focused inventory: **115 passed**, existing `asyncio_mode` warning.
Existing тесты и expectations не переписывались. `git diff --check` чист.
Ruff не выполнен: `No module named ruff` в выбранном Python 3.12 environment.
Полный regression, current live Kotlin и held-out не запускались.

## Один paired replay при 1500

`unified_read_replay.py` читает complete **native retrieved-candidate captures**
из archived baseline. Это не passage/owner inventory API 01–04.

- 80 cases, 429 distinct request-bound candidates после exact span deduplication.
- Capture order сохранён; sources/char spans сверены с frozen documents.
- Rebinding использует тот же archived snapshot/generation; DB read-only.
- Оба arms имеют один inventory, native compiler, порядок, serializer/selector
  и final source/permission проверки. Typed research compiler не подключён.
- Existing selector rechecks решение перед final rendering.

| Метрика | Current native read function | Unified research read |
|---|---:|---:|
| Cases | 80 | 80 |
| Packets | 18 | 18 |
| Supported required claims | 11 | 11 |
| Cases с review queue | 11 | 11 |
| Packets в 8 unanswerable cases | 0 | 0 |

**Actual payloads совпадают на всех 80 cases.** Recovered claims: 0; lost: 0.
Maximum whole-DTO units 632 ≤1500. Answer/edit flags не повышены.

Изменились 10 first-refusal reasons, не allow/reject outcomes:

- 4 `fastapi-01` candidates: proof-local отказ → native applicability отказ.
- 6 `httpx-06` candidates: proof-local reasons → locality refusal.

Это демонстрирует, что proof reason whitelist не нужен как отдельный read veto
в измеренном inventory. Но снятие такого coupling **не улучшило recall**.

## Почему baseline здесь 11, а не 49 или 15

- 49 — исторический **полный native pipeline**, с qualification/typed preferences
  и другими selection branches.
- 15 — прежний owner/passage **research candidate** на другом inventory.
- 11 — freshly evaluated **native read function alone** на captured native
  candidates с одинаковым experimental renderer/selector и budget 1500.

Нельзя выдавать 11→11 за parity полного production pipeline с 49 supported.
Этот trial проверяет именно isolated read decision; приёмка его как замены
всех native routes потеряла бы доказанные возможности существующей системы.

Полезные known partial facts `pydantic-07`, `ruff-07` сохранены в обоих arms;
их private tail остаётся `needs_review`, не supported. Другие partial losses
не восстановлены. Ноль packets на одном шаблоне восьми negatives не доказывает
универсальную abstention/safety.

## Решение: не наращивать этот вариант

**Пункт 5 выполнен как минимальный isolated contract/prototype и paired проверка.**
Proof/read обязанности разделены, но retention не улучшен. Production replacement
не разрешён; runtime route и 01–04 не менялись.

Не добавлять теперь typed-local rescue обратно в этот read route ради `httpx-06`:
это вернуло бы конкурирующие обязанности. Не уменьшать term/pair threshold.

Открытый следующий вопрос — общий read-relevance контракт, способный сохранить
полезный контекст и реальные negative expectations. Его следует сформулировать
до следующего кода. Если для него вновь нужны exceptions под cases, вариант
отклонить, рабочий native pipeline сохранить.

## Артефакты / воспроизведение

`artifacts/unified-read-native-1500/`:

- `results.json`: request-bound native inventory, оба packets/assessments/decisions;
- `summary.json`: transitions, recovered/lost IDs, negative/review counts;
- `provenance.json`: source protocol, capture/code hashes, отсутствие retrieval
  replay и compiler changes, scope isolated read arms.

```bash
PYTHONPATH=. /usr/bin/python3.12 v2plan/unified_read_replay.py --input /home/viadmin/.cache/docatlas-experiments/grounded-budget-20261003-06 --output v2plan/artifacts/unified-read-native-1500-NEW
/usr/bin/python3.12 -m pytest -q tests/docs/test_unified_read_admission_probe.py
```

Новый output обязателен. Historical artifacts/gold/user experiments не изменены.
Commits и rollout не выполнялись.
