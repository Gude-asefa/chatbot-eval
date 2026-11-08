# Chatbot Evaluation App - From Scratch to Deployment

> Draft prepared with AI assistance. Have IT Security / Compliance review the hosting choice (Streamlit Community Cloud + Neon are third-party cloud services) before sharing the link widely.

## What you get

| Piece | File |
|---|---|
| Entry point + routing | `app.py` |
| Tester pages (welcome, evaluation, submit-once logic) | `user_pages.py`, `validation.py` |
| Admin console (login, charts, filters, Excel export, Excel→DB pipeline) | `admin_page.py` |
| Database (2 tables: `questions`, `evaluations`) | `db.py` |
| Excel → `questions` pipeline | `pipeline/ingest.py` |
| Excel goes here | `data/` |
| Theme, hidden toolbar | `.streamlit/config.toml`, `ui.py` |
| Secrets template | `.env.example`, `.streamlit/secrets.toml.example` |

**URLs after deployment**
- Testers: `https://<your-app>.streamlit.app/`
- Admin: `https://<your-app>.streamlit.app/admin` (not linked anywhere; username/password required)

---

## Step 1 - Neon database (5 min)

1. Go to https://neon.tech → sign up → **Create project** (name: `chatbot-eval`, pick the region nearest to your users).
2. On the project dashboard click **Connect**. Turn **Connection pooling ON** and copy the connection string. It looks like:
   `postgresql://USER:PASSWORD@ep-xxxx-pooler.eu-central-1.aws.neon.tech/neondb?sslmode=require`
   Use the **pooled** (`-pooler`) string - 100+ testers can connect at the same time.
3. Keep it private. Do **not** paste it into GitHub or chat.
4. You do **not** create tables by hand - the app creates `questions` and `evaluations` on first start.

## Step 2 - Run locally and load the questions (10 min)

```bash
# in the project folder
python -m venv .venv
.venv\Scripts\activate            # Windows
pip install -r requirements.txt
```

Create `.env` (copy `.env.example`, same folder as `app.py`) and fill in:
- `DATABASE_URL` - the Neon string from Step 1
- `ADMIN_USERNAME` - e.g. `admin`
- `ADMIN_PASSWORD_HASH` - run `python tools/hash_password.py`, type your password (hidden), paste the printed line into `.env`

Neon tables: the app creates them if missing. If you created them by hand, they must match `schema.sql`.

Put the Excel file in `data/` (already there) and run the pipeline:

```bash
python -m pipeline.ingest
```

Expected: `Done: {'inserted': 504, 'updated': 0, 'deactivated': 0, 'total': 504}`

Start the app:

```bash
streamlit run app.py
```

- Testers: http://localhost:8501
- Admin: http://localhost:8501/admin

Do one full test submission, then check the admin page. (Before launch, delete your test rows in Neon: **SQL Editor** → `DELETE FROM evaluations;`.)

> Changing the questions later: edit the Excel in `data/` and re-run `python -m pipeline.ingest` from your PC (it writes straight to Neon using your `.env`). The admin *Question bank & data* tab only displays the questions. Matching is by **Question ID**; questions missing from the file are deactivated (existing answers are kept).

## Step 3 - GitHub (5 min)

1. https://github.com → **New repository** → name `chatbot-evaluation` → **Private** (recommended: hides your code and username link) → *do not* add README/.gitignore (we have one).
2. In the project folder:

```bash
git init
git add .
git status          # CHECK: `.env` and data/*.xlsx must NOT be listed
git commit -m "Chatbot evaluation app"
git branch -M main
git remote add origin https://github.com/<your-user>/chatbot-evaluation.git
git push -u origin main
```

## Step 4 - Streamlit Community Cloud (5 min)

1. https://share.streamlit.io → sign in with GitHub → authorize access to your private repo.
2. **Create app** → *Deploy a public app from GitHub* → choose repo `chatbot-evaluation`, branch `main`, main file `app.py`.
3. **Advanced settings** → Python 3.12 (or 3.11/3.13) → **Secrets** → paste the three values in TOML form (see `.streamlit/secrets.toml.example`). **Cloud does not read `.env`.**
4. Click **Deploy**. First build takes 2-3 minutes.
5. Under app **Settings → Sharing** set the app to **public** (anyone with the link), so testers need no Streamlit account.
6. Custom URL: Settings → *General* → change the subdomain, e.g. `boa-chatbot-eval.streamlit.app`.

## Step 5 - Hiding GitHub / developer links

The app already hides the menu, Deploy button, toolbar and footer (`config.toml` + CSS), and testers never see "Manage app".
Additionally:
- Keep the repo **Private** so any profile link leads nowhere.
- Share the link with `?embed=true` appended (e.g. `https://boa-chatbot-eval.streamlit.app/?embed=true`) - this removes extra Streamlit chrome.
- Streamlit Community Cloud may still show a small platform badge at the bottom-right that the app code cannot remove. **Open the live link in a private window after deploying and verify.** If it must be fully clean, put the app inside an iframe on a bank-hosted page or self-host (e.g. on a bank VM/container).

## Step 6 - Share and monitor

- Send testers the tester link. Tell them: name + department, 4 submissions (Informational/Action × Amharic/English), submit once per section.
- Each tester is identified by **name + department** (case/space-insensitive). Two people with the same name in one department would collide - ask them to use full names. A tester who refreshes or returns later is recognized and sees which sections are already done.
- Admin → Comments shows the overall comments testers leave before *Finish and exit*. Admin → Overview (pie/bar/sunburst charts, participation per department, problem questions) → Results (filter by language, department, section, category, status → Excel export).
- Streamlit Community Cloud apps sleep after inactivity; the first visitor after a quiet period waits ~30 s for wake-up. Open the link a few minutes before announcing it.
- Neon free tier auto-suspends compute; the app reconnects automatically (first query may take ~1 s).

## Troubleshooting

- **`DLL load failed ... Application Control policy has blocked this file`** when running locally: the bank PC's security policy blocks pandas/pyarrow native files. The tester pages and the `pipeline.ingest` command are pandas-free and should run; only the **admin console** needs pandas. The admin tables are rendered as HTML, so `pyarrow` is not needed. If pandas is blocked too, ask IT to allow-list the Python environment, or test the admin page after deploying (Step 3-4).
- **Connection string options**: `sslmode` / `channel_binding` in the Neon URL are handled automatically (the app uses the pure-Python `pg8000` driver with TLS).
- **Python 3.14 locally**: if a package fails to install, use Python 3.12 (`py -3.12 -m venv .venv`).

## Known behaviors / limits

- Answers are saved only on **Submit** - if a tester closes the browser mid-section, that section's draft is lost (previous submitted sections stay).
- Submissions with 9+ digit sequences in response/comment are rejected (guards against account/card/phone numbers). Test cases for Check Balance/Transaction flows may expose such data in responses - testers must mask them.
- No admin "reset a tester" function exists; to let someone redo a section, delete their rows in Neon SQL Editor: `DELETE FROM evaluations WHERE tester_key = 'credit|abebe kebede' AND section='Action' AND language='English';`
- Hosting customer-facing-adjacent data (even tester names) outside the bank's infrastructure may need Compliance/IT Security approval - confirm before launch.
