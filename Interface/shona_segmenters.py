#   FSTSegmenter      - authored morphotactic rules + lexicon guard
#   FlatCatSegmenter  - unsupervised HMM segmentation (Morfessor FlatCat)
#   HybridSegmenter   - FlatCat boundary validated and completed by the FST
#
# Rule sources: shona_affixes.csv (Wiktionary) and published Shona grammar
# (Fortune; Doke). No rule is derived from the gold pairs.
import unicodedata
from collections import defaultdict, namedtuple

Analysis = namedtuple("Analysis", "lemma rule morphs")


def normalise(s):
    "Tone-insensitive, case-insensitive lookup key."
    s = str(s).replace("\u2019", "'").replace("\u02bc", "'")
    return unicodedata.normalize(
        "NFC", "".join(c for c in unicodedata.normalize("NFD", s)
                       if not unicodedata.combining(c))
    ).lower().strip()


# Shona noun class pairings: (plural prefix, candidate singular prefixes, label)
CLASS_PAIRS = [
    ("va",  ["mu", ""],                  "1/2, 1a/2a"),
    ("mi",  ["mu"],                      "3/4"),
    ("ma",  ["", "ri", "ru", "u", "bu"], "5/6, 11/6, 14/6"),
    ("zvi", ["chi"],                     "7/8"),
    ("zv",  ["ch"],                      "7/8"),
    ("tu",  ["ka"],                      "12/13"),
]

# class 5/6 alternation: ma- devoices a voiced stem-initial consonant
DEVOICE = {"k": "g", "p": "b", "t": "d", "ts": "dz",
           "sv": "zv", "f": "v", "s": "z", "ch": "j"}

INFINITIVE = "ku"
STEM_CATEGORIES = {"STM", "stem"}


class _Base:
    # Decompositions rank above identity: an inflected form often has its own
    # lexicon entry, and returning that would mean never segmenting anything
    # already known. Identity still wins when no rule applies.
    prefer_decomposition = True

    def __init__(self, lexicon):
        self.lex = lexicon

    def _rank(self, analyses):
        if not self.prefer_decomposition:
            return analyses
        return ([a for a in analyses if a.rule != "identity"]
                + [a for a in analyses if a.rule == "identity"])

    def lemma(self, surface):
        "Single best lemma - what the query-time pipeline returns."
        a = self._rank(self.analyse(surface))
        return a[0].lemma if a else None

    def candidates(self, surface):
        "All accepted lemmas, best first."
        return [a.lemma for a in self._rank(self.analyse(surface))]


def _stem_variants(stem):
    out = {stem}
    for k, v in DEVOICE.items():
        if stem.startswith(k):
            out.add(v + stem[len(k):])
    return out


class FSTSegmenter(_Base):
    "Authored rules. Tries every affix; the lexicon decides."

    name = "FST-only"

    def analyse(self, surface):
        s = normalise(surface)
        out, seen = [], set()

        def add(lemma, rule, morphs):
            if lemma in self.lex and (lemma, rule) not in seen:
                seen.add((lemma, rule))
                out.append(Analysis(lemma, rule, morphs))

        if s in self.lex:
            add(s, "identity", [s])

        if s.startswith(INFINITIVE):
            root = s[len(INFINITIVE):]
            rule = "ku-INF" if "VERB" in self.lex.get(root, ()) else "ku-INF?"
            add(root, rule, [INFINITIVE, root])

        for pl, sgs, label in CLASS_PAIRS:
            if not s.startswith(pl):
                continue
            stem = s[len(pl):]
            for sg in sgs:
                for var in _stem_variants(stem):
                    cand = sg + var
                    if cand != s:
                        add(cand, f"{pl}->{sg or 'Z'} [{label}]",
                            [pl, sg, var] if sg else [pl, var])
        return out


def _morphs_of(model, s):
    "Call viterbi_analyze defensively across FlatCat versions."
    res = model.viterbi_analyze(s)
    an = res[0] if isinstance(res, tuple) else res
    return [(m.morph, str(m.category)) for m in an]


class FlatCatSegmenter(_Base):
    "Unsupervised only. Knows where boundaries are, not what they mean."

    name = "FlatCat-only"

    def __init__(self, lexicon, model):
        super().__init__(lexicon)
        self.model = model

    def analyse(self, surface):
        s = normalise(surface)
        try:
            morphs = _morphs_of(self.model, s)
        except Exception:
            return []
        pieces = [m for m, _ in morphs]
        stems = [m for m, c in morphs if c in STEM_CATEGORIES] or pieces[-1:]
        cand = max(stems, key=len)
        rule = "flatcat/" + "+".join(f"{m}:{c}" for m, c in morphs)
        return [Analysis(cand, rule, pieces)]


class HybridSegmenter(_Base):
    "Backoff hybrid: FlatCat first, FST when FlatCat proposes no usable boundary."

    name = "Hybrid-backoff"

    def __init__(self, lexicon, model, fst=None):
        super().__init__(lexicon)
        self.model = model
        self.fst = fst or FSTSegmenter(lexicon)

    def analyse(self, surface):
        s = normalise(surface)
        out, seen = [], set()
        if s in self.lex:
            out.append(Analysis(s, "identity", [s]))
            seen.add(s)
        try:
            morphs = _morphs_of(self.model, s)
        except Exception:
            morphs = []
        pieces = [m for m, _ in morphs]
        if len(pieces) >= 2:
            for cut in range(1, len(pieces)):
                prefix = "".join(pieces[:cut])
                rest = "".join(pieces[cut:])
                if prefix == INFINITIVE and rest in self.lex and rest not in seen:
                    seen.add(rest)
                    out.append(Analysis(rest, "hybrid ku-INF", [prefix, rest]))
                for pl, sgs, label in CLASS_PAIRS:
                    if prefix != pl:
                        continue
                    for sg in sgs:
                        for var in _stem_variants(rest):
                            cand = sg + var
                            if cand in self.lex and cand not in seen:
                                seen.add(cand)
                                out.append(Analysis(
                                    cand, f"hybrid {pl}->{sg or 'Z'} [{label}]",
                                    [prefix, cand]))
        # FlatCat contributed nothing beyond identity -> back off to the rules
        if not [a for a in out if a.rule != "identity"]:
            for a in self.fst.analyse(s):
                if a.lemma not in seen:
                    seen.add(a.lemma)
                    out.append(a)
        return out


class StrictHybridSegmenter(_Base):
    "Faithful to the project plan: FlatCat generates candidates, the FST filters."
    # No FST fallback. If FlatCat proposes no boundary, nothing is segmented.
    # This is the architecture the title describes, and it is the condition
    # that actually measures the unsupervised layer's contribution.

    name = "Hybrid-strict"

    def __init__(self, lexicon, model):
        super().__init__(lexicon)
        self.model = model

    def analyse(self, surface):
        s = normalise(surface)
        try:
            morphs = _morphs_of(self.model, s)
        except Exception:
            return []
        pieces = [m for m, _ in morphs]
        out, seen = [], set()
        if len(pieces) >= 2:
            for cut in range(1, len(pieces)):
                prefix = "".join(pieces[:cut])
                rest = "".join(pieces[cut:])
                if prefix == INFINITIVE and rest in self.lex and rest not in seen:
                    seen.add(rest)
                    out.append(Analysis(rest, "ku-INF", [prefix, rest]))
                for pl, sgs, label in CLASS_PAIRS:
                    if prefix != pl:
                        continue
                    for sg in sgs:
                        for var in _stem_variants(rest):
                            cand = sg + var
                            if cand in self.lex and cand not in seen:
                                seen.add(cand)
                                out.append(Analysis(
                                    cand, f"{pl}->{sg or 'Z'} [{label}]",
                                    [prefix, cand]))
        if s in self.lex and s not in seen:
            out.append(Analysis(s, "identity", [s]))
        return out


def build_lexicon(entry_df, headword_col="headword", pos_col="pos_unified"):
    lex = defaultdict(set)
    for h, p in zip(entry_df[headword_col], entry_df[pos_col]):
        lex[normalise(h)].add(p)
    return lex