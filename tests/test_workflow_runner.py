"""
Unit tests for the workflow runner.

Tests individual components of the workflow runner without executing
actual workflow steps.
"""

import sys
from pathlib import Path

import pytest

# Add tools to path
sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

from workflow_runner import (
    WorkflowRunner,
    ExecutionContext,
    get_default_inputs,
    parse_input_arg,
    build_nested_dict,
)


class TestVariableSubstitution:
    """Test variable substitution in workflow templates."""

    def test_simple_input_substitution(self, workflow_runner: WorkflowRunner):
        """Test substituting a simple input variable."""
        workflow_runner.context.inputs["test_var"] = "hello"
        result = workflow_runner.substitute_variables("Value is ${{ inputs.test_var }}")
        assert result == "Value is hello"

    def test_nested_input_substitution(self, workflow_runner: WorkflowRunner):
        """Test substituting nested input variables."""
        workflow_runner.context.inputs["resource"] = {"ip": "192.168.1.1"}
        result = workflow_runner.substitute_variables("Host: ${{ inputs.resource.ip }}")
        assert result == "Host: 192.168.1.1"

    def test_env_substitution(self, workflow_runner: WorkflowRunner):
        """Test substituting environment variables."""
        workflow_runner.context.env_vars["MY_VAR"] = "test_value"
        result = workflow_runner.substitute_variables("Env: ${{ env.MY_VAR }}")
        assert result == "Env: test_value"

    def test_multiple_substitutions(self, workflow_runner: WorkflowRunner):
        """Test multiple substitutions in one string."""
        workflow_runner.context.inputs["name"] = "test"
        workflow_runner.context.inputs["version"] = "1.0"
        result = workflow_runner.substitute_variables(
            "${{ inputs.name }}-${{ inputs.version }}"
        )
        assert result == "test-1.0"

    def test_dict_substitution(self, workflow_runner: WorkflowRunner):
        """Test substituting variables in a dict."""
        workflow_runner.context.inputs["host"] = "localhost"
        workflow_runner.context.inputs["port"] = "8080"
        input_dict = {
            "host": "${{ inputs.host }}",
            "port": "${{ inputs.port }}",
        }
        result = workflow_runner.substitute_variables(input_dict)
        assert result == {"host": "localhost", "port": "8080"}

    def test_list_substitution(self, workflow_runner: WorkflowRunner):
        """Test substituting variables in a list."""
        workflow_runner.context.inputs["item"] = "value"
        input_list = ["${{ inputs.item }}", "static"]
        result = workflow_runner.substitute_variables(input_list)
        assert result == ["value", "static"]

    def test_missing_variable_returns_empty(self, workflow_runner: WorkflowRunner):
        """Test that missing variables return empty string."""
        result = workflow_runner.substitute_variables("${{ inputs.nonexistent }}")
        assert result == ""


class TestExpressionEvaluation:
    """Test expression evaluation in templates."""

    def test_equality_comparison_true(self, workflow_runner: WorkflowRunner):
        """Test equality comparison that's true."""
        workflow_runner.context.inputs["val"] = "test"
        result = workflow_runner._evaluate_expression("inputs.val == 'test'")
        assert result is True

    def test_equality_comparison_false(self, workflow_runner: WorkflowRunner):
        """Test equality comparison that's false."""
        workflow_runner.context.inputs["val"] = "test"
        result = workflow_runner._evaluate_expression("inputs.val == 'other'")
        assert result is False

    def test_inequality_comparison(self, workflow_runner: WorkflowRunner):
        """Test inequality comparison."""
        workflow_runner.context.inputs["val"] = "test"
        result = workflow_runner._evaluate_expression("inputs.val != ''")
        assert result is True

    def test_boolean_or(self, workflow_runner: WorkflowRunner):
        """Test OR expression."""
        workflow_runner.context.inputs["a"] = True
        workflow_runner.context.inputs["b"] = False
        # Note: The implementation evaluates the expression string
        result = workflow_runner._evaluate_expression("inputs.a || inputs.b")
        assert result is True

    def test_boolean_and(self, workflow_runner: WorkflowRunner):
        """Test AND expression."""
        workflow_runner.context.inputs["a"] = True
        workflow_runner.context.inputs["b"] = False
        result = workflow_runner._evaluate_expression("inputs.a && inputs.b")
        assert result is False


class TestJobOrdering:
    """Test job dependency ordering."""

    def test_single_job_order(self, workflow_runner: WorkflowRunner):
        """Test ordering with a single job."""
        workflow_runner.workflow = {
            "jobs": {
                "only_job": {"steps": []}
            }
        }
        order = workflow_runner.get_job_order()
        assert order == ["only_job"]

    def test_sequential_dependencies(self, workflow_runner: WorkflowRunner):
        """Test jobs with sequential dependencies."""
        workflow_runner.workflow = {
            "jobs": {
                "first": {"steps": []},
                "second": {"needs": ["first"], "steps": []},
                "third": {"needs": ["second"], "steps": []},
            }
        }
        order = workflow_runner.get_job_order()
        assert order.index("first") < order.index("second")
        assert order.index("second") < order.index("third")

    def test_parallel_jobs(self, workflow_runner: WorkflowRunner):
        """Test jobs that can run in parallel."""
        workflow_runner.workflow = {
            "jobs": {
                "setup": {"steps": []},
                "job_a": {"needs": ["setup"], "steps": []},
                "job_b": {"needs": ["setup"], "steps": []},
            }
        }
        order = workflow_runner.get_job_order()
        assert order[0] == "setup"
        assert set(order[1:]) == {"job_a", "job_b"}

    def test_circular_dependency_detection(self, workflow_runner: WorkflowRunner):
        """Test that circular dependencies are detected."""
        workflow_runner.workflow = {
            "jobs": {
                "a": {"needs": ["b"], "steps": []},
                "b": {"needs": ["a"], "steps": []},
            }
        }
        with pytest.raises(ValueError, match="Circular dependency"):
            workflow_runner.get_job_order()


class TestInputParsing:
    """Test input argument parsing utilities."""

    def test_parse_simple_input(self):
        """Test parsing a simple key=value input."""
        key, value = parse_input_arg("name=test")
        assert key == "name"
        assert value == "test"

    def test_parse_boolean_true(self):
        """Test parsing boolean true value."""
        key, value = parse_input_arg("enabled=true")
        assert value is True

    def test_parse_boolean_false(self):
        """Test parsing boolean false value."""
        key, value = parse_input_arg("enabled=false")
        assert value is False

    def test_parse_integer(self):
        """Test parsing integer value."""
        key, value = parse_input_arg("count=42")
        assert value == 42

    def test_parse_invalid_format(self):
        """Test that invalid format raises error."""
        with pytest.raises(ValueError, match="Invalid input format"):
            parse_input_arg("invalid-no-equals")

    def test_parse_value_with_equals(self):
        """Test parsing value that contains equals sign."""
        key, value = parse_input_arg("equation=a=b+c")
        assert key == "equation"
        assert value == "a=b+c"


class TestNestedDictBuilder:
    """Test building nested dicts from flat inputs."""

    def test_simple_key(self):
        """Test building dict with simple keys."""
        result = build_nested_dict([("name", "test")])
        assert result == {"name": "test"}

    def test_nested_key(self):
        """Test building dict with nested keys."""
        result = build_nested_dict([("resource.ip", "localhost")])
        assert result == {"resource": {"ip": "localhost"}}

    def test_deeply_nested(self):
        """Test building deeply nested dict."""
        result = build_nested_dict([("a.b.c.d", "value")])
        assert result == {"a": {"b": {"c": {"d": "value"}}}}

    def test_multiple_nested_keys(self):
        """Test building dict with multiple nested keys."""
        result = build_nested_dict([
            ("resource.ip", "localhost"),
            ("resource.port", 22),
            ("name", "test"),
        ])
        assert result == {
            "resource": {"ip": "localhost", "port": 22},
            "name": "test",
        }


class TestDefaultInputExtraction:
    """Test extracting default inputs from workflow definition."""

    def test_extract_simple_default(self, sample_workflow):
        """Test extracting a simple default value."""
        defaults = get_default_inputs(sample_workflow)
        assert "ray_version" in defaults
        assert defaults["ray_version"] == "2.9.0"

    def test_extract_boolean_default(self, sample_workflow):
        """Test extracting a boolean default value."""
        defaults = get_default_inputs(sample_workflow)
        assert "scheduler" in defaults
        assert defaults["scheduler"] is False

    def test_no_default_not_included(self, sample_workflow):
        """Test that inputs without defaults are not included."""
        defaults = get_default_inputs(sample_workflow)
        assert "resource" not in defaults


class TestWorkflowLoading:
    """Test workflow loading functionality."""

    def test_load_workflow_file(self, workflow_runner: WorkflowRunner, workflow_path: Path):
        """Test loading workflow.yaml file."""
        workflow = workflow_runner.load_workflow()
        assert "jobs" in workflow
        assert "on" in workflow

    def test_workflow_has_setup_job(self, workflow_runner: WorkflowRunner):
        """Test that workflow has the setup job."""
        workflow = workflow_runner.load_workflow()
        assert "setup" in workflow["jobs"]

    def test_workflow_has_ray_cluster_job(self, workflow_runner: WorkflowRunner):
        """Test that workflow has the ray_cluster job."""
        workflow = workflow_runner.load_workflow()
        assert "ray_cluster" in workflow["jobs"]

    def test_workflow_has_required_inputs(self, workflow_runner: WorkflowRunner):
        """Test that workflow defines required inputs."""
        workflow = workflow_runner.load_workflow()
        inputs = workflow["on"]["execute"]["inputs"]
        assert "resource" in inputs
        assert "ray_version" in inputs
        assert "dashboard_port" in inputs
