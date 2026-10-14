# Atomic learned set selector — проект, NOT IMPLEMENTED

Цель: выбрать совместно полезный **целый набор исходных окон** при полном
конечном DTO budget12000. Не reranking permutation с последующим first-fit.
Opt-in internal policy; wire API/authority/access/gold неизменны.

## Вход и capability boundary

`SelectionRequest` — immutable:

- исходный `question`, без rewrite и добавленных diagnostic lookup queries;
- весь admitted/source-rechecked `candidate_pool` в фиксированном native order;
  для каждого: existing request-owned evidence ID, original full snippet,
  source/document/snippet hashes, char/line span (единица char offsets явно),
  identity/request generation, scope/version, existing authority;
- pool manifest/hash и generation, code SHA, trained bundle/config revision;
- `dto_limit=12000`, действующая serializer/tokenizer identity;
- host-owned pure `price(ids)` capability: exact full proposed final DTO
  включая envelope/metadata/estimated_tokens/continuations; returns bytes,
  tokenizer tokens, ceil(UTF8 bytes/4), cost=max двух, DTO fingerprint.

Не передавать gold, witness IDs/ranges, expected answers или diagnostic packet.
Pool ID сам по себе не authority. Model видит source content как данные, не
команды; не имеет tools, записи, retrieval или доступа к другим namespaces.
Model bundle/input token budgets отличны от output DTO12000.
Source identity/hash проверяет host, scorer их не назначает.

`price` не создаёт/регистрирует resources, не меняет DB, не запускает retrieval
или source validator с побочными действиями. Для registration-dependent fields
нужен staging/exact deterministic preview и atomic commit. Нельзя использовать
сырую сумму text tokens/поштучных row costs как окончательный budget.

## Выход и принятие

`SelectionResult`:

- `status=selected | no_feasible_set | input_overflow | resource_limit | error`;
- **один** `selected_ids` set (stable emitted order определяется native order),
  только существующие IDs, без duplicates; не новый source text или metadata;
- diagnostics вне public protocol stdout/DTO budget: input/pool/model/policy
  hashes, seed/backend/dtype/hardware, input counts/tokens, scored/priced sets,
  learned scores доступных sets, exact pricing fingerprints, rejected-set
  counts/reasons, per-window selected/not-in-selected-set status, wall/CPU/RSS/
  GPU peaks. `not_in_selected_set` не означает individual semantic irrelevance.

Host проверяет membership, identities/generation, source validation без
restore/crop; строит **один полный** DTO и проверяет cost. Любой invalid ID,
altered provenance или пропавшее окно — reject **всего набора**, не silent repair.
Набор может быть superseded только другим явно scored/validated feasible set;
не молчаливым удалением части принятого набора. После окончательного выбора
`accepted_ids == emitted_ids`; поздняя mutation/over-budget → atomic failure,
не baseline fallback, не partial successful DTO. При staged registrations
failure не оставляет side effects. Error не объявлять semantic refusal.
Empty/no feasible set не является доказательством отсутствия ответа в корпусе.
Объяснения/learned scores не повышают authority, не доказывают полноту.

## Предварительно фиксируемая search policy для первого pilot

Это **проект** budget-aware адаптации paper, не inference reproduction.
После bundle gate сначала проверить поддержку режима, затем заморозить policy
manifest до открытия P03/E01 результатов. Если limits bundle несовместимы —
BLOCKED, а не tuning или уменьшение pool.

1. Learned ParaSet-compatible query–set score; singleton evaluation **всех N**.
2. Approximate beam width2, expansion каждого beam set каждым ещё не включённым
   ID из полного pool, exact dedupe; stable score ties по immutable ID order.
   Нет keyword/library boosts, MMR, neighbor/parent inclusion или ручного score.
3. Pricing **целых** proposed sets настоящим DTO builder, сохранить receipt.
   Выбирать только feasible complete sets; SetCE rerank10 лучших feasible
   proposed sets если он входит в подтверждённый bundle. Без SetCE bundle
   изменение arm/policy требует явного нового preflight, не скрытой подмены.
4. Search max depthN, scorer ceiling50000 unique sets/case, host wall600s,
   per-public-call120s; если реальные модели не укладываются — явный resource
   gate failure, не усечение candidate universe. Hardware RAM/VRAM ceilings
   задать после реального bundle preflight, не угадывать.
5. Full DTO cost может быть **не монотонен** из-за envelope/continuations/
   tokenizer. Pruning расширений over-budget prefixes допустим только с
   доказанным lower bound по настоящему builder. Без этого продолжать search
   при разрешённых compute limits; over-budget sets не выдавать/не crop.
6. Для каждого SetCE candidate считать полный actual model tokenizer input,
   не truncation. Unsupported model input означает зафиксированную ограниченность
   поиска/ошибку gate, не gold-guided исключение. Encoder overflow любого
   исходного окна блокирует full-pool claim; не незаметно резать текст.

Beam search — явное приближение: участие всех окон не означает перебор всех
`2^N` subsets или гарантию optimum/полноты. Set-level objective обучаемый;
approximate search и budget feasibility — отдельные технические ограничения,
не замена learned score ручной формулой. Не менять hyperparameters ради PASS.

## Integration acceptance

Только real documents → isolated SQLite → installed public MCP/SDK → final
complete DTO → independent frozen raw-span evaluation. Paired pool hashes и
state snapshots обязательны. Никаких новых unit/helper tests, mocked retrieval
или canned responses. Gate P03/E01 полностью PASS до одного full unchanged V40;
8 strict-empty отдельно, semantic refusal за пределами данного selector.
Verbose diagnostics можно выключить: off/on должны давать одинаковую выдачу,
права, sources и число продуктовых вызовов; trace omissions/errors явны.
