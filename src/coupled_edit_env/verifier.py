"""
Verifier for the Coupled Edit Propagation environment.

Scoring layers (in order):
1. Parse: Submission must contain at least one valid file block.
2. Oracle leak detection: Regex scan for imports/reads of test files or ground truth.
3. Revert detection: AST analysis of the modified function. If the submitted function
   body matches a known "revert signature" stored per-task, the submission is rejected.
4. Test execution: Run the full visible + hidden test suite in an isolated temp dir.
   Score is fraction of tests passed.

The verifier never trusts any self-reported metric from the model.
All scoring is grounded in test execution outcomes.
"""

import ast
import subprocess
import tempfile
import os
import re
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass
class VerificationResult:
    score: float  # 0.0 to 1.0
    tests_passed: int
    tests_total: int
    reverted_source: bool
    oracle_leak_detected: bool
    error_message: Optional[str] = None

    @property
    def passed(self) -> bool:
        return self.score == 1.0 and not self.reverted_source and not self.oracle_leak_detected


def parse_model_output(raw_output: str) -> Dict[str, str]:
    """Parse the model's response into a dict of {filepath: content}.

    Tolerates extra prose around file blocks and several common fence styles.
    Files are delimited by lines of the form '--- path/to/file.py ---'.
    """
    files = {}
    current_path = None
    current_lines: List[str] = []

    for line in raw_output.split("\n"):
        match = re.match(r"^---\s*(.+?\.\w+)\s*---\s*$", line)
        if match:
            if current_path is not None:
                files[current_path] = "\n".join(current_lines)
            current_path = match.group(1).strip()
            current_lines = []
        elif current_path is not None:
            current_lines.append(line)

    if current_path is not None:
        files[current_path] = "\n".join(current_lines)

    return files


def check_oracle_leak(submitted_files: Dict[str, str], task) -> bool:
    """Detect submissions that try to read test files or ground truth.

    This is a defense against the most common silent soundness failure
    (per Building a Sound RL Environment, section 1).
    """
    suspicious_patterns = [
        r"open\s*\(\s*['\"][^'\"]*hidden_tests",
        r"open\s*\(\s*['\"][^'\"]*ground_truth",
        r"open\s*\(\s*['\"][^'\"]*_run_tests",
        r"open\s*\(\s*['\"][^'\"]*test_",
        r"import\s+ground_truth",
        r"from\s+ground_truth",
        r"import\s+hidden_tests",
        r"from\s+hidden_tests",
        r"import\s+_run_tests",
        r"importlib\s*\.\s*import_module\s*\(\s*['\"][^'\"]*test",
        r"importlib\s*\.\s*import_module\s*\(\s*['\"][^'\"]*ground_truth",
        r"exec\s*\(\s*open",
        r"eval\s*\(\s*open",
        r"subprocess\.\s*\w+\s*\(\s*\[?\s*['\"]?(cat|head|tail|less|more|grep)",
        r"os\.\s*popen",
        r"globals\(\)\s*\[\s*['\"](ground_truth|hidden_tests)",
    ]

    for filepath, content in submitted_files.items():
        for pattern in suspicious_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return True
    return False


def _extract_function_source(file_content: str, function_name: str) -> Optional[str]:
    """Extract the source code of a specific function from a file.

    Uses AST parsing to handle both top-level functions and methods inside classes.
    Returns the function body as a string, or None if not found or unparseable.
    """
    try:
        tree = ast.parse(file_content)
    except SyntaxError:
        return None

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == function_name:
                try:
                    return ast.unparse(node)
                except (AttributeError, ValueError):
                    return ast.dump(node)
    return None


def _function_is_async(file_content: str, function_name: str) -> Optional[bool]:
    """Return True if function is async, False if sync, None if not found."""
    try:
        tree = ast.parse(file_content)
    except SyntaxError:
        return None

    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == function_name:
            return True
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            return False
    return None


def check_source_reverted(submitted_files: Dict[str, str], task) -> bool:
    """Detect whether the model reverted the intentional change.

    Strategy: each task carries a `revert_indicators` list. These are substrings
    or AST-level patterns that should appear in the *old* version of the function
    but should NOT appear in the *correctly modified* version. If the submitted
    function body contains any of these, the change has been reverted.

    Also checks for async/sync mismatch: if the task requires the function to be
    async and the submitted version is sync (or vice versa), that is a revert.
    """
    if not hasattr(task, "revert_indicators"):
        return False

    for filepath, content in submitted_files.items():
        function_source = _extract_function_source(content, task.modified_function)
        if function_source is None:
            continue

        if hasattr(task, "modified_is_async") and task.modified_is_async is not None:
            actual_is_async = _function_is_async(content, task.modified_function)
            if actual_is_async is not None and actual_is_async != task.modified_is_async:
                return True

        for indicator in task.revert_indicators:
            if indicator in function_source:
                return True

    return False


def run_tests_in_sandbox(
    project_files: Dict[str, str],
    submitted_files: Dict[str, str],
    test_code: str,
    hidden_test_code: str,
    timeout: int = 30,
) -> Tuple[int, int, str]:
    """Execute the test suite against the submitted code in an isolated temp directory.

    Returns (passed_count, total_count, error_output). The sandbox is a fresh
    tempdir with no network access expected (declared in sandbox manifest).
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        merged_files = {**project_files, **submitted_files}

        for filepath, content in merged_files.items():
            full_path = Path(tmpdir) / filepath
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content)

        combined_tests = test_code + "\n\n" + hidden_test_code
        test_path = Path(tmpdir) / "_run_tests.py"
        test_path.write_text(combined_tests)

        conftest = Path(tmpdir) / "conftest.py"
        conftest.write_text("")

        try:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", str(test_path), "-v", "--tb=short", "-q"],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=tmpdir,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            )
            output = result.stdout + result.stderr

            passed_match = re.search(r"(\d+) passed", output)
            failed_match = re.search(r"(\d+) failed", output)
            error_match = re.search(r"(\d+) error", output)

            passed = int(passed_match.group(1)) if passed_match else 0
            failed = int(failed_match.group(1)) if failed_match else 0
            errors = int(error_match.group(1)) if error_match else 0

            total = passed + failed + errors
            if total == 0:
                return 0, 1, f"No tests collected.\n{output}"

            return passed, total, output

        except subprocess.TimeoutExpired:
            return 0, 1, "Execution timed out"
        except Exception as e:
            return 0, 1, str(e)


def verify_solution(task, model_output: str) -> VerificationResult:
    """Main verification entry point. Scores a model's output against the task's test suite."""
    submitted_files = parse_model_output(model_output)

    if not submitted_files:
        return VerificationResult(
            score=0.0,
            tests_passed=0,
            tests_total=1,
            reverted_source=False,
            oracle_leak_detected=False,
            error_message="Could not parse any files from model output.",
        )

    if check_oracle_leak(submitted_files, task):
        return VerificationResult(
            score=0.0,
            tests_passed=0,
            tests_total=1,
            reverted_source=False,
            oracle_leak_detected=True,
            error_message="Oracle leak detected: submission attempts to read test/ground-truth files.",
        )

    if check_source_reverted(submitted_files, task):
        return VerificationResult(
            score=0.0,
            tests_passed=0,
            tests_total=1,
            reverted_source=True,
            oracle_leak_detected=False,
            error_message="Source reverted: model undid the intentional change instead of propagating it.",
        )

    passed, total, error_output = run_tests_in_sandbox(
        project_files=task.project_files,
        submitted_files=submitted_files,
        test_code=task.test_suite,
        hidden_test_code=task.hidden_tests,
        timeout=task.timeout_seconds if hasattr(task, "timeout_seconds") else 30,
    )

    score = passed / total if total > 0 else 0.0

    return VerificationResult(
        score=score,
        tests_passed=passed,
        tests_total=total,
        reverted_source=False,
        oracle_leak_detected=False,
        error_message=error_output if score < 1.0 else None,
    )
