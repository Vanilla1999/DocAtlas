# M2: причинное сравнение httpx-07

## Метод

Checkpoint `5a732198` и current запущены через один и тот же native fixture
`capture_reference_case` на исходном вопросе и corpus из exposed protocol.
Wrapper вокруг `reference_query_tagging.qualify_evidence` только записывает
аргументы/результат, возвращая native verdict без изменений.
`git diff 5a732198` для evaluator, corpus runtime, этих fixtures, regression,
`evidence_qualification.py` и `reference_query_tagging.py` пуст.
Это exposed diagnostic, не независимая multilingual acceptance.

## Наблюдения

Checkpoint доставляет два sources, current — один. Current контекст не пуст:
виден раздел fine tuning, но не обязательный абзац:

> HTTPX is careful to enforce timeouts everywhere by default.
> The default behavior is to raise a `TimeoutException` after 5 seconds of
> network inactivity.

В checkpoint этот абзац достигает tagging через `query-hint-2` (default),
`query-need-1`, `query-need-2` и `query-part-1`. Их native verdicts соответственно:
visible_fields, verified_local_demand, visible_fields, visible_fields.
Original query на том же абзаце отвергается и в checkpoint:
body matches httpx/default/timeout, ratio 3/14=0.2143.

В current абзаца нет среди вызовов tagging: loss начинается до qualification
этого абзаца. Видимые current candidates для original также недостаточны,
а literal anchor направляет в другие окна того же документа.
Это две зависимости: discovery после удаления generated probes и downstream
qualification полного вопроса. Какой внутренний retrieval cap/ranking шаг
теряет абзац, этим wrapper ещё не установлено.

Предыдущий `m2_httpx07_diagnostic.json` отражает более ранний checkpoint;
утверждение «current context_pack пуст» больше нельзя использовать как
актуальную локализацию. Отказ current evaluator остаётся реальным.

## Контроли и поисковые эксперименты

`m2_causal_review_controls.log`: **115 passed / 1 failed**. Единственное
падение — исходный httpx-07; assertion и исходный запрос не изменены.
Проходят explicit planner, CLI boundary, read/change permission controls,
source metadata/lifecycle, catalog budget и соседний typer-01.

Отдельные diagnostic requests с сохранённым original question и explicit
lookup `HTTPX default timeout exception`, `What is HTTPX default timeout
behavior` или `default` не восстановили required claim: needs_review.
Эти варианты не добавлены в regression fixture. В первом варианте проверены
answer_supported=False, edit_ready=False; private claim тоже needs_review.
Поэтому «просто добавить explicit lookup» не является доказанным исправлением.

## Граница решения

Возврат generated need/part/hint paths нарушит explicit-only M2. Снижение ratio
не восстановит отсутствующий candidate и ослабит остальные controls.
Без causal retrieval/cap experiment нельзя утверждать, что это plumbing fix.
Следующий шаг требует либо ограниченного cross-stage discovery/delivery slice
с сохранением guards, либо согласованной отдельной boundary acceptance M2 с
открытой end-to-end регрессией. Автоматически M2 не закрывается.
