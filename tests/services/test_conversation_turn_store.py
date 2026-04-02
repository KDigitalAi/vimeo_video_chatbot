from __future__ import annotations

import pytest

from app.core.exceptions import NotFoundError, PersistenceError


class FakeExecuteResult:
    def __init__(self, data):
        self.data = data


class FakeConversationTurnTable:
    def __init__(self, rows=None, insert_data=None, delete_data=None):
        self.rows = rows or []
        self.insert_data = insert_data
        self.delete_data = delete_data
        self.insert_payload = None
        self.execute_calls = 0

    def select(self, _columns):
        return self

    def eq(self, *_args):
        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, _limit):
        return self

    def insert(self, payload):
        self.insert_payload = payload
        return self

    def delete(self):
        return self

    def execute(self):
        self.execute_calls += 1
        if self.insert_payload is not None:
            return FakeExecuteResult(self.insert_data)
        if self.delete_data is not None:
            return FakeExecuteResult(self.delete_data)
        return FakeExecuteResult(self.rows)


class FakeSupabase:
    def __init__(self, table):
        self._table = table

    def table(self, _name):
        return self._table


@pytest.fixture
def conversation_turn_module():
    import app.services.conversation_turn_store as module

    module._session_history_cache.clear()
    module._user_sessions_cache.clear()
    module.list_conversation_turns_for_user.cache_clear()
    yield module
    module._session_history_cache.clear()
    module._user_sessions_cache.clear()
    module.list_conversation_turns_for_user.cache_clear()


def test_get_chat_sessions_uses_cache(conversation_turn_module, monkeypatch):
    table = FakeConversationTurnTable(
        rows=[
            {"session_id": "s1", "created_at": "2026-01-01", "user_message": "hello"},
            {"session_id": "s1", "created_at": "2026-01-01", "user_message": "duplicate"},
        ]
    )
    monkeypatch.setattr(conversation_turn_module, "get_supabase", lambda: FakeSupabase(table))

    first = conversation_turn_module.get_chat_sessions("user-1")
    second = conversation_turn_module.get_chat_sessions("user-1")

    assert len(first) == 1
    assert first == second
    assert table.execute_calls == 1


def test_store_chat_interaction_truncates_long_messages(conversation_turn_module, monkeypatch):
    table = FakeConversationTurnTable(insert_data=[{"id": "chat-1"}])
    monkeypatch.setattr(conversation_turn_module, "get_supabase", lambda: FakeSupabase(table))
    monkeypatch.setattr(conversation_turn_module, "memory_guard", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(conversation_turn_module, "log_memory_usage", lambda *_args, **_kwargs: None)

    result = conversation_turn_module.store_chat_interaction(
        "user-1",
        "session-1",
        "u" * 12000,
        "b" * 12000,
    )

    assert result == "chat-1"
    assert table.insert_payload["user_message"].endswith("...")
    assert table.insert_payload["bot_response"].endswith("...")
    assert len(table.insert_payload["user_message"]) == 10003
    assert len(table.insert_payload["bot_response"]) == 10003


def test_delete_chat_session_raises_not_found(conversation_turn_module, monkeypatch):
    table = FakeConversationTurnTable(delete_data=[])
    monkeypatch.setattr(conversation_turn_module, "get_supabase", lambda: FakeSupabase(table))

    with pytest.raises(NotFoundError):
        conversation_turn_module.delete_chat_session("user-1", "session-1")


def test_list_conversation_turns_raises_persistence_error_on_db_failure(
    conversation_turn_module, monkeypatch
):
    def failing_supabase():
        raise RuntimeError("db down")

    monkeypatch.setattr(conversation_turn_module, "get_supabase", failing_supabase)
    monkeypatch.setattr(conversation_turn_module, "memory_guard", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(conversation_turn_module, "cleanup_memory", lambda *_args, **_kwargs: None)

    with pytest.raises(PersistenceError):
        conversation_turn_module.list_conversation_turns_for_user("user-1")
