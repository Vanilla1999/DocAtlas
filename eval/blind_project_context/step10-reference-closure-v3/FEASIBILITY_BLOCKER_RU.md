# PRE-INFERENCE BLOCKED — этот holdout не может подтвердить принятый контракт

Это вывод по raw источникам, **не scored FAIL и не threshold simulation**.
Ни model calls, ни public runtime, ни замены корпуса ради PASS не выполнялись.
Исторический Qwen validation FAIL остаётся отдельным неизменённым результатом.

## Короткое доказательство для OTel

Для H-O1/H-O2/H-O3 требуются дочерние sections Baggage/Context/Propagators.
Если они не доставлены, required gate FAIL. Если они доставлены, принимаемый
контракт требует ancestor bodies, их реальные TOC links и транзитивные targets:

1. `context/api-propagators.md` root, lines10–39: TOC адресует все разделы этого
   документа. `baggage/api.md` root lines15–24 и `context/README.md` root17–24
   аналогично раскрывают свои документы, включая heading-only Operations.
2. `api-propagators.md:331` Global Propagators ссылается на Baggage Propagation.
   `baggage/api.md:188–202` ссылается обратно на Propagators sections и на
   `context/env-carriers.md`; ancestor Baggage root раскрывает Context Interaction.
3. `baggage/api.md:141` адресует **полный Context document**. Его Overview
   ссылается на отсутствующий в declared corpus `glossary.md#execution-unit`.
4. Status links из root bodies адресуют весь `document-status.md`; тот ссылается
   на отсутствующий `maturity-levels.md`. Propagators Distribution также ссылается
   на отсутствующий `overview.md#core-packages`, а Baggage — external W3C/RFC.

Следовательно, достижение required OTel bodies неизбежно влечёт unresolved
delivered dependencies. При **неизменных scope/no-fetch/complete-dependency
правилах** это `dependency_incomplete` refusal, не successful complete result.
Никакой score/tau не способен одновременно убрать эти links и сохранить все
required bodies/ancestor/reference obligations. Уже это исключает acceptance
всего нового holdout независимо от численного reduction и поведения второй темы.

Дополнительно all-reachable navigation заставляет включить все четыре allowed
OTel documents при удовлетворении этих questions. Это source-visible loss of
economy для OTel: полная выдача разрешённого текста, а не экономия. Aggregate
token ratio всего holdout сейчас НЕ вычислялся; численный невозможный50% для
всего двухдоменного split не утверждаем без такого расчёта. Refusal с0sources
вообще нельзя засчитывать как экономию successful answer.

Rust Embedded Book также содержит external API references и inline-code labels,
не поддерживаемые existing masking в reference definitions. Эти явно отмеченные
gaps дополнительно ограничивают closed dependency completeness; мы не добавляли
новый selective Markdown parser и не скрывали их.

## Scope и no-answer

`env-carriers.md` официально публичен и его raw bytes скачаны. Его module scope
— **граница этого finite experiment collection**, не upstream access prohibition.
Ссылка из project body не даёт разрешение расширить query scope. Аналогично
`src/start/semihosting.md` — настоящий публичный excluded chapter.

Unresolved links во всех full incoming-context documents — диагностический count.
Только links реально включённого closure текста становятся обязательствами.
Empty seed set не наследует unrelated gaps; может дать successful no-answer
только после complete scan и независимой no-answer проверки. Nonempty closure с
unresolved dependency даёт body-free error/hard_stop, reason `dependency_incomplete`,
scan_complete может быть true, но answer не complete. Это **не no-answer**.

## Итог

Материалы пригодны для code/source/oracle review, **не для freeze/inference**
этого holdout. Рекомендованный текущий бюджет public/model calls — **0**.
Не запускать даже seen fitting ради обхода установленного holdout blocker.
Не исключать TOC/ancestor links, не менять sources/questions/threshold и не
расширять scope молча. Возможное изменение product contract или source scope
требует отдельного явного решения родителя; никакой новый corpus не подобран.
