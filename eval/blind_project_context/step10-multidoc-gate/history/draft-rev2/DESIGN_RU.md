# Многодокументный gate: draft для review, НЕ frozen и НЕ запускался

Agent-authored synthetic projects, не independent external dataset. Данные не
основаны на T01/PR/CONTRIBUTING и не доказывают перенос на реальный DocAtlas.
Четыре новых проекта, по 7 документов, по 4 вопроса: 16 всего. Calibration:
TideGauge и Loom; validation: Meridian и Cairn. Предметные проекты и исходники не
пересекаются, но структурные мотивы (процедура, исключение, ссылка) повторяются
намеренно. Это НЕ task-template-disjoint validation и не доказательство обобщения.
Каждый проект готовится целиком один раз через public preparation. В query нет
source_path: все шесть project-documents конкурируют в одном scope=project;
седьмой документ — module-only и никогда не разрешён в этих запросах.

## Контракт разметки

tasks.json задаёт дословные исходные вопросы и независимые исходные цитаты с
path/heading. direct — собственные тела с необходимыми фактами; structural —
нужные вводные/зависимости, не обязанные пройти semantic gate напрямую.
Rev2 добавляет optional_support и допустимый optional ancestor context: они не
обязательны и не false positives. Rationale: LABEL_REVIEW_REV2_RU.md.
Остальные непустые тела разрешённого корпуса — negatives. hard_negatives — особо опасные
или тематически близкие negatives; нельзя считать исторический пример текущим
правилом. Полные required obligation bodies должны быть доставлены, одних цитат
недостаточно; optional witnesses не становятся обязательными.
Никакие expected answer/labels не попадают в подготовленный project или service.
Все цитаты сверяются с authored files независимым простым ATX-инвентарём,
не production parser/scorer. Номера строк и hashes вычисляются из этих файлов,
но usefulness задаётся вручную до inference.

На каждый проект: три answerable questions и один no-answer. Русские вопросы к
английским docs и английские содержательные вопросы присутствуют в обоих splits;
это не переводы одного вопроса. Нет автоматического перевода/дополнительных lanes.
EXIT original-RU — эксперимент за пределами language contract его model card.
Если нужен translation arm, это отдельный reviewed/frozen recipe до inference.

Loom C-L2 и Cairn V-C2 явно требуют полный родительский раздел вместе с детьми.
Это блокирует замену subtree на безусловное own-only. Другие вопросы содержат
исключения под соседним заголовком без anchor, cross-document dependencies,
списки условий, scope introductions и конкурирующие архитектурные обзоры.
TideGauge operations intro и Meridian reservations intro имеют навигационные
anchors: обязательный intro может привести к лишнему closure; amplification
считается, не замалчивается. Overview также содержит навигационные ссылки.
Консервативное следование всем anchors может провалить hard-negative gate;
потеря условия либо сокрытие такого FAIL недопустимы. Решение этого риска открыто.

## До первого запуска

1. Родитель проверяет docs, факты, роли direct/structural и hard negatives.
2. Утверждает classifier/prompt/segmentation/overflow и structural recipe.
3. Дорабатывается public runner на основе V3: project-level documents, identity
   (path, heading/span), нет старого ограничения match_scores на один document.
4. Freeze manifest включает исходники, tasks, scope catalog, design, evaluator,
   runtime/model/tokenizer revisions+hashes, dtype, prompt, label-token handling,
   segmentation и policy fitting. Draft manifest сейчас только контроль целостности,
   не утверждение frozen_before_inference.
5. Calibration вызывается первой; policy замораживается до однократной validation.
   При FAIL факты/labels не исправляются ради PASS. Все попытки сохраняются.

## Acceptance, согласованное для этой серии

- 100% обязательных фактов, условий, исключений и полных required obligation bodies в
  конечном public packet; действительные refs/hash/spans/scope/version.
- 4/4 no-answer по всему набору пустые после полного успешного scan; ошибки,
  overflow и emergency не засчитываются как корректный пустой ответ.
- 0 module-only sources. 0 delivered hard-negative own bodies (дополнительно
  записать все прочие negative bodies и structural причины их добавления).
- На answerable задачах каждого split отдельно: минимум 50% сокращения суммарного
  source-text tokens относительно всего разрешённого корпуса для тех же запросов.
  Это экспериментальный критерий, НЕ runtime quota, НЕ top-k, НЕ продуктовый лимит.
  Показывать также каждый случай; aggregate не скрывает потери фактов.
- Полные source/DB/model-cache before/after read-only receipts; подготовка отдельно.
- Отдельно: direct/structural recall, hard-negative rate, delivered negative tokens,
  seed→closure и anchor amplification, wire/model-visible tokens, pairs, время,
  память, полный scan или явный failure. Все операции включены в counts.

Порог: использовать только calibration с заранее утверждённой fitting recipe;
closure-aware feasibility разрешён. Нет feasible policy — остановка, не подбор
на validation/T01. 16 synthetic cases не дают статистической гарантии.

## После локального gate

Обязательны отдельные реальные project gates, installed stdio и client fidelity.
T01 — diagnostic dev, не calibration. Default off; Terra/full L2 не запускаются
при targeted quality FAIL. 50000 остаётся только emergency stop.
