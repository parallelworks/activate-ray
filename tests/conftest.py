"""
Pytest configuration and fixtures for Ray Cluster workflow tests.
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path
from typing import Generator

import pytest

# Add tools directory to path for imports
REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools"))

from workflow_runner import (
    WorkflowRunner,
    ExecutionContext,
    get_default_inputs,
    parse_input_arg,
    build_nested_dict,
)


@pytest.fixture
def repo_root() -> Path:
    """Return the repository root path."""
    return REPO_ROOT


@pytest.fixture
def workflow_path(repo_root: Path) -> Path:
    """Return the path to workflow.yaml."""
    return repo_root / "workflow.yaml"


@pytest.fixture
def temp_work_dir() -> Generator[Path, None, None]:
    """Create a temporary working directory for tests."""
    work_dir = Path(tempfile.mkdtemp(prefix="test-ray-workflow-"))
    yield work_dir
    # Cleanup
    if work_dir.exists():
        shutil.rmtree(work_dir)


@pytest.fixture
def default_context(temp_work_dir: Path) -> ExecutionContext:
    """Create a default execution context for testing."""
    return ExecutionContext(
        inputs={
            "resource": {"ip": "localhost", "schedulerType": ""},
            "ray_version": "2.9.0",
            "ray_port": 6379,
            "dashboard_port": 8265,
            "num_cpus": 0,
            "num_gpus": 0,
            "user_script": "",
            "scheduler": False,
        },
        env_vars={
            "PW_JOB_ID": "test-123",
            "PW_PARENT_JOB_DIR": str(temp_work_dir),
            "PW_USER": "testuser",
            "HOME": os.environ.get("HOME", "/tmp"),
        },
        work_dir=temp_work_dir,
        dry_run=False,
        verbose=False,
    )


@pytest.fixture
def dry_run_context(temp_work_dir: Path) -> ExecutionContext:
    """Create a dry-run execution context for testing."""
    return ExecutionContext(
        inputs={
            "resource": {"ip": "localhost", "schedulerType": ""},
            "ray_version": "2.9.0",
            "ray_port": 6379,
            "dashboard_port": 8265,
            "num_cpus": 0,
            "num_gpus": 0,
            "user_script": "",
            "scheduler": False,
        },
        env_vars={
            "PW_JOB_ID": "test-456",
            "PW_PARENT_JOB_DIR": str(temp_work_dir),
            "PW_USER": "testuser",
            "HOME": os.environ.get("HOME", "/tmp"),
        },
        work_dir=temp_work_dir,
        dry_run=True,
        verbose=False,
    )


@pytest.fixture
def workflow_runner(workflow_path: Path, default_context: ExecutionContext) -> WorkflowRunner:
    """Create a WorkflowRunner instance for testing."""
    return WorkflowRunner(workflow_path, default_context)


@pytest.fixture
def sample_workflow() -> dict:
    """Return a sample workflow structure for unit testing."""
    return {
        "jobs": {
            "setup": {
                "steps": [
                    {"name": "Create Dir", "run": "mkdir -p /tmp/test"},
                ]
            },
            "main": {
                "needs": ["setup"],
                "steps": [
                    {"name": "Run Command", "run": "echo 'Hello World'"},
                ]
            },
        },
        "on": {
            "execute": {
                "inputs": {
                    "resource": {
                        "type": "compute-clusters",
                        "label": "Resource",
                    },
                    "ray_version": {
                        "type": "string",
                        "default": "2.9.0",
                    },
                    "scheduler": {
                        "type": "boolean",
                        "default": False,
                    },
                }
            }
        },
    }
