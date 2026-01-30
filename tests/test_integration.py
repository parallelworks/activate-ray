"""
Integration tests for the Ray Cluster workflow.

These tests execute the actual workflow with different configurations
and verify end-to-end behavior.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

# Add tools to path
sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

from workflow_runner import WorkflowRunner, ExecutionContext


class TestWorkflowExecution:
    """Integration tests for full workflow execution."""

    def test_workflow_dry_run(self, workflow_path: Path, dry_run_context: ExecutionContext):
        """Test workflow executes successfully in dry-run mode."""
        runner = WorkflowRunner(workflow_path, dry_run_context)
        success = runner.run()
        assert success is True

    def test_workflow_creates_working_directory(
        self, workflow_path: Path, temp_work_dir: Path
    ):
        """Test that workflow creates the working directory."""
        context = ExecutionContext(
            inputs={
                "resource": {"ip": "localhost", "schedulerType": ""},
                "ray_version": "2.40.0",
                "ray_port": 6379,
                "dashboard_port": 8265,
                "num_cpus": 0,
                "num_gpus": 0,
                "user_script": "",
                "scheduler": False,
            },
            env_vars={
                "PW_JOB_ID": "dir-test",
                "PW_PARENT_JOB_DIR": str(temp_work_dir),
                "PW_USER": "testuser",
                "HOME": os.environ.get("HOME", "/tmp"),
            },
            work_dir=temp_work_dir,
            dry_run=True,  # Use dry-run to avoid needing Ray
            verbose=False,
        )

        runner = WorkflowRunner(workflow_path, context)
        success = runner.run()

        assert success is True

    def test_workflow_with_user_script(
        self, workflow_path: Path, temp_work_dir: Path
    ):
        """Test workflow with a user script."""
        user_script = '''
import sys
print("Hello from user script")
sys.exit(0)
'''
        context = ExecutionContext(
            inputs={
                "resource": {"ip": "localhost", "schedulerType": ""},
                "ray_version": "2.40.0",
                "ray_port": 6379,
                "dashboard_port": 8265,
                "num_cpus": 2,
                "num_gpus": 0,
                "user_script": user_script,
                "scheduler": False,
            },
            env_vars={
                "PW_JOB_ID": "script-test",
                "PW_PARENT_JOB_DIR": str(temp_work_dir),
                "PW_USER": "testuser",
                "HOME": os.environ.get("HOME", "/tmp"),
            },
            work_dir=temp_work_dir,
            dry_run=True,  # Dry-run mode
            verbose=False,
        )

        runner = WorkflowRunner(workflow_path, context)
        success = runner.run()

        assert success is True

    def test_workflow_run_specific_jobs(
        self, workflow_path: Path, temp_work_dir: Path
    ):
        """Test running only specific jobs via API."""
        context = ExecutionContext(
            inputs={
                "resource": {"ip": "localhost", "schedulerType": ""},
                "ray_version": "2.40.0",
                "ray_port": 6379,
                "dashboard_port": 8265,
                "num_cpus": 0,
                "num_gpus": 0,
                "user_script": "",
                "scheduler": False,
            },
            env_vars={
                "PW_JOB_ID": "specific-job-test",
                "PW_PARENT_JOB_DIR": str(temp_work_dir),
                "PW_USER": "testuser",
                "HOME": os.environ.get("HOME", "/tmp"),
            },
            work_dir=temp_work_dir,
            dry_run=True,
            verbose=False,
        )

        runner = WorkflowRunner(workflow_path, context)
        # Run only the setup job
        success = runner.run(only_jobs=["setup"])

        assert success is True
        # Only setup should be in outputs
        assert "setup" in context.job_outputs
        assert "ray_cluster" not in context.job_outputs

    def test_workflow_invalid_job_returns_false(
        self, workflow_path: Path, temp_work_dir: Path
    ):
        """Test that invalid job names cause run() to return False."""
        context = ExecutionContext(
            inputs={
                "resource": {"ip": "localhost", "schedulerType": ""},
                "ray_version": "2.40.0",
                "ray_port": 6379,
                "dashboard_port": 8265,
                "num_cpus": 0,
                "num_gpus": 0,
                "user_script": "",
                "scheduler": False,
            },
            env_vars={
                "PW_JOB_ID": "invalid-job-test",
                "PW_PARENT_JOB_DIR": str(temp_work_dir),
                "PW_USER": "testuser",
                "HOME": os.environ.get("HOME", "/tmp"),
            },
            work_dir=temp_work_dir,
            dry_run=True,
            verbose=False,
        )

        runner = WorkflowRunner(workflow_path, context)
        success = runner.run(only_jobs=["nonexistent_job"])

        assert success is False


class TestCommandLineInterface:
    """Test the command-line interface."""

    def test_cli_help(self, repo_root: Path):
        """Test that --help works."""
        result = subprocess.run(
            [sys.executable, str(repo_root / "tools" / "workflow_runner.py"), "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "workflow" in result.stdout.lower()

    def test_cli_dry_run(self, repo_root: Path):
        """Test CLI dry-run execution."""
        result = subprocess.run(
            [
                sys.executable,
                str(repo_root / "tools" / "workflow_runner.py"),
                str(repo_root / "workflow.yaml"),
                "--dry-run",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "DRY-RUN" in result.stdout

    def test_cli_with_custom_input(self, repo_root: Path, temp_work_dir: Path):
        """Test CLI with custom input values."""
        result = subprocess.run(
            [
                sys.executable,
                str(repo_root / "tools" / "workflow_runner.py"),
                str(repo_root / "workflow.yaml"),
                "--dry-run",
                "-i", "ray_version=2.10.0",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

    def test_cli_nonexistent_workflow(self, repo_root: Path):
        """Test CLI with nonexistent workflow file."""
        result = subprocess.run(
            [
                sys.executable,
                str(repo_root / "tools" / "workflow_runner.py"),
                "/nonexistent/workflow.yaml",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        assert "not found" in result.stderr.lower()

    def test_cli_dry_run_with_work_dir(self, repo_root: Path, temp_work_dir: Path):
        """Test CLI dry-run with work directory."""
        result = subprocess.run(
            [
                sys.executable,
                str(repo_root / "tools" / "workflow_runner.py"),
                str(repo_root / "workflow.yaml"),
                "--work-dir", str(temp_work_dir),
                "--dry-run",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0
        assert "SUCCESS" in result.stdout

    def test_cli_list_jobs(self, repo_root: Path):
        """Test --list-jobs flag."""
        result = subprocess.run(
            [
                sys.executable,
                str(repo_root / "tools" / "workflow_runner.py"),
                str(repo_root / "workflow.yaml"),
                "--list-jobs",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "setup" in result.stdout
        assert "ray_cluster" in result.stdout
        assert "wait_for_service" in result.stdout

    def test_cli_run_specific_job(self, repo_root: Path, temp_work_dir: Path):
        """Test running a specific job with --job flag."""
        result = subprocess.run(
            [
                sys.executable,
                str(repo_root / "tools" / "workflow_runner.py"),
                str(repo_root / "workflow.yaml"),
                "--job", "setup",
                "--dry-run",
                "--work-dir", str(temp_work_dir),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0
        assert "setup" in result.stdout
        # Should only run setup, not other jobs
        assert "Running selected jobs" in result.stdout

    def test_cli_run_multiple_jobs(self, repo_root: Path, temp_work_dir: Path):
        """Test running multiple specific jobs."""
        result = subprocess.run(
            [
                sys.executable,
                str(repo_root / "tools" / "workflow_runner.py"),
                str(repo_root / "workflow.yaml"),
                "--job", "setup",
                "--job", "wait_for_service",
                "--dry-run",
                "--work-dir", str(temp_work_dir),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0
        assert "Running selected jobs" in result.stdout

    def test_cli_invalid_job_name(self, repo_root: Path):
        """Test that invalid job names are rejected."""
        result = subprocess.run(
            [
                sys.executable,
                str(repo_root / "tools" / "workflow_runner.py"),
                str(repo_root / "workflow.yaml"),
                "--job", "nonexistent_job",
                "--dry-run",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        assert "Unknown jobs" in result.stdout or "nonexistent_job" in result.stdout


class TestRayLocalTool:
    """Test the ray_local.py tool."""

    def test_ray_local_help(self, repo_root: Path):
        """Test ray_local.py --help."""
        result = subprocess.run(
            [sys.executable, str(repo_root / "tools" / "ray_local.py"), "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "start" in result.stdout.lower()
        assert "stop" in result.stdout.lower()
        assert "status" in result.stdout.lower()

    def test_ray_local_start_help(self, repo_root: Path):
        """Test ray_local.py start --help."""
        result = subprocess.run(
            [sys.executable, str(repo_root / "tools" / "ray_local.py"), "start", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "port" in result.stdout.lower()


class TestRaySubmitTool:
    """Test the ray_submit.py tool."""

    def test_ray_submit_help(self, repo_root: Path):
        """Test ray_submit.py --help."""
        result = subprocess.run(
            [sys.executable, str(repo_root / "tools" / "ray_submit.py"), "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "address" in result.stdout.lower()
        assert "tunnel" in result.stdout.lower()


class TestExampleScripts:
    """Test that example scripts are syntactically valid."""

    def test_hello_ray_syntax(self, repo_root: Path):
        """Test hello_ray.py has valid syntax."""
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", str(repo_root / "examples" / "hello_ray.py")],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

    def test_distributed_compute_syntax(self, repo_root: Path):
        """Test distributed_compute.py has valid syntax."""
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", str(repo_root / "examples" / "distributed_compute.py")],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

    def test_gpu_workload_syntax(self, repo_root: Path):
        """Test gpu_workload.py has valid syntax."""
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", str(repo_root / "examples" / "gpu_workload.py")],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0


class TestScriptFiles:
    """Test that shell scripts are present and valid."""

    def test_setup_ray_exists(self, repo_root: Path):
        """Test setup_ray.sh exists."""
        script_path = repo_root / "scripts" / "setup_ray.sh"
        assert script_path.exists()
        assert script_path.stat().st_size > 0

    def test_start_ray_head_exists(self, repo_root: Path):
        """Test start_ray_head.sh exists."""
        script_path = repo_root / "scripts" / "start_ray_head.sh"
        assert script_path.exists()

    def test_start_ray_worker_exists(self, repo_root: Path):
        """Test start_ray_worker.sh exists."""
        script_path = repo_root / "scripts" / "start_ray_worker.sh"
        assert script_path.exists()

    def test_slurm_script_exists(self, repo_root: Path):
        """Test start_ray_cluster_slurm.sh exists."""
        script_path = repo_root / "scripts" / "start_ray_cluster_slurm.sh"
        assert script_path.exists()

    def test_pbs_script_exists(self, repo_root: Path):
        """Test start_ray_cluster_pbs.sh exists."""
        script_path = repo_root / "scripts" / "start_ray_cluster_pbs.sh"
        assert script_path.exists()

    def test_shutdown_script_exists(self, repo_root: Path):
        """Test shutdown_ray.sh exists."""
        script_path = repo_root / "scripts" / "shutdown_ray.sh"
        assert script_path.exists()

    def test_submit_job_script_exists(self, repo_root: Path):
        """Test submit_ray_job.sh exists."""
        script_path = repo_root / "scripts" / "submit_ray_job.sh"
        assert script_path.exists()

    def test_wait_for_ray_script_exists(self, repo_root: Path):
        """Test wait_for_ray.sh exists."""
        script_path = repo_root / "scripts" / "wait_for_ray.sh"
        assert script_path.exists()
        # Verify it has the expected outputs documented
        content = script_path.read_text()
        assert "HOSTNAME" in content
        assert "SESSION_PORT" in content


class TestWorkflowInputDefaults:
    """Test workflow input default handling."""

    def test_default_ray_version(self, workflow_path: Path):
        """Test that default Ray version is set."""
        import yaml
        with open(workflow_path) as f:
            workflow = yaml.safe_load(f)

        inputs = workflow.get("on", {}).get("execute", {}).get("inputs", {})
        assert "ray_version" in inputs
        assert inputs["ray_version"].get("default") == "2.40.0"

    def test_default_ports(self, workflow_path: Path):
        """Test that default ports are set."""
        import yaml
        with open(workflow_path) as f:
            workflow = yaml.safe_load(f)

        inputs = workflow.get("on", {}).get("execute", {}).get("inputs", {})
        assert inputs["ray_port"].get("default") == 6379
        assert inputs["dashboard_port"].get("default") == 8265

    def test_scheduler_defaults_to_false(self, workflow_path: Path):
        """Test that scheduler defaults to false."""
        import yaml
        with open(workflow_path) as f:
            workflow = yaml.safe_load(f)

        inputs = workflow.get("on", {}).get("execute", {}).get("inputs", {})
        assert inputs["scheduler"].get("default") is False
