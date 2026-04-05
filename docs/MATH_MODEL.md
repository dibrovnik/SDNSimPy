# MATH_MODEL

## Назначение

Этот документ фиксирует математическую модель, которая реализована в headless-слое `secure_delivery/` поверх legacy-репозитория `SDNSimPy`.

## Топология

Минимальный стенд моделируется как ориентированный граф:

```text
G = (V, E)
V = {s_1, s_2, ..., s_n, g, r}
```

где:

- `s_i` — источники сообщений;
- `g` — защищённый шлюз-планировщик;
- `r` — получатель.

В текущей реализации конкуренция сосредоточена в `g`:

- криптографический ресурс моделируется через `SimPy PriorityResource`;
- выходной канал моделируется через `SimPy Resource`;
- межклассовые очереди моделируются отдельными класс-ориентированными буферами.

## Модель сообщения

Каждое сообщение задаётся структурой `SecureMessage`:

```text
m = <id, src, dst, c, L, t_gen, ddl, seq, prof>
```

Поля реализованы в [secure_delivery/models/message.py](/Users/macbookair/.codex/worktrees/867a/SDNSimPy/secure_delivery/models/message.py).

Основные параметры:

- `c` — класс сообщения: `critical`, `control`, `telemetry`, `background`;
- `L` — размер полезной нагрузки;
- `ddl` — дедлайн;
- `seq` — номер последовательности;
- `prof` — профиль защиты;
- `policy_version_id` — версия политики.

## Полный размер пакета

Полный размер вычисляется в `CryptoEngine`:

```text
L_full = L + h_sec + h_tag + h_aux
```

где:

- `h_sec` — размер заголовка безопасности;
- `h_tag` — размер тега аутентичности;
- `h_aux` — служебные поля профиля.

Реализация: [secure_delivery/crypto/engine.py](/Users/macbookair/.codex/worktrees/867a/SDNSimPy/secure_delivery/crypto/engine.py).

## Полная задержка

Полная задержка сообщения:

```text
T(m) = t_class(m) + t_crypto(m) + t_queue(m) + t_tx(m) + t_ack(m)
```

Компоненты реализованы так:

- `t_class` — `classification_delay_s` из конфига;
- `t_crypto` — вычисляется `CryptoEngine`;
- `t_queue` — время между `queue_enter_at` и `queue_leave_at`;
- `t_tx` — время обслуживания канала;
- `t_ack` — задержка ожидания подтверждения для профилей с `ack_required=true`.

Дедлайн проверяется условием:

```text
T(m) <= ddl(m)
```

Если условие нарушено, выставляется `deadline_missed=true`.

## Криптографическая стоимость

Базовая параметрическая модель:

```text
t_crypto(m) = alpha_a + beta_a * L + gamma_a_ver + gamma_a_rekey
```

где:

- `alpha_a` — постоянные накладные расходы;
- `beta_a` — стоимость обработки на байт;
- `gamma_a_ver` — стоимость проверки тега;
- `gamma_a_rekey` — стоимость обновления ключа.

Поддержанные режимы:

- `synthetic`
- `lookup_table`
- `measured_stub`

Дополнительно задаётся режим обслуживания crypto-stage:

- `uniform` — одинаковый приоритет доступа к крипторесурсу для всех классов;
- `class` — приоритет доступа зависит от класса сообщения.

В текущем комплекте сценариев:

- A и B используют `uniform`;
- C использует `class`.

Профили защиты задаются во внешнем JSON: [configs/policies/baseline_policies.json](/Users/macbookair/.codex/worktrees/867a/SDNSimPy/configs/policies/baseline_policies.json).

## Передача по каналу

Для канала с пропускной способностью `B` и задержкой распространения `d`:

```text
t_tx(m) = (8 * L_full(m)) / B + d
```

Если на канале задана вероятность потери `p`, то при событии потери:

- для классов с разрешённой повторной передачей запускается retry;
- иначе сообщение помечается как dropped.

## Политика обслуживания

Для каждого класса задаются:

- `priority`
- `weight`
- `max_retransmissions`
- `aggregation_enabled`
- `drop_allowed`
- `deadline_s`
- `security_profile`

Текущие дисциплины обслуживания:

- `fifo`
- `strict_priority`
- `drr`

`drr` используется как текущая реализация взвешенного обслуживания для сценария C.

## Политика из смарт-контракта

В стенде реализован имитационный backend политики:

```text
P^(k) = {(c, prio(c), w(c), prof(c), r_max(c), agg(c), drop(c), auth(c))}
```

Компоненты:

- `PolicyManager` — [secure_delivery/policy/manager.py](/Users/macbookair/.codex/worktrees/867a/SDNSimPy/secure_delivery/policy/manager.py)
- `FilePolicyBackend` — [secure_delivery/policy/backends.py](/Users/macbookair/.codex/worktrees/867a/SDNSimPy/secure_delivery/policy/backends.py)

`EvmPolicyBackend` полноценно внедрен. Шлюз динамически скачивает JSON-манифесты политик (включающие приоритизацию и профили защиты) из смарт-контракта EVM-совместимого блокчейна.
Для обеспечения автономности в условиях *ненадежной связи*:
1. Внедрен механизм *Exponential Backoff* (увеличение задержек при недоступности RPC).
2. Политика валидируется и локально кешируется. Если контракт стал полностью недоступен, агенты "выживают" на закэшированном профиле до восстановления сети.

## Anti-replay

Защита от повторов реализована через окно последовательностей `ReplayWindow`:

- хранится ограниченное окно последних sequence numbers;
- дубликаты и устаревшие номера отбрасываются;
- инциденты пишутся в `policy_events.csv`.

Реализация: [secure_delivery/crypto/replay.py](/Users/macbookair/.codex/worktrees/867a/SDNSimPy/secure_delivery/crypto/replay.py).

## Метрики

Сводные метрики формируются в [secure_delivery/metrics/collector.py](/Users/macbookair/.codex/worktrees/867a/SDNSimPy/secure_delivery/metrics/collector.py).

Поддержаны:

- средняя задержка, медиана, `p95`, `p99`;
- дедлайны, потери, retransmissions;
- jitter;
- queue length;
- channel/crypto utilization;
- mean component delays;
- доля `crypto_time` в полной задержке;
- доля security overhead в размере пакета;
- useful throughput и wire throughput по классам.
