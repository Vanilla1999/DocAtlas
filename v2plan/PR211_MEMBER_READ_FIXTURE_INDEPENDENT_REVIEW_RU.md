# PR211: независимый review member/read fixture migrations

**APPROVE** точных source bytes ниже. Base `04ff1dda57efb5236d7b3577d4e2736b2820df5b`.
Runtime **NOT RUN**; review не объявляет шесть tests PASS.

Root независимо прочитал весь diff четырёх модулей и текущий confirmed fixture
helper, member transaction, source-state/read boundaries. Во всех шести target
functions исходные statements за исключением legacy setup сохранены в прежнем
порядке. Остальные definitions, names, signatures и decorators AST-exact.
50 исходных assert AST сохранены буквально; единственный inline sync-success
assert заменён на status того же реального результата. Новых pytest nodes нет.

## Что сохраняет migration

- Module test объявляет ровно прежние README/orion/vega members из неизменённого
  catalog. Все module scope/path, nonempty read и public MCP assertions прежние.
- Foreign source реально добавляется в ТОТ ЖЕ trusted store после owned source.
  Один captured generation используется как CAS; refresh/retry нет. Проверяются
  две непустые generation rows, полные text/content/catalog bindings и разные
  project identities. Обе строки остаются в новой generation, deletions=0.
  Проверка catalog entry hash для обоих корректна: catalog скопирован буквально,
  одинаковый relative README entry не зависит от project identity. Этот setup
  positive не объявляется отдельным successful foreign MCP answer. Исходные
  public non-contamination/integrity assertions и вопрос сохранены.
- Четыре README fixtures явно задают единственный supporting/overview member.
  Catalog supporting является текущим default, а overview требует project scope.
  Это attribution данных, не instruction/answer/edit authority. Roots/code_files
  явно пусты, нет discovery по ожидаемому результату.
- Indexed/stale inspect case сохраняет прежний положительный ready-state перед
  изменением bytes. В трёх read guards добавлен реальный непустой read того же
  исходного вопроса до прежнего изменения README: проверяются path/source,
  текущий content SHA и marker. После изменения документа sync не вызывается.
  Исходные stale/confirmation/empty-result assertions остаются прежними.

Current helper использует private host store, explicit confirm и точные
source/catalog/entry hashes; cold CAS None, generation binding, отсутствие vectors
и deletions проверяются реально. Shared helper, production, исходные questions/
document text, oracle expectations, thresholds, workflows и retrieval не меняются.
Отдельный root mtime slice интегрируется только после своей проверки; этот review
не присваивает его production outcomes этим fixture bytes.

Статически проверены AST parse/compile без исполнения, полный statement order,
исходные asserts и module size. 73 base test names и diagnostic inventories
сверены авторским полным inventory; root independently verified неизменные names/
decorators всех четырёх parsed modules. Модули130/159/768/775 <1000.
`git diff --check` PASS. Runtime входит в последующий обычный full CI.

| File | SHA256 |
|---|---|
| tests/docs/test_module_docs_manifest_e2e.py | 03ab60949fbb467487e82257ad0614eb641b892e77f564bd16dfc1e54721ad4c |
| tests/evidence_quality_v2/test_readme_neutral_context.py | 7334d6493b1273fd4724cca8b27ac6674b4927b29e3d52df95c9b7dae8c9f95c |
| tests/test_docs_service.py | 46864d74480a24869130d6d3083991de01a1aa949b93f1d88f5ae3e835a9f00b |
| tests/test_docs_service_part04.py | d8df782d1e2356c3ad64d3ee1800f5cce36eb7206e52fad4651657dae0220e95 |

Author report SHA256: `f7abc15c44727810c9f2355489461debe50a372f064a9f1e6544eabbb0b27e64`.
Independent source inventory: `04ff1dd-member-read-independent-source-checks.json`.
Before publication общий test_docs_service.py требует integration AST comparison
обоих непересекающихся reviewed slices; старые file hashes не заменяют merged hash.
