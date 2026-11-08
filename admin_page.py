"""Admin dashboard: login, analytics, filterable results + Excel export, question-bank pipeline."""
from __future__ import annotations

import hmac
import io
import time

import pandas as pd
import plotly.express as px
import streamlit as st

import db
from security import verify_password
from ui import BRAND_YELLOW, hero, show_table

STATUS_ORDER = ["Passed", "Failed", "Not Enough Info"]
STATUS_COLORS = {"Passed": "#2E8B57", "Failed": "#C62828", "Not Enough Info": BRAND_YELLOW}

EXPORT_COLUMNS = {
    "submitted_at": "Submitted (EAT)",
    "tester_name": "Tester",
    "department": "Department",
    "section": "Section",
    "language": "Language",
    "category": "Category",
    "question_id": "Question ID",
    "question_text": "Question / Instruction",
    "actual_response": "Actual Response",
    "comment": "Comment",
    "status": "Status",
}


# --------------------------------------------------------------------------- auth
def _admin_credentials() -> tuple[str, str] | None:
    from config import get_setting

    user, pw_hash = get_setting("ADMIN_USERNAME"), get_setting("ADMIN_PASSWORD_HASH")
    return (user, pw_hash) if user and pw_hash else None


def _login() -> None:
    hero("Admin Console", "Chatbot evaluation results", compact=True)
    creds = _admin_credentials()
    if creds is None:
        st.error("Admin credentials are not configured. Set ADMIN_USERNAME and ADMIN_PASSWORD_HASH in .env or Streamlit Secrets.")
        return
    with st.form("admin_login"):
        user = st.text_input("Username")
        pwd = st.text_input("Password", type="password")
        go = st.form_submit_button("Sign in", type="primary")
    if go:
        ok_user = hmac.compare_digest(user.encode(), creds[0].encode())
        ok_pwd = verify_password(pwd, creds[1])  # always run, so timing doesn't reveal the username
        if ok_user and ok_pwd:
            st.session_state.admin_ok = True
            st.rerun()
        else:
            time.sleep(1.0)  # slow down guessing
            st.error("Invalid username or password.")


# --------------------------------------------------------------------------- helpers
def _status_counts(df: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    return df.groupby(by + ["status"]).size().reset_index(name="count")


def _style(fig, height=380):
    fig.update_layout(
        height=height,
        margin=dict(l=10, r=10, t=50, b=10),
        font=dict(color="#111"),
        legend_title_text="Status",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def _excel_bytes(df: pd.DataFrame) -> bytes:
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    export = df[list(EXPORT_COLUMNS)].rename(columns=EXPORT_COLUMNS)
    summary = (
        df.pivot_table(index=["department", "section", "language"], columns="status", values="id",
                       aggfunc="count", fill_value=0)
        .reindex(columns=STATUS_ORDER, fill_value=0)
        .reset_index()
        .rename(columns={"department": "Department", "section": "Section", "language": "Language"})
    )
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        export.to_excel(xw, sheet_name="Evaluations", index=False)
        summary.to_excel(xw, sheet_name="Summary", index=False)
        for ws in xw.book.worksheets:
            for cell in ws[1]:
                cell.fill = PatternFill("solid", fgColor="F1AB15")
                cell.font = Font(bold=True, color="000000")
            ws.freeze_panes = "A2"
            for i, col in enumerate(ws.columns, 1):
                width = min(60, max(12, max(len(str(c.value or "")) for c in list(col)[:200]) + 2))
                ws.column_dimensions[get_column_letter(i)].width = width
                if ws.title == "Evaluations":
                    for c in list(col)[1:]:
                        c.alignment = Alignment(wrap_text=True, vertical="top")
    return buf.getvalue()


# --------------------------------------------------------------------------- filters
def _filters(df: pd.DataFrame, key: str) -> pd.DataFrame:
    c = st.columns(5)
    lang = c[0].multiselect("Language", sorted(df["language"].unique()), key=f"{key}_lang")
    dept = c[1].multiselect("Department", sorted(df["department"].unique()), key=f"{key}_dept")
    sect = c[2].multiselect("Section", sorted(df["section"].unique()), key=f"{key}_sect")
    cat = c[3].multiselect("Category", sorted(df["category"].unique()), key=f"{key}_cat")
    stat = c[4].multiselect("Status", [s for s in STATUS_ORDER if s in set(df["status"])], key=f"{key}_stat")
    out = df
    for col, sel in [("language", lang), ("department", dept), ("section", sect), ("category", cat), ("status", stat)]:
        if sel:
            out = out[out[col].isin(sel)]
    return out


# --------------------------------------------------------------------------- tabs
def _overview(df: pd.DataFrame) -> None:
    if df.empty:
        st.info("No evaluations match the current filters.")
        return
    total = len(df)
    n = df["status"].value_counts()
    k = st.columns(5)
    k[0].metric("Evaluated answers", f"{total:,}")
    k[1].metric("Testers", df["tester_key"].nunique())
    k[2].metric("Pass rate", f"{n.get('Passed', 0) / total:.1%}")
    k[3].metric("Failed", f"{n.get('Failed', 0):,}")
    k[4].metric("Not enough info", f"{n.get('Not Enough Info', 0):,}")

    c1, c2 = st.columns(2)
    pie = px.pie(
        _status_counts(df, []), names="status", values="count", hole=0.45,
        color="status", color_discrete_map=STATUS_COLORS, category_orders={"status": STATUS_ORDER},
        title="Overall status distribution",
    )
    c1.plotly_chart(_style(pie), width="stretch")
    by_dept = px.bar(
        _status_counts(df, ["department"]), x="department", y="count", color="status", barmode="stack",
        color_discrete_map=STATUS_COLORS, category_orders={"status": STATUS_ORDER},
        title="Status by department", labels={"department": "", "count": "Answers"},
    )
    c2.plotly_chart(_style(by_dept), width="stretch")

    c3, c4 = st.columns(2)
    sec_lang = _status_counts(df.assign(section_language=df["section"] + " · " + df["language"]), ["section_language"])
    pie2 = px.bar(
        sec_lang, x="section_language", y="count", color="status", barmode="group",
        color_discrete_map=STATUS_COLORS, category_orders={"status": STATUS_ORDER},
        title="Status by section and language", labels={"section_language": "", "count": "Answers"},
    )
    c3.plotly_chart(_style(pie2), width="stretch")
    by_cat = px.bar(
        _status_counts(df, ["category"]), y="category", x="count", color="status", orientation="h",
        barmode="stack", color_discrete_map=STATUS_COLORS, category_orders={"status": STATUS_ORDER},
        title="Status by category (share of answers)", labels={"category": "", "count": "Share"},
    )
    by_cat.update_layout(barnorm="percent")
    by_cat.update_xaxes(ticksuffix="%")
    c4.plotly_chart(_style(by_cat), width="stretch")

    st.subheader("Participation")
    part = (
        df.groupby(["department", "section", "language"])["tester_key"].nunique().reset_index(name="testers")
        .assign(col=lambda d: d["section"] + " · " + d["language"])
        .pivot(index="department", columns="col", values="testers").fillna(0).astype(int)
    )
    part["Unique testers"] = df.groupby("department")["tester_key"].nunique()
    st.caption("Number of testers who submitted each section (rows = departments).")
    show_table(part, index=True)

    st.subheader("Problem questions")
    pdf = _filters(df, "ov")  # filters apply to this table only
    bad = pdf[pdf["status"] != "Passed"]
    if bad.empty:
        st.success("No failed or incomplete answers in this selection.")
    else:
        grp = pdf.groupby(["question_id", "department", "language", "category", "question_text"])["status"]
        problem = pd.DataFrame({
            "answers": grp.size(),
            "failed": grp.apply(lambda s: (s == "Failed").sum()),
            "not_enough_info": grp.apply(lambda s: (s == "Not Enough Info").sum()),
        }).reset_index()
        problem["problem_rate"] = (problem["failed"] + problem["not_enough_info"]) / problem["answers"]
        problem = problem[problem["problem_rate"] > 0].sort_values(
            ["problem_rate", "answers"], ascending=False).head(25)
        problem["problem_rate"] = problem["problem_rate"].map("{:.0%}".format)
        show_table(problem)


def _results(df: pd.DataFrame) -> None:
    df = _filters(df, "res")
    st.caption(f"{len(df):,} rows match the filters.")
    if df.empty:
        return
    st.download_button(
        "⬇️ Export filtered results to Excel",
        data=_excel_bytes(df),
        file_name=f"chatbot_evaluation_{pd.Timestamp.now():%Y%m%d_%H%M}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
    )
    show_table(df[list(EXPORT_COLUMNS)].rename(columns=EXPORT_COLUMNS), height=600)


def _question_bank() -> None:
    qdf = db.load_questions()
    if qdf.empty:
        st.info("The question bank is empty. Load it with:  python -m pipeline.ingest")
        return
    act = qdf[qdf["is_active"]]
    st.caption(f"{len(act):,} active questions ({len(qdf) - len(act):,} inactive).")

    c = st.columns(5)
    dept = c[0].multiselect("Department", sorted(qdf["department"].unique()), key="qb_dept")
    sect = c[1].multiselect("Section", sorted(qdf["section"].unique()), key="qb_sect")
    lang = c[2].multiselect("Language", sorted(qdf["language"].unique()), key="qb_lang")
    cat = c[3].multiselect("Category", sorted(qdf["category"].unique()), key="qb_cat")
    state = c[4].selectbox("Status", ["Active", "Inactive", "All"], key="qb_state")
    view = qdf
    for col, sel in [("department", dept), ("section", sect), ("language", lang), ("category", cat)]:
        if sel:
            view = view[view[col].isin(sel)]
    if state != "All":
        view = view[view["is_active"] == (state == "Active")]

    st.caption(f"{len(view):,} questions match.")
    show = view.assign(is_active=view["is_active"].map({True: "Yes", False: "No"}))[
        ["question_id", "department", "section", "language", "category", "question_type", "question_text", "is_active"]
    ].rename(columns={
        "question_id": "Question ID", "department": "Department", "section": "Section", "language": "Language",
        "category": "Category", "question_type": "Type", "question_text": "Question / Instruction",
        "is_active": "Active",
    })
    show_table(show, height=620)


def _comments() -> None:
    fdf = db.load_feedback()
    if fdf.empty:
        st.info("No comments have been submitted yet.")
        return
    c = st.columns(3)
    dept = c[0].multiselect("Department", sorted(fdf["department"].unique()), key="fb_dept")
    view = fdf[fdf["department"].isin(dept)] if dept else fdf
    c[1].metric("Comments", f"{len(view):,}")
    show = view[["submitted_at", "tester_name", "department", "comment"]].rename(columns={
        "submitted_at": "Submitted (EAT)", "tester_name": "Tester", "department": "Department", "comment": "Comment"})
    buf = io.BytesIO()
    show.to_excel(buf, index=False, engine="openpyxl")
    st.download_button(
        "⬇️ Export comments to Excel", data=buf.getvalue(),
        file_name=f"chatbot_comments_{pd.Timestamp.now():%Y%m%d_%H%M}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    show_table(show, height=600)


# --------------------------------------------------------------------------- entry
def render() -> None:
    if not st.session_state.get("admin_ok"):
        _login()
        return

    top = st.columns([6, 1, 1])
    with top[0]:
        hero("Admin Console", "Chatbot evaluation results", compact=True)
    if top[1].button("↻ Refresh"):
        st.cache_data.clear()
        st.rerun()
    if top[2].button("Sign out"):
        st.session_state.admin_ok = False
        st.rerun()

    tab_over, tab_res, tab_q, tab_fb = st.tabs(
        ["📊 Overview", "📋 Evaluation results", "🗂️ Question bank & data", "💬 Comments"]
    )

    try:
        df = db.load_evaluations()
    except Exception as exc:  # noqa: BLE001
        st.error(f"Database error: {exc}")
        return

    with tab_over:
        if df.empty:
            st.info("No evaluations have been submitted yet.")
        else:
            _overview(df)
    with tab_res:
        if df.empty:
            st.info("No evaluations have been submitted yet.")
        else:
            _results(df)
    with tab_q:
        _question_bank()
    with tab_fb:
        _comments()
