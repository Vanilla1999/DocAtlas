# PR #211: оставшиеся проверки полного recovery output

Статус: static review завершено; следующий CI должен подтвердить результат на опубликованном SHA.
Production в этом slice не меняется. Новых test functions и параметров нет.

## Основание

Последний полностью прочитанный core на `c1e058cb51072f02620329000e2d68706a96bd67`:
[CI 37995500411 / JUnit reader 114043788747](https://github.com/Vanilla1999/DocAtlas/actions/runs/37995500411/job/114043788747).
Во всех Python 3.11/3.12/3.13 совпадают counts: read tails 56 PASS/2 FAIL; unit helpers 47 PASS/1 FAIL; MCP output contract 5 PASS/1 FAIL.
Это четыре прежних failures. Фактические текущие producers уже сохраняют полный output;
ошибочны оставшиеся ожидания обрезки 220/160 символов, 8 terms, 1500-symbol constructor cap и 256-token module locator.
Пользователь отменил произвольные output ceilings: стоимость измеряем и сокращаем без потери смысла и guards.

## Изменения

1. `test_dictionary_exit_read_tails.py`: сравниваем полный question.strip() и точный recovery query term.
   Для всех шести исходных вопросов recognized_spans пусты, что отдельно проверено по текущему requirement builder.
   Exact path Guide.md остаётся scope binding и не превращается в обязательный body symbol.
   Две origin-параметризации и прежние запреты query synthesis, automatic execution и repeat context call сохранены.
2. `test_dictionary_exit_unit_helpers.py`: длинный текст без согласованного digest по-прежнему отвергается как hash mismatch.
   В том же существующем тесте отдельный длинный Unicode unit с representation_bounded=False должен сохранить весь текст,
   ограничивающий хвост, char offsets, SHA-256, deterministic identity и materialization.
   Expected identity вычисляется непосредственно из kind/start/end/text; сохранены immutable, invalid-offset и остальные negative controls.
   Совместимый bounded parser по умолчанию и operational MAX_UNITS не меняются.
3. `test_mcp_output_contract.py`: исходный locator длиной около 20 тысяч символов и recovery action сохраняются целиком.
   Сравниваются все поля, кроме пересчитанного estimated_tokens; estimate должен точно соответствовать фактическому payload.
   Сохраняются answer_supported=False, answer_available=False, auto_execute=False и подтверждение неизменных action grants.
   Обычная administrative compaction и guards невалидных patch packets остаются прежними.

## Review и acceptance

Root проверил actual failures и source contracts. Независимый reviewer отдельно прочитал recovery.py,
requirement/query terms, AnswerUnit/_make_unit/materialize и оба recovery binders; блокеров нет.
Сохранены прежние 12 + 8 + 6 test function names и все decorators/expanded params.
Это миграция четырёх ожиданий, а не сокращение количества тестов и не evidence runtime PASS.
Новых dependencies, production imports, локальных pytest/AST/runtime запусков нет.

| Файл | Base blob | Proposed blob | Mode |
| --- | --- | --- | --- |
| tests/test_dictionary_exit_read_tails.py | a0624287b9a9d29079bb40b3576328678628f99c | 645c3b9a747e7e9bc933608ee045d66659b4c5a3 | 100644 |
| tests/test_dictionary_exit_unit_helpers.py | 774233422f36c2f480f67422e890d7611b5f713e | 193dcea337e16653d62705eb7084cd1ccfc62cff | 100644 |
| tests/docs/test_mcp_output_contract.py | 5ebd8552531bcf45faa199284dc0112c8f04b14c | 1a9fc2b50d97d42717cea5c83e6d623135f34de9 | 100644 |
