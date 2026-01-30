#!/usr/bin/env python3
"""
Local Ray Cluster Manager for Testing

Start a local Ray cluster for testing workflows without remote infrastructure.
This allows you to verify Ray jobs work correctly before deploying to HPC.

Usage:
    # Start a local Ray cluster
    python tools/ray_local.py start

    # Start with specific resources
    python tools/ray_local.py start --num-cpus 4 --num-gpus 0

    # Check cluster status
    python tools/ray_local.py status

    # Stop the local cluster
    python tools/ray_local.py stop

    # Submit a job to the local cluster
    python tools/ray_local.py submit examples/hello_ray.py

    # Run the example scripts
    python tools/ray_local.py run-examples
"""

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path


def check_ray_installed():
    """Check if Ray is installed."""
    try:
        import ray
        return True, ray.__version__
    except ImportError:
        return False, None


def start_cluster(args):
    """Start a local Ray cluster."""
    installed, version = check_ray_installed()
    if not installed:
        print("Error: Ray is not installed. Install with: pip install 'ray[default]'")
        return 1

    print(f"Starting local Ray cluster (Ray {version})...")
    print()

    # Build the ray start command
    cmd = ["ray", "start", "--head"]
    cmd.extend(["--port", str(args.port)])
    cmd.extend(["--dashboard-host", "0.0.0.0"])
    cmd.extend(["--dashboard-port", str(args.dashboard_port)])

    if args.num_cpus:
        cmd.extend(["--num-cpus", str(args.num_cpus)])
    if args.num_gpus is not None:
        cmd.extend(["--num-gpus", str(args.num_gpus)])

    print(f"Command: {' '.join(cmd)}")
    print()

    result = subprocess.run(cmd)

    if result.returncode == 0:
        print()
        print("=" * 60)
        print("  Local Ray Cluster Started")
        print("=" * 60)
        print()
        print(f"  Dashboard:   http://localhost:{args.dashboard_port}")
        print(f"  Ray Address: ray://localhost:10001")
        print()
        print("  To submit jobs:")
        print(f"    ray job submit --address=http://localhost:{args.dashboard_port} -- python your_script.py")
        print()
        print("  To connect in Python:")
        print("    import ray")
        print("    ray.init('ray://localhost:10001')")
        print()
        print("  To stop the cluster:")
        print("    python tools/ray_local.py stop")
        print("=" * 60)

    return result.returncode


def stop_cluster(args):
    """Stop the local Ray cluster."""
    print("Stopping local Ray cluster...")
    result = subprocess.run(["ray", "stop", "--force"])

    if result.returncode == 0:
        print("Ray cluster stopped.")
    return result.returncode


def cluster_status(args):
    """Show cluster status."""
    installed, version = check_ray_installed()
    if not installed:
        print("Error: Ray is not installed.")
        return 1

    print(f"Ray version: {version}")
    print()

    # Try ray status
    result = subprocess.run(["ray", "status"], capture_output=True, text=True)

    if result.returncode == 0:
        print(result.stdout)
    else:
        print("No Ray cluster is currently running.")
        if result.stderr:
            print(f"Details: {result.stderr}")

    return 0


def submit_job(args):
    """Submit a job to the Ray cluster."""
    script_path = Path(args.script)
    if not script_path.exists():
        print(f"Error: Script not found: {script_path}")
        return 1

    print(f"Submitting job: {script_path}")
    print()

    # Build the ray job submit command
    cmd = ["ray", "job", "submit"]
    cmd.extend(["--address", args.address])

    if args.working_dir:
        cmd.extend(["--working-dir", args.working_dir])
    else:
        # Use the script's directory as working dir
        cmd.extend(["--working-dir", str(script_path.parent)])

    cmd.append("--")
    cmd.append("python")
    cmd.append(script_path.name)

    # Add any extra arguments
    if args.extra_args:
        cmd.extend(args.extra_args)

    print(f"Command: {' '.join(cmd)}")
    print()

    result = subprocess.run(cmd)
    return result.returncode


def run_script(args):
    """Run a Ray script directly (without job submission)."""
    script_path = Path(args.script)
    if not script_path.exists():
        print(f"Error: Script not found: {script_path}")
        return 1

    print(f"Running: {script_path}")
    print()

    env = os.environ.copy()
    if args.address:
        env["RAY_ADDRESS"] = args.address

    result = subprocess.run(
        ["python", str(script_path)],
        env=env
    )
    return result.returncode


def run_examples(args):
    """Run the example Ray scripts."""
    examples_dir = Path(__file__).parent.parent / "examples"

    if not examples_dir.exists():
        print(f"Error: Examples directory not found: {examples_dir}")
        return 1

    examples = sorted(examples_dir.glob("*.py"))
    if not examples:
        print("No example scripts found.")
        return 0

    print("=" * 60)
    print("  Running Ray Examples")
    print("=" * 60)
    print()

    overall_success = True
    for example in examples:
        print(f"\n{'='*60}")
        print(f"  Running: {example.name}")
        print(f"{'='*60}\n")

        env = os.environ.copy()
        env["RAY_ADDRESS"] = args.address if args.address else "auto"

        result = subprocess.run(["python", str(example)], env=env)

        if result.returncode != 0:
            print(f"\nExample {example.name} failed with exit code {result.returncode}")
            overall_success = False
            if not args.continue_on_error:
                return result.returncode

    print()
    print("=" * 60)
    if overall_success:
        print("  All examples completed successfully!")
    else:
        print("  Some examples failed.")
    print("=" * 60)

    return 0 if overall_success else 1


def main():
    parser = argparse.ArgumentParser(
        description="Local Ray cluster manager for testing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start a local cluster
  python tools/ray_local.py start

  # Check cluster status
  python tools/ray_local.py status

  # Submit a job
  python tools/ray_local.py submit examples/hello_ray.py

  # Run a script directly
  python tools/ray_local.py run examples/hello_ray.py

  # Run all examples
  python tools/ray_local.py run-examples

  # Stop the cluster
  python tools/ray_local.py stop
"""
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # start command
    start_parser = subparsers.add_parser("start", help="Start a local Ray cluster")
    start_parser.add_argument("--port", type=int, default=6379,
                              help="Ray head port (default: 6379)")
    start_parser.add_argument("--dashboard-port", type=int, default=8265,
                              help="Dashboard port (default: 8265)")
    start_parser.add_argument("--num-cpus", type=int,
                              help="Number of CPUs (default: auto-detect)")
    start_parser.add_argument("--num-gpus", type=int,
                              help="Number of GPUs (default: auto-detect)")

    # stop command
    subparsers.add_parser("stop", help="Stop the local Ray cluster")

    # status command
    subparsers.add_parser("status", help="Show cluster status")

    # submit command
    submit_parser = subparsers.add_parser("submit", help="Submit a job to Ray cluster")
    submit_parser.add_argument("script", help="Python script to submit")
    submit_parser.add_argument("--address", default="http://localhost:8265",
                               help="Ray cluster address (default: http://localhost:8265)")
    submit_parser.add_argument("--working-dir",
                               help="Working directory for the job")
    submit_parser.add_argument("extra_args", nargs="*",
                               help="Extra arguments for the script")

    # run command
    run_parser = subparsers.add_parser("run", help="Run a Ray script directly")
    run_parser.add_argument("script", help="Python script to run")
    run_parser.add_argument("--address", default="auto",
                            help="Ray address (default: auto)")

    # run-examples command
    examples_parser = subparsers.add_parser("run-examples", help="Run all example scripts")
    examples_parser.add_argument("--address", default="auto",
                                 help="Ray address (default: auto)")
    examples_parser.add_argument("--continue-on-error", action="store_true",
                                 help="Continue running examples even if one fails")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    commands = {
        "start": start_cluster,
        "stop": stop_cluster,
        "status": cluster_status,
        "submit": submit_job,
        "run": run_script,
        "run-examples": run_examples,
    }

    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
