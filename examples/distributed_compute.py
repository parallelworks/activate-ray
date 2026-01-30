#!/usr/bin/env python3
"""
Distributed Compute Example - Demonstrates Ray's distributed computing capabilities.

This script shows:
1. Distributed task execution across nodes
2. Actor pattern for stateful computation
3. Task dependencies and workflows
4. Resource-aware scheduling

Usage:
    python distributed_compute.py
    ray job submit --address=http://localhost:8265 -- python distributed_compute.py
"""

import ray
import os
import time
import socket
import numpy as np
from typing import List


def main():
    print("=" * 60)
    print("  Distributed Compute Example")
    print("=" * 60)
    print()

    # Initialize Ray
    ray_address = os.environ.get("RAY_ADDRESS", "auto")
    ray.init(address=ray_address)

    resources = ray.cluster_resources()
    num_cpus = int(resources.get("CPU", 4))
    print(f"Cluster has {num_cpus} CPUs available")
    print()

    # =========================================================================
    # Example 1: Distributed Map-Reduce
    # =========================================================================
    print("-" * 60)
    print("  Example 1: Distributed Map-Reduce")
    print("-" * 60)

    @ray.remote
    def map_function(data_chunk: List[int]) -> dict:
        """Map: Count occurrences of each value."""
        hostname = socket.gethostname()
        counts = {}
        for item in data_chunk:
            counts[item] = counts.get(item, 0) + 1
        return {"hostname": hostname, "counts": counts}

    @ray.remote
    def reduce_function(results: List[dict]) -> dict:
        """Reduce: Merge all counts together."""
        final_counts = {}
        for result in results:
            for key, count in result["counts"].items():
                final_counts[key] = final_counts.get(key, 0) + count
        return final_counts

    # Generate sample data and split into chunks
    data = [i % 10 for i in range(1000)]
    chunk_size = len(data) // num_cpus
    chunks = [data[i:i + chunk_size] for i in range(0, len(data), chunk_size)]

    print(f"Processing {len(data)} items in {len(chunks)} chunks...")

    # Map phase
    start_time = time.time()
    map_futures = [map_function.remote(chunk) for chunk in chunks]
    map_results = ray.get(map_futures)

    # Show which nodes processed the data
    hosts = set(r["hostname"] for r in map_results)
    print(f"Map phase executed on hosts: {hosts}")

    # Reduce phase
    final_result = ray.get(reduce_function.remote(map_results))
    elapsed = time.time() - start_time

    print(f"Reduce result (value counts): {final_result}")
    print(f"Total time: {elapsed:.3f}s")
    print()

    # =========================================================================
    # Example 2: Actor Pattern (Stateful Computation)
    # =========================================================================
    print("-" * 60)
    print("  Example 2: Actor Pattern (Stateful Computation)")
    print("-" * 60)

    @ray.remote
    class Counter:
        """A stateful counter actor."""

        def __init__(self, name: str):
            self.name = name
            self.value = 0
            self.hostname = socket.gethostname()

        def increment(self, amount: int = 1) -> int:
            self.value += amount
            return self.value

        def get_value(self) -> int:
            return self.value

        def get_info(self) -> dict:
            return {
                "name": self.name,
                "value": self.value,
                "hostname": self.hostname
            }

    # Create multiple counter actors
    counters = [Counter.remote(f"counter-{i}") for i in range(3)]

    # Increment counters in parallel
    print("Creating 3 counter actors and incrementing them...")
    increment_futures = []
    for i, counter in enumerate(counters):
        for j in range(5):
            increment_futures.append(counter.increment.remote(i + 1))

    ray.get(increment_futures)

    # Get final values
    info_futures = [counter.get_info.remote() for counter in counters]
    infos = ray.get(info_futures)

    for info in infos:
        print(f"  {info['name']}: value={info['value']}, "
              f"running on {info['hostname']}")
    print()

    # =========================================================================
    # Example 3: Task Dependencies (DAG)
    # =========================================================================
    print("-" * 60)
    print("  Example 3: Task Dependencies (DAG)")
    print("-" * 60)

    @ray.remote
    def stage_a(x: int) -> int:
        """First stage: multiply by 2."""
        time.sleep(0.1)  # Simulate work
        return x * 2

    @ray.remote
    def stage_b(x: int) -> int:
        """Second stage: add 10."""
        time.sleep(0.1)
        return x + 10

    @ray.remote
    def stage_c(a_result: int, b_result: int) -> int:
        """Final stage: combine results."""
        time.sleep(0.1)
        return a_result + b_result

    print("Executing task DAG: (a -> c) + (b -> c)")
    print("  Stage A: x * 2")
    print("  Stage B: x + 10")
    print("  Stage C: a_result + b_result")

    start_time = time.time()

    # Create task graph
    x = 5
    a_future = stage_a.remote(x)
    b_future = stage_b.remote(x)
    c_future = stage_c.remote(a_future, b_future)

    # Execute and get result
    result = ray.get(c_future)
    elapsed = time.time() - start_time

    print(f"  Input: x = {x}")
    print(f"  Result: {result}")
    print(f"  Expected: (5*2) + (5+10) = 25")
    print(f"  Time: {elapsed:.3f}s (stages A and B run in parallel)")
    print()

    # =========================================================================
    # Example 4: Parallel Matrix Operations
    # =========================================================================
    print("-" * 60)
    print("  Example 4: Parallel Matrix Operations")
    print("-" * 60)

    @ray.remote
    def matrix_multiply(a: np.ndarray, b: np.ndarray) -> np.ndarray:
        """Multiply two matrices."""
        return np.dot(a, b)

    @ray.remote
    def matrix_sum(matrices: List[np.ndarray]) -> np.ndarray:
        """Sum a list of matrices."""
        return np.sum(matrices, axis=0)

    # Create random matrices
    matrix_size = 100
    num_matrices = num_cpus

    print(f"Creating {num_matrices} random {matrix_size}x{matrix_size} matrices...")
    matrices_a = [np.random.rand(matrix_size, matrix_size) for _ in range(num_matrices)]
    matrices_b = [np.random.rand(matrix_size, matrix_size) for _ in range(num_matrices)]

    # Parallel matrix multiplications
    start_time = time.time()
    multiply_futures = [
        matrix_multiply.remote(a, b)
        for a, b in zip(matrices_a, matrices_b)
    ]
    products = ray.get(multiply_futures)

    # Sum all products
    final_matrix = ray.get(matrix_sum.remote(products))
    elapsed = time.time() - start_time

    print(f"Computed {num_matrices} matrix multiplications in parallel")
    print(f"Final matrix shape: {final_matrix.shape}")
    print(f"Final matrix sum: {final_matrix.sum():.2f}")
    print(f"Time: {elapsed:.3f}s")
    print()

    # =========================================================================
    # Summary
    # =========================================================================
    print("=" * 60)
    print("  Distributed Compute Example Complete!")
    print("=" * 60)

    ray.shutdown()


if __name__ == "__main__":
    main()
