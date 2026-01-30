# Ray Cluster Workflow

A Parallel Works ACTIVATE workflow for starting Ray clusters on HPC resources and submitting distributed computing jobs.

## Overview

This workflow deploys a Ray cluster on HPC compute resources, supporting:
- **SSH Direct Mode**: Single-node Ray cluster on login/head nodes
- **SLURM**: Multi-node Ray cluster across SLURM-allocated nodes
- **PBS**: Multi-node Ray cluster across PBS-allocated nodes

Once the cluster is running, you can submit Ray jobs for distributed computing, machine learning, and data processing workloads.

## Features

- **Multi-Mode Deployment**: SSH direct, SLURM, or PBS scheduler support
- **Fast Installation**: Uses `uv` package manager for rapid Ray installation (with pip fallback)
- **Auto-Detection**: Automatically detects SLURM/PBS environments and configures head/worker nodes
- **Dashboard Access**: Ray dashboard for monitoring cluster health and job progress
- **Job Submission**: Submit jobs via `ray job submit` or directly connect with `ray.init()`
- **Resource Configuration**: Configure CPUs, GPUs, and memory per node
- **Local Testing**: Full local testing support without ACTIVATE platform

## Quick Start

### On ACTIVATE Platform

1. Navigate to this workflow in ACTIVATE
2. Select your compute resource
3. Configure Ray settings (version, resources)
4. Choose execution mode:
   - Disable "Submit via Scheduler" for single-node SSH mode
   - Enable for multi-node SLURM/PBS clusters
5. (Optional) Provide a Ray job script in the editor
6. Click **Run**

### Local Testing

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies with uv
uv sync                      # Install base dependencies
uv sync --extra ray          # Install with Ray for local testing
uv sync --extra dev          # Install with dev/test dependencies
uv sync --all-extras         # Install everything

# load the venv to run the command
source .venv/bin/activate

# Start a local Ray cluster
python tools/ray_local.py start

# Run example scripts
python tools/ray_local.py run-examples

# Submit a job
python tools/ray_local.py submit examples/hello_ray.py

# Stop the cluster
python tools/ray_local.py stop
```

### Test the Workflow Locally

```bash
# Dry-run the workflow (see what would execute)
./tools/run_local.sh --dry-run

# Run workflow locally (will install Ray in temp directory)
./tools/run_local.sh --keep-work-dir

# Verbose output
./tools/run_local.sh -v
```

## Configuration Options

### Ray Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| **Ray Version** | Ray version to install | 2.9.0 |
| **Ray Port** | Head node GCS port | 6379 |
| **Dashboard Port** | Web dashboard port | 8265 |
| **CPUs per Node** | CPU allocation (0 = auto) | 0 |
| **GPUs per Node** | GPU allocation (0 = auto) | 0 |

### User Job Script

The **Ray Job Script** editor lets you provide a Python script that will be executed on the cluster after startup. Example:

```python
import ray

ray.init()

@ray.remote
def compute(x):
    return x * 2

futures = [compute.remote(i) for i in range(10)]
results = ray.get(futures)
print(f"Results: {results}")
```

Leave empty to just start the cluster without running a job.

### SLURM Settings

| Parameter | Description | Default |
|-----------|-------------|---------|
| **Account** | SLURM account | (optional) |
| **Partition** | Compute partition | (optional) |
| **QoS** | Quality of Service | (optional) |
| **Walltime** | Job duration | 04:00:00 |
| **Nodes** | Number of nodes | 2 |
| **CPUs per Task** | CPUs per task | 4 |
| **GPUs (gres)** | GPU request | (optional) |
| **Memory** | Memory per node | (optional) |

### PBS Settings

| Parameter | Description | Default |
|-----------|-------------|---------|
| **Account** | PBS account | (optional) |
| **Queue** | Job queue | (optional) |
| **Walltime** | Job duration | 04:00:00 |
| **Select** | Resource selection | (optional) |

## Directory Structure

```
activate-ray/
├── README.md               # This file
├── PLAN.md                 # Implementation plan
├── workflow.yaml           # Main ACTIVATE workflow
├── requirements.txt        # Python dependencies
│
├── scripts/                # Cluster management scripts
│   ├── setup_ray.sh        # Ray installation (with uv)
│   ├── start_ray_head.sh   # Head node startup
│   ├── start_ray_worker.sh # Worker node startup
│   ├── start_ray_cluster_slurm.sh  # SLURM multi-node
│   ├── start_ray_cluster_pbs.sh    # PBS multi-node
│   ├── shutdown_ray.sh     # Cluster shutdown
│   └── submit_ray_job.sh   # Job submission helper
│
├── examples/               # Example Ray jobs
│   ├── hello_ray.py        # Simple verification script
│   ├── distributed_compute.py  # Distributed computing demo
│   └── gpu_workload.py     # GPU workload example
│
├── tools/                  # Development tools
│   ├── workflow_runner.py  # Local workflow execution
│   ├── run_local.sh        # Convenience wrapper
│   ├── ray_local.py        # Local Ray cluster manager
│   ├── ray_submit.py       # Job submission tool
│   └── run_tests.sh        # Test runner
│
└── tests/                  # Test suite
    ├── conftest.py         # Pytest fixtures
    ├── test_workflow_runner.py
    └── test_integration.py
```

## Local Development

### Managing Local Ray Clusters

```bash
# Start a local Ray cluster
uv run python tools/ray_local.py start

# Start with specific resources
uv run python tools/ray_local.py start --num-cpus 4 --num-gpus 0

# Check cluster status
uv run python tools/ray_local.py status

# Run example scripts
uv run python tools/ray_local.py run-examples

# Submit a job
uv run python tools/ray_local.py submit examples/hello_ray.py

# Run a script directly
uv run python tools/ray_local.py run examples/hello_ray.py

# Stop the cluster
uv run python tools/ray_local.py stop
```

### Submitting Jobs to Remote Clusters

```bash
# Submit to local cluster
uv run python tools/ray_submit.py examples/hello_ray.py

# Submit via SSH tunnel to remote cluster
uv run python tools/ray_submit.py examples/hello_ray.py \
    --tunnel user@hpc-cluster \
    --remote-host compute-node-1

# List jobs
uv run python tools/ray_submit.py --list

# Get job logs
uv run python tools/ray_submit.py --logs raysubmit_abc123
```

### Running Tests

```bash
# Run all tests with uv
uv run pytest

# Unit tests only
uv run pytest tests/test_workflow_runner.py

# Integration tests only
uv run pytest tests/test_integration.py

# With coverage
uv run pytest --cov=tools --cov-report=term-missing
```

## Connecting to Running Clusters

After the workflow starts your Ray cluster, you'll see connection information:

```
==============================================
  Ray Cluster Connection Information
==============================================
RAY_HEAD_IP=10.0.0.100
RAY_ADDRESS=ray://10.0.0.100:10001
DASHBOARD_URL=http://10.0.0.100:8265

To connect from your local machine:
1. Set up SSH tunnel:
   ssh -L 8265:10.0.0.100:8265 -L 10001:10.0.0.100:10001 user@cluster

2. Access dashboard: http://localhost:8265

3. Submit jobs:
   ray job submit --address=http://localhost:8265 -- python your_script.py
```

### Connecting Programmatically

```python
import ray

# Connect to cluster via Ray client
ray.init("ray://localhost:10001")  # After setting up SSH tunnel

# Or connect directly if on the same network
ray.init("ray://10.0.0.100:10001")

# Check cluster resources
print(ray.cluster_resources())

# Run distributed tasks
@ray.remote
def task(x):
    return x * 2

results = ray.get([task.remote(i) for i in range(10)])
```

## Example Output

### Cluster Startup

```
==============================================
  Starting Ray Cluster
==============================================
Head Node:    node001
Head Node IP: 10.0.0.100
Total Nodes:  4

Starting Ray HEAD on node001...
Starting Ray WORKER on node002...
Starting Ray WORKER on node003...
Starting Ray WORKER on node004...

Cluster Status:
======== Autoscaler status ========
Node status
---------------------------------------------------------------
Alive nodes: 4

Resources
---------------------------------------------------------------
Usage: 0.0/64.0 CPU, 0.0/8.0 GPU, 0.0/128.0 GiB memory

==============================================
  Ray Cluster Ready
==============================================
```

### Example Job Output

```
==================================================
  Hello Ray - Cluster Verification
==================================================

Connecting to Ray cluster: auto
Successfully connected to Ray cluster!

--------------------------------------------------
  Cluster Resources
--------------------------------------------------
  CPU: 64.0
  GPU: 8.0
  memory: 137438953472.0
  node:10.0.0.100: 1.0
  node:10.0.0.101: 1.0
  node:10.0.0.102: 1.0
  node:10.0.0.103: 1.0

--------------------------------------------------
  Running Distributed Tasks
--------------------------------------------------
Submitting 10 tasks...
  Task 0: hostname=node001, pid=12345
  Task 1: hostname=node002, pid=12346
  ...

==================================================
  Hello Ray completed successfully!
==================================================
```

## Troubleshooting

### Ray installation fails
- Ensure Python 3.8+ is available on the remote system
- Check network connectivity for package downloads
- Try setting `USE_UV=false` to use pip instead of uv

### Workers don't connect
- Verify network connectivity between nodes
- Check firewall rules allow Ray ports (6379, 8265, 10001)
- Ensure all nodes can resolve each other's hostnames

### Dashboard not accessible
- Set up SSH tunnel: `ssh -L 8265:HEAD_IP:8265 user@cluster`
- Verify dashboard port isn't blocked by firewall
- Check that dashboard-host is set to `0.0.0.0`

### SLURM/PBS job fails
- Check scheduler logs: `squeue -u $USER` or `qstat -u $USER`
- Verify account/partition settings are valid
- Ensure walltime is sufficient for your workload

### Local testing issues
- Install uv: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Install dependencies: `uv sync --all-extras`
- Check Python version: requires 3.8+
- Use `--verbose` flag for detailed output

## How It Works

### SSH Direct Mode

1. Connects to remote host via SSH
2. Installs Ray in a virtual environment (using uv or pip)
3. Starts Ray head node with dashboard
4. Runs user job script (if provided)
5. Keeps cluster alive for interactive use

### SLURM/PBS Mode

1. Submits job to scheduler with requested resources
2. First allocated node becomes Ray head
3. Remaining nodes start as Ray workers
4. Workers connect to head node automatically
5. User job runs after cluster is ready
6. Cluster stays active until job walltime expires

## References

- [Ray Documentation](https://docs.ray.io/)
- [Ray Cluster Setup](https://docs.ray.io/en/latest/cluster/getting-started.html)
- [Ray on SLURM](https://docs.ray.io/en/latest/cluster/vms/user-guides/community/slurm.html)
- [Ray Job Submission](https://docs.ray.io/en/latest/cluster/running-applications/job-submission/index.html)
- [ACTIVATE Documentation](https://parallelworks.com/docs)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on contributing to this workflow.

## License

This workflow is provided as-is for educational and testing purposes.
