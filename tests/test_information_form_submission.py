import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

import db
import user_pages


QUESTION = {
    "question_id": "Q1",
    "category": "General",
    "question_type": "Text",
    "question_text": "Ask something",
}
SAVED_SUBMISSIONS = []


def _information_form_app():
    import user_pages

    user_pages._information_section_form("Tester", "Dept", "Information", "English", set())


class InformationFormSubmissionTest(unittest.TestCase):
    def setUp(self):
        SAVED_SUBMISSIONS.clear()
        self.patches = [
            patch.object(db, "get_questions", return_value=[QUESTION]),
            patch.object(db, "get_answers", return_value={}),
            patch.object(db, "tester_key", return_value="tester"),
            patch.object(db, "save_submission", side_effect=lambda *args: SAVED_SUBMISSIONS.append(args)),
        ]
        for db_patch in self.patches:
            db_patch.start()

    def tearDown(self):
        for db_patch in reversed(self.patches):
            db_patch.stop()

    def test_corrected_answers_submit_on_first_click(self):
        app = AppTest.from_function(_information_form_app).run()
        app.form_submit_button[0].click().run()
        self.assertTrue(any("choose a status" in error.value for error in app.error))

        app.radio(key="Information_English_Q1_status").set_value("Failed")
        app.text_area(key="Information_English_Q1_resp").set_value("A response")
        app.form_submit_button[0].click().run()

        self.assertEqual(len(SAVED_SUBMISSIONS), 1)
        self.assertFalse(app.error)


if __name__ == "__main__":
    unittest.main()
