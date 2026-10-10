# Независимый integration review member/read + mtime

**APPROVE corrected integration bytes** ниже. Прежний integration APPROVE был отозван из-за missing description в двух authored mtime catalogs; повторная сверка подтверждает correction и точное объединение. Base `04ff1dda57efb5236d7b3577d4e2736b2820df5b`. Runtime **NOT RUN**.

| Файл | Строки | SHA256 |
|---|---:|---|
| `tests/docs/test_module_docs_manifest_e2e.py` | 130 | `03ab60949fbb467487e82257ad0614eb641b892e77f564bd16dfc1e54721ad4c` |
| `tests/evidence_quality_v2/test_readme_neutral_context.py` | 159 | `7334d6493b1273fd4724cca8b27ac6674b4927b29e3d52df95c9b7dae8c9f95c` |
| `tests/test_docs_service.py` | 793 | `75abdfa38c29f7588acbbb0d2e3bcca7fa2021a5a4dec533c32e675c1ef5c1f1` |
| `tests/test_docs_service_part04.py` | 775 | `d8df782d1e2356c3ad64d3ee1800f5cce36eb7206e52fad4651657dae0220e95` |
| `tests/test_docs_service_part03.py` | 794 | `3f763853a94c831db2a7d83f0e115d1f9cca7c7ec26031ce58044b3e10b0af01` |
| `docmancer/docs/application/project_docs_member_transaction.py` | 364 | `e255652379cefb73ce393f2f7e7a1996672e54cda66f608c359ff288c053a2b6` |

Независимо пересчитаны все шесть hashes/line counts и прочитаны предыдущие member/read и mtime reviews. Пять файлов, кроме общего `test_docs_service.py`, побайтно равны своим frozen authored files.

В общем файле сравнение полного function AST подтвердило:

- `test_inspect_project_docs_reports_indexed_and_stale_sources` и `test_get_project_docs_never_returns_hash_mismatched_stale_content` точно равны member/read author версии (`test_docs_service.py` SHA256 `46864d74480a24869130d6d3083991de01a1aa949b93f1d88f5ae3e835a9f00b`).
- `test_inspect_project_docs_does_not_mark_mtime_only_change_stale` точно равен mtime author версии (SHA256 `15de8ad7d6ced8dd8c44b90ba9d12c7aebc56a00b2fddc71279becf764842268`).
- Весь module AST вне этих трёх definitions равен baseline04ff. Ни одна сторона merge не потеряла assertions, fixture inputs или control flow другой стороны.

Повторно сверены все шесть corrected hashes. В обоих mtime catalogs добавлена только обязательная literal `description: Authored project overview fixture.`; все остальные fields/statements/assertions прежние. Полный catalog validator review отражён в corrected `PR211_MEMBER_MTIME_INDEPENDENT_REVIEW_RU.md`, одинаковые bytes которого сохранены в author и integration worktrees. Entries соответствуют schema/field/path/role/scope/description/authority/status/impact требованиям; actual runtime validation остаётся NOT RUN.

Для всех шести modules дополнительно подтверждены AST-exact contents вне девяти разрешённых function bodies (восемь existing tests и `_execute_pinned`), прежние signatures/decorators и **97** неизменных base test names. Новых или удалённых collection nodes интеграция не добавляет. Все модули ниже 1000 строк; `git diff --check` PASS.

Root inventory `04ff1dd-member-integration-source-checks.json` совпадает с независимыми результатами, SHA256 `397511b0e2e1c2119a447bbc2bd1f0770d49303e38dff30d6e668fffee69b30d`. Сохраняются границы отдельных reviews: descriptor-bound mtime, metadata/generation consequence, explicit member grants, stale/foreign controls и отсутствие post-mutation reindex в read tests. Фактические исходы и repeat/CAS безопасность нового production source должен подтвердить обычный CI на итоговом SHA.

Новых runtime/import/test/provider/client операций не было. Self-host slice этим review не покрывается. Изменён только данный report.
