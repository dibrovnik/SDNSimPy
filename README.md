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

## Headless secure-delivery mode (Article Experiments Workflow)

The repository contains a separate research layer for secure prioritized inter-agent delivery experiments.
This layer is isolated from the legacy GUI simulator and is intended for reproducible CLI runs for the article.

### 0. Local virtual environment & setup

Create a project-local virtual environment and install the headless dependencies:

    python3 -m venv .venv
    .venv/bin/pip install -r requirements-headless.txt

### 1. Run full batch (Baseline)

Run the initial grid to test the environment (optional but recommended):

    PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m secure_delivery.cli run-batch --config-dir configs/experiments --output-root /tmp/secure-delivery-batch

### 2. Run the 30-seed series for the article (Statistical Significance)

Perform the main set of experiments with 30 replicates to ensure statistical validity:

    PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m secure_delivery.cli run-batch --config-dir configs/experiments --output-root /tmp/secure-delivery-batch-30x --replicates 30 --seed-step 1

### 3. Run expanded parameter sweep (Matrix Sweep)

Run the extended grid of parameters for deeper analysis:

    PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m secure_delivery.cli run-sweep --base-config-dir configs/experiments --matrix configs/sweeps/article_extended_grid.json --output-root /tmp/secure-delivery-expanded-sweep --replicates 1 --seed-step 1

### 4. Export article tables

Extract the aggregated and calculated results (including stddev, stderr, 95% CI) directly into CSVs for the article:

    PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m secure_delivery.cli export-article --input-root /tmp/secure-delivery-batch-30x --output-dir /tmp/secure-delivery-article-tables

### 5. Build plots

Generate visualizations in a headless environment:

    PYTHONDONTWRITEBYTECODE=1 MPLCONFIGDIR=/tmp XDG_CACHE_HOME=/tmp .venv/bin/python -m secure_delivery.cli build-plots --input-dir /tmp/secure-delivery-batch-30x --output-dir /tmp/secure-delivery-batch-30x-plots

### 6. Run validations and unit tests

To verify the integrity of the models, policies, and cryptographic components before or after the experiments:

    PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_sweep tests.test_scheduler tests.test_analysis tests.test_runner tests.test_behaviors tests.test_policy tests.test_crypto tests.test_replay

### Helper Scripts (Alternative to CLI)

You can also use the preset bash scripts in the `scripts/` directory:

    scripts/run_headless_batch.sh /tmp/secure-delivery-batch
    scripts/run_article_study_30x.sh /tmp/secure-delivery-batch-30x
    scripts/run_expanded_sweep.sh /tmp/secure-delivery-expanded-sweep configs/sweeps/article_extended_grid.json 5
    scripts/export_article_assets.sh /tmp/secure-delivery-batch-30x /tmp/secure-delivery-article-tables /tmp/secure-delivery-batch-plots
