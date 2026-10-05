# Reader pilot — review before execution, 2026-10-05

Base: 2e46c7754b1e407dc8fcc0de4861815705c20858, branch next07-feasibility-audit.
Авторское ревью кода и контрпримеров, НЕ независимый внешний аудит.
Проверены новый опубликованный native pilot и старый ZIP. ZIP не применяется:
он использует другой snapshot-host, две navigation operations и 60 сессий;
опубликованный pilot — native first packet, inline map, одно section-read и20.

## Исправленные замечания

1. Workflow вызывал live mode при push при наличии secret и сам выбирал default
   model. В новой revision push запускает только technical/native; paid/provider
   run требует manual dispatch+run_model+явного model. Локальный --mode live тоже
   требует --model. API/temperature/caps не подстраиваются и не переключаются.
2. SectionHost считал seen intervals по ВСЕМ private snapshot rows. Это могло
   объявить недоставленный материал прочитанным и лишить модель ссылки. Теперь
   учитываются только evidence_id из public sources с точным initial span.
   Более широкий underlying span не выдаётся за seen; текст не ищется elsewhere.
3. Malformed model tool call с отсутствующим id мог пройти JSON args validation,
   выполнить read, затем вызвать KeyError. Некорректные контейнеры тоже могли
   уронить runner. Теперь role/type/id/function и reused IDs проверяются до I/O;
   INVALID_MODEL_ACTION сохраняется отдельно от поломки runner и provider.
4. finish_reason=length/refusal ранее превращался в INVALID_PROVIDER, терял usage
   и останавливал остальные cases. Теперь полученная модельная неполнота имеет
   отдельный status и сохраняет message/identity/usage. Это не PASS/не retry.
5. Provider returned model теперь проверяется на наличие и неизменность между
   calls; malformed transport JSON получает typed failure. Это freeze фактически
   возвращаемого имени, НЕ доказательство идентичности весов за alias.
6. После двух read attempts не рекламируется невозможный третий read. Последний
   turn содержит только submit_answer; число turns/calls не увеличено. Tool result
   сохраняется сразу, до следующего обращения к provider.
7. Whitespace quote не считается evidence; пустой question_for_user при
   needs_user_data записывается как contract error. Проверка не судит семантику.
8. Review queue получает отдельную rubric и execution/contract errors; случайный
   review_id заменяет перебираемый SHA(case+arm). Hidden fixtures по-прежнему не
   попадают в model requests. Полной blind из-за объёма evidence не обещаем.

## Что сознательно не исправлялось

Runtime docmancer, public MCP schemas/tools/list, frozen cases/evaluator,
retrieval, exact/subject/source guards, owner delivery, first_fit и транспорт.
Новый parser/алфавит/словари/эвристики relevance не добавлены. N10 NOT_RUN.
По-прежнему selected-docs-only, max2 reads,40 lines,600 DTO units на read.
Полный Markdown section не доказывает семантическую completeness.

## Пределы выводов

A/B проверяют navigation+read, не один заголовок и не equal-compute comparison.
Десять exposed development cases, один повтор: pilot, не универсальная гарантия.
Native initial packets не урезаются специально ради нужды в follow-up. Если
контроль уже answered или source safety отказал до exposure, это надо отметить.
Наличие grep/цитаты не проверяет финальный смысл. Внешний reader отделён от
coding-организатора и reviewer. Исследовательский callback не установлен в любом
MCP-host автоматически. Адаптер пока OpenAI API, не любой локальный provider.

## Проверка до push

Оригиналы host/model/run, восстановленные для локальной проверки, сверены по
Git blob SHA с base. py_compile успешен. 15 изолированных model-loop tests
прошли локально; 10 остальных новых tests требуют actual project dependencies
и запускаются в CI. Ни один локальный stub не называется native acceptance.
Workflow сохраняет JUnit/native evidence и отдельно NOT_RUN модели; это не
зелёная приёмка качества. Результат фактического CI записывается отдельно после run.

Справка по типам ответов provider: официальная API reference
https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create
подтверждает необходимость проверки generated function arguments и различие
finish_reason; она не доказывает качество reader.
