# PR #211: однобуквенные явно цитированные literals

Статус: узкое выравнивание двух текущих lexical APIs; runtime PENDING.
Base: `1c6c2c8454cdd6fe797fe80e85f3b651aef01a0a`.
Production path: `docmancer/docs/domain/query_terms.py`.
Base blob: `5eecc570a8c3317fc762b9730a5c1643978f07ae`.
Proposed blob: `8d047ff87066d43416ae5102038237605ada0a28`.

## Контракт и причина

`query_reference_binding.py::query_mentions` уже принимает непустой quoted
literal длиной1–160 символов, сохраняет его исходные offsets и назначает явную
symbol identity. Exact source blob:
`61257ce508a737d4fa21a2580b49673f5c900ec5`.

В `query_terms.py` два quoted patterns вместо этого требовали2–160:
technical-anchor extraction и typed exact-term extraction. Поэтому явно указанное
имя `с` попадало в mention API, но исчезало из hard_exact и anchors. Это
расхождение формы одного явно заданного literal, не вывод роли из обычного текста.

Существующий `test_explicit_literal_keeps_identity_and_original_offsets`
проверяет именно это имя и обе поддерживаемые quote формы. Последний полный
corea348 показывает у `test_admission_role_boundaries.py`28PASS/4FAIL.
Два случая с однобуквенным quoted именем объясняются этой границей.
Два других ожидания bare-capitalized hard_exact относятся к отдельной проверке
текущего контракта; этот slice не объявляет весь модуль зелёным.
Current1c6 full core ещё не завершён при подготовке slice.

## Изменение и сохранённые границы

Меняется только нижняя граница длины двух существующих quoted patterns:2→1.
Это соответствует уже существующему mention grammar.
Пустые quotes по-прежнему не создают identity, верхняя input граница160 сохранена.
Исходные символы, Unicode, negation/connectors, unquoted token rules,
query planning, source binding и answer/edit authority не меняются.

Новые обычные tests не добавлены; все имена, параметры и существующие assertions
остаются. После изменения нужно прочитать реальные outcomes этих двух случаев
и current literal/critical gates. Ни нового PASS, ни mutation proof пока нет.

Literal comparison protocol не содержит mutants для `query_terms.py`;
его51 существующий anchor и frozen test inputs не переписываются этим slice.
Обратная замена только двух lower bounds восстанавливает production base побайтно.
Local imports/AST/pytest/subprocesses не выполнялись.
