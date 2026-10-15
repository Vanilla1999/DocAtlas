# PR #211: отрицательная fixture с ранним отказом

## Основание

На опубликованном `eb2c4f3b3e0065110a1bfe2c855e4a05803fa37a` существующий pytest core run [38010627863](https://github.com/Vanilla1999/DocAtlas/actions/runs/38010627863) завершился на каждой из Python 3.11, 3.12 и 3.13 с **6063 PASS / 1653 FAIL / 0 ERROR / 10 SKIP**. Это незелёный CI.

JUnit observation для `test_path_only_projection_uses_the_current_exact_topic_guard` показал, что positive ветвь уже прошла сохранённые проверки полного факта, пути, SHA-256, окна, coverage и consent. Failure произошёл в первом negative `filename_only`: настоящий ранний veto корректно не вызывал projector, но wrapper `capture_reference_case` требовал непустой `projection_attempts` для любого `docs_context`.

Наблюдение получено из существующих JUnit artifacts через reader job [114091874403](https://github.com/Vanilla1999/DocAtlas/actions/runs/38010627863/job/114091874403). Оно относится к этому test case; не выдаёт полный проход модуля или всех пяти read fixtures.

## Изменение

Внутри только этого теста отрицательные вызовы используют существующий underlying `tests.docs._global_evidence_fixtures.capture_fixture`. Он вызывает тот же настоящий public handler и проверяет каждую фактически имеющуюся проекцию, source paths/line spans и отсутствие answer/edit полномочий. При раннем veto допустимо отсутствие projector attempts.

Positive вызов продолжает использовать более строгий `capture_reference_case`. Все четыре отрицательных вопроса, source bodies и assertions error/kind/status/sources/coverage/authority, а также все positive full-fact/hash/window assertions сохранены побайтно. Общие wrappers и production не изменены. Функции или pytest cases не удалены и не добавлены.

## Review manifest

| Path | Base | Proposed |
|---|---|---|
| `tests/docs/test_context_projection_boundaries.py` | `da596b3c19c73a21788b4871e2564d622dfd7ae7` | `61e303d5d9686f1f19a3809e104e6f9975b1fdba` |
| `v2plan/PR211_EARLY_VETO_FIXTURE_RU.md` | NEW | эта запись |

Mode обоих файлов — `100644`. Root проверил exact inverse двух изменений и create/fetch roundtrip; contracts reviewer независимо сверил underlying fixture `ce01e23f813c876921be2995f2ce19e906e3c27d` и wrapper `7fd30e607488b9841e3fd78f146af737c6c1c04e`: **static APPROVE**.

## Acceptance

Runtime после исправления ещё не выполнен. Следующий общий CI должен проверить эту неизменённую группу assertions. Предыдущий failure не превращается в PASS из статического review; required CI, downstream, installed/client acceptance остаются отдельными требованиями.
