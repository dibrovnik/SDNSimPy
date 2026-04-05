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

### Build plots from exported CSV

For headless environments it is recommended to set temporary cache directories for matplotlib:

    MPLCONFIGDIR=/tmp XDG_CACHE_HOME=/tmp .venv/bin/python -m secure_delivery.cli build-plots --input-dir /tmp/secure-delivery-scenario-c-normal --output-dir /tmp/secure-delivery-scenario-c-normal-plots
