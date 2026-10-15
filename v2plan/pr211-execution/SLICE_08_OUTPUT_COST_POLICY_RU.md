# PR211: output cost policy без произвольного source-count ceiling

Основание: владелец отменил фиксированные output ceilings и поручил выполнять план минимизации стоимости без потери фактов и guards. Независимый review подтвердил, что прежние три источника ограничивали готовый DTO, а не чтение, scope или доступ к данным.

Удалён только source-count pass/fail ceiling в self-host и V2. Количество источников, canonical UTF-8 bytes и token estimate сохраняются как измерения. Acquisition/read/call/parser/time bounds неизменны. Новый числовой потолок не введён.

Все 25 исходных cases, вопросы, lookups, scopes, типы, 41 obligation ID и accepted witnesses побайтово эквивалентны HEAD до изменения. Сохранены semantic/lookup/original coverage floors, original minimum12, safety, identity, citation uniqueness и negative controls. Корпус5, evaluator2.6, protocol-lock6, result4 и acceptancev3 явно фиксируют policy migration; историческая тройка остаётся только diagnostic metadata.

Существующий cost/fidelity test использует четыре distinct contiguous README windows и >800 estimated tokens; должен сохранять все исходные факты. Удаление installer fact по-прежнему делает semantic_useful false. Duplicate evidence IDs продолжают отвергаться существующим citation_integrity, независимо от числа источников; nonempty answer по-прежнему нарушает context contract.

Независимый source review: APPROVE. AST/compile, corpus/obligations equality, protocol/corpus/acceptance/doc hashes, diagnostic roster и diff-check PASS. Runtime ещё ожидается; отмена числового cost gate не заявлена улучшением retrieval.
