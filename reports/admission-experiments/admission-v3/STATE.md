# Admission V3 — состояние

2026-10-12. Новый запрос владельца разрешает исполнение ограниченного V3.

- HEAD `4849b8f796d9e3e25e2c49e58562ec6859978411`, ветка `fix/main-flow-compact-evidence` подтверждены.
- Пять modified и untracked selector из V1/V2 сохранены; повторное применение patches запрещено.
- Default OFF; commit/push/merge/release, новые модели/providers/downloads запрещены.
- A: анализ admission-контракта, только A_ADMISSION_CONTRACT_RU.md до разрешения product patch.
- B: client citation adapter и его контракт; product DTO не меняет.
- C: review/ — новые frozen inputs/oracle и независимый review; product не меняет.
- Координатор: protocol, runtime, ledger, итоговые артефакты. Все public/model/host calls только последовательно координатором.
- Docs MCP вернул insufficient_evidence/source_unavailable; разрешён переход к source inspection, без повторения.
- Пока runtime не начат; contract delta и точный меньший workload будут зафиксированы до inference.

## Pre-inference продолжение

- CONTRACT_DECISION_RU.md фиксирует узкий scalar-label fallback; multi-facet/empty-source ограничения явны.
- A реализовал только два назначенных domain файла; V3_PRODUCT.patch относительно сохранённой baseline.
- C заморозил 7 новых cases и 2 controls, 17 hashes; labels не переданы A/B.
- PROTOCOL_V3_RU.md и EXECUTION_CONFIG.json фиксируют 19 cases/57contexts/7prepares/28host/0forwards.
- Citation fixed IDs: V3CAL01/V3H01 parent V3, Q16/Q46 parent B1.
- Первый независимый static preflight выявил неправильный envelope hash operand и неполный authority guard B; исправления запрошены до runtime. Это НЕ failed integration cycle: запусков ещё нет.
- Source/adapter/runner hashes замораживаются после final preflight, до execution.

- C обнаружил source-edge sign/operator gap и stop-guard gaps до запуска. A исправил проверку контекста по полному raw без расширения delivery; координатор добавил strict authority, envelope/line/duplicate/source-authority/pool-identity и preparation-set guards.
- Frozen-files gate теперь проверяется до импортов product/reused runners; список непустой (40 operands). Финальные runner/patch/config hashes сохранены в SOURCE_IDENTITY.json. Runtime всё ещё 0, требуется consolidated final static review.

## Исполнено

- review/EXECUTION_GATE_RU.md закрыл обязательные static blockers до первого runtime.
- Один непрерывный coordinator run: 7 prepares / 57 contexts / 28 host attempts / 0 neural forwards, 136.946345699s; errors 0, все host outputs сохранены.
- Все 40 execution identities неизменны после runtime. Исходный C freeze не редактировался.
- 4 citation extraction outputs EXTRACTED без repair; это только адресация/дословность, semantic PASS пока не заявлен.
- COSTS_V3.json учитывает real requests/parent reuse/reconstruction/actual prompt chars+UTF8 bytes; billing/tokens/backend UNKNOWN, timing sums lower bounds.
- C выполняет final saved-data/source/semantic независимый review. Больше public/model/host запусков не запланировано; успешный execution не даёт default approval.

- Дополнительный учёт: до experiment был 1 Docs MCP documentation lookup (insufficient_evidence/source_unavailable), записан отдельно от 57 evaluation contexts: всего 58 context requests внутри потолка80. Setup `python` alias error127 не потребил product/model/host вызовов; сохранён в ledger.

## Финал

- C independent review завершён: все57public/28rawhost, source-policy audit errors0;40execution/17freeze/397product/315raw hashes проверены.
- Новые positive complete1/4→3/4 (CAL01/H02 gains); known numeric0/3→1/3 (HOLD03). CAL02/refunds/cargo fullFAIL сохранены.
- Strict negative contract6/9FAIL B1/V3, Default9/9PASS; все8negativehostrefusalsPASS не исправляютpacketFAIL.
- Coordinate4/4exact+semanticPASS противbase-parent literal2/4, ноsubmittedchars+99.7%; этоновый generator/clientcontract, неrankergain.
- RESULT_V3_RU.md, RESULTS_V3.json, INDEPENDENT_REVIEW_RU.md, COSTS_V3.json, COMPACT_CHECKPOINT_RU.md завершены. DefaultOFF, новых запусков нет. Только новый запрос владельца может разрешить продолжение.

## Отдельное поручение владельца: commit

Создан commit `6adc8e655fa69b5475adf613c8c446dd3a604b98` в `fix/main-flow-compact-evidence`, message `feat(docs): add opt-in admission and candidate selection experiments`. Все6 файлов совпали с independently reviewed V3 hashes до staging. Working tree clean. Push/default/deployment/new runtime не выполнялись. Исторические research receipts/HEAD остаются неизменными; добавление commit не является новым runtime PASS.

Пределы: 8 prepares / 80 contexts / 40 host attempts / 500 forwards / 7200 runtime seconds / 4 GiB; CPU ≤8 threads, ≤12 GiB RSS/process.
Никаких unit/private-helper/AST/compile checks. Никаких удалений tests/fixtures, retune V2 holdout или повторения UNKNOWN.
