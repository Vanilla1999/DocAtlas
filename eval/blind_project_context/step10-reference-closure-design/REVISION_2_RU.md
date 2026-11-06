# Revision 2 — консервативное замыкание явно адресованных разделов

**Только design; не production/inference approval.** Предыдущий текст сохранён
байтово в `history/revision-1/` с SHA256. Эта ревизия заменяет его proposed closure
semantics и бюджет:32calls не являются утверждённым планом. Historical validation
FAIL неизменен; frozen code/data/policy не редактируются.

## Одно выбранное правило

**В пределах checked authorized corpus сохранять source-exact замыкание всех
явных ссылок из всего фактически включённого текста на полный адресованный
автором раздел.** Ни admission role, ни повторный relevance threshold не
фильтруют эти зависимости.

1. Semantic seed по-прежнему допускается по score и первоначально включает
   только own body, headings и ancestor introductions — не весь subtree seed.
2. Все включённые bodies обрабатываются одинаково: seeds, ancestors, reference
   targets, дети адресованного раздела и definition owners. Их реальные links
   обходятся без деления на «полезные» и «incidental navigation».
3. Однозначный heading anchor включает **section extent**: от адресованного
   heading до следующего heading равного/меньшего уровня или конца документа,
   со всеми дочерними bodies. Heading-only section подчиняется тому же правилу.
   Добавляются ancestor introductions. Root-section может охватить весь документ;
   это допустимая стоимость, а не повод обрезать children.
4. Local link без fragment адресует весь checked документ: включается документ
   целиком. Для explicit HTML anchor, привязанного parser к owning section,
   консервативно включается весь owning section extent. Неоднозначное владение
   anchor или неподдержанная адресация — explicit incomplete, не выбор первого
   match и не объявление зависимости удовлетворённой.
5. Reference/footnote definition сохраняется вместе с **целым definition-owner
   body**, включая continuation lines. Все реальные links этого delivered body
   обрабатываются тем же правилом. Existing masking/reference/footnote logic
   переиспользуется; selective occurrence-span parser не создаётся ради экономии.
6. Обход до fixpoint, cycles/multi-hop дедуплицируются по полной native source
   identity и spans. Нет depth cap/top-k/квот. Каждое newly included body сканируется
   независимо от причины inclusion; порядок текста внутри source сохраняется.

## Что гарантируется — и что нет

Для допущенного seed и транзитивно включённого текста **каждая распознанная,
однозначно разрешённая и авторизованная explicit dependency** получает полный
адресованный extent; target score не может её удалить. Whole bodies, условия,
списки и код не режутся. Гарантия относится к supported source syntax и реальной
структуре документов, не к универсальному пониманию всех ссылок/требований.

Graph reachability не расширяет scope/authority/version. Каждый добавленный
source/span проходит native lineage/hash/catalog/live rechecks; одинаковые paths
разных versions не склеиваются. External/unavailable/excluded sources не
скачиваются и не подменяются похожими: остаются typed gaps. Unsupported syntax
явно ограничивает completeness; code/fenced link-like literals не являются edges.
Resolved edge считается satisfied только после полного extent и recheck.
При failed qualification — incomplete/refusal, не успешный partial answer.

Остаются **seed false negatives, неявные зависимости, недоступные источники и
ограничения syntax resolver**. Closed-world closure не доказывает полноту ответа
вне заданного корпуса. Пустые seeds не доказывают no-answer: нужен полный scan
и независимая проверка исходной задачи. Даже отсутствие graph gaps не является
semantic sufficiency.

## Отличие от прежнего subtree blowup и цена

Subtree выдаётся **только вследствие explicit source reference на section**,
не вследствие semantic admission любого parent. Но selected navigation body или
его ancestor с root links действительно может развернуть весь reachable corpus.
Это честный worst case, а не исключение, которое разрешено скрыть фильтром.
Role-based отсечение parent links убрано. Все extra tokens учитываются;
50% reduction gate может FAIL.50k emergency — whole-result stop, не trimming.
Ни одна ссылка не объявляется доказанно полезной только из-за inclusion.

## Smallest next diff и доказательство успеха

Отдельная structural/selection recipe, например
`explicit_addressed_section_closure_v3`: использовать existing parents/subtree
extents, anchor/definition/masking helpers и queue closure; изменить правила
expansion/typed gaps, не строить новый parser. Затем versioned dispatch/policy/
continuation binding и независимый evaluator closure oracle. Историческиеv1/v2
сохранить; repaired capability lifecycle не менять. Scorer inputs/prompt/model
math не менять; structural fingerprint и calibration provenance должны быть
новыми. Old policy/calibration SHA не выдавать за подтверждение новой структуры.

Сначала review конкретного syntax/extent контракта и source feasibility. Git/
SQLite — только кандидаты, ещё не dataset. Старые16cases — seen regression;
новый holdout выбирается/размечается **до scores**, с direct/linked/nested,
navigation, scope/version и no-answer obligations. Успех должен подтвердить
полные source-backed facts/conditions и>=50% экономии отдельно на независимом
holdout, без relabelling/tuning после результата. Сейчас datasets/runtime/tests
не создаются и не запускаются; число будущих calls не утверждено.

## Три тезиса для пользователя

1. **Было сломано:** система оставляла утверждение со ссылкой, но могла выбросить
   обязательные условия из адресованного раздела из-за низкой оценки relevance.
2. **Меняем:** после выбора текста сохраняем его явные зависимости полностью,
   включая детей адресованного раздела и ссылки из уже включённых ancestors.
3. **Успех надо доказать:** на новых заранее размеченных задачах не потерять
   обязательные факты и условия и при этом сократить source tokens минимум вдвое.
