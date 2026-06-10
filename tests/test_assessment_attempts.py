import pytest

from campusops.assessments.attempts import AssessmentBook
from campusops.assessments.models import Assessment, AssessmentAttempt, Question
from campusops.assessments.scoring import ScorePolicy, score_attempt


def make_assessment(*, published=True):
    return Assessment(
        assessment_id=" mid-term.ict ",
        title="ICT Mid Term",
        programme="Information Technology",
        published=published,
        questions=(
            Question("Q1", "What is 2 + 2?", "math basics", "4", points=2),
            Question("Q2", "Binary of decimal 5?", "digital logic", "101", points=3),
            Question("Q3", "Name the HTTP success code", "web", "200", points=1),
        ),
    )


def test_question_and_assessment_normalize_old_labels():
    assessment = make_assessment()

    assert assessment.assessment_id == "mid_term_ict"
    assert assessment.questions[0].question_id == "q1"
    assert assessment.questions[0].topic == "math_basics"
    assert assessment.total_points == 6


def test_assessment_rejects_duplicate_question_ids():
    with pytest.raises(ValueError, match="duplicate question ids"):
        Assessment(
            assessment_id="quiz-one",
            title="Quiz One",
            programme="IT",
            questions=(
                Question("Q1", "First", "general", "a"),
                Question(" q1 ", "Second", "general", "b"),
            ),
        )


def test_attempt_normalizes_student_and_response_keys_without_mutating_input():
    responses = {" Q1 ": " 4 ", "q-2": "101"}
    attempt = AssessmentAttempt(
        attempt_id=" Attempt.01 ",
        student_id=" s001 ",
        assessment_id="mid-term.ict",
        responses=responses,
        metadata={"device": {"id": "tablet-1"}},
    )

    responses[" Q1 "] = "mutated"

    assert attempt.attempt_id == "attempt_01"
    assert attempt.student_id == "S001"
    assert attempt.assessment_id == "mid_term_ict"
    assert attempt.responses == {"q1": " 4 ", "q_2": "101"}
    assert attempt.metadata == {"device": {"id": "tablet-1"}}


def test_score_attempt_counts_correct_missing_and_extra_responses():
    assessment = make_assessment()
    attempt = AssessmentAttempt(
        attempt_id="A1",
        student_id="S001",
        assessment_id="mid_term_ict",
        responses={
            "q1": " 4 ",
            "q2": "wrong",
            "extra": "ignored",
        },
    )

    result = score_attempt(assessment, attempt)

    assert result.raw_points == 2
    assert result.adjusted_points == 2
    assert result.total_points == 6
    assert result.fraction == pytest.approx(0.333333)
    assert result.passed is False
    assert result.missing_questions == ("q3",)
    assert result.extra_responses == ("extra",)


def test_score_policy_applies_late_penalty_and_topic_weights():
    assessment = make_assessment()
    attempt = AssessmentAttempt(
        attempt_id="A1",
        student_id="S001",
        assessment_id="mid_term_ict",
        responses={"q1": "4", "q2": "101", "q3": "200"},
        late_minutes=20,
    )
    policy = ScorePolicy(
        passing_fraction=0.8,
        late_penalty_per_minute=0.1,
        max_late_penalty=1.5,
        topic_weights={"digital_logic": 2.0},
    )

    result = score_attempt(assessment, attempt, policy=policy)

    assert result.raw_points == 9
    assert result.adjusted_points == 7.5
    assert result.total_points == 9
    assert result.fraction == pytest.approx(0.833333)
    assert result.passed is True
    assert result.topic_breakdown["digital_logic"] == {
        "earned": 6.0,
        "possible": 6.0,
        "correct": 1.0,
        "count": 1.0,
    }


def test_assessment_book_publish_submit_score_and_audit():
    book = AssessmentBook()
    assessment = book.add_assessment(make_assessment(published=False), actor="lecturer")

    assert assessment.published is False

    with pytest.raises(ValueError, match="not published"):
        book.submit_attempt(
            AssessmentAttempt("A1", "S001", "mid-term.ict", {"q1": "4"}),
            actor="tablet",
        )

    book.publish("mid-term.ict", actor="lecturer")
    book.submit_attempt(
        AssessmentAttempt("A1", "S001", "mid-term.ict", {"q1": "4", "q2": "101", "q3": "200"}),
        actor="tablet",
    )

    result = book.score("A1")

    assert result.passed is True
    assert [event.event_type for event in book.audit.all_events()] == [
        "assessment_created",
        "assessment_published",
        "assessment_attempt_submitted",
    ]


def test_assessment_book_rejects_duplicate_attempts():
    book = AssessmentBook(assessments=[make_assessment()])
    attempt = AssessmentAttempt("A1", "S001", "mid-term.ict", {"q1": "4"})

    book.submit_attempt(attempt)

    with pytest.raises(ValueError, match="attempt already exists"):
        book.submit_attempt(attempt)


def test_attempts_for_student_are_sorted_by_assessment_and_time():
    book = AssessmentBook(
        assessments=[
            make_assessment(),
            Assessment(
                assessment_id="assignment-2",
                title="Assignment Two",
                programme="Information Technology",
                published=True,
                questions=(Question("Q1", "One", "general", "yes"),),
            ),
        ]
    )

    book.submit_attempt(AssessmentAttempt("B2", "S001", "mid-term.ict", {"q1": "4"}, submitted_at="2026-01-02T10:00:00+00:00"))
    book.submit_attempt(AssessmentAttempt("A1", "S001", "assignment-2", {"q1": "yes"}, submitted_at="2026-01-01T10:00:00+00:00"))
    book.submit_attempt(AssessmentAttempt("C3", "S002", "mid-term.ict", {"q1": "4"}, submitted_at="2026-01-01T11:00:00+00:00"))

    assert [attempt.attempt_id for attempt in book.attempts_for_student(" s001 ")] == ["a1", "b2"]


def test_leaderboard_orders_by_score_then_student_then_attempt():
    book = AssessmentBook(assessments=[make_assessment()])

    book.submit_attempt(AssessmentAttempt("A2", "S002", "mid-term.ict", {"q1": "4", "q2": "101", "q3": "200"}))
    book.submit_attempt(AssessmentAttempt("A1", "S001", "mid-term.ict", {"q1": "4", "q2": "101", "q3": "200"}))
    book.submit_attempt(AssessmentAttempt("A3", "S003", "mid-term.ict", {"q1": "wrong"}))

    assert [(row.student_id, row.adjusted_points) for row in book.leaderboard("mid-term.ict")] == [
        ("S001", 6.0),
        ("S002", 6.0),
        ("S003", 0.0),
    ]


def test_assessment_book_json_roundtrip(tmp_path):
    book = AssessmentBook(assessments=[make_assessment()])
    book.submit_attempt(
        AssessmentAttempt("A1", "S001", "mid-term.ict", {"q1": "4", "q2": "101", "q3": "200"})
    )

    path = tmp_path / "book.json"
    book.save_json(path)
    loaded = AssessmentBook.load_json(path)

    assert len(loaded) == 1
    assert loaded.score("A1").adjusted_points == 6
    assert loaded.to_dict()["assessments"][0]["assessment_id"] == "mid_term_ict"