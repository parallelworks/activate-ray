#!/usr/bin/env python3
"""
Ray Job Submission Tool

Submit jobs to local or remote Ray clusters. Supports SSH tunneling for
remote cluster access.

Usage:
    # Submit to local cluster
    python tools/ray_submit.py examples/hello_ray.py

    # Submit to remote cluster via SSH tunnel
    python tools/ray_submit.py examples/hello_ray.py --tunnel user@cluster

    # Submit with custom Ray address
    python tools/ray_submit.py examples/hello_ray.py --address http://10.0.0.1:8265

    # Submit with working directory
    python tools/ray_submit.py examples/hello_ray.py --working-dir /path/to/deps
"""

import argparse
import os
import subprocess
import sys
import time
import signal
import atexit
from pathlib import Path


# Track tunnel processes for cleanup
tunnel_processes = []


def cleanup_tunnels():
    """Clean up any SSH tunnels on exit."""
    for proc in tunnel_processes:
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


atexit.register(cleanup_tunnels)


def setup_ssh_tunnel(ssh_host: str, remote_host: str, dashboard_port: int = 8265,
                     ray_port: int = 10001, local_dashboard_port: int = None,
                     local_ray_port: int = None) -> tuple:
    """
    Set up SSH tunnel to remote Ray cluster.

    Returns:
        Tuple of (local_dashboard_port, local_ray_port, tunnel_process)
    """
    local_dashboard_port = local_dashboard_port or dashboard_port
    local_ray_port = local_ray_port or ray_port

    print(f"Setting up SSH tunnel to {ssh_host}...")
    print(f"  Dashboard: localhost:{local_dashboard_port} -> {remote_host}:{dashboard_port}")
    print(f"  Ray:       localhost:{local_ray_port} -> {remote_host}:{ray_port}")

    tunnel_cmd = [
        "ssh", "-N", "-f",
        "-L", f"{local_dashboard_port}:{remote_host}:{dashboard_port}",
        "-L", f"{local_ray_port}:{remote_host}:{ray_port}",
        ssh_host
    ]

    # Start tunnel in background
    proc = subprocess.Popen(
        tunnel_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    tunnel_processes.append(proc)

    # Wait for tunnel to be established
    time.sleep(2)

    # Check if tunnel is working
    if proc.poll() is not None:
        _, stderr = proc.communicate()
        raise RuntimeError(f"SSH tunnel failed: {stderr.decode()}")

    print("  SSH tunnel established.")
    return local_dashboard_port, local_ray_port, proc


def submit_job(script_path: Path, address: str, working_dir: str = None,
               env_vars: dict = None, runtime_env: dict = None,
               extra_args: list = None) -> int:
    """
    Submit a job to the Ray cluster.

    Returns:
        Exit code from ray job submit
    """
    print(f"\nSubmitting job: {script_path}")
    print(f"  Address: {address}")

    cmd = ["ray", "job", "submit"]
    cmd.extend(["--address", address])

    # Set working directory
    if working_dir:
        cmd.extend(["--working-dir", working_dir])
    else:
        # Use script's parent directory
        cmd.extend(["--working-dir", str(script_path.parent.absolute())])

    # Add environment variables
    if env_vars:
        for key, value in env_vars.items():
            cmd.extend(["--env-var", f"{key}={value}"])

    # Add runtime environment (JSON)
    if runtime_env:
        import json
        cmd.extend(["--runtime-env-json", json.dumps(runtime_env)])

    # Add the script command
    cmd.append("--")
    cmd.append("python")
    cmd.append(script_path.name)

    # Add extra arguments for the script
    if extra_args:
        cmd.extend(extra_args)

    print(f"  Command: {' '.join(cmd)}")
    print()

    # Run the submission
    result = subprocess.run(cmd)
    return result.returncode


def list_jobs(address: str) -> int:
    """List jobs on the Ray cluster."""
    cmd = ["ray", "job", "list", "--address", address]
    result = subprocess.run(cmd)
    return result.returncode


def get_job_logs(address: str, job_id: str) -> int:
    """Get logs for a specific job."""
    cmd = ["ray", "job", "logs", "--address", address, job_id]
    result = subprocess.run(cmd)
    return result.returncode


def stop_job(address: str, job_id: str) -> int:
    """Stop a running job."""
    cmd = ["ray", "job", "stop", "--address", address, job_id]
    result = subprocess.run(cmd)
    return result.returncode


def main():
    parser = argparse.ArgumentParser(
        description="Submit jobs to Ray clusters (local or remote)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Submit to local cluster
  python tools/ray_submit.py examples/hello_ray.py

  # Submit to remote cluster via SSH tunnel
  python tools/ray_submit.py examples/hello_ray.py \\
      --tunnel user@hpc-cluster \\
      --remote-host compute-node-1

  # Submit with custom address (when tunnel is already set up)
  python tools/ray_submit.py examples/hello_ray.py \\
      --address http://localhost:8265

  # Submit with extra script arguments
  python tools/ray_submit.py examples/distributed_compute.py \\
      -- --num-tasks 100

  # List jobs
  python tools/ray_submit.py --list

  # Get job logs
  python tools/ray_submit.py --logs raysubmit_abc123

  # Stop a job
  python tools/ray_submit.py --stop raysubmit_abc123
"""
    )

    parser.add_argument("script", nargs="?", type=Path,
                        help="Python script to submit")
    parser.add_argument("--address", default="http://localhost:8265",
                        help="Ray cluster address (default: http://localhost:8265)")
    parser.add_argument("--working-dir", type=Path,
                        help="Working directory for the job")

    # SSH tunnel options
    parser.add_argument("--tunnel", metavar="SSH_HOST",
                        help="SSH host for tunneling (e.g., user@cluster)")
    parser.add_argument("--remote-host", default="localhost",
                        help="Remote host for Ray cluster (default: localhost)")
    parser.add_argument("--dashboard-port", type=int, default=8265,
                        help="Dashboard port (default: 8265)")
    parser.add_argument("--ray-port", type=int, default=10001,
                        help="Ray client port (default: 10001)")

    # Environment options
    parser.add_argument("--env", action="append", default=[],
                        help="Environment variable (KEY=VALUE)")

    # Job management
    parser.add_argument("--list", action="store_true",
                        help="List jobs on the cluster")
    parser.add_argument("--logs", metavar="JOB_ID",
                        help="Get logs for a job")
    parser.add_argument("--stop", metavar="JOB_ID",
                        help="Stop a running job")

    # Extra args for the script
    parser.add_argument("extra_args", nargs="*",
                        help="Extra arguments for the script")

    args = parser.parse_args()

    # Set up SSH tunnel if requested
    address = args.address
    if args.tunnel:
        try:
            dashboard_port, _, _ = setup_ssh_tunnel(
                args.tunnel,
                args.remote_host,
                args.dashboard_port,
                args.ray_port
            )
            address = f"http://localhost:{dashboard_port}"
        except Exception as e:
            print(f"Error setting up SSH tunnel: {e}")
            return 1

    # Handle job management commands
    if args.list:
        return list_jobs(address)

    if args.logs:
        return get_job_logs(address, args.logs)

    if args.stop:
        return stop_job(address, args.stop)

    # Validate script argument
    if not args.script:
        parser.print_help()
        print("\nError: script argument is required for job submission")
        return 1

    if not args.script.exists():
        print(f"Error: Script not found: {args.script}")
        return 1

    # Parse environment variables
    env_vars = {}
    for env in args.env:
        if "=" in env:
            key, value = env.split("=", 1)
            env_vars[key] = value

    # Submit the job
    return submit_job(
        args.script,
        address,
        str(args.working_dir) if args.working_dir else None,
        env_vars if env_vars else None,
        extra_args=args.extra_args if args.extra_args else None
    )


if __name__ == "__main__":
    sys.exit(main())
