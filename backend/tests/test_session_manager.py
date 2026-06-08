import pytest
from session_manager import SessionManager


@pytest.fixture
def sm():
    return SessionManager(max_history=2)


def test_create_session_returns_unique_ids(sm):
    id1 = sm.create_session()
    id2 = sm.create_session()
    assert id1 != id2
    assert id1 == "session_1"
    assert id2 == "session_2"


def test_add_message_to_existing_session(sm):
    sid = sm.create_session()
    sm.add_message(sid, "user", "hello")
    assert len(sm.sessions[sid]) == 1
    assert sm.sessions[sid][0].role == "user"
    assert sm.sessions[sid][0].content == "hello"


def test_add_message_auto_creates_session(sm):
    sm.add_message("ghost_session", "user", "hi")
    assert "ghost_session" in sm.sessions
    assert len(sm.sessions["ghost_session"]) == 1


def test_history_limit_prunes_oldest(sm):
    # max_history=2 means limit = 2*2 = 4 messages stored
    sid = sm.create_session()
    for i in range(5):
        sm.add_message(sid, "user", f"msg {i}")
    messages = sm.sessions[sid]
    assert len(messages) == 4
    assert messages[0].content == "msg 1"  # msg 0 was pruned


def test_get_history_formats_roles_capitalized(sm):
    sid = sm.create_session()
    sm.add_message(sid, "user", "What is RAG?")
    sm.add_message(sid, "assistant", "Retrieval-Augmented Generation.")
    history = sm.get_conversation_history(sid)
    assert history == "User: What is RAG?\nAssistant: Retrieval-Augmented Generation."


def test_get_history_returns_none_for_nonexistent(sm):
    assert sm.get_conversation_history("no_such_session") is None


def test_get_history_returns_none_for_empty_session(sm):
    sid = sm.create_session()
    assert sm.get_conversation_history(sid) is None


def test_get_history_returns_none_for_none_input(sm):
    assert sm.get_conversation_history(None) is None


def test_clear_session_empties_history(sm):
    sid = sm.create_session()
    sm.add_message(sid, "user", "hello")
    sm.clear_session(sid)
    assert sm.sessions[sid] == []


def test_clear_nonexistent_session_no_error(sm):
    sm.clear_session("does_not_exist")  # must not raise


def test_add_exchange_stores_both_messages(sm):
    sid = sm.create_session()
    sm.add_exchange(sid, "user question", "assistant answer")
    messages = sm.sessions[sid]
    assert len(messages) == 2
    assert messages[0].role == "user"
    assert messages[0].content == "user question"
    assert messages[1].role == "assistant"
    assert messages[1].content == "assistant answer"
