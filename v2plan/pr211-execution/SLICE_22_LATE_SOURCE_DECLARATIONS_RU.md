# Slice 22: позднее объявление не теряется после восьми ранних references

Реальный positive из Task 33C на `118e5d1` не находил PermissionService,
хотя source boundary явно разрешал его файл. Первые восемь case-insensitive
упоминаний заполняли per-term pool до чтения позднего объявления; существующая
итоговая declaration priority уже не могла вернуть отброшенный кандидат.
[Failure job](https://github.com/Vanilla1999/DocAtlas/actions/runs/37968004995/job/113947140389).

В `build_project_source_evidence` сохраняются восемь лучших body candidates
на term по прежнему порядку declaration/path/line; каждый более поздний кандидат
может заменить худший. Для итогового порядка используется тот же ranking key.
Exact-path seeds, конечные code-file grants, generated-file opt-in, file/read/work
bounds и итоговый selection policy сохранены. Source enumeration не расширяется.

Изменён один existing test `test_named_gate_source_evidence_exposes_declaration_metadata`:
baseline declaration → 8/16 ранних uses. Объявление, snippet и symbol неизменны,
координата сдвигается точно на prefix. No-grant делает ноль чтений, unlisted файл
с таким же символом не читается. Все 29 имён тестов сохранены.
Это проверка реального дефекта; input/work token budget не является отменённым
потолком стоимости model-visible DTO.

Автор agent_fixtures_impl; root independent review: APPROVE. Полная string
реконструкция подтверждает, что вне одной production function и одного existing
test bytes неизменны. Новые blobs: source
`f1a2e08eaaa2f3a66f655daa27ab13f05d0471bb`, test
`adf763482eabc04484285e54cf462bc00ce6fa2b`. Source имеет 915 строк.
Local AST/runtime **NOT RUN** после exec outage; ordinary CI проверит positive
на реальной fixture и отсутствие регрессий.
