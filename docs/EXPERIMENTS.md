# EXPERIMENTS

## Набор сценариев

В репозитории подготовлен стартовый комплект конфигураций:

- `A`: FIFO + единый профиль защиты
- `B`: strict priority + единый профиль защиты
- `C`: differentiated security + DRR

Для каждого сценария заданы четыре режима нагрузки:

- `normal`
- `high`
- `overload`
- `emergency`

Конфиги лежат в [configs/experiments](/Users/macbookair/.codex/worktrees/867a/SDNSimPy/configs/experiments).

## Логика нагрузочных режимов

### `normal`

- умеренная частота `telemetry`;
- редкий `background`;
- без критических бурстов.

### `high`

- повышенные интенсивности `control` и `telemetry`;
- буфер и канал те же, что в `normal`;
- цель — проверить рост очередей без явной деградации канала.

### `overload`

- уменьшенный буфер;
- увеличенная вероятность потерь;
- повышенные частоты `telemetry/background`;
- критические bursts.
- в сценарии `C` используется emergency policy с самого начала прогона;
- telemetry aggregation в сценарии `C` ограничена меньшим batch size, чтобы длинные передачи реже блокировали `critical`.

### `emergency`

- bursts по `critical`;
- ускоренный `control`;
- в сценарии C включено переключение на emergency policy version.

## Команды запуска

Один прогон:

```bash
.venv/bin/python -m secure_delivery.cli run-experiment \
  --config configs/experiments/scenario_c_normal.json \
  --output-dir /tmp/secure-delivery-scenario-c-normal
```

Пакетный прогон:

```bash
.venv/bin/python -m secure_delivery.cli run-batch \
  --config-dir configs/experiments \
  --output-root /tmp/secure-delivery-batch
```

Пакетный прогон серии seed-replicates:

```bash
.venv/bin/python -m secure_delivery.cli run-batch \
  --config-dir configs/experiments \
  --output-root /tmp/secure-delivery-batch-30x \
  --replicates 30 \
  --seed-step 1
```

Расширенный sweep по bandwidth/buffer/loss:

```bash
.venv/bin/python -m secure_delivery.cli run-sweep \
  --base-config-dir configs/experiments \
  --matrix configs/sweeps/article_extended_grid.json \
  --output-root /tmp/secure-delivery-expanded-sweep \
  --replicates 5 \
  --seed-step 1
```

Сравнение по конкретной метрике:

```bash
.venv/bin/python -m secure_delivery.cli compare-metric \
  --input-root /tmp/secure-delivery-batch \
  --metric critical_deadline_met_ratio
```

Экспорт статейных таблиц:

```bash
.venv/bin/python -m secure_delivery.cli export-article \
  --input-root /tmp/secure-delivery-batch \
  --output-dir /tmp/secure-delivery-article-tables
```

Графики:

```bash
MPLCONFIGDIR=/tmp XDG_CACHE_HOME=/tmp .venv/bin/python -m secure_delivery.cli build-plots \
  --input-dir /tmp/secure-delivery-batch \
  --output-dir /tmp/secure-delivery-batch-plots
```

## Файлы результатов

Для каждого одиночного прогона формируются:

- `messages.csv`
- `runs.csv`
- `queue_timeseries.csv`
- `resource_usage.csv`
- `policy_events.csv`
- `manifest.json`

Для batch-режима дополнительно формируются агрегаты:

- `batch_runs.csv`
- `batch_messages.csv`
- `batch_queue_timeseries.csv`
- `batch_resource_usage.csv`
- `batch_policy_events.csv`
- `scenario_comparison.csv`
- `comparison_<metric>.csv`

Графики строятся в двух форматах:

- `png`
- `svg`

## Стартовые наблюдения на текущем наборе

На стартовой сетке уже доступны сравнения A/B/C.

Пример:

- по `critical_latency_mean_s` в режиме `normal` текущая реализация даёт:
  - `A`: `0.1013 s`
  - `B`: `0.0807 s`
  - `C`: `0.0744 s`
- по `critical_deadline_met_ratio` в режиме `normal`:
  - `A`: `0.8182`
  - `B`: `0.9091`
  - `C`: `0.9091`

Это означает, что уже на стартовом наборе есть режим, где сценарий C улучшает среднюю задержку `critical` относительно A и B.

## Ограничения текущего этапа

- По умолчанию batch-сетка запускается с одним зерном на конфиг.
- Для статьи подготовлена поддержка серий по `30` зерен на каждую точку через `--replicates 30`.
- Для более широкого анализа добавлен matrix-sweep по `bandwidth_bps`, `buffer_size`, `loss_probability`.
- `EvmPolicyBackend` пока не подключён к реальному локальному EVM-стенду.
