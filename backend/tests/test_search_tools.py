import pytest
from unittest.mock import MagicMock
from search_tools import CourseSearchTool, CourseOutlineTool, ToolManager
from vector_store import SearchResults


def make_search_results(docs, metas, error=None):
    if error:
        return SearchResults.empty(error)
    return SearchResults(documents=docs, metadata=metas, distances=[0.1] * len(docs))


@pytest.fixture
def mock_store():
    return MagicMock()


@pytest.fixture
def search_tool(mock_store):
    return CourseSearchTool(mock_store)


@pytest.fixture
def outline_tool(mock_store):
    return CourseOutlineTool(mock_store)


@pytest.fixture
def tool_manager(search_tool):
    tm = ToolManager()
    tm.register_tool(search_tool)
    return tm


# --- Tool definition schema ---

def test_search_tool_definition_schema(search_tool):
    defn = search_tool.get_tool_definition()
    assert defn["name"] == "search_course_content"
    schema = defn["input_schema"]
    assert schema["type"] == "object"
    assert "query" in schema["properties"]
    assert schema["required"] == ["query"]


def test_outline_tool_definition_schema(outline_tool):
    defn = outline_tool.get_tool_definition()
    assert defn["name"] == "get_course_outline"
    schema = defn["input_schema"]
    assert "course_title" in schema["properties"]
    assert schema["required"] == ["course_title"]


# --- ToolManager registration and execution ---

def test_tool_manager_register_and_list(tool_manager, search_tool):
    defs = tool_manager.get_tool_definitions()
    names = [d["name"] for d in defs]
    assert "search_course_content" in names


def test_tool_manager_execute_known_tool(tool_manager, mock_store):
    mock_store.search.return_value = make_search_results(
        ["content"], [{"course_title": "TC", "lesson_number": 1}]
    )
    mock_store.get_lesson_link.return_value = "https://example.com/l1"
    result = tool_manager.execute_tool("search_course_content", query="test")
    assert isinstance(result, str)
    assert "TC" in result


def test_tool_manager_execute_unknown_returns_error_string(tool_manager):
    result = tool_manager.execute_tool("nonexistent_tool")
    assert "nonexistent_tool" in result


def test_tool_manager_reset_clears_sources(tool_manager, mock_store):
    mock_store.search.return_value = make_search_results(
        ["content"], [{"course_title": "TC", "lesson_number": 1}]
    )
    mock_store.get_lesson_link.return_value = None
    tool_manager.execute_tool("search_course_content", query="anything")
    assert len(tool_manager.get_last_sources()) > 0
    tool_manager.reset_sources()
    assert tool_manager.get_last_sources() == []


# --- CourseSearchTool behaviour ---

def test_search_tool_deduplicates_sources_by_label(search_tool, mock_store):
    # Two results from same course+lesson → only one source entry
    mock_store.search.return_value = make_search_results(
        ["chunk A", "chunk B"],
        [
            {"course_title": "My Course", "lesson_number": 1},
            {"course_title": "My Course", "lesson_number": 1},
        ],
    )
    mock_store.get_lesson_link.return_value = "https://example.com/l1"
    search_tool.execute(query="anything")
    assert len(search_tool.last_sources) == 1


def test_search_tool_handles_empty_results(search_tool, mock_store):
    mock_store.search.return_value = make_search_results([], [])
    result = search_tool.execute(query="nothing here")
    assert "No relevant content found" in result


def test_search_tool_handles_error_results(search_tool, mock_store):
    mock_store.search.return_value = make_search_results([], [], error="DB unavailable")
    result = search_tool.execute(query="test")
    assert result == "DB unavailable"


# --- CourseOutlineTool behaviour ---

def test_outline_tool_returns_formatted_outline(outline_tool, mock_store):
    mock_store.get_course_outline.return_value = {
        "title": "Test Course",
        "course_link": "https://example.com",
        "lessons": [
            {"lesson_number": 0, "lesson_title": "Intro"},
            {"lesson_number": 1, "lesson_title": "Advanced"},
        ],
    }
    result = outline_tool.execute(course_title="Test")
    assert "Test Course" in result
    assert "Intro" in result
    assert "Advanced" in result


def test_outline_tool_handles_missing_course(outline_tool, mock_store):
    mock_store.get_course_outline.return_value = None
    result = outline_tool.execute(course_title="Ghost Course")
    assert "No course found" in result


# --- ToolManager validation ---

def test_register_tool_without_name_raises():
    class BadTool(CourseSearchTool):
        def get_tool_definition(self):
            return {"input_schema": {}}  # no "name" key

    tm = ToolManager()
    with pytest.raises(ValueError):
        tm.register_tool(BadTool(MagicMock()))
