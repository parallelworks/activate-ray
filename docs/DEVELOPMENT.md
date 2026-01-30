# Development Guide

Local development and testing documentation for the Ray Cluster workflow.

## Setup

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync --all-extras

# Activate the virtual environment
source .venv/bin/activate
```

## Local Ray Cluster

```bash
# Start a local Ray cluster
python tools/ray_local.py start

# Start with specific resources
python tools/ray_local.py start --num-cpus 4 --num-gpus 0

# Check cluster status
python tools/ray_local.py status

# Run example scripts
python tools/ray_local.py run-examples

# Submit a job
python tools/ray_local.py submit examples/hello_ray.py

# Stop the cluster
python tools/ray_local.py stop
```

## Testing the Workflow

```bash
# Dry-run the workflow (see what would execute)
./tools/run_local.sh --dry-run

# Run workflow locally
./tools/run_local.sh --keep-work-dir

# Verbose output
./tools/run_local.sh -v

# List available jobs
python tools/workflow_runner.py workflow.yaml --list-jobs

# Run specific job
python tools/workflow_runner.py workflow.yaml --job setup --dry-run
```

## Running Tests

```bash
# Run all tests
uv run pytest

# Unit tests only
uv run pytest tests/test_workflow_runner.py

# Integration tests only
uv run pytest tests/test_integration.py

# With coverage
uv run pytest --cov=tools --cov-report=term-missing
```

## Submitting to Remote Clusters

```bash
# Submit to local cluster
python tools/ray_submit.py examples/hello_ray.py

# Submit via SSH tunnel
python tools/ray_submit.py examples/hello_ray.py \
    --tunnel user@hpc-cluster \
    --remote-host compute-node-1

# List jobs
python tools/ray_submit.py --list

# Get job logs
python tools/ray_submit.py --logs raysubmit_abc123
```

## Directory Structure

```
activate-ray/
├── workflow.yaml           # Main ACTIVATE workflow
├── scripts/                # Cluster scripts
│   ├── setup.sh            # Controller setup (installs Ray)
│   └── start.sh            # Compute node startup
├── examples/               # Example Ray jobs
├── tools/                  # Development tools
│   ├── workflow_runner.py  # Local workflow execution
│   ├── ray_local.py        # Local cluster manager
│   └── ray_submit.py       # Job submission tool
├── tests/                  # Test suite
└── docs/                   # Documentation
```

## Connecting Programmatically

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
