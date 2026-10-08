# PR211: разбиение fidelity test без смены cases или guards

Дата: 2026-10-08. Base `4320a6841cb5a04b3c817c4f61595987c11d8f7c`.

CI обнаружил регрессию нового test-only slice: module-size gate допускает 1000
строк, а `tests/docs/test_model_visible_projection.py` вырос до 1039. Фактический
main job 113490384156 и P2 federated job 113490382853 остановились на этом gate;
federated candidate verifier и его 13 mutation self-tests перед ним прошли.

Тело одного параметрического fidelity test целиком перенесено в существующий
`tests/docs/_shared_test_model_visible_projection.py`. Исходная test function
остаётся на прежнем пути, с прежним именем, signature и четырьмя budget parameters;
она вызывает helper с тем же budget. Helper начинается с `_assert_`, поэтому
не создаёт pytest test node. Модуль уже импортирует shared declarations через
существующий globals update; новый import path или общий framework не вводится.

Все payload values, вызовы projector/estimator/validator, full-DTO assertions,
bool identity guards и восемь invalid controls перенесены AST-exact. Используемые
deepcopy и три production functions уже импортировались из того же shared module.
Остальные test declarations, старое содержимое helper, параметры и manifests
сохранены; никакие assertions, nodes, skips или thresholds не удалены.

Root выполнил AST/compile comparison и статическое повторение существующего
module-size scan обычной stdlib без imports/исполнения repository code. Oversized
modules отсутствуют; diff check чист. Сам gate, CI commands и runtime product
code не изменены. Независимый review и общий CI нового HEAD следуют отдельно.

Это исправление моей новой статической регрессии, не waiver gate и не заявление
о прохождении ещё выполняющегося core CI на 4320a68.
