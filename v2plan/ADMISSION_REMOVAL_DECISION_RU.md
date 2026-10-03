# Решение по упрощению admission

2026-10-03. Рекомендация по запросу пользователя; implementation и production
переключение этим документом не выполняются.

## Выбор

Выбираем ограниченное разделение read и proof. Первое изменение — убрать
qualification reason whitelist из original-read, сохранив explicit guards и
existing locality. Не выбираем замену всего pipeline unified prototype.
Расширение grammar/rescue и поиск очередного lexical threshold прекращаем.

Это уменьшает coupling, но не обещает улучшения recall. Общий semantic relevance
predicate при текущих ограничениях ещё не найден; архитектура его не заменяет.

## Что удалять, что сохранять

| Обязанность | Решение | Почему |
|---|---|---|
| `qualify_evidence` verdict/reason как permission original-read | Первый кандидат на удаление после scoped full-pipeline проверки | Read не обязан иметь answer proof; explicit source/identity/applicability guards уже выделены в prototype |
| `qualify_evidence` как claim-support механизм | Сохранить | Это отдельная обязанность, audited read outcomes не проверяют proof semantics |
| Три terms + adjacent pair | Пока сохранить, не развивать | Recall потери измерены, но безопасная замена не установлена; это control policy, не универсальная проверка смысла |
| Typed двухсловный read path | Пока сохранить существующее поведение; не делать общим правилом | Может сохранить partial fact, но разрешение двух terms не доказывает relevance |
| Relation/list preferences | Сохранить сейчас; целевая обязанность — только ordering | Сейчас они также сохраняют proposals для prefit; удаление изменит доступность контекста |
| Раннее удаление без qualified IDs в ranking | Сейчас не удалять | Его context exemption связан с существующим prefit; глобальное снятие фильтра не проверено |
| Source/security/version/scope/freshness/span/request, literal/subject/applicability | Сохранить | Unknown condition не становится applicable; immutable request/source binding обязателен |
| Повторные проверки после clipping | Сохранить | Новые visible bytes требуют нового решения, это не дублирующая политика |

Не переносить locality в новый scoring feature сейчас: это одновременно изменит
admission и ordering, не будет behavior-preserving удалением.

## Что означают наши данные

2159 exact windows: 586 typed-permitted/original-rejected, из них 570 locality
и 16 qualification reasons. 64 disagreement windows имеют annotated witness.
Окна коррелируют, это не 64 independent claims и не 586 доказанных false rejects.
Typed scope — отдельный need; original scope — весь вопрос.

434 typed proposals отсутствуют в preferred/read prefit proposals. Это
асимметрия этих веток, не доказанная потеря в полном orchestrator.
Audit inventory построен из native candidates и typed windows, а не всех
возможных original-read окон; обратных расхождений в нём нет, но универсальная
вложенность двух политик не доказана.

Native/unified outcomes совпали на всех 2159 windows. Это аргумент за первый
рефакторинг, не доказательство избыточности каждого veto: следующий locality
отказ может маскировать снятый qualification refusal. Нужны guards/mutations
и full-pipeline сравнение, а не только aggregate parity.

## Основание в исследованиях — перепроверено по первичным источникам

- [Callan, SIGIR 1994](https://www.cs.cmu.edu/~callan/Papers/callan794.pdf), §1:
  короткие passages хуже совпадают с длинными queries; факт может пересекать
  границы; all-or-nothing proximity имеет ограничения. Это аргумент против
  универсальности pair veto, не готовая замена и не указание снять locality.
- [BEIR, NeurIPS 2021](https://datasets-benchmarks-proceedings.neurips.cc/paper/2021/hash/65b9eea6e1cc6bb9f0cd2a47751a186f-Abstract-round2.html):
  BM25 — robust baseline на разнородных retrieval задачах. Retrieval score не
  устанавливает applicability, достаточность или право ответить.
- [Sufficient Context, 2025, v3](https://arxiv.org/html/2411.06037v3), §3–5:
  полезный неполный контекст отличается от достаточного; LLM может ошибаться
  с обоими. Autorater/selective generation используют модели. Это обоснование
  разделения read/support, не model-free admission и не гарантия от flags API.

## Один следующий implementation шаг

Удаление original-read зависимости от qualification reasons — отдельный patch,
без миграции typed path, prefit, preferences или раннего ranking filter.
Проверить его в полном current native pipeline относительно freshly measured
baseline того же checkout, с неизменными retrieval и budget. Исторические 49
и isolated 11 не подменяют этот baseline.

Критерии: сохранены baseline claims и partial facts; неизменны proof/edit flags;
нет новых packets в frozen negatives; source/request/identity/applicability
mutations остаются закрыты. Проверить actual final bytes и positive/negative
requests за пределами exposed 80-case набора. Если поведение расходится,
остановить patch и разобрать расхождение, не добавлять case exceptions.

После такого изменения не объявлять единый read admission завершённым.
Удаление двухсловного/трёхсловного конфликта и перенос preferences в чистый
ordering — отдельное policy решение, пока BLOCKED общим relevance контрактом.
Не запускать очередной compiler или сетку thresholds вместо этого решения.
