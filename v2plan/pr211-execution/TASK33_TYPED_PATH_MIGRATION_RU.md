# Task33: текущий delivery и явно заданный путь

## Контракт и причина

Исходный запрос `Fix module.py.` создавал обязательное требование буквального `module.py` внутри source body, хотя host уже явно задавал тот же путь как `required_target_paths`. У файла `module.py` с содержимым `VALUE = 1` правильная identity, но имя файла не обязано повторяться в теле. Это отдельная ошибка построения требований, а не повод дописать имя файла в gold или принять partial как успешную доставку.

В `docmancer/docs/application/evidence_requirements.py` добавлено ровно девять строк. Только полное совпадение extracted term с явно переданным evidence/target path (после нормализации разделителей) помечает query term как необязательный `declared_path`. Его ID, value, исходный span и extraction provenance сохраняются. Само отдельное `evidence_path` / `target_path` остаётся mandatory. Свободный dotted symbol без точного host path и независимо заданные public `exact_term` / `required_fact` сохраняют прежнее содержание и обязательность.

## Контроли в существующем тесте

Расширен существующий `test_requirement_set_hash_is_deterministic_under_input_ordering_differences`; его исходные assertions о hash и перестановках сохранены.

- Без host path `module.py` и `Client.open` остаются content obligations.
- Для обоих явных аргументов сохраняются ID, `module.py`, span `(4, 13, "module.py")`, provenance и mandatory path.
- Источник с верным путём, но без явно заданного доказанного content obligation остаётся partial с `visible_content_assignment_required`.
- Отдельный полный факт `VALUE = 1` даёт complete, при этом `edit_ready=False`.
- `other.py` и `module.py.old` не закрывают обязательный путь; неверно объявленный путь не снимает обязательность исходного имени.
- Независимое public требование `module.py` обоих типов остаётся mandatory и missing, когда filename отсутствует в body.

Проверка source-кода подтвердила цепочку: `build_action_packet` передаёт требования selector, identity assignments не имеют `unit_id`, и отсутствие content assignment добавляет `visible_content_assignment_required`. Ослабления этого guard нет.

## Три миграции Task33

1. Required-once positive использует настоящий валидированный packet v4 и его model-visible projection. Исходные запрос `Fix module.py.`, два source facts и реальное ожидаемое изменение `VALUE = 1\n` → `VALUE = 2\n` сохранены. Длинный текст, ранее вставленный в удалённый unbound acceptance field, становится отдельным явно созданным source window. Проверяются полные тексты всех трёх источников, SHA-256 и точное равенство JSON, фактически переданного model callback. Размер >6000 символов остаётся проверкой сохранения длинного текста, output ceiling не вводится. Host `allowed_write_paths` задаётся отдельно; packet сам не даёт edit grant.
2. Required-once negative получает валидный failure/unavailable projection вместо malformed legacy envelope. Исходное содержимое файла, rejected edit и отрицательный policy audit сохранены.
3. Isolated-worker и Task33C проверки читают текущие sources/result/completeness. Objective и snapshot fingerprint проверяются в реальном selector request. Четыре исходных Task33C текста не изменены: acceptance phrase, присутствующая только в metadata, не становится фактом. Отдельный явно заданный полный literal даёт complete без edit grant; hashes, untrusted data и trajectory contract проверяются.

## Review и состав

База чтения: `10277b269ff686320cb191da93747b73e1f37f4b`. Root и отдельный reviewer прочитали production contract, четыре diff, guards и настоящий adapter request/response путь. Имена и порядок всех существующих test functions сохранены: evidence selection — 33; adapter — 11; isolated — 7. Новых collected test functions нет.

| Файл | Исходный blob | Proposed blob |
| --- | --- | --- |
| `docmancer/docs/application/evidence_requirements.py` | `969a0a9259ff7cf4c0f4b14f4aaaac2de83186f3` | `1c359345f314ddf02b2674866c2847af784d554b` |
| `tests/docs/test_evidence_selection.py` | `0ab75386a484fa1c7e3a27c8ba66236bc343d80a` | `2435f620b36bc31a74dc9a1247baabfb1d4505e2` |
| `tests/task_level/test_github_models_adapter.py` | `aa78433bd632ffa5872803b26f2db80dc5c2007e` | `920bd03a990a1040e34784a197b6ec658b712dc6` |
| `tests/task_level/test_task33_isolated_delivery.py` | `3e00607b9391bbaf3329f79cffc414a421f99e79` | `09d1db9bcdaf4106c5df5f47e264641370cf52b3` |

Локальные imports, AST/compile, pytest, server или provider calls не выполнялись. Runtime-результат для этого slice ещё не получен: необходим обычный CI на опубликованном SHA, включая Task33, focused existing requirement node и required gates. Source review не объявляется acceptance.
