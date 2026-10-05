# PR-1: техническая поправка регистрации тестов

Дата: 2026-10-05. Предыдущая revision: 71da4adb985f24021489c1dd8a9d18850f3fe8c9.
Авторское ревью до повторного CI. Это не изменение алгоритма или ожиданий.

Исходный CI run 37298191615 сохраняется. Job 111724364402 (Python 3.12)
прочитан полностью: `diagnostic_unclassified modules` перечисляет ровно три
новых тестовых модуля; collected 5929 items; `no tests ran`; exit 4.
Это моя ошибка интеграции тестов, НЕ содержательный отказ исправлений.
Результаты остальных jobs сохраняются отдельно, не объявляются общим PASS.

Добавляется только tests/diagnostic_labels.output_integrity.json через уже
существующий reviewed-shard механизм tests/diagnostic_labels.py. Новые три
модуля получают явную классификацию и hash base node IDs. Основной manifest,
его прежние labels/overrides/hashes, pytest hooks, tests и product code неизменны.
Shard не может переопределять существующие записи: штатные collision checks
остаются. Нет skip/xfail, снятия guard или перевода существующих tests в другой gate.

Все три модуля включены в тот же штатный core suite. Label serialization
для terminal/SDK проверок не заявляет semantic correctness; behavioral в
constructor/audit означает проверку выполнения этих функций, не ответов LLM.
Hash = SHA256('\n'.join(sorted(unique base nodeids))); parametrization IDs
исключены штатным способом. Имена функций получены AST из неизменных тестов.

Allowlist PR расширен ровно одним технически обязательным файлом регистрации.
Ожидания и resource budgets не меняются. Следующий CI не переписывает первый
invalid run. Stage 3 и merge по-прежнему требуют весь CI и отдельное ревью.
