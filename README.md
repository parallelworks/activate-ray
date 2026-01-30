# Ray Cluster Workflow

Deploy Ray clusters on HPC resources with ACTIVATE.

## Quick Start

1. Select your **compute resource**
2. Choose **Ray Version** (default: 2.40.0)
3. Enable **Submit to Job Scheduler** for multi-node clusters (SLURM/PBS)
4. Click **Run**

The workflow installs Ray, starts the cluster, and opens a session to the Ray Dashboard.

## Execution Modes

| Mode | Use Case |
|------|----------|
| **SSH Direct** | Single-node cluster on login node (scheduler disabled) |
| **SLURM** | Multi-node cluster across SLURM-allocated nodes |
| **PBS** | Multi-node cluster across PBS-allocated nodes |

## Connecting to Your Cluster

After the workflow completes, access the Ray Dashboard via the session link:

```
Ray Dashboard Session is ready!
  Proxy URL: https://platform.parallel.works/me/session/...
```

### Submit Jobs

From the dashboard or via CLI:

```bash
ray job submit --address=http://localhost:8265 -- python your_script.py
```

### Connect Programmatically

```python
import ray

ray.init("ray://localhost:10001")  # Via SSH tunnel or session proxy

@ray.remote
def compute(x):
    return x * 2

results = ray.get([compute.remote(i) for i in range(10)])
print(results)
```

## Local Development

Test the scripts locally without the full workflow.

**Requirements:** Python 3.9-3.12 (or uv will auto-install 3.12)

```bash
# Clone and setup
git clone https://github.com/parallelworks/activate-ray.git
cd activate-ray

# Set required env vars
export PW_PARENT_JOB_DIR=$(pwd)/test_job
export RAY_DIR=$(pwd)
mkdir -p $PW_PARENT_JOB_DIR

# Run setup (installs Ray)
bash scripts/setup.sh

# Run start (starts Ray cluster)
bash scripts/start.sh
```

Access dashboard at http://localhost:8265

## Documentation

- [Configuration Reference](docs/CONFIGURATION.md) - All input options and settings
- [Development Guide](docs/DEVELOPMENT.md) - Local testing and development

## References

- [Ray Documentation](https://docs.ray.io/)
- [Ray on SLURM](https://docs.ray.io/en/latest/cluster/vms/user-guides/community/slurm.html)
- [ACTIVATE Documentation](https://parallelworks.com/docs)
