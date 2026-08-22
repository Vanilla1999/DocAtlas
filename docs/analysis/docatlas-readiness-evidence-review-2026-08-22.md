# Повторный доказательный анализ готовности DocAtlas

Дата среза: **22 августа 2026 года**  
Базовый post-repair `main`: `867e609694fbf05963781a87960469439706c13a`  
Статус документа: **supporting analysis**, не новый source of truth. Канонические статусы остаются в [`roadmap/README.md`](../../roadmap/README.md), [`docs/public-truth-scorecard.md`](../public-truth-scorecard.md) и [`docs/release-identity.md`](../release-identity.md).

## Резюме

После повторной проверки и merge [PR #131](https://github.com/Vanilla1999/DocAtlas/pull/131) состояние проекта изменилось существенно:

- подтверждённый fail-open на границе recovery → edit authorization исправлен;
- Agent Developer adversarial gate теперь проходит **28/28**, без нарушений;
- source-search recovery больше не может самостоятельно выдать `edit_ready=true`;
- legitimate explicit patch workflow при этом не сломан: безопасный локальный поиск исходного кода остаётся допустимым следующим шагом;
- semantic `1.3.1` находится непосредственно в reviewed tree;
- одноразовые `materialize-*` / `materialize_*` carriers удалены;
- exact-head `required-ci` и `required-release` зелёные;
- repair merged в `main` как `867e609694fbf05963781a87960469439706c13a`.

Но **Public Truth всё ещё не закрыта**: `v1.3.1` пока не существует, PyPI Trusted Publisher для replacement identity не доказан успешной публикацией, exact public bytes не зафиксированы, а post-publish Linux/macOS/Windows MCP smokes не выполнены. Поэтому P0.6 остаётся `INCOMPLETE`, а maturity — **Beta**.

Также по-прежнему не доказаны Agent Truth и Product Truth: deterministic/oracle trajectory закрывает 11/11, историческая autonomous live trajectory остаётся 0/11, причинный first-divergence atlas отсутствует, а реальное улучшение coding outcomes не показано.

## Как в этом анализе классифицируются проблемы

Чтобы не смешивать дефекты, blockers и исследовательские неизвестные, используются четыре класса.

### 1. Подтверждённый дефект

Должны одновременно существовать:

1. воспроизводимое наблюдаемое поведение;
2. declared contract или acceptance criterion, которому оно противоречит;
3. тест, fixture, лог или diff, связывающий поведение с конкретным участком реализации;
4. доказательство после исправления, что положительный control сохранён, а отрицательный case закрыт.

### 2. Подтверждённый operational blocker

Это реальная преграда release/operation, но не обязательно дефект runtime/retrieval. Например, mismatch внешней Trusted Publisher identity способен остановить publish при полностью корректных wheel и MCP runtime.

### 3. Evidence gap

Claim пока нельзя сделать, потому что нужного измерения или публичного артефакта нет. Отсутствие доказательства **не является доказательством дефекта**.

### 4. Гипотеза

Правдоподобное объяснение наблюдаемого результата, которое ещё не изолировано ablation/replay. До такой проверки гипотеза не должна превращаться в root-cause claim или API change.

---

# Подтверждённые реальные дефекты

## D1. Recovery мог самостоятельно авторизовать edit workflow — исправлено

### Что было реально

До PR #131 MCP projection связывал достаточно похожий на `code_search` recovery с:

```text
disposition = search_local_source
edit_ready = true
```

Авторизация выводилась из самого recovery action. В результате три adversarial scope/fail-closed case получали `insufficient_evidence`, но одновременно модель-видимый edit authorization:

- `module_scope_rejects_project_policy_detail`;
- `project_scope_rejects_module_detail`;
- `project_policy_detail_fails_closed`.

До исправления gate проходил только **25/28** случаев.

### Почему это вредно

`edit_ready` — не декоративное поле. Это control-plane сигнал для coding-agent host/loop. Ложное `edit_ready=true` могло разрешить переход к patch workflow после ответа, который сам DocAtlas классифицировал как документально недостаточный или scope-invalid.

Это **не** доказательство remote code execution и не означает, что DocAtlas сам менял файлы. Реальный вред точнее:

```text
неподтверждённый / out-of-scope documentary result
        ↓
ложная host-visible edit authorization
        ↓
coding agent может начать unsupported edit workflow
```

Для продукта, позиционируемого как fail-closed evidence authority, это был stop-the-line agent-control defect.

### Как исправлено

PR #131 разделил два независимых решения:

1. можно ли безопасно передать задачу локальному source search;
2. может ли host продолжать explicit mutation workflow.

Strict local-source handoff требует все поля:

```text
tool                  = code_search
type                  = search_local_source
handled_by            = coding_agent
requires_confirmation = false
repeat_docs_context   = false
auto_execute          = false
```

Но даже корректный handoff больше не выдаёт edit authorization сам по себе. `edit_ready=true` разрешён только при host-owned explicit mutation intent и отсутствии blockers.

### Исправленный invariant

Неверная слишком широкая формулировка:

```text
insufficient_evidence ⇒ edit_ready = false
```

Она ломает legitimate workflow, где документация честно не доказывает implementation fact, но explicit coding task может безопасно продолжиться через обязательный локальный source search.

Корректная формула:

```text
edit_ready =
    explicit host-owned mutation intent
    AND strict safe local-source handoff
    AND NOT hard_stop
    AND NOT requires_confirmation
    AND NOT operational recovery precedence
```

При этом:

```text
documentation_supported = false
```

может сосуществовать с:

```text
investigation_allowed = true
source_search_status = required
edit_ready = true
```

Это не превращает documentary claim в supported и не разрешает пропустить code search. Оно означает только: explicit edit task может перейти к локальному исследованию исходников под контролем coding-agent host.

### Доказательство closure

Exact clean PR head: `6d92574468814a3190b306cdc141eead5249c6d4`.

- CI run [`32583477679`](https://github.com/Vanilla1999/DocAtlas/actions/runs/32583477679): `required-ci` success;
- Agent Developer target: **11/11**;
- adversarial v2: **28/28**, `violations=0`;
- Agent Developer adversarial mutation gate: **9/9 mutants killed**;
- recovery mutation gate: **6/6 mutants killed**;
- core tests green на Python 3.11, 3.12 и 3.13;
- legitimate source-search continuation integration test green.

**Вердикт:** дефект был реальным и вредным; сейчас закрыт.

## D2. Reviewed tree отличался от intended post-merge tree — исправлено

### Что было реально

Семейство temporary materializer workflows/scripts должно было после merge создать semantic release state. Поэтому существовало расхождение:

```text
reviewed PR tree ≠ intended final main tree
```

PR проверял transformation logic, а version/changelog/workflow/docs/tests могли измениться уже после review boundary.

### Почему это вредно

Это release-trust defect:

- reviewer не видит exact final semantic diff;
- PR CI и release source могут быть разными деревьями;
- audit trail усложняется;
- carrier получает слишком широкое право менять source, tests и release workflow;
- regression можно внести трансформацией после merge, минуя нормальное code review.

### Как исправлено

PR #131 непосредственно materialized semantic `1.3.1` в diff и удалил tracked one-shot materializers. Final tree больше не зависит от post-merge преобразования source/version/tests/workflow.

**Вердикт:** дефект был реальным и вредным; сейчас закрыт.

## D3. Source/release identity была split-brain — repository-side исправлено

До repair `main`, intended release number, changelog, scorecard и carrier plan не представляли одну reviewable identity. После PR #131:

- source version = `1.3.1`;
- changelog и release docs = `1.3.1`;
- release workflow example = `v1.3.1`;
- replacement environment = `release-current`;
- scorecard честно остаётся pre-public `INCOMPLETE`.

Это закрывает repository-side consistency defect, но **не закрывает public release**: tag, public bytes и public install evidence ещё отсутствуют.

**Вердикт:** repository defect закрыт; public-truth work остаётся pending.

## D4. В active docs оставалась устаревшая environment/status формулировка — исправляется этим MR

После merge #131 canonical publish workflow и release identity используют `release-current`, но roadmap всё ещё говорил `release`. Scorecard также говорил, что reviewed source candidate «being prepared», хотя он уже merged.

Это не runtime blocker, но реальная documentation-consistency ошибка. Она опасна тем, что оператор может зарегистрировать неправильный PyPI Trusted Publisher tuple и снова получить `invalid-publisher`.

Этот MR:

- приводит roadmap к `release-current`;
- фиксирует post-merge wording scorecard;
- добавляет regression assertions против возврата старого environment name.

**Вердикт:** реальная низко-/среднесерьёзная operational documentation defect; закрывается этим MR.

---

# Подтверждённый открытый operational blocker

## O1. PyPI Trusted Publisher identity ещё не доказана успешной публикацией

Исторический `v1.3.0` workflow дошёл до OIDC publication и получил `invalid-publisher` до upload. Это реальный release blocker, но не доказательство дефекта retrieval, package build или MCP runtime.

Repository contract теперь однозначно требует tuple:

```text
owner:       Vanilla1999
repository:  DocAtlas
workflow:    publish.yml
environment: release-current
```

Что нельзя доказать из repository:

- как фактически настроен publisher на PyPI прямо сейчас;
- существует ли точное совпадение всех claims;
- примет ли PyPI replacement OIDC identity.

Следовательно, root cause можно классифицировать только как **historical publisher-claims mismatch**. Конкретное неверное поле (`environment`, workflow filename, owner/repo или отсутствие publisher) остаётся неизвестным без external settings/evidence.

Closure наступит только после:

1. настройки exact tuple на PyPI;
2. immutable `v1.3.1` на exact reviewed `main` commit;
3. successful OIDC publish без long-lived token;
4. сохранённой provenance/attestation identity.

**Вердикт:** реальный и открытый operational blocker; не runtime bug.

---

# Реальные evidence gaps, которые нельзя называть подтверждёнными багами

## E1. Exact public `1.3.1` artifacts отсутствуют

Нет immutable `v1.3.1`, public wheel/sdist и тройного совпадения:

```text
gated SHA-256
= PyPI metadata SHA-256
= downloaded artifact SHA-256
```

Pre-public build/release gates сильны, но не заменяют public artifact truth.

**Класс:** evidence gap / P0 blocker, не code defect.

## E2. Exact public MCP behavior на трёх ОС не доказан

PR-level wheel/install smokes прошли, включая platform lanes, но P0 требует no-cache install **из публичного PyPI** после publication на Linux, macOS и Windows.

**Класс:** evidence gap / P0 blocker, не подтверждённая cross-platform ошибка.

## E3. Autonomous Agent Truth остаётся недоказанной

Текущая каноническая граница claims:

```text
oracle/deterministic: 11/11
historical autonomous live: 0/11
```

Из этого следует, что реальная модель пока не доказала способность автономно воспроизвести intended evidence trajectory. Но это не доказывает, что причиной является retrieval, schema, host context или model behavior.

**Класс:** подтверждённый outcome gap, root cause неизвестен.

## E4. Installed-MCP live-model harness отсутствует

Есть protocol-level stdio smoke и deterministic model/host tests, но нет одной packaged live trajectory, связывающей:

```text
wheel/commit/schema identity
→ provider/model/request
→ attempted tool calls
→ validation/recovery
→ result hashes
→ support decision
→ final coding outcome
```

**Класс:** measurement/evidence gap, не runtime defect.

## E5. First-divergence atlas для 11 frozen tasks отсутствует

Без P1.2 нельзя честно ответить, где происходит первая причинная divergence:

```text
model formatting
→ MCP schema
→ server validation
→ retrieval
→ support
→ recovery
```

**Класс:** causal-attribution gap.

## E6. Product Truth остаётся недоказанной

Исторический Task 23 — `INCONCLUSIVE`. Нет валидного причинного доказательства, что DocAtlas улучшает correct-patch outcome или снижает unsupported/wrong-version claims при приемлемой стоимости.

**Класс:** product evidence gap, не отрицательный product verdict.

## E7. Context7 parity не доказана

Наличие отдельных retrieval benchmarks и snapshots не закрывает full parity claim.

**Класс:** unproven claim, не defect.

---

# Гипотезы, которые пока нельзя выдавать за root causes

Для historical live 0/11 правдоподобны:

1. модель неверно форматирует tool call;
2. public MCP schema слишком сложна для первого прохода;
3. host не передаёт достаточный working path/scope context;
4. server validation корректно отклоняет вызов, но recovery трудно интерпретировать;
5. модель получает evidence, но неверно читает support/recovery state;
6. lifecycle continuation между calls недостаточно явна;
7. server-owned scope inference могла бы снизить call complexity;
8. opaque continuation token мог бы предотвратить потерю состояния.

Ни одна из этих причин сейчас не подтверждена как primary root cause. Поэтому до P1.1/P1.2 нельзя:

- расширять public API «по интуиции»;
- автоматически добавлять `working_path` как доказанное решение;
- приписывать все 0/11 schema complexity;
- ослаблять validation/fail-closed behavior ради pass rate;
- считать continuation token обязательной функцией.

Privacy/leak risk будущего live transcript recorder также пока является design risk, а не найденной утечкой production path. Его надо закрывать allowlist transcript schema и secret/path canaries при реализации P1.1.

---

# Текущее доказательное состояние после PR #131

| Область | Состояние | Доказательный смысл |
|---|---|---|
| Repository semantic `1.3.1` | `green` | Version/changelog/docs/workflow/tests согласованы в reviewed `main`. |
| Agent fail-closed authorization | `green` | 28/28 adversarial, mutation gates green; recovery не self-authorizes edits. |
| Review-tree hygiene | `green` | Semantic state находится в PR diff; one-shot materializers удалены. |
| Branch protection | `accepted_risk` | Remote `main` не protected; это не называется green. |
| Trusted Publisher | `pending` | External PyPI tuple ещё не подтверждён successful OIDC publish. |
| Immutable `v1.3.1` | `pending` | Tag пока отсутствует. |
| Exact public artifact bytes | `pending` | Public wheel/sdist SHA evidence отсутствует. |
| Exact public MCP install | `pending` | Public no-cache package smoke отсутствует. |
| Public Linux/macOS/Windows | `pending` | Pre-public smoke не заменяет post-publish evidence. |
| Autonomous Agent Truth | `unproven` | 0/11 historical live outcome, без first-divergence attribution. |
| Product Truth | `unproven` | Correct-task benefit не доказан. |
| Context7 parity | `unproven` | Comparative claim не закрыт. |
| Maturity | **Beta** | Stable claim запрещён текущим evidence. |

---

# Правильная дальнейшая последовательность

```text
1. merge этого analysis/docs consistency MR после exact-head CI
2. зафиксировать exact final reviewed main SHA
3. настроить PyPI Trusted Publisher:
   Vanilla1999 / DocAtlas / publish.yml / release-current
4. создать immutable v1.3.1 на exact reviewed main SHA
5. dispatch canonical publish.yml
6. OIDC upload + provenance
7. скачать wheel/sdist и сравнить exact SHA-256
8. no-cache install exact public 1.3.1
9. Linux/macOS/Windows public MCP smoke
10. записать immutable release evidence
11. перевести pending rows P0.6 в green
12. сохранить branch protection как accepted_risk и maturity как Beta
13. начать P1.1 installed-MCP live-model harness
14. построить P1.2 first-divergence atlas
```

До шага 11 P0 остаётся открыт. До P1.1/P1.2 нельзя утверждать причины 0/11. До валидного P2 нельзя утверждать coding-outcome improvement или Stable maturity.

## Команды воспроизведения текущих deterministic gates

```bash
python scripts/run_agent_developer_gate.py
python scripts/run_agent_developer_adversarial_gate.py
python scripts/run_agent_developer_adversarial_mutation_gate.py
python scripts/run_recovery_contract_gate.py
python scripts/run_recovery_mutation_gate.py
pytest tests/ -m "not advanced and not live and not live_network"
pytest tests/ -m advanced
python -m build
python scripts/release_gate.py --manifest dist/release-manifest.json
```

## Итоговый вердикт

Исходный pre-repair анализ был прав в главном: на 22 августа 2026 года DocAtlas нельзя считать доказанно закрытым по Public Truth, Agent Truth или Product Truth, а maturity должна оставаться Beta.

Но после повторной проверки требуются две важные коррекции:

1. PR-specific утверждения о #130/#131 и materialized state должны быть обновлены: repair уже merged, 1.3.1 semantic state reviewable, required CI/release green, materializers удалены.
2. Blanket invariant `insufficient_evidence ⇒ edit_ready=false` неверен. Правильная граница отделяет documentary support от host-owned permission продолжить explicit coding workflow через обязательный safe local source search.

Реальные закрытые дефекты не должны оставаться в списке «открытых проблем». Реальные evidence gaps не должны называться багами. Гипотезы не должны называться root causes до causal replay. Именно такое разделение сохраняет доказательность DocAtlas и предотвращает как преждевременные claims, так и ненужное расширение продукта.