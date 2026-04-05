# Sample Results

Этот каталог содержит примерные CSV-результаты, полученные реальным batch-прогоном текущего headless-слоя `secure_delivery`.

Содержимое:

- `sample_batch_runs.csv` — агрегированный `runs.csv` по стартовой сетке A/B/C × {normal, high, overload, emergency};
- `sample_scenario_comparison.csv` — усреднённые batch-метрики по `scenario_family` и `load_profile`;
- `sample_critical_deadline_comparison.csv` — сравнение по `critical_deadline_met_ratio`;
- `sample_critical_latency_comparison.csv` — сравнение по `critical_latency_mean_s`;
- `sample_table_critical_performance.csv` — таблица для статьи по `critical`;
- `sample_table_system_cost.csv` — системные издержки;
- `sample_table_critical_components.csv` — разложение компонент задержки `critical`;
- `sample_table_scenario_deltas.csv` — дельты `B-A`, `C-A`, `C-B` для текста статьи;
- `sample_scenario_c_normal_messages.csv` — пример детального per-message результата для одного сценария.

Команды воспроизведения описаны в:

- [README.md](/Users/macbookair/.codex/worktrees/867a/SDNSimPy/README.md)
- [docs/EXPERIMENTS.md](/Users/macbookair/.codex/worktrees/867a/SDNSimPy/docs/EXPERIMENTS.md)
- [docs/ARTICLE_EXPORT.md](/Users/macbookair/.codex/worktrees/867a/SDNSimPy/docs/ARTICLE_EXPORT.md)
