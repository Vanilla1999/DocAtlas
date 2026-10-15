# PR211: убрать оставшиеся жёсткие output ceilings из тестов

Политика владельца — минимизировать стоимость при сохранении исходных фактов и guards. В 44 тестовых файлах изменён 81 assert: удалены только верхние границы 800 output tokens, эквивалентных 3200 UTF-8 bytes и трёх model-visible sources. Положительные нижние границы, kind/edit flags и все остальные assertions сохранены. Новые пустые или тавтологические тесты вместо этих ceilings не добавляются.

Полный AST после удаления только этих cost clauses и 16 ставших ненужными imports совпадает с текущими файлами. Исходные вопросы, authored fixtures, function names, parametrization, source/citation/hash/span/consent/authority guards и runtime configuration не меняются. Ни один test function или case не удалён в этом slice.

Центральные retrieval-evidence/V2 cost reports и continuation JUnit properties продолжают измерять полный DTO. Existing fidelity/source-removal/guard mutations остаются обязательными. Это отмена output policy, а не утверждение роста recall или прохождения остальных старых тестов.

Сохранены явно заданный internal query work budget 800 в test_docs_service_part02 и frozen within_budget classification исторической corpus fixture. Некоторые совместимые вызовы передают max_tokens=800 валидатору; текущий validate_model_visible_projection не читает этот аргумент и не вводит через него потолок.

Независимый agent_fixtures_impl review APPROVE: все 81 delta и полный оставшийся AST сверены, operational budgets не затронуты. Подробный diff ledger и независимая сверка сохранены рядом. Статические проверки PASS; новый runtime ожидается из обычного CI.
