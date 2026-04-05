# SDNSimPy

1. Installing Python 3.8

Access the Python page and download version 3.8 (Windows x86-64 executable installer).

    https://www.python.org/downloads/release/python-380/
              
Once downloaded, run it and install it following the installation process.

2. Libraries installation

Press the Windows button and type CMD and run it as administrator.
    
Execute the following commands in order to install the necessary packages for this project:
    
    python -m pip install --upgrade pip
    pip install networkx
    pip install Image
    pip install scapy
    pip install matplotlib
    pip install ttkbootstrap

3. Running the program

Unzip the ZIP project file downloaded from GitHub 
    
Double click on the file "SDN_Simulator.py".

You can see the installation process in the following video:

    https://youtu.be/T5qDrh1dSyA

Execution examples:

    https://youtu.be/xUWRIovdtKA
    
    https://youtu.be/bnh35npcA-A

## Headless secure-delivery mode

The repository now also contains a separate research layer for secure prioritized inter-agent delivery experiments.
This layer is isolated from the legacy GUI simulator and is intended for reproducible CLI runs.

### Local virtual environment

Create a project-local virtual environment and install the headless dependencies:

    python3 -m venv .venv
    .venv/bin/pip install -r requirements-headless.txt

### Run one experiment

    .venv/bin/python -m secure_delivery.cli run-experiment --config configs/experiments/scenario_c_normal.json --output-dir /tmp/secure-delivery-scenario-c-normal

### Run a batch of experiments

    .venv/bin/python -m secure_delivery.cli run-batch --config-dir configs/experiments --output-root /tmp/secure-delivery-batch

### Run a seed series for article experiments

    .venv/bin/python -m secure_delivery.cli run-batch --config-dir configs/experiments --output-root /tmp/secure-delivery-batch-30x --replicates 30 --seed-step 1

### Run an expanded parameter sweep

    .venv/bin/python -m secure_delivery.cli run-sweep --base-config-dir configs/experiments --matrix configs/sweeps/article_extended_grid.json --output-root /tmp/secure-delivery-expanded-sweep --replicates 5 --seed-step 1

### Compare one metric across A/B/C

    .venv/bin/python -m secure_delivery.cli compare-metric --input-root /tmp/secure-delivery-batch --metric critical_deadline_met_ratio

`compare-metric` now also exports `stddev`, `stderr` and `95% CI` for seed-series runs.

### Export article tables

    .venv/bin/python -m secure_delivery.cli export-article --input-root /tmp/secure-delivery-batch --output-dir /tmp/secure-delivery-article-tables

The export includes:

- `table_critical_performance.csv`
- `table_system_cost.csv`
- `table_critical_components.csv`
- `table_scenario_deltas.csv`

### Build plots from exported CSV

For headless environments it is recommended to set temporary cache directories for matplotlib:

    MPLCONFIGDIR=/tmp XDG_CACHE_HOME=/tmp .venv/bin/python -m secure_delivery.cli build-plots --input-dir /tmp/secure-delivery-scenario-c-normal --output-dir /tmp/secure-delivery-scenario-c-normal-plots

Helper scripts:

    scripts/run_headless_batch.sh /tmp/secure-delivery-batch
    scripts/run_article_study_30x.sh /tmp/secure-delivery-batch-30x
    scripts/run_expanded_sweep.sh /tmp/secure-delivery-expanded-sweep configs/sweeps/article_extended_grid.json 5
    scripts/export_article_assets.sh /tmp/secure-delivery-batch /tmp/secure-delivery-article-tables /tmp/secure-delivery-batch-plots
