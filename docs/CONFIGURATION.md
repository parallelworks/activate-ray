# Configuration Reference

Detailed configuration options for the Ray Cluster workflow.

## Ray Settings

| Parameter | Description | Default |
|-----------|-------------|---------|
| **Ray Version** | Ray version to install | 2.9.0 |
| **Dashboard Port** | Web dashboard port | 8265 |

Hidden/advanced options (modify in workflow.yaml):
- **Ray Port**: Head node GCS port (default: 6379)
- **CPUs per Node**: CPU allocation, 0 = auto-detect
- **GPUs per Node**: GPU allocation, 0 = auto-detect

## SLURM Settings

| Parameter | Description | Default |
|-----------|-------------|---------|
| **Account** | SLURM account (--account) | optional |
| **Partition** | Compute partition (--partition) | optional |
| **QoS** | Quality of Service (--qos) | optional |
| **Walltime** | Job duration (--time) | 04:00:00 |
| **Nodes** | Number of nodes (--nodes) | 2 |
| **CPUs per Task** | CPUs per task (--cpus-per-task) | 4 |
| **GPUs (gres)** | GPU request (--gres) | optional |
| **Additional Directives** | Extra #SBATCH lines | optional |

## PBS Settings

| Parameter | Description | Default |
|-----------|-------------|---------|
| **Account** | PBS account (-A) | optional |
| **Queue** | Job queue (-q) | optional |
| **Walltime** | Job duration (-l walltime=) | 04:00:00 |
| **Select** | Resource selection (-l select=) | 2:ncpus=4 |
| **Additional Directives** | Extra #PBS lines | optional |

## Environment Variables

These can be set in `inputs.sh` or passed to the scripts:

```bash
RAY_VERSION=2.9.0        # Ray version to install
DASHBOARD_PORT=8265      # Dashboard port
RAY_PORT=6379            # GCS port
NUM_CPUS=0               # CPUs per node (0=auto)
NUM_GPUS=0               # GPUs per node (0=auto)
DEBUG=true               # Enable debug output
```

## Troubleshooting

### Ray installation fails
- Ensure Python 3.8+ is available on the remote system
- Check network connectivity for package downloads
- The workflow uses `uv` for fast installation with automatic pip fallback

### Workers don't connect
- Verify network connectivity between nodes
- Check firewall rules allow Ray ports (6379, 8265, 10001)
- Ensure all nodes can resolve each other's hostnames

### Dashboard not accessible
- The workflow automatically sets up a session proxy
- Access via the ACTIVATE session link shown in output
- For manual access, set up SSH tunnel: `ssh -L 8265:HEAD_IP:8265 user@cluster`

### SLURM/PBS job fails
- Check scheduler logs: `squeue -u $USER` or `qstat -u $USER`
- Verify account/partition settings are valid
- Ensure walltime is sufficient for your workload
