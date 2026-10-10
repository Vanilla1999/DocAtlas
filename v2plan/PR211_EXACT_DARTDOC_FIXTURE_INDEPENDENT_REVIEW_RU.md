# PR211: независимый review exact Dartdoc fixture

Дата: 2026-10-08. Base `03583656617336a746e9192249467017d6131f29`.
Вердикт: **APPROVE** для `tests/test_web_fetcher.py`, SHA256
`2c6a1e7826c8f4d0e2f424155c14367fb1b362bb2a2b0ef0f4e84860f6149923`.

Root независимо прочитал полный diff, авторский report, finite membership,
`WebFetcher._fetch_finite` и `_new_client`, transport policy и исходный test.
Проверяемый контракт — извлечение Dartdoc из уже указанной class page без browser.
Исходный exact URL не был результатом discovery и остаётся единственным document
member. Отдельный robots URL соответствует current control contract; его ответ
проходит штатный RobotsChecker, `respect_robots` не отключён.

MockTransport заменяет только raw HTTP boundary. Штатные WebFetcher client
construction, DocsHttpClient, public-IP validation/pinning, finite preflight,
контрольные и document URL policies, extraction и пределы сохраняются. Захваченный
до patch `client_type` исключает рекурсивный вызов mock factory. Transport получает
только фиксированный публичный IP и проверяет точный исходный document URL через
Host/raw_path. Env proxy по current default выключен; внешние DNS/HTTP обращения
не нужны. Политика path prefixes не служит membership: selected content и robots
контролируются отдельными exact lists.

Positive fixture сохраняет nonempty class/constructor/property extraction и
browser=False. Два negatives изменяют только entry URL либо наличие robots
control; оба требуют точный ValueError и ноль дополнительных requests. Финальный
trace остаётся `[robots, selected]`. False-positive через неиспользованный response,
пустой docs list, другую source identity или silent discovery блокируют assertions.

Независимый stdlib AST comparison подтвердил сохранность всех шести исходных
Assert nodes и добавление пяти новых; весь module AST вне одной функции совпал.
Signature, decorators, остальные tests и HTML fixture неизменны. 957 строк не
превышают действующий предел 1000; static compile и diff-check прошли. Никакой
runtime/import/network/installation здесь не выполнялся. Actual pytest PASS
должен подтвердить ordinary CI опубликованного SHA. Другие remote discovery и
provenance tests не входят в одобренный slice.
