# PR211: self-host fixture — независимый source review

Дата: 2026-10-08. Reviewer: root; implementation author: catalog_compaction.
Base: `04ff1dda57efb5236d7b3577d4e2736b2820df5b`.

**Решение: APPROVE для обычной публикации и совместного CI. Runtime NOT RUN.**
Это source/contract review, а не подтверждение downstream quality или готовности PR к merge.
Review выполнен по окончательным implementation bytes в объединённом checkout.

## Причина и сохранённый контракт

Legacy и V2 self-host использовали retired eager/implicit sync setup. Новая fixture
проверяет настоящий cold public read и лишь после отказа без создания store выполняет
explicit confirmed member transaction. Временная копия содержит все tracked regular
files исходного checkout, включая физические unselected docs/code/eval distractors.
Члены индекса выбираются только из исходного конечного catalog; вопросы и gold не
участвуют в selection. Catalog и document bytes сохраняются, project identity честно
меняется на identity копии. Config меняет только index.db_path на host-selected target;
остальные значения сохраняются и проверяются. Git witness копии явно not_git.

Проверены полный helper, шесть новых tests, оба изменённых unit setup consumers,
runner diff и additive V2 passthrough; production dependencies просмотрены как source.
Read-only Git использует literal argv, sanitized GIT environment и bounded existing
subprocess helper. Требуются stage0 regular files, полный inventory и exact Git blob
binding. Symlink/hardlink/unsafe paths, staging drift, байтовое отличие, превышение
work bounds или истечение deadline отвергают весь setup, без усечения membership.
Каждый файл читается отдельным existing PinnedProject context; source identities и
inventory перепроверяются. Source read limits не изменены. Copy-only bounds измеримы
и не используются как новый production catalog/output ceiling.

Private fixture mirror становится readonly на время actual calls; cleanup восстанавливает
permissions только собственных копий. Исходный repository, пользовательский store и
process environment не усваиваются fixture. Общий existing environment RLock допускает
вложенное isolated_service; HOME/XDG/DOCATLAS и Git redirections изолированы. Actual
imports остаются в исполняемом checkout, direct script entrypoint сохраняет bootstrap.

## Cold/preparation и отсутствие ложного PASS

Cold payload должен иметь точный failed/permission_denied execution PermissionError,
retryable=False и отсутствие sources/kind. Пять authority/availability flags принимают
только отсутствующее/None либо настоящий False. Обнаруженные ранним peer review
CLI/import-origin и mutation_ready/falsey-nonboolean проблемы исправлены в final bytes.
Противоречивый cold ответ оставляет pre-sync FAIL; preparation и scoring loops не
запускаются. Ошибка реального prepare прекращает run, не синтезирует успешный ответ.

Prepare использует тот же cold factory/policy/config/host store, исходные catalog,
content и entry hashes и CAS None. До вызова требуется отсутствие initialized store;
после проверяются generation, полный точный indexed path set и source/catalog/root
bindings. Обход подтверждения, retry/refresh, library adoption или read-path repair
не добавлены. Два прежних unit harness изолируют только setup seam; это не runtime
доказательство. Шесть новых fixture tests предусматривают real Git/MCP preparation,
непустой bound source/snapshot positive и controls до и после mutation.

## Машинная сверка сохранённых проверок

- Все function/class definitions runner вне run AST-exact относительно base.
- Обе полные positive/negative loop AST-exact после единственного project root binding.
- Весь scoring/report tail побайтно прежний, кроме additive setup_provenance.
- V2 source побайтно прежний после удаления двух строк optional provenance passthrough.
- В двух существующих test modules изменены только согласованные setup consumers;
  прочие definitions, имена и decorators/parameter inventories прежние.
- Сохранены все прежние assertions этих consumers: 3/3 и 8/8.
- 15+13 прежних base test names сохранены; добавлены ровно шесть непараметризованных
  self-host nodes. Новый diagnostic inventory отдельный, старые labels не изменены.
- Синтаксис проверен ast.parse/compile без исполнения. Module-size <1000 и
  git diff --check подтверждены. Repository runtime/imports/pytest/install/providers
  локально не запускались.

Root source audit SHA256: `1aebd25009cf4f3300902f63be102cb48ec8a6e1c37d167a1bde063d1082784a`.
Первый запуск этого audit не выбрал negative loop из-за неверного имени в самом
аудиторе; после проверки actual AST targets обе полные loop проверены. Source не
менялся в ответ на эту ошибку аудитора.

## Обязательная последующая проверка

Один обычный общий CI на конечном опубликованном SHA должен проверить шесть новых
nodes, unchanged unit parameters, оба downstream commands и отсутствие новых PASS
regressions. Новая fixture не обещает пройти неизменённые retrieval/quality floors.
Provenance — artifact metadata; public MCP DTO, responses, scoring и token estimates
не расширены этим полем. Git auto-sync, исходный storage config, installed wheels и
actual Claude Code/Codex/OpenCode sessions этим in-process setup не сертифицируются.
Deferred retrieval, frozen gold/thresholds и critical mutation gate не изменены.

## Проверенные окончательные файлы

| Path | SHA256 |
| --- | --- |
| `scripts/_project_docs_self_host_fixture.py` | `3a867afe6346bc595c5bf246907c33825f1c9fdcb27fe6982eb2c4f13c0cba85` |
| `scripts/run_project_docs_self_host_gate.py` | `bc2db12f7ca306c99fa3426304fb1b36431295b9ab287067045cce5b5089b8b5` |
| `eval/project_context_quality_v2_protocol.py` | `15d23a8c79e73b33efe28e7fa949f536868f2457c718e0c453116d7a8ba12e1d` |
| `tests/test_release_gate.py` | `f272a812afa28f7d6bcf3491c1473088a0aac90fc5904a62daceb973e247ebef` |
| `tests/test_project_context_quality_protocol.py` | `d5b0a6a138cf29f28ffcdeb713ffd9ea26e788cb33fb7b9809ddb6351a187169` |
| `tests/test_project_docs_self_host_fixture.py` | `51831edb77d84af6afe597ebc74c0ec9e962c59b44507231cac51749cc457a49` |
| `tests/diagnostic_labels.project_docs_self_host_fixture.json` | `bc653faa03300249877061c2d5953fe882e528af4f66b487e4a28b6bd82246eb` |
| `v2plan/PR211_SELF_HOST_FIXTURE_REVIEW_RU.md` | `818276d98e53cf76fdfb69e7aeb4c4fe4f4c828fc7fda8dc6e94cb375746fc92` |
