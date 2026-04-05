# AGENTS.md

## Назначение

Этот репозиторий содержит исходный `SDNSimPy`, который нужно использовать как архитектурный каркас для исследовательского стенда по теме приоритетной защищённой межагентной доставки.

Полное ТЗ находится в `docs/TECHNICAL_SPEC.md`.
Стартовый контекст по текущему состоянию репозитория находится в `docs/AGENT_START_HERE.md`.

## Обязательный порядок работы

1. Сначала проанализировать фактическую структуру репозитория, а не полагаться только на описание из статьи.
2. Перед крупными изменениями подготовить `docs/ADAPTATION_MAP.md` с точками встраивания новой логики.
3. Сохранять существующую функциональность `SDNSimPy`, если она не мешает новому режиму.
4. Изолировать новый исследовательский режим от GUI-логики и обеспечить пакетный `headless`-запуск.
5. Не зашивать параметры в код: использовать конфиги, манифесты запусков и сериализуемые модели.
6. Все ключевые решения и компромиссы документировать в `docs/`.

## Проверенные workflow-команды

- Одиночный headless-прогон:
  `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m secure_delivery.cli run-experiment --config configs/experiments/scenario_c_normal.json --output-dir /tmp/secure-delivery-scenario-c-normal`
- Полный batch по стартовой сетке:
  `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m secure_delivery.cli run-batch --config-dir configs/experiments --output-root /tmp/secure-delivery-batch`
- Серия для статьи на `30` сидов:
  `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m secure_delivery.cli run-batch --config-dir configs/experiments --output-root /tmp/secure-delivery-batch-30x --replicates 30 --seed-step 1`
- Расширенный matrix-sweep:
  `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m secure_delivery.cli run-sweep --base-config-dir configs/experiments --matrix configs/sweeps/article_extended_grid.json --output-root /tmp/secure-delivery-expanded-sweep --replicates 1 --seed-step 1`
- Экспорт статейных таблиц:
  `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m secure_delivery.cli export-article --input-root /tmp/secure-delivery-batch-30x --output-dir /tmp/secure-delivery-article-tables`
- Построение графиков в headless-среде:
  `PYTHONDONTWRITEBYTECODE=1 MPLCONFIGDIR=/tmp XDG_CACHE_HOME=/tmp .venv/bin/python -m secure_delivery.cli build-plots --input-dir /tmp/secure-delivery-batch-30x --output-dir /tmp/secure-delivery-batch-30x-plots`
- Полный набор текущих unit-тестов:
  `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_sweep tests.test_scheduler tests.test_analysis tests.test_runner tests.test_behaviors tests.test_policy tests.test_crypto tests.test_replay`

## Практические замечания

- Для прогонов и тестов предпочтительно использовать `PYTHONDONTWRITEBYTECODE=1`, чтобы не засорять дерево `__pycache__` и `*.pyc`.
- Для построения графиков в headless-окружении выставлять `MPLCONFIGDIR=/tmp` и `XDG_CACHE_HOME=/tmp`.
- Вспомогательные обёртки лежат в `scripts/`: `run_headless_batch.sh`, `run_article_study_30x.sh`, `run_expanded_sweep.sh`, `export_article_assets.sh`.

## Цель расширения

Нужно переориентировать исследовательский центр проекта:

- было: моделирование поведения SDN-контроллера и связанных служебных сообщений;
- должно стать: моделирование защищённого шлюза-планировщика для сообщений классов `critical`, `control`, `telemetry`, `background`.

## Минимальные обязательные артефакты

- `docs/ADAPTATION_MAP.md`
- `docs/MATH_MODEL.md`
- `docs/EXPERIMENTS.md`
- `docs/ARTICLE_EXPORT.md`
- набор конфигураций для сценариев A/B/C
- CLI для одиночных и пакетных запусков
- CSV-результаты и скрипты построения графиков
- тесты на политику, дедлайны, anti-replay, retransmission и воспроизводимость

## Ключевые ограничения

- Не делать тотальный big-bang rewrite.
- Не смешивать визуализацию и вычислительную логику.
- Не удалять старую функциональность без необходимости.
- Новые сущности вводить как отдельный исследовательский слой.
- Политики приоритетов и профили защиты должны быть внешними и версионируемыми.

## Источник истины

Если между текущим кодом и ожиданиями из статьи есть расхождения, приоритет такой:

1. фактическая структура репозитория;
2. `docs/TECHNICAL_SPEC.md`;
3. решения, зафиксированные в `docs/ADAPTATION_MAP.md`.
