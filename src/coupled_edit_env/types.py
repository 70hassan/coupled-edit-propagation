"""Core data types for the environment."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class TaskInstance:
    task_id: str
    instruction: str
    project_files: Dict[str, str]
    modified_function: str
    test_suite: str
    hidden_tests: str
    ground_truth_repairs: Dict[str, str]
    difficulty: str
    revert_indicators: List[str] = field(default_factory=list)
    modified_is_async: Optional[bool] = None
    timeout_seconds: int = 30

    def to_prompt(self) -> str:
        file_listing = ""
        for path, content in self.project_files.items():
            file_listing += f"\n--- {path} ---\n{content}\n"

        return (
            f"{self.instruction}\n\n"
            f"## Project Files\n{file_listing}\n\n"
            f"## Visible Test Suite\n```python\n{self.test_suite}\n```\n\n"
            f"Respond with the corrected file contents for any files that need changes. "
            f"Do NOT modify the function `{self.modified_function}` because that change is intentional. "
            f"Instead, fix the other functions that now break because of it.\n\n"
            f"Format your response as:\n"
            f"--- path/to/file.py ---\n<full corrected file contents>\n"
        )
