# PR211: preserved lookup meaning в installed guidance tests

Дата: 2026-10-08. Base `3be9c34afa49dcf4278d2910ec29ed37c305225c`.
Изменён только один Assert в `tests/test_dictionary_exit_corpus_policy.py`.

Шесть template parameters в прежнем core CI 37824782946 падают на старом
prefix «A lookup does not establish coverage». Текущий canonical workflow
объявляет тот же запрет полной фразой «Lookup coverage does not transfer to the
original question». Это запрет приписывать исходному вопросу coverage отдельно
supplied lookup; он следует из explicit-question contract и остаётся обязательным.

Successor принимает ровно две полные эквивалентные фразы, обе с явным original
question. Удаление запрета, original-question target или отрицания не удовлетворяет
новой проверке. Это сильнее прежнего незавершённого prefix и не word-bag predicate.
Условия runtime admission/retrieval/coverage не меняются, producer wording также
не меняется этим test-only slice.

Все шесть прежних параметров, function/decorator и остальные семь assertions
в этом function сохранены: identity/placeholder, explicitly supplied lookups,
mutation target/authorization и три запрета inferred behavior. Все остальные
test bodies, sources, gold, manifests, thresholds и gates неизменны.

Source SHA256: `f768ee34f36af4593fe88eb1b07c4080a88898ebde3f56a7fac2e83a44774ac0`.
Independent review и фактический общий CI фиксируются отдельно; runtime NOT RUN.
