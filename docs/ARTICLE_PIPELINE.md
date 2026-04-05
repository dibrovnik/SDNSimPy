# Пайплайн проведения экспериментов для научной статьи

Данный документ описывает пошаговый процесс воспроизведения экспериментов, оценки результатов и генерации графиков/таблиц для публикации статьи о методе приоритетной защищённой доставки.

## Этап 1: Подготовка окружения

Убедитесь, что все зависимости установлены. Работа с симулятором выполняется в headless-режиме (без GUI).

```bash
# Активируем виртуальное окружение
source .venv/bin/activate

# Устанавливаем базовые зависимости (если ещё не установлены)
pip install -r requirements-headless.txt

# Устанавливаем зависимости для визуализации и отчета
pip install matplotlib seaborn pandas numpy
```

*Примечание: для подавления генерации байт-кода Python и избежания конфликтов в кэше X11 рекомендуется использовать префиксы `PYTHONDONTWRITEBYTECODE=1 MPLCONFIGDIR=/tmp XDG_CACHE_HOME=/tmp`.*

---

## Этап 2: Запуск пакетных (Batch) симуляций

Для обеспечения статистической значимости данных результаты усредняются по 30 независимым случайным сидам. Все конфигурации лежат в `configs/experiments/`.

**Команда:**
```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m secure_delivery.cli run-batch \
  --config-dir configs/experiments/ \
  --output-root ./secure-delivery-results \
  --replicates 30 \
  --seed-step 1
```

**Ожидаемый результат:**
- Директория `./secure-delivery-results` будет заполнена подпапками для каждого сочетания `сценарий_и_нагрузка`.
- В корне директории `secure-delivery-results` появится единый агрегированный файл `batch_runs.csv` со всеми запусками.

---

## Этап 3: Аналитика и экспорт табличных данных для статьи

Для статьи требуются четкие числовые выкладки: дельты между сценариями, показатели дедлайнов и стоимость системы.

**Команда для генерации таблиц:**
```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m secure_delivery.cli export-article \
  --input-root ./secure-delivery-results \
  --output-dir ./article-tables
```

**Ожидаемый результат:**
В каталоге `./article-tables/` появятся готовые к публикации CSV выжимки:
- `table_critical_performance.csv` (Сравнение задержек критического трафика)
- `table_system_cost.csv` (Утилизация криптомодуля и канала)
- `table_scenario_deltas.csv` (Деградация или улучшение QoS при переходе от A к C)

---

## Этап 4: Визуализация данных (построение графиков)

Расширенный скрипт визуализации генерирует базовые и дополнительные графики по всем batch-CSV,
а также формирует markdown-отчет с актуальными числовыми результатами.

**Команда:**
```bash
# Даем скрипту права на исполнение
chmod +x scripts/visualize_results.py

# Запускаем скрипт 
PYTHONDONTWRITEBYTECODE=1 MPLCONFIGDIR=/tmp XDG_CACHE_HOME=/tmp .venv/bin/python scripts/visualize_results.py \
  --input ./secure-delivery-results/batch_runs.csv \
  --outdir ./article-plots \
  --input-root ./secure-delivery-results \
  --report-name experiment_report.md
```

**Ожидаемый результат:**
В директории `./article-plots/` будут созданы:
1. Базовые графики из `secure_delivery.plots.builder`.
2. Расширенный набор сравнительных графиков (QoS, ресурсы, очередь, policy, trade-off).
3. Файл `experiment_report.md` с автоматическим описанием эксперимента на основе актуальных данных.

Все этапы полностью независимы, и экспериментальные данные (`batch_runs.csv`) можно анализировать любым сторонним инструментом (R, SPSS, Excel) на ваше усмотрение.
