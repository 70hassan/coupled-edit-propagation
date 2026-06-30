"""
Task 004: Authentication - Async conversion propagation

Scenario: The core `validate_token` method was converted from sync to async.
All callers in the middleware and route handlers must now await it, and functions
that call those callers need to become async too (transitive propagation).

Difficulty: Medium-Hard
Coupling type: Sync-to-async contract change with transitive effects
"""

from coupled_edit_env.types import TaskInstance


def create_task() -> TaskInstance:
    project_files = {
        "auth/token_store.py": '''
import hashlib
import time


TOKEN_DB = {
    "abc123": {"user": "alice", "role": "admin", "expires": 9999999999},
    "def456": {"user": "bob", "role": "viewer", "expires": 9999999999},
    "exp789": {"user": "charlie", "role": "editor", "expires": 1000000000},
}


class TokenStore:
    def __init__(self):
        self._cache = {}
        self._revoked = set()

    async def validate_token(self, token: str):
        """
        MODIFIED: Now async because it needs to hit an external token service.
        Previously was synchronous and returned the same thing.

        Returns user info dict if valid, None if invalid/expired/revoked.
        """
        if not token or token in self._revoked:
            return None

        if token in self._cache:
            entry = self._cache[token]
            if entry["expires"] > time.time():
                return entry
            return None

        entry = TOKEN_DB.get(token)
        if entry is None:
            return None
        if entry["expires"] < time.time():
            return None

        self._cache[token] = entry
        return entry

    def revoke_token(self, token: str):
        self._revoked.add(token)
        self._cache.pop(token, None)
''',
        "auth/middleware.py": '''
from auth.token_store import TokenStore


class AuthMiddleware:
    def __init__(self, store: TokenStore):
        self.store = store

    def authenticate(self, request: dict) -> dict:
        """Validate the request token and return enriched request or error."""
        token = request.get("headers", {}).get("Authorization", "").replace("Bearer ", "")
        if not token:
            return {"status": 401, "error": "missing token"}

        user_info = self.store.validate_token(token)
        if user_info is None:
            return {"status": 401, "error": "invalid or expired token"}

        return {"status": 200, "user": user_info["user"], "role": user_info["role"]}

    def require_role(self, request: dict, required_role: str) -> dict:
        """Authenticate and check role. Returns auth result with role check."""
        auth_result = self.authenticate(request)
        if auth_result["status"] != 200:
            return auth_result

        if auth_result["role"] != required_role and auth_result["role"] != "admin":
            return {"status": 403, "error": f"requires {required_role} role"}

        return auth_result

    def batch_validate(self, tokens: list[str]) -> dict[str, bool]:
        """Check multiple tokens at once, returning validity map."""
        results = {}
        for token in tokens:
            user_info = self.store.validate_token(token)
            results[token] = user_info is not None
        return results
''',
        "auth/handlers.py": '''
from auth.middleware import AuthMiddleware


class RequestHandler:
    def __init__(self, middleware: AuthMiddleware):
        self.middleware = middleware
        self._audit_log = []

    def handle_admin_action(self, request: dict, action: str) -> dict:
        """Process an admin action with role check."""
        auth = self.middleware.require_role(request, "admin")
        if auth["status"] != 200:
            return auth

        self._audit_log.append({"user": auth["user"], "action": action})
        return {"status": 200, "result": f"action '{action}' performed by {auth['user']}"}

    def handle_read(self, request: dict) -> dict:
        """Process a read request (any authenticated user)."""
        auth = self.middleware.authenticate(request)
        if auth["status"] != 200:
            return auth
        return {"status": 200, "data": "content here", "viewer": auth["user"]}
''',
    }

    modified_function = "validate_token"

    test_suite = '''
import sys
import asyncio
sys.path.insert(0, ".")
from auth.token_store import TokenStore


def test_validate_token_is_async():
    store = TokenStore()
    result = asyncio.run(store.validate_token("abc123"))
    assert result is not None
    assert result["user"] == "alice"


def test_validate_invalid_token():
    store = TokenStore()
    result = asyncio.run(store.validate_token("nonexistent"))
    assert result is None


def test_validate_revoked():
    store = TokenStore()
    store.revoke_token("abc123")
    result = asyncio.run(store.validate_token("abc123"))
    assert result is None
'''

    hidden_tests = '''
import sys
import asyncio
sys.path.insert(0, ".")
from auth.token_store import TokenStore
from auth.middleware import AuthMiddleware
from auth.handlers import RequestHandler


def _make_request(token):
    return {"headers": {"Authorization": f"Bearer {token}"}}


def test_middleware_authenticate_valid():
    store = TokenStore()
    mw = AuthMiddleware(store)
    result = asyncio.run(mw.authenticate(_make_request("abc123")))
    assert result["status"] == 200
    assert result["user"] == "alice"


def test_middleware_authenticate_invalid():
    store = TokenStore()
    mw = AuthMiddleware(store)
    result = asyncio.run(mw.authenticate(_make_request("bogus")))
    assert result["status"] == 401


def test_middleware_authenticate_missing():
    store = TokenStore()
    mw = AuthMiddleware(store)
    result = asyncio.run(mw.authenticate({"headers": {}}))
    assert result["status"] == 401


def test_require_role_admin():
    store = TokenStore()
    mw = AuthMiddleware(store)
    result = asyncio.run(mw.require_role(_make_request("abc123"), "admin"))
    assert result["status"] == 200


def test_require_role_denied():
    store = TokenStore()
    mw = AuthMiddleware(store)
    result = asyncio.run(mw.require_role(_make_request("def456"), "admin"))
    assert result["status"] == 403


def test_batch_validate():
    store = TokenStore()
    mw = AuthMiddleware(store)
    result = asyncio.run(mw.batch_validate(["abc123", "bogus", "def456"]))
    assert result["abc123"] is True
    assert result["bogus"] is False
    assert result["def456"] is True


def test_handler_admin_action():
    store = TokenStore()
    mw = AuthMiddleware(store)
    handler = RequestHandler(mw)
    result = asyncio.run(handler.handle_admin_action(_make_request("abc123"), "delete_user"))
    assert result["status"] == 200
    assert "alice" in result["result"]


def test_handler_read():
    store = TokenStore()
    mw = AuthMiddleware(store)
    handler = RequestHandler(mw)
    result = asyncio.run(handler.handle_read(_make_request("def456")))
    assert result["status"] == 200
    assert result["viewer"] == "bob"


def test_handler_unauthorized():
    store = TokenStore()
    mw = AuthMiddleware(store)
    handler = RequestHandler(mw)
    result = asyncio.run(handler.handle_read(_make_request("invalid")))
    assert result["status"] == 401
'''

    ground_truth_repairs = {
        "auth/middleware.py": "authenticate, require_role, batch_validate must become async and await validate_token",
        "auth/handlers.py": "handle_admin_action and handle_read must become async and await middleware methods",
    }

    return TaskInstance(
        task_id="task_004_auth",
        instruction=(
            "The method `validate_token` in auth/token_store.py was converted from synchronous to async. "
            "It now must be awaited. This change is correct and must NOT be reverted. "
            "Fix all downstream code in auth/middleware.py and auth/handlers.py. "
            "Methods that call validate_token must become async, and any methods that call THOSE "
            "must also become async (the change propagates transitively up the call chain)."
        ),
        project_files=project_files,
        modified_function=modified_function,
        test_suite=test_suite,
        hidden_tests=hidden_tests,
        ground_truth_repairs=ground_truth_repairs,
        difficulty="medium-hard",
        revert_indicators=[],
        modified_is_async=True,
    )
