# PR #211 — точная версия в finite library index

## Фактический результат до изменения

На HEAD 38da10d347ae2227eee6d1624db58dbf30938674
(фактический merge checkout 984bb65205140221552728fc03dc8b5121f3e218)
[P1.5 run 38000724676, job 114057857626](https://github.com/Vanilla1999/DocAtlas/actions/runs/38000724676/job/114057857626)
показал 4/7 PASS, 2/6 полных фактов, 0 runtime errors.
Все 6 oracle controls, report integrity и syntax прошли.
Quality gate остался FAIL.

Для исходных dependency и mixed вопросов real resolve_library вернул
python:tenacity@8.2.3:reference, resolved_version=8.2.3,
docs_snapshot_exact=True, local=True, status=available.
Реальный get_docs затем вернул no_library_docs_results: lexical candidates=0,
post_guard before=0, accepted=0, failures={}. Согласие, запись registry и
postprocessing не были первой причиной потери.

Данные stored_children сохранены в исходном JSON artifact. GitHub connector
предоставил ZIP, но в разрешённом tool-only режиме его содержимое не было
декодировано. Поэтому конкретные значения SQL ниже — вывод из полностью
прослеженного source path, а не заявление о дополнительно выполненном SQL.

## Причинная цепочка в текущем исходнике

1. Public finite manifest проходит DocsPrefetchService и реальный agent.add.
   При передаче metadata он сохранял canonical_source_identity, library_id,
   canonical_id и старое поле version.
2. Direct-text fetcher не выводит версию из тела документа или URL. Agent
   переносит переданные metadata; source-owned URL/title/format остаются
   отдельными полями.
3. normalized_filter_metadata читает resolved_version и docs_snapshot_exact,
   а не version. Без этих двух ключей promoted child получает пустую
   resolved_version и NULL docs_snapshot_exact; metadata_json получает те же
   нормализованные значения.
4. Library get_docs использует разрешённую запись registry и требует
   resolved_version=8.2.3 и exact_snapshot_required=True. Dispatcher компилирует
   последний фильтр в docs_snapshot_exact=True, SQLite сравнивает promoted
   columns, затем dispatcher повторно проверяет hydrated metadata.
   Child без точной привязки закономерно не проходит.

Таким образом, full text уже успешно подготовлен, но finite producer потерял
существующую точную привязку до retrieval. FTS grammar, ранжирование и
квалификация исходного вопроса для этого исправления не меняются.

## Изменение

DocsPrefetchService использует существующий metadata_for_record(record) из
library_refresh_policy — то же преобразование, что и ordinary refresh.
Перед каждым agent.add передаются реальные requested/resolved version,
docs_snapshot_exact, source type и docs root из записи registry.
Per-URL canonical_source_identity и прежний canonical_id fallback сохранены.

Helper не изменён. Он сохраняет False для неподтверждённого snapshot и не
добавляет в таком случае legacy version. Новый код не устанавливает True,
не выводит версию из имени вопроса/факта и не выдаёт source authority.
Registry semantics, exact URL/robots grants, preflight, checkpoint,
refresh authorization, staging и commit paths остаются прежними.

Исправление применяется при разрешённой индексации. Для ранее подготовленного
индекса без binding нужен обычный явный refresh; read не выполняет скрытую
запись и не ослабляет фильтр.

## Oracle и диагностика

Существующий P1.5 preparation oracle теперь проверяет exact binding каждого
committed member официального versioned docset, включая robots.
Ожидаемая версия берётся из независимой frozen identity; exactness принимает
только bool True или SQLite integer 1. Строки, float, NULL и иные числа
отклоняются. Проверки bytes/hash/spans, member/library roster, successful job,
read-only state и закрытой сети сохранены.

В прежней функции test_provenance_gap_is_retained_but_not_hidden добавлены
2 положительных DTO-представления exactness и 20 fault variants:
для каждого из двух members отдельно изменяется resolved_version либо
docs_snapshot_exact. Registry и видимый полный факт остаются прежними,
но finite_public_preparation обязан стать FAIL. Это oracle controls,
а не выполнение реального retrieval; шесть исходных test names сохранены.

Runner для неуспешных cases выводит уже сохранённые prepared library records
и child bindings через существующий body-free formatter. Новых сетевых/SQL/
retrieval calls нет. Runtime manifest явно требует уже используемый
library_refresh_policy.py. Семь вопросов, 13 исходных candidates, шесть
обязательных полных фактов, два negative cases, frozen protocol/crosswalk
и historical report не менялись.

## Что ещё не закрыто

Это исправление первого library barrier; новый actual P1.5 result pending.
Оно само по себе не доказывает успешную qualification/public delivery.

Document-statement case уже находит правильный docs/release-policy.md,
но body qualification остаётся 1/8 и insufficient_visible_match.
У mixed question project lane возвращает not_found; точный private project
trace ещё требуется. Эти задачи не подменяются ослаблением source/fact gold.

Local runtime/import/AST не запускался. Следующий acceptance — реальный
P1.5 quality плюс прежние 6 oracle controls и syntax на опубликованном SHA.
