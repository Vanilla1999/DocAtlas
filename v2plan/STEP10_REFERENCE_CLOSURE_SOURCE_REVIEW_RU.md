# Step10 reference closure v3: предварительный parent source review

## Итог после завершённого checkpoint исполнителя

**PRE-INFERENCE BLOCKED подтверждён родителем. Эксперимент в текущем виде
не допущен к freeze/calibration/validation. Бюджет public/model calls — 0.**

Прочитаны итоговые CHECKPOINT, SUPPORTED_CONTRACT, FEASIBILITY_BLOCKER и весь
шестифайловый implementation.diff, а также задействованные control-flow участки.
Отдельная read-only проверка stdlib подтвердила:

- все 54 entries итогового manifest совпадают с текущими bytes;
- 39 новых literal facts совпадают с raw spans/hash;
- прежние 16 canonical tasks не изменились;
- implementation.diff точно воспроизводится из пяти BEFORE files, нового
  contract module и текущих файлов (шесть операций).

Manifest SHA256:
`b5b955b82a930dda810cdbffdf27fb3350f33065c6f0eb4f7a2f916d5e76d817`.
Родитель не повторял compile/AST, не импортировал production и не запускал
inference, closure, tests или threshold simulation. Дополнения 25→39 facts
закрывают перечисленные ниже конкретные замечания; прежние draft hashes
сохранены как история, а не выдаются за hashes новой разметки.

### Подтверждённый источник блокировки

Для H-O1/H-O2/H-O3 отсутствие required sections нарушает quality gate.
Их наличие при revision2 требует root introductions, TOC targets и downstream
ссылки на отсутствующие/excluded документы. Поэтому complete answer невозможен
при текущем finite scope и обязательности каждой explicit dependency. Это
достаточно для остановки независимо от score/threshold. Расширение scope само
по себе не решает navigation amplification, а настройка threshold не устраняет
противоречие. Совокупная token reduction численно не оценивалась.

Это ограничение принятого нами design, а не только проблема качества модели:
правило приравнивает все hyperlinks, включая навигацию и справочные ссылки,
к обязательным зависимостям ответа. Нельзя представить отказ с пустой выдачей
как успешную экономию или no-answer. Исторический validation FAIL остаётся
отдельным результатом; новый runtime FAIL не заявляется.

### Code review: поддержанные части и незакрытое замечание

В просмотренном diff semantic seeds не раскрывают subtree; targets раскрывают
полный section/document; очередь включает ancestors/definition owners и
дедуплицирует полные document identities. V3 начинает delivered gaps с пустого
списка, а incoming diagnostics учитывает отдельно. Новый policy schema4 связан
с unchanged scorer subcontract; scorer bytes совпали с manifest. Refusal
отделён от no-answer и отвергается evaluator. Это статический review, не proof
live qualification/installed/public runtime.

Обнаружен дополнительный code-review blocker перед любым будущим допуском:
`minimal_context_selection.py:211–217` возвращает новый dependency-incomplete
packet до `delivery_size`/EMERGENCY_TOKENS проверки (`:273–278`). В packet
передаётся полный closure с неограниченным списком gaps/targets. `_refresh_estimate`
лишь пересчитывает estimate. Поэтому утверждение о сохранённом delivery guard
для нового error path не подтверждается кодом; нужен bounded public diagnostic
receipt/whole-result size guard, без усечения source obligations и без потери
явного признака неполной трассы. Фактический overflow не воспроизводился.

### Следующее решение

Текущий V3 сохранить как заблокированный эксперимент; не тратить inference
и не заменять корпус для PASS. Для продолжения нужен отдельный явно изменённый
product contract: что считается обязательной зависимостью ответа и как
отличается от navigation/reference-only links. Надёжность такого различения
ещё не доказана; молчаливое исключение TOC/ancestor links недопустимо.
Новая версия должна пройти отдельный design review, использовать этот набор
только как seen regression и получить новый независимый holdout до inference.
Это рекомендация следующего направления, не разрешение на реализацию или вызовы.

## История: предварительный review до итогового diff

**Решение на предварительном этапе: freeze/inference пока не разрешены.** Это review подготовки,
не новый scored FAIL и не завершённое review production diff.

## Проверено независимо

Родитель прочитал исходные baggage/context/propagators документы OpenTelemetry
и interrupts/exceptions/panicking из Rust Embedded Book. Однократная read-only
проверка Python3 stdlib сопоставила 12 записей provenance с локальными bytes/SHA256
и 25 новых fact-spans с буквальным текстом и hash исходника: расхождений нет.
Production/scorer/closure не вызывались, model calls отсутствуют. Эта проверка
подтверждает согласованность локальных артефактов, не сетевую аутентичность upstream
и не полноту смыслового эталона. Первоначальный вызов `python` не выполнился:
команда отсутствует; проверка выполнена через `python3`.

Проверенная draft revision в `eval/blind_project_context/step10-reference-closure-v3/`:

| Артефакт | SHA256 |
| --- | --- |
| source-provenance.json | c07af1035a32b2cf5875a04ebf7bf7714371ffb58abf582dde6c051b99118ca8 |
| holdout-tasks.json | e9f0834b71cbce1e5b492f41029f6ed44a589498544eabf683cf1ec32f07c268 |
| fact-spans.json | 0f6998f93d5e0cbe457282d58a2fe449426df7526b2842f2d63730e8087d0ed5 |
| projects.json | ba2df3bb43b7d58c4c1e19182a1b38c73babdf90d844b4060174d01f7292f039 |
| source-extent-graph.json | a83808677f28b1c1e6cdd3eda3b834ab0d27b4e9378af531efd917b03bd68f8d |
| prepare_annotations.py | 61c0956c53d215f8f88536db03b06434aad4cae76fae63399f72878efe39343b |

## Блокер feasibility: оглавление входит в ancestor body

В OTel `specification/context/api-propagators.md:10–39`,
`specification/baggage/api.md:15–24` и `specification/context/README.md:17–24`
находятся реальные локальные ссылки оглавлений. По принятому revision2 правилу
required child включает root introduction, а ссылки root раскрывают все разделы
документа. Draft independent graph уже отражает эти edges.

Это не предположение о score: в тексте есть цепи
`api-propagators.md:331` → baggage Propagation,
`baggage/api.md:188–193` → propagators distribution / env-carriers,
`baggage/api.md:141` → полный Context document. Дополнительно появляются ссылки
на отсутствующие в collection glossary/overview и внешние нормативные документы.
env-carriers присутствует только в исключённом module scope эксперимента.
Это ограничение разрешённой experiment collection, не запрет доступа upstream.

Следовательно, до inference требуется явный feasibility verdict: навигация
разворачивает документы, а delivered unresolved references требуют incomplete.
Нельзя исключать оглавления по admission role, обрезать children, скрывать gaps
или заменять corpus по полученному score. Точное сокращение в токенах здесь не
измерялось; новый quality/reduction PASS или runtime FAIL не заявляется.

## Разметка: совпадения цитат недостаточно

Возвращены замечания к смысловому покрытию новых вопросов:

- H-O1: Context Overview:37–39,47–51 (immutability и использование concern APIs
  вместо прямого implicit Context API); baggage:157–161,174–176 (implicit get/set
  и способы очистки). Сейчас Overview не отмечен direct required, хотя отдельные
  facts могут попасть в выдачу как зависимость.
- H-O2: GetAll ordering и самостоятельная HTTP case-insensitivity оговорка
  (`api-propagators.md:241,249`).
- H-O3: цитаты условий обрываются перед bullet с Getter/Setter; обязательные
  Context/carrier должны быть покрыты (`api-propagators.md:290–306`).
- H-R1: прямой вызов handler отличается от программной генерации interrupt
  (`interrupts.md:43–47`).
- H-R2: диагностический смысл PC (`exceptions.md:250–251`).

Whole required units уже могут защищать часть этих условий; это не утверждение
об их потере в ещё не выполненном packet. Требуется явно связать semantic
obligations с исходным вопросом, не считать 25 цитат полным эталоном автоматически.
Дополнение новой разметки допускается только до freeze/inference с историей;
вопросы, источники, критерии и старые 16 cases не подгоняются.

## Следующий шаг

Astra Low получает замечания и завершает review-ready checkpoint с конкретным
feasibility verdict, versioned diff и перечислением изменённых после этого
review артефактов. Если raw-source analysis уже показывает невозможность
acceptance, зафиксировать preparation blocker без расхода inference.
T01/installed/Terra/L2 остаются заблокированы. Historical Qwen validation FAIL
и отсутствие доказанной экономии provider tokens сохраняются.
