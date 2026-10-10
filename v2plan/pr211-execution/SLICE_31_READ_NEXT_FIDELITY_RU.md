# PR211: read_next после снятия output ceiling

Base: `589a6366e33278fe542a0e3c971d2502e5e9f99f`.
Файл: `tests/docs/test_docs_context_read_next.py`.
Base blob: `89c4ed96ea17315563d8b7833a4fbb099faa4f35`.
Proposed blob: `9826ba4b27bfe203dffa05917fcdf0d6345ef536`.

## Доказанная причина

Обычный CI на ec85a496, JUnit diagnostics job 113973962296, показал для Python 3.13 этой семьи 22 PASS / 9 FAIL. Восемь реальных continuation-сценариев проходят quality, no-authority, snapshot validator, project/path и raw-file hash, затем расходятся со старым фиксированным диапазоном: фактически 18–25 вместо 12–25. Старый сценарий budget omission получает пустой read_next.

Фиксированные output ceilings отменены владельцем. Разбиение цитаты по старому output budget больше не является контрактом. Настоящий resource-read bound 600 токенов остаётся.

## Что изменено

Только две существующие test functions. Все 31 concrete cases, имена, параметризации и исходные вопросы сохранены. Helpers с документом polling, direct explanation и code fixture побайтно не менялись.

1. Реальный source обязан содержать точные raw bytes префикса от строки 1, включая все прежние обязательные строки 1–11. Дополнительные строки цитаты допустимы. Continuation начинается после видимого префикса, до конца файла покрывает весь оставшийся суффикс и может пропустить только пустые разделители. Ни число 18, ни новое output ceiling в oracle не добавлялись.
2. Исторический oversized example теперь обязан полностью присутствовать в sources: исходный code block из 183 строк, включая все 180 comment lines, точные ranges, project identity и snapshot binding. Полный source не требует дублирующего read_next или выдачи range capability. Пустой либо укороченный source не проходит новый positive.

Сохранены actual SourceReadController/read_docs_resource, exact raw snippets, SHA, URI, project/catalog policy revocation, остановка после отказа, resource bound 600, legacy component-proof negatives, retrieval_only/cite_only и запрет answer/edit authority.

## Проверка и границы

Source-only сравнение подтвердило изменения ровно двух функций и сохранение остальных байтов. Родитель независимо одобрил diff. После отказа local executor AST, project imports и runtime не выполнялись.

Runtime нового blob ожидается в обычном PR CI. До его результата не утверждается, что все девять failures закрыты: если пустой read_next вызван действительной потерей example, строгий full-code positive останется красным и выявит product defect. Предыдущий CI остановился на первом range assertion, поэтому дальнейшие reader/revocation assertions нового prefix пока не исполнены.
