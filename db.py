"""Database layer (Neon PostgreSQL via SQLAlchemy)."""
from __future__ import annotations

import re
from datetime import datetime, timezone

import sqlalchemy as sa
import streamlit as st

SECTIONS = ["Information", "Action"]
LANGUAGES = ["Amharic", "English"]

metadata = sa.MetaData()

questions = sa.Table(
    "questions",
    metadata,
    sa.Column("question_id", sa.String(50), primary_key=True),
    sa.Column("department", sa.String(100), nullable=False, index=True),
    sa.Column("section", sa.String(20), nullable=False),
    sa.Column("category", sa.String(100), nullable=False),
    sa.Column("question_type", sa.String(30), nullable=False, server_default=""),
    sa.Column("language", sa.String(20), nullable=False),
    sa.Column("question_text", sa.Text, nullable=False),
    sa.Column("expected_answer", sa.Text, nullable=False, server_default=""),
    sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
)

evaluations = sa.Table(
    "evaluations",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("tester_name", sa.String(200), nullable=False),
    sa.Column("tester_key", sa.String(320), nullable=False, index=True),
    sa.Column("department", sa.String(100), nullable=False, index=True),
    sa.Column("section", sa.String(20), nullable=False),
    sa.Column("language", sa.String(20), nullable=False),
    sa.Column("question_id", sa.String(50), sa.ForeignKey("questions.question_id"), nullable=False),
    # Snapshot of the question at answer time (keeps history if the Excel changes later)
    sa.Column("category", sa.String(100), nullable=False),
    sa.Column("question_type", sa.String(30), nullable=False, server_default=""),
    sa.Column("question_text", sa.Text, nullable=False),
    sa.Column("status", sa.String(30), nullable=False),
    sa.Column("actual_response", sa.Text, nullable=False, server_default=""),
    sa.Column("comment", sa.Text, nullable=False, server_default=""),
    sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
    # Keep one current answer per tester and question; automatic saves update this row.
    sa.UniqueConstraint("tester_key", "question_id", name="uq_tester_question"),
)

answer_drafts = sa.Table(
    "answer_drafts",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("tester_key", sa.String(320), nullable=False, index=True),
    sa.Column("department", sa.String(100), nullable=False),
    sa.Column("section", sa.String(20), nullable=False),
    sa.Column("language", sa.String(20), nullable=False),
    sa.Column("question_id", sa.String(50), sa.ForeignKey("questions.question_id"), nullable=False),
    sa.Column("category", sa.String(100), nullable=False),
    sa.Column("question_type", sa.String(30), nullable=False, server_default=""),
    sa.Column("question_text", sa.Text, nullable=False),
    sa.Column("status", sa.String(30)),
    sa.Column("actual_response", sa.Text, nullable=False, server_default=""),
    sa.Column("comment", sa.Text, nullable=False, server_default=""),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.UniqueConstraint("tester_key", "question_id", name="uq_tester_question_draft"),
)

# Optional overall comment a tester leaves before "Finish and exit"
feedback = sa.Table(
    "feedback",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("tester_name", sa.String(200), nullable=False),
    sa.Column("tester_key", sa.String(320), nullable=False, index=True),
    sa.Column("department", sa.String(100), nullable=False, index=True),
    sa.Column("comment", sa.Text, nullable=False),
    sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
)


# --------------------------------------------------------------------------- connection
def _normalize_url(url: str) -> str:
    url = url.strip()
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://") or url.startswith("postgresql+psycopg2://"):
        url = "postgresql+pg8000://" + url.split("://", 1)[1]
    return url


def get_database_url() -> str:
    """DATABASE_URL from env var, .env file, or Streamlit secrets (see config.py)."""
    from config import get_setting

    url = get_setting("DATABASE_URL")
    if url:
        return _normalize_url(url)
    raise RuntimeError(
        "DATABASE_URL is not configured. Put it in .env (local) or Streamlit Secrets (cloud)."
    )


def make_engine(url: str | None = None) -> sa.Engine:
    url = url or get_database_url()
    if url.startswith("sqlite"):
        return sa.create_engine(url, connect_args={"check_same_thread": False})
    # pg8000 (pure Python) does not understand libpq-style query options; use TLS instead.
    parsed = sa.engine.make_url(url)
    query = {k: v for k, v in parsed.query.items() if k not in ("sslmode", "channel_binding")}
    parsed = parsed.set(query=query)
    local = parsed.host in (None, "localhost", "127.0.0.1")
    return sa.create_engine(
        parsed,
        connect_args={} if local else {"ssl_context": True},
        pool_pre_ping=True,   # Neon suspends idle compute; reconnect transparently
        pool_recycle=240,
        pool_size=5,
        max_overflow=5,
    )


@st.cache_resource(show_spinner="Connecting to database...")
def get_engine() -> sa.Engine:
    engine = make_engine()
    metadata.create_all(engine)
    return engine


# --------------------------------------------------------------------------- helpers
def tester_key(name: str, department: str) -> str:
    clean = re.sub(r"\s+", " ", name.strip().lower())
    return f"{department.strip().lower()}|{clean}"


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------- tester side
@st.cache_data(ttl=300, show_spinner=False)
def list_departments() -> list[str]:
    q = (
        sa.select(questions.c.department)
        .where(questions.c.is_active.is_(True))
        .distinct()
        .order_by(questions.c.department)
    )
    with get_engine().connect() as conn:
        return [r[0] for r in conn.execute(q)]


@st.cache_data(ttl=300, show_spinner=False)
def available_sections(department: str) -> list[tuple[str, str]]:
    """(section, language) combinations that have active questions for this department."""
    q = (
        sa.select(questions.c.section, questions.c.language)
        .where(questions.c.department == department, questions.c.is_active.is_(True))
        .distinct()
    )
    with get_engine().connect() as conn:
        found = {(r[0], r[1]) for r in conn.execute(q)}
    return [(s, l) for s in SECTIONS for l in LANGUAGES if (s, l) in found]


@st.cache_data(ttl=300, show_spinner=False)
def get_questions(department: str, section: str, language: str) -> list[dict]:
    q = (
        sa.select(questions)
        .where(
            questions.c.department == department,
            questions.c.section == section,
            questions.c.language == language,
            questions.c.is_active.is_(True),
        )
        .order_by(questions.c.question_id)
    )
    with get_engine().connect() as conn:
        return [dict(r._mapping) for r in conn.execute(q)]


def submitted_sections(key: str) -> set[tuple[str, str]]:
    info_q = (
        sa.select(evaluations.c.section, evaluations.c.language)
        .where(evaluations.c.tester_key == key, evaluations.c.section == "Information")
        .distinct()
    )
    with get_engine().connect() as conn:
        completed = {(r[0], r[1]) for r in conn.execute(info_q)}
        action_groups = conn.execute(
            sa.select(evaluations.c.department, evaluations.c.language)
            .where(evaluations.c.tester_key == key, evaluations.c.section == "Action")
            .distinct()
        )
        for department, language in action_groups:
            total = conn.execute(
                sa.select(sa.func.count())
                .select_from(questions)
                .where(
                    questions.c.department == department,
                    questions.c.section == "Action",
                    questions.c.language == language,
                    questions.c.is_active.is_(True),
                )
            ).scalar_one()
            answered = conn.execute(
                sa.select(sa.func.count(sa.distinct(evaluations.c.question_id)))
                .select_from(evaluations.join(questions, evaluations.c.question_id == questions.c.question_id))
                .where(
                    evaluations.c.tester_key == key,
                    evaluations.c.department == department,
                    evaluations.c.section == "Action",
                    evaluations.c.language == language,
                    questions.c.is_active.is_(True),
                )
            ).scalar_one()
            drafts = conn.execute(
                sa.select(sa.func.count())
                .select_from(answer_drafts.join(questions, answer_drafts.c.question_id == questions.c.question_id))
                .where(
                    answer_drafts.c.tester_key == key,
                    answer_drafts.c.department == department,
                    answer_drafts.c.section == "Action",
                    answer_drafts.c.language == language,
                    questions.c.is_active.is_(True),
                )
            ).scalar_one()
            if total and answered >= total and not drafts:
                completed.add(("Action", language))
    return completed


def get_answers(key: str, section: str, language: str) -> dict[str, dict]:
    """Load completed answers and overlay newer incomplete drafts."""
    filters = (
        evaluations.c.tester_key == key,
        evaluations.c.section == section,
        evaluations.c.language == language,
    )
    with get_engine().connect() as conn:
        saved = {
            row["question_id"]: dict(row)
            for row in conn.execute(sa.select(evaluations).where(*filters)).mappings()
        }
        drafts = conn.execute(
            sa.select(answer_drafts).where(
                answer_drafts.c.tester_key == key,
                answer_drafts.c.section == section,
                answer_drafts.c.language == language,
            )
        ).mappings()
        for row in drafts:
            saved[row["question_id"]] = dict(row)
    return saved


def _upsert(conn: sa.Connection, table: sa.Table, row: dict, update_columns: list[str]) -> None:
    if conn.dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    elif conn.dialect.name == "sqlite":
        from sqlalchemy.dialects.sqlite import insert
    else:
        raise RuntimeError(f"Autosaving is not supported for database dialect {conn.dialect.name!r}.")

    statement = insert(table).values(**row)
    statement = statement.on_conflict_do_update(
        index_elements=[table.c.tester_key, table.c.question_id],
        set_={column: getattr(statement.excluded, column) for column in update_columns},
    )
    conn.execute(statement)


def save_answer_draft(
    name: str, department: str, section: str, language: str, answer: dict
) -> None:
    """Persist an answer as soon as it changes, even before it is complete."""
    row = {
        "tester_key": tester_key(name, department),
        "department": department,
        "section": section,
        "language": language,
        "question_id": answer["question_id"],
        "category": answer["category"],
        "question_type": answer["question_type"],
        "question_text": answer["question_text"],
        "status": answer["status"],
        "actual_response": answer["actual_response"],
        "comment": answer["comment"],
        "updated_at": _now(),
    }
    with get_engine().begin() as conn:
        _upsert(
            conn,
            answer_drafts,
            row,
            [
                "department",
                "section",
                "language",
                "category",
                "question_type",
                "question_text",
                "status",
                "actual_response",
                "comment",
                "updated_at",
            ],
        )


def save_action_answer(name: str, department: str, language: str, answer: dict) -> None:
    """Save one validated Action answer and remove its pending draft."""
    key = tester_key(name, department)
    row = {
        "tester_name": re.sub(r"\s+", " ", name.strip()),
        "tester_key": key,
        "department": department,
        "section": "Action",
        "language": language,
        "question_id": answer["question_id"],
        "category": answer["category"],
        "question_type": answer["question_type"],
        "question_text": answer["question_text"],
        "status": answer["status"],
        "actual_response": answer["actual_response"],
        "comment": answer["comment"],
        "submitted_at": _now(),
    }
    with get_engine().begin() as conn:
        _upsert(
            conn,
            evaluations,
            row,
            [
                "tester_name",
                "department",
                "section",
                "language",
                "category",
                "question_type",
                "question_text",
                "status",
                "actual_response",
                "comment",
                "submitted_at",
            ],
        )
        conn.execute(
            sa.delete(answer_drafts).where(
                answer_drafts.c.tester_key == key,
                answer_drafts.c.question_id == answer["question_id"],
            )
        )


def save_submission(name: str, department: str, section: str, language: str, answers: list[dict]) -> str:
    """Save a valid section atomically, updating existing answers rather than duplicating them."""
    key = tester_key(name, department)
    now = _now()
    rows = [
        {
            "tester_name": re.sub(r"\s+", " ", name.strip()),
            "tester_key": key,
            "department": department,
            "section": section,
            "language": language,
            "question_id": a["question_id"],
            "category": a["category"],
            "question_type": a["question_type"],
            "question_text": a["question_text"],
            "status": a["status"],
            "actual_response": a["actual_response"],
            "comment": a["comment"],
            "submitted_at": now,
        }
        for a in answers
    ]
    with get_engine().begin() as conn:
        for row in rows:
            _upsert(
                conn,
                evaluations,
                row,
                [
                    "tester_name",
                    "department",
                    "section",
                    "language",
                    "category",
                    "question_type",
                    "question_text",
                    "status",
                    "actual_response",
                    "comment",
                    "submitted_at",
                ],
            )
        conn.execute(
            sa.delete(answer_drafts).where(
                answer_drafts.c.tester_key == key,
                answer_drafts.c.section == section,
                answer_drafts.c.language == language,
            )
        )
    return "ok"


def save_feedback(name: str, department: str, comment: str) -> None:
    with get_engine().begin() as conn:
        conn.execute(
            sa.insert(feedback),
            {
                "tester_name": re.sub(r"\s+", " ", name.strip()),
                "tester_key": tester_key(name, department),
                "department": department,
                "comment": comment.strip(),
                "submitted_at": _now(),
            },
        )


# --------------------------------------------------------------------------- admin side
@st.cache_data(ttl=20, show_spinner=False)
def load_evaluations():
    import pandas as pd  # admin only

    with get_engine().connect() as conn:
        df = pd.read_sql(sa.select(evaluations).order_by(evaluations.c.submitted_at.desc()), conn)
    if not df.empty:
        ts = pd.to_datetime(df["submitted_at"], utc=True)
        # Ethiopia has no DST: EAT = UTC+3
        df["submitted_at"] = (ts + pd.Timedelta(hours=3)).dt.tz_localize(None)
    return df


@st.cache_data(ttl=20, show_spinner=False)
def load_questions():
    import pandas as pd  # admin only

    with get_engine().connect() as conn:
        df = pd.read_sql(sa.select(questions).order_by(questions.c.question_id), conn)
    return df


@st.cache_data(ttl=20, show_spinner=False)
def load_feedback():
    import pandas as pd  # admin only

    with get_engine().connect() as conn:
        df = pd.read_sql(sa.select(feedback).order_by(feedback.c.submitted_at.desc()), conn)
    if not df.empty:
        ts = pd.to_datetime(df["submitted_at"], utc=True)
        df["submitted_at"] = (ts + pd.Timedelta(hours=3)).dt.tz_localize(None)  # EAT
    return df
