# Завершение аудита legacy/proof entry points

Этап поверх `b9ef424d`, вместе с предыдущими vector/patch и patch-plan/hybrid
изменениями. Этот отчёт заменяет их историческую пометку «ещё не закоммичено»
после публикации общего коммита.

## Прослеженные пути и изменения

| Путь | Итог аудита |
| --- | --- |
| MCP project/library/mixed → unified/project services | Сохранены request-owned live receipts; прямым вызовам сервисов добавлен такой же lifetime. Вложенный MCP-вызов использует существующий scope. Самостоятельный projector не получает права воспроизводить receipt. |
| SDK `get_docs_context`, `get_project_docs`, `DocmancerClient.get_context` | Проверены реальными индексами и исходными фактами в существующем публичном сценарии. |
| CLI `context` → project service | Удалён обход live read scope. Найдено и исправлено создание ancillary registry/jobs при первом чтении: CLI включает read-only metadata и не возобновляет jobs. Это не изменение режима всех остальных команд CLI. |
| Exact-document fallback | Удалены hit-count score 1000+N, фильтр по probe terms и сортировка по ним; исходный текст больше не strip-ится. Сохраняются finite bound, literal source/project checks. |
| Legacy project rerank | Удалены greedy query-coverage selection, source quotas, повторная сортировка по score и synthetic rank score. Сохраняются membership, lifecycle и source admission. |
| Legacy service relevance/trust | Удалены веса path/title/content/symbol, пороги overlap и выдача answer authority по наличию snippet/dependency или большому score. Диагностика — unassessed; цитаты не становятся ответом. |
| Evidence deduplication/selection | И patch, и legacy docs сохраняют acquisition order. Только взаимозаменяемые evidence rows могут дедуплицироваться; overlap/Jaccard больше не удаляют кандидатов. Удалены greedy mandatory cover/repair, utility-ratio selection, dominance и source caps из вызываемого selection пути. Legacy docs сохраняет конечный token budget. |
| Proof/witness assignment | Удалены completeness/length/relevance ordering и поиск «лучшего» literal witness. Первый проверенный witness связывается с требованием; source window, lifecycle, literal equality, scope/version и proof-role validation остаются. |
| Library assembly | Emoji, HTML anchors и крайние whitespace не удаляются из окон. Witness comparator и model-visible serialization сохраняют тот же исходный текст. |
| Mixed assembly | Раньше после project validation терялись line/scope/identity/authority поля. Теперь project quote сохраняет полную схему, а validator выбирает её по внутреннему source snapshot, не по клиентскому флагу. |
| Patch-plan и dense/sparse/hybrid | Результаты предыдущих двух отчётов сохранены. Новых изменений retrieval runtime на этом этапе нет, поэтому real-model hybrid повторно не запускался. |

Пройденные product entry points не вызывают старые `_candidate_preference`,
`_assignment_preference`, `_repair_mandatory_selection`, `_marginal_utility`,
`_rank_and_dedupe` и модули `need_context_projection`/`context_candidate_ranking`.
Некоторые их определения/экспорты остаются compatibility/dead code; это **не**
заявление, что эвристических формул больше нет нигде в репозитории. Jaccard
остаётся в диагностике redundant-token ratio, не в выборе источников.
Сортировка requirements/hashes/trace для стабильной сериализации не ранжирует
источники. BM25, vector similarity, RRF/weighted RRF и явное expansion сохранены.

## Проверки конечной выдачи

- `legacy-proof-final.log/xml`: **13 PASS** после исправления library и mixed
  projection, включая три прежние patch-plan интеграции.
- `integration-final.log/xml`: **11 PASS за 6.41 s** после удаления оставшегося
  legacy utility selector. Это шесть public heuristic-removal, четыре prepared
  retrieval и один существующий MCP literal patch-validation сценарий.
  Последний подтверждает mechanical comparison без policy/edit authority.
- `explicit-final.log/xml`: **1 PASS** после удаления strip из exact fallback.
- В расширенном публичном сценарии проверены порядок patch-источников против
  read-only выдачи, SDK-факты и неизменность состояния.
- Новый mixed-сценарий использует настоящие project/library индексы: исходные
  optics-факты, точную библиотечную версию, emoji+HTML anchor без изменения
  текста, hashes/line spans/scope/identity проектных источников и неизменность
  обеих БД и файлов. Retrieval/selection/storage/validation не подменены.
- `installed-stdio-verified/SUMMARY.json`: **PASS** установленного финального
  wheel, `python -I`, MCP SDK stdio, default arm V0. Один prepare, два context
  (positive + неверная версия), один resource read, ноль model calls.
- `installed-cli-verified/SUMMARY.json`: **PASS** финального установленного CLI
  на свежем результате stdio prepare. Факт доставлен, answer/edit authority
  отсутствует, все logical table hashes и файлы проекта неизменны.
- `git diff --cached --check -- docmancer tests eval`: PASS перед коммитом.
  Полная staged-проверка дополнительно сообщает trailing whitespace в сырых
  pytest/Qdrant логах и XML; исходные артефакты не переформатированы.

## Разбор обнаруженных FAIL

1. Library: после сохранения original whitespace старый comparator всё ещё
   сравнивал с cleaned text. Исправлен comparator, не oracle.
2. Mixed fixture: первоначально использовался read-only provisioner; затем
   отсутствовал owned-home marker/private mode и не совпадал library root.
   Исправлена только явная подготовка изолированного fixture.
3. Mixed public source integrity: факты были доставлены, но project provenance
   поля были потеряны при конвертации в library schema. Исправлен продукт.
4. CLI harness сначала искал edit_ready на верхнем уровне вместо существующего
   `answer_completeness.edit_ready`; исправлен путь проверки, требование false
   сохранено.
5. CLI first-read state: `installed-cli-state-debug3/before.json` и `after.json`
   показывают появление `doc_libraries`, `docs_job_schema`, `docs_jobs`.
   Повторный вызов на уже изменённой БД проходил, но не принят за исправление.
   После исправления CLI/service выполнен новый prepare в новом каталоге;
   `installed-cli-verified` подтверждает отсутствие этих изменений.

## Воспроизведение и границы

`eval/heuristic_removal/installed_stdio.py` запускается через Python venv с
установленным wheel, `-I`, новым `--work`, новым `--output`, `--arm V0` и
`--manifest` из этого каталога. Затем тем же Python запускается
`eval/heuristic_removal/installed_cli_context.py --work <тот же work>
--output <новый output>`. Используется отдельный приватный state root и
tokenizer cache; модели/сервисы при этих проверках не запускаются.

Это source-tree integration + installed SDK stdio/CLI; не GUI/реальный клиент,
не production smoke, не оценка relevance или скорости. Старые unit-импорты
удалённых модулей не мигрировались и полный старый suite не запускался.
Library upstream trace gaps не объявляются устранёнными: факты и сохранность
выдачи проверяются независимо от полноты диагностической трассы.
