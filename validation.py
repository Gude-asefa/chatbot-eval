"""Answer validation rules for one section submission."""
import re

PASSED, FAILED, NEI = "Passed", "Failed", "Not Enough Info"
STATUS_OPTIONS = {
    "Information": [PASSED, FAILED, NEI],
    "Action": [PASSED, FAILED],
}

# 9+ digits (allowing spaces/dashes between them) looks like an account, card or phone number.
_LONG_DIGITS = re.compile(r"(?:\d[\s\-]?){9,}")


def looks_sensitive(text: str) -> bool:
    return bool(_LONG_DIGITS.search(text or ""))


def validate(section: str, items: list[dict]) -> list[str]:
    """items: [{no, status, actual_response, comment}] -> list of human-readable errors."""
    errors: list[str] = []
    allowed = STATUS_OPTIONS[section]
    for it in items:
        no, status = it["no"], it["status"]
        resp, comment = it["actual_response"].strip(), it["comment"].strip()
        if status not in allowed:
            errors.append(f"Question {no}: choose a status.")
            continue
        if status == FAILED and not resp:
            errors.append(f"Question {no}: the chatbot's actual response is required when the status is Failed.")
        if status == NEI:
            if not resp:
                errors.append(f"Question {no}: the chatbot's actual response is required for 'Not Enough Info'.")
            if not comment:
                errors.append(f"Question {no}: a comment on what needs to be improved is required for 'Not Enough Info'.")
        if looks_sensitive(resp) or looks_sensitive(comment):
            errors.append(
                f"Question {no}: remove account, card or phone numbers (9+ digits) - "
                "mask them, e.g. 1000XXXXXXXXX."
            )
    return errors
