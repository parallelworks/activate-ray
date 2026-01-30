#!/usr/bin/env python3
"""
Local Workflow Runner for Activate Batch Submitter

Executes workflow.yaml locally for testing without the ACTIVATE platform.
Simulates SSH execution by running commands on the local machine.

Usage:
    python tools/workflow_runner.py workflow.yaml
    python tools/workflow_runner.py workflow.yaml --dry-run
    python tools/workflow_runner.py workflow.yaml -i commands="hostname\ndate"
    python tools/workflow_runner.py workflow.yaml --work-dir /tmp/test-run -v
"""

import argparse
import os
import re
import subprocess
import sys
import tempfile
import shutil
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    print("Error: PyYAML is required. Install with: pip install pyyaml", file=sys.stderr)
    sys.exit(1)


@dataclass
class StepResult:
    """Result from executing a step."""
    success: bool = True
    outputs: dict[str, str] = field(default_factory=dict)
    stdout: str = ""
    stderr: str = ""
    error: str | None = None


@dataclass
class JobResult:
    """Result from executing a job."""
    success: bool = True
    step_results: list[StepResult] = field(default_factory=list)
    error: str | None = None


@dataclass
class ExecutionContext:
    """Context for workflow execution."""
    inputs: dict[str, Any]
    env_vars: dict[str, str]
    work_dir: Path
    dry_run: bool = False
    verbose: bool = False
    job_outputs: dict[str, JobResult] = field(default_factory=dict)


class WorkflowRunner:
    """Runs ACTIVATE workflows locally for testing."""

    def __init__(self, workflow_path: Path, context: ExecutionContext):
        self.workflow_path = workflow_path
        self.workflow_dir = workflow_path.parent
        self.context = context
        self.workflow: dict[str, Any] = {}

    def load_workflow(self) -> dict[str, Any]:
        """Load and parse the workflow YAML file."""
        with open(self.workflow_path) as f:
            self.workflow = yaml.safe_load(f)
        return self.workflow

    def substitute_variables(self, value: Any) -> Any:
        """Recursively substitute ${{ ... }} variables in a value."""
        if isinstance(value, str):
            return self._substitute_string(value)
        elif isinstance(value, dict):
            return {k: self.substitute_variables(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [self.substitute_variables(item) for item in value]
        return value

    def _substitute_string(self, text: str) -> str:
        """Substitute variables in a string."""
        pattern = r'\$\{\{\s*(.+?)\s*\}\}'

        def replacer(match: re.Match) -> str:
            expr = match.group(1).strip()
            result = self._evaluate_expression(expr)
            return str(result) if result is not None else ""

        return re.sub(pattern, replacer, text)

    def _evaluate_expression(self, expr: str) -> Any:
        """Evaluate a template expression."""
        # Handle comparison expressions
        if ' != ' in expr:
            left, right = expr.split(' != ', 1)
            left_val = self._evaluate_expression(left.strip())
            right_val = self._parse_literal(right.strip())
            return left_val != right_val

        if ' == ' in expr:
            left, right = expr.split(' == ', 1)
            left_val = self._evaluate_expression(left.strip())
            right_val = self._parse_literal(right.strip())
            return left_val == right_val

        if ' || ' in expr:
            parts = expr.split(' || ')
            return any(self._evaluate_expression(p.strip()) for p in parts)

        if ' && ' in expr:
            parts = expr.split(' && ')
            return all(self._evaluate_expression(p.strip()) for p in parts)

        # Handle property access
        if expr.startswith('inputs.'):
            return self._get_nested_value(self.context.inputs, expr[7:])

        if expr.startswith('env.'):
            env_name = expr[4:]
            return self.context.env_vars.get(env_name, os.environ.get(env_name, ''))

        if expr.startswith('needs.'):
            # needs.job_name.outputs.output_name or needs.job_name.steps.step_id.outputs.output_name
            parts = expr[6:].split('.')
            if len(parts) >= 1:
                job_name = parts[0]
                job_result = self.context.job_outputs.get(job_name)
                if job_result and len(parts) >= 3 and parts[1] == 'outputs':
                    output_name = '.'.join(parts[2:])
                    for step_result in job_result.step_results:
                        if output_name in step_result.outputs:
                            return step_result.outputs[output_name]
            return ''

        # Return expression as-is if not recognized
        return expr

    def _get_nested_value(self, obj: dict, path: str) -> Any:
        """Get a nested value from a dict using dot notation."""
        parts = path.split('.')
        current = obj
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part, '')
            else:
                return ''
        return current

    def _parse_literal(self, value: str) -> Any:
        """Parse a literal value from an expression."""
        if (value.startswith("'") and value.endswith("'")) or \
           (value.startswith('"') and value.endswith('"')):
            return value[1:-1]
        if value == 'true':
            return True
        if value == 'false':
            return False
        if value == '':
            return ''
        try:
            return int(value)
        except ValueError:
            pass
        return value

    def get_job_order(self) -> list[str]:
        """Return jobs in topologically sorted order based on dependencies."""
        jobs = self.workflow.get('jobs', {})

        # Build dependency graph
        dependencies: dict[str, set[str]] = {}
        for job_name, job_config in jobs.items():
            needs = job_config.get('needs', [])
            if isinstance(needs, str):
                needs = [needs]
            dependencies[job_name] = set(needs)

        # Topological sort (Kahn's algorithm)
        result: list[str] = []
        no_deps = [j for j, deps in dependencies.items() if not deps]

        while no_deps:
            job = no_deps.pop(0)
            result.append(job)

            for other_job, deps in dependencies.items():
                if job in deps:
                    deps.remove(job)
                    if not deps and other_job not in result:
                        no_deps.append(other_job)

        if len(result) != len(jobs):
            remaining = set(jobs.keys()) - set(result)
            raise ValueError(f"Circular dependency detected in jobs: {remaining}")

        return result

    def run_job(self, job_name: str, job_config: dict) -> JobResult:
        """Execute a single job."""
        print(f"\n{'='*60}")
        print(f"JOB: {job_name}")
        print(f"{'='*60}")

        result = JobResult()
        steps = job_config.get('steps', [])

        # Get working directory for job
        work_dir = job_config.get('working-directory', '')
        if work_dir:
            work_dir = self.substitute_variables(work_dir)
            # For local execution, use a subdirectory of work_dir
            job_work_dir = self.context.work_dir / work_dir.lstrip('/')
        else:
            job_work_dir = self.context.work_dir

        job_work_dir.mkdir(parents=True, exist_ok=True)
        print(f"Working directory: {job_work_dir}")

        # Check for SSH config (we'll run locally instead)
        ssh_config = job_config.get('ssh', {})
        if ssh_config:
            remote_host = self.substitute_variables(ssh_config.get('remoteHost', 'localhost'))
            print(f"[LOCAL] Simulating SSH to {remote_host}")

        for i, step in enumerate(steps):
            step_name = step.get('name', f'Step {i+1}')
            print(f"\n  [{i+1}/{len(steps)}] {step_name}")

            try:
                step_result = self.run_step(step, job_work_dir)
                result.step_results.append(step_result)

                if not step_result.success:
                    result.success = False
                    result.error = step_result.error
                    print(f"    ERROR: {step_result.error}")
                    break

            except Exception as e:
                result.success = False
                result.error = str(e)
                result.step_results.append(StepResult(success=False, error=str(e)))
                print(f"    EXCEPTION: {e}")
                break

        return result

    def run_step(self, step: dict, work_dir: Path) -> StepResult:
        """Execute a single step."""
        result = StepResult()

        if 'run' not in step:
            print("    [SKIP] No 'run' command in step")
            return result

        # Substitute variables in the command
        command = self.substitute_variables(step['run'])

        if self.context.verbose:
            print(f"    Command:\n{self._indent(command)}")
        else:
            # Show abbreviated command
            lines = command.strip().split('\n')
            if len(lines) > 3:
                print(f"    Command: {lines[0][:50]}... ({len(lines)} lines)")
            else:
                print(f"    Command: {lines[0][:60]}...")

        if self.context.dry_run:
            print("    [DRY-RUN] Would execute command")
            return result

        # Create outputs file for the command
        outputs_file = work_dir / 'step_outputs.txt'

        env = {
            **os.environ,
            **self.context.env_vars,
            'OUTPUTS': str(outputs_file),
            'PWD': str(work_dir),
        }

        try:
            proc = subprocess.run(
                ['bash', '-c', command],
                cwd=work_dir,
                env=env,
                capture_output=True,
                text=True,
                timeout=300
            )

            result.stdout = proc.stdout
            result.stderr = proc.stderr

            if self.context.verbose:
                if proc.stdout:
                    print(f"    STDOUT:\n{self._indent(proc.stdout)}")
                if proc.stderr:
                    print(f"    STDERR:\n{self._indent(proc.stderr)}")
            else:
                # Show condensed output
                if proc.stdout:
                    lines = proc.stdout.strip().split('\n')
                    if len(lines) <= 5:
                        for line in lines:
                            print(f"      {line[:80]}")
                    else:
                        print(f"      ... ({len(lines)} lines of output)")

            if proc.returncode != 0:
                result.success = False
                result.error = f"Command failed with exit code {proc.returncode}"
                if proc.stderr:
                    result.error += f": {proc.stderr[:200]}"
                return result

            # Parse outputs
            if outputs_file.exists():
                for line in outputs_file.read_text().splitlines():
                    if '=' in line:
                        key, value = line.split('=', 1)
                        result.outputs[key.strip()] = value.strip()

            print("    [OK]")

        except subprocess.TimeoutExpired:
            result.success = False
            result.error = "Command timed out after 300 seconds"
        except Exception as e:
            result.success = False
            result.error = str(e)

        return result

    def _indent(self, text: str, spaces: int = 6) -> str:
        """Indent text for display."""
        prefix = ' ' * spaces
        return '\n'.join(prefix + line for line in text.splitlines())

    def run(self, only_jobs: list[str] | None = None) -> bool:
        """Execute the workflow and return success status.

        Args:
            only_jobs: If specified, only run these jobs (and skip dependency checks)
        """
        self.load_workflow()

        print(f"\n{'='*60}")
        print("RAY CLUSTER WORKFLOW - LOCAL EXECUTION")
        print(f"{'='*60}")
        print(f"Workflow: {self.workflow_path}")
        print(f"Work Dir: {self.context.work_dir}")
        print(f"Mode: {'DRY-RUN' if self.context.dry_run else 'EXECUTE'}")

        if self.context.verbose:
            print(f"\nInputs: {self.context.inputs}")

        # Get job execution order
        job_order = self.get_job_order()

        # Filter jobs if specified
        if only_jobs:
            # Validate requested jobs exist
            available_jobs = set(self.workflow.get('jobs', {}).keys())
            invalid_jobs = set(only_jobs) - available_jobs
            if invalid_jobs:
                print(f"\nError: Unknown jobs: {', '.join(invalid_jobs)}")
                print(f"Available jobs: {', '.join(available_jobs)}")
                return False
            job_order = [j for j in job_order if j in only_jobs]
            print(f"\nRunning selected jobs: {' -> '.join(job_order)}")
        else:
            print(f"\nJobs to execute: {' -> '.join(job_order)}")

        # Execute jobs
        all_success = True
        for job_name in job_order:
            job_config = self.workflow['jobs'][job_name]

            # Check dependencies (skip if running specific jobs)
            if not only_jobs:
                needs = job_config.get('needs', [])
                if isinstance(needs, str):
                    needs = [needs]

                deps_ok = all(
                    self.context.job_outputs.get(dep, JobResult()).success
                    for dep in needs
                )

                if not deps_ok:
                    print(f"\n[SKIP] Job {job_name} - dependency failed")
                    self.context.job_outputs[job_name] = JobResult(success=False, error="Dependency failed")
                    all_success = False
                    continue

            job_result = self.run_job(job_name, job_config)
            self.context.job_outputs[job_name] = job_result

            if not job_result.success:
                all_success = False

        # Summary
        print(f"\n{'='*60}")
        print("EXECUTION SUMMARY")
        print(f"{'='*60}")
        for job_name, job_result in self.context.job_outputs.items():
            status = "PASS" if job_result.success else "FAIL"
            print(f"  {job_name}: {status}")
            if job_result.error:
                print(f"    Error: {job_result.error}")

        print(f"\nOverall: {'SUCCESS' if all_success else 'FAILED'}")
        return all_success


def get_default_inputs(workflow: dict) -> dict[str, Any]:
    """Extract default input values from workflow definition."""
    defaults: dict[str, Any] = {}
    inputs_def = workflow.get('on', {}).get('execute', {}).get('inputs', {})

    def extract_defaults(prefix: str, obj: dict) -> None:
        for key, config in obj.items():
            full_key = f"{prefix}.{key}" if prefix else key

            if isinstance(config, dict):
                if 'default' in config:
                    defaults[full_key] = config['default']
                if config.get('type') == 'group' and 'items' in config:
                    extract_defaults(full_key, config['items'])

    extract_defaults('', inputs_def)
    return defaults


def parse_input_arg(arg: str) -> tuple[str, Any]:
    """Parse an input argument like 'key=value'."""
    if '=' not in arg:
        raise ValueError(f"Invalid input format: {arg} (expected key=value)")
    key, value = arg.split('=', 1)

    # Parse value type
    if value.lower() == 'true':
        value = True
    elif value.lower() == 'false':
        value = False
    elif value.isdigit():
        value = int(value)

    return key, value


def build_nested_dict(flat_inputs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Build a nested dict from flat key=value pairs."""
    result: dict[str, Any] = {}
    for key, value in flat_inputs:
        parts = key.split('.')
        current = result
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        current[parts[-1]] = value
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Run ACTIVATE batch workflow locally for testing',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Basic execution
  python tools/workflow_runner.py workflow.yaml

  # Dry-run mode (show what would execute)
  python tools/workflow_runner.py workflow.yaml --dry-run

  # Run only specific jobs
  python tools/workflow_runner.py workflow.yaml --job setup
  python tools/workflow_runner.py workflow.yaml --job setup --job wait_for_service

  # List available jobs
  python tools/workflow_runner.py workflow.yaml --list-jobs

  # Custom input values
  python tools/workflow_runner.py workflow.yaml -i "ray_version=2.10.0"

  # Verbose output with custom work directory
  python tools/workflow_runner.py workflow.yaml -v --work-dir /tmp/test-run

  # Keep working directory for inspection
  python tools/workflow_runner.py workflow.yaml --keep-work-dir
'''
    )

    parser.add_argument('workflow', type=Path, help='Path to workflow.yaml')
    parser.add_argument('-i', '--input', action='append', dest='inputs', default=[],
                        help='Input value (e.g., ray_version="2.10.0")')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be executed without running')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Verbose output')
    parser.add_argument('--work-dir', type=Path,
                        help='Working directory (default: temp dir)')
    parser.add_argument('--keep-work-dir', action='store_true',
                        help='Keep working directory after execution')
    parser.add_argument('--job', action='append', dest='jobs', default=[],
                        help='Run only specific job(s) (can be repeated)')
    parser.add_argument('--list-jobs', action='store_true',
                        help='List available jobs and exit')

    args = parser.parse_args()

    if not args.workflow.exists():
        print(f"Error: Workflow not found: {args.workflow}", file=sys.stderr)
        return 1

    # Load workflow to get defaults
    with open(args.workflow) as f:
        workflow = yaml.safe_load(f)

    # Handle --list-jobs
    if args.list_jobs:
        jobs = workflow.get('jobs', {})
        print(f"Available jobs in {args.workflow}:")
        for job_name, job_config in jobs.items():
            needs = job_config.get('needs', [])
            steps = job_config.get('steps', [])
            needs_str = f" (needs: {', '.join(needs)})" if needs else ""
            print(f"  - {job_name}: {len(steps)} steps{needs_str}")
        return 0

    # Build inputs from defaults + command line
    default_inputs = get_default_inputs(workflow)
    cli_inputs = [parse_input_arg(inp) for inp in args.inputs]

    # Merge defaults with CLI inputs
    all_inputs = build_nested_dict(
        [(k, v) for k, v in default_inputs.items()] +
        cli_inputs
    )

    # Add required mock values for resource if not provided
    if 'resource' not in all_inputs:
        all_inputs['resource'] = {}
    if 'ip' not in all_inputs['resource']:
        all_inputs['resource']['ip'] = 'localhost'
    if 'schedulerType' not in all_inputs['resource']:
        all_inputs['resource']['schedulerType'] = ''

    # Create working directory
    job_id = str(uuid.uuid4())[:8]
    if args.work_dir:
        work_dir = args.work_dir
        work_dir.mkdir(parents=True, exist_ok=True)
        cleanup_work_dir = False
    else:
        work_dir = Path(tempfile.mkdtemp(prefix=f'batch-workflow-{job_id}-'))
        cleanup_work_dir = not args.keep_work_dir

    try:
        # Set up environment variables
        env_vars = {
            'PW_JOB_ID': job_id,
            'PW_PARENT_JOB_DIR': str(work_dir),
            'PW_USER': os.environ.get('USER', 'testuser'),
            'HOME': os.environ.get('HOME', '/tmp'),
        }

        context = ExecutionContext(
            inputs=all_inputs,
            env_vars=env_vars,
            work_dir=work_dir,
            dry_run=args.dry_run,
            verbose=args.verbose,
        )

        runner = WorkflowRunner(args.workflow, context)
        success = runner.run(only_jobs=args.jobs if args.jobs else None)

        print(f"\nWork directory: {work_dir}")
        if cleanup_work_dir:
            print("(will be cleaned up, use --keep-work-dir to preserve)")
        else:
            print("(preserved for inspection)")

        return 0 if success else 1

    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1

    finally:
        if cleanup_work_dir and work_dir.exists():
            shutil.rmtree(work_dir)


if __name__ == '__main__':
    sys.exit(main())
