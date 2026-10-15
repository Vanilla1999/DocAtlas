# PR #211: exact Dartdoc fixture migration

Дата: 2026-10-08. База `03583656617336a746e9192249467017d6131f29`.
Slice разрешён владельцем работы после read-only классификации remote failures.
Изменён только
`tests/test_web_fetcher.py::TestWebFetcherDartdoc::test_direct_dartdoc_class_page_without_browser`.
SHA256 testfile:
`2c6a1e7826c8f4d0e2f424155c14367fb1b362bb2a2b0ef0f4e84860f6149923`.

В исходном сценарии уже задан точный URL
`https://api.flutter.dev/flutter/widgets/SizedBox-class.html` и authored
`DARTDOC_SIZED_BOX_HTML`; сценарий проверяет извлечение class/constructor/property
без browser. Его первый barrier в 3be9c34 core JUnit — отсутствие explicit member
selection. Этот сценарий не проверяет nav/index/sitemap discovery. Выбранный
URL не извлечён из HTML, ожидаемого результата или ответа discovery.

Текущий `_fetch_finite` требует nonempty exact selection, selected entry URL,
полную preflight-проверку transport policy и отдельно объявленный robots control.
Положительный fixture теперь передаёт только прежний class URL в `exact_urls`,
а `https://api.flutter.dev/robots.txt` — отдельно в `robots_urls`.
`max_pages=10`, `browser=False`, `doc_format="dartdoc"` сохраняются;
`respect_robots=True` остаётся default и явно проверяется. Ни work/security
limit, ни production contract не меняются.

Исходный MagicMock HTTP response заменён настоящими HTTPX responses через
fixture-owned MockTransport. Сохранён настоящий `_new_client` и DocsHttpClient,
включая DNS validation, IP pinning, Host/SNI, redirect/member checks и response
bounds. Только resolver возвращает фиксированный публичный IPv4, поэтому нет
DNS/network зависимости. Политика разрешает прежний host и два конкретных path
prefixes; exact content/control memberships остаются раздельными. Factory
захватывает настоящий `httpx.Client` до patch и создаёт новый offline client для
каждого штатного вызова. `WebFetcher._new_client`, DocsHttpClient, validation и
extraction не подменены; patch затрагивает только конструирование raw
`httpx.Client`, добавляя ему MockTransport.

Handler проверяет pinned host `93.184.216.34`, восстанавливает исходный URL по
Host/raw_path, обслуживает только объявленный robots control либо прежний exact
class URL. Исходный `assert url == ...SizedBox-class.html` сохранён без изменения
в content branch. Для robots задан явный allow response; обход robots не введён.
Exact request trace `[robots, selected]` исключает дополнительные document URLs,
nav, llms, sitemap, index или browser fallback.

Добавлены два отрицательных контроля на том же реальном production route:

- query-variant entry URL вне exact selection отклоняется с
  `finite_member_seed_mismatch`;
- тот же выбранный документ без объявленного robots control отклоняется с
  `explicit_robots_member_required`.

После обоих отказов trace по-прежнему ровно `[robots, selected]`: дополнительный
HTTP request не допускается. Exact returned source identity проверяется отдельно.
Исходные пять post-fetch assertions (один документ, SizedBox class, Constructors,
width, browser=False) сохранены дословно. Вместе с исходным URL guard все шесть
прежних Assert AST присутствуют в successor; новый node содержит 11 Assert AST.

Статические проверки: signature/decorators unchanged; AST всего module вне одной
function byte-equivalent базе; fixture HTML и все остальные test bodies unchanged.
Module содержит 957 строк, меньше действующего предела 1000. Сохраняются 35 base
test IDs и hash `83a06465f2bab1e48fc02d9a2b330e9f5795b0ad9c953744c597c1e20cab58c7`,
независимо вычисленный из AST и совпадающий с неизменённым diagnostic manifest.
`ast.parse`, compile без исполнения и `git diff --check` — PASS.

Это миграция одного offline fixture на текущий explicit fetch contract.
Другие remote discovery/canonical/provenance failures, production, retrieval,
gold, thresholds и workflows не менялись. Repository runtime/imports, pytest,
provider/client calls и installations локально не выполнялись. Runtime PASS
не утверждается: необходим независимый review и обычный CI на опубликованном SHA.
