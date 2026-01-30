#!/usr/bin/env python3
"""
Hello Ray - Simple Ray cluster verification script.

This script verifies that a Ray cluster is working correctly by:
1. Connecting to the cluster
2. Printing cluster resources
3. Running simple distributed tasks

Usage:
    # Connect to local cluster
    python hello_ray.py

    # Connect to remote cluster
    RAY_ADDRESS=ray://192.168.1.100:10001 python hello_ray.py

    # Submit as a Ray job
    ray job submit --address=http://localhost:8265 -- python hello_ray.py
"""

import ray
import os
import socket
import sys


def main():
    print("=" * 50)
    print("  Hello Ray - Cluster Verification")
    print("=" * 50)
    print()

    # Get Ray address from environment or use default
    ray_address = os.environ.get("RAY_ADDRESS", "auto")
    print(f"Connecting to Ray cluster: {ray_address}")

    # Initialize Ray
    try:
        ray.init(address=ray_address)
        print("Successfully connected to Ray cluster!")
    except Exception as e:
        print(f"Failed to connect to Ray cluster: {e}")
        sys.exit(1)

    # Print cluster information
    print()
    print("-" * 50)
    print("  Cluster Resources")
    print("-" * 50)
    resources = ray.cluster_resources()
    for key, value in sorted(resources.items()):
        print(f"  {key}: {value}")

    print()
    print("-" * 50)
    print("  Available Resources")
    print("-" * 50)
    available = ray.available_resources()
    for key, value in sorted(available.items()):
        print(f"  {key}: {value}")

    # Get nodes information
    print()
    print("-" * 50)
    print("  Cluster Nodes")
    print("-" * 50)
    nodes = ray.nodes()
    for i, node in enumerate(nodes):
        print(f"  Node {i + 1}:")
        print(f"    NodeID: {node['NodeID'][:8]}...")
        print(f"    Alive: {node['Alive']}")
        print(f"    Resources: {node.get('Resources', {})}")

    # Define a simple remote function
    @ray.remote
    def get_node_info(task_id):
        """Get information about the node executing this task."""
        return {
            "task_id": task_id,
            "hostname": socket.gethostname(),
            "pid": os.getpid(),
        }

    # Run distributed tasks
    print()
    print("-" * 50)
    print("  Running Distributed Tasks")
    print("-" * 50)

    num_tasks = min(10, int(resources.get("CPU", 4)))
    print(f"Submitting {num_tasks} tasks...")

    futures = [get_node_info.remote(i) for i in range(num_tasks)]
    results = ray.get(futures)

    for result in results:
        print(f"  Task {result['task_id']}: "
              f"hostname={result['hostname']}, "
              f"pid={result['pid']}")

    # Simple computation test
    @ray.remote
    def compute_square(x):
        return x * x

    print()
    print("-" * 50)
    print("  Computation Test")
    print("-" * 50)

    numbers = list(range(10))
    futures = [compute_square.remote(n) for n in numbers]
    squares = ray.get(futures)

    print(f"  Input:  {numbers}")
    print(f"  Output: {squares}")

    print()
    print("=" * 50)
    print("  Hello Ray completed successfully!")
    print("=" * 50)

    # Shutdown Ray
    ray.shutdown()


if __name__ == "__main__":
    main()
