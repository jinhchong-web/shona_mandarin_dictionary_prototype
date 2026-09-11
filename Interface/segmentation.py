"""Query-time Shona segmentation for the prototype.

This module does not reimplement anything: it imports `shona_segmenters.py`,
the exact module the evaluation notebooks scored, so the segmentation the user
sees in the interface is the segmentation that was measured.

The lexicon is built from `shona_entry` rather than from the CSV used during
evaluation. The FST accepts an analysis only when the remainder is a known
lemma, so sourcing the lexicon from the same table the retrieval step reads
makes "the segmenter found a lemma" and "there is a row to retrieve" the same
statement. `shona_segmenters.build_lexicon` also wants a POS column, which the
table does not have — POS is only ever used there to choose between the rule
labels `ku-INF` and `ku-INF?`, never to accept or reject a lemma, so an empty
POS set costs nothing.
"""

import sys
from pathlib import Path

import streamlit as st

APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from shona_segmenters import (  # noqa: E402 — path must be set first
    FSTSegmenter,
    HybridSegmenter,
    StrictHybridSegmenter,
    normalise,
)

from db import SHONA_TABLE, fetch  # noqa: E402

FLATCAT_MODEL_PATH = APP_DIR / "flatcat_model.tar.gz"

FST_ONLY = "FST-only"
HYBRID_STRICT = "Hybrid-strict"
HYBRID_BACKOFF = "Hybrid-backoff"

METHOD_NOTES = {
    FST_ONLY: "Authored morphotactic rules only. No unsupervised model involved.",
    HYBRID_STRICT: "Weighted towards FlatCat: the unsupervised model proposes the "
                   "boundary and the rules only filter it. Nothing is segmented "
                   "when FlatCat proposes no boundary.",
    HYBRID_BACKOFF: "Weighted towards the FST rules: FlatCat goes first, and the "
                    "rules take over whenever FlatCat proposes no usable boundary.",
}


@st.cache_resource(show_spinner="Loading the Shona lexicon…")
def load_lexicon():
    """Map normalised headword -> POS set (empty; see the module docstring)."""
    rows = fetch(f"SELECT DISTINCT headword FROM {SHONA_TABLE} WHERE headword IS NOT NULL")
    return {normalise(r["headword"]): set() for r in rows}


@st.cache_resource(show_spinner="Loading the FlatCat model…")
def load_flatcat_model():
    """Load the trained FlatCat model, or return (None, reason) if unavailable."""
    if not FLATCAT_MODEL_PATH.exists():
        return None, f"{FLATCAT_MODEL_PATH.name} not found next to the app."
    try:
        import flatcat

        return flatcat.FlatcatIO().read_tarball_model_file(str(FLATCAT_MODEL_PATH)), None
    except Exception as exc:  # noqa: BLE001 — reported in the UI
        return None, f"{type(exc).__name__}: {exc}"


@st.cache_resource(show_spinner=False)
def load_segmenters():
    """Return (segmenters_by_name, warning_or_None)."""
    lexicon = load_lexicon()
    fst = FSTSegmenter(lexicon)
    segmenters = {FST_ONLY: fst}

    model, problem = load_flatcat_model()
    if model is None:
        return segmenters, (
            f"FlatCat model unavailable, so only {FST_ONLY} is offered. {problem}"
        )

    segmenters[HYBRID_STRICT] = StrictHybridSegmenter(lexicon, model)
    segmenters[HYBRID_BACKOFF] = HybridSegmenter(lexicon, model, fst)
    return segmenters, None


def lemma_candidates(surface, segmenter):
    """Ordered, de-duplicated lemma candidates for a surface form."""
    seen, ordered = set(), []
    for lemma in segmenter.candidates(surface):
        if lemma not in seen:
            seen.add(lemma)
            ordered.append(lemma)
    return ordered
