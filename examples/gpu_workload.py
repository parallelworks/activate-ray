#!/usr/bin/env python3
"""
GPU Workload Example - Demonstrates Ray with GPU resources.

This script shows:
1. GPU resource allocation and scheduling
2. Running tasks on specific GPU devices
3. Basic GPU computation (if PyTorch/TensorFlow available)

Usage:
    python gpu_workload.py
    ray job submit --address=http://localhost:8265 -- python gpu_workload.py

Note: Requires GPUs to be available on the cluster.
"""

import ray
import os
import socket


def check_gpu_availability():
    """Check if GPUs are available via different methods."""
    gpu_info = {
        "nvidia_smi": False,
        "cuda_visible": os.environ.get("CUDA_VISIBLE_DEVICES", "not set"),
        "pytorch": False,
        "tensorflow": False,
    }

    # Check nvidia-smi
    try:
        import subprocess
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            gpu_info["nvidia_smi"] = True
            gpu_info["nvidia_smi_output"] = result.stdout.strip()
    except Exception:
        pass

    # Check PyTorch
    try:
        import torch
        gpu_info["pytorch"] = torch.cuda.is_available()
        if gpu_info["pytorch"]:
            gpu_info["pytorch_devices"] = torch.cuda.device_count()
            gpu_info["pytorch_device_name"] = torch.cuda.get_device_name(0)
    except ImportError:
        gpu_info["pytorch_error"] = "PyTorch not installed"
    except Exception as e:
        gpu_info["pytorch_error"] = str(e)

    # Check TensorFlow
    try:
        import tensorflow as tf
        gpus = tf.config.list_physical_devices("GPU")
        gpu_info["tensorflow"] = len(gpus) > 0
        gpu_info["tensorflow_devices"] = len(gpus)
    except ImportError:
        gpu_info["tensorflow_error"] = "TensorFlow not installed"
    except Exception as e:
        gpu_info["tensorflow_error"] = str(e)

    return gpu_info


def main():
    print("=" * 60)
    print("  GPU Workload Example")
    print("=" * 60)
    print()

    # Initialize Ray
    ray_address = os.environ.get("RAY_ADDRESS", "auto")
    ray.init(address=ray_address)

    # Check cluster GPU resources
    resources = ray.cluster_resources()
    num_gpus = resources.get("GPU", 0)

    print("-" * 60)
    print("  Cluster GPU Resources")
    print("-" * 60)
    print(f"Total GPUs in cluster: {num_gpus}")

    if num_gpus == 0:
        print()
        print("WARNING: No GPUs detected in the cluster!")
        print("This example requires GPUs to run the GPU-specific tasks.")
        print("Running CPU-only verification instead...")
        print()

        # Run CPU verification
        @ray.remote
        def cpu_task(task_id: int) -> dict:
            return {
                "task_id": task_id,
                "hostname": socket.gethostname(),
                "gpu_info": check_gpu_availability(),
            }

        print("-" * 60)
        print("  CPU Task Verification")
        print("-" * 60)

        futures = [cpu_task.remote(i) for i in range(min(4, int(resources.get("CPU", 2))))]
        results = ray.get(futures)

        for result in results:
            print(f"Task {result['task_id']} on {result['hostname']}:")
            gpu_info = result["gpu_info"]
            print(f"  CUDA_VISIBLE_DEVICES: {gpu_info['cuda_visible']}")
            print(f"  nvidia-smi available: {gpu_info['nvidia_smi']}")
            if gpu_info.get("nvidia_smi_output"):
                print(f"  GPUs: {gpu_info['nvidia_smi_output']}")

    else:
        print()

        # =====================================================================
        # GPU Task Definition
        # =====================================================================
        @ray.remote(num_gpus=1)
        def gpu_task(task_id: int) -> dict:
            """Task that requires 1 GPU."""
            hostname = socket.gethostname()
            gpu_info = check_gpu_availability()

            result = {
                "task_id": task_id,
                "hostname": hostname,
                "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES", "not set"),
                "gpu_info": gpu_info,
            }

            # Try to do some GPU computation
            try:
                import torch
                if torch.cuda.is_available():
                    device = torch.device("cuda")
                    # Simple GPU computation
                    x = torch.rand(1000, 1000, device=device)
                    y = torch.rand(1000, 1000, device=device)
                    z = torch.mm(x, y)
                    result["pytorch_computation"] = f"Matrix multiply result sum: {z.sum().item():.2f}"
                    result["pytorch_device"] = str(device)
            except ImportError:
                result["pytorch_computation"] = "PyTorch not available"
            except Exception as e:
                result["pytorch_computation"] = f"Error: {e}"

            return result

        # =====================================================================
        # Run GPU Tasks
        # =====================================================================
        print("-" * 60)
        print("  Running GPU Tasks")
        print("-" * 60)

        num_tasks = int(num_gpus)
        print(f"Submitting {num_tasks} GPU tasks (1 GPU each)...")

        futures = [gpu_task.remote(i) for i in range(num_tasks)]
        results = ray.get(futures)

        for result in results:
            print()
            print(f"Task {result['task_id']}:")
            print(f"  Hostname: {result['hostname']}")
            print(f"  CUDA_VISIBLE_DEVICES: {result['cuda_visible_devices']}")
            if result.get("pytorch_computation"):
                print(f"  PyTorch: {result['pytorch_computation']}")

        # =====================================================================
        # Multi-GPU Task (if multiple GPUs available)
        # =====================================================================
        if num_gpus >= 2:
            print()
            print("-" * 60)
            print("  Multi-GPU Task")
            print("-" * 60)

            @ray.remote(num_gpus=2)
            def multi_gpu_task() -> dict:
                """Task that requires 2 GPUs."""
                return {
                    "hostname": socket.gethostname(),
                    "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES", "not set"),
                    "num_gpus_requested": 2,
                }

            print("Running task requiring 2 GPUs...")
            result = ray.get(multi_gpu_task.remote())
            print(f"  Hostname: {result['hostname']}")
            print(f"  CUDA_VISIBLE_DEVICES: {result['cuda_visible_devices']}")

    # =========================================================================
    # Summary
    # =========================================================================
    print()
    print("=" * 60)
    print("  GPU Workload Example Complete!")
    print("=" * 60)

    ray.shutdown()


if __name__ == "__main__":
    main()
