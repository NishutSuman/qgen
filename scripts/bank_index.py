#!/usr/bin/env python3
"""bank_index.py — fast near-duplicate search for the question banks.

Replaces the old O(new × bank) all-pairs Jaccard scan with:

  - EXACT repeats  -> O(1) fingerprint set lookup.
  - NEAR repeats   -> MinHash + LSH (locality-sensitive hashing). Each stem gets
    a 128-int MinHash signature; signatures are banded so only stems that ALREADY
    collide in a band are compared with a true Jaccard. Candidate retrieval is
    sub-linear, so checking one new question against a 1000+ bank is sub-millisecond.

MinHash signatures for bank rows are cached to a sidecar (<bank>.sigcache.json)
keyed by fingerprint, so the expensive hashing is paid once per stem ever — not on
every run. All of this is pure stdlib and runs in a script (no model tokens).

This module is imported by question_bank.py; it is not a CLI itself.
"""
import hashlib
import json
import os
import random
import re

# ---- shared text helpers (single source of truth for both banks) ----
def tokens(s):
    return set(re.findall(r"[a-z0-9]+", (s or "").lower()))


def jaccard(a, b):
    """a, b are token SETS."""
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def fingerprint(text):
    toks = sorted(tokens(text))
    return hashlib.sha1(" ".join(toks).encode("utf-8")).hexdigest()


def dedup_text(q):
    """Text a question is de-duplicated on: the shared stimulus PLUS the prompt.

    Set questions (RC passages, DI tables/graphs) carry only a short generic prompt
    in question_text ("What is the main idea of the passage?"), which would collide
    across papers even when the passage is completely different. Including the
    stimulus makes dedup reflect the real question.
    """
    s = q.get("stimulus") or {}
    md = (s.get("markdown") or "").strip()
    qt = (q.get("question_text") or "").strip()
    return (md + "\n" + qt).strip() if md else qt


def record_text(r):
    """Text stored for a bank record (new records carry dedup_text)."""
    return r.get("dedup_text") or r.get("question_text", "")


# ---- MinHash / LSH ----
NUM_PERM = 128
BANDS = 32
ROWS = NUM_PERM // BANDS          # 4 rows per band
MERSENNE = (1 << 61) - 1
_MAXHASH = (1 << 64) - 1

# Fixed permutation coefficients (seeded -> stable across runs & machines).
_rng = random.Random(0xC0FFEE)
_A = [_rng.randrange(1, MERSENNE) for _ in range(NUM_PERM)]
_B = [_rng.randrange(0, MERSENNE) for _ in range(NUM_PERM)]


def _tok_hash(tok):
    return int.from_bytes(hashlib.blake2b(tok.encode("utf-8"), digest_size=8).digest(), "big")


def minhash(token_set):
    """Return a 128-int MinHash signature for a set of tokens."""
    if not token_set:
        return [_MAXHASH] * NUM_PERM
    hs = [_tok_hash(t) for t in token_set]
    sig = []
    for a, b in zip(_A, _B):
        sig.append(min(((a * h + b) % MERSENNE) for h in hs))
    return sig


def _band_keys(sig):
    for j in range(BANDS):
        yield (j, tuple(sig[j * ROWS:(j + 1) * ROWS]))


class BankIndex:
    """In-memory exact + LSH index over a list of bank records.

    Each record is a dict with at least 'question_text' (and ideally
    'fingerprint'). Bank MinHash signatures are loaded from / saved to a
    fingerprint-keyed sidecar cache so they are computed once per stem ever.
    """

    def __init__(self, records, cache_path=None):
        self.records = records
        self.cache_path = cache_path
        self._token_cache = {}                 # idx -> token set (lazy, candidates only)
        cache = self._load_cache()
        self.fp_to_idx = {}
        self.buckets = {}
        dirty = False
        for idx, r in enumerate(records):
            text = record_text(r)
            fp = r.get("fingerprint") or fingerprint(text)
            self.fp_to_idx.setdefault(fp, idx)
            sig = cache.get(fp)
            if sig is None:
                sig = minhash(tokens(text))
                cache[fp] = sig
                dirty = True
            for key in _band_keys(sig):
                self.buckets.setdefault(key, []).append(idx)
        if dirty:
            self._save_cache(cache)

    def _load_cache(self):
        if self.cache_path and os.path.exists(self.cache_path):
            try:
                with open(self.cache_path, encoding="utf-8") as f:
                    return json.load(f)
            except (ValueError, OSError):
                return {}
        return {}

    def _save_cache(self, cache):
        if not self.cache_path:
            return
        try:
            os.makedirs(os.path.dirname(self.cache_path) or ".", exist_ok=True)
            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump(cache, f)
        except OSError:
            pass

    def _toks(self, idx):
        t = self._token_cache.get(idx)
        if t is None:
            t = tokens(record_text(self.records[idx]))
            self._token_cache[idx] = t
        return t

    def query(self, text, threshold):
        """Return (verdict, score, matched_record_or_None).

        verdict in {EXACT_DUPLICATE, NEAR_DUPLICATE, UNIQUE}.
        """
        fp = fingerprint(text)
        if fp in self.fp_to_idx:
            return "EXACT_DUPLICATE", 1.0, self.records[self.fp_to_idx[fp]]
        qtok = tokens(text)
        sig = minhash(qtok)
        cands = set()
        for key in _band_keys(sig):
            cands.update(self.buckets.get(key, ()))
        best, best_idx = 0.0, None
        for idx in cands:
            j = jaccard(qtok, self._toks(idx))
            if j > best:
                best, best_idx = j, idx
        if best >= threshold:
            return "NEAR_DUPLICATE", round(best, 3), self.records[best_idx]
        return "UNIQUE", round(best, 3), None
