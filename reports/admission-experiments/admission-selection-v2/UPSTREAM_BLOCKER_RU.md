# Остаточная потеря до ранжирования: numeric identity constraint

Новые public результаты, без повторного runtime:

- HOLD03:10полных upstream candidate records, selectablepool0, публично пусто во всех arms. В вопросе12часов и100градусов; документы содержат12,80,120,40, но не100.
- HOLD05:6candidate records, selectablepool0. Вопрос про1,3метра, source threshold1,4; queryvalue1,3 в source отсутствует.
- HOLD06:10candidate records, selectablepool1. Source sailing.md содержит1,4 и admitted. Найденный cargo.md прямо описывает незакреплённый груз, matros action и запрет gas cylinders, но не содержит1,4; originaltrace insufficient_visible_match, admissionfalse. Поэтому целый cargofacet не попадает к selector.
- Calibration CAL01/CAL02 также empty доselection: вопрос11/8 процентов, source threshold9. Это ограничивает представительность k-calibration: реальная достаточность k подтверждена для B1-delivered остатка, не для всех четырёх positive calibration задач.

Source-level sufficient explanation: `_policy_valid_body_blocks` в `docmancer/docs/domain/ordinary_body_context.py:232–237` берёт ВСЕ numeric literalterms исходногоquestion и требует их subset в одном bodyblock. Оба ordinary и B1candidate lanes используют этот generator. Для указанных неqualified bodywindows отсутствие numericliteral — достаточное условие отказа после более ранних guards.

**Не называем это observed branch receipt:** raw записывает low lexical qualification, null admission/emptiness и исходные bytes; конкретный numeric branch реконструирован по коду, другие более ранние причины могут также существовать. Missing hard-exact terms в raw=[]; это не canonical missing-exact denial.

Guard защищает прежние negative priority7/7-9 contracts; здесь он также мешает числовому сравнению и multi-document ответу, где только один facet содержит numericvalue. Исправлять его вслепую снятием numericcheck нельзя. Это отдельное решение о relevance/query-condition контракте и public positive+negative проверке; текущий эксперимент его не менял.

Практический приоритет: sourcepolicy (project/catalog/hash/currentgeneration/access) отделить от доказательства числового условия и owner/relation sufficiency. Для выбранныхcandidate semantics не требовать, чтобы каждый contributing fragment повторял все querynumbers; но не давать чужой numericcondition/fact authority. Ranker/pruner downstream не восстановит omittedpool.
