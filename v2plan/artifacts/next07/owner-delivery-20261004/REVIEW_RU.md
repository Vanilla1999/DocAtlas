# Review до запуска: owner-delivery

Reviewed code commit: 5f982a568ccfc8794062c7d35009190b213daa21.
Baseline: ea7eef380eb2b0a11b0216063939b2b8ae1773de.
Тип: авторское статическое ревью, НЕ независимый внешний аудит.
Native tests/target/corpus на момент этого review: NOT_RUN.

## Проверен diff

Production исходники, next07_grounded_public.py (включая prepared/scope/first_fit),
assessor/audit, ports и старые tests не изменены. Из существующего code изменён
только next07_grounded_candidate.py: импорт общего mapping, materialize_hit после
rank_rows, проверка canonical delivery spans вместо search spans.

AST-сверка с baseline: port, rank_rows, _source_state_witness и
_hidden_structural_dependency совпадают. После удаления двух объявленных
producer/consumer выражений proposals/read_decision совпадают с baseline по AST.
Добавленные helper и tests прошли Python syntax compilation; это не pytest PASS.

## Разобранные риски

1. Ranking не видит увеличенный текст. Score/order/count исходных hits сохраняются;
   retrieval_span и retrieval_content остаются в trace для сравнения.
2. Materialization не разрешает чтение сама. Затем вызываются прежние
   SourceReferenceContext.prepare, current catalog/hash/lifecycle, eligibility,
   exact/subject, condition mismatch, owner/dependency checks и handler validator.
3. Consumer не доверяет delivery_unit_kind/owner_spans metadata: допустимый span
   заново вычисляется из snapshot raw и existing structural_spans.
4. Полуоткрытые диапазоны не включают следующий sibling на точной границе. При
   пересечении нескольких секций возвращается один непрерывный исходный slice,
   не склейка и не поиск одинакового текста по заголовку.
5. Кэш хранит только parse bounds по (raw, document_id), максимум 16 entries;
   не хранит query approval. Новые IO/lookup/hydration не добавлены.
6. Длинная цитата может увеличить размер выдачи; 800/3 уже отменены пользователем.
   Это не обещание минимального semantic context. Старый guard произвольного
   среза заменён canonical owner unit, но сам dependency guard не ослаблен.
7. Parser parents — разделы до следующего heading, не общий semantic graph.
   Cross-section смысловая полнота не доказана. Missing exact/subject остаётся
   отдельным возможным отказом и не чинится расширением по догадке.

Блокирующих несогласованностей в объявленной границе при этом review не найдено.
Решение: разрешён предусмотренный native запуск; не объявляется acceptance PASS.

## Зафиксированные hashes проверенного кода

- v2plan/next07_owner_delivery.py SHA-256 8950a4c4cc7d7f5b5e4a42c96825edd5dd57e124bbd40c04ebac4c1b3448fe63
- v2plan/next07_grounded_candidate.py SHA-256 19ba718c15da60a2dcdff42f1a3796136d50b6fa3d554407bc0cfdc94daf90d3
- v2plan/test_next07_owner_delivery.py SHA-256 f937d6b5192595c1bfc1f8d0cc0a43f7c34412ce4036872328b452e76f6a4690

Следующий workflow запускает новые structural tests, прежние read/security
regression, закрытые wiring/scope/compact contracts, LeaseClient P1/P2/P3 и
80 N/C. Старые файлы expectations неизменны. N10 standalone / его test module
не запускаются. Frozen corpus не урезается. Старый N10 REJECTED остаётся;
этот review не разрешает общий rollout.
