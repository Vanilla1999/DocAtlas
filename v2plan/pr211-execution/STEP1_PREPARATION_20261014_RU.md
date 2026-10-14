# PR211: подготовка измерений до исправления выбора контекста

Исходный head: `c35aabe21397fb378d29eb26bb58d5ac6fceb622`.
Изменения ограничены тестами, evaluator и его изолированными fixtures.
Runtime selection/budget/sufficiency/model code и main не изменяются.

Удалены31 test-function /46 core-cases:21 FAIL и25 PASS. Это retirement
отменённых/private/synthetic проверок, не21 исправление продукта. Список,
основания и hash базового JUnit: STEP1_TEST_MIGRATION_20261014.json.
Общие helpers для оставшихся consumers и все исходные SKIP сохранены.

Observer использует текущие acquisition/query/projector границы и существующую
ограниченную finalization-трассу. Старые ranking/fragments/expansion помечены
retired, а не успешно пройденными пустыми стадиями. Старый private replay
удалён; существующий prepare/MCP/SQLite сценарий проверяет off/on/off, факт,
один retrieval/validation и восстановление observer. Один новый интеграционный
сценарий проверяет frozen-каталог через Git mirror, cold consent, реальную
SQLite подготовку, публичную выдачу и неизменность origin.

V2 получает отдельный catalog.frozen.yaml: точные исторические байты с прежним
hash независимого lock. Root catalog, вопросы, gold, locks и floors не меняются.
Замена применяется только к изолированному mirror, записывается в provenance
и проверяется перед реальной подготовкой. Исходная версия и hashes приведены
в STEP1_FROZEN_CATALOG_20261014.json.

Subprocess-проверка pytest-selector указывает на существующий публичный
сценарий и проверяет collection, не повторяя его продуктовый runtime.
Ожидаемый core roster1547-46+1=1502; требуется собственная CI collection.
Общая историческая цель−40% имеет baseline8291: повторная−40% от остатка не
требуется. Весь остаточный набор не объявляется построчно переклассифицированным
по этому ограниченному manifest. Новых unit-тестов нет.

V40/P03/E01/negative-case критерии не меняются. Завершённый25-case отчёт V2
означает работоспособное измерение, а не прохождение quality floors.
Результаты конкретного candidate SHA сохраняются отдельно в Actions.
