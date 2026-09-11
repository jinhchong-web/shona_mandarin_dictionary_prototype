"""Shona <-> Mandarin dictionary prototype (7005SCN).

Run with:  streamlit run app.py
"""

from html import escape

import streamlit as st

from db import MANDARIN_TABLE, SHONA_TABLE, check_connection
from retrieval import (
    MANDARIN,
    SHONA,
    detect_language,
    has_vector,
    lookup_mandarin,
    resolve_shona,
    search_from_mandarin,
    search_from_shona,
)
from segmentation import METHOD_NOTES, load_segmenters

st.set_page_config(page_title="Shona–Mandarin dictionary", page_icon="📖", layout="centered")

st.markdown(
    """
    <style>
      .entry-card {
        border: 1px solid rgba(128,128,128,.25);
        border-radius: 10px;
        padding: .9rem 1.1rem;
        margin-bottom: .6rem;
      }
      .entry-head { font-size: 1.35rem; font-weight: 600; }
      .entry-sub  { opacity: .7; font-size: .9rem; }
      .entry-sim  { float: right; font-variant-numeric: tabular-nums; opacity: .75;
                    font-size: .85rem; }
      .entry-body { margin-top: .45rem; line-height: 1.5; }
      .entry-label { opacity: .55; font-size: .78rem; text-transform: uppercase;
                     letter-spacing: .04em; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Shona–Mandarin dictionary")
st.caption(
    "Type a word in either language. Mandarin input is matched against the "
    "simplified or traditional form; Shona input is reduced to a lemma by the "
    "segmentation layer before lookup."
)

ok, status = check_connection()
if not ok:
    st.error(f"Cannot read the database. {status}")
    st.stop()

segmenters, segmenter_warning = load_segmenters()
if segmenter_warning:
    st.warning(segmenter_warning)

with st.sidebar:
    st.subheader("Retrieval settings")
    embedding_key = st.selectbox(
        "Embedding",
        options=["3a", "3b"],
        format_func=lambda k: {
            "3a": "3a — English gloss",
            "3b": "3b — POS + English gloss",
        }[k],
    )
    method_name = st.selectbox("Segmentation method (Shona Word)", options=list(segmenters))
    st.caption(METHOD_NOTES[method_name])
    top_k = st.slider("Results", min_value=1, max_value=10, value=5)
    st.divider()
    st.caption(f"Connected to {status}")

segmenter = segmenters[method_name]


def esc(value):
    """Dictionary text can contain angle brackets; the cards are raw HTML."""
    return escape(str(value)) if value is not None else ""


def similarity_badge(row):
    value = row.get("similarity")
    return f"<span class='entry-sim'>{value:.4f}</span>" if value is not None else ""


def render_mandarin(row):
    head = esc(row["simplified"])
    if row.get("traditional") and row["traditional"] != row["simplified"]:
        head += f" · {esc(row['traditional'])}"
    parts = [
        f"<div class='entry-card'>{similarity_badge(row)}",
        f"<div class='entry-head'>{head}</div>",
    ]
    if row.get("pinyin"):
        parts.append(f"<div class='entry-sub'>{esc(row['pinyin'])}</div>")
    parts.append(f"<div class='entry-body'>{esc(row['english_gloss'])}</div>")
    if row.get("shiyi"):
        parts.append(f"<div class='entry-body'>{esc(row['shiyi'])}</div>")
    parts.append("</div>")
    st.markdown("".join(parts), unsafe_allow_html=True)
    if row.get("audio_url"):
        try:
            st.audio(row["audio_url"])
        except Exception:  # noqa: BLE001 — audio is optional, never fatal
            st.caption(f"Audio: {row['audio_url']}")


def render_shona(row):
    parts = [
        f"<div class='entry-card'>{similarity_badge(row)}",
        f"<div class='entry-head'>{esc(row['headword'])}</div>",
    ]
    if row.get("shona_status"):
        parts.append(f"<div class='entry-sub'>{esc(row['shona_status'])}</div>")
    parts.append(f"<div class='entry-body'>{esc(row['english_gloss'])}</div>")
    if row.get("shona_definition"):
        parts.append(f"<div class='entry-body'>{esc(row['shona_definition'])}</div>")
    parts.append("</div>")
    st.markdown("".join(parts), unsafe_allow_html=True)


def choose_row(rows, label, describe):
    """Show a picker when more than one row matches; otherwise pass the row through."""
    if len(rows) == 1:
        return rows[0]
    st.info(f"{len(rows)} entries match. Choose one to search from.")
    index = st.radio(
        label,
        options=range(len(rows)),
        format_func=lambda i: describe(rows[i]),
        label_visibility="collapsed",
    )
    return rows[index]


query = st.text_input("Word", placeholder="e.g. 山  or  hanzi", label_visibility="collapsed")

if not query.strip():
    st.stop()

language = detect_language(query)

if language == MANDARIN:
    rows = lookup_mandarin(query)
    if not rows:
        st.warning(
            f"“{query.strip()}” is not in the Mandarin collection. Lookup is by exact "
            "headword, so words outside the indexed vocabulary return nothing."
        )
        st.stop()

    source = choose_row(
        rows,
        "Matching Mandarin entries",
        lambda r: f"{r['simplified']} · {r['pinyin'] or '—'} — {r['english_gloss']}",
    )
    st.markdown("<div class='entry-label'>Entry</div>", unsafe_allow_html=True)
    render_mandarin(source)

    if not has_vector(MANDARIN_TABLE, source["row_id"], embedding_key):
        st.warning(f"This entry has no {embedding_key} vector, so it cannot be searched.")
        st.stop()

    st.markdown("<div class='entry-label'>Shona candidates</div>", unsafe_allow_html=True)
    results = search_from_mandarin(source["row_id"], embedding_key, top_k)
    if not results:
        st.warning("No Shona entries carry this embedding.")
    for row in results:
        render_shona(row)

else:
    rows, resolved_by = resolve_shona(query, segmenter)
    if not rows:
        st.warning(
            f"“{query.strip()}” could not be resolved to a headword in the Shona "
            "collection — either the segmentation layer found no analysis, or the "
            "lemma is outside the indexed vocabulary."
        )
        st.stop()

    source = choose_row(
        rows,
        "Matching Shona entries",
        lambda r: f"{r['headword']} — {r['english_gloss']}",
    )

    if resolved_by == "segmented" and source.get("resolved_from"):
        st.caption(f"{query.strip()} → {source['resolved_from']}")

    st.markdown("<div class='entry-label'>Entry</div>", unsafe_allow_html=True)
    render_shona(source)

    if not has_vector(SHONA_TABLE, source["row_id"], embedding_key):
        st.warning(f"This entry has no {embedding_key} vector, so it cannot be searched.")
        st.stop()

    st.markdown("<div class='entry-label'>Mandarin candidates</div>", unsafe_allow_html=True)
    results = search_from_shona(source["row_id"], embedding_key, top_k)
    if not results:
        st.warning("No Mandarin entries carry this embedding.")
    for row in results:
        render_mandarin(row)
