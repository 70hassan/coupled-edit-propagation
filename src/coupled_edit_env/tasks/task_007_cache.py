"""
Task 007: Cache Layer - Sync/Async + return type change with multiple consumers

Scenario: A caching layer where `get` was changed from returning the value directly
(or None on miss) to returning a CacheResult dataclass that includes hit/miss info,
TTL remaining, and the value. Additionally, it's now async. Multiple services that
use the cache need updating.

Difficulty: Hard
Coupling type: Combined return-type + sync-to-async change with multiple consumers
"""

from coupled_edit_env.types import TaskInstance


def create_task() -> TaskInstance:
    project_files = {
        "cache/store.py": '''
import time
from dataclasses import dataclass


@dataclass
class CacheResult:
    """Result of a cache lookup with metadata."""
    hit: bool
    value: object
    ttl_remaining: float
    key: str

    @property
    def missed(self) -> bool:
        return not self.hit


class CacheStore:
    def __init__(self, default_ttl: float = 300.0):
        self._data = {}
        self._expiry = {}
        self._default_ttl = default_ttl
        self._hits = 0
        self._misses = 0

    def set(self, key: str, value: object, ttl: float = None):
        """Store a value with optional TTL override."""
        self._data[key] = value
        self._expiry[key] = time.time() + (ttl if ttl is not None else self._default_ttl)

    async def get(self, key: str) -> CacheResult:
        """
        MODIFIED: Now async and returns CacheResult instead of raw value/None.
        Previously: def get(self, key) -> object | None (returned value or None).
        Now: async def get(self, key) -> CacheResult (always returns a result object).
        """
        if key not in self._data:
            self._misses += 1
            return CacheResult(hit=False, value=None, ttl_remaining=0.0, key=key)

        if time.time() > self._expiry[key]:
            del self._data[key]
            del self._expiry[key]
            self._misses += 1
            return CacheResult(hit=False, value=None, ttl_remaining=0.0, key=key)

        self._hits += 1
        ttl_left = self._expiry[key] - time.time()
        return CacheResult(hit=True, value=self._data[key], ttl_remaining=ttl_left, key=key)

    def delete(self, key: str):
        self._data.pop(key, None)
        self._expiry.pop(key, None)

    @property
    def hit_rate(self) -> float:
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0
''',
        "cache/services.py": '''
from cache.store import CacheStore


class UserProfileService:
    def __init__(self, cache: CacheStore):
        self.cache = cache
        self._db = {
            "user_1": {"name": "Alice", "email": "alice@example.com", "plan": "pro"},
            "user_2": {"name": "Bob", "email": "bob@example.com", "plan": "free"},
            "user_3": {"name": "Charlie", "email": "charlie@example.com", "plan": "enterprise"},
        }

    def get_profile(self, user_id: str):
        """Get user profile, using cache first."""
        cached = self.cache.get(f"profile:{user_id}")
        if cached is not None:
            return cached

        profile = self._db.get(user_id)
        if profile:
            self.cache.set(f"profile:{user_id}", profile)
        return profile

    def get_display_name(self, user_id: str) -> str:
        """Get just the display name for a user."""
        profile = self.get_profile(user_id)
        if profile is None:
            return "Unknown User"
        return profile["name"]


class ConfigService:
    def __init__(self, cache: CacheStore):
        self.cache = cache
        self._defaults = {
            "max_upload_mb": 10,
            "feature_dark_mode": True,
            "feature_beta": False,
            "rate_limit": 100,
        }

    def get_setting(self, key: str) -> object:
        """Get a config setting, cache-first with fallback to defaults."""
        cached = self.cache.get(f"config:{key}")
        if cached is not None:
            return cached

        value = self._defaults.get(key)
        if value is not None:
            self.cache.set(f"config:{key}", value, ttl=60.0)
        return value

    def get_feature_flag(self, flag_name: str) -> bool:
        """Check if a feature flag is enabled."""
        value = self.get_setting(f"feature_{flag_name}")
        return bool(value) if value is not None else False


class SessionManager:
    def __init__(self, cache: CacheStore):
        self.cache = cache

    def create_session(self, session_id: str, user_id: str, data: dict):
        """Create a new session."""
        session = {"user_id": user_id, **data}
        self.cache.set(f"session:{session_id}", session, ttl=3600.0)

    def get_session(self, session_id: str):
        """Retrieve session data."""
        return self.cache.get(f"session:{session_id}")

    def is_active(self, session_id: str) -> bool:
        """Check if session exists and is active."""
        session = self.cache.get(f"session:{session_id}")
        return session is not None
''',
    }

    modified_function = "get"

    test_suite = '''
import sys
import asyncio
sys.path.insert(0, ".")
from cache.store import CacheStore, CacheResult


def test_cache_get_returns_result():
    cache = CacheStore()
    cache.set("key1", "value1")
    result = asyncio.run(cache.get("key1"))
    assert isinstance(result, CacheResult)
    assert result.hit is True
    assert result.value == "value1"
    assert result.ttl_remaining > 0


def test_cache_miss_returns_result():
    cache = CacheStore()
    result = asyncio.run(cache.get("missing"))
    assert isinstance(result, CacheResult)
    assert result.hit is False
    assert result.value is None
    assert result.ttl_remaining == 0.0
'''

    hidden_tests = '''
import sys
import asyncio
sys.path.insert(0, ".")
from cache.store import CacheStore
from cache.services import UserProfileService, ConfigService, SessionManager


def test_profile_cache_hit():
    cache = CacheStore()
    svc = UserProfileService(cache)
    cache.set("profile:user_1", {"name": "Alice", "email": "alice@example.com", "plan": "pro"})
    result = asyncio.run(svc.get_profile("user_1"))
    assert result is not None
    assert result["name"] == "Alice"


def test_profile_cache_miss_db_hit():
    cache = CacheStore()
    svc = UserProfileService(cache)
    result = asyncio.run(svc.get_profile("user_2"))
    assert result is not None
    assert result["name"] == "Bob"


def test_profile_not_found():
    cache = CacheStore()
    svc = UserProfileService(cache)
    result = asyncio.run(svc.get_profile("user_999"))
    assert result is None


def test_display_name_found():
    cache = CacheStore()
    svc = UserProfileService(cache)
    result = asyncio.run(svc.get_display_name("user_1"))
    assert result == "Alice"


def test_display_name_not_found():
    cache = CacheStore()
    svc = UserProfileService(cache)
    result = asyncio.run(svc.get_display_name("nobody"))
    assert result == "Unknown User"


def test_config_setting():
    cache = CacheStore()
    svc = ConfigService(cache)
    result = asyncio.run(svc.get_setting("max_upload_mb"))
    assert result == 10


def test_config_cached():
    cache = CacheStore()
    cache.set("config:rate_limit", 200, ttl=60.0)
    svc = ConfigService(cache)
    result = asyncio.run(svc.get_setting("rate_limit"))
    assert result == 200


def test_feature_flag_enabled():
    cache = CacheStore()
    svc = ConfigService(cache)
    result = asyncio.run(svc.get_feature_flag("dark_mode"))
    assert result is True


def test_feature_flag_disabled():
    cache = CacheStore()
    svc = ConfigService(cache)
    result = asyncio.run(svc.get_feature_flag("beta"))
    assert result is False


def test_session_create_and_get():
    cache = CacheStore()
    mgr = SessionManager(cache)
    mgr.create_session("sess_1", "user_1", {"ip": "127.0.0.1"})
    result = asyncio.run(mgr.get_session("sess_1"))
    assert result is not None
    assert result["user_id"] == "user_1"


def test_session_missing():
    cache = CacheStore()
    mgr = SessionManager(cache)
    result = asyncio.run(mgr.get_session("nonexistent"))
    assert result is None


def test_session_is_active():
    cache = CacheStore()
    mgr = SessionManager(cache)
    mgr.create_session("s1", "u1", {})
    assert asyncio.run(mgr.is_active("s1")) is True
    assert asyncio.run(mgr.is_active("s_none")) is False
'''

    ground_truth_repairs = {
        "cache/services.py": "All methods calling cache.get must become async, await cache.get, and check result.hit instead of 'is not None', using result.value for the actual data",
    }

    return TaskInstance(
        task_id="task_007_cache",
        instruction=(
            "The `get` method in cache/store.py was changed in two ways: "
            "(1) it is now async (must be awaited), and (2) it returns a CacheResult object "
            "with .hit (bool), .value (the data), and .ttl_remaining instead of returning "
            "the raw value or None. This change is correct and must NOT be reverted. "
            "Fix all code in cache/services.py. Methods that call cache.get must become async, "
            "must await the call, and must check result.hit instead of comparing to None."
        ),
        project_files=project_files,
        modified_function=modified_function,
        test_suite=test_suite,
        hidden_tests=hidden_tests,
        ground_truth_repairs=ground_truth_repairs,
        difficulty="hard",
        revert_indicators=[
            "return self._data[key]",
            "return None\n\n    def delete",
        ],
        modified_is_async=True,
    )
