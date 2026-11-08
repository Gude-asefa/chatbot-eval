"""Tester-facing pages: welcome -> evaluate."""
from __future__ import annotations

import html

import streamlit as st

import db
from ui import CHATBOT_DESCRIPTION, CHATBOT_NAME, hero
from validation import STATUS_OPTIONS, validate

SECTION_LABEL = {"Information": "Informational", "Action": "Action"}
LANG_LABEL = {"Amharic": "Amharic · አማርኛ", "English": "English"}


# --------------------------------------------------------------------------- state
def _init_state() -> None:
    for k, v in {
        "stage": "welcome",
        "tester_name": "",
        "department": None,
        "sel_section": None,
        "sel_lang": None,
        "flash": None,
    }.items():
        st.session_state.setdefault(k, v)


def render() -> None:
    _init_state()
    if st.session_state.stage == "welcome":
        _welcome()
    else:
        _evaluate()


# --------------------------------------------------------------------------- page 1
def _start() -> None:
    st.session_state.tester_name = st.session_state.in_name.strip()
    st.session_state.department = st.session_state.in_dept
    st.session_state.stage = "evaluate"


def _welcome() -> None:
    hero(f"{CHATBOT_NAME} · Pilot Evaluation", "Bank of Abyssinia")

    st.markdown(f'<div class="card"><h4>About the chatbot</h4>{CHATBOT_DESCRIPTION}</div>', unsafe_allow_html=True)

    st.markdown(
        """
<div class="card"><h4>How the testing works</h4>
<ol>
<li>Enter your name and choose your department below.</li>
<li>You will see two test sections: <b>Informational</b> and <b>Action</b>. Each is available in <b>Amharic</b> and <b>English</b> - that is <b>4 submissions</b> in total.</li>
<li>For every test case, perform the instruction in the chatbot (type, speak or click) and compare the result with what you expect.</li>
<li>Record the <b>actual response</b> of the chatbot, an optional <b>comment</b>, and a <b>status</b>.</li>
<li>Press <b>Submit</b> at the bottom of each section. <b>A section can only be submitted once</b>, so review your answers first.</li>
</ol></div>
""",
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns(2)
    with c1:
        st.markdown(
            """
<div class="card"><h4>Status guide</h4>
<ul>
<li><b>Passed</b> - the chatbot answered / acted correctly. Response and comment are optional.</li>
<li><b>Failed</b> - wrong or no answer. The <b>actual response</b> is required.</li>
<li><b>Not Enough Info</b> <i>(Informational only)</i> - answer is incomplete. The <b>actual response</b> and a <b>comment on what to improve</b> are both required.</li>
</ul></div>
""",
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            """
<div class="card"><h4>Data protection</h4>
Use <b>test accounts</b> where possible. Do <b>not</b> type real customer names, account numbers,
card numbers, phone numbers or balances in your responses or comments - mask them
(e.g. <code>1000XXXXXXXXX</code>). Submissions containing long digit sequences are rejected.
</div>
""",
            unsafe_allow_html=True,
        )

    try:
        departments = db.list_departments()
    except Exception as exc:  # noqa: BLE001
        st.error("The evaluation database is not reachable right now. Please try again shortly.")
        st.caption(f"Technical detail for the administrator: {type(exc).__name__}")
        return
    if not departments:
        st.warning("No test questions have been loaded yet. Please contact the evaluation administrator.")
        return

    st.subheader("Your details")
    st.text_input("Full name", key="in_name", placeholder="e.g. Abebe Kebede", max_chars=100)
    st.selectbox("Department", departments, index=None, key="in_dept", placeholder="Select your department")
    ready = bool(st.session_state.get("in_name", "").strip()) and bool(st.session_state.get("in_dept"))
    st.button("Continue", type="primary", disabled=not ready, on_click=_start)
    if not ready:
        st.caption("Continue is enabled once you enter your name (press Enter) and choose your department.")


# --------------------------------------------------------------------------- page 2
def _toggle_section(section: str) -> None:
    if st.session_state.sel_section == section:
        st.session_state.sel_section = None
    else:
        st.session_state.sel_section = section
    st.session_state.sel_lang = None


def _pick_lang(lang: str) -> None:
    st.session_state.sel_lang = None if st.session_state.sel_lang == lang else lang


def _restart() -> None:
    for k in ("stage", "tester_name", "department", "sel_section", "sel_lang", "flash", "in_name", "in_dept"):
        st.session_state.pop(k, None)


def _evaluate() -> None:
    name, dept = st.session_state.tester_name, st.session_state.department
    key = db.tester_key(name, dept)

    hero(f"{CHATBOT_NAME} · Evaluation", f"{html.escape(name)} · {html.escape(dept)}", compact=True)

    available = db.available_sections(dept)
    done = db.submitted_sections(key)
    todo = [x for x in available if x not in done]

    if st.session_state.flash:
        st.success(st.session_state.flash)
        st.session_state.flash = None

    total = len(available)
    finished = total - len(todo)
    st.progress(finished / total if total else 0.0, text=f"{finished} of {total} sections submitted")

    if not available:
        st.warning("There are no active questions for your department. Please contact the administrator.")
    elif not todo:
        st.markdown(
            '<div class="card"><h4>🎉 Thank you!</h4>You have submitted all of your evaluation sections. '
            "Your feedback will be used to improve the chatbot. You may now close this page.</div>",
            unsafe_allow_html=True,
        )

    for section in db.SECTIONS:
        langs = [l for s, l in available if s == section]
        if not langs:
            continue
        sec_done = all((section, l) in done for l in langs)
        selected = st.session_state.sel_section == section
        st.button(
            f"{'✅ ' if sec_done else ''}{SECTION_LABEL[section]}",
            key=f"sec_{section}",
            type="primary" if selected else "secondary",
            width="stretch",
            on_click=_toggle_section,
            args=(section,),
        )
        if not selected:
            continue

        cols = st.columns(len(langs))
        for col, lang in zip(cols, langs):
            with col:
                st.button(
                    f"{'✅ ' if (section, lang) in done else ''}{LANG_LABEL[lang]}",
                    key=f"lang_{section}_{lang}",
                    type="primary" if st.session_state.sel_lang == lang else "secondary",
                    width="stretch",
                    on_click=_pick_lang,
                    args=(lang,),
                )
        lang = st.session_state.sel_lang
        if lang in langs:
            _section_form(name, dept, section, lang, done)

    st.divider()
    st.button(
        "Finish and exit",
        on_click=_restart,
        disabled=bool(todo) or not available,
        help="Enabled once all sections are submitted." if todo else "Returns to the welcome page.",
    )


def _section_form(name: str, dept: str, section: str, lang: str, done: set) -> None:
    title = f"{SECTION_LABEL[section]} · {lang}"
    if (section, lang) in done:
        st.success(
            f"✅ You have already submitted **{title}**. Your answers are saved - "
            "please continue with the other sections."
        )
        return

    qs = db.get_questions(dept, section, lang)
    if not qs:
        st.info("No questions available in this section.")
        return

    options = STATUS_OPTIONS[section]
    st.markdown(f"##### {title} - {len(qs)} test cases")
    with st.form(f"form_{section}_{lang}", border=False):
        for i, q in enumerate(qs, 1):
            k = f"{section}_{lang}_{q['question_id']}"
            with st.container(border=True):
                st.markdown(
                    f'<div class="q-head"><span class="q-no">{i}</span>'
                    f'<span class="q-cat">{html.escape(q["category"])}</span>'
                    f'<span class="q-type">{html.escape(q["question_type"])}</span>'
                    f'<span class="q-id">{html.escape(q["question_id"])}</span></div>'
                    f'<div class="q-text">{html.escape(q["question_text"])}</div>',
                    unsafe_allow_html=True,
                )
                c1, c2 = st.columns(2)
                c1.text_area(
                    "Actual response of the chatbot",
                    key=f"{k}_resp",
                    height=110,
                    max_chars=4000,
                    help="Required if Failed or Not Enough Info.",
                )
                c2.text_area(
                    "Comment" + (" / what needs to be improved" if section == "Information" else ""),
                    key=f"{k}_comment",
                    height=110,
                    max_chars=4000,
                    help="Required if Not Enough Info.",
                )
                st.radio("Status", options, index=None, horizontal=True, key=f"{k}_status")

        submitted = st.form_submit_button(f"Submit {title}", type="primary")

    if not submitted:
        return

    items = [
        {
            "no": i,
            "status": st.session_state.get(f"{section}_{lang}_{q['question_id']}_status"),
            "actual_response": st.session_state.get(f"{section}_{lang}_{q['question_id']}_resp", "") or "",
            "comment": st.session_state.get(f"{section}_{lang}_{q['question_id']}_comment", "") or "",
        }
        for i, q in enumerate(qs, 1)
    ]
    errors = validate(section, items)
    if errors:
        st.error("Please fix the following before submitting:\n\n" + "\n".join(f"- {e}" for e in errors))
        return

    answers = [
        {
            "question_id": q["question_id"],
            "category": q["category"],
            "question_type": q["question_type"],
            "question_text": q["question_text"],
            "status": it["status"],
            "actual_response": it["actual_response"].strip(),
            "comment": it["comment"].strip(),
        }
        for q, it in zip(qs, items)
    ]
    try:
        result = db.save_submission(name, dept, section, lang, answers)
    except Exception as exc:  # noqa: BLE001
        st.error(f"Could not save your answers ({type(exc).__name__}). Nothing was submitted - please try again.")
        return

    if result == "duplicate":
        st.session_state.flash = f"{title} was already submitted earlier - no changes were made."
    else:
        st.session_state.flash = f"✅ {title} submitted. Thank you! Please continue with the remaining sections."
    st.session_state.sel_section = None
    st.session_state.sel_lang = None
    st.rerun()
