# PR #211 — wiring текущей closure в P1-stack

## Исходный caller и обнаруженная причина

Проверен `.github/workflows/p1-stack-exact-validation.yml`,
blob d1b407769889516d59db30843f6aef56dc1b8826 на public
a348cafb4807a5b4af852e0029cf6b98ff7a3f91 и work 14776d3.
Оба содержат одинаковый caller.

Job advanced сначала запускал production-path shell block, затем P1-loop без
output/report/gate аргументов. `set -e` останавливал loop на первом FAIL.
Для новой closure вызов без настоящего outcome receipt корректно даёт FAIL.

В loop также перечислялись четыре отсутствующих файла:
run_agent_developer_first_divergence_gate.py,
first_divergence_contract_self_test.py,
run_agent_contract_v2_ablation_gate.py,
agent_contract_v2_ablation_self_test.py.
Проверены точные paths и полный Git tree: эти файлы отсутствуют, а условие
`if -f` молча пропускало их. Существующие реальные guards —
build_agent_developer_first_divergence.py --check и
build_agent_contract_v2_ablation.py --check. Именно их уже использует
отдельный current-closure workflow.

## Изменение

Изменяется только advanced job. Все прежние production команды сохраняются
в прежнем порядке: advanced pytest, hermetic quality, recovery и mutation,
Legacy report/lineage, V2 quality, question surface, Agent Developer,
adversarial, critical mutation, adversarial mutation.

Adversarial и adversarial mutation выделены в самостоятельные steps для
получения настоящих `steps.*.outcome`. P1-loop заменён явными шагами:

| Receipt key | Реально исполняемый gate |
|---|---|
| dependencies | существующая установка .[dev] |
| first_divergence | build_agent_developer_first_divergence.py --check |
| contract_ablation | build_agent_contract_v2_ablation.py --check |
| p14_quality / p14_oracle | current P1.4 runner / исходные oracle controls |
| p15_quality / p15_oracle | current P1.5 runner / исходные oracle controls |
| p16_quality / p16_oracle | current P1.6 runner / исходные oracle controls |
| adversarial | исходный Agent Developer adversarial gate |
| adversarial_mutation | исходный adversarial mutation gate |
| syntax | прежние temp-workflow, compileall, module-size и diff guards |

P1.4/P1.5/P1.6 получают явные temporary output paths; oracle controls получают
ровно соответствующий report. Closure runner и её четыре controls получают
те же три paths и один receipt с реальными outcomes, GitHub SHA, run ID и
attempt. Syntax выполняется до closure, чтобы его outcome был проверяемым
входом. Ни один guard не помечен continue-on-error.

## Сохранение ранних failures

Обычная последовательность gates сохраняет default success condition и
прежний short-circuit: первая ошибка остаётся failure, зависимые последующие
шаги получают настоящий skipped. Только capture receipt, сохранение closure
и artifact выполняются после ранней ошибки. Skipped не преобразуется в success:
current closure строго требует все 12 successful outcomes.

При недостающих current reports closure сохраняет честный FAIL, self-controls
возвращают явный input-proof FAIL. Failed production block либо critical
mutation также блокируют job и конечный p1-stack-exact aggregator. Их нельзя
скрыть успешной загрузкой artifact.

Отсутствующие старые filenames больше не дают условный пропуск: существующие
P1.2/P1.3 builders вызываются напрямую в read-only --check режиме. Их 7+6
существующих pytest controls остаются в core suite; дополнительных тестов
или повторного запуска этих controls в advanced не добавлено.

Core, platform, build, wheel, sdist и конечный aggregator сохранены побайтно.
Historical reports, protocol inputs, questions, facts, scorers, quality floors,
production source и self-test rosters этим slice не меняются.

## Проверка

Проведены static source review и текстовая сверка: все 12 receipt keys имеют
соответствующие step IDs; все прежние production команды и repository guards
сохранены; существующие три runner output paths совпадают с oracle и closure
inputs. Изменён только advanced block.

Нового CI выполнения этого wiring ещё не было. Нужен independent review и
фактический P1-stack run после публикации вместе с reviewed current closure.
