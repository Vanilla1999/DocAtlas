# PR211: фактический project scope для смешанной проекции

## Назначение

Смешанная выдача использует общие library requirements. Чтобы отдельно проверить
уже полученные проектные окна, consumer должен получить фактическое решение
project reader о корне, модуле и пути. Выводить ожидаемый scope из самих кандидатов
или повторно разрешать имя модуля по отфильтрованному context pack нельзя.

Этот slice только переносит внутренний контракт. Сам по себе он не добавляет
проектные источники в публичный ответ и не закрывает оставшийся mixed failure.

## Изменение

В конец `ProjectDocsResult` добавлен `request_scope` с отдельным
`default_factory=dict`. Прежний порядок positional arguments сохранён.
После текущего чтения `get_project_docs` создаёт один dict из существующих locals:

- `schema_version=1`, исходные `query`, `requested_scope`,
  `requested_module`, `requested_module_path`;
- `project_path=str(root)` и `project_identity=self._repository_identity(root)`;
- фактически разрешённые `doc_scope=query_scope`, `module_path` и `evidence_path`.

Тот же dict передаётся в оба завершающих результата: с обычными results и
с `no_results`. Второй путь нужен для существующего retention, который хранит
найденные окна отдельно от control results. Ранние ошибки и legacy constructors
сохраняют пустое поле. Scope не меняет status, confirmation или delivery.

В конец `UnifiedDocsContextResult` добавлен `project_context_contract` с отдельным
пустым dict по умолчанию. Только при наличии project result и library results
копируются выбранные поля из **уже сериализованного**
`lane_details["project"]`: question, project_path, status,
requires_confirmation, delivery_decision и requirements.

Дополнительно передаются исходный Unified `request_project_path`,
project docs `read_scope`, status и requires_confirmation, а также только
`selection_decision.unresolved_conflicts`. Полные selection, context pack,
source bodies и lane details в новый контракт не включаются.
Если вложенные project_docs или selection_decision отсутствуют либо не являются
dict, их выбранные proof-поля получают `None`. Значения внутри dict переносятся
как записаны; отсутствующие status/consent/conflicts не заменяются успешными
значениями.

## Сохранённые границы

Разрешение scope/module/evidence path, ambiguous/not-found outcomes, metadata
validation, поиск, retention, ranking, ownership и generation checks прежние.
Новых retrieval/SQL/filesystem/subprocess вызовов нет. Дополнительное вычисление
project identity использует существующую чистую root-local hash функцию.

Outer Unified status, consent и delivery не выводятся из context_available.
В частности, existing mixed gate по-прежнему блокирует неподходящие lane statuses:
перенос scope через `no_results` не превращает его в разрешение mixed delivery.
Публичная проекция и её schema в этом slice не меняются; consumer будет проверен
отдельно против текущих MCP arguments и финального same-call snapshot.

## Exact manifest и проверка

Base PR HEAD: `f7b9253c8e477babf276ae8dd2cb18905451cd15`.
Все файлы mode **100644**.

| Путь | Base blob | Новый blob |
|---|---|---|
| `docmancer/docs/models.py` | `6afdc3e6ba8f6d5c1a2bf380be240b97cc0eab19` | `9bb323e4c890e25dc5ef341d045609708ebe3ac0` |
| `docmancer/docs/application/_project_docs_service_part03.py` | `14075c0e78996c610004e17c4db7d4d61cc3077f` | `94fe9ee6629d14034d337fae879272c5b6d16a64` |
| `docmancer/docs/application/_unified_context_service_part01.py` | `d2ddeed566ae4f26aa314bfe57ec544966004117` | `483f04887c10f6c09e0ddd96d38e3a3a1c540a81` |

Узкие замены: 2 + 3 + 2; обратные замены восстанавливают каждый base побайтно.
GitHub roundtrip всех трёх production blobs точный. Обычные тесты, case rosters,
frozen questions, oracle, thresholds и mutation runners не менялись.
Локальные execution/import/AST/pytest не выполнялись. Independent review и
фактический PR CI для нового producer/consumer остаются обязательными;
нового runtime PASS этот slice не заявляет.

## Root review

Root независимо сопоставил точные три source diff с base: прежние positional
arguments, status/consent/delivery и read/SQL calls сохранены. Два post-read
результата несут фактические selectors; ранние failures не получают proof.
Unified берёт conflict state из project lane, не из своего library selection.
`no_results` внутри ProjectDocsResult обозначает control view; consumer может
сохранить found windows только при прежнем успешном outer/project delivery и
собственной проверке current scope/raw member. Отсутствующий selection/conflict
proof не заменяется пустым списком. Producer slice APPROVE; consumer и joint
runtime оцениваются отдельно.
