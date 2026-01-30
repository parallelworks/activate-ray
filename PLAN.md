# Ray Cluster Workflow Implementation Plan

## Overview

This document outlines the implementation plan for creating an ACTIVATE workflow that starts a Ray cluster on HPC resources (via SSH, SLURM, or PBS) and allows users to submit Ray jobs to it.

## Goals

1. **Start a Ray cluster** on compute resources (direct SSH or scheduler-allocated nodes)
2. **Support SLURM and PBS** job schedulers for multi-node Ray clusters
3. **Expose Ray cluster** for job submission (dashboard URL, job submission API)
4. **Allow users to submit Ray jobs** to the running cluster
5. **Handle cleanup** when the workflow completes

---

## Architecture

### Ray Cluster Components

```
┌─────────────────────────────────────────────────────────────────┐
│                    ACTIVATE Workflow                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐    ┌──────────────────────────────────────┐   │
│  │ Preprocessing │───▶│           Ray Head Node              │   │
│  │    Job        │    │  - Ray Dashboard (port 8265)         │   │
│  └──────────────┘    │  - Job Submission API                 │   │
│                       │  - GCS (Global Control Store)         │   │
│                       └──────────────┬───────────────────────┘   │
│                                      │                           │
│                       ┌──────────────┴───────────────────────┐   │
│                       │                                       │   │
│              ┌────────▼────────┐              ┌──────────────▼┐  │
│              │ Ray Worker Node │   ...        │ Ray Worker Node│  │
│              │  (Scheduler     │              │  (Scheduler    │  │
│              │   Compute Node) │              │   Compute Node)│  │
│              └─────────────────┘              └────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Execution Modes

| Mode | Description | Ray Head | Ray Workers |
|------|-------------|----------|-------------|
| **SSH Direct** | Single-node Ray cluster | Login node | Same node (local workers) |
| **SLURM** | Multi-node Ray cluster | First allocated node | All allocated nodes |
| **PBS** | Multi-node Ray cluster | First allocated node | All allocated nodes |

---

## Implementation Phases

### Phase 1: Core Workflow Structure

#### 1.1 Create New Workflow File

Create `workflow.yaml` (replacing the existing hello-world example) with:

- **Metadata**: Name, description, thumbnail for Ray cluster workflow
- **Input Definitions**: Resource selection, scheduler options, Ray configuration
- **Job Definitions**: Preprocessing, cluster startup, monitoring

#### 1.2 Define Workflow Inputs

| Input | Type | Description | Default |
|-------|------|-------------|---------|
| `resource` | compute-clusters | Target HPC resource | (autoselect) |
| `scheduler` | boolean | Use job scheduler | true |
| `ray_version` | string | Ray version to install | "2.9.0" |
| `num_cpus_per_node` | integer | CPUs per Ray worker | 4 |
| `num_gpus_per_node` | integer | GPUs per Ray worker | 0 |
| `ray_memory_gb` | integer | Memory per worker (GB) | 8 |
| `cluster_idle_timeout` | integer | Minutes before auto-shutdown | 60 |
| `dashboard_port` | integer | Ray dashboard port | 8265 |
| `user_script` | editor | Optional Ray job script to run | (empty) |

**Scheduler-specific inputs** (conditionally shown):
- SLURM: account, partition, QoS, walltime, nodes, additional directives
- PBS: account, queue, walltime, select statement

#### 1.3 Job Structure

```yaml
jobs:
  setup_environment:
    # Install Ray and dependencies on remote system

  start_ray_cluster:
    # Start Ray head + workers (handles SSH/SLURM/PBS modes)
    needs: [setup_environment]

  output_connection_info:
    # Display dashboard URL and connection instructions
    needs: [start_ray_cluster]

  run_user_job:
    # (Optional) Submit user's Ray job script
    needs: [start_ray_cluster]
    condition: ${{ inputs.user_script != '' }}
```

---

### Phase 2: Ray Cluster Startup Scripts

#### 2.1 SSH Direct Mode Script (`start_ray_ssh.sh`)

```bash
#!/bin/bash
set -e

# Start Ray head node locally
ray start --head \
    --port=6379 \
    --dashboard-host=0.0.0.0 \
    --dashboard-port=${DASHBOARD_PORT} \
    --num-cpus=${NUM_CPUS} \
    --num-gpus=${NUM_GPUS}

# Output connection info
echo "RAY_ADDRESS=ray://$(hostname):10001"
echo "DASHBOARD_URL=http://$(hostname):${DASHBOARD_PORT}"
```

#### 2.2 SLURM Multi-Node Script (`start_ray_slurm.sh`)

```bash
#!/bin/bash
set -e

# Get allocated nodes
NODELIST=$(scontrol show hostnames $SLURM_JOB_NODELIST)
HEAD_NODE=$(echo "$NODELIST" | head -n 1)
HEAD_NODE_IP=$(getent hosts $HEAD_NODE | awk '{ print $1 }')

# Start Ray head on first node
if [[ "$(hostname)" == "$HEAD_NODE" ]]; then
    ray start --head \
        --port=6379 \
        --dashboard-host=0.0.0.0 \
        --dashboard-port=${DASHBOARD_PORT} \
        --num-cpus=${NUM_CPUS} \
        --num-gpus=${NUM_GPUS}
fi

# Start Ray workers on all other nodes
for node in $NODELIST; do
    if [[ "$node" != "$HEAD_NODE" ]]; then
        srun --nodes=1 --ntasks=1 -w $node \
            ray start --address=${HEAD_NODE_IP}:6379 \
            --num-cpus=${NUM_CPUS} \
            --num-gpus=${NUM_GPUS} &
    fi
done

wait

echo "RAY_ADDRESS=ray://${HEAD_NODE_IP}:10001"
echo "DASHBOARD_URL=http://${HEAD_NODE_IP}:${DASHBOARD_PORT}"
```

#### 2.3 PBS Multi-Node Script (`start_ray_pbs.sh`)

```bash
#!/bin/bash
set -e

# Get allocated nodes from PBS
NODELIST=$(cat $PBS_NODEFILE | sort -u)
HEAD_NODE=$(echo "$NODELIST" | head -n 1)
HEAD_NODE_IP=$(getent hosts $HEAD_NODE | awk '{ print $1 }')

# Start Ray head on first node
if [[ "$(hostname -s)" == "$HEAD_NODE" ]] || [[ "$(hostname)" == "$HEAD_NODE" ]]; then
    ray start --head \
        --port=6379 \
        --dashboard-host=0.0.0.0 \
        --dashboard-port=${DASHBOARD_PORT} \
        --num-cpus=${NUM_CPUS} \
        --num-gpus=${NUM_GPUS}
fi

# Start Ray workers on other nodes
for node in $NODELIST; do
    if [[ "$node" != "$HEAD_NODE" ]]; then
        ssh $node "ray start --address=${HEAD_NODE_IP}:6379 \
            --num-cpus=${NUM_CPUS} \
            --num-gpus=${NUM_GPUS}" &
    fi
done

wait

echo "RAY_ADDRESS=ray://${HEAD_NODE_IP}:10001"
echo "DASHBOARD_URL=http://${HEAD_NODE_IP}:${DASHBOARD_PORT}"
```

---

### Phase 3: Environment Setup

#### 3.1 Ray Installation Script (`setup_ray.sh`)

```bash
#!/bin/bash
set -e

# Create/activate virtual environment
VENV_DIR="${PW_PARENT_JOB_DIR}/ray_venv"
python3 -m venv $VENV_DIR
source $VENV_DIR/bin/activate

# Install Ray
pip install --upgrade pip
pip install "ray[default]==${RAY_VERSION}"

# Verify installation
ray --version
python -c "import ray; print(f'Ray {ray.__version__} installed successfully')"

# Output venv path for subsequent jobs
echo "VENV_PATH=$VENV_DIR"
```

#### 3.2 Dependency Management

- Support custom `requirements.txt` upload for additional packages
- Handle conda environments as alternative to venv
- Support pre-existing Ray installations (skip install if detected)

---

### Phase 4: Job Submission Interface

#### 4.1 Ray Job Submission Script (`submit_job.sh`)

```bash
#!/bin/bash
set -e

# Submit job to Ray cluster
ray job submit \
    --address="${RAY_ADDRESS}" \
    --working-dir="${WORKING_DIR}" \
    -- python ${USER_SCRIPT}
```

#### 4.2 Interactive Connection Instructions

Output to user:
```
===========================================
Ray Cluster Started Successfully!
===========================================

Dashboard URL: http://<head-node>:8265
Ray Address:   ray://<head-node>:10001

To submit jobs from your local machine:
1. Set up SSH tunnel:
   ssh -L 8265:<head-node>:8265 -L 10001:<head-node>:10001 user@cluster

2. Submit jobs:
   ray job submit --address=http://localhost:8265 -- python your_script.py

3. Or connect programmatically:
   import ray
   ray.init("ray://localhost:10001")

===========================================
```

---

### Phase 5: Cluster Lifecycle Management

#### 5.1 Keep-Alive Mechanism

The Ray cluster needs to stay running to accept jobs. Options:

**Option A: Background Process with Heartbeat**
- Start Ray cluster as background job
- Monitor heartbeat file that user can touch to extend lifetime
- Auto-shutdown after idle timeout

**Option B: Persistent Scheduler Job**
- Submit long-running scheduler job (e.g., 4 hours)
- User can cancel when done
- Job resources released on cancellation

**Recommended: Option B** (simpler, leverages scheduler resource management)

#### 5.2 Shutdown Script (`shutdown_ray.sh`)

```bash
#!/bin/bash

# Stop Ray on all nodes
ray stop --force

# Clean up temporary files
rm -rf /tmp/ray/*
```

---

### Phase 6: Workflow YAML Implementation

#### 6.1 Complete Job Definitions

```yaml
jobs:
  preprocessing:
    name: Setup Environment
    runs-on: ${{ inputs.resource }}
    steps:
      - name: Create working directory
        run: mkdir -p ${PW_PARENT_JOB_DIR}

      - name: Generate startup scripts
        run: |
          # Generate all Ray startup scripts based on mode

  start_cluster:
    name: Start Ray Cluster
    needs: [preprocessing]
    runs-on: ${{ inputs.resource }}
    uses: marketplace/job_runner/v4.0
    with:
      script_path: ${PW_PARENT_JOB_DIR}/start_ray.sh
      slurm:
        is_disabled: ${{ inputs.resource.schedulerType != 'slurm' || !inputs.scheduler }}
        # SLURM settings...
      pbs:
        is_disabled: ${{ inputs.resource.schedulerType != 'pbs' || !inputs.scheduler }}
        # PBS settings...
    steps:
      - name: Display connection info
        run: |
          cat ${PW_PARENT_JOB_DIR}/connection_info.txt

  submit_user_job:
    name: Run User Script
    needs: [start_cluster]
    runs-on: ${{ inputs.resource }}
    condition: ${{ inputs.user_script != '' }}
    steps:
      - name: Submit user job to Ray
        run: |
          source ${PW_PARENT_JOB_DIR}/ray_venv/bin/activate
          ray job submit --address="${RAY_ADDRESS}" -- python user_job.py
```

---

## File Structure

```
activate-ray/
├── workflow.yaml                    # Main ACTIVATE workflow
├── README.md                        # Updated documentation
├── PLAN.md                          # This file
├── thumbnail.png                    # Workflow thumbnail
│
├── scripts/
│   ├── setup_ray.sh                 # Ray installation script
│   ├── start_ray_ssh.sh             # Single-node startup (SSH mode)
│   ├── start_ray_slurm.sh           # Multi-node startup (SLURM)
│   ├── start_ray_pbs.sh             # Multi-node startup (PBS)
│   ├── submit_job.sh                # Job submission helper
│   └── shutdown_ray.sh              # Cleanup script
│
├── examples/
│   ├── hello_ray.py                 # Simple Ray hello world
│   ├── distributed_compute.py       # Multi-node compute example
│   └── gpu_workload.py              # GPU-enabled example
│
├── tools/
│   ├── workflow_runner.py           # Local testing (existing)
│   ├── run_local.sh                 # Local run script (existing)
│   └── run_tests.sh                 # Test runner (existing)
│
└── tests/
    ├── conftest.py                  # Test fixtures
    ├── test_workflow_runner.py      # Unit tests
    └── test_integration.py          # Integration tests
```

---

## Implementation Tasks

### Task List

- [ ] **Phase 1: Core Workflow**
  - [ ] 1.1 Create new workflow.yaml with Ray-specific metadata
  - [ ] 1.2 Define all input parameters with proper types and defaults
  - [ ] 1.3 Define job structure with dependencies

- [ ] **Phase 2: Startup Scripts**
  - [ ] 2.1 Create `scripts/start_ray_ssh.sh` for SSH direct mode
  - [ ] 2.2 Create `scripts/start_ray_slurm.sh` for SLURM mode
  - [ ] 2.3 Create `scripts/start_ray_pbs.sh` for PBS mode

- [ ] **Phase 3: Environment Setup**
  - [ ] 3.1 Create `scripts/setup_ray.sh` for Ray installation
  - [ ] 3.2 Add support for custom requirements.txt

- [ ] **Phase 4: Job Submission**
  - [ ] 4.1 Create `scripts/submit_job.sh` for job submission
  - [ ] 4.2 Generate connection instructions output

- [ ] **Phase 5: Lifecycle Management**
  - [ ] 5.1 Implement cluster keep-alive via scheduler job
  - [ ] 5.2 Create `scripts/shutdown_ray.sh` for cleanup

- [ ] **Phase 6: Documentation & Examples**
  - [ ] 6.1 Update README.md with Ray workflow documentation
  - [ ] 6.2 Create example Ray job scripts in `examples/`
  - [ ] 6.3 Add usage examples and troubleshooting guide

- [ ] **Phase 7: Testing**
  - [ ] 7.1 Update unit tests for new workflow
  - [ ] 7.2 Add integration tests for Ray startup scripts
  - [ ] 7.3 Test on SLURM and PBS clusters

---

## Configuration Examples

### Minimal Configuration (SSH Direct)
```yaml
inputs:
  resource: my-cluster
  scheduler: false
  ray_version: "2.9.0"
```

### SLURM Multi-Node Configuration
```yaml
inputs:
  resource: my-slurm-cluster
  scheduler: true
  ray_version: "2.9.0"
  num_cpus_per_node: 8
  num_gpus_per_node: 2
  slurm_nodes: 4
  slurm_partition: gpu
  slurm_time: "04:00:00"
```

### PBS Multi-Node Configuration
```yaml
inputs:
  resource: my-pbs-cluster
  scheduler: true
  ray_version: "2.9.0"
  num_cpus_per_node: 16
  pbs_select: "4:ncpus=16:mem=64gb"
  pbs_walltime: "04:00:00"
```

---

## Success Criteria

1. **Functional**: Ray cluster starts successfully on SSH, SLURM, and PBS
2. **Accessible**: Dashboard URL and job submission endpoint are reachable
3. **Scalable**: Multi-node clusters work with proper worker distribution
4. **Documented**: Clear instructions for users to submit jobs
5. **Tested**: All modes tested with example workloads

---

## Open Questions / Decisions Needed

1. **Port forwarding**: How should the dashboard be exposed to users?
   - Option A: SSH tunnel instructions (manual)
   - Option B: Automatic tunnel setup via workflow
   - Option C: Reverse proxy through ACTIVATE platform

2. **Persistent vs. ephemeral clusters**:
   - Should the cluster stay running after the workflow job completes?
   - How long should idle timeout be?

3. **GPU support**:
   - What GPU types need to be supported (NVIDIA, AMD)?
   - Should CUDA version be configurable?

4. **Container support**:
   - Should there be an option to run Ray in containers (Singularity/Apptainer)?

---

## References

- [Ray Documentation](https://docs.ray.io/)
- [Ray Cluster Setup](https://docs.ray.io/en/latest/cluster/getting-started.html)
- [Ray on SLURM](https://docs.ray.io/en/latest/cluster/vms/user-guides/community/slurm.html)
- [ACTIVATE Workflow Documentation](https://parallelworks.com/docs)
