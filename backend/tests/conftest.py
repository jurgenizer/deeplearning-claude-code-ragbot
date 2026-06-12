import sys
import os
import pytest

# Add backend directory to path so all modules resolve
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models import Course, Lesson, CourseChunk
from document_processor import DocumentProcessor
from session_manager import SessionManager
from vector_store import VectorStore

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


@pytest.fixture
def tmp_chroma_path(tmp_path):
    return str(tmp_path / "chroma_db")


@pytest.fixture
def vector_store(tmp_chroma_path):
    return VectorStore(
        chroma_path=tmp_chroma_path,
        embedding_model="all-MiniLM-L6-v2",
        max_results=5,
    )


@pytest.fixture
def document_processor():
    return DocumentProcessor(chunk_size=800, chunk_overlap=100)


@pytest.fixture
def sample_course_file():
    return os.path.join(FIXTURES_DIR, "sample_course.txt")


@pytest.fixture
def full_course():
    lesson0 = Lesson(
        lesson_number=0, title="Introduction", lesson_link="https://example.com/l0"
    )
    lesson1 = Lesson(
        lesson_number=1, title="Advanced", lesson_link="https://example.com/l1"
    )
    return Course(
        title="Test Course",
        course_link="https://example.com/course",
        instructor="Test Instructor",
        lessons=[lesson0, lesson1],
    )


@pytest.fixture
def minimal_course():
    """Course with all optional fields set to None — exposes Bug A."""
    return Course(title="Minimal Course", course_link=None, instructor=None)


@pytest.fixture
def full_chunk():
    return CourseChunk(
        content="Some lesson content.",
        course_title="Test Course",
        lesson_number=1,
        chunk_index=0,
    )


@pytest.fixture
def null_lesson_chunk():
    """Chunk with lesson_number=None (fallback path) — exposes Bug B."""
    return CourseChunk(
        content="Content with no lesson.",
        course_title="Test Course",
        lesson_number=None,
        chunk_index=0,
    )
