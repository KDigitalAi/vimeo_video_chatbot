from __future__ import annotations

import pytest

from app.core.exceptions import NotFoundError, PersistenceError


class FakeExecuteResult:
    def __init__(self, data):
        self.data = data


class FakeUserProfileTable:
    def __init__(self, *, rpc_data=None, select_data=None, update_data=None, rpc_error=None):
        self.rpc_data = rpc_data
        self.select_data = select_data
        self.update_data = update_data
        self.rpc_error = rpc_error

    def rpc(self, _name, _payload):
        class RpcCall:
            def __init__(self, data, error):
                self.data = data
                self.error = error

            def execute(self):
                if self.error:
                    raise self.error
                return FakeExecuteResult(self.data)

        return RpcCall(self.rpc_data, self.rpc_error)

    def table(self, _name):
        return self

    def select(self, _columns):
        return self

    def update(self, _payload):
        return self

    def eq(self, *_args):
        return self

    def limit(self, _value):
        return self

    def order(self, *_args, **_kwargs):
        return self

    def execute(self):
        if self.select_data is not None:
            return FakeExecuteResult(self.select_data)
        return FakeExecuteResult(self.update_data)


@pytest.fixture
def user_profile_module():
    import app.services.user_profile_manager as module

    yield module


def test_set_active_session_success(user_profile_module, monkeypatch):
    supabase = FakeUserProfileTable(rpc_data="profile-1")
    monkeypatch.setattr(user_profile_module, "get_supabase", lambda: supabase)
    monkeypatch.setattr(user_profile_module, "memory_guard", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(user_profile_module, "log_memory_usage", lambda *_args, **_kwargs: None)

    result = user_profile_module.set_active_session("user-1", "session-1")

    assert result == "profile-1"


def test_get_active_session_returns_none_when_empty(user_profile_module, monkeypatch):
    supabase = FakeUserProfileTable(rpc_data=None)
    monkeypatch.setattr(user_profile_module, "get_supabase", lambda: supabase)

    assert user_profile_module.get_active_session("user-1") is None


def test_deactivate_session_by_id_raises_not_found(user_profile_module, monkeypatch):
    supabase = FakeUserProfileTable(update_data=[])
    monkeypatch.setattr(user_profile_module, "get_supabase", lambda: supabase)

    with pytest.raises(NotFoundError):
        user_profile_module.deactivate_session_by_id("session-1")


def test_is_session_active_returns_false_for_empty_result(user_profile_module, monkeypatch):
    supabase = FakeUserProfileTable(select_data=[])
    monkeypatch.setattr(user_profile_module, "get_supabase", lambda: supabase)

    assert user_profile_module.is_session_active("session-1") is False


def test_set_active_session_raises_persistence_error(user_profile_module, monkeypatch):
    supabase = FakeUserProfileTable(rpc_error=RuntimeError("rpc failed"))
    monkeypatch.setattr(user_profile_module, "get_supabase", lambda: supabase)
    monkeypatch.setattr(user_profile_module, "memory_guard", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(user_profile_module, "cleanup_memory", lambda *_args, **_kwargs: None)

    with pytest.raises(PersistenceError):
        user_profile_module.set_active_session("user-1", "session-1")

