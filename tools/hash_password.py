"""Generate the ADMIN_PASSWORD_HASH value.

Run from the project root:
    python tools/hash_password.py
(the password is typed hidden and never stored; only the hash is printed)
"""
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from security import hash_password  # noqa: E402

pw = getpass.getpass("Admin password: ")
if len(pw) < 12:
    sys.exit("Use at least 12 characters.")
if pw != getpass.getpass("Repeat password: "):
    sys.exit("Passwords do not match.")

h = hash_password(pw)
print("\nPut this line in your .env  (keep the single quotes):\n")
print(f"ADMIN_PASSWORD_HASH='{h}'")
print("\nFor Streamlit Cloud Secrets use:\n")
print(f'ADMIN_PASSWORD_HASH = "{h}"')
