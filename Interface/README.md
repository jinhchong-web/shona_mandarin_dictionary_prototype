# Shona–Mandarin dictionary prototype

Localhost interface over the `mandarin_shona_database` Postgres database.

## Setup

Copy two files into this folder before the first run:

- `shona_segmenters.py` — written by cell 12 of `shona_segmentation_methods.ipynb`
- `flatcat_model.tar.gz` — from `E:/Data/models/`

Then:

```
pip install -r requirements.txt
copy .env.example .env        # then edit PGPASSWORD
streamlit run app.py
```

`shona_segmenters.py` is a **copy**. Regenerating it from the notebook means
re-copying it here, or the interface and the evaluation drift apart.

## How a query runs

**Mandarin → Shona.** Exact match on `simplified` or `traditional` → picker if
several rows match → that row's stored vector → cosine search against
`shona_entry` → top-k.

**Shona → Mandarin.** The raw input is tried against `lower(headword)` first, so
a directly typed lemma resolves to itself. Only on a miss does the segmentation
layer run, and its candidate lemmas are looked up in order → picker if several
rows match → stored vector → cosine search against `mandarin_entry_v2` → top-k.

Raw-first matters because `shona_segmenters._Base.prefer_decomposition` ranks
decompositions above identity. That ranking is right when scoring inflected
forms and wrong for lookup: a word that is itself a headword should return its
own entry.

## Design decisions worth recording

- **Nothing is embedded at query time.** Both directions enter the index by
  exact word match and reuse a stored vector, so every vector compared is one
  the evaluation already measured. BGE-M3 is not a runtime dependency.
- **The segmentation layer is imported, not reimplemented.** `segmentation.py`
  wraps `shona_segmenters.py` directly, which is what makes "the same layer runs
  at query time as at index time" a checkable claim rather than an assertion.
- **The lexicon is built from the database**, not from `shona_entry.csv`. The
  FST accepts an analysis only when the remainder is a known lemma, so sourcing
  the lexicon from the table the retrieval step reads means a found lemma always
  has a row behind it. `build_lexicon`'s POS argument is unused here — POS only
  selects between the rule labels `ku-INF` and `ku-INF?` and never affects
  acceptance.
- **Rows are identified by `ctid`.** Neither table declares a primary key and
  `(simplified, pinyin)` is not enforced unique, so ctid is the only identifier
  that names exactly one row. Read-only session, so it is stable.
- **No ANN index.** At ~34k Mandarin rows and ~500 Shona rows an exact
  sequential scan is fast and avoids having to report recall/probe settings.
- **Cosine similarity is shown per result** as `1 - (a <=> b)`.

## Known limitations

- **Vocabulary size (OOV).** Lookup is exact-match, so a word outside the
  indexed vocabulary returns nothing in either direction.
- **Shona retrieval is lemma-level.** Inflected forms are resolved to a lemma
  first; sense-level and morpheme-level retrieval are out of scope.
- Dialectal variants (*zhou* → *nzou*) are lexical lookup, not segmentation, and
  are not handled by any of the three methods.
