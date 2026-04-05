# Project Guidelines (SDNSimPy Secure Delivery)

## Architecture

Этот репозиторий содержит исходный `SDNSimPy` как архитектурный каркас для исследовательского стенда по теме приоритетной защищённой межагентной доставки.

- **Цель**: Моделирование защищённого шлюза-планировщика для сообщений классов `critical`, `control`, `telemetry`, `background` (вместо моделирования обычного SDN-контроллера).
- Полное ТЗ: [docs/TECHNICAL_SPEC.md](docs/TECHNICAL_SPEC.md)
- Стартовый контекст: [docs/AGENT_START_HERE.md](docs/AGENT_START_HERE.md)
- Карта адаптации (точки встраивания логики): [docs/ADAPTATION_MAP.md](docs/ADAPTATION_MAP.md)
- Математическая модель: [docs/MATH_MODEL.md](docs/MATH_MODEL.md)

## Code Style & Conventions

- Не делать тотальный big-bang rewrite.
- Не смешивать визуализацию и вычислительную логику (сохранять `SDNSimPy` GUI, но изолировать новый исследовательский режим для `headless`-запуска).
- Не зашивать параметры в код: использовать конфиги, манифесты запусков и сериализуемые модели.
- Политики приоритетов и профили защиты должны быть внешними и версионируемыми.
- **Источник истины** (по убыванию приоритета): Фактическая структура репозитория > `docs/TECHNICAL_SPEC.md` > `docs/ADAPTATION_MAP.md`.

## Build and Test

Используйте виртуальное окружение: `.venv/bin/python`
Рекомендуется использовать флаг: `PYTHONDONTWRITEBYTECODE=1` 
Для графиков в headless: `MPLCONFIGDIR=/tmp XDG_CACHE_HOME=/tmp`

**Юнит-тесты:**
`PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_sweep tests.test_scheduler tests.test_analysis tests.test_runner tests.test_behaviors tests.test_policy tests.test_crypto tests.test_replay`

**Ключевые workflow-команды** (см. исходники скриптов в `scripts/` для деталей):
- Одиночный прогон: `.venv/bin/python -m secure_delivery.cli run-experiment --config configs/experiments/scenario_c_normal.json --output-dir /tmp/secure-delivery-scenario-c-normal`
- Batch-серия для статьи (30 сидов): `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m secure_delivery.cli run-batch --config-dir configs/experiments --output-root /tmp/secure-delivery-batch-30x --replicates 30 --seed-step 1`
- Matrix Sweep: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m secure_delivery.cli run-sweep --base-config-dir configs/experiments --matrix configs/sweeps/article_extended_grid.json --output-root /tmp/secure-delivery-expanded-sweep --replicates 1 --seed-step 1`

Ссылки на детали проведения экспериментов и экспорта:
- [docs/EXPERIMENTS.md](docs/EXPERIMENTS.md)
- [docs/ARTICLE_EXPORT.md](docs/ARTICLE_EXPORT.md)
- [README.md](README.md#headless-secure-delivery-mode-article-experiments-workflow)
