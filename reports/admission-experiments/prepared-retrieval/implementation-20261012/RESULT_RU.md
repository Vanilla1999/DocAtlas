# Реализованный путь до модели: результат и границы

## Что готово

В ветке `fix/main-flow-compact-evidence` реализована первая opt-in поставка:
общий source-valid admission, reader подготовленных parent sections, повторная
проверка итоговых source spans и бюджет всего конечного MCP-пакета. Default не
переключён. Новых правил под числа, единицы, тематику или вопросы fixtures нет.

**Пройдены четыре новых интеграционных сценария и две существующие публичные
регрессии.** Независимый reviewer после зелёного запуска нашёл реальный дефект
атрибуции при уменьшении пакета. Он исправлен; тот же checklist-сценарий усилен
и адресно повторён успешно. Полный набор после этой последней правки повторно
не запускался. [Независимый отчёт](INDEPENDENT_REVIEW_RU.md) сохраняет исходный
review FAIL и последующее закрытие замечания.

Граница: установленный editable пакет → публичный in-process MCP → настоящая
подготовка member, SQLite и lexical retrieval → selection/finalizers/validation
→ конечный context DTO и source resources. **Вызовов моделей — 0.** Это не тест
качества сгенерированного ответа и не installed-stdio или production smoke.

## Изменения в коде

### 1. Общий admission

`DOCATLAS_EXPERIMENT_ADMISSION=source_valid_candidates_v1` разрешает доставить
исходный найденный фрагмент, не требуя от каждого документа повторить все числа
и достаточную долю слов составного вопроса. При этом сохраняются текущие
membership/scope/version/hash/span/owner/lifecycle, hard-exact, locator и
unresolved-name ограничения. Нужен live receipt именно текущего исходного чтения.

Новый witness не становится `qualified=True`, не получает coverage credit и не
разрешает отвечать или редактировать. Source validity и semantic contribution
остаются разными свойствами. Режим доступен только исходному project read;
explicit lookups и module/all scope не получают этот расширенный admission.
Точка подключения экспериментального selector принимает новый режим, но
автоматический Mini/reranker не установлен.

### 2. Проверка после поздних преобразований

До finalizers сохраняются canonical native seeds. После structural/recovery
преобразований проверяется связь каждого итогового исходного фрагмента с ними:
то же окно, точный subspan, допустимое структурное расширение или подтверждённый
связанный блок. Близость в файле сама по себе не разрешает добавить произвольный
соседний текст. Повторно проверяются source/request условия; сериализованная
квитанция не заменяет текущего receipt.

Review устранил ошибочную классификацию crop по широкому reference envelope
и перенос ограничения размера structural expander на обычный native crop.
Оба исправления сделаны до первого broad runtime, без специальных условий
для проверяемых вопросов.

### 3. Reader подготовленной структуры

При `DOCATLAS_EXPERIMENT_PREPARED_PARENTS=1` новое поколение индекса может получить
необязательный manifest `validation_json.prepared_parents`. Он связывает schema,
parser revision, generation, source identity/hash, число и digest полного
канонического списка parents. Перед сертификацией список сравнивается с результатом
существующего parser, а не просто хешируется произвольное содержимое таблицы.

`SourceReferenceContext._document` читает существующие `retrieval_parents`,
проверяет сертификат и восстанавливает текст точным срезом проверенного raw.
Reader не выбирает дублированный `display_text`. Отсутствующий/устаревший/невалидный
артефакт даёт явный miss и прежний parser fallback. Query не мигрирует базу,
не запускает sync и не кэширует разрешение на источник. Старое поколение без
manifest остаётся рабочим; неизменённый sync не принуждается создавать новое.

Это **первое переиспользование подготовленных parents в source-reference
consumer**. Остальные structural consumers пока могут снова разбирать parents;
atoms, статистики и граф не перенесены целиком в prepared provider. Скорость
всего pipeline этой поставкой не доказана. Parser semantics, chunk IDs и общий
generation config hash не менялись.

### 4. Конечный бюджет

`DOCATLAS_EXPERIMENT_CONTEXT_MAX_TOKENS=<positive integer>` независим от admission
mode и не вводит default cap. В eligible project scope проверяется весь JSON,
который возвращает MCP, после recovery decoration и повторно после регистрации
resources. Мера — максимум из offline `o200k_base` и `ceil(UTF8_bytes/4)` на том же
не ASCII-escaped JSON с обычными разделителями.

При переполнении выбираются целые подтверждённые строки или уже допущенные
native варианты. Нового поиска, произвольной обрезки текста или модели нет.
Неполнота обозначается явно. Credit после repack может только уменьшиться:
видимый фрагмент квалифицируется заново, новые IDs сверх входного публичного
ceiling запрещены, старые assignment IDs не переносятся без witness.
Cap меньше даже обязательной пустой оболочки — ошибка конфигурации.

Это бюджет данного MCP DTO. История разговора, framing внешнего клиента, полный
host prompt и генерация в него не входят.

## Что показали конечные пакеты

| Проверка | Наблюдаемый результат | Что это подтверждает |
|---|---|---|
| Составной вопрос: 11 линз, упаковка, получатель/подпись акта | Default: 2/4 обязательных факта из одного документа. Experimental: 4/4, оба документа | Доставка уже нужных исходных сведений в этом независимом сценарии |
| Полный checklist | Все 16 пунктов сохранены при широком и малом cap | Содержимое не потеряно в проверенном budget repack |
| Cap 900 | Финальный пакет 758; wide 906 | Весь MCP JSON укладывается в cap, не только сумма snippets |
| Prepared off/on | Полный DTO совпадает, кроме объявленных session URI/estimate | Совместимость вывода на данном корпусе |
| Legacy → edit → sync → restart | Legacy fallback совпадает; stale чтение пустое; после явного sync новая редакция, после restart тот же результат | Freshness и lifecycle по публичному пути |
| Module / project / all | Правильная доставка module-документа; нет переноса в project-only | Сохранение scope |
| Unlisted / другой проект / неизвестный locator | Источники не выданы | Проверенные границы доступа/адресации |
| Hard-exact negative | Default и experimental пусты; old empty-source oracle PASS | Один конкретный отрицательный тип, не общая semantic relevance |
| Чтение | Документы и логическое содержимое SQLite неизменны | Нет скрытого prepare/sync при query |

В optics цена доставки выросла: полный JSON **1460 → 3262 bytes**,
UTF8-quarter proxy **365 → 816**. Это реальный прирост полноты с увеличением
контекста; доказательства удешевления нет. Контроль здесь — обычный default без
cap, experimental — с cap 12000. Это интеграционный контроль доставки, а не
отдельный чистый причинный A/B всех компонентов при полностью одинаковом packing.
[JSON-результаты](RESULTS.json) содержат ссылки на точные пакеты.

У baseline optics `query_coverage=full` не означает полного ответа: политика
поля — `retrieval_attribution_only`. Оба факта об упаковке действительно отсутствуют.
Source content SHA в публичной row — projection fingerprint; raw-file SHA
проверяется отдельно по опубликованному snapshot и continuation binding.

## Запуски и обнаруженные проблемы

| Run | Итог | Prepare/sync | Context | Resource | Model |
|---|---|---:|---:|---:|---:|
| 01 | Setup FAIL: отсутствовал жёстко заданный `/tmp` | 0 | 0 | 0 | 0 |
| 02 | Verifier FAIL на default: потерян исходный LF при реконструкции span | 1 | 1 | 0 | 0 |
| 03 | 4 pytest PASS; независимое review нашло attribution defect | 5 | 22 | 6 | 0 |
| 04 | 2 существующие default-регрессии PASS | 2 | 2 | 0 | 0 |
| 05 | Адресный checklist retest после исправления: PASS | 1 | 4 | 0 | 0 |
| **Все фактические попытки** | | **9** | **29** | **6** | **0** |

Из девяти подготовок семь выполнены через public `prepare_docs`, две — через
прежний подтверждённый member service fixture. Время pytest: Run03 4.01 s,
Run04 0.81 s, Run05 1.85 s. Это время тестовых сценариев, не benchmark latency.
Resource ответы проверены тестами; отдельно их raw JSON не сохранён.

До первого broad output независимый reviewer подтвердил два исправления verifier:
сохранение LF через `splitlines(keepends=True)` и снятие неверного требования
обнулить уже существовавшую retrieval attribution. Это изменения assertion/
предпосылки теста, а не «неизменный oracle». **Документы, вопросы, редакции, факты
и caps не менялись.** После Run03 добавлена отдельная regression assertion для
реального product defect: сокращение пакета не повышает credit/проверенность.
История и SHA до/после сохранены в [ledger](execution_ledger.json),
[frozen_inputs.json](frozen_inputs.json), [решениях о контракте](CONTRACT_DECISION_RU.md)
и manifests соответствующих запусков.

После runtime убрана только лишняя пустая строка в конце двух файлов — реализации
finalization и интеграционного теста. [Финальный manifest](final_file_manifest.json)
связывает эти SHA с протестированными версиями; содержимое кода, assertions и
fixtures не изменилось. Исходные pytest log/XML сохранены побайтно, включая
служебные trailing spaces, и исключены только из проверки форматирования текста.

## Как включить

Добавьте в окружение существующего MCP-сервера:

```json
{
  "DOCATLAS_EXPERIMENT_ADMISSION": "source_valid_candidates_v1",
  "DOCATLAS_EXPERIMENT_PREPARED_PARENTS": "1",
  "DOCATLAS_EXPERIMENT_CONTEXT_MAX_TOKENS": "12000"
}
```

Prepared flag должен присутствовать при создании нового поколения и при чтении.
Старый snapshot автоматически не перестраивается: без manifest работает fallback.
Обычные подтверждённые операции подготовки остаются прежними. Флаги задаёт host,
а не документ или вопрос. Каждый механизм можно включать отдельно; удаление
трёх переменных возвращает прежний default путь.

В установленном dev-окружении минимальные новые проверки запускаются так:

```bash
python -m pytest tests/test_prepared_retrieval_integration.py -q
```

Fixture сама использует offline lexical путь. Для сохранения точных конечных DTO
задайте `PYTEST_DOCATLAS_ARTIFACT_DIR` вне каталога fixture project/storage.
В sandbox без `/tmp` используйте существующий приватный `TMPDIR`.

## Решение о дальнейшем использовании

Opt-in реализация пригодна для следующих контролируемых исследований и проверки
на реальных данных проекта. Оснований включать broad admission по умолчанию пока
нет: источник может быть подлинным, но относиться к другому исполнителю, условию
или отношению. General relevance, set sufficiency и модельный ответ здесь не
оценивались. Старые V1–V3 результаты и отрицательные критерии не пересчитывались.

Следующий шаг оптимизации структуры — один request-scoped provider неизменяемых
parents для остальных consumers, если профиль подтвердит заметную повторную
работу. В него нельзя переносить qualification/admission/access decisions.
Добавление Mini или другой модели требует отдельного подтверждённого gap в
поиске/отборе и полного учёта стоимости; эта реализация новых моделей не требует.

## Навигация

- [Протокол](PROTOCOL_RU.md), [решения о контракте](CONTRACT_DECISION_RU.md).
- [Интеграционные сценарии](../../../../tests/test_prepared_retrieval_integration.py).
- [Машинные результаты](RESULTS.json), [полный ledger](execution_ledger.json).
- [Независимое review](INDEPENDENT_REVIEW_RU.md).
- [Run03 JSON](run-03-packets/), [Run05 JSON после исправления](run-05-packets/).
