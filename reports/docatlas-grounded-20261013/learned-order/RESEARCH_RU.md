# После неудачного пилота: исследования, не новые ручные правила

Дата поиска:2026-10-13. Прочитаны первичные abstract/full papers и официальный
репозиторий SetR. Никакая вторая модель не запускалась. Исследовательские
результаты ниже принадлежат авторам на их данных, не DocAtlas.
Primary HTML/official README сохранены lossless в `receipts.tar.xz`, включая
versioned URLs, resolved URLs и hashes в `research-sources/SOURCES.json`.

## Что реально показал наш пилот

Один learned pointwise reranker поднял ESLint список137→1 и доставил его, но
продолжение исходного witness поставил46-м, вне final packet. Poetry rule попало
в начало, code example опустился74→106. Это согласуется с риском independent
scoring of complementary windows. НЕ доказывает, что все rerankers бессмысленны,
что bigger model не поможет или что одна из статей обязательно исправит DocAtlas.

Оба main user facts теперь присутствуют, но полный старый witness всё ещё нет.
Это особенно важно: gold сохраняет example/placement, не только краткий ответ.
Не переписывать oracle и не смешивать strict witness delivery с semantic
sufficiency. Сгенерированных answers0; их correctness/citations не измерялись.

##1. SetR — learned выбор набора, а не отдельных окон

**Lee et al., ACL2025**, *Shifting from Ranking to Set Selection for Retrieval
Augmented Generation*.

- Peer-reviewed primary page: https://aclanthology.org/2025.acl-long.861/
- Paper: https://arxiv.org/html/2507.06838v2
- Official implementation: https://github.com/LGAI-Research/SetR
- DOI:10.18653/v1/2025.acl-long.861.

В abstract и §3.1–3.3: вместо независимого ranking модель рассматривает вопрос
и pool совместно, выявляет информационные требования и выбирает набор,
совместно покрывающий требования. Distilled Llama3.1-8B-Instruct, teacherGPT-4o;
IRI prompting/training, а не ручные keywords/bonuses. Эталон user task не
передаётся at inference: требования выводятся из исходного вопроса, не gold.

§4–5: multi-hop QA (HotpotQA,2Wiki,MuSiQue,MultiHopRAG), reranking/selection
обычно над top20, fixed-k baselines5. Авторы показывают collective coverage и
answer metrics, а не source-provenance guarantee или строгий full-DTO token cap.
Нельзя переносить numbers на technical docs,167–256 windows или наш бюджет.
Разные passage counts дополнительно ограничивают причинную интерпретацию gain.

Практическая проверка official README: описаны teacher-data generation, training,
inference; evaluation step — TBD. Ready downloadable trained checkpoint/точный
готовый deployment bundle в просмотренном README **не подтверждён**. Нельзя
выдать произвольный prompted8B model за воспроизведение trained SetR.

**Для нас:** наиболее прямое направление learned selection без ручных
semantic rules. Сначала подтвердить weights/license/context limits, понять
как полные source-native тексты167–256 окон помещаются в selector input и
как выбирается set при неизменённом full-public-DTO cap. Если cap потом снова
произвольно отсечёт дополнение — возвращается прежняя проблема.

##2. ParaSet / SetCE — set-level compatibility learning

**Song & Lee, preprint2026-07-07**, *Retrieving a Set, Not Independent Passages:
Set-Level Compatibility Learning for Efficient Set Exploration*.

- Primary full text: https://arxiv.org/html/2607.05712v1
- Abstract/version: https://arxiv.org/abs/2607.05712v1

§3: обучают scorer различать complete/compatible sets и incomplete/noisy sets;
training constructs additions/eliminations/interchanges of annotated gold sets.
ParaSet — attention over precomputed passage embeddings; SetCE — jointly
encoded query+set. Это обучение collective evidence usefulness, не синонимы и
не boosts отдельных окон. **Training gold** из отдельного train split допустим;
наши exposed40 gold не использовать для обучения/настройки будущего сравнения.

Важное несоответствие «без эвристик»: §3.2/AppendixA используют depth-limited
**beam search**, beam width и maximum set size — approximate search choices.
CE augmentation использует direct union; это не полностью free-of-heuristics
end-to-end решение, хотя semantic scorer learned. Не реализовывать этот поиск
под видом буквального исполнения запрета эвристик.

§4.2: CE/ListCE/SetCE pool20, ParaSet pool up to50; это не equal candidate-pool
доказательство всех сравнений. Table1 содержит и проигрыши на отдельных settings:
не заявлять безусловного превосходства. AppendixG — NVIDIA RTX3090/24GB; latency
не переносится на наш CPU. Статус preprint, ready checkpoints не подтверждены.

**Для нас:** хорошая постановка training objective, полезно для будущего trained
set scorer; не самый простой drop-in следующий запуск без собственного обучения.

##3. Late Chunking — контекст фрагмента без переписывания source text

**Günther et al.**, *Late Chunking: Contextual Chunk Embeddings Using Long-Context
Embedding Models* (arXiv initial2024, далее обновления).

- Primary paper: https://arxiv.org/abs/2409.04701
- Official implementation: https://github.com/jina-ai/late-chunking

Механизм: сначала transformer token representations для длинного исходного
document/macrochunk, затем pooling по native chunk spans. Small chunk vector
учитывает окружающий текст, без добавления synthetic summary в доказательство.
Это не «автоматически прицепить соседнее окно», не lexical adjacency bonus и
не learned set selection. Whole-source chars/spans должны остаться независимыми.

Ограничения: нужен long-context embedding backend/индексация и boundary cues;
наша первая потеря terminal budget, оба окна уже acquired. Улучшенные contextual
embeddings сами не гарантируют совместную доставку под конечным cap. Full docs
длиннее model context требуют macrochunks/overlap — дополнительные параметры,
не объявлять архитектуру буквально без boundary/search choices.

**Для нас:** перспективно против isolation of code/example windows, но более
широкое изменение retrieval/indexing, не минимальное исправление нашего terminal
selection FAIL. Не первый runtime эксперимент после этого pilot.

##4. Sufficient Context — отдельный проверяемый сигнал

**Joren et al., ICLR2025**, *Sufficient Context: A New Lens on Retrieval Augmented
Generation Systems*.

- Primary paper: https://arxiv.org/html/2411.06037v3
- Official publisher PDF:
  https://proceedings.iclr.cc/paper_files/paper/2025/file/33dffa2e3d2ab74a783d1a8c292f66d9-Paper-Conference.pdf
- Code: https://github.com/hljoren/sufficientcontext

§3: sufficiency оценивается по паре original question+whole final context, без
GT answer. Не равна topical relevance или наличие source hash. Autorater
93% accuracy оценён на115 human-labeled instances — не гарантия для DocAtlas.
§5: selective generation соединяет sufficiency+confidence через обученный
logistic model и calibrated threshold. Тот threshold не произвольный reranker
logit cutoff. Это отдельный supervised/calibration experiment, а не механизм
«пустые sources если score<0».

Ограничения: learned/model judgments могут ошибаться; article использует global
QA и допускает parametric knowledge в анализе correct answers при недостаточном
context. Для нашего source-grounded API unsupported parametric facts не должны
превращаться в source-authorized facts. Авторы не обещают provenance/consent.
FLAMe разрезает на1600 и any-sufficient chunk: это не автоматически подходящая
проверка distributed evidence. Не переносить эту policy на нас без эксперимента.

**Для нас:** оценивать final packet sufficiency независимо от hash/span integrity
и старой empty-source метрики; сначала собрать отдельную независимую annotation,
потом calibration на train/dev, затем frozen holdout. Не делать implicit authority.

## Рекомендация после чтения

Следующий обоснованный метод — **learned set selection по полному вопросу и
контексту кандидатов**, а не ещё один сортировщик независимых коротких окон.
Приоритет: воспроизводимый pretrained set selector (SetR-подобный), если
подтвердятся доступные weights, лицензия и лимиты; иначе явно сообщить, что
требуется отдельное обучение/инфраструктура, а не имитировать paper правилами.

До нового runtime зафиксировать:

1. Метод и artifacts, exact input representation из неизменённых source-native
   текстов. Никакого oracle/exposed40 training, никаких model-generated источников.
2. Выбор source IDs/span-preserving subset, независимую validation каждого ID.
   Невалидные/generated IDs — ошибка, не evidence, не тихий fallback.
3. Budget учитывает полный публичный DTO; модель не может отменять cap/правила
   access/consent/version. Не отрезать selected set с потерей обязательных фактов
   и не объявлять oversized context PASS.
4. Equal admitted pool, equal final cap, separate inference cost/input budget.
   Frozen old metrics + отдельные independently annotated semantic metrics.
5. Открытые E01/P03 остаются development cases; fresh holdout нужен для
   generalization. Это не разрешение перестроить эталоны ради нового метода.

Не делать MMR/xQuAD, automatic-neighbor bonuses, score ratios, library-specific
boosts или score cutoffs в качестве обхода запрета эвристик. Не снимать budget.
Отдельная sufficiency модель/оценка требуется для negatives; set relevance не
доказывает, что система знает момент отказа от ответа.

Здесь заканчивается исследовательский этап. Новые models/training/evaluation
calls не запускались и улучшение set selection для DocAtlas не утверждается.
