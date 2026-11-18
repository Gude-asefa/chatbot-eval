"""Tester-facing pages: welcome -> evaluate."""
from __future__ import annotations

import html

import streamlit as st

import db
from ui import CHATBOT_DESCRIPTION, CHATBOT_NAME, hero
from validation import FAILED, STATUS_OPTIONS, looks_sensitive, validate

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
    hero(f"{CHATBOT_NAME} · Pilot Test", "Bank of Abyssinia")
    if st.session_state.pop("finished", False):
        st.success("Thank you for completing the evaluation. Your answers and comments have been recorded.")

    st.markdown(f'<div class="card"><h4>About the chatbot</h4>{CHATBOT_DESCRIPTION}</div>', unsafe_allow_html=True)

    st.markdown(
        """
<div class="card"><h4>How the testing works</h4>
<ol>
<li>Enter your name and select your department. Use the same name each time to track your progress and continue where you left off.</li>
<li>You will see two test sections: <b>Informational</b> and <b>Action</b>. Each is available in <b>Amharic</b> and <b>English</b>.</li>
<li>For every test case, perform the instruction in the chatbot (type, speak or click) and compare the result with what you expect.</li>
<li>Record the <b>actual response</b> of the chatbot, an optional <b>comment</b>, and a <b>status</b>.</li>
<li>For <b>Informational</b>, press <b>Submit</b> when the section is complete; it can only be submitted once. For <b>Action</b>, select a status to save each answer. A <b>Failed</b> answer needs an actual response before it saves. Change the status again to save later edits; completing an Action section opens the next incomplete Action section.</li>
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
<div class="card"><h4>Chatbot access and Feedback</h4>
Explore the chatbot by asking any questions you like.
Experiment with different queries, test its capabilities,
and share your feedback or comments with us.
<p style="margin:8px 0 2px 0"><b>Telegram:</b> <code>@boachatbottest_bot</code></p>
<p style="margin:2px 0"><b>Website:</b>
<a href="https://customersupportbottest.bankofabyssinia.com/" target="_blank" rel="noopener noreferrer">Access the Chatbot</a></p>
<p style="margin:8px 0 0 0">Happy Testing!</p>
</div>
""",
            unsafe_allow_html=True,
        )

    try:
        departments = db.list_departments()
    except RuntimeError as exc:
        if str(exc).startswith("DATABASE_URL is not configured."):
            st.error(
                "DATABASE_URL is not configured. Set it in .env for local use or Streamlit Secrets for deployment."
            )
            return
        st.error("The evaluation database is not reachable right now. Please try again shortly.")
        st.caption(f"Technical detail for the administrator: {type(exc).__name__}")
        return
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
    for k in ("stage", "tester_name", "department", "sel_section", "sel_lang", "flash",
              "in_name", "in_dept", "fb_comment", "fb_error", "autosave_error"):
        st.session_state.pop(k, None)
    for key in list(st.session_state):
        if key.startswith(("Information_Amharic_", "Information_English_", "Action_Amharic_", "Action_English_")):
            st.session_state.pop(key, None)


def _finish() -> None:
    """Save the optional overall comment, then return to the welcome page."""
    comment = (st.session_state.get("fb_comment") or "").strip()
    st.session_state.pop("fb_error", None)
    if comment:
        if looks_sensitive(comment):
            st.session_state.fb_error = (
                "Please remove account, card or phone numbers (9+ digits) from your comment - mask them, "
                "e.g. 1000XXXXXXXXX."
            )
            return
        try:
            db.save_feedback(st.session_state.tester_name, st.session_state.department, comment)
        except Exception as exc:  # noqa: BLE001
            st.session_state.fb_error = f"Could not save your comment ({type(exc).__name__}). Please try again."
            return
    _restart()
    st.session_state.finished = True


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
    if st.session_state.get("autosave_error"):
        st.error(st.session_state.autosave_error)

    total = len(available)
    finished = total - len(todo)
    st.progress(finished / total if total else 0.0, text=f"{finished} of {total} sections complete")

    if not available:
        st.warning("There are no active questions for your department. Please contact the administrator.")
    elif not todo:
        st.markdown(
            '<div class="card"><h4>🎉 Thank you!</h4>You have completed all of your evaluation sections. '
            "Informational sections are locked after submission. You can reopen Action sections to update your answers.</div>",
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
    all_done = bool(available) and not todo
    if all_done:
        st.markdown("##### 💬 Before you finish - tell us about the chatbot")
        st.text_area(
            "Your overall comment on the chatbot (optional, but we would really value it)",
            key="fb_comment",
            height=130,
            max_chars=4000,
            placeholder="What worked well? What was confusing or missing? What should we improve?",
        )
        if st.session_state.get("fb_error"):
            st.error(st.session_state.fb_error)
    st.button(
        "Finish and exit",
        on_click=_finish,
        disabled=not all_done,
        help="Enabled once all sections are complete." if not all_done else "Saves your comment and returns to the welcome page.",
    )


def _section_form(name: str, dept: str, section: str, lang: str, done: set) -> None:
    if section == "Information":
        _information_section_form(name, dept, section, lang, done)
        return

    title = f"{SECTION_LABEL[section]} · {lang}"
    qs = db.get_questions(dept, section, lang)
    if not qs:
        st.info("No questions available in this section.")
        return

    saved = db.get_answers(db.tester_key(name, dept), section, lang)
    options = STATUS_OPTIONS[section]
    st.markdown(f"##### {title} - {len(qs)} test cases")
    for i, q in enumerate(qs, 1):
        k = f"{section}_{lang}_{q['question_id']}"
        old = saved.get(q["question_id"], {})
        has_draft = "updated_at" in old
        needs_response = has_draft or (
            old.get("status") == FAILED and not (old.get("actual_response") or "").strip()
        )
        st.session_state.setdefault(f"{k}_resp", old.get("actual_response", "") or "")
        st.session_state.setdefault(f"{k}_comment", old.get("comment", "") or "")
        st.session_state.setdefault(f"{k}_status", old.get("status"))
        st.session_state.setdefault(f"{k}_save_pending", needs_response)
        if has_draft and not st.session_state.get(f"{k}_validation_error"):
            errors = validate(
                "Action",
                [{
                    "no": i,
                    "status": old.get("status"),
                    "actual_response": old.get("actual_response", "") or "",
                    "comment": old.get("comment", "") or "",
                }],
            )
            if errors:
                st.session_state[f"{k}_validation_error"] = errors[0]

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
                help="Required if Failed.",
                on_change=_action_field_changed,
                args=(name, dept, lang, q, i),
            )
            c2.text_area(
                "Comment",
                key=f"{k}_comment",
                height=110,
                max_chars=4000,
                help="Optional.",
                on_change=_action_field_changed,
                args=(name, dept, lang, q, i),
            )
            st.radio(
                "Status",
                options,
                index=None,
                horizontal=True,
                key=f"{k}_status",
                on_change=_action_status_changed,
                args=(name, dept, lang, q, i),
            )
            if st.session_state.get(f"{k}_validation_error"):
                st.error(st.session_state[f"{k}_validation_error"])
            elif "submitted_at" in saved.get(q["question_id"], {}):
                st.caption("Saved. Change the status again to save later edits.")

    if (section, lang) in done:
        st.success(f"✅ **{title}** is complete. Change a status again to save any later edits.")
    else:
        st.caption(
            "Choose a status to save each answer. Failed requires an actual response; after you enter it, "
            "that answer saves automatically."
        )


def _information_section_form(name: str, dept: str, section: str, lang: str, done: set) -> None:
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

    saved = db.get_answers(db.tester_key(name, dept), section, lang)
    options = STATUS_OPTIONS[section]
    st.markdown(f"##### {title} - {len(qs)} test cases")
    for q in qs:
        k = f"{section}_{lang}_{q['question_id']}"
        old = saved.get(q["question_id"], {})
        st.session_state.setdefault(f"{k}_resp", old.get("actual_response", "") or "")
        st.session_state.setdefault(f"{k}_comment", old.get("comment", "") or "")
        st.session_state.setdefault(f"{k}_status", old.get("status"))

    form_id = f"form_{section}_{lang}"
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
                    "Comment / what needs to be improved",
                    key=f"{k}_comment",
                    height=110,
                    max_chars=4000,
                    help="Required if Not Enough Info.",
                )
                st.radio("Status", options, index=None, horizontal=True, key=f"{k}_status")

        st.form_submit_button(
            f"Submit {title}",
            type="primary",
            on_click=_submit_information_section,
            args=(name, dept, section, lang, qs),
        )

    if error := st.session_state.get(f"{form_id}_error"):
        st.error(error)


def _submit_information_section(name: str, dept: str, section: str, lang: str, qs: list[dict]) -> None:
    form_id = f"form_{section}_{lang}"
    title = f"{SECTION_LABEL[section]} · {lang}"
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
        st.session_state[f"{form_id}_error"] = "Please fix the following before submitting:\n\n" + "\n".join(
            f"- {e}" for e in errors
        )
        return

    answers = [
        {
            "question_id": q["question_id"],
            "category": q["category"],
            "question_type": q["question_type"],
            "question_text": q["question_text"],
            "status": item["status"],
            "actual_response": item["actual_response"].strip(),
            "comment": item["comment"].strip(),
        }
        for q, item in zip(qs, items)
    ]
    try:
        db.save_submission(name, dept, section, lang, answers)
    except Exception as exc:  # noqa: BLE001
        st.session_state[f"{form_id}_error"] = (
            f"Could not save your answers ({type(exc).__name__}). Please try again."
        )
        return

    st.session_state.pop(f"{form_id}_error", None)
    st.session_state.flash = f"✅ {title} submitted. Thank you! Please continue with the remaining sections."
    st.session_state.sel_section = None
    st.session_state.sel_lang = None


def _action_status_changed(name: str, dept: str, lang: str, question: dict, number: int) -> None:
    key = f"Action_{lang}_{question['question_id']}"
    st.session_state[f"{key}_save_pending"] = True
    _try_save_action_answer(name, dept, lang, question, number, save_invalid_draft=True)


def _action_field_changed(name: str, dept: str, lang: str, question: dict, number: int) -> None:
    key = f"Action_{lang}_{question['question_id']}"
    if st.session_state.get(f"{key}_save_pending"):
        _try_save_action_answer(name, dept, lang, question, number, save_invalid_draft=False)


def _try_save_action_answer(
    name: str,
    dept: str,
    lang: str,
    question: dict,
    number: int,
    save_invalid_draft: bool,
) -> None:
    key = f"Action_{lang}_{question['question_id']}"
    answer = {
        "question_id": question["question_id"],
        "category": question["category"],
        "question_type": question["question_type"],
        "question_text": question["question_text"],
        "status": st.session_state.get(f"{key}_status"),
        "actual_response": st.session_state.get(f"{key}_resp", "") or "",
        "comment": st.session_state.get(f"{key}_comment", "") or "",
    }
    errors = validate(
        "Action",
        [{
            "no": number,
            "status": answer["status"],
            "actual_response": answer["actual_response"],
            "comment": answer["comment"],
        }],
    )
    validation_key = f"{key}_validation_error"
    if errors:
        st.session_state[validation_key] = errors[0]
        if not save_invalid_draft:
            return
        if looks_sensitive(answer["actual_response"]) or looks_sensitive(answer["comment"]):
            return
        try:
            db.save_answer_draft(name, dept, "Action", lang, answer)
        except Exception as exc:  # noqa: BLE001
            st.session_state.autosave_error = (
                f"Could not save the selected status ({type(exc).__name__}). Please try again."
            )
        else:
            st.session_state.pop("autosave_error", None)
        return

    key_id = db.tester_key(name, dept)
    try:
        was_complete = ("Action", lang) in db.submitted_sections(key_id)
        db.save_action_answer(
            name,
            dept,
            lang,
            {
                **answer,
                "actual_response": answer["actual_response"].strip(),
                "comment": answer["comment"].strip(),
            },
        )
    except Exception as exc:  # noqa: BLE001
        st.session_state.autosave_error = f"Could not save this answer ({type(exc).__name__}). Please try again."
        return

    st.session_state.pop("autosave_error", None)
    st.session_state.pop(validation_key, None)
    st.session_state[f"{key}_save_pending"] = False
    try:
        completed = ("Action", lang) in db.submitted_sections(key_id)
    except Exception as exc:  # noqa: BLE001
        st.session_state.autosave_error = (
            f"This answer was saved, but section progress could not be refreshed ({type(exc).__name__})."
        )
        return
    if completed and not was_complete:
        try:
            _advance_action_section(dept, lang, db.submitted_sections(key_id))
        except Exception as exc:  # noqa: BLE001
            st.session_state.autosave_error = (
                f"This answer was saved, but the next section could not be opened ({type(exc).__name__})."
            )


def _advance_action_section(dept: str, completed_lang: str, done: set[tuple[str, str]]) -> None:
    next_lang = next(
        (
            lang
            for section, lang in db.available_sections(dept)
            if section == "Action" and (section, lang) not in done
        ),
        None,
    )
    completed_title = f"{SECTION_LABEL['Action']} · {completed_lang}"
    if next_lang:
        st.session_state.flash = f"✅ Finished {completed_title}. Opening {LANG_LABEL[next_lang]} next."
        st.session_state.sel_section = "Action"
        st.session_state.sel_lang = next_lang
    else:
        st.session_state.flash = (
            f"✅ Finished {completed_title}. All Action sections are complete; select another section to continue."
        )
        st.session_state.sel_section = None
        st.session_state.sel_lang = None
