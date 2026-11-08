"""Database layer (Neon PostgreSQL via SQLAlchemy).

Two tables only:
  * questions    - the test cases loaded from the Excel file by the pipeline
  * evaluations  - one row per tester per question answered
"""
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
    # A tester can answer a given question only once -> a section can only be submitted once
    sa.UniqueConstraint("tester_key", "question_id", name="uq_tester_question"),
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
    metadata.create_all(engine)  # creates the two tables on first run
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
    q = (
        sa.select(evaluations.c.section, evaluations.c.language)
        .where(evaluations.c.tester_key == key)
        .distinct()
    )
    with get_engine().connect() as conn:
        return {(r[0], r[1]) for r in conn.execute(q)}


def save_submission(name: str, department: str, section: str, language: str, answers: list[dict]) -> str:
    """Insert all answers for one section+language atomically. Returns 'ok' or 'duplicate'."""
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
    try:
        with get_engine().begin() as conn:
            already = conn.execute(
                sa.select(sa.func.count())
                .select_from(evaluations)
                .where(
                    evaluations.c.tester_key == key,
                    evaluations.c.section == section,
                    evaluations.c.language == language,
                )
            ).scalar()
            if already:
                return "duplicate"
            conn.execute(sa.insert(evaluations), rows)
        return "ok"
    except sa.exc.IntegrityError:
        return "duplicate"


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
