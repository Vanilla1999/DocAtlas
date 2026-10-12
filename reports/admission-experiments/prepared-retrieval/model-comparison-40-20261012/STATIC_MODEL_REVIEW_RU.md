# Независимый static review model/no-model режима

Дата: 2026-10-12, до нового runtime. Reviewer не автор product changes, не
исполнял продукт/модель/тесты и не изменял вопросы или oracle. Прочитаны изменения
`experimental_candidate_selection.py`, `original_body_discovery.py`, optional
extra в `pyproject.toml` и новый `experimental_selection_modes.py`.

## Заключение

Блокирующего дефекта в проверенных границах выбора источника, model scoring и
учёта работы не найдено. Это разрешает замороженный интеграционный эксперимент,
но не является runtime PASS, доказательством качества Mini или общим security
аудитом. Следующий обязательный уровень — конечные публичные пакеты и их
независимые исходные witnesses.

## Что проверено по коду

- Переключатель захватывается один раз из окружения хоста внутри eligible
  original project read. Request/candidate metadata не включают режим. Без
  experimental admission прежний путь возвращает исходные candidates, без
  импорта torch или transformers. Явный старый callback имеет прежний приоритет.
- Budget и Mini используют один прежний pool: live original discovery binding,
  checked qualified/literal admission, dedup по source/chunk. Оба возвращают
  только индексы объектов этого pool. Ранжирование не переписывает тексты,
  metadata, source grants или query credit. Downstream validators не отключены.
- Настройки валидируются как `budget|mini`, целый top-k 1..20 и абсолютный local
  model path для Mini. По умолчанию k=2. Модель загружается локально, с
  `trust_remote_code=False`, safetensors и проверкой SHA шести pinned assets.
  Нет скрытого обращения к provider или загрузки модели из интернета в запросе.
- CPU FP32 raw logit каждого полного question/window pair определяет порядок;
  ties разрешаются исходным ordinal. Score не превращается в probability,
  cutoff для отказа, qualification или sufficiency verdict.
- При `pool <= k` Mini возвращает тот же budget order и статус `not_needed`
  без model forward. Сначала tokenized весь большой pool без truncation; если
  любой pair длиннее 512 токенов, до inference возвращается весь budget order
  с явным `budgetfallback_overflow` и нулём forwards. Это не «получился Mini».
- Ошибка отсутствующей/несовместимой модели не маскируется budget fallback.
  Receipt сохраняет ошибку и выполненные/попытанные forwards. Один RLock
  защищает resident loader и inference; кэшируется модель, не source admission.
- Observer получает deep copies диагностических представлений, не исходные
  candidate objects. Его исключение сохраняется в отдельном state и не меняет
  выбранные индексы. Полный raw document заменяется hash/length; точные native
  texts остаются в receipt. Проверка исходных документов требует отдельного
  frozen source manifest.

## Правильное чтение метрик

`model_load_seconds` уже включает asset verification/import/load. Его части
нельзя ещё раз прибавлять к этому total. `inference_seconds` и per-row seconds
также являются разложением `total_seconds`, а не дополнительной ценой поверх
полного outer public call. Tokenization с overflow остаётся реальной работой,
хотя model forward не выполнялся.

Полная стоимость query измеряется координатором снаружи реального public call.
Cold preload выполняется отдельно без readiness inference; его wall/import/
asset/hash costs публикуются отдельно. Resident provenance относится к реально
загруженной pinned модели, а не повторной проверке файлов на каждом запросе.

В итоговых результатах обязательны отдельные counts `ranked`, `not_needed`,
`budgetfallback_overflow` и errors. Все 40 запросов в режиме Mini не означают
40 model inferences. При текущем поштучном scoring один успешный forward равен
одной кандидатной паре; вопрос может потребовать несколько forwards.

## Оставшиеся границы доказательства

Этот review не исполнял bad-config, callback/observer failures, concurrency,
asset corruption или default-off integration. Их нельзя объявлять новым
runtime покрытием. Source provenance и final budget требуют проверки реального
public DTO; число кандидатов перед packing недостаточно. Relevance не
устанавливается от наличия live receipt или высокого logit. Question-specific
ветвей, числовых исключений или обращений к evaluation oracle в этих изменениях
не обнаружено.
