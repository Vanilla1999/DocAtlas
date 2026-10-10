# P1.5: ownership выбранного fixture host до library preparation

## Фактический результат на 2acfaa4f

[P1.5 run 37994136720 / job 114035683948](https://github.com/Vanilla1999/DocAtlas/actions/runs/37994136720/job/114035683948) выполнился на `2acfaa4fdac8cc599d84ae1c48836335e9cd29a7`:

- 1/7 cases, 0/6 complete facts, 5 runtime errors.
- Все шесть oracle self-controls, current-report integrity и source syntax/format checks прошли.
- В пяти external-source случаях preparation теперь останавливается с `status=failed`, `reason_code=job_failed` и пустым `target_results`: непустой fixture `docatlas_home` не имеет общего `state-owner.json`.
- Прежняя ошибка `explicit_robots_member_required` в этом запуске не наблюдается. Это ещё не доказывает successful preparation или корректные remote source/read-only результаты.
- `document_statement_binds_exact_path` по-прежнему проваливает только full-fact check; его authority, source integrity и read-only проверки проходят. Другой local-only negative case прошёл целиком.

Полный артефакт: [11645868801](https://github.com/Vanilla1999/DocAtlas/actions/runs/37994136720/artifacts/11645868801), ZIP SHA-256 `a6333b164fefb4477e270840bb5864275b367d74e37d509226fb548820480a68`.

## Причина и узкое изменение

`isolated_service` выбирает новый приватный временный host namespace и возвращает холодный MCP facade без создания state, registry или owner marker. Первый `sync_project_docs` создаёт `mcp-members/members.db` и отдельный inode-bound `members.db.member-owner.json`. Это ownership конкретного member store, а не общее ownership machine state.

External library preparation также использует machine-state consumers. Их действующий `ensure_owned_home` обоснованно отказывается присваивать уже непустой `docatlas_home` без общего marker. Общая директория к этому моменту уже содержит подготовленный member store.

P1.5 теперь до `index_project` и `service.materialize()`, только при наличии external targets, вызывает действующий `ensure_owned_home(service.member_storage_policy.app_home)`. Путь приходит от host-selected policy холодного fixture service, не от документа, каталога, question или remote URL. Это явное provisioning изолированного fixture host перед public preparation.

Initializer сам проверяет missing/empty/already-owned state; foreign, symlinked и ambiguous nonempty roots по-прежнему отклоняются. Здесь нет ручной записи marker, присваивания непустой директории, очистки state или ослабления production guard.

## Сохранённые границы

- Общий `isolated_service` и cold-storage behavior остальных suites не изменены.
- Public project/library preparation и требование genuine succeeded job не изменены. Изменение не принимает partial/failed job за успех.
- Сохранены исходные 7 вопросов, 13 question candidates, 6 full facts, 2 negatives; robots остаётся отдельно объявленным frozen infrastructure member без fact credit.
- Manifest grants, два exact URL, version/source identity, actual stored bytes/hash/lineage, read-network prohibition, scorer и output-cost observation прежние.
- Host setup находится до measured `state_before`; retrieval-call/validator counts и сравнение индексов, каталога, документов и registry остаются прежними.
- Никакие локальные Python imports, subprocesses, provider/model/server runs при подготовке этого slice не выполнялись.

## Manifest и приёмка

Base commit: `2acfaa4fdac8cc599d84ae1c48836335e9cd29a7`.

| Путь | Base blob | Proposed blob | Mode |
| --- | --- | --- | --- |
| `eval/agent_developer_v1/mixed_retrieval_runtime.py` | `3c0236d3b9b0e46f87e6db54ebd06e16425a02a8` | `a384e125bb208eb2f8902fe62a4b98a5d4e73590` | 100644 |

Runtime изменён на пять строк: import и guarded initializer перед первым public member preparation. Всё после `project_preparation = index_project(...)` побайтно совпадает с базой. Self-control функции не добавлены и не удалены.

Статический review не является runtime PASS. После independent review и публикации нужен обычный P1.5 job на новом SHA: фактический succeeded preparation, полные stored members и отдельные source/read-only/full-fact результаты.
