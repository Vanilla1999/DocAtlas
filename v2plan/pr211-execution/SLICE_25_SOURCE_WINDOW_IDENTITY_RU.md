# Slice 25: одна физическая source window имеет одну идентичность

На `5d4767f` [Task33C](https://github.com/Vanilla1999/DocAtlas/actions/runs/37973183155/job/113964737595)
получил 51 PASS / 13 FAIL. Late declarations теперь найдены, включая все четыре
mutation targets и preserve file. Следующий реальный defect: одна строка,
найденная разными terms, давала stable identity collision.

Причина: query-dependent `match_type` и `confidence` копировались во вложенный
`source`. Stable ID описывал ту же строку, но сериализованный source identity и
evidence ID различались. Удалены только эти два query diagnostics из nested
source; верхние значения сохраняются. Source path, coordinates, text, symbols,
freshness и собственно identity validator не меняются.

Existing declaration test дополнен same-window transformation: exact symbol и
явный `sync gate` дают разные реальные match types и terms, но один evidence ID,
один полный packet source и валидный bound packet. Reused identity с изменённой
line2 по-прежнему обязан вызвать `stable_identity_collision`. Старые baseline,
8/16 ранних uses, no-grant, unlisted-file и read-byte guards сохранены.
Все29test names прежние.

Автор agent_fixtures_impl; root independent source review APPROVE. Проверены
actual candidate identity/display adapters и двухстрочный production diff.
Blobs source `6cc977084fcd321184046bf0f59ad6ee1b4fa973`,
test `d6208cefc0e62daa175be3d29670a258e7cefa71`.
Local AST/runtime **NOT RUN**; CI должен подтвердить actual positive и guards.
