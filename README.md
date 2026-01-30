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

**From the Ray head node** (same machine running Ray):
```bash
source ~/pw/activate-ray/ray_venv/bin/activate
cd ~/pw/activate-ray/examples

# Use absolute path for local files
ray job submit --address=http://localhost:8265 -- python $PWD/hello_ray.py
```

**From the cluster controller** (different machine than head node):
```bash
source ~/pw/activate-ray/ray_venv/bin/activate

# Use --working-dir to upload your code to Ray
ray job submit --address=http://localhost:8265 --working-dir . -- python hello_ray.py
```

**From your PW user workspace** (via tunnel on port 8888):
```bash
source ~/pw/activate-ray/ray_venv/bin/activate

# Submit job through the session tunnel (uploads code via --working-dir)
ray job submit --address=http://localhost:8888 --working-dir . -- python hello_ray.py
```

**From your local machine** (via SSH tunnel):
```bash
# Set up tunnel first
ssh -i ~/.ssh/pwcli -L 8888:localhost:8888 -o ProxyCommand="pw ssh --proxy-command %h" $USER@workspace

# Then submit jobs (uploads code via --working-dir)
ray job submit --address=http://localhost:8888 --working-dir . -- python hello_ray.py
```

### Installing Additional Packages

The default Ray installation includes only `ray[default]`. For GPU workloads with PyTorch or TensorFlow:

```bash
# Install PyTorch with CUDA support (uv is pre-installed by the workflow)
uv pip install --python ~/pw/activate-ray/ray_venv/bin/python torch

# Or install TensorFlow
uv pip install --python ~/pw/activate-ray/ray_venv/bin/python tensorflow
```

> **Note:** The `examples/gpu_workload.py` script works without PyTorch but will show "PyTorch not available" messages. Install PyTorch to enable GPU matrix computations in the example.

### Connect Programmatically

```python
import ray

# From cluster head node
ray.init("ray://localhost:10001")

# Or from workspace/local machine via tunnel
ray.init("ray://localhost:8888")

@ray.remote
def compute(x):
    return x * 2

results = ray.get([compute.remote(i) for i in range(10)])
print(results)
```

## Local Development

Test the scripts locally without the full workflow.

```bash
git clone https://github.com/parallelworks/activate-ray.git
cd activate-ray
bash scripts/setup.sh   # Installs Ray (uses uv to auto-install Python 3.12 if needed)
bash scripts/start.sh   # Starts Ray cluster
```

Access dashboard at http://localhost:8265

## Documentation

- [Configuration Reference](docs/CONFIGURATION.md) - All input options and settings
- [Development Guide](docs/DEVELOPMENT.md) - Local testing and development

## References

- [Ray Documentation](https://docs.ray.io/)
- [Ray on SLURM](https://docs.ray.io/en/latest/cluster/vms/user-guides/community/slurm.html)
- [ACTIVATE Documentation](https://parallelworks.com/docs)
