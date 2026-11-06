# Parent review: кандидат нового dependency contract

**Решение: принять направление и уточнённый контракт для подготовки capability
experiment; production implementation и inference не разрешены.** Это результат
design review, не подтверждение качества relation classifier. Модель пока не
выбрана. Данный документ уточняет `DESIGN_RU.md`; при расхождении действует он.
V3 остаётся PRE-INFERENCE BLOCKED; исторический Qwen validation остаётся FAIL.

## Принятое изменение продукта

Прежнее правило требовало раскрыть каждую ссылку. Новый кандидат требует
сохранить зависимости исходной задачи **и условия всех фактически выданных
утверждений**. Справочная/навигационная ссылка может остаться буквальной ссылкой
без адресованного текста. Это явное изменение reference-completeness контракта,
а не исправление результатов прошлого эксперимента.

Единственный предлагаемый метод — отдельная source-grounded классификация
каждого occurrence в REQUIRED / NONBINDING / UNKNOWN. Старый unary Qwen score
не является оценкой типа зависимости. Непроверенный relation component не
получает права на production omission только благодаря новому prompt.

Приняты следующие инварианты:

- Для NONBINDING должны отсутствовать оба основания: необходимость для задачи
  и необходимость для корректного понимания выданного утверждения. Низкая
  relevance, название раздела, положение в ancestor или наличие TOC не основания.
- REQUIRED и UNKNOWN включают полный однозначно разрешённый addressed extent,
  children, ancestors и definition-owner bodies; новые bodies обрабатываются
  одинаково. UNKNOWN с недоступным target/неразрешимым parse scope даёт incomplete.
- Scope/version/hash/live qualification не расширяются по ссылке. Удаления
  текста, скрытого fetch, урезания extent и caps ради экономии нет.
- Решение привязано к immutable inputs, не к текущей выдаче/порядку обхода/бюджету.
  Target, включённый хотя бы одной зависимостью, другая ссылка не удаляет.
- Source witness проверяем на literal span/hash; это не доказательство
  семантической правильности NONBINDING. False omission остаётся основным риском.

## Обязательные уточнения до capability experiment

### 1. Два явных режима входа вместо неявного пропуска target

`resolved_target`: весь checked source document + question + точный occurrence +
полный checked target document/extent/ancestors в контексте. Если это не помещается,
UNKNOWN. Нельзя перейти к source-only только ради fit, стоимости или решения no.

`unavailable_target`: весь checked source document + question + occurrence + typed
resolution failure. В модель не передаются excluded bytes, target excerpts из
oracle, содержание из памяти или labels. Source-only NONBINDING допускается
только как отдельно проверяемая способность определить ненормативную функцию
ссылки по доступному источнику. Неясная функция означает UNKNOWN/refusal.
Оба режима независимо представлены в oracle и frozen policy.

### 2. Проверять разрешение на пропуск, а не требовать угаданного имени класса

| Независимый gold | Допустимое итоговое поведение |
| --- | --- |
| REQUIRED | Полный target и обязательные факты; prediction UNKNOWN допустим, если closure действительно всё сохранил. NONBINDING — FAIL, даже если другой seed случайно спас текст. |
| UNKNOWN | NONBINDING — FAIL. Полное покрытие доступной зависимости или явный refusal для неразрешимой. |
| NONBINDING | Пропуск target допустим. Консервативное включение — лишняя стоимость, не потеря facts. |
| Unlabelled | Не использовать как negative/permission-to-omit ground truth. |

Отдельно проверяются решения и конечные public packets: случайная redundant
доставка не должна скрыть неверное разрешение выкинуть условие. Для gold UNKNOWN
не требовать угадывания неизвестного содержания. Refusal на задаче, заранее
объявленной answerable, не становится quality PASS.

Capability experiment не проходит при постоянном UNKNOWN/REQUIRED: должны быть
продемонстрированы реальные правильные NONBINDING на заранее размеченных
navigation и reference-only occurrences, включая source-only unavailable route,
при нуле ложных разрешений пропуска на REQUIRED/UNKNOWN. Числа примеров,
разбиение и критерий фиксируются до первого вызова; не назначаются по scores.
Итоговая достаточная экономия проверяется отдельно исходным >=50% gate.

### 3. Parser feasibility — отдельная обязательная граница

Текущий native `_edges` не возвращает occurrence spans; existing masking теряет
inline-code reference labels. Новый relation model сам это не исправляет.
До production diff нужен inventory существующих parser capabilities: полные
точные occurrences, definition-use binding, unsupported coverage. Сначала
переиспользовать native parser; не считать regex приближением корректного
occurrence parser и не скрывать неизвестные участки.

Offline capability component может получать независимо размеченные raw spans,
но такой опыт доказывает только classification на предоставленном input. Public
integration gate обязан получать их реальным production path, без oracle/mocks
в extraction/selection/validation. Если для этого нужен существенный parser
rewrite, это отдельный blocker и review; не неучтённый «малый diff».

### 4. Новый oracle и прежние источники

16 synthetic + 8 OTel/Rust задач считаются seen development. Их вопросы, raw
sources и факты не меняются. Изменение reference contract не превращает их в
независимый holdout и не отменяет уже найденную потерю погодных условий.

До вызовов relation model нужны source-backed gold decisions, оба основания,
полные extents и literal witnesses. Parent независимо читает оригиналы и
утверждает labels. Если функция ссылки неоднозначна, gold UNKNOWN; не создавать
удобный NONBINDING ради проходимости. Paired occurrences одинакового target
должны различаться реальным исходным употреблением, не дописанными нормативными
словами. Требуются true safe-to-omit targets и required positives.

Новый source-backed holdout отбирается по заранее описанным задачам/мотивам,
до inference. Author upstream, selector/annotator agent — не blind external
benchmark. Новые cross-version и scope cases используют реальные native
boundaries, а pinned upstream commit сам по себе не доказывает native versioning.

### 5. Стоимость, остановка и разрешения

Считать отдельно seed forwards/tokens, relation requests/input/output/repeats,
cache hits и rechecks, final source tokens, wire/rendering, latency и failures.
Relation prompting может съесть всю экономию. Provider-token экономия требует
сопоставимого end-to-end измерения позже; >=50% source reduction её не доказывает.

Все return paths, в том числе dependency refusal, должны иметь bounded public
diagnostics и whole-result emergency guard. Это учитывает найденный V3 early
return defect, но сейчас production исправление не выполняется. Сокращение
диагностики явно отмечается; source obligations не урезаются.

Следующий допускаемый шаг — подготовить **review-ready capability package**:
один обоснованный candidate model/runtime без загрузки, два точных input schemas,
source/parser feasibility inventory, независимо размеченные development relations,
новую holdout specification, frozen decision rules и конкретный ограниченный
call/token бюджет на review. Ни training/model search, ни trial prompts, ни
production integration, ни вызовы модели этим design review не разрешены.
Для inference требуется отдельное утверждение конкретного пакета; после FAIL
не менять policy/questions/labels ради PASS. T01/Terra/L2 заблокированы.

## Короткий вывод

Пропускать можно только ссылку, признанную необязательной для задачи и смысла
выданного текста. Сомнение сохраняет зависимость. Успех требует независимого
доказательства правильных пропусков, сохранения всех обязательных фактов и
экономии — новое название класса ничего из этого не доказывает.
