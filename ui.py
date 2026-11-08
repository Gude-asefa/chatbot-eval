"""Shared look & feel (Bank of Abyssinia: yellow #F1AB15, black, white)."""
import streamlit as st

BRAND_YELLOW = "#F1AB15"
BRAND_BLACK = "#111111"

# ---- Edit these two to change the wording on the welcome page ----
CHATBOT_NAME = "Customer Support Chatbot"
CHATBOT_DESCRIPTION = (
    "The Bank of Abyssinia customer support chatbot answers customer questions (<b>Informational</b>) and performs "
    "banking service flows such as checking exchange rates, finding a branch/ATM, checking loan limit, "
    "creating support case , checking case status , checking transaction, "
    "blocking a card and  checking card status  (<b>Action</b>). It is available in <b>Amharic</b> and "
    "<b>English</b>, through written text, voice and buttons."
)

CSS = f"""
<style>
/* Hide Streamlit chrome (menu, GitHub/Deploy links, footer, status widget) */
#MainMenu, footer, header[data-testid="stHeader"], [data-testid="stToolbar"],
[data-testid="stDecoration"], [data-testid="stStatusWidget"], [data-testid="stAppDeployButton"],
.stDeployButton, [class*="viewerBadge"], [class*="_profileContainer"], [data-testid="manage-app-button"]
{{ display: none !important; visibility: hidden !important; }}
.block-container {{ padding-top: 1.2rem; max-width: 980px; }}
.admin .block-container {{ max-width: 1400px; }}

.hero {{ background:{BRAND_BLACK}; border-bottom:6px solid {BRAND_YELLOW}; border-radius:12px;
        padding:26px 30px; margin-bottom:18px; }}
.hero h1 {{ color:{BRAND_YELLOW}; margin:0; font-size:1.9rem; }}
.hero p  {{ color:#fff; margin:6px 0 0 0; font-size:1rem; }}
.hero.compact {{ padding:14px 22px; }}
.hero.compact h1 {{ font-size:1.3rem; }}

.card {{ background:#fff; border:1px solid #e6e6e6; border-left:5px solid {BRAND_YELLOW};
        border-radius:8px; padding:14px 18px; margin-bottom:12px; }}
.card h4 {{ margin:0 0 6px 0; }}

.q-head {{ display:flex; gap:8px; align-items:center; flex-wrap:wrap; margin-bottom:6px; }}
.q-no   {{ background:{BRAND_BLACK}; color:{BRAND_YELLOW}; font-weight:700; border-radius:6px; padding:2px 10px; }}
.q-cat  {{ background:{BRAND_YELLOW}; color:#000; font-weight:600; border-radius:6px; padding:2px 10px; }}
.q-type {{ border:1px solid #999; color:#333; border-radius:6px; padding:1px 8px; font-size:.8rem; }}
.q-id   {{ color:#888; font-size:.75rem; margin-left:auto; }}
.q-text {{ background:#FFF6DC; border-radius:6px; padding:10px 12px; font-size:1.02rem;
          white-space:pre-wrap; margin-bottom:8px; }}

/* Tables (rendered as HTML so no pyarrow is needed) */
.boa-scroll {{ overflow:auto; border:1px solid #e6e6e6; border-radius:8px; margin-bottom:12px; }}
table.boa-table {{ border-collapse:collapse; width:100%; font-size:.85rem; }}
table.boa-table th {{ background:{BRAND_YELLOW}; color:#000; text-align:left; padding:6px 10px;
                     position:sticky; top:0; white-space:nowrap; }}
table.boa-table td {{ padding:6px 10px; border-top:1px solid #eee; vertical-align:top;
                     max-width:420px; word-wrap:break-word; }}
table.boa-table tr:nth-child(even) td {{ background:#FFFBF0; }}

/* Buttons: yellow with black text, black outline for secondary */
[data-testid^="stBaseButton-primary"], [data-testid^="stBaseButton-primary"] p
{{ color:#000 !important; font-weight:600; }}
[data-testid^="stBaseButton-secondary"] {{ border:1.5px solid {BRAND_BLACK}; }}
[data-testid^="stBaseButton-secondary"]:hover {{ border-color:{BRAND_YELLOW}; background:#FFF6DC; }}
</style>
"""


def inject_css(admin: bool = False) -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    if admin:
        st.markdown("<style>.block-container{max-width:1400px !important}</style>", unsafe_allow_html=True)


def hero(title: str, subtitle: str = "", compact: bool = False) -> None:
    cls = "hero compact" if compact else "hero"
    sub = f"<p>{subtitle}</p>" if subtitle else ""
    st.markdown(f'<div class="{cls}"><h1>{title}</h1>{sub}</div>', unsafe_allow_html=True)


def show_table(data, index: bool = False, max_rows: int = 500, height: int = 520) -> None:
    """Render a DataFrame / list of dicts as a styled HTML table (replaces st.dataframe)."""
    import html as _html

    import pandas as pd

    df = data if isinstance(data, pd.DataFrame) else pd.DataFrame(data)
    total = len(df)
    shown = df.head(max_rows)
    cells = shown.astype(object).where(shown.notna(), "").map(
        lambda v: _html.escape(str(v)).replace(chr(10), "<br>")
    )
    cells.columns = [_html.escape(str(c)) for c in cells.columns]
    if index:
        cells.index = [_html.escape(str(i)) for i in cells.index]
        cells.index.name = _html.escape(str(df.index.name or ""))
    table = cells.to_html(index=index, escape=False, border=0, classes="boa-table").replace(chr(10), "")
    st.markdown(f'<div class="boa-scroll" style="max-height:{height}px">{table}</div>', unsafe_allow_html=True)
    if total > max_rows:
        st.caption(f"Showing the first {max_rows:,} of {total:,} rows - use the Excel export for everything.")
