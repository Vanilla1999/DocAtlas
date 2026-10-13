# Границы интерпретации40 вопросов

Эта серия измеряет выдачу документации по прежнему фиксированному oracle:

-24 within_budget: все обязательные оригинальные witness spans должны быть
  доставлены; отсутствие хотя бы одного span означает FAIL этой метрики.
-8 partial: проверяется только документированная часть. Наличие её цитат не
  доказывает полный ответ на вопрос или правильную обработку неизвестной части.
-8 unanswerable: прежний строгий критерий требует пустых sources. Непустые
  sources — FAIL этого критерия даже при false answer/edit authority. Но это
  само по себе не сгенерированная галлюцинация и не дефект source provenance.

Coverage здесь coordinate-based: полный alternative witness set, union spans,
не semantic entailment. Oracle включает прежние line ranges, включая headings/
examples/wording. Не заменять их более короткими цитатами ради повышения PASS.

Native означает конечный публичный DTO до дополнительной packing policy runner,
а НЕ все acquisition candidates. Отсутствие факта в native не позволяет автоматически
назначить причину retrieval/admission/selection. Промежуточные поля trace ограничены;
omission/gap должны оставаться unknown. Для факта, бывшего в native и потерянного
в packed, граница external pack доказана независимо от внутренних scores.

Read-only checks относятся к подтверждённо prepared isolated member index и
исходным project files. Source integrity проверяет принадлежность fixture root,
scope/version/authority/identity, exact source spans, continuation raw hashes.
Public content_sha256 — fingerprint, не сырой file SHA; raw source pinning проверено
в prepare snapshots. Эта серия не покрывает cold consent attacks, другие версии,
multi-module isolation, concurrency или production/client deployment.

Два SDK API fixes проверялись отдельной installed SDK серией. Эти40 запросов идут
через MCP project default без explicit expansion; они не заменяют проверку SDK
caps или expansion и не устанавливают их причинный эффект на retrieval quality.

Время включает trace и неизменённую assembly; peak RSS — общий resident process.
Сумма saved pretty-JSON tokens и packed source tokens — разные measures, не billing.
Оценки SDK character/4 и MCP max(o200k,UTF8/4) не смешиваются в одну метрику.

Старые V40 aggregates измеряли другие code/config: они полезны как история,
но новая серия40x1 без paired baseline не доказывает gain/регрессию именно API fixes.
Не выполняются дополнительные context calls, попытки починки или подбор вопросов
после открытия результатов. Исправления новых findings требуют отдельного этапа.
