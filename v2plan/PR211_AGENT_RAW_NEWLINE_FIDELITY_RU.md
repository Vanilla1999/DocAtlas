# PR #211: raw newline fidelity в Agent oracle

## Наблюдаемое состояние

База: опубликованный HEAD `a9fba17d13ea16ed0dbbb4692ab6029ae6da6a07`
(slice 136), tree `7f663bac25aa6e79c48a07301d2e94e5e7352c42`.

Независимо прочитан [P1.6 job 114139516306](https://github.com/Vanilla1999/DocAtlas/actions/runs/38026891749/job/114139516306).
Точный decoded log: 84279 UTF-8 bytes,
SHA-256 `4b83e9c22e1323105008f8adfd2706faa83bc063229c6fb0a87bbc4efeec95d0`.

- Current P1.6 public-delivery gate: 6/6 PASS, full facts 1/1, errors 0.
- Его отдельные oracle controls: 6/6 PASS.
- Последующий Agent adversarial gate: 24/28; V1 target contract не закрыт.
- Named module behavior/requirements возвращают `status=ok`, но получают
  `source_fidelity: quote or coordinates changed`. Такой же mismatch виден у
  explicit catalog module, tiny-budget counterparts и project policy detail.
- Cross-module comparison остаётся `insufficient_evidence` с отсутствующим
  required fact/source. Это отдельный production gap; его не исправляет данный
  evaluator slice.

Короткий log содержит generic mismatches, но не сами source rows с snippet и
координатами. Поэтому **не утверждается**, что конкретные observed coordinates
уже доказаны правильными, что все эти failures имеют единственную причину или
что правка уже дала новый PASS. Следующий normal CI должен это проверить.
Standalone P1.6 artifact содержит current-delivery report, а не полный Agent
adversarial baseline; дополнительных runtime/actions для его получения не было.

## Доказанный дефект текущего oracle

`scripts/run_agent_developer_gate.py`, base `bf28d7c3`, функция
`_source_fidelity_mismatches` обещает сравнивать цитату с исходными fixture bytes.
Однако она использует `read_text(encoding="utf-8")`, затем
`"\n".join(original.splitlines()[start - 1:end])`.

Первое действие допускает universal-newline преобразование CRLF в LF.
Второе удаляет терминатор последней заявленной строки. Поэтому точная цитата,
содержащая его, отвергается независимо от того, правильны ли её границы.
Для CRLF теряются также исходные внутренние terminators.

После raw-window slice 133 literal context намеренно сохраняет полный raw
window, включая LF/CRLF. Это обнаружило несовместимый evaluator contract.
Самостоятельный контрпример не зависит от gold, реального retrieval ranking
или вопроса конкретного Agent case.

Фактические authored files также сохранены и прочитаны без изменения:

| Fixture path под `eval/agent_developer_v1/projects/explicit_manifest_monorepo` | Blob | Bytes | SHA-256 |
| --- | --- | ---: | --- |
| `packages/orders/README.md` | `56274f1c600ad3575c2665fac9d4be6db0627b04` | 434 | `09169078cabb337d8b3220008fa22fd550781d6b42ce5a36e23859e97f93ee5e` |
| `ARCHITECTURE.md` | `7cec4c32a3760b27482b14f6d7d5f3e3d53f96aa` | 485 | `ccad600f6c90895fa820d0516c37382a7ed7b2cbed5f99137bdefa2e40d05ba7` |

Оба файла оканчиваются LF. Это source evidence об authored bytes, а не
подмена отсутствующего actual public snapshot этими файлами.

## Узкое исправление и сохранённые ограничения

Oracle читает `read_bytes().decode("utf-8")`, формирует
`splitlines(keepends=True)` и сравнивает snippet с
`"".join(lines[start - 1:end])`. Для валидного UTF-8 такое точное строковое
сравнение сохраняет исходные байты, включая terminators.

Все прежние требования сохранены: source должен быть текущим файлом внутри
fixture, snippet — непустой строкой, обе координаты — точными `int`, диапазон
1-based и внутри числа реальных строк. Цитата обязана содержаться **в этом
диапазоне**, а не где-либо в документе. Project identity, candidate hash shape,
evidence ID и version binding проверяются как раньше.

Существующий `content_sha256` остаётся hash bound candidate, а не объявляется
file hash. Никакого `strip`, изменения цитаты, расширения диапазона, допуска
нескольких несовместимых форматов или ослабления source/authority guard нет.
Сами failure labels и классификация результата не изменены.

Production, public schema, lookup/original questions, gold facts, thresholds,
membership, scope, stored documents и mutation runner не редактируются.

## Контроль без новых pytest functions

Расширен один existing self-test `source_quote_fidelity` в
`run_agent_developer_adversarial_gate.py`. Все восемь имён его checks и старые
positive/forged-quote проверки сохранены.

Два маленьких независимых файла записываются как exact bytes: header, пустая
строка, `Raw λ source fact.` и финальный terminator. У одного все окончания LF,
у другого CRLF. Для каждого проверяются:

1. Exact полная цитата третьей строки вместе с её терминатором проходит.
2. Та же цитата с заявленным диапазоном 1:1 отвергается.
3. Диапазон до несуществующей четвёртой строки отвергается: завершающий newline
   не создаёт фиктивную EOF-строку.
4. LF↔CRLF подмена в snippet отвергается.

Это **2 positive и 6 negative oracle evaluations**, два дополнительных
temporary fixture files, восемь вызовов существующей проверки. Нет новых
business/native public reads, retrieval calls, tests/nodes или evaluator
control names. Unicode и окончания записаны независимо от фактического DTO.

Existing `agent_source_fidelity` mutant и его `source_quote_fidelity` guard
не изменены: unique anchor count остаётся 1. На новом oracle source before
SHA-256 `bc14b4436ceb6b85e24c2a5b945339d99a35a4ed9fec50c7e249c4c6ec7ad9a1`,
after прежнего fault —
`1a39a3083c8f297387960e29086b75696cdde0d2f954d9aca51bb2c39962eaf1`.
Сохранены все девять Agent mutants и требование здоровых evaluator/full
public baselines до выдачи mutation credit. Нового kill здесь не заявлено.

## Exact manifest и проверка

Все bases повторно прочитаны на HEAD136. Modes независимо подтверждены через
root tree и scripts subtree `ca5dd8dc0b0a2706ec53f3e333bb595374fbce2b`.

| Path | Mode | Base blob | Proposed blob |
| --- | --- | --- | --- |
| `scripts/run_agent_developer_gate.py` | 100644 | `bf28d7c3cb9700a7822a3fcb14d1b5e4046c6bb2` | `f815ae53c6b3b6763a5225af478cc5ec34bdca13` |
| `scripts/run_agent_developer_adversarial_gate.py` | 100644 | `9afd8eb0e5690648fc8f5a89a9536579dd59cec4` | `5b344c4828f2494d91b96ab94629d89952c7c35e` |
| `v2plan/PR211_AGENT_RAW_NEWLINE_FIDELITY_RU.md` | 100644 | new | this note |

Оба code blobs прошли exact GitHub readback; inverse двух hunks в каждом
возвращает соответствующий base побайтно. Oracle 984 строки, adversarial
runner 424; новых imports или dependency нет. Refs и commits агент не менял.

Нужны фактические восемь evaluator controls и повторение исходных public
trajectories на конечном tree. Cross-module gap нельзя засчитать исправленным
по этому oracle diff; полномочия на answer/edit и source fidelity остаются
обязательными. Локальное исполнение, pytest, imports и subprocess не запускались.
