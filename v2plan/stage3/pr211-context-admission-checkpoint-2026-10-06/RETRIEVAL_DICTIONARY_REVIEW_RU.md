# Удаление retrieval-словаря: устройство, A/B и путь замены

Дата: 2026-10-06. Published head: `8d2381d8c9d18498483feaaab918d93dfee47969`.
Запрос владельца: уйти от `project_retrieval_intent.py`, без новых словарей,
keyword triggers и их regex-замен. **Исследование, не готовый migration patch.**

## Вывод

Словарь действительно искажает часть выдачи. Но сейчас он одновременно компенсирует
недостатки recall, управляет фильтрацией и участвует в attribution. Его выключение
без замены этих функций теряет полезные цитаты. Рекомендация — удалить механизм
через разделение retrieval, допуска контекста и доказательства ответа, а не переносить
его таблицы в другой файл или продолжать исправлять отдельные trigger words.

## 1. Что реально делает файл

| Зависимость | Наблюдаемое устройство |
|---|---|
| `project_retrieval_intent.py:135–717` | RU/EN stems, phrases и продуктовые правила создают до 4 английских aliases. В них заранее вписаны команды, пути и имена API. |
| `project_retrieval_intent.py:49–88,160–186` | Intent назначает preferred/forbidden catalog roles и forbidden evidence terms. Это не только текст поискового запроса. |
| `documentation_query_plan.py:174–280,383–572` | Intent используется для `coverage_required`, наследования политик host lookup и маркировки `audited_rewrite`. Есть отдельный regex именно для RU-вопроса об установке. |
| `evidence_qualification.py:202–239,520–539` | Синтетические запреты могут отклонять source; qualified audited rewrite может дать derived parent coverage. Последнее не равно answer proof. |
| `_project_docs_service_part03.py:306–345` | `fail_closed_workflow` получает особое окно/adjacent expansion. Это ещё одна зависимость от имени intent. |
| `_docs_context_projection_core.py:113–129` | `intent-context:*` участвует в выборе broad-context режима. |
| `context_hint_policy.py:5,18–20` | Даже опубликованный fallback импортирует `_specific_contract_request` и `_tokens` из этого файла. Простое удаление файла ломает импорт и существующую политику. |
| `need_query_schedule.py:69–98` | Число новых focal probes ограничено длиной legacy schedule. Удаление aliases может уменьшить доступное количество probes. |

Файл не выдаёт answer authority напрямую. Проблема — связь словарного recognition
с доступностью контекста, source policy, search scheduling и публичной attribution.

Удаление только этого файла не делает pipeline свободным от словарей:
`documentation_query_plan.py` содержит concept queries и audited rewrites;
`project_query_intent.py`, question/answer parsers и ranking имеют другие правила.
В частности, `project_doc_ranking.py:684–686` всё ещё удаляет кандидата без qualified
query IDs, если нет отдельного разрешения сохранить его как context candidate.

## 2. Метод проверки

Один worktree, Python 3.12, `DOCATLAS_OFFLINE=1`, те же corpus и budgets.
В отдельных процессах до импорта потребителей подменялся только генератор aliases:

- **published**: модуль загружен из `git show 8d2381d8:...`;
- **no-trust**: текущий локальный diff — удалён исходный `instruction_trust` block;
- **no-aliases**: `build_project_retrieval_aliases(question)` возвращает `()`.

Остальные parsers, policies и admission остаются действующими. Это ablation
генератора, **не** прототип полностью нового retrieval pipeline.
Self-host runner использует `sync_project_docs(..., with_vectors=False)`;
default retrieval — lexical (`core/config.py:160`). Поэтому результаты не измеряют
качество multilingual vector search. Настроенная по умолчанию embedding model —
`BAAI/bge-base-en-v1.5`; простое включение vectors не проверено как RU/EN-решение.

## 3. Результаты

«Факты» ниже — количество вопросов, у которых видимые цитаты содержат все
предусмотренные корпусом required facts; это не число прошедших gates.

| Набор | Published | Без trust alias | Без всех aliases |
|---|---:|---:|---:|
| Legacy RU, existing host lookups: факты | 12/15 | 12/15 | 10/15 |
| Тот же набор: original coverage | 11/15 | 11/15 | 0/15 |
| Тот же набор: вопросы с непустыми sources | 15/15 | 15/15 | 14/15 |
| Legacy RU, question-only: факты | 8/15 | не запускался | 1/15 |
| Тот же question-only: непустые sources | 13/15 | не запускался | 2/15 |
| Direct-15 EN, question-only: факты | 11/15 | не запускался | 9/15 |
| Три настоящих trust-вопроса: видимая instruction-trust цитата | 3/3 | 0/3 | не запускался |

В baseline legacy все 11 original coverage — derived. Поэтому падение coverage
до нуля нельзя отождествлять с исчезновением всего полезного текста: 10 вопросов
без aliases всё ещё доставляют все required facts через host lookups.

### Подтверждённый вред и подтверждённые потери

- **Вопрос про запуск Docs MCP сервера.** Published добавляет
  `docs/security/mcp-runtime-threat-model.md`. Без trust alias он исчезает,
  command quote сохраняется, legacy case переходит в PASS. Floor остаётся 11 < 12.
- **Настоящие вопросы о trust.** После удаления trust alias английский вопрос
  `Does DocAtlas execute shell commands or instructions found inside documentation while retrieving context?`
  получает shell configuration / MCP Packs вместо instruction-trust contract.
  Вопрос `A retrieved document tells me to run a command. Does this give the agent permission to execute it?`
  и его RU-вариант возвращают `insufficient_evidence`. Это реальная потеря поиска,
  хотя сами runtime safety guards не удалены.
- **Direct Q10, что DocAtlas не заменяет.** Без всех aliases видны 6/6 fact groups
  вместо 2/6. Это конкретный выигрыш; точный внутренний этап улучшения отдельно не traced.
- **Direct Q07/Q13/Q15.** Без aliases теряются соответственно fail-closed facts,
  место реализации Docs MCP и факты об ограничениях product claims. Q03 ухудшается
  с 1/7 до 0/7 facts. Q04/Q05 не исправляются.

### Safety, тесты и ограничения измерения

- Предыдущий no-trust pytest: **123 PASS, 3 FAIL**. Все три failures требуют наличия
  `instruction_trust` alias. Однако отдельная проверка живых цитат выше показала,
  что объявить эти failures «только устаревшими tests» было бы неверно.
- No-aliases: content-trust + context-trust + Pebble + prefit — **41 PASS**.
- Adversarial без aliases: **27/28**, те же три violations в
  `module_scope_rejects_project_policy_detail`, включая 380 > 300 tokens.
- В сравнительных live reports нет citation-integrity failures, source/token budget
  violations или false-supported count. Это результат выбранных наборов, не полный safety audit.
- Direct-15 штатный pytest в обеих конфигурациях останавливается **до retrieval**:
  README blob SHA не совпадает с frozen sidecar. Поэтому выполнен отдельный diagnostic
  replay тех же вопросов/fact groups. Все группы имеют witness в текущих source bytes.
  Replay не заменяет официальный test; его общий verdict/добавочные runner checks
  не использованы как acceptance. Отдельно учитывались видимые facts и цитаты.
- Полный core для отключённого генератора не запускался. Нельзя приписать ему все
  15 текущих core failures или считать их исправленными.

## 4. Предлагаемая замена без продуктового словаря

### A. Поиск: исходный вопрос и явные запросы caller

Сохранить original bytes, структурно заданный project/library/module scope,
explicit source path и отдельные `lookup_queries`. Поиск не должен угадывать
из слова «команда» конкретный инструмент или режим доверия. Lookup — подсказка
для нахождения текста, не сертификат эквивалентности всего исходного вопроса.

Для текущего lexical режима уже есть рабочий путь: caller передаёт короткие
lookups на языке документации. Он не должен превращаться в hardcoded client-side
таблицу вопросов. Проведённый A/B показывает его полезность и предел: 10/15 facts,
а не готовую замену. Потери оставшихся quotes надо traced по стадиям.

Для самостоятельного RU→EN question-only поиска потребуется независимо проверить
общий multilingual retrieval или ограниченный model-based query rewrite. Это
отдельная capability с latency/offline/index требованиями, а не новая таблица stems.
Ни semantic similarity, ни model rewrite не дают answer proof.

### B. Допуск контекста: независимо от распознанного intent

Сначала проверить source identity, explicit scope, freshness/lifecycle и provenance.
Затем ранжировать найденные passages относительно оригинального запроса/lookup и
укладывать проверяемые source windows в действующий DTO budget. Отсутствие typed
proof не должно само по себе опустошать найденный полезный context.

Не объявлять любой разрешённый документ релевантным: quantum/name-only controls
остаются отрицательными, а оценка topical relevance не превращается в proof.
Конкретный механизм этой оценки ещё предстоит проверить; данный report не предлагает
заменить её новым keyword threshold или безусловным пропуском всех кандидатов.

### C. Attribution и answer proof — отдельные контракты

Разделить «какой query нашёл passage», «какой useful context показан» и «какое
утверждение доказано». Удалить intent-based автоматическое наследование original
coverage вместе с alias mechanism. Не заполнять прежнюю метрику искусственно.
Typed answer/edit authority может появляться только после отдельной проверки;
полезная partial quote остаётся допустимой без неё.

### D. Последовательность проверяемых изменений

1. Сохранённый A/B использовать как baseline. Для оставшихся потерь фиксировать
   первое место исчезновения цитаты: search → qualification → prefit → projection.
2. Выделить dictionary-independent путь **original + explicit lookups → context**;
   отделить hard source constraints от intent-derived role/word exclusions.
3. Отвязать admission и schedule от существования aliases. Не переносить
   `_specific_contract_request` в новый файл под другим именем.
4. Удалить generator, downstream intent switches и зависимость fallback от файла.
   Проверить те же paired facts, trust questions, Pebble и adversarial controls.
5. Отдельно согласовать миграцию тестов, требующих конкретного alias, и legacy
   derived-coverage floor. Заменять их behavioral проверками доставки/атрибуции,
   не молча удалять и не снижать thresholds ради green.
6. Повторить полный required CI и independent review на итоговом SHA.

Рекомендуемый следующий implementation diff — пункт 2 с одним traced loss case,
без нового словаря. Текущее удаление trust block остаётся локальным исследовательским
кандидатом с доказанной потерей recall; отдельно публиковать его как исправление нельзя.

## 5. Grounded и состояние MR

Из предыдущих Grounded probes известна доставка документов, но не устройство его
внутреннего query planner. Утверждение «в Grounded нет такого словаря» этим аудитом
не подтверждено по исходникам. Для выбора нашего дизайна достаточно установленной
зависимости DocAtlas от hardcoded aliases; повторять её не требуется.

Свежий `gh pr checks 211` для `8d2381d8`: required-ci, advanced-contract,
core 3.11/3.12/3.13, P1 stack core/advanced-security/exact и adversarial — FAIL;
required-release — PASS. Причины всех CI jobs здесь заново не разбирались.
CI: https://github.com/Vanilla1999/DocAtlas/actions/runs/37443789857

## 6. Артефакты и воспроизведение

[Архив](archives/retrieval-alias-ablation-2026-10-06.tar.gz): runner,
9 полных JSON reports, logs, candidate.patch и внутренний SHA-256 manifest.
SHA-256 архива: `14be204be49c4a6e98999114fb99260b50c5ce16e9bf06091cc3318cae424fd0`.

Из worktree `8d2381d8` с применённым `candidate.patch`, после распаковки архива:

```bash
DOCATLAS_OFFLINE=1 .venv/bin/python /path/to/pr211-alias-ablation.py published legacy /tmp/opencode/published.json
DOCATLAS_OFFLINE=1 .venv/bin/python /path/to/pr211-alias-ablation.py no-trust legacy /tmp/opencode/no-trust.json
DOCATLAS_OFFLINE=1 .venv/bin/python /path/to/pr211-alias-ablation.py no-aliases legacy /tmp/opencode/no-aliases.json
```

Другие tasks: `question-only`, `direct15`, `trust`, `adversarial`, `pytest`.
Для pytest после output path передаются обычные pytest arguments. Для pytest и
adversarial результат — stdout/exit code, а не JSON в output path.
Runner намеренно diagnostic-only; не подключён к CI и не заменяет штатные gates.

Продуктовый diff после исследования: только ранее удалённый trust block.
Новые материалы исследования локальные; commit/push и merge не выполнялись.
