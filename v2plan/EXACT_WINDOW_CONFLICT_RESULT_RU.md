# Exact-window сравнение действующих read путей

2026-10-03. Выполнено без изменения production, retrieval, compiler, thresholds,
budgets и guards. Скрипт: `exact_window_conflict_audit.py`.

## Метод и границы

80 frozen cases, 429 native captured candidates; archived source snapshots
проверены против frozen documents, DB read-only. Для каждого candidate берём
исходное окно и окна, рассмотренные actual typed projector (включая blocked
dispositions из diagnostics). 2159 distinct request/path/span windows.

На каждом **одинаковом snippet и absolute span** заново вызываем original-read,
unified research read, qualification каждого typed need и typed disposition.
Также выполняем actual typed/preferred/read proposal iterators на том же candidate
при whole-DTO budget 1500. Membership сравнивается по exact visible bytes внутри
source interval; повторяющиеся bytes дали бы UNKNOWN. Таких случаев: 0.

Это диагностический inventory, а не новый selection route. Не делаем OR разрешений.
Qualification evaluated по need scope, original-read по whole-question scope:
разницу scope сохраняем в rows, не называем любой disagreement ошибкой.
Annotation labels используются только после решений для наблюдения witnesses.

**Не измерены:** все rejected окна original-read, отсутствующие среди typed
альтернатив; полный batch prefit/final orchestrator; actual delivered packets,
claim recovery, false-admission rate и unseen validation. Membership означает
предложение, не окончательную выдачу. Исходные retrieval captures не изменены.

## Результаты

| Original-read | Хотя бы один typed need не blocked | Окон |
|---|---|---:|
| reject | нет | 1493 |
| reject | да | 586 |
| allow | да | 80 |
| allow | нет | 0 |

First original-read reasons на 586 disagreements:

- `no_local_topic_witness`: 570;
- `missing_local_demand`: 13;
- `verified_local_demand`: 3.

На 64 disagreement окнах присутствует полный annotated literal witness:
61 locality refusal, 3 verified_local_demand refusal. Это **не 64 claims** и
не независимый causal эффект: окна могут содержать один и тот же факт.

434 budget-fitting typed proposals не представлены ни preferred, ни read
proposal iterators. Их typed final fallback может предложить, но эти две
prefit ветки их не сохраняют. Это конкретная асимметрия proposal policy, не
доказательство, что все 434 теряются в полном pipeline с другими prefit routes.

Все 2159 windows source eligible. Native vs unified research read:
2079 reject/reject, 80 allow/allow, никаких allow/reject disagreements.
Qualification reason coupling можно убрать из измеренной isolated read boundary
без наблюдаемого изменения разрешений; relevance конфликт при этом остаётся.

## Какую обязанность можно удалить

**Подтверждённый isolated candidate:** proof-qualification reason whitelist
как владелец original-read разрешения. Его source/reference/literal/applicability
обязанности должны остаться в explicit guards, как в unified prototype.
Production removal пока не делаем: compiler/projection paths и исторические
49 supported claims полного native pipeline не проверены этим аудитом.

**Нельзя пока удалить:**

- locality veto просто потому, что typed route разрешил: weaker read relevance
  требует negatives и final-packet проверки;
- typed path: original-read отвергает часть окон с annotated useful facts;
- preferences целиком: они выполняют ordering и proposal preservation;
- повторные source/request/span проверки после clipping;
- claim support и proof flags: typed retrieval_only не является supported.

Целевое упрощение selection: preferences только сортируют уже одинаково
admitted окна; prefit/final используют одну proposal policy. Сейчас это не так.
Перенос ordering отдельно без общего read контракта ещё не определяет, какие
из 586 disagreements разрешать. Поэтому implementation migration остановлена
на проверенной матрице, а не замаскирована новым fallback.

## Проверка

- Инварианты: span length соответствует exact snippet; все windows source eligible;
  preferred membership включён в typed membership; read/unified outcomes равны.
- 66 focused tests passed; existing asyncio_mode warning.
- Это не полный regression и не тест нового admission predicate.

Артефакты: `artifacts/exact-window-conflicts/{rows,summary,provenance}.json`.
Rows содержат snippets, spans, need scope, qualification/disposition reasons,
membership и annotation witnesses. Provenance содержит capture и runner hashes.

```bash
PYTHONPATH=. /usr/bin/python3.12 v2plan/exact_window_conflict_audit.py --input /home/viadmin/.cache/docatlas-experiments/grounded-budget-20261003-06 --output v2plan/artifacts/exact-window-conflicts-NEW
```

Следующее решение — один общий read контракт с paired negatives на disagreement
окнах. Если его нельзя сформулировать без exceptions/threshold tuning, сохраняем
native pipeline и не продолжаем replacement. Новый compiler не нужен.
