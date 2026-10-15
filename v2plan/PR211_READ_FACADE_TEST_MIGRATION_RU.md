# PR #211: spies на текущем read facade

## Фактическая отправная точка

[Core reader](https://github.com/Vanilla1999/DocAtlas/actions/runs/38003248365/job/114068441329) для PR head `1c6c2c8454cdd6fe797fe80e85f3b651aef01a0a`, merge checkout `64caa3caf213a6a67d44c92546660ef1ced23d87`, shared tree `8a544267409f0dbf3ab498dfa864c07b13cdfb73`: на каждой Python **6031 PASS / 1748 FAIL / 0 ERROR / 10 SKIP**.

Сравнение модулей с последним полным a348 показывает три добавленных FAIL:
- catalog equivalence: **4 PASS / 1 FAIL**, healthy positive получил failed вместо ok;
- MCP dispatch boundary: **2 PASS / 1 FAIL**, handler_exception вместо permission_denied;
- context projection boundaries: **13 PASS / 7 FAIL** вместо 14/6.

Для первых двух источник подтверждает старую сигнатуру spy: dispatcher передаёт keyword `read_only_startup`, старый spy его не принимает. Ошибка возникает до счётчика service/ожидаемого PermissionError.
Третий новый node не восстановлен из полного traceback: два чтения больших core logs завершились Transport closed; first-failure reader показывает прежний path-only FAIL.
Найденный ниже fixture defect подтверждён цепочкой вызовов, но пока не объявлен фактической причиной именно нового +1 FAIL.

## Точный контракт

`docmancer/mcp/_docs_server_part01.py`, blob `9e6e57dfd786ad1665497524785db5fad093a439`:
- docs_status и get_docs_context вызывают service routing с read_only_startup=True;
- confirmed member sync остаётся отдельным validated cold path;
- cold.project_docs создан отдельно от materialized reader.project_docs.

`eval/evidence_quality_v2/runtime.py`, blob `73e5e30fe41394d2be33271a03d9e550bf6f4ae1`, передаёт обычный fixture method lookup в read facade.
Явный materialize() выбирает writable facade. В test_gap_quote_is_not_a_mutation_grant он вызывался уже после before fingerprint только для установки spy, хотя последующий direct sync использует reader.
Service facade `728a7c62e46eebd19f65c90e86059db1bad788fa` делегирует sync своему project_docs; настоящий service `6e203fc973122da90a1532f639944398622c3bd1` без mutation немедленно отказывает до legacy producer.

## Изменения и сохранённые проверки

1. Два routing spies принимают обязательный keyword и утверждают именно True. Healthy effects 1/1/1, invalid-input effects 0/0/0, ожидаемый permission_denied и все no-initialization guards сохраняются.
2. Mutation fixture получает уже используемый reader, проверяет его cached identity и bound-method owner, ставит прежний producer spy на него. Дополнительно требует отсутствие созданного writable service. Before fingerprint и финальное равенство generation/DB bytes остаются на прежних местах; первый cold.project_docs spy также сохранён.
3. Existing JUnit reader выводит node outcomes этих трёх модулей и existing incremental-generation selector; failures четырёх модулей получают bounded trace. Полный artifact, counts, integrity verdict, required-ci и operational console cap не меняются.

Ни одной test function или параметризованного случая не добавлено и не удалено; production здесь не изменён.
Два routing diff независимо проверены alias reviewer; reader/fixture — readonly reviewer; root проверил source ownership и сохранность прежних guards. **APPROVE static; runtime pending.**

## Manifest

| Path | Base blob | Reviewed blob |
| --- | --- | --- |
| tests/docs/test_pr211_catalog_equivalence.py | 95f35311dd0eb747e0d2e721e81ada457ea604da | 3709ec82d62af26a033e154cbf42f4b35b9214c1 |
| tests/test_mcp_delivery_dispatch_boundary.py | c3ebfdb60e96baa6541e7c194f5d8d42f1209afd | d10a8031cea801f3412604d77af0f9dd0369a4e7 |
| tests/docs/test_context_projection_boundaries.py | 2dd7a23e348461695ec278e518042708907dedc7 | 8a4151b586f0f14405b363feaacfbbb1d69e47b7 |
| scripts/summarize_pytest_acceptance.py | 5a5001a5c3a6c36e5bc0c06a86b89334d4f473b2 | 3de25fe8481ccd8ac13d2deeb215d73610ca59fd |

Нужен совместный actual core на конечном SHA. Известные другие шесть projection failures и остальные quality/downstream gaps здесь не решены. Локальные imports, tests или subprocesses не выполнялись.
