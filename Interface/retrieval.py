"""Lookup and cross-lingual retrieval.

Nothing is embedded at query time. A query enters the vector index by exact word
match, and the matched row's stored vector is what gets compared against the
other language's collection — so every vector in play is one the evaluation
already measured.

Rows are identified by `ctid::text`. Neither table declares a primary key, and
`(simplified, pinyin)` is not enforced as unique, so ctid is the only identifier
guaranteed to name exactly one row. It is stable for the life of a read-only
session, which is all the picker needs.
"""

import re

import streamlit as st
from psycopg import sql

from db import (
    EMBEDDING_COLUMNS,
    MANDARIN_DISPLAY_COLUMNS,
    MANDARIN_TABLE,
    SHONA_DISPLAY_COLUMNS,
    SHONA_TABLE,
    fetch,
)
from segmentation import lemma_candidates
from shona_segmenters import normalise

CJK = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")

MANDARIN = "mandarin"
SHONA = "shona"


def detect_language(text):
    """Mandarin if the input contains any Han character, otherwise Shona."""
    return MANDARIN if CJK.search(text) else SHONA


def _select_rows(table, columns, where, params):
    query = sql.SQL("SELECT ctid::text AS row_id, {cols} FROM {table} WHERE {where}").format(
        cols=sql.SQL(", ").join(sql.Identifier(c) for c in columns),
        table=sql.Identifier(table),
        where=where,
    )
    return fetch(query, params)


@st.cache_data(show_spinner=False)
def lookup_mandarin(word):
    """Rows whose simplified or traditional form is exactly `word`."""
    word = word.strip()
    if not word:
        return []
    rows = _select_rows(
        MANDARIN_TABLE,
        MANDARIN_DISPLAY_COLUMNS,
        sql.SQL("simplified = %s OR traditional = %s"),
        (word, word),
    )
    return sorted(rows, key=lambda r: (r["simplified"] != word, r["pinyin"] or ""))


@st.cache_data(show_spinner=False)
def lookup_shona_headword(lemma):
    """Rows whose headword matches `lemma`, compared case-insensitively.

    `normalise()` lowercases and strips tone. No headword in the table carries
    tone (tone appears only on inflected forms), so `lower()` is an equivalent
    comparison on this data and keeps the query a plain index-friendly predicate.
    """
    lemma = normalise(lemma)
    if not lemma:
        return []
    return _select_rows(
        SHONA_TABLE,
        SHONA_DISPLAY_COLUMNS,
        sql.SQL("lower(headword) = %s"),
        (lemma,),
    )


def resolve_shona(surface, segmenter):
    """Resolve a Shona surface form to candidate rows.

    The raw input is tried first: if someone types a word that is itself a
    headword, that entry is the right answer. The segmenter's own ranking
    prefers decompositions over identity, which is correct when scoring
    inflected forms and wrong for dictionary lookup.

    Returns (rows, resolved_by) where resolved_by is "raw" or "segmented".
    """
    rows = [dict(r, resolved_from=None) for r in lookup_shona_headword(surface)]
    if rows:
        return rows, "raw"

    found, seen = [], set()
    for lemma in lemma_candidates(surface, segmenter):
        for row in lookup_shona_headword(lemma):
            if row["row_id"] in seen:
                continue
            seen.add(row["row_id"])
            found.append(dict(row, resolved_from=lemma))
    return found, "segmented"


def cross_lingual_search(source_table, source_row_id, target_table, target_columns,
                         embedding_key, limit=5):
    """Top-k rows from `target_table` nearest the source row's stored vector.

    The comparison runs entirely in Postgres — the 1024-dim vector is never
    round-tripped into Python. `<=>` is pgvector's cosine distance, so
    similarity is 1 minus that.
    """
    embedding_column = EMBEDDING_COLUMNS[embedding_key]
    query = sql.SQL(
        """
        WITH q AS (
            SELECT {emb} AS v
            FROM {src}
            WHERE ctid = %(row_id)s::tid
        )
        SELECT {cols}, 1 - (t.{emb} <=> q.v) AS similarity
        FROM {tgt} AS t, q
        WHERE t.{emb} IS NOT NULL
        ORDER BY t.{emb} <=> q.v
        LIMIT %(limit)s
        """
    ).format(
        emb=sql.Identifier(embedding_column),
        src=sql.Identifier(source_table),
        tgt=sql.Identifier(target_table),
        cols=sql.SQL(", ").join(sql.Identifier("t", c) for c in target_columns),
    )
    return fetch(query, {"row_id": source_row_id, "limit": limit})


def search_from_mandarin(row_id, embedding_key, limit=5):
    return cross_lingual_search(
        MANDARIN_TABLE, row_id, SHONA_TABLE, SHONA_DISPLAY_COLUMNS, embedding_key, limit
    )


def search_from_shona(row_id, embedding_key, limit=5):
    return cross_lingual_search(
        SHONA_TABLE, row_id, MANDARIN_TABLE, MANDARIN_DISPLAY_COLUMNS, embedding_key, limit
    )


def has_vector(table, row_id, embedding_key):
    """Guard against rows whose embedding column is NULL."""
    query = sql.SQL("SELECT {emb} IS NOT NULL AS ok FROM {table} WHERE ctid = %s::tid").format(
        emb=sql.Identifier(EMBEDDING_COLUMNS[embedding_key]),
        table=sql.Identifier(table),
    )
    rows = fetch(query, (row_id,))
    return bool(rows) and rows[0]["ok"]
