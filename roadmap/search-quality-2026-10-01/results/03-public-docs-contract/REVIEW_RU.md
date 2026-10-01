# Саморевью шагов 03 и 04 перед коммитом

Это саморевью автора изменений, не независимый quality gate. После исправления замечания блокирующих проблем в выбранных границах не обнаружено.

## Замечание к шагу 03 — исправлено

В начальном response-contract абзаце `docs/mcp-docs-server.md` осталось `The host may answer only covered claims`: это конфликтовало с новым разрешением host synthesis по verbatim snippets при unverified facets. Новый assertion воспроизвёл ошибку ([review red](review-red.log)); теперь абзац явно разрешает поддержанные snippet facts независимо от unverified facets и не обещает completeness. В этом же абзаце `docs_answer` ограничен library/dependency/mixed lanes, согласованно с ADR 0003. Runtime, flags и edit guards не менялись.

## Шаг 04 — границы подтверждены

ADR 0003 явно retired project-answer v1–v4; исправлен только подтверждённый v1 catalog entry. ADR 0002 уже superseded, ADR 0003/current context protocol остаются active. Не удалены исторические cases и команды; active roadmap и supporting plans не превращены ни в current operational guarantees, ни в blanket deprecated sources. Module/project scope, lifecycle validation и existing history routing не менялись.

## Повторные проверки

- [81 passed](review-tests.log): оба новых regression modules, catalog, task19 closure, self-host agent surface, public output contract, retrieval features.
- [10 control packets после ревью](review-controls/provenance.json), тот же список original questions; это consistency probe, не A/B recall measurement.
- [Installed MCP stdio повторно PASS](../04-corpus-authority/review-installed/provenance.json): текущие sources только active; явная history evaluation возвращает retained superseded v1. [Evidence IDs/роли](../04-corpus-authority/review-installed/evidence-roles.json) привязаны к fixture catalog. Runner получил `--output`, чтобы повторный запуск не переписывал прежние результаты.
- Archive manifest hashes, diagnostic node hashes и corpus parity обоих review fixtures проверены. Ни один production Python файл не изменён.

## Оговорки

Full suite, независимый reviewer gate и улучшение recall не заявляются. Fixtures ограничены выбранными страницами; не проверен каждый исторический документ. Исторические прогоны сохраняют исходные corpus hashes; итоговые review прогоны соответствуют текущим bytes. Оставшиеся ограничения предыдущих шагов не закрыты. Общий коммит шагов 03–04 сделан по явному запросу пользователя; без push/merge, шаг 05 не начат.
