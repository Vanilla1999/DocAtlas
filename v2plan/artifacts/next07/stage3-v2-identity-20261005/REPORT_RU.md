# Продолжение стабилизации: V2 identity закрыта, quality остаётся FAIL

**BLOCKED_OWNER_DECISION_REQUIRED_AND_BASELINE_CAUSES_UNRESOLVED**

**main merge: NOT_DONE.** Независимое ревью PENDING. Этап 3 не завершён.
Опубликованный baseline не пересоздавался; reused evidence index на 2bf8cfde
проверен. Исходные пользовательские изменения не затронуты.

## 1. Frozen documents — оба IDENTITY_ONLY_SAFE для used V2 facts

| Document | Historical commit | Git blob |
|---|---|---|
| README.md | be4e9c7e5aa2dfa3a99aabb06078ac7015f8a295 | 1a1975b2ffaf587f3b752c1966acdb20e7a88468 |
| docs/project-docs-mcp-workflow.md | 2facdba3b84c1c5e4a396b4e0d06b2a5e32aacd4 | 316a520a4df91ebb577da84c99d783c3583b035f |

Expected/current SHA256, полный diff, все obligations, cases, scope/authority,
условия, отрицания и обязательные части: `DOCUMENT_SEMANTICS_RU.md`,
`raw/provenance.json`, `raw/identity-proof.json` и lossless `.diff.json` файлы.
Команды onboarding и соседняя authority policy менялись; они не являются
используемыми фактами этих двух документов в V2. Используемые sync/catalog/
health/install/product statements и их условия сохранены. Подробное авторское
semantic review сопровождает executable checks — substring equality отдельно
не считается доказательством смысла.

PR #210, branch `fix/stage3-v2-document-identity`, exact head
**aafe6a461013bb0de97c3097253c7cb81cacfca7**, base exact main d2ed5c4c.
Изменены только:

- `eval/project_context_quality_v2/protocol.lock.json`: два document hashes;
- `eval/project_context_quality_v2/acceptance.lock.json`: один dependent lock hash.

Byte proof соответствует historical approach 18f53fe6: fixed-length replacements,
обратимость и отсутствие других изменений. Executable proof опубликован в
research, не добавлен в product PR с разрешённым составом только двух файлов.
Existing inventory FAIL before (published exact baseline); **47/47 protocol tests
PASS after** на committed identity head. Полный V2 quality после снятия identity
блокера выполняется и реально FAIL, не превращён в PASS обновлением hash.

## 2. Разбор 22 failures и итог 17

`FAILURE_CLASSIFICATION.json`: отдельный record на каждый из исходных 22 node IDs,
exact fixture/request/expected source, before traceback/locals, after observed
request/response frames, owning function там, где доказана, и native node reproducer.
Preflight не имеет runtime request/response: NOT_EXECUTED обозначено явно.
**Полная причинная классификация всех оставшихся отказов NOT_DONE.** Неизвестный
owner сохраняется как null; похожие названия не используются для общей причины.

Две доказанные общие причины:

1. **8 V2 preflight failures**: одно и то же сравнение active_document hashes в
   `eval.project_context_quality_v2_protocol.validate_corpus`, line 180. Refresh
   снимает этот blocker во всех восьми; **5 node IDs становятся PASS**, а три
   открывают deeper existing failures: stale-health missing witnesses, first-session
   missing query witness и evidence-selection missing selection_proof.
2. **4 failures на budget=256**: projector правильно ставит docs/diverse.md первым,
   затем отклоняет полный DTO: **268 > 256**; docs/single.md **263 > 256**.
   Первый установленный divergence — complete DTO token admission line 528
   `_docs_context_projection_core.project_docs_context`, не порядок ранжирования.
   Existing budget=800 controls PASS при обеих ориентациях и числе aliases.
   Лимиты/expectations не изменены. Без доказательства безопасного representation
   fix не убирались поля/guard checks ради вместимости.

Отдельно доказанный preflight конфликт: direct-15 sidecar требует frozen README
Git blob 1a1975b2..., current blob 9678dd4d10ca77856e33393ffa8e0db1c7539772.
Это другой freeze, не два разрешённых V2 lock-файла. Все exact direct-15 witness
texts в active docs присутствуют, но gate требует **также** exact full-document
identity. Его gold/sidecar не менялся. **OWNER_DECISION_REQUIRED** для допустимой
проверки frozen vs active revision либо отдельно разрешённого identity refresh;
просто заменить sidecar hash вне разрешённого состава нельзя.

Прочие наблюдения не выдаются за общие owning causes:

- Request-flow: не все четыре fact witnesses видны; два independent assertions
  показывают неполную выдачу. На полных run метрики и наборы missing могут отличаться;
  не объединяем с другими completeness failures без доказанного upstream loss.
- Projection_clip: действующий projector доставляет поздний source-bound testing
  факт, тогда как old case ожидает потерю/исключение источника. Scope/source integrity
  checks PASS до failing old assertion; clipping expectation не изменялась.
- Unknown Pebble question: retrieved safe witness существует; projector получает
  пустой context_pack. Trace подтверждает, что initial project_context_pack был
  непустым и placeholder/low-value/trust фильтры его не отклонили; последующий pack
  пустой. Точный owning transition не доказан полностью, поэтому не добавлены
  aliases/dictionary/parser exceptions и не снят guard.
- Frozen V2 contract hash, лишний canonical_intent в question plan и retrieval IDs
  query-hint vs anchor/original имеют самостоятельные exact reproducers; owner
  недостаточно доказан для совместного исправления.
- Тест с именем non_project_docs включает docs/note-* в catalog как supporting
  **project** docs. Ответ содержит именно этот project, не внешнюю/модульную утечку.
  Реальный конфликт — исключение supporting distractors; исправление по одному
  названию теста или ranking heuristic недопустимо.

Исходные **22 FAIL → 17 FAIL**. Full core: **5282 PASS, 10 skipped**.
Skipped не засчитаны PASS. Related modules: **191 PASS / 14 FAIL**; это не green
positives/negatives certificate, оставшиеся FAIL явно сохранены.

## 3. Scope/status/budget конфликт gate

`raw/scope-case.json` содержит existing case
`module_scope_rejects_project_policy_detail`, фактический request и полный response.
Нет запрещённых ARCHITECTURE.md/payments sources; единственный source — scoped
orders/README.md. Response: retrieval-only, partial, answer_supported=false,
edit_ready=false; **не сертифицированный ответ о числе retry attempts**.

Gate требует insufficient_evidence и 300-token packet. Но actual `_context_args`
**не передаёт packet_tokens**; удалённое поле исключено при миграции d30aeec1
(`#174`). Response 380 > frozen gate ceiling 300 остаётся FAIL. Нельзя называть
это доказанным нарушением **переданного** caller limit, которого в request нет.
**OWNER_DECISION_REQUIRED**: согласование frozen status/budget gate с нынешним
retrieval-only/API контрактом либо отдельно разрешённое исправление producer,
которое сохраняет текущие требования. Никакой policy change здесь не принят.

## 4. Новый clean integration, без изменения #209

Branch `integration/stage3-v2-identity-pr1`, draft **#211**.
Head **264694706ff3c521abaf616f366db02a014362ea**.
Base **d2ed5c4c73dc3b7d56276fc37591cba8a4ae123c**.
CI synthetic checkout **dc03bf97d4a812334faabb4e5758b44ba5f460e0**.
Parents = exact main + exact integration head. Это не реальный main merge.

Состав: #208 FastEmbed pin + #210 identity refresh + исходные четыре PR-1 commits.
Cherry-pick provenance и подтверждение unchanged PR-1 diffs в index.
Новых algorithmic baseline fixes не добавлено без доказанной безопасной причины.
Исходные #206/#208/#209 heads неизменны. Owner acceptance #208/#210 не утверждается.

## 5. Проверки exact candidate

Focused: **110 PASS** (PR-1 42, FastEmbed/multilingual 21, V2 protocol 47).
Все 22 прошлых native node IDs отдельно replayed: **17 FAIL / 5 PASS**.
Full local core и CI 3.11/3.12/3.13: **17 FAIL / 5282 PASS / 10 skipped**.

Hosted CI run **37315327369**, attempt **1**, checkout dc03bf97:

| Gate | Job ID | Результат |
|---|---|---|
| Core 3.11 | 111780505242 | FAIL |
| Core 3.12 | 111780505221 | FAIL |
| Core 3.13 | 111780505527 | FAIL |
| Advanced/security pytest | 111780505230 | 622 PASS, job позднее FAIL на lineage |
| Installed MCP harness | 111780505018 | PASS |
| Windows | 111780505042 | PASS |
| macOS | 111780505592 | PASS |
| Installer | 111780504935 | PASS |
| Static | 111780505308 | PASS |
| Docs/CLI | 111780505190 | PASS |
| Retrieval evidence | 111780505489 | PASS |
| required-ci | 111785249540 | FAIL |

Release validation **37315327379**, attempt **1**, exact checkout dc03bf97:
build 111780505259, wheel 3.11 111780922556 / 3.12 111780922675 /
3.13 111780922574, sdist/installer 111780922539, required-release 111782135407:
**PASS**. Publish/public-release smoke/registry steps skipped по условиям PR;
это NOT_EXECUTED, не PASS и не release.

Локально на head 26469470 исполнены все subsequent gates независимо от CI stop:
recovery contract/mutation, agent developer, critical mutation, adversarial mutation,
source stdio, harness self-test — PASS. Legacy report generation exit 0 — не quality
PASS. Lineage **11 < 12 FAIL**; V2 natural semantic **9/15**, component **9/15** и
exposed lookup **11/12 FAIL**; question-surface **FAIL**; adversarial **FAIL**.
Skipped CI steps не подменены чужим SHA: separate local executions явно отделены.

Reviewed installed wheel + real MCP/stdio + report verification **PASS**, 1/1 task,
full source_commit=26469470; это deterministic pre-public harness, не LLM experiment
и не smoke разрешённого main merge. Wheel SHA256 в index.

Полный gate roster, точные Run commands, exit evidence, branch head, checkout,
run/job/attempt: `GATE_ROSTER.json`, `raw/ci-raw.log.json`, release raw logs,
`raw/candidate-gates/ledger.json`, `LOCAL_EXECUTIONS.json`.
Нативные action steps имеют conclusion, но не числовой process exit от API;
он не придуман. Exit 0 для successful Run steps выводится из штатной runner
семантики и обозначен `inferred_from_step_success`; явно залогированные exits
сохраняются отдельно. Unknown/skipped/queued checks остаются таковыми.

## 6. Публикация и границы

Product diff просмотрен; git diff --check exact main→product heads PASS.
Research report отдельно: `EVIDENCE_INDEX.json`. External observation hooks только
читают frames/return values, не заменяют runtime callable/fixtures/results.
Не менялись workflows, guards, parser/ranking, cases/gold/thresholds/budgets,
public schema/API, 800/3, 32000 или explicit caller limits.
N10, PR-2/read-path, retention и LLM эксперименты не выполнялись.

Готовности к main нет: остаются 17 failures, незавершённая owning-cause диагностика,
явные acceptance/API conflicts и внешнее независимое ревью. Нет owner-approved
изменения acceptance policy. **main merge: NOT_DONE.**
