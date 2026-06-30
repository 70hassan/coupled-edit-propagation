"""
Task 002: Job Scheduler - Exception handling contract change

Scenario: A job scheduler where `submit_job` was changed from returning None
on failure to raising a custom exception. Multiple callers that checked for None
returns are now broken because they don't catch the exception.

Difficulty: Easy-Medium
Coupling type: Error-handling contract change
"""

from coupled_edit_env.types import TaskInstance


def create_task() -> TaskInstance:
    project_files = {
        "scheduler/core.py": '''
class JobValidationError(Exception):
    """Raised when a job fails validation."""
    def __init__(self, job_id: str, reason: str):
        self.job_id = job_id
        self.reason = reason
        super().__init__(f"Job {job_id} invalid: {reason}")


class JobScheduler:
    def __init__(self, max_concurrent: int = 5):
        self.max_concurrent = max_concurrent
        self._queue = []
        self._running = []
        self._completed = []

    def submit_job(self, job_id: str, priority: int, resources: dict) -> dict:
        """
        MODIFIED: Now raises JobValidationError on invalid jobs instead of
        returning None. On success returns {"queued": True, "position": int}.
        Previously returned None on failure and a position int on success.
        """
        if not job_id or not job_id.strip():
            raise JobValidationError(job_id, "empty job ID")
        if priority < 0 or priority > 10:
            raise JobValidationError(job_id, f"priority {priority} out of range 0-10")
        if not resources or "cpu" not in resources:
            raise JobValidationError(job_id, "missing cpu resource spec")
        if resources["cpu"] > 16:
            raise JobValidationError(job_id, f"cpu request {resources['cpu']} exceeds limit of 16")

        position = len(self._queue)
        self._queue.append({
            "id": job_id,
            "priority": priority,
            "resources": resources,
        })
        self._queue.sort(key=lambda j: j["priority"], reverse=True)
        actual_position = next(i for i, j in enumerate(self._queue) if j["id"] == job_id)
        return {"queued": True, "position": actual_position}

    def get_queue_length(self) -> int:
        return len(self._queue)
''',
        "scheduler/batch.py": '''
from scheduler.core import JobScheduler


class BatchSubmitter:
    def __init__(self, scheduler: JobScheduler):
        self.scheduler = scheduler
        self.results = []

    def submit_batch(self, jobs: list[dict]) -> dict:
        """Submit multiple jobs, collecting successes and failures."""
        succeeded = []
        failed = []

        for job in jobs:
            result = self.scheduler.submit_job(
                job["id"], job.get("priority", 5), job.get("resources", {})
            )
            if result is None:
                failed.append(job["id"])
            else:
                succeeded.append(job["id"])

        return {
            "submitted": len(succeeded),
            "failed": len(failed),
            "failed_ids": failed,
        }

    def submit_safe(self, job_id: str, priority: int, resources: dict) -> tuple:
        """Submit a single job, returning (success: bool, result_or_error: str)."""
        result = self.scheduler.submit_job(job_id, priority, resources)
        if result is None:
            return (False, "submission failed")
        return (True, f"queued at position {result}")

    def retry_until_accepted(self, job_id: str, priorities: list[int], resources: dict) -> int:
        """Try submitting with decreasing priority until accepted. Returns final priority or -1."""
        for p in sorted(priorities, reverse=True):
            result = self.scheduler.submit_job(job_id, p, resources)
            if result is not None:
                return p
        return -1
''',
    }

    modified_function = "submit_job"

    test_suite = '''
import sys
sys.path.insert(0, ".")
from scheduler.core import JobScheduler, JobValidationError


def test_submit_valid_job():
    s = JobScheduler()
    result = s.submit_job("job1", 5, {"cpu": 4, "memory": "8G"})
    assert result["queued"] is True
    assert "position" in result


def test_submit_invalid_raises():
    s = JobScheduler()
    try:
        s.submit_job("", 5, {"cpu": 4})
        assert False, "Should have raised"
    except JobValidationError as e:
        assert "empty" in str(e)


def test_submit_bad_priority_raises():
    s = JobScheduler()
    try:
        s.submit_job("job2", 99, {"cpu": 4})
        assert False, "Should have raised"
    except JobValidationError as e:
        assert "out of range" in str(e)
'''

    hidden_tests = '''
import sys
sys.path.insert(0, ".")
from scheduler.core import JobScheduler, JobValidationError
from scheduler.batch import BatchSubmitter


def test_batch_submit_mixed():
    s = JobScheduler()
    bs = BatchSubmitter(s)
    jobs = [
        {"id": "ok1", "priority": 3, "resources": {"cpu": 2}},
        {"id": "", "priority": 5, "resources": {"cpu": 1}},
        {"id": "ok2", "priority": 7, "resources": {"cpu": 4}},
        {"id": "bad", "priority": 5, "resources": {}},
    ]
    result = bs.submit_batch(jobs)
    assert result["submitted"] == 2
    assert result["failed"] == 2
    assert "" in result["failed_ids"] or "bad" in result["failed_ids"]


def test_batch_submit_all_valid():
    s = JobScheduler()
    bs = BatchSubmitter(s)
    jobs = [
        {"id": "a", "priority": 1, "resources": {"cpu": 1}},
        {"id": "b", "priority": 2, "resources": {"cpu": 2}},
    ]
    result = bs.submit_batch(jobs)
    assert result["submitted"] == 2
    assert result["failed"] == 0


def test_submit_safe_valid():
    s = JobScheduler()
    bs = BatchSubmitter(s)
    success, msg = bs.submit_safe("x", 5, {"cpu": 2})
    assert success is True
    assert "position" in msg


def test_submit_safe_invalid():
    s = JobScheduler()
    bs = BatchSubmitter(s)
    success, msg = bs.submit_safe("", 5, {"cpu": 2})
    assert success is False
    assert "failed" in msg.lower() or "invalid" in msg.lower() or "error" in msg.lower()


def test_retry_until_accepted_immediate():
    s = JobScheduler()
    bs = BatchSubmitter(s)
    result = bs.retry_until_accepted("retryable", [3, 5, 7], {"cpu": 4})
    assert result == 7


def test_retry_until_accepted_no_resources():
    s = JobScheduler()
    bs = BatchSubmitter(s)
    result = bs.retry_until_accepted("nope", [3, 5, 7], {})
    assert result == -1
'''

    ground_truth_repairs = {
        "scheduler/batch.py": "All three methods need try/except around submit_job to catch JobValidationError",
    }

    return TaskInstance(
        task_id="task_002_scheduler",
        instruction=(
            "The function `submit_job` in scheduler/core.py was intentionally changed. "
            "It now raises JobValidationError on invalid input instead of returning None. "
            "On success it returns a dict {'queued': True, 'position': int} instead of just an int. "
            "This change is correct and must NOT be reverted. "
            "Fix all code in scheduler/batch.py that relies on the old None-return contract."
        ),
        project_files=project_files,
        modified_function=modified_function,
        test_suite=test_suite,
        hidden_tests=hidden_tests,
        ground_truth_repairs=ground_truth_repairs,
        difficulty="easy-medium",
        revert_indicators=[
            "return None",
            "-> int:",
            "return position",
        ],
        modified_is_async=False,
    )
