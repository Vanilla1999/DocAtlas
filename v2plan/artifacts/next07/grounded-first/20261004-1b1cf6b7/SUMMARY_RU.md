# Grounded-first: BLOCKED, native recovery не проверена

## Отчёт по шаблону плана

- **Branch / baseline HEAD+patch / candidate HEAD+patch:**
  `next07-feasibility-audit`; baseline `1b1cf6b7` + `baseline.patch` (hash в
  `provenance.json`). Candidate — research-only additions над этим HEAD;
  `candidate-code-manifest.json` и commit с этим отчётом. Runtime patch отсутствует.
- **Последний выполненный шаг:** попытка проверки I.3; переходы не приняты.
- **G actual package run:** DONE. Настоящий npm CLI 3.2.1, не SQL reconstruction
  и не новый MCP transport. Два отдельных stores, три исходных файла в каждом.
- **C final packet:** NOT_RUN.
- **Часть I verdict:** BLOCKED — после разрешённого logging retry не получен
  корректный positive на требуемой DTO-boundary.
- **Часть II:** NOT_RUN.
- **LeaseClient P1/P2/P3:** в G:
  `# LeaseClient\nThe default timeout is 17 seconds.` и
  `# LeaseClient\nAn expired operation raises \`LeaseExpired\`.`;
  во втором store — `29 seconds` и `WaitExpired` с тем же owner/expired condition.
  Это нормализованный G text, не точные original bytes. Оригиналы сохранены
  отдельно. N sources доставляют overview, не оба факта. P3 NOT_RUN.
- **Recovered / lost / retained partial fact IDs:** recovery в C NOT_RUN;
  fresh retention и partial retention NOT_RUN. Из versioned ledger выделены
  49 уникальных historical baseline-supported pairs; original archive hash
  совпал с versioned provenance. Extraction не равна проверке сохранения.
- **Hard guard / budget / span violations:** guard acceptance NOT_MEASURED;
  I.3 positives не дошли до неё. Runtime unchanged (hashes всех 388 modules
  проверены; фактическое число см. `runtime-unchanged.json`). N whole-DTO 313/314
  tokens, source cap соблюдён existing capture assertions. C budget NOT_RUN.
  G размер измерен отдельно; parity с бюджетом 800/3 не заявляется.
- **Policy conflicts и старые failing nodes:** четыре exact collected node IDs
  заранее записаны в policy allowlist. Старые expectations/frozen labels не
  редактировались. Old-policy tests/full suite не запускались после остановки;
  прежние failures 06 остаются открытыми. Новые v2plan failures — harness
  evidence, не новые failing nodes production suite.
- **Unseen / reader evaluation:** NOT_RUN.
- **Изменённая и удалённая ответственность:** initial retrieval адаптирован в
  isolated helper; read owner предложен отдельно. В production ни одна
  ответственность не удалена/не переключена: wiring не выполнен. Нет fallback.
- **Changed files / exact commands / artifacts:** три research runners/helper,
  отдельный research test module, pure ports + MIT/LICENSE/manifest, журнал плана,
  этот каталог evidence. Команды и outputs — ниже и в raw command JSON.
- **Not_run и причина:** I.4–I.6, paired replay, native C, retention, gates,
  full suite, remaining mandatory controls, II — нет корректного DONE I.3.
- **Один следующий шаг:** отдельное решение о новой попытке с authenticated
  index→read DTO conversion и полной предварительной заморозкой controls.
  Эта попытка закончена; rollout не разрешён.

## Почему BLOCKED, не REJECTED алгоритма

1. Первый I.3 run: 8 PASS / 16 FAIL, invalid evidence logger (`__dict__` у
   dataclass со slots). Сохранены `i3-tests.json`, `i3-tests.xml`.
2. Единственный retry изменил только logger на `dataclasses.asdict`, не candidate,
   corpus или assertions. Результат 9 PASS / 15 FAIL: `i3-retry/run.json`, XML,
   append-only control records.
3. Все обязательные working positives получают `missing_project_request`:
   observer передал `source_class=project_file` из index metadata. Existing
   source-window guard принимает `project_doc` на prepared read boundary.
   Этот отказ нельзя обходить или выдавать за semantic-policy failure.
4. Двенадцать damage controls не дошли до mutation, поскольку positive assertion
   упал. «PASS» restriction control — пустой отказ, не доказательство guard.
5. После этого повторов/правок алгоритма нет. Приёмка недоступна в данном harness.

## Границы и отклонения исполнения

- I.0 сохранил provenance, protocol/plan predicates и policy allowlist, но
  конкретные дополнительные control fixtures были записаны позже, перед I.3 run,
  не до реализации. Полный DONE I.0 не подтверждён.
- I.2 успешно проверяет source bytes и FTS parity на fixture inventory. Actual
  current-snapshot/source admission inventory integration ещё не реализована;
  это isolated diagnostics, не полный DONE I.2 и не recovery.
- I.3 запускался над рабочим checkout в отдельном pytest process; runtime bytes
  равны captured baseline. N запускался в archived isolated baseline checkout.
- Первая postflight introspection ошибочно разрешила symlink venv Python в base
  interpreter, потеряв dependencies. Исходный output сохранён. Исправленная
  introspection использовала protocol project Python и подтвердила origin в
  isolated checkout. Это не повтор benchmark и не дополнительный I.3 retry.

## Команды

```sh
git fetch origin next07-feasibility-audit
git merge --ff-only origin/next07-feasibility-audit
.venv/bin/python -m v2plan.next07_grounded_run --out v2plan/artifacts/next07/grounded-first/20261004-1b1cf6b7
npm install --prefix /tmp/opencode/next07-grounded-321-20261004 --no-audit --no-fund @arabold/docs-mcp-server@3.2.1
.venv/bin/python -m v2plan.next07_grounded_reference --out v2plan/artifacts/next07/grounded-first/20261004-1b1cf6b7 --install /tmp/opencode/next07-grounded-321-20261004
```

Точные packaged help/scrape/search/registry/pack/source-ref commands с exits и
stdout/stderr — `reference/`. N invocation — `reference/{17,29}/native-command.json`.
I.2 pytest command — `i2-tests.json`. I.3 commands/environments — `i3-tests.json`,
`i3-retry/run.json`; logger output path — соответствующий controls directory.
Same-index-row SQL parity inputs/results — `i2-result.json`. Все checks —
development evidence, не held-out.

## Долговременное восстановление baseline

Полный tracked baseline находится в Git commit `1b1cf6b7`; dirty binary patch и
untracked executable inputs committed отдельно. Нет необходимости коммитить
дубликат Git tree размером 40 MB. `baseline-reconstruction.json` описывает
восстановление; временный tar — только cache, не единственная evidence база.
Original historical results/protocol упакованы в `historical-results.tar.gz`.
Historical outputs чужой dirty работы не изменены и не включены как рабочие
файлы в этот commit.
