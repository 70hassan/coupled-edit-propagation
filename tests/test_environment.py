"""
Tests for environment loading and task structure integrity.
"""

import pytest
from coupled_edit_env.environment import load_environment, TaskInstance


class TestEnvironmentLoading:
    def test_load_train_split(self):
        env = load_environment(split="train")
        assert len(env.tasks) == 4
        assert env.name == "coupled-edit-propagation"

    def test_load_eval_split(self):
        env = load_environment(split="eval")
        assert len(env.tasks) == 4
        assert env.name == "coupled-edit-propagation"

    def test_all_tasks_have_required_fields(self):
        for split in ["train", "eval"]:
            env = load_environment(split=split)
            for task in env.tasks:
                assert task.task_id, "Task must have an ID"
                assert task.instruction, "Task must have an instruction"
                assert task.project_files, "Task must have project files"
                assert task.modified_function, "Task must specify the modified function"
                assert task.test_suite, "Task must have a visible test suite"
                assert task.hidden_tests, "Task must have hidden tests"
                assert task.difficulty, "Task must have a difficulty rating"

    def test_task_ids_unique(self):
        all_ids = set()
        for split in ["train", "eval"]:
            env = load_environment(split=split)
            for task in env.tasks:
                assert task.task_id not in all_ids, f"Duplicate task ID: {task.task_id}"
                all_ids.add(task.task_id)

    def test_prompts_are_well_formed(self):
        env = load_environment(split="train")
        for task in env.tasks:
            prompt = task.to_prompt()
            assert task.modified_function in prompt
            assert "Do NOT modify" in prompt
            assert "---" in prompt


class TestTaskDifficulty:
    def test_difficulty_values_are_valid(self):
        valid = {"easy", "easy-medium", "medium", "medium-hard", "hard"}
        for split in ["train", "eval"]:
            env = load_environment(split=split)
            for task in env.tasks:
                assert task.difficulty in valid, (
                    f"Invalid difficulty '{task.difficulty}' for {task.task_id}"
                )

    def test_train_has_easier_tasks(self):
        train_env = load_environment(split="train")
        difficulties = [t.difficulty for t in train_env.tasks]
        assert "easy" in difficulties or "easy-medium" in difficulties
