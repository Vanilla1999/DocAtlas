# Результат: ограниченно ослабить лексические проверки стоит

## Решение

После исправления чистоты вмешательства получено **37/48 вместо предыдущих35/48 и ordinary-hybrid34/48**. Два новых выигрыша: fastapi-01 (время выполнения background tasks) и fastapi-02 (обычная def или async def). Унаследованный starlette-01 не выдаётся за новый выигрыш. Все прежние35 sufficient и все ранее supported required claims сохранены. Все32 контрольных payload полностью неизменны относительно scope.

Это поддерживает предложение пользователя: отсутствие имени библиотеки в каждом абзаце и человеческое написание CamelCase-заголовка не должны автоматически запрещать выдавать релевантный исходный контекст. Проверенная metadata не равна произвольной metadata; контекстная эквивалентность не равна взаимозаменяемости идентификаторов в коде.

Production не менялся, main не затронут, PR189 остаётся draft. Формальный exposed-development screening пройден, но он не равен production readiness: есть побочные изменения выбранных цитат, оба новых выигрыша происходят на одной странице FastAPI, native/live-agent и holdout не проверялись.

## Итоговая матрица исправленного кода

Один frozen ordinary hybrid, те же вопросы, документы и старый assessor. Все новые правила применяются на первичном и повторном допуске видимых окон. Шесть логических вариантов x80 вопросов =480 DTO (48 positives и32 controls, не480 независимых вопросов).

| Политика | Sufficient/48 | Новые против35 | Средний полный DTO | Max |
|---|---:|---|---:|---:|
| current: старый hybrid |34|—|371.0500|795|
| scope: предыдущий раздел + повторная проверка |35|—|378.0375|795|
| scope + catalog |36|fastapi-01|378.5875|795|
| scope + spelling |36|fastapi-02|380.6750|795|
| scope + one_anchor |35|нет|378.0375|795|
| scope + все три |37|fastapi-01, fastapi-02|381.0750|795|

Комбинация добавляет в среднем3.0375 токена (+0.8035%) относительно scope. Это не сумма task tokens и не измерение latency. Новых моделей, генерации пересказов, индексов, embeddings или изменений БД нет. Индивидуальное one_anchor не изменило ни одного из80 конечных payload. Вариант только catalog+spelling без one_anchor отдельно не прогонялся: из таблицы нельзя автоматически выводить отсутствие взаимодействий в такой абляции.

## Что разрешили и чего не разрешали

**Catalog.** Имя библиотеки берётся из независимого pinned source-manifest: project, repository, ref, commit и SHA256 файла. Цитата дополнительно проверяется прежним source-bound binder: файл, проект, stamps, freshness, безопасное происхождение и координаты. Если вопрос о библиотеке в целом, имя не обязано повторяться в каждом абзаце. Произвольные library_id/title/heading_path кандидата не служат таким доказательством. Проверенный контекст виден в существующем section и оплачивается бюджетом. В production для этого необходим реальный доверенный registry contract, а не копирование project label из теста.

**Spelling.** Полное CamelCase-имя из вопроса разбивается на слова и сопоставляется с полным реальным заголовком-предком. BackgroundTasks может соответствовать Background Tasks как заголовку темы. Singular/plural, prefix, соседний или вложенный другой API не отождествляются. Тело цитаты не переписывается. Эксперимент сохраняет консервативные исключения для code-identity запросов, включая backticks; это ограничение и возможный источник дополнительных false negatives, не универсальный parser намерения.

**One anchor.** Одного совпадения достаточно только для самодостаточного определения термина из ближайшего заголовка и при отдельном подтверждённом слове родительского раздела. Старый общий ratio и exact-условия сохраняются. Одиночное упоминание, кнопка с таким названием и heading-only не проходят. Это структурная эвристика, не LLM/семантическое доказательство.

Жёсткие project/source/snapshot/дословность/budget границы не отключались. answer_supported, answer_available, edit_ready остаются false. Query coverage — атрибуция поиска, не доказательство полноты ответа.

## Два действительных возвращённых ответа

fastapi-01: в исходной выдаче были технические подробности, dependency injection и caveat, но не прямое правило о запуске после возврата response. Catalog допускает исходный первый фрагмент docs/en/docs/tutorial/background-tasks.md, строки1–5. В combined этот фрагмент доходит до выдачи; размер790→789 токенов. Caveat заменён более полезным для данного вопроса прямым ответом. Это не буквальное сохранение всего старого текста.

fastapi-02: исходные Dependency Injection и Recap не отвечали, может ли task function быть обычной def. Сопоставление исходного Background Tasks с BackgroundTasks возвращает раздел Create a task function с явным разрешением normal def и async def. В combined строки24–30, размер582→781. В индивидуальном spelling582→793; в обоих случаях прежние цитаты сохранены и добавлен ответ. Различие размеров связано с обычной упаковкой при другом section metadata и прежнем800-token лимите.

Эти факты уже находились в документации. Не требуется, чтобы модель допридумывала их по памяти; ей нужно получить исходный текст с понятной привязкой. Новая модель-генератор ответов не запускалась, поэтому её фактическая точность отдельно не измерена.

## Почему fastapi-06 всё ещё не считается достаточным

Правильное определение origin находится в том же исходном кандидате. В one_anchor и combined оно теперь проходит и первичный, и повторный допуск: до — missing cors, body=[origin], ratio0.2; после — headings дают cors, body по-прежнему [origin], ratio0.4, qualified=true. Прямое определение проверено в пределах исходных заголовков CORS и Origin и исходного файла по SHA.

Но окончательная выдача остаётся прежней: общее введение CORS, preflight и simple requests,789 токенов. Определение origin отсутствует. Следовательно, это уже не только отказ допуска: после него нужный фрагмент не сохраняется дальнейшим отбором/упаковкой. В этом опыте не меняли selector и не выполняли отдельного вмешательства, чтобы различить внутри него ranking/novelty/budget причины. Не приписывать точную последующую причину без такого вмешательства.

Нейросеть действительно могла бы использовать выданное определение. Сейчас же его нет в получаемом пакете. Дополнительное ослабление admission само по себе не гарантирует исправления этого случая.

## Проверка всех восьми изменённых combined payload

| Случай | Изменение относительно scope | Оценка |
|---|---|---|
| fastapi-01 | Caveat заменён прямым правилом,790→789 | Новый sufficient |
| fastapi-02 | Добавлено правило normal/async def,582→781 | Новый sufficient |
| fastapi-04 | Только section: catalog version,665→676 | Старые цитаты сохранены |
| starlette-01 | Только section,515→526 | Унаследованный выигрыш сохранён |
| starlette-02 | Основное правило сохранено; пример lifespan заменён обрезанным введением и shallow-copy пояснением,655→770 | Frozen sufficient сохранён, но добавка не нужна вопросу и часть введения обрывается. Реальный quality caveat |
| pydantic-04 | Только section,701→714 | Старые цитаты сохранены |
| pydantic-05 | Только section,596→609 | По-прежнему needs_review |
| ruff-02 | Основной preview-фрагмент сохранён; две --config цитаты заменены другой --config цитатой,788→670 | Старый sufficient сохранён, но вторичная информация не обязательна вопросу |

В combined изменилось8 payload,4 набора цитат. Некоторые старые детали потеряны в fastapi-01/starlette-02/ruff-02; primary sufficient/required-claim preservation не означает отсутствие любых регрессий. Spelling — наиболее чистый отдельный кандидат: изменился ровно fastapi-02, остальные79 payload прежние. Catalog полезен, но одновременно проявляет прежнюю проблему полезности отбора и расхода места на вторичные сведения. В section catalog печатается также для некоторых унаследованных scope-источников; расходы этой избыточной metadata не скрыты.

## Чистота опыта и проверки

Протокол опубликован до результатов:51aa4a7db1990e9c78d37f217e876ccf3e1d3a9c. Первый прогон2cccff1 тоже дал37, но ручной аудит обнаружил незапланированное общее использование заголовков без активации одной из трёх гипотез. Оно удалено, добавлены4 regression cases, вся матрица повторена. Подробности и SHA первого архива — IMPLEMENTATION_AUDIT_RU.md. Ни вопросы, ни gold, ни thresholds не подбирались по ошибкам.

Финальный tested code:3e91f5dce24e80acc5e48192a0d94c1ea3edb96f. Actions run34785964033, job103801381131, completed/success. **83 tests passed**:43 новых и40 прежних section/research проверок. Перед основной матрицей воспроизведены native80, historical factorial320 и240 прежних scope DTO. Нативные исторические33/48 не подменяют hybrid34.

480 логических DTO, <=3 sources, max795/800;0 source/snapshot/range/heading/catalog/budget ошибок. Все32 control payload неизменны в каждой исправленной новой lane. Это не проверка галлюцинаций модели и не полная оценка false relevance; отрицательные controls имеют ограничения frozen witness-проверки.

Финальный artifact10325979852, SHA256 f3e78c127d0c0fae4686da0613efd34c5f0c28ae3bb04bf8e4f25db834319c96. Архив скачан и пересчитан отдельным скриптом:480 уникальных id/mode,521 source entries, точное воспроизведение160 current/scope payload против архива предыдущего эксперимента. У всех90 новых qualification-rescue events проверена активация зарегистрированного сигнала. Пересчёт saved assessor statuses не является независимым семантическим оценщиком.

## Дальнейшее решение

Да — отделять жёсткую проверку происхождения от мягких проверок написания/релевантности. Spelling — первый небольшой кандидат для отдельной production-интеграции и native-handler теста. Catalog — следующий с реальным trusted registry binding и регрессиями на полезность набора; не заставлять каждый абзац повторять имя пакета. One_anchor пока остаётся диагностикой доступного определения, а не доказанным улучшением конечной выдачи.

Старый screening >=36 и2 project groups против34 выполнен; оба новых выигрыша против35 — FastAPI, один source document. Не объявлять переносимость доказанной. Holdout20 оставлен закрытым согласно протоколу этого прохода. Никаких автоматических merge, новых inference-зависимостей или обещаний48/48.

## Воспроизведение

Из корня checkout tested code с установленными существующими .[dev] зависимостями, Linux:

```sh
export PYTHONPATH="$PWD:$PWD/experiments/grounded-partial/bounded-relaxation:$PWD/experiments/grounded-partial/section-scope"
export DOCATLAS_OFFLINE=1 DOCATLAS_AUTO_VECTORS=0 PYTHONHASHSEED=0
python -m pytest experiments/grounded-partial/bounded-relaxation experiments/grounded-partial/section-scope/test_section_scope.py experiments/grounded-partial/contextual-late/test_factorial.py experiments/grounded-partial/semantic-selection/test_evaluate.py -q
python experiments/grounded-partial/research-suite/restore.py
python experiments/grounded-partial/hypothesis5/no_network.py experiments/grounded-partial/research-suite/verify_baseline.py
python experiments/grounded-partial/hypothesis5/no_network.py experiments/grounded-partial/bounded-relaxation/run.py --output /tmp/docatlas-bounded-relaxation-new
```

Output-каталог должен быть новым. Artifact содержитcode/tests, head, pip freeze, native/tests/replay logs, полные вопросы/DTO/snapshots, первоначальные input fingerprints и before/after qualification traces. Его срок хранения в Actions14 дней; код и компактный результат сохраняются в ветке.
