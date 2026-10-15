# Независимый preflight V3 — до inference

Дата: 2026-10-12. Reviewer C. Прочитаны `CONTRACT_DECISION_RU.md`, `A_ADMISSION_CONTRACT_RU.md`, `B_CITATION_CONTRACT_RU.md`, `citation_adaptation.py`; дополнительно только статический product source и сохранённый V2 Q16 payload для понимания schema. Runtime/product/tests/models/host/adapter import не запускались. Case/oracle/исходный FREEZE не изменены; holdout labels в этом отчёте отсутствуют.

## Вердикт

**Узкий admission experiment допустим условно; citation arm в текущем adapter имеет pre-inference blocker.** Это разрешимость исследовательского дизайна, не PASS реализации, не новое разрешение runtime и не рекомендация default. Final product patch, runner, точный workload и raw outputs ещё требуют отдельного review. Одновременные full multifacet recall и strict relevance/empty-source контракт здесь не решены.

## A: контракт admission

Принятое решение координатора ограничивает V3 host-only opt-in `scalar_label_candidates_v3`, наследующим B1 retrieval-only/unassessed lane. Это согласуется с предложением A §§3–6 при следующих обязательных различиях:

- Live source/native/catalog/member/generation/window/structural-owner/hard-exact gates остаются независимыми обязательными условиями. Сопоставление scalar+label не даёт ни answer/edit authority, ни coverage credit, ни новой source-policy grant.
- Число вопроса может отличаться от числа источника. Совпадение буквенного label лишь синтаксическое: не доказывает общую единицу, измеряемый показатель, actor/relation или истинность условия. Incidental number/label остаётся риском ложной доставки; honest host refusal не превращает её в empty-source PASS.
- DefaultOff и старый B1 не должны получать новый numeric fallback. Сохранение старой ветки надо доказать по patch и final public output, не по имени режима.
- Non-numeric contributing facet не получает исключение из-за числа в другом документе. Полный составной ответ может остаться FAIL даже при восстановленной numeric части. Это заранее признанный blocker, не допустимость последующего изменения oracle или gate ради PASS.
- Structural owner не равен semantic actor/relation. Наследуемые B1 irrelevant nonempty failures остаются CURRENT_CONTRACT FAIL. Сохранение source-policy не означает сохранение precision всех semantic negatives.

**Уточнение текста до исполнения:** `CONTRACT_DECISION_RU.md:7` запрещает ranges/versions/signs/operator expressions в новом fallback, а A §3 явно сохраняет прежний B1 numeric route первым. Поэтому запрет следует читать как ограничение *добавочного scalar-label fallback*, не как обещание глобального запрета exact-supported ranges в любой старой lane. Если координатор намеревался ввести глобальный запрет, тексты расходятся и нужен новый checkpoint. Старый numeric exact route нельзя молча переписать под это прочтение.

A §6 перечисляет возможный docstring edit третьего product файла; принятое решение координатора §13 строже: владение лишь двумя указанными domain файлами. Расширение ownership не требуется и не подразумевается. A proposal status в начале файла исторический; authority на узкую реализацию даёт отдельное решение координатора, не сам proposal.

На момент чтения в working source видны capture нового режима и отдельный fallback с query/source spans. Это только контекст текущего preflight, **не final patch review** и не доказательство всех parser/structural boundary состояний. Особое внимание final review: maximal digit tokens; decimal comma; соседние signs/operators; headings/link masks; rows/list items; оригинальные pair spans; повторный admission на packing/projection bytes; отсутствие cross-document/global bypass.

## B: обязательный blocker binding

**B1 — неверная hash schema, блокирует citation arm.** `citation_adaptation.py:75` требует `item['content_sha256'] == SHA256(snippet UTF-8)`. `B_CITATION_CONTRACT_RU.md:23` заявляет то же как наблюдаемую V2 схему. Product задаёт другое:

- `docmancer/docs/application/_model_visible_docs_support.py:33–38` берёт digest из `_source_digest(item)`;
- `:42–50` digest вычисляется по canonical JSON envelope с полями `path`, `section`, `content`, `snippet`, `version`, а не по одному snippet;
- `model_visible_projection.py:744–750` проверяет этот envelope digest against snapshot bound source;
- V2 independent review уже разделял full-source SHA и envelope SHA.

Значит текущий adapter проверяет неподходящий operand и способен отклонить корректный public packet до host. Нельзя исправлять это переписыванием public hash/bound source или отключением проверки. Требуется offline/client проверка именно сохранённого envelope operand, с явно совпадающей canonical serialization; отдельно можно вычислить собственный `text_sha256`. Full raw-document hash и allowlist остаются отдельной проверкой. Исправить также описание B §23 и зафиксировать новую identity adapter/contract до host, затем статический re-review. Здесь adapter не исполнялся и конкретное число отклонённых packets не заявляется.

**B2 — неполный authority guard.** B §21 и общий критерий требуют отсутствия product answer/edit authority. `prepare_packet:47–48` проверяет `answer_supported` и `edit_ready`, но пропускает `answer_available`. Требуется проверять все три false; нельзя считать недостающую проверку доказанной только за счёт внешнего `integrity_errors=[]`. Это исправление reusable boundary, не изменение product.

## B: ограничения, которые не следует обходить ради результата

1. `prepare_packet:69–71` требует `public snippet == ref.text == raw_document[a:b]`. Это честный fail-closed узкий контракт, но public projection/packing может выдавать иной точный subspan/trimmed snippet. Q16/Q46 compatibility не доказана самим чтением B. Несовместимость означает PREPARE_BLOCKED/NOT_RUN, не пустой host ответ, не inference FAIL и не повод к незафиксированному alignment/search rescue после outputs. Если нужен новый exact subspan binding, отдельно зафиксировать контракт до соответствующих host attempts.
2. `payload['sources']` перебирается без нормализации; `sources=null`, как в сохранённых empty public results, не поддержан и может вызвать TypeError вне обещанного ValueError. Для текущего positive citation среза это не самостоятельный blocker, но reusable API не следует объявлять работающим для всех insufficient packets. Либо явно ограничить подготовку nonempty positives, либо до исполнения задокументировать/исправить пустую схему без source fabrication.
3. Adapter читает authority/path/line provenance, но не валидирует все эти operands сам; он опирается на внешний saved integrity audit. `integrity_errors=[]` — утверждение producer, а не самостоятельное доказательство. Runner должен сохранять проверяемые snapshot/state/catalog/document hashes и actual scope; reviewer независимо проверяет operand schema/parent lines/source class. Нельзя подавать произвольную user-created запись как validated public result.
4. `prepared_sha256` — защита от случайной модификации сохранённого packet, не подпись доверенного producer. Prepared и model messages сохраняются до host, hashes входят в workload freeze. Raw content bytes и transport receipt сохраняются независимо от extraction.
5. Coordinate extraction действительно не генерирует quote: выбирает непустой диапазон snippets, проверяет raw equality и сохраняет исходные claims. `EXTRACTED` не означает semantic entailment/complete/source relevance. Ссылку на не тот actor или на одну из нескольких нужных частей можно адресовать идеально точно и всё равно получить semantic FAIL. Нет оснований объявить устранёнными Q16 newline/Q46 Markdown ошибки до raw.
6. Новый prompt/claims schema — отдельное вмешательство. Сравнение base host и coordinate host на одном B1 packet показывает эффект *generator+client contract*, не улучшение того же старого generator и не product admission gain. Quotes extraction, generator schema validity, semantic completeness и original literal-quote metric — отдельные оси. Невалидный schema/offset — REJECTED без rescue/retry; отсутствие citations не зелёная completeness метрика.

## Workload preflight: условия координатору до первого inference

Предложенный узкий дизайн разумен: DefaultOff/B1/V3 public без selector изменений; base-host B1/V3 на frozen synthetic и known V2 numeric; citation pair на **одинаковом B1 public содержимом** Q16/Q46 и двух synthetic positives. До outputs необходимо отдельным workload manifest зафиксировать:

- все 7 новых + 2 старых priority inputs; actual family project binding, сохранённые relative paths/bytes и initial catalog/state;
- какие optional OtherAPI/Setext/compound/unrelated controls действительно включены; точные вопросы и bytes/paths (не повторять V2 переименование unrelated path незаметно);
- known HOLD03/HOLD05/HOLD06 как diagnostics, не новый независимый holdout и не calibration параметров;
- **две конкретные synthetic citation IDs до outputs**, без выбора по удачной public выдаче/host ответу и без раскрытия holdout labels A; если packet empty или несовместим с adapter, записать blocker, не заменить case;
- список public/host attempts, ceiling prepares/calls, fresh request receipts, model alias/transport/prompt hashes, pair reuse и cost accounting. Один общий public packet для citation pair не считать несколькими public вызовами; каждый новый host attempt считать отдельно;
- точные patch/adapter identities после исправлений, arms env и отсутствие активного experimental selector callback; DefaultOff не равен уже записанному B1 и старые generations не являются новым paired baseline;
- любые UNKNOWN/NOT_RUN/PREPARE_BLOCKED сохраняются в accounting; default parity относится только к реально выбранному срезу, не full40/50 regression.

Mini не обоснован без восстановленного нетривиального pool и отдельной ограниченной selection задачи. Включать его автоматически, retune holdout или запускать model matrix нельзя. Синтетические 7 cases — малый independent corpus, а не доказательство arbitrary numeric/multifacet/ACL/version способности. Public in-process MCP/SQLite evidence нельзя объявлять installed stdio/real client/production smoke.

## Итоговые gates

- **Admission design: CONDITIONALLY ACCEPTABLE** как ограниченный opt-in retrieval-only experiment с неизменным frozen oracle и честными negatives/multifacet FAIL.
- **Citation implementation: BLOCKED_PENDING_BINDING_FIX_AND_STATIC_REVIEW** (B1/B2 выше); source/schema совместимость целевых packets пока NOT_TESTED.
- **Workload: PENDING_EXACT_FREEZE**, включая fixed synthetic citation IDs и ceilings.
- **Default readiness/full multifacet/source-policy completeness: NOT_ESTABLISHED.** Ничего в этом review не обещает release/default, качество будущих ответов или PASS ещё не запущенных controls.

Исходный `review/FREEZE.json` и его 17 frozen file hashes не менялись. Этот новый review — последующий документ, не подмена pre-output corpus/oracle freeze. Final patch/output review ожидает отдельного запроса координатора.
