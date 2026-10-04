# Technical test-data correction, before second execution

Первый run 37232816139 / f0edb888: 172 PASS, 1 FAIL. Artifact 11313889328,
SHA-256 9c97b4bc3e4dbd46f806302c79d02ed1ea4be65954e837d0c8cab083799e1f37.

Failure: test_proposals_rank_search_text_before_materialization ожидал несколько
search chunks, но подготовил 3542-символьный текст; existing splitter законно
вернул один chunk. Assertion len(indexed)>1 остановил тест ДО вызова проверяемого
proposals и ДО spy rank. Это ошибка precondition нового development test, не
meaningful failure алгоритма. В том же run оба новых real-service owner tests
и все прежние read/scope/compact controls прошли. Target/corpus были SKIPPED.

Меняется только размер генерируемого текста этого одного нового теста:
400 коротких абзацев вместо 220, чтобы превысить существующий search chunk max
5000. Сам splitter, его параметры, source-owner алгоритм, frozen fixtures и все
product expectations неизменны. Assertion len(indexed)>1 не снят; проверки
исходного ranking/order/text сохраняются.

Review повторного diff: единственная test-data замена плюс manifest hash в
workflow. Новый SHA-256 test файла:
20c672aee2693bce6d0339d99b033fd3b72f4ade4e6140f6c28759320d6be7f1.
SHA-256 candidate 19ba718c15da60a2dcdff42f1a3796136d50b6fa3d554407bc0cfdc94daf90d3
и owner helper 8950a4c4cc7d7f5b5e4a42c96825edd5dd57e124bbd40c04ebac4c1b3448fe63
остаются теми же. Исходный failed run сохраняется. Это авторское review,
не независимая оценка. Разрешён технический повтор; N10 по-прежнему NOT_RUN.
