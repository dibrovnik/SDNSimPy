#!/usr/bin/env bash

# Скрипт для полностью автоматического запуска пайплайна экспериментов.
# Предполагается, что все зависимости (включая matplotlib, seaborn, pandas, web3) уже установлены,
# а виртуальное окружение активировано (либо используется системный python с нужными пакетами).

set -euo pipefail

# Директории вывода (можно переопределить через переменные окружения)
RESULTS_DIR="${RESULTS_DIR:-./secure-delivery-results}"
TABLES_DIR="${TABLES_DIR:-./article-tables}"
PLOTS_DIR="${PLOTS_DIR:-./article-plots}"
REPLICATES="${REPLICATES:-30}"
REPORT_NAME="${REPORT_NAME:-experiment_report.md}"
PYTHON_BIN="${PYTHON_BIN:-.venv/bin/python}"

if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "Ошибка: интерпретатор ${PYTHON_BIN} не найден или не исполняемый."
  echo "Создайте окружение и установите зависимости:"
  echo "  python3 -m venv .venv && .venv/bin/pip install -r requirements-headless.txt"
  exit 1
fi

echo "================================================================="
echo " Запуск автоматического пайплайна экспериментов (SDNSimPy)"
echo "================================================================="
echo "[1/3] Запуск пакетных (Batch) симуляций..."
echo "Количество сидов (replicates): ${REPLICATES}"
echo "Директория результатов: ${RESULTS_DIR}"

# Запуск batch симуляций с подавлением байткода
PYTHONDONTWRITEBYTECODE=1 "${PYTHON_BIN}" -m secure_delivery.cli run-batch \
  --config-dir configs/experiments/ \
  --output-root "${RESULTS_DIR}" \
  --replicates "${REPLICATES}" \
  --seed-step 1

echo "================================================================="
echo "[2/3] Агрегация метрик и экспорт таблиц для статьи..."
echo "Директория таблиц: ${TABLES_DIR}"

PYTHONDONTWRITEBYTECODE=1 "${PYTHON_BIN}" -m secure_delivery.cli export-article \
  --input-root "${RESULTS_DIR}" \
  --output-dir "${TABLES_DIR}"

echo "================================================================="
echo "[3/3] Визуализация результатов (генерация графиков)..."
echo "Директория графиков: ${PLOTS_DIR}"

# Подавление конфликтов кеша для matplotlib в headless среде
PYTHONDONTWRITEBYTECODE=1 MPLCONFIGDIR=/tmp XDG_CACHE_HOME=/tmp "${PYTHON_BIN}" scripts/visualize_results.py \
  --input "${RESULTS_DIR}/batch_runs.csv" \
  --outdir "${PLOTS_DIR}" \
  --input-root "${RESULTS_DIR}" \
  --report-name "${REPORT_NAME}"

echo "================================================================="
echo "Пайплайн успешно завершен!"
echo " • Сырые данные:    ${RESULTS_DIR}/batch_runs.csv"
echo " • Таблицы (CSV):   ${TABLES_DIR}/"
echo " • Графики (PNG):   ${PLOTS_DIR}/"
echo " • Отчет (MD):      ${PLOTS_DIR}/${REPORT_NAME}"
echo "================================================================="
