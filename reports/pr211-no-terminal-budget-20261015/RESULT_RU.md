# PR211: отключение terminal first-fit — два вопроса PASS

База: PR211, `5e324e357dde61a0f562ee9c4bd124ddbb27ed20`.
Изменение: закомментированы вызовы terminal first-fit и последующей проверки
того же cap в `context_tools.py`. Source recheck и итоговая валидация сохранены.
Это явное изменение контракта: полный DTO больше не ограничен12000 на этой
границе. Остальные ограничения acquisition не менялись. Модельный вызов не
добавлялся; автоматический отказ от модели по размеру здесь не реализован.

Из изменённой рабочей копии собран и отдельно установлен wheel без обновления
общей среды. Loaded context_tools bytes совпали с изменённым исходником.
Выполнены2 cold prepare и2 исходных get_docs_context через публичный in-process
MCP dispatcher с реальной изолированной SQLite, на полных frozen source families.
Default PR path, без experiment env/lookup/model/mock retrieval.

| Case | Старое архивное покрытие | Новое покрытие | Sources | DTO o200k_base | Bytes | Call seconds |
|---|---:|---:|---:|---:|---:|---:|
| P03 |442/515|**515/515 PASS**|167|47851|144210|1.545|
| E01 |0/557|**557/557 PASS**|256|73612|217053|2.293|

Старые числа — архив baseline, не новый парный A/B. Новая выдача содержит
полное правило и примеры Poetry, все6 ESLint filenames, TS setup caveats и
продолжение root/export. Oracle и вопросы не менялись, gold прочитан только
после обоих вызовов. Проверены exact snippets в заявленных raw lines,
scope/version/authority/project identity и committed source content hashes.
Ошибок проверки источников0. SQLite и проектные файлы неизменны за context calls.
Полный historical snapshot metadata audit не выполнен: сохранены committed
content hashes, но не полный metadata_json. Это не installed stdio/real client
и не проверка сгенерированных ответов. Models0, V40 не запускался.

Вывод: на коде PR211 оба прежних witness полностью доставляются после отключения
этапа. Цена — существенно увеличенный пакет; вместимость конкретной модели
этим запуском не доказана. Negative/strict-empty качество не проверялось.

Доказательства: `RAW_RESULTS.json`, `*-dto.json`, `*-raw-assessment.json`,
`*-request.json`, `preparation/`, `MANIFEST.json`, `product.patch`.
Runtime scripts сохранены как `run.py` и `assess.py`; временные абсолютные пути
в них относятся к этому изолированному запуску, не к production configuration.
