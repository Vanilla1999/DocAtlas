# PR #211: независимый review семи v4 caller migrations

Дата: 2026-10-08. Reviewer — координатор; реализацию выполнил отдельный агент.

## Verdict

**APPROVE** для ограниченного test-only slice из четырёх modules,
перечисленных в `PR211_TASK_CALLER_MIGRATION_REVIEW_RU.md`. Это статический review,
не результат исполнения семи tests и не merge/release approval.

Проверены exact diff от b68759e, producer build_action_packet, flat projector,
оба metadata consumers, Codex JSONL normalization и broker
`_deliver_with_worker`. Изменения соответствуют уже существующему v4 contract.

- Metadata negatives теперь предваряются принимаемым валидным flat v4 control.
  Wrong objective, malformed/error result, legacy wrapper и edit grant остаются
  самостоятельными отказами. В Codex explicit format и один logical call
  проверяются отдельно от корректности самого payload.
- Builder/projector используют реальные validators, непустой полный source,
  SHA-256 и coordinates. AGENTS.md/canonical labels не дают instruction authority.
- Objective проверяется host snapshot против envelope **до worker call**;
  candidate.calls==0 подтверждает правильную границу. Forged старый scaffold
  отдельно отвергается validator. Invented и mutated host evidence, capability,
  usage, timeout и consumed-attempt guards не удалены.
- Exploratory positive использует конкретный host-selected target source.
  Предварительный negative сохраняет исходный suspected_modules и доказывает,
  что documentary mention не заменяет target assignment. Paths/text/hash/spans,
  fingerprints и отсутствие causal/client verification claims сохраняются.
- Persisted handoff проверяет реальную projection/snapshot пару, полный текст и
  отсутствие authority. Failure projection не оставляет принятых artifacts.
  1500-token и envelope budgets сохранены; representation cap не возвращается.

Все 53 test interfaces (имена, аргументы, decorators) независимо сравнены с
21fe472d и совпадают. Shared _packet используется только прежними callers;
никакие посторонние test functions/classes не переписаны. Source/evaluator,
gold, thresholds, markers и diagnostic inventory не менялись.

Два явно выделенных конфликта actionability/frozen semantic density остаются
неизменными. Их normative/edit-ready expectations и 2000 ceiling не разрешены
этим review. One-call retrieval-to-edit boundary также не менялась.

## Exact reviewed SHA-256

| Test module | SHA-256 |
|---|---|
| test_github_models_adapter.py | `7aab4d9dbd95c75a38b3803009688cb49bca1952bf3178d0312ae51aaccb77bc` |
| test_runner_adapter.py | `fd20e366432543f3d6023dfc4c965f5ffbd8e0575094dc285945d11cb8876140` |
| test_task33_codex_exploratory.py | `2aaf64225e3d87391b6f668d0b85b22c33f5a5fad28688359661d5b67ec2e39d` |
| test_task33_isolated_delivery.py | `e084642ecc46a88f7a51804d82eafe8a916a7bb141e3b2c5247db6318d041702` |

AST/roster/source review выполнен без repository runtime imports. Actual pytest,
builder/projector execution и persisted handoff должны быть подтверждены общим
CI на конечном SHA; hashes и статический review не подменяют эти результаты.
