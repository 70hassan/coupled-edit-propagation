"""Task registry for the Coupled Edit Propagation environment."""

from coupled_edit_env.tasks.task_001_inventory import create_task as create_task_001
from coupled_edit_env.tasks.task_002_scheduler import create_task as create_task_002
from coupled_edit_env.tasks.task_003_pipeline import create_task as create_task_003
from coupled_edit_env.tasks.task_004_auth import create_task as create_task_004
from coupled_edit_env.tasks.task_005_calculator import create_task as create_task_005
from coupled_edit_env.tasks.task_006_event_bus import create_task as create_task_006
from coupled_edit_env.tasks.task_007_cache import create_task as create_task_007
from coupled_edit_env.tasks.task_008_formatter import create_task as create_task_008

TASK_REGISTRY = {
    "train": [
        create_task_001,
        create_task_002,
        create_task_003,
        create_task_004,
    ],
    "eval": [
        create_task_005,
        create_task_006,
        create_task_007,
        create_task_008,
    ],
}
