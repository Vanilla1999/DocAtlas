# Owner delivery: протокол до реализации

Baseline ea7eef380eb2b0a11b0216063939b2b8ae1773de; только next07-feasibility-audit.
Порядок: зафиксировать baseline → правка → review → native run. N10 не запускается по явному решению пользователя; старый verdict не повышается.

## Единственная заменяемая ответственность

Ранее целый greedy search chunk требовался одновременно как delivery unit и как полный parser owner. Теперь поиск/ranking прежний, но результат после ranking материализуется в минимальный непрерывный диапазон, содержащий полностью все parser-owned секции, пересекающиеся с hit. Он содержит исходный hit и исходные ограничения без переписывания bytes.

Парсер секций — существующий parse_markdown_parents. Повторяющиеся headings различаются offsets, не именем. Конец half-open hit не захватывает соседний раздел. Это структурная сохранность известных границ, не универсальное доказательство полноты смысловых зависимостей.

Производитель и read consumer используют одну функцию вычисления диапазона. Consumer выводит допустимые единицы из raw snapshot и существующего splitter заново: boolean metadata или выдуманные routing IDs не выдают разрешения. SourceReferenceContext/current catalog/read guards проверяют новые bytes/offsets как прежде.

Разрешённые code files: v2plan/next07_grounded_candidate.py, новый v2plan/next07_owner_delivery.py, новый v2plan/test_next07_owner_delivery.py. Документы/артефакты в v2plan и isolated workflow запуска отдельно. Wiring, first_fit, production исходники, evaluator, public schema, old tests и labels не изменяются.

## Обязательные проверки

- Hit в начале, середине и конце длинной секции → целая секция с поздним restriction.
- Несколько пересекаемых секций → точный непрерывный исходный диапазон, не склейка.
- LF/CRLF, Unicode, повторы текста/headings и fence с символом #.
- Неверный span/hash/content и потеря хвостового restriction не получают owner approval.
- Полный новый диапазон заново проходит source identity/scope/version/freshness/snapshot/exact guards; отрицания и existing opposite-state checks не удаляются.
- Порядок/count/bm25 score retrieval hits не меняются; исходные spans сохраняются в research trace.
- P1/P2/P3 через реальный MCP и исходные 80 questions/corpus.

## Review gate

До native execution: проверить полный diff, неизменность rank_rows/first_fit/source guards, отсутствие corpus-specific значений, наличие единого producer/consumer mapping, сохраняемые ограничения и source rebinding. Review авторский, не независимая внешняя оценка. Сохранить REVIEW_RU.md; не объявлять результат тестов, которые ещё не выполнены.

## Конечные результаты

OWNER_DELIVERY_VALIDATED: structural positives/negatives и native target проходят; 80/80 исполнены, source audit чистый, поддержанные baseline C facts не потеряны и structural-row потери уменьшены. Это локальное завершение выбранной обязанности.
REJECTED: valid candidate теряет прежний C факт, вводит source/condition нарушение либо проваливает обязательный structural positive/negative. Не подгонять правила после результата.
BLOCKED/PARTIAL: объективно отсутствует исполнение/данные; сохранить всё измеренное, не считать неизвестные IDs пустыми множествами.

Полная приёмка DocAtlas отдельно требует всех обязательных прежних фактов и quality negatives; N10 исключён из этого запуска, поэтому общий rollout NOT_AUTHORIZED даже при локальном успехе.
Размеры выдачи измеряются, не ограничиваются 800/3. Resource/search caps остаются. Нельзя компенсировать lost IDs новыми gains или преобразовывать needs_review в supported.
