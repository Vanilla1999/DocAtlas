# PR #211 — закрытый контекст требований по точному имени

## Доказанная причина

На a348cafb (фактическое совпадающее дерево merge0e84988d) P1.4 остаётся9/14:
run37998331831, job114049949393. Два исходных вопроса:
`What does OrderValidationContract require?` и
`Which conditions are required by OrderValidationContract?`.

В обоих найден правильный packages/orders/README.md, полное окно103символа,
current owner/generation/catalog/hash bindings присутствуют. Единственная
причина rejection — insufficient_visible_match:1/4 и1/6 слов соответственно.
Точная body occurrence OrderValidationContract есть, но closed-context helper
ранее допускал только формы What does X do? и What is X?.
Документированные ответы, исходные вопросы и quality thresholds не меняются.

## Изменение контракта

Тот же путь частичного контекста принимает ещё две полностью закрытые формы:

- What does X require?
- Which conditions are required by X?

X по-прежнему один неявный unresolved syntactic identifier из исходного
неизменённого вопроса. Перед ним и после него должны полностью совпасть
указанные формы. Дополнительные условия, определения, clauses, второй literal
и изменение регистра самого имени не получают новое разрешение.

Это выбор контекста по точному имени. Новая форма не выводит из прозы
requirements/default relation и не квалифицирует весь исходный вопрос.
Query coverage остаётся partial, query-original — missing, coverage_credit=False.
Answer/edit/reference-role authority не выдаётся.

Весь admit_original_literal_context после helper сохранён побайтно: current
source/window/raw-document hash, owner, scope, generation, catalog, lifecycle,
source class, case-sensitive body occurrence и substantive body guards прежние.
Обычный qualifier и порог0.5 не изменены. Имена из frozen P14/P15 в production
не добавляются. Policy-count, alias и document-statement формы этим slice
не расширяются и остаются отдельными задачами.

## Проверки без новой обычной test family

Расширён существующий recovery case closed_literal_context; общее число
case functions остаётся12. Все прежние исходники сценариев, вопросы,
negative controls, state fingerprint comparisons и assertions сохранены.

Добавлен независимый literal DispatchInvariant и authored body:
`DispatchInvariant rejects records missing an id or a currency.`
Он не копирует P14fixture. Существующая проверка context() проверяет полный
source fact, actual immutable bytes/hash/spans, сохранённый unresolved role,
отсутствие answer/edit и query-coverage credit для обеих новых форм.

Три дополнительных negative controls требуют отказа при условии
when preview is disabled, хвосте under the lunar policy и модификаторе optional.
Все проходят через прежний public read и строгий before/after equality.
Before-hash не переносится; warming не добавляется.

Существующий mutation runner получает два отдельных intended defects:
отключение active require формы и ошибочный допуск optional modifier.
Они должны упасть на recovery_closed_literal_source_fact и
recovery_closed_complete_syntax соответственно. Существующие16mutants,
runner validation и запрет засчитывать crashes/failed baseline сохранены.
Итоговый целевой proof —12зелёных baseline cases и18intendedkills.

Это не снижение actual runtime работы: обычных case functions не добавлено,
но внутри существующего case стало на6public reads больше и добавлены2mutants.
Test retirement здесь отсутствует.

## Acceptance

Source review выполняется против38da10d347ae2227eee6d1624db58dbf30938674.
Локальный runtime/import/AST не запускался. Новый P14 результат и12/18recovery
proof ещё pending. Уже известный cold-first SQLite write остаётся отдельной
production проблемой и не маскируется данным slice; до его исправления
recovery baseline не даёт mutation credit.
