# ARTICLE_EXPORT

## Что брать в статью

На текущем этапе пакетный режим уже формирует минимально полезный набор таблиц и графиков.

## Основные таблицы

Использовать CSV из `export-article`:

- `table_critical_performance.csv`
  - доля своевременно доставленных `critical`
  - средняя задержка `critical`
  - `95% CI` для доли своевременно доставленных `critical`
  - `95% CI` для средней задержки `critical`
  - `p95` для `critical`
  - jitter `critical`
- `table_system_cost.csv`
  - channel utilization
  - crypto utilization
  - average queue length
  - delivered/drop ratio для `background`
- `table_critical_components.csv`
  - mean `classification`
  - mean `crypto`
  - mean `queue`
  - mean `tx`
  - mean `ack`
- `table_scenario_deltas.csv`
  - разница `B-A`, `C-A`, `C-B`
  - дельта по `critical_deadline_met_ratio`
  - дельта по `critical_latency_mean_s`
  - относительное улучшение по задержке
  - цена улучшения для `background`

## Основные графики

Для одиночного прогона:

- `latency_distribution.png`
- `critical_latency_cdf.png`
- `deadline_met_ratio.png`
- `latency_components.png`
- `queue_timeseries.png`
- `throughput_by_class.png`
- `crypto_share.png`

Для batch-сравнения:

- `critical_latency_cdf_by_scenario.png`
- `critical_deadline_by_scenario.png`
- `critical_components_by_scenario.png`
- `useful_throughput_by_class_and_scenario.png`

SVG-версии тех же графиков сохраняются рядом с PNG в том же каталоге.

## Какие метрики использовать в тексте статьи

Основные:

- `critical_deadline_met_ratio`
- `critical_latency_mean_s`
- `critical_latency_p95_s`
- `critical_jitter_s`
- доверительные интервалы `95% CI` для `critical_deadline_met_ratio` и `critical_latency_mean_s`

Поясняющие:

- `critical_queue_time_mean_s`
- `critical_crypto_time_mean_s`
- `channel_utilization`
- `crypto_utilization`
- `background_delivered_ratio`
- `background_dropped_ratio`

## Логика интерпретации

Рекомендуемый порядок изложения:

1. Показать улучшение `critical` относительно A и B хотя бы для части режимов.
2. Отдельно разложить вклад `queue_time` и `crypto_time`.
3. Показать цену этого улучшения на `background`.
4. Отдельно отметить роль emergency policy в сценарии C:
в `emergency` через policy switch, в `overload` через старт в emergency-конфигурации.

## Примерные артефакты в репозитории

В репозитории должен лежать примерный набор CSV в каталоге `examples/results/`.

Полезные файлы:

- `sample_batch_runs.csv`
- `sample_scenario_comparison.csv`
- `sample_critical_deadline_comparison.csv`
- `sample_critical_latency_comparison.csv`
- `sample_table_critical_performance.csv`
- `sample_table_system_cost.csv`
- `sample_table_critical_components.csv`
- `sample_table_scenario_deltas.csv`
- `sample_scenario_c_normal_messages.csv`

## Команды

Получить batch:

```bash
.venv/bin/python -m secure_delivery.cli run-batch \
  --config-dir configs/experiments \
  --output-root /tmp/secure-delivery-batch
```

Получить полноценную seed-series для статьи:

```bash
.venv/bin/python -m secure_delivery.cli run-batch \
  --config-dir configs/experiments \
  --output-root /tmp/secure-delivery-batch-30x \
  --replicates 30 \
  --seed-step 1
```

Получить article tables:

```bash
.venv/bin/python -m secure_delivery.cli export-article \
  --input-root /tmp/secure-delivery-batch \
  --output-dir /tmp/secure-delivery-article-tables
```

Получить plots:

```bash
MPLCONFIGDIR=/tmp XDG_CACHE_HOME=/tmp .venv/bin/python -m secure_delivery.cli build-plots \
  --input-dir /tmp/secure-delivery-batch \
  --output-dir /tmp/secure-delivery-batch-plots
```
