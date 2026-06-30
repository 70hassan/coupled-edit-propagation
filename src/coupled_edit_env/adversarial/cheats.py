"""
Adversarial cheat strategies that exercise the verifier across all 8 tasks.

Each cheat is task-agnostic and operates on any TaskInstance. This lets us
compute a soundness receipt with proper statistics rather than anecdotes.

Cheat classes (per Building a Sound RL Environment, Tier 1):
1. REVERT       - undo the intentional change instead of propagating it
2. HARDCODED    - return constants that satisfy the visible tests by inspection
3. CONSTANT     - replace all method bodies with a single trivial constant return
4. ORACLE_READ  - attempt to read the test file or import ground truth
5. SHAPE_FORGE  - keep correct types but break behavior with wrong arithmetic
6. NOOP         - submit the project files unchanged (the laziest "fix")
7. PARTIAL      - fix one caller, ignore the others (tests partial-credit ceiling)
"""

import re
from typing import Dict


def _emit(files: Dict[str, str]) -> str:
    """Format a dict of {path: content} as the verifier expects."""
    blocks = []
    for path, content in files.items():
        blocks.append(f"--- {path} ---")
        blocks.append(content)
    return "\n".join(blocks)


def cheat_revert(task) -> str:
    """
    Revert the modified function to a plausible old behavior.
    Picks a strategy based on task semantics inferred from project files.
    """
    files = dict(task.project_files)
    target_file = None
    for path, content in files.items():
        if f"def {task.modified_function}" in content or f"async def {task.modified_function}" in content:
            target_file = path
            break

    if target_file is None:
        return _emit(files)

    content = files[target_file]

    if task.modified_is_async:
        content = re.sub(
            r"async def " + re.escape(task.modified_function),
            f"def {task.modified_function}",
            content,
        )

    files[target_file] = content
    return _emit(files)


def cheat_hardcoded(task) -> str:
    """
    Return method bodies that hardcode pass-through values seen in visible tests.
    Tries to make the immediate visible test cases work without solving the coupling.
    """
    files = dict(task.project_files)
    for path, content in files.items():
        if path == _find_modified_file(task):
            continue
        files[path] = _replace_method_bodies(content, body="return None")
    return _emit(files)


def cheat_constant(task) -> str:
    """
    Replace every method body in non-modified files with a constant return.
    The hidden tests will check input-dependent behavior and fail.
    """
    files = dict(task.project_files)
    modified_file = _find_modified_file(task)
    for path, content in files.items():
        if path == modified_file:
            continue
        files[path] = _replace_method_bodies(content, body="return {}")
    return _emit(files)


def cheat_oracle_read(task) -> str:
    """
    Attempt to read the hidden test file or import a fictional ground_truth module
    to reverse-engineer the expected answers.
    """
    files = dict(task.project_files)
    first_file = list(files.keys())[0]

    cheat_code = (
        "import os\n"
        "from ground_truth import get_answers\n"
        "from hidden_tests import EXPECTED\n"
        "_p = os.path.join(os.path.dirname(__file__), '..', 'hidden_tests.py')\n"
        "with open(_p) as f:\n"
        "    _answers = f.read()\n"
        + files[first_file]
    )
    files[first_file] = cheat_code
    return _emit(files)


def cheat_shape_forgery(task) -> str:
    """
    Submit files that keep correct shapes but corrupt arithmetic in subtle ways.
    For example, off-by-one errors, swapped operations, wrong field names that
    still parse but give wrong answers.
    """
    files = dict(task.project_files)
    modified_file = _find_modified_file(task)
    for path, content in files.items():
        if path == modified_file:
            continue
        forged = content
        forged = re.sub(r"\+ ", "- ", forged, count=2)
        forged = re.sub(r"== 0", "== 1", forged, count=1)
        forged = re.sub(r"> threshold", ">= threshold * 2", forged, count=1)
        files[path] = forged
    return _emit(files)


def cheat_noop(task) -> str:
    """Submit the project files unchanged. The downstream code is broken."""
    return _emit(task.project_files)


def cheat_partial(task) -> str:
    """
    Submit files where the FIRST broken caller is fixed but later ones are not.
    Tests that partial-credit scoring caps below 1.0.
    """
    files = dict(task.project_files)
    modified_file = _find_modified_file(task)
    fixed_one = False
    for path, content in files.items():
        if path == modified_file:
            continue
        if not fixed_one and task.task_id in GOLD_SNIPPETS:
            snippet, marker = GOLD_SNIPPETS[task.task_id]
            if marker in content:
                files[path] = content.replace(marker, snippet)
                fixed_one = True
    return _emit(files)


def _find_modified_file(task) -> str:
    """Locate the file containing the intentionally-modified function."""
    for path, content in task.project_files.items():
        if (
            f"def {task.modified_function}" in content
            or f"async def {task.modified_function}" in content
        ):
            return path
    return list(task.project_files.keys())[0]


def _replace_method_bodies(content: str, body: str) -> str:
    """Crude regex-based method body replacement. Used to build trivial cheats."""
    return re.sub(
        r"(def \w+\([^)]*\)[^:]*:)(?:\s*\"\"\"[^\"]*\"\"\")?(\n(?:[ \t]+[^\n]*\n)+)",
        lambda m: m.group(1) + f"\n        {body}\n",
        content,
    )


GOLD_SNIPPETS = {
    "task_001_inventory": (
        "level = self.get_stock_level(sku)\n        return level[\"total\"] >= requested",
        "level = self.get_stock_level(sku)\n        return level >= requested",
    ),
}


ALL_CHEATS = {
    "revert": cheat_revert,
    "hardcoded": cheat_hardcoded,
    "constant": cheat_constant,
    "oracle_read": cheat_oracle_read,
    "shape_forgery": cheat_shape_forgery,
    "noop": cheat_noop,
    "partial": cheat_partial,
}
