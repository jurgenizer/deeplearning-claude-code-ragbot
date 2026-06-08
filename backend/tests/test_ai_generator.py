import pytest
import sys
import os
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from ai_generator import AIGenerator


# --- Helpers ---

def make_text_block(text="Response text"):
    block = MagicMock()
    block.type = "text"
    block.text = text
    return block


def make_tool_use_block(name="search_course_content", tool_id="tool_1", input_data=None):
    block = MagicMock()
    block.type = "tool_use"
    block.name = name
    block.id = tool_id
    block.input = input_data or {"query": "test query"}
    return block


def make_response(stop_reason, content_blocks):
    response = MagicMock()
    response.stop_reason = stop_reason
    response.content = content_blocks
    return response


# --- Fixtures ---

@pytest.fixture
def mock_client():
    return MagicMock()


@pytest.fixture
def generator(mock_client):
    gen = AIGenerator(api_key="test-key", model="test-model")
    gen.client = mock_client
    return gen


@pytest.fixture
def mock_tool_manager():
    tm = MagicMock()
    tm.execute_tool.return_value = "Search results"
    return tm


# --- Tests: no tool use ---

def test_direct_answer_makes_one_api_call(generator, mock_client):
    mock_client.messages.create.return_value = make_response(
        "end_turn", [make_text_block("Direct answer")]
    )
    result = generator.generate_response("What is Python?")
    assert result == "Direct answer"
    assert mock_client.messages.create.call_count == 1


def test_no_tools_provided_omits_tools_from_request(generator, mock_client):
    mock_client.messages.create.return_value = make_response(
        "end_turn", [make_text_block("Answer")]
    )
    generator.generate_response("Question", tools=None)
    assert "tools" not in mock_client.messages.create.call_args[1]


def test_tool_manager_none_prevents_tool_execution(generator, mock_client):
    """With tool_manager=None the loop is skipped; a capping call retrieves the final text."""
    mock_client.messages.create.side_effect = [
        make_response("tool_use", [make_tool_use_block()]),
        make_response("end_turn", [make_text_block("Capped answer")]),
    ]
    result = generator.generate_response("Query", tools=[{}], tool_manager=None)
    assert result == "Capped answer"
    assert mock_client.messages.create.call_count == 2


# --- Tests: one tool round ---

def test_one_tool_round_returns_final_text(generator, mock_client, mock_tool_manager):
    tool_block = make_tool_use_block("search_course_content", "t1", {"query": "Python"})
    mock_client.messages.create.side_effect = [
        make_response("tool_use", [tool_block]),
        make_response("end_turn", [make_text_block("Final answer")]),
    ]
    result = generator.generate_response("Search for Python", tools=[{}], tool_manager=mock_tool_manager)
    assert result == "Final answer"
    assert mock_client.messages.create.call_count == 2
    mock_tool_manager.execute_tool.assert_called_once_with("search_course_content", query="Python")


def test_second_api_call_includes_tools(generator, mock_client, mock_tool_manager):
    """After a tool round the next call still carries tools so Claude can search again."""
    tools_list = [{"name": "search_course_content"}]
    mock_client.messages.create.side_effect = [
        make_response("tool_use", [make_tool_use_block()]),
        make_response("end_turn", [make_text_block("Answer")]),
    ]
    generator.generate_response("Query", tools=tools_list, tool_manager=mock_tool_manager)
    second_call_kwargs = mock_client.messages.create.call_args_list[1][1]
    assert "tools" in second_call_kwargs


def test_tool_result_passed_to_next_api_call(generator, mock_client, mock_tool_manager):
    tool_block = make_tool_use_block("search_course_content", "tool_abc", {"query": "test"})
    mock_tool_manager.execute_tool.return_value = "Course content here"
    mock_client.messages.create.side_effect = [
        make_response("tool_use", [tool_block]),
        make_response("end_turn", [make_text_block("Answer")]),
    ]
    generator.generate_response("Query", tools=[{}], tool_manager=mock_tool_manager)
    # messages is mutated in place — after the run it contains the full conversation
    messages = mock_client.messages.create.call_args_list[1][1]["messages"]
    tool_result_msg = next(
        m for m in messages
        if m["role"] == "user" and isinstance(m["content"], list)
    )
    assert tool_result_msg["content"][0]["type"] == "tool_result"
    assert tool_result_msg["content"][0]["tool_use_id"] == "tool_abc"
    assert tool_result_msg["content"][0]["content"] == "Course content here"


# --- Tests: two tool rounds ---

def test_two_tool_rounds_then_text(generator, mock_client, mock_tool_manager):
    mock_client.messages.create.side_effect = [
        make_response("tool_use", [make_tool_use_block("get_course_outline", "t1")]),
        make_response("tool_use", [make_tool_use_block("search_course_content", "t2")]),
        make_response("end_turn", [make_text_block("Full answer")]),
    ]
    result = generator.generate_response("Complex query", tools=[{}], tool_manager=mock_tool_manager)
    assert result == "Full answer"
    assert mock_client.messages.create.call_count == 3
    assert mock_tool_manager.execute_tool.call_count == 2


def test_intermediate_api_calls_include_tools(generator, mock_client, mock_tool_manager):
    tools_list = [{"name": "search"}]
    mock_client.messages.create.side_effect = [
        make_response("tool_use", [make_tool_use_block("t1", "t1")]),
        make_response("tool_use", [make_tool_use_block("t2", "t2")]),
        make_response("end_turn", [make_text_block("Answer")]),
    ]
    generator.generate_response("Query", tools=tools_list, tool_manager=mock_tool_manager)
    # All calls inside the loop should carry tools
    for i in range(2):
        assert "tools" in mock_client.messages.create.call_args_list[i][1]


# --- Tests: max rounds / capping call ---

def test_capping_call_fires_after_max_rounds(generator, mock_client, mock_tool_manager):
    mock_client.messages.create.side_effect = [
        make_response("tool_use", [make_tool_use_block("t1", "t1")]),
        make_response("tool_use", [make_tool_use_block("t2", "t2")]),
        make_response("tool_use", [make_tool_use_block("t3", "t3")]),  # cap hit
        make_response("end_turn", [make_text_block("Forced synthesis")]),
    ]
    result = generator.generate_response("Query", tools=[{}], tool_manager=mock_tool_manager)
    assert result == "Forced synthesis"
    assert mock_client.messages.create.call_count == 4
    assert mock_tool_manager.execute_tool.call_count == 2  # cap-hit response tools not executed


def test_capping_call_omits_tools(generator, mock_client, mock_tool_manager):
    tools_list = [{"name": "search"}]
    mock_client.messages.create.side_effect = [
        make_response("tool_use", [make_tool_use_block("t1", "t1")]),
        make_response("tool_use", [make_tool_use_block("t2", "t2")]),
        make_response("tool_use", [make_tool_use_block("t3", "t3")]),
        make_response("end_turn", [make_text_block("Synthesis")]),
    ]
    generator.generate_response("Query", tools=tools_list, tool_manager=mock_tool_manager)
    capping_call_kwargs = mock_client.messages.create.call_args_list[3][1]
    assert "tools" not in capping_call_kwargs


# --- Tests: tool execution errors ---

def test_tool_execution_error_does_not_propagate(generator, mock_client, mock_tool_manager):
    mock_tool_manager.execute_tool.side_effect = Exception("Connection failed")
    mock_client.messages.create.side_effect = [
        make_response("tool_use", [make_tool_use_block()]),
        make_response("end_turn", [make_text_block("Error acknowledged")]),
    ]
    result = generator.generate_response("Query", tools=[{}], tool_manager=mock_tool_manager)
    assert result == "Error acknowledged"
    assert mock_client.messages.create.call_count == 2


def test_tool_error_string_passed_as_tool_result(generator, mock_client, mock_tool_manager):
    mock_tool_manager.execute_tool.side_effect = Exception("Service unavailable")
    tool_block = make_tool_use_block("search_course_content", "err_tool", {"query": "test"})
    mock_client.messages.create.side_effect = [
        make_response("tool_use", [tool_block]),
        make_response("end_turn", [make_text_block("Handled")]),
    ]
    generator.generate_response("Query", tools=[{}], tool_manager=mock_tool_manager)
    messages = mock_client.messages.create.call_args_list[1][1]["messages"]
    tool_result_msg = next(
        m for m in messages
        if m["role"] == "user" and isinstance(m["content"], list)
    )
    error_content = tool_result_msg["content"][0]["content"]
    assert "failed" in error_content.lower()


# --- Tests: conversation history ---

def test_conversation_history_appended_to_system_prompt(generator, mock_client):
    mock_client.messages.create.return_value = make_response(
        "end_turn", [make_text_block("Answer")]
    )
    generator.generate_response("Query", conversation_history="User: Hi\nAssistant: Hello")
    system = mock_client.messages.create.call_args[1]["system"]
    assert "Previous conversation" in system
    assert "User: Hi" in system
