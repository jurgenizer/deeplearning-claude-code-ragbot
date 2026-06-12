import pytest
from models import Course, Lesson, CourseChunk
from vector_store import VectorStore

# --- Helpers ---


def make_full_course(title="Full Course"):
    lesson = Lesson(
        lesson_number=0, title="Intro", lesson_link="https://example.com/l0"
    )
    return Course(
        title=title,
        course_link="https://example.com/course",
        instructor="Dr. Test",
        lessons=[lesson],
    )


def make_chunk(course_title="Full Course", lesson_number=0, idx=0):
    return CourseChunk(
        content=f"Lesson {lesson_number} chunk {idx}: some educational content about the topic.",
        course_title=course_title,
        lesson_number=lesson_number,
        chunk_index=idx,
    )


# --- add_course_metadata ---


def test_add_course_metadata_full(vector_store):
    course = make_full_course()
    vector_store.add_course_metadata(course)
    assert vector_store.get_course_count() == 1


def test_add_course_metadata_none_instructor(vector_store):
    """Bug A: ChromaDB rejects None in metadata — instructor=None must not crash."""
    course = Course(
        title="No Instructor", course_link="https://example.com", instructor=None
    )
    vector_store.add_course_metadata(course)  # should not raise
    assert vector_store.get_course_count() == 1


def test_add_course_metadata_none_link(vector_store):
    """Bug A: ChromaDB rejects None in metadata — course_link=None must not crash."""
    course = Course(title="No Link", course_link=None, instructor="Someone")
    vector_store.add_course_metadata(course)  # should not raise
    assert vector_store.get_course_count() == 1


def test_add_course_metadata_all_none_optional(vector_store):
    """Both optional fields None simultaneously."""
    course = Course(title="Bare Course", course_link=None, instructor=None)
    vector_store.add_course_metadata(course)
    assert vector_store.get_course_count() == 1


# --- add_course_content ---


def test_add_course_content_with_lesson_number(vector_store):
    chunk = make_chunk()
    vector_store.add_course_content([chunk])  # should not raise


def test_add_course_content_none_lesson_number(vector_store):
    """Bug B: ChromaDB rejects None — lesson_number=None (fallback path) must not crash."""
    chunk = CourseChunk(
        content="Plain content with no lesson context.",
        course_title="Test Course",
        lesson_number=None,
        chunk_index=0,
    )
    vector_store.add_course_content([chunk])  # should not raise


def test_add_course_content_empty_list(vector_store):
    vector_store.add_course_content([])  # early return, no error


# --- get_existing_course_titles / get_course_count ---


def test_get_existing_course_titles_empty(vector_store):
    titles = vector_store.get_existing_course_titles()
    assert isinstance(titles, list)
    assert len(titles) == 0


def test_get_existing_course_titles_after_add(vector_store):
    vector_store.add_course_metadata(make_full_course("Alpha"))
    vector_store.add_course_metadata(make_full_course("Beta"))
    titles = vector_store.get_existing_course_titles()
    assert set(titles) == {"Alpha", "Beta"}


def test_get_course_count(vector_store):
    assert vector_store.get_course_count() == 0
    vector_store.add_course_metadata(make_full_course())
    assert vector_store.get_course_count() == 1


# --- search ---


def test_search_returns_results(vector_store):
    course = make_full_course()
    vector_store.add_course_metadata(course)
    chunk = make_chunk()
    vector_store.add_course_content([chunk])
    results = vector_store.search(query="educational content about the topic")
    assert not results.is_empty()
    assert results.documents[0]  # non-empty string


def test_search_empty_collection_returns_empty_not_crash(vector_store):
    results = vector_store.search(query="anything")
    # Either empty results or a graceful error — must not raise
    assert results is not None


def test_search_with_course_filter(vector_store):
    for name in ("Course A", "Course B"):
        vector_store.add_course_metadata(make_full_course(name))
        vector_store.add_course_content([make_chunk(course_title=name)])

    results = vector_store.search(query="educational content", course_name="Course A")
    if not results.is_empty():
        for meta in results.metadata:
            assert meta["course_title"] == "Course A"


# --- get_course_outline / get_lesson_link ---


def test_get_course_outline(vector_store):
    course = make_full_course()
    vector_store.add_course_metadata(course)
    outline = vector_store.get_course_outline("Full Course")
    assert outline is not None
    assert outline["title"] == "Full Course"
    assert isinstance(outline["lessons"], list)
    assert outline["lessons"][0]["lesson_number"] == 0


def test_get_lesson_link(vector_store):
    course = make_full_course()
    vector_store.add_course_metadata(course)
    link = vector_store.get_lesson_link("Full Course", 0)
    assert link == "https://example.com/l0"


def test_get_lesson_link_nonexistent_course(vector_store):
    link = vector_store.get_lesson_link("Ghost", 0)
    assert link is None


# --- clear_all_data ---


def test_clear_all_data(vector_store):
    vector_store.add_course_metadata(make_full_course())
    assert vector_store.get_course_count() == 1
    vector_store.clear_all_data()
    assert vector_store.get_course_count() == 0


# --- round-trip: processor → store → search ---


def test_round_trip_processor_to_store(
    vector_store, document_processor, sample_course_file
):
    """Full pipeline: parse a file, store it, then search it."""
    course, chunks = document_processor.process_course_document(sample_course_file)
    vector_store.add_course_metadata(course)
    vector_store.add_course_content(chunks)

    results = vector_store.search(query="advanced material")
    assert not results.is_empty()
    assert vector_store.get_course_count() == 1
