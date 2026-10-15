# PR #211: сохранить project-контекст в смешанной выдаче

## Наблюдаемый дефект

В P1.5 на `f7b9253c8e477babf276ae8dd2cb18905451cd15`, [job 114082883391](https://github.com/Vanilla1999/DocAtlas/actions/runs/38008532078/job/114082883391), исходный mixed-вопрос `Explain ProjectRetryRule and TenacityRetryingContract.` получил две полезные lanes внутри одного вызова. Полное 37-символьное project-окно из `ARCHITECTURE.md` было допущено как literal context, project delivery разрешён. Итоговая MCP-проекция сохранила только 65-символьный library источник. Наблюдение и hashes сохранены в `v2plan/pr211-execution/RUNTIME_EVIDENCE_f7b9253c.json`.

Source audit связал потерю с выбором одной library selection и её requirements в общем answer projector. Наличие project-окна во внутреннем context pack само по себе не позволяет пропустить scope/consent/source guards. Для исправления нужен независимый текущий контракт project lane.

## Producer и consumer

Предыдущий отдельный commit `3064eb635058af44609ee35181c39154da7d3224` добавил внутренние `ProjectDocsResult.request_scope` и `UnifiedDocsContextResult.project_context_contract`. Поля добавлены в конец dataclasses; они описывают уже выполненное чтение и не инициируют новое. Отсутствующее доказательство остаётся отсутствующим. Подробности: `v2plan/PR211_MIXED_PROJECT_SCOPE_PRODUCER_RU.md`.

Новый `mixed_context_projection.py` композиционно добавляет только независимо допущенные project-цитаты к уже валидному library packet. Его вызов находится внутри `model_visible_projection.project_docs_answer`, после существующих глобальных и library guards. Поэтому существующий observer настоящего authoritative projector видит именно итоговую mixed-проекцию. MCP boundary непосредственно перед этим вызовом заново записывает текущие request arguments, не доверяя одноимённому полю из retrieval.

Проверяются:

- исходный вопрос в request, read receipt и query plan; versioned schema и типы полей;
- текущие root, project identity, scope, module и module path, полный requested/read scope;
- глобальный и project delivery, допустимые статусы, явный false consent и пустой inner conflict list;
- scope каждого project item, все обязательные technical requirements для path/identity/module/version/snapshot;
- source/member/raw-window guards существующего `project_docs_context`;
- исходный library snapshot, полный добавляемый snippet и исходный raw snapshot;
- уникальность evidence IDs, отсутствие противоречивых collision и валидность итогового packet.

Статус nested reader `no_results` допустим только вместе с сохранёнными context windows и отдельно явным разрешением project и unified delivery. Он не становится самостоятельным доказательством полезного контекста или отсутствия конфликта.

## Граница доверия и поведения

Detached project projection получает явный whitelist уже имеющихся полей, без continuation root. Новых retrieval, SQL, файловых чтений, resolving или mutation actions в consumer нет. При malformed/current-scope mismatch или невалидном project snapshot возвращается исходная безопасная library-проекция без частично добавленных sources.

Public packet остаётся retrieval-only. Добавление точных цитат не повышает answer/edit authority, original-question coverage или answer-unit proof. Полный текущий набор project requirements передаётся в существующий projector; ограничения не удаляются ради выдачи.

## Известное ограничение root aliases

Для этой чистой композиции текущий request root должен уже быть каноническим абсолютным путём, совпадающим с independently recorded reader root. Относительные пути, `~`, symlink aliases и пути с `..` требуют отдельного доверенного разрешения, которого нет в текущих MCP arguments.

Это **ограничение новой mixed augmentation**, а не новый запрет входных аргументов public API. Для таких aliases сохраняется прежний library packet. Работоспособность полного mixed-контекста для aliases здесь не заявляется; `Path.resolve()`, `expanduser()` или файловый обход ради подстановки доказательства не добавляются.

## Manifest и review

| Path | Mode | Base | Proposed |
|---|---|---|---|
| `docmancer/docs/application/mixed_context_projection.py` | 100644 | NEW | `dcdf502c9d9b2a3788c1bfc41d377ad3cf1ade63` |
| `docmancer/docs/application/model_visible_projection.py` | 100644 | `dfde451b4af3474bcc3225bcc74e2aa0f62c1772` | `3c377e64bf104b598bb68a0d062625c4fc83f5ef` |
| `docmancer/docs/interfaces/mcp/context_tools.py` | 100644 | `7a3cb4f113603c27accf3feb44f27f546ff595fd` | `c6e2bda4208a43b7764fe484928fd7ce55ed6183` |
| `v2plan/PR211_MIXED_PROJECT_CONTEXT_PROJECTION_RU.md` | 100644 | NEW | эта запись |

Root и independent readonly reviewer: **static APPROVE** финального helper и двух hooks. В review исправлены два реальных пробела: self-consistent чужой root не должен подтверждать текущий request; resolved module не должен появляться без текущего module selector. Эти ограничения проверяются до рассмотрения candidates. У двух существующих файлов по четыре добавленные строки; их прежний код не переписывается. Create/fetch roundtrip helper и hooks точный.

## Acceptance

Runtime нового consumer ещё не выполнен. Независимый finite project/library contract и направленные mutations готовятся отдельным test slice перед совместной публикацией. Одного static review недостаточно для удаления старых tests или утверждения PASS. Последующий CI должен отдельно подтвердить настоящий same-call public result, пять mutation kills и улучшение фактического P1.5. Installed MCP и реальные client проверки остаются отдельными gates.
