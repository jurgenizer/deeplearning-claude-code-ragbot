import os
import pytest


def test_parse_minimal_valid_course(document_processor, sample_course_file):
    course, chunks = document_processor.process_course_document(sample_course_file)
    assert course.title == "Test Course"
    assert course.course_link == "https://example.com/course"
    assert course.instructor == "Test Instructor"
    assert len(course.lessons) == 2
    assert course.lessons[0].lesson_number == 0
    assert course.lessons[1].lesson_number == 1


def test_parse_course_lesson_links(document_processor, sample_course_file):
    course, _ = document_processor.process_course_document(sample_course_file)
    assert course.lessons[0].lesson_link == "https://example.com/lesson0"
    assert course.lessons[1].lesson_link == "https://example.com/lesson1"


def test_parse_course_produces_chunks(document_processor, sample_course_file):
    _, chunks = document_processor.process_course_document(sample_course_file)
    assert len(chunks) > 0
    for chunk in chunks:
        assert chunk.course_title == "Test Course"
        assert chunk.content  # non-empty


def test_parse_course_without_instructor(document_processor, tmp_path):
    f = tmp_path / "no_instructor.txt"
    f.write_text(
        "Course Title: No Instructor Course\n"
        "Course Link: https://example.com\n"
        "Course Instructor: Unknown\n\n"
        "Lesson 0: Only Lesson\n"
        "Some content here.\n"
    )
    course, _ = document_processor.process_course_document(str(f))
    assert course.instructor is None


def test_parse_course_without_link(document_processor, tmp_path):
    f = tmp_path / "no_link.txt"
    f.write_text(
        "Course Title: No Link Course\n"
        "Course Instructor: Someone\n\n"
        "Lesson 0: Only Lesson\n"
        "Some content here.\n"
    )
    course, _ = document_processor.process_course_document(str(f))
    assert course.course_link is None


def test_parse_fallback_no_lessons(document_processor, tmp_path):
    """When there are no Lesson markers the entire content becomes chunks with lesson_number=None."""
    f = tmp_path / "no_lessons.txt"
    f.write_text(
        "Course Title: No Lessons Course\n"
        "Course Link: https://example.com\n"
        "Course Instructor: Someone\n\n"
        "This is just plain content with no lesson markers at all.\n"
    )
    course, chunks = document_processor.process_course_document(str(f))
    assert len(chunks) > 0
    for chunk in chunks:
        assert chunk.lesson_number is None


def test_chunk_text_empty_input(document_processor):
    assert document_processor.chunk_text("") == []


def test_chunk_text_shorter_than_chunk_size(document_processor):
    text = "This is a short sentence."
    chunks = document_processor.chunk_text(text)
    assert len(chunks) == 1
    assert "short sentence" in chunks[0]


def test_chunk_text_respects_size_limit(document_processor):
    # Build text with many short sentences to force multiple chunks
    sentence = "This is one sentence."
    text = " ".join([sentence] * 60)  # well over 800 chars
    chunks = document_processor.chunk_text(text)
    assert len(chunks) > 1
    # Allow small overhead from sentence boundary alignment
    for chunk in chunks:
        assert len(chunk) <= document_processor.chunk_size + len(sentence)


def test_chunk_text_produces_overlap(document_processor):
    # Use very small chunk size to force multiple chunks with overlap
    dp_small = type(document_processor).__new__(type(document_processor))
    dp_small.chunk_size = 80
    dp_small.chunk_overlap = 30
    sentences = [f"Sentence number {i} has some content." for i in range(10)]
    text = " ".join(sentences)
    chunks = dp_small.chunk_text(text)
    assert len(chunks) >= 2
    # The last few words of chunk[0] should appear in chunk[1]
    last_words_of_first = chunks[0].split()[-3:]
    second_chunk_words = chunks[1].split()
    assert any(w in second_chunk_words for w in last_words_of_first)


def test_chunk_counter_increments_across_lessons(document_processor, sample_course_file):
    _, chunks = document_processor.process_course_document(sample_course_file)
    indices = [c.chunk_index for c in chunks]
    # All indices should be unique
    assert len(indices) == len(set(indices))
    # Indices should be non-decreasing
    assert indices == sorted(indices)
