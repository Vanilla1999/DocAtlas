# Step13: ошибки запуска и стоимость клиентского контекста

Дата: 7 ноября 2026, Europe/Moscow. Исходный commit:
`1e8f3a3a90c772ef2016ae2bbbf44b78a6c6d3d7`.

Поручение: исправить найденные при review ошибки, затем исследовать и проверить
сокращение токенов относительно прямого поиска. Это не разрешение включить
Qwen/one-hop по умолчанию, менять frozen вопросы/факты/порог или покупать GPU.
Словари синонимов, question-to-file правила, aliases и таблицы расшифровки
не добавляются. Исторический step12-live-comparison не переписывается.

## Изменения и заранее заданные границы проверки

1. Разделить техническую неполноту retrieval (`scan_incomplete`, аварийный
   предел выдачи) и обычное отсутствие подходящих доказательств. Проверить
   настоящий публичный MCP результат и `isError`, сохранив source/scope guards.
   Переиспользовать существующий интеграционный/installed сценарий; не подменять
   scorer. Недоступный/невалидный подготовленный Qwen model path даёт реальную
   ошибку provenance без inference и позволяет проверить публичный отказ.
2. Отдельная исправленная версия live runner: ограниченный standalone OpenCode
   процесс на сессию, гарантированное завершение только принадлежащих запуску
   процессов, структурированный статус retrieval и fail-fast. Исторический
   runner/сбой сохраняются. Проверку lifecycle выполнить с настоящими клиентом
   и MCP; внешний scripted provider допустим только для проверки транспорта,
   доставки и управления процессами, не качества Qwen/Terra.
3. Сначала измерить повторяемые инструкции и tool schemas на сохранённых
   provider payloads. Затем один явно именованный opt-in компактный профиль:
   сохранённые common/source-to-draft правила, target/scope/version, language,
   continuation, uncertainty и authorization. Не менять обычный серверный
   каталог или профиль по умолчанию. Измерить его через настоящий OpenCode
   вместе с прежним профилем на одном фиксированном сценарии.
4. Проверки только интеграционные и выше. До новых запусков записать точные
   сценарии/лимиты. Одинаковый набор повторять только после конкретного дефекта
   или изменения проверяемого кода. Сохранять первый сбой и все реальные calls.
   Не запускать blind260 или широкий старый набор. Финальный independent review
   отдельно проверяет ошибки/права и не выдаёт scripted run за model quality.

## Измерения

Provider totals исходного live-прогона остаются фактами прошлого запуска.
Offline tokenizer даёт только локальную оценку текста, а scripted provider —
проверку фактически переданных prompts/tools/results. Ни то ни другое не
объявляется новыми биллинговыми токенами или качеством конечного ответа.
Нужны абсолютные baseline/candidate counts, видимые инструменты, число шагов,
источники/ограничения и изменения состояния. Экономия не оправдывает потерю
обязательных условий или защитных правил.

## Доступность в текущем workspace

При начальной проверке GPU/nvidia-smi отсутствуют; OpenCode2.2.5 установлен,
но `auth list` возвращает `No authenticated integrations`. Доступны Python3.12
и прежний isolated wheel/client runtime для ограниченных локальных проверок.
Fresh Qwen/Terra inference не запускается без настоящей разрешённой среды;
платные ресурсы, извлечение чужих credentials и ослабление runtime pins исключены.
Отсутствие inference будет явно отделено от выполненных исправлений и замеров.

## Точный ограниченный roster до исполнения

- Existing `test_literal_presentation_public_stdio_preserves_sources_and_read_guards`:
  1 prepare, 7 context requests, 3 resource reads, 0 inference. Один дополнительный
  настоящий stdio Qwen request с существующей пустой model directory проверяет
  отсутствующие provenance/assets: технический отказ, а не обычный no-answer.
  Прежние позитивы, source text, snapshot/version/read guards не изменяются.
- Offline classification: ровно 12 сохранённых step12 `raw.jsonl`; ожидается
  11 завершённых без технического retrieval failure и один `retrieval_failed`
  (one-hop V-M4). Это проверка классификации старого сбоя, не новый запуск.
- Existing `check_profile_client.py --compare-concise`: три независимые реальные
  client sessions, MCP standard4 + MCP concise4 + files2 scripted provider
  requests (максимум10). Один public prepare + один canonical context до
  сессий; в каждом MCP-сеансе status + context + issued resource read и один
  отклонённый status bypass. Files: одно разрешённое и одно отклонённое чтение.
  Вызовы выполняет настоящий установленный пакет. Frozen вопрос/источники
  существующего сценария сохраняются; отдельно проверяются source-to-draft
  paragraph, реальные prompts/tool schemas и неизменность source/database.
  Этот же прогон использует новый bounded standalone session runner и проверяет
  завершение принадлежащих каждой сессии процессов. Отдельного повторного
  lifecycle-прогона без новой причины не планируется.
- До исполнения client acceptance добавлен один отрицательный MCP-сеанс на том
  же fixture: существующая пустая Qwen directory, status → context; максимум
  3 scripted provider requests. Третий объясняющий ответ может успеть начаться
  одновременно с внешним fail-fast listener; дополнительных retrieval/retries
  не допускается. Проверить failed retrieval receipt, отсутствие успешной
  выдачи и завершение owned server. Итого максимум13 scripted requests,0 models.
  Это также позволяет увидеть настоящий concise four-tool Qwen catalog без
  model inference; paired ordinary catalog остаётся отдельным измерением.
- Свежий wheel перед client acceptance; проверка соответствия установленного
  продуктового кода checkout. Локальные текстовые token counts не объявляются
  provider billing. Исходный live comparison и blind260 не перезапускаются.

## Первая попытка client acceptance и основание повтора

`step13-client.OdvhxB/run-01`: FAIL после первого standard MCP-сеанса,
4 scripted requests,0 models. Сам retrieval/source read и отказ jobs bypass
завершились, но независимый PID observer показал реальный MCP child в другой
группе/session, чем лидер OpenCode. Group-only tracking его не наблюдал;
проверка остановилась до concise/files/negative. Это не PASS lifecycle.

Согласовано узкое исправление: host-owned registry реальных MCP PID/start_ticks
и PID namespace, безопасные pidfd handles для точных зарегистрированных процессов
плюс прежняя private client group. Не сканировать credentials/environment чужих
процессов, не выполнять global kill и не сигналить чужую новую группу. Отсутствие
или ошибка registry не дают подтверждения cleanup. Transparent wrapper пишет
свою идентичность и исполняет тот же сервер без подмены stdout/results.

После исправления допустим один повтор того же ограниченного acceptance в
новом output, максимум13 scripted requests,0 models; первая попытка сохраняется.

## Результат повтора и финальное read-only review

`client-attempt-02`: PASS,13 scripted requests,0 models. Зарегистрированные
transport/server в положительных и отрицательном сценариях завершены;
`scan_incomplete` даёт failed retrieval и fail-fast. Повторный запуск этого
acceptance без изменения проверенного helper/profile не планируется.

Ревью будущего `run.py` отдельно выявило P2 воспроизводимости: подготовка
профилей шла внутри execution loop, а provenance продукта покрывала только
Python-файлы. До будущего inference исправляются оба пункта: заранее
сформированные12 конфигураций, единый upfront manifest packaged product /
профиль / observer / runtime inputs, проверка drift до каждой сессии.
Эти правки не меняют уже проверенные helper/profile и не являются причиной
заново исполнять клиентский roster. Допустимы синтаксис и read-only review;
новый Qwen/Terra запуск по-прежнему NOT RUN.

Новый raw layout отличается от исторического. Старые `account.py`/`audit.py`
с жёстким историческим output не запускаются для нового runner. До настоящего
качества нужен отдельный parameterized offline audit; guarded launcher сам
по себе не считается законченным проверенным quality benchmark.
