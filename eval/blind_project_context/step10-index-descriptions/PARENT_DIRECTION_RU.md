# Parent: решения эксперимента до запуска

2026-11-07. Владелец поручил реализацию через Astra Low, анализ и одно итоговое
review — родителю. Разрешение относится к первому небольшому development
эксперименту из STEP10_INDEX_PREPARATION_ANALYSIS_RU, не к Terra/Qwen reruns.

- Публичные ingestion и lexical dispatcher, настоящие storage/retrieval,
  isolated DB; embeddings/model downloads не нужны. Это отдельный baseline,
  не сравнение с Qwen full scan и не полноценный hybrid benchmark.
- Шесть top-level исходников Meridian; modules/private исключены.
- Четыре исходных вопроса V-M1..4 и 19 literal facts сохранены в queries.json.
  Это seen development; прежний validation FAIL сохраняется.
- limit5, budget4096, expand none; единицы выдачи/вопросы/критерии фиксированы
  до результатов. Полнота — все обязательные факты, экономия без полноты не PASS.
- Пояснения готовит отдельный Astra Low, которому доступны только шесть
  исходников, без queries/labels/results. Это harness generation, не production
  generator service. Exact weight revision и provider token usage недоступны.
- Язык пояснений — английский, как у источников. Русские вопросы сохраняются;
  проверяется именно contextual description, не добавляется отдельный переводчик.
- Description максимум512 UTF8 bytes. Добавлять после прежнего retrieval text,
  только если итог укладывается в прежний512 engineering-token limit. Иначе
  целиком пропускать с явным статусом, не менять исходные границы и prefix.
- Артефакт строго привязан к source path/hash и точному child span/hash,
  recipe/model/description hash. Все источники контекста — containing document.
  Неизвестный/устаревший артефакт отклоняется до публикации generation.
- Display evidence — оригинал. Метаданные описания не доказывают обязательный
  факт. Final packet оценивается отдельно от candidate retrieval; если runner
  видит только returned chunks, он не заявляет измерение внутреннего recall.
- Разрешён один scoped integration run и один frozen A/B run после готовности
  implementation/inputs. Повтор допускается только при конкретной новой причине;
  исходный FAIL/ERROR сохраняется. До готовности runtime не выполняется.
- Родитель проверяет исходные facts, diff и raw outputs в одном итоговом review.
  Промежуточные ответы исполнителям — указания, не quality PASS.

Ожидаемое ограничение заранее: чисто lexical поиск по англоязычным исходникам
может не отвечать на русские вопросы. Безусловного выигрыша не предполагаем.
Изменение input языка или retrieval backend потребует отдельного эксперимента.
Пустая выдача на русскоязычный V-M4 сама по себе не доказывает умение различать
answerable/no-answer: V-M1 тоже на русском, но имеет ответ. Их результаты нужно
показывать рядом. Два английских вопроса отдельно показывают эффект пояснений
без этой языковой границы; нельзя объявлять их новой заменой исходного набора.
