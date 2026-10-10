# Кандидат: сохранить полезный unresolved context до публичной проверки

Дата: 2026-10-06. Base: `755b33cdaff1a4ef8e9ccfc22bee0ca4e351c6fd`.
Статус: **CANDIDATE, NOT MERGE READY**. Владелец разрешил commit/push этого
кандидата вместе с тестами и документами в активный #211; разрешения merge нет.

## Причина Pebble failures

`query_project_docs` возвращает один current owned source с нужной цитатой.
`project_context_pack` первоначально тоже содержит источник. Затем
`rerank_project_doc_chunks` отбрасывает его: нет qualified query IDs, а разрешённые
`context_candidate_ids` до исправления формировались только через set-context
variants. После rerank context pack пуст. Поэтому полезный текст не достигает
существующего публичного retrieval-only fallback.

Диагностическая проба, сохраняющая кандидат только в prefit, показала:
публичная выдача содержит полезную цитату, `retrieval_coverage=partial`,
`covered_query_ids=[]`, `answer_supported=False`, `answer_available=False`,
`edit_ready=False`. Это не требует нового proof rule.

## Что меняет текущий кандидат

- `_project_context_service_part01.py`: при **отсутствии любых qualified candidates
  и checked set variants** сохраняет тематические unresolved candidates для rerank.
- `context_hint_policy.py`: новая retention preference использует существующие
  ограничения hint fallback и source policy; body matches вычисляются заново,
  поддельные cached traces не дают права на сохранение кандидата.
- Final projection по-прежнему самостоятельно проверяет eligibility, source
  windows, attribution и DTO budget. Retention ID не становится answer proof.
- Ни hard exact/structured requests, ни semantic qualification rules этим diff
  не ослаблены. Body-term floor остаётся прежним; это не удаление эвристик.
- Существующие tests/gold/guards/limits/workflows не изменены. Новые tests вынесены
  в отдельный файл и зарегистрированы отдельным hash-bound diagnostic shard.

## Отвергнутая широкая попытка

Первая попытка сохраняла такие candidates и при наличии qualified sources.
Полный core показал два новых failures:

- `tests/docs/test_evidence_set_delivery_acceptance.py::test_native_required_delivery[pydantic-03]`;
- `tests/docs/test_pydantic_direct_context.py::test_original_direct_question_delivers_all_four_strict_mode_controls`.

На отдельном detached baseline `755b33cd` эти проверки проходят. Приоритет
дополнительного текста вытеснял полезные источники. Широкая попытка **не принята**;
она заменена условием empty-prefit fallback. После сужения оба теста проходят.

## Выполненные проверки текущего кандидата, Python 3.12

| Проверка | Результат |
|---|---|
| Pebble + новые guards + ranking + native delivery/Pydantic | 57 PASS |
| Полный offline core | 15 FAIL, 5290 PASS, 10 skipped, 622 deselected |
| Полный advanced pytest | 622 PASS, 5315 deselected |
| Legacy live + lineage check | Coverage 11 < 12; FAIL; до patch было 10 < 12 |
| Adversarial gate | 27/28; 3 violations; FAIL, прежний module-scope case |

Core оставшиеся failure IDs совпадают с исходным CI roster за вычетом двух Pebble.
Это локальное сравнение с CI, не paired full-core baseline в том же окружении.
В отдельном baseline выполнены только Pebble/native-delivery/Pydantic — 24 PASS,
2 прежних Pebble FAIL. Сравнение с main ещё не выполнено.

Adversarial: `module_scope_rejects_project_policy_detail` выдаёт `status=ok` вместо
`insufficient_evidence`; context и trajectory projection 380 > 300 tokens.
Этот дефект данным patch не закрыт. Advanced pytest PASS не закрывает полный
advanced-contract job: его legacy floor всё ещё красный.

### Команды

```bash
DOCATLAS_OFFLINE=1 .venv/bin/python -m pytest -q tests/docs/test_unresolved_context_prefit.py tests/evidence_quality_v2/test_readme_neutral_context.py tests/docs/test_evidence_set_delivery_acceptance.py tests/docs/test_pydantic_direct_context.py tests/docs/test_context_ranking_regressions.py
DOCATLAS_OFFLINE=1 .venv/bin/python -m pytest tests/ -m 'not advanced and not live and not live_network' -q --tb=short
DOCATLAS_OFFLINE=1 .venv/bin/python -m pytest tests/ -m advanced -q --tb=short
DOCATLAS_OFFLINE=1 .venv/bin/python eval/project_context_quality_protocol.py --live --report-only --output /tmp/opencode/pr211-prefit-narrow-legacy.json
.venv/bin/python scripts/check_legacy_project_context_lineage.py /tmp/opencode/pr211-prefit-narrow-legacy.json
DOCATLAS_OFFLINE=1 .venv/bin/python scripts/run_agent_developer_adversarial_gate.py
```

Локальные полные logs/XML: `/tmp/opencode/pr211-prefit-narrow-{core,advanced}.{log,xml}`;
legacy: `/tmp/opencode/pr211-prefit-narrow-legacy.{log,json}`;
adversarial: `/tmp/opencode/pr211-prefit-narrow-adversarial.log`.
Baseline: `/tmp/opencode/pr211-prefit-baseline-20261006` (detached, без новой ветки),
его targeted log: `/tmp/opencode/pr211-prefit-baseline-targeted.log`.
Это временные артефакты, пока не committed evidence archive.

## Точные hashes проверенного diff

SHA-256:

| Файл | Hash |
|---|---|
| `docmancer/docs/application/_project_context_service_part01.py` | `76cf3854d1dda48553ecb64a166d9f38bcfb98d4743ad1872d7ff29ddcf09307` |
| `docmancer/docs/domain/context_hint_policy.py` | `fe9f41303b17e8fb24125a09b54d30d292a5cfbe489208c0e712e6e53d0e81a9` |
| `tests/docs/test_unresolved_context_prefit.py` | `72a4b0d1c4b2d3757ac4348f6d824b2189f8431fb3e238ed3de0c567a2c2c8f1` |
| `tests/diagnostic_labels.unresolved_context_prefit.json` | `1afa68437880c79961b3a91b18b8aa84d60e5ac569d0621b19c7e256bd29d118` |

## Grounded и следующий шаг

Grounded доставлял полезную Pebble-цитату уже до patch; теперь этот локальный
разрыв устранён на проверенных fixtures. Чужой scope/DTO budget Grounded API этим
сравнением не покрыты; adversarial нельзя честно пометить «проблема у обоих».

Далее: независимо оценить candidate diff и проверить его относительно main;
разбирать оставшиеся 15 core failures и последнюю недостающую legacy case.
После окончательного scope — полный required CI на фиксированном SHA и owner
approval. Независимое review и merge пока не выполнены. Публикация кандидата
разрешена владельцем отдельно и не означает прохождения обязательных gates.
