# PR211: причина остановки guard fixtures до projector

Дата: 2026-10-08. Base `03583656617336a746e9192249467017d6131f29`.
Автор: root. Это diagnostic-only slice, не исправление retrieval и не PASS claim.

Во всех трёх actual core JUnit на `4320a68` сохраняются 24 setup ERROR в
`test_context_completion_guards.py` и 23 в `test_query_block_guards.py`.
Fixture проходит `index_project`, затем индексирует пустой список projector
stages. Traceback показывает IndexError, но не возвращённый публичным вызовом
payload. Поэтому конкретный upstream reason пока не установлен. Возможность
раннего operational block/error или другого projection route — гипотеза по
source flow, не установленный runtime диагноз.

Добавлена одна setup assertion в каждую из двух существующих fixtures перед
прежним индексированием. При отсутствии нужного stage сообщение содержит только
status/kind/reason/message/operational reason, confirmation/hard-stop flags,
число sources и количества наблюдённых stages. Для актуального MCP error envelope
также показывается whitelist вложенного `error`: reason_code, message и
exception_type, только если это dict. Reviewer обнаружил необходимость этой
ветки: current error producer не обязан дублировать reason на верхнем уровне.
Тела документов, snapshot, traceback и весь error object не выводятся.
`empty_seed` теперь сохраняет уже возвращённый payload вместо `_`;
дополнительного вызова retrieval нет.

Запросы, original-only вопросы, корпус, protocol/gold, каталог и подтверждённая
подготовка остаются прежними. Все test bodies, negatives, read/work/output
проверки, return values и collection IDs сохранены. Ранее пустая трасса по-прежнему
останавливает setup до guard bodies; ошибка не превращается в PASS, SKIP или XFAIL.
Если stage присутствует, используется прежний результат и тот же индекс `[0]`.

Локально допускается только stdlib AST/compile/diff review без исполнения
repository code. Обычный CI следующего опубликованного SHA должен дать настоящий
machine reason. Решение о migration или исправлении после него принимается
отдельно по текущему контракту; этот slice не меняет frozen gates или deferred
retrieval policy.
