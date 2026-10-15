# Независимый критерий V3 — freeze до outputs

## Статус и граница

Oracle выведен вручную из новых исходных документов, до просмотра V3 outputs. V2 checkpoint, final review и protocol прочитаны. Семейства новые: кусочно-заданный расчёт счёта с арифметикой; независимо — направленный граф и аддитивный бюджет с разделением полномочий. Это не переименование seed/rigging/ceramic/ferry V2. Малый набор не доказывает универсальную numeric reasoning capability.

Роль C меняет только `admission-v3/review/`. Product/runtime/tests/models/host не запускаются. Только чтение артефактов и stdlib сборка/hash frozen данных допустимы. Последующее независимое review A/B и raw выполняется по отдельному запросу координатора. Новых агентов нет.

## Замороженные оси verdict

1. **Public positive delivery:** конечные snippets должны содержать достаточно исходного текста для всех запрошенных фактов/выводов. Числа вопроса не обязаны буквально повторяться в документе; арифметику разрешено делать только по явно связанным единицам, тарифу/направлению/владельцу. Передача единственного numeric facet не решает составной вопрос.
2. **Exact-witness delivery:** private oracle фиксирует конкретные дословные опоры, raw-document SHA256, character spans `[start,end)` в Unicode code points, 1-based inclusive lines и UTF-8 witness SHA256. Все обязательные witnesses считаются отдельно от semantic sufficiency. Не требуем произвольного числа документов; альтернативное entailment можно признать semantic PASS с объяснением, сохранив frozen witness FAIL. Пропущенный текст нельзя засчитывать по parent/full-file metadata.
3. **Unsupported-query source contract:** для замороженных unsupported numeric/relation/owner cases требуется `sources` отсутствующее/null/[] (нормализуется в пустое), `context_available=false`, `support_status=insufficient_evidence`. Непустой нерелевантный источник — отдельный FAIL независимо от правильного host отказа. Лексическое совпадение числа, акторов или мест не доказывает нужную relation.
4. **Host answer:** положительный ответ должен решить все запрошенные части, показать корректный числовой вывод и не добавлять неподдержанные обязанности. Negative host PASS — честный отказ от запрошенного неподдержанного affirmative/снятие ложной предпосылки; не обязательно молчание. Host refusal и expected empty-source — независимые столбцы. Host не запускался: до raw эта ось NOT_RUN, не PASS.
5. **Literal citations:** только точная подстрока фактически отправленного source snippet, с валидным evidence ID. Пробелы/newlines/Markdown не нормализуются для PASS. Отсутствие цитат в отказе — NOT_APPLICABLE, не доказательство positive completeness.
6. **Source policy/state:** actual project/scope/path/full-source hash/char+line spans/catalog/generation и public envelope hash проверяются отдельно. Public read не получает answer/edit authority: answer_supported/answer_available/edit_ready=false. Нет изменения source bytes/catalog/generation/storage rows и нет расширения source-policy grants. Foreign project, invented version или unbound operand — blocker, не relevance fix.

## Минимальные старые controls

Оставлены ровно `OLD_PRIORITY7` и `OLD_PRIORITY7_9` из `tests/test_project_context_quality_v2_protocol.py:466–561` и сохранённого `admission-full-20261012/live-default-off-controls/pytest/test_public_partial_context_prcurrent/qualification-review-proof.json`. Оба проверяют отсутствие числовой condition/relation, которую нельзя заменить общим packet-delivery фактом. Сохранены точные вопросы и все пять markdown исходных документов, provenance/hash — в `CONTROL_PROVENANCE.json`. Saved default-off output пуст, но это лишь историческое наблюдение, не новый V3 PASS. Compound/Setext/OtherAPI не входят в этот минимальный numeric срез и не объявляются защищёнными текущим пакетом.

## Review A/B и accounting

До holdout фиксировать implementation identity, contract A/B, defaults/opt-in, admission boundary и параметры. Проверять отсутствие naked numeric-guard removal, relation/owner widening, ответа/действия по model-score authority. Сравнение — по одинаковым frozen source bytes/questions/project scope; фиксировать реальные подготовки, публичные вызовы, forwards/host attempts/UNKNOWN и конечные snippets. Не подменять retrieval/storage/validation mocks, не объявлять сохранённый текст offline public evidence. Calibration/holdout/control — разные denominators. Без нового исполнения baseline/V3 quality пока NOT_RUN. Не менять oracle/вопросы после outputs; обнаруженный избыточный witness constraint объяснять отдельной semantic осью, не переписывать freeze.

## Разделение доступа

Авторам patch доступен только `inputs/` и этот общий criteria. `private/oracle.json` содержит holdout labels и остаётся у reviewer. `private/calibration_labels.json` не содержит holdout. `FREEZE.json` связывает файлы hashes, но не раскрывает labels. Это процедурное разделение, не файловая ACL sandbox; запрещение чтения private следует явно передать участникам. Freeze подтверждает исходные данные до V3 outputs, а не принятие ещё не увиденных контрактов A/B.
