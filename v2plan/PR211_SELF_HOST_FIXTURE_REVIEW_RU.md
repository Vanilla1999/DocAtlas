# PR211: full tracked self-host fixture migration — author review

Дата: 2026-10-08. Base `04ff1dda57efb5236d7b3577d4e2736b2820df5b`. Worktree `DocAtlas-self-host-fixture`.
Root разрешил этот узкий setup slice и отдельный additive V2 provenance passthrough.
Никаких production/retrieval/corpus/gold/threshold/workflow правок в этом slice.

## Причина и текущий контракт

Два downstream entrypoints импортируют один `run_project_docs_self_host_gate.run`:
Legacy live/report-only + lineage floor и V2 live acceptance. Старые eager SQLite,
implicit `sync_project_docs(..., with_vectors=False)` и sync recommendation от cold
read не соответствуют текущему host-selected member transaction.
Оригинальный `docatlas.yaml` содержит `.docatlas/docatlas.db`, конфликтующий с
обязательным external host store. Удаление config либо bypass validation не разрешены.

Новый fixture зеркалирует ВСЕ tracked regular files checkout. На base04 read-only
inventory: 2793 files / 119277715 bytes; maximum file 14100090 bytes. Это baseline
measurement, не hardcoded expected final count: новые reviewed tracked files в
следующем CI также зеркалируются. Catalog остаётся исходным: 10 docs / 88427 bytes,
2614 catalog bytes; SHA256 `4e51d2baee5be889a9828d5f5527e1f937c59c3ba67cba056e59b4e9cf6a86e1`.
Unselected tracked docs/code/eval/gold остаются физическими distractors. Untracked
build/venv files и `.git` не копируются; membership не выводится из вопросов/gold.

## Реализация и изоляция

- Read-only Git argv: `rev-parse` root/HEAD/tree/object format, cached `diff --quiet`
  с `--no-ext-diff --no-textconv`, `ls-files --stage -z --cached`. Stage0/regular
  modes/unique literal paths обязательны; symlink/submodule/unmerged/missing/hardlink,
  traversal, bytes не соответствующие index blob или изменение inventory — FAIL.
  Git config/global/environment redirections удаляются; optional locks и fsmonitor
  отключены. stdout bounded 4 MiB, stderr bounded existing process helper; stderr,
  truncation, timeout или ненулевой code — FAIL, без пропуска элементов.
- Отдельные fixture-copy work bounds: 10000 files / 4 MiB inventory / 32 MiB file /
  256 MiB total / 60 s copy. Общий deadline передаётся также в Git и source recheck;
  каждый Git command ≤10 s. Это не production source/retrieval/catalog limits.
- Source bytes читаются через existing POSIX `PinnedProject` no-follow descriptors
  отдельным context на файл; original Git blob, SHA256 и copied SHA256 проверяются.
  Original identity/version metadata и Git inventory повторно сверяются до yield
  и после нормального завершения calls. Copy файлы/directories закрываются от записи
  на время calls; cleanup изменяет permissions только принадлежащего fixture mirror.
- Original config сохраняется. Только copied mapping `index.db_path` меняется на
  literal absolute host target; все остальные значения, включая source boundaries,
  query settings и original extracted_dir, проверяются на точное равенство.
  Catalog и `.gitignore` сохраняют bytes. Source selected paths/content/entry hashes
  не меняются и не получают новую authority.
- `isolated_service` используется без изменения: private external home/store,
  sanitized HOME/XDG/DOCATLAS, offline/no-vectors, общий environment lifetime lock,
  actual cold factory + existing materialized facade forwarding wrapper.
  `index_project` и `write_project` не используются и не меняются.
- Cold public read обязан вернуть typed execution PermissionError/permission_denied;
  database/marker отсутствуют и facade не materialized. Kind и противоречивые
  answer/edit/mutation/context flags отвергаются; falsey non-booleans не принимаются.
  Invalid cold response сохраняет явную `pre-sync` FAIL и не запускает preparation
  или вопросы. Ошибка real preparation прекращает run, а не превращается в PASS.
- Real public `prepare_docs` получает explicit confirm, host path, full original
  catalog/member hashes и initial CAS None. Не принимает existing store, не делает
  refresh/retry. Read-only diagnostics того же store проверяют generation, весь
  точный indexed path set, source bytes/catalog hash/root identity. Materialization
  разрешена только последующим actual read.
- Весь прежний positive/negative observer/handler loop работает внутри fixture
  lifetime. Direct CLI получает стандартный bootstrap исходного checkout root;
  mirror не попадает в cwd/sys.path. Provenance записывает actual import module
  paths+disk hashes пяти исполняемых modules и отвергает mirror/site-packages origin.

## Provenance и границы утверждений

`setup_provenance` содержит actual checked-out Git HEAD/tree (в CI это может быть
PR merge SHA), complete per-file hashes/bytes/blob modes, source manifest digest,
mirror identity, config delta, actual imports, command argv, cold guard и committed
transaction/generation. `source_manifest_sha256` канонически хеширует fields
path/git_mode/git_blob/bytes/original_sha256 каждой sorted row; mirror digest включает
copied/relocated hashes. Original root identity не подделывается под временную.
V2 только переносит тот же object в `production_setup_provenance`, если поле есть;
старые mocked reports без поля сохраняют прежнюю форму. Это artifact metadata,
не часть public MCP payload, `responses`, case scoring или token estimate.

Dependency/source metadata текущего reader остаётся unresolved; copied tracked
pyproject/code физически сохранены, но не становятся read/mutation membership.
Git witness mirror — not_git; source checkout HEAD хранится отдельно. Этот run не
сертифицирует original storage configuration, Git auto-sync/impact, installed wheel
или actual Claude/Codex/OpenCode sessions. Новая fixture initialization не обещает
пройти неизменённые Legacy/V2 retrieval/quality floors.

## Статическая проверка (выполнена)

- Все 6 изменённых/новых Python modules успешно `ast.parse`; repository imports,
  pytest, Git/server fixture runtime, installs/providers локально НЕ запускались.
- Все остальные runner function/class AST полностью совпадают с base04, включая
  `_call_with_snapshot`. Обе полные positive/negative loop AST совпадают после
  единственной normalization `fixture.root` → `REPO_ROOT`.
- Весь runner scoring/report tail от `positives = ...` побайтно совпадает после
  удаления единственного additive provenance field. Questions/lookups/scopes,
  all cases/negative payload handling/floors/budgets/qualification guards неизменны.
- V2 protocol source совпадает побайтно после удаления двух additive passthrough
  строк. `evaluate`, frozen corpus и acceptance/lineage wrappers не изменены.
- Только названные setup consumer definitions изменены в двух existing test modules;
  все остальные definitions, все decorators/parameter inventories и старые assertions
  сохранены. Legacy malformed preflight всё ещё вызывает явный pre-sync FAIL.
- `tests/test_release_gate.py`: 15 прежних base IDs; `dce84035996d7a074bea07f6def387cdc2081e8fcc2b94ed7b0e0c72f5ed8d19`; все 3 прежних assertions изменённого setup consumer сохранены.
- `tests/test_project_context_quality_protocol.py`: 13 прежних base IDs; `326d78abf4f62354d3a4b277b6234f6f0afcbd5c42302e98074d2ad10c4da48c`; все 8 прежних assertions изменённого setup consumer сохранены.
- Новый inventory ровно 6 fixed base IDs; hash `5971ee4cc33c3cffc4b8e174f16ae450115b99db6d70eab9878cad3105faad14`. Никакой старый
  diagnostic label/hash не изменён. Все modules <1000 строк. `git diff --check` PASS.

## Новые meaningful controls (CI pending)

- `tests/test_project_docs_self_host_fixture.py::test_self_host_cold_read_does_not_create_or_authorize_storage`
- `tests/test_project_docs_self_host_fixture.py::test_self_host_confirmed_prepare_binds_one_host_store_and_copied_project`
- `tests/test_project_docs_self_host_fixture.py::test_self_host_conflicting_config_and_changed_hashes_fail_before_initialization`
- `tests/test_project_docs_self_host_fixture.py::test_self_host_fixture_restores_environment_and_preserves_original_repository`
- `tests/test_project_docs_self_host_fixture.py::test_self_host_snapshot_does_not_select_members_from_questions_or_unselected_files`
- `tests/test_project_docs_self_host_fixture.py::test_self_host_snapshot_preserves_all_catalog_bytes_and_source_boundaries`

Эти nodes предусматривают настоящий fixture-only Git checkout и actual MCP member
preparation/retrieval, полную copy-byte и config equivalence, physical unselected
sentinels при ограниченном index membership, readonly/source identity/import proof,
whole-setup overflow rejection, symlink/hardlink rejection, cold no-grant negatives,
ошибочные content/catalog/entry/CAS bindings до записи, real positive same-store
snapshot/generation checks, conflicting original config rejection и exception-safe
environment/original-repository preservation. Production policy/reader не mocked;
два старых unit scoring harness используют только отдельный setup seam.

Обязательная последующая проверка: независимый source review и один общий обычный CI
на итоговом опубликованном SHA, включая эти 6 tests, unchanged existing parameter
nodes и оба unchanged downstream commands. Без этого runtime PASS не утверждается.

## Frozen implementation hashes

| Path | Lines | SHA256 |
| --- | ---: | --- |
| `scripts/_project_docs_self_host_fixture.py` | 346 | `3a867afe6346bc595c5bf246907c33825f1c9fdcb27fe6982eb2c4f13c0cba85` |
| `scripts/run_project_docs_self_host_gate.py` | 812 | `bc2db12f7ca306c99fa3426304fb1b36431295b9ab287067045cce5b5089b8b5` |
| `eval/project_context_quality_v2_protocol.py` | 452 | `15d23a8c79e73b33efe28e7fa949f536868f2457c718e0c453116d7a8ba12e1d` |
| `tests/test_release_gate.py` | 720 | `f272a812afa28f7d6bcf3491c1473088a0aac90fc5904a62daceb973e247ebef` |
| `tests/test_project_context_quality_protocol.py` | 223 | `d5b0a6a138cf29f28ffcdeb713ffd9ea26e788cb33fb7b9809ddb6351a187169` |
| `tests/test_project_docs_self_host_fixture.py` | 299 | `51831edb77d84af6afe597ebc74c0ec9e962c59b44507231cac51749cc457a49` |
| `tests/diagnostic_labels.project_docs_self_host_fixture.json` | 10 | `bc653faa03300249877061c2d5953fe882e528af4f66b487e4a28b6bd82246eb` |
