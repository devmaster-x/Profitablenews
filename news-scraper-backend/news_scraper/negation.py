"""Negation-context detection for keyword scoring (Phase 1).

A keyword that appears inside a negated context (denial, delay, cancellation,
rejection, ...) must not inflate a profit score. Single-token negators are
matched token-exactly; multi-token phrases are matched as substrings of the
+/- window around the keyword.
"""

from __future__ import annotations

import re

# Single-token negators. Matched token-exactly within the keyword's window.
NEGATION_SINGLE = {
    # Simple negators
    'not', 'no', 'never', 'nor', 'neither',
    # Contractions
    "wasn't", "isn't", "aren't", "weren't", "won't", "wouldn't",
    "can't", "couldn't", "don't", "doesn't", "didn't", "haven't", "hasn't", "ain't",
    # Denial / rejection
    'deny', 'denies', 'denied', 'denial', 'reject', 'rejects', 'rejected',
    'rejection', 'rejecting', 'refuse', 'refuses', 'refused',
    # Failure
    'fail', 'fails', 'failed', 'failure', 'scrapped',
    # Delay / postponement
    'postpone', 'postpones', 'postponed', 'delay', 'delays', 'delayed',
    'defer', 'defers', 'deferred', 'stall', 'stalls', 'stalled',
    # Cancellation / suspension
    'cancel', 'cancels', 'canceled', 'cancelled', 'halt', 'halts', 'halted',
    'suspend', 'suspends', 'suspended', 'suspension', 'pause', 'pauses', 'paused',
    # Withdrawal / reversal
    'withdraw', 'withdraws', 'withdrawn', 'reverses', 'reversed', 'reversal',
    'abandon', 'abandons', 'abandoned', 'abandonment', 'block', 'blocks', 'blocked',
}

# Multi-token negation phrases, matched as substrings of the window.
NEGATION_MULTI = [
    'falls through', 'fell through', 'on hold', 'turn down', 'turns down',
    'turned down', 'knocked back', 'rebuffed', 'blocked by', 'scrapped by',
]


class NegationDetector:
    def __init__(
        self,
        single: set[str] = NEGATION_SINGLE,
        multi: list[str] = NEGATION_MULTI,
    ) -> None:
        self.negation_patterns_single = single
        self.negation_patterns_multi = multi

    def check_negation_context(self, text: str, keyword: str, window: int = 6) -> float:
        """Return 0.0 if ``keyword`` appears in a negated context, else 1.0.

        Sentence-bounded: the text is split into sentences first, so a
        negation in a *different* sentence does not cancel the keyword.
        Within the keyword's sentence, the +/- ``window`` words are scanned
        for negation phrases.
        """
        kw_tokens = re.findall(r"[a-z0-9']+", keyword.lower())
        if not kw_tokens:
            return 1.0

        k = len(kw_tokens)
        sentences = re.split(r'[.!?;\n]+', text.lower())
        for sentence in sentences:
            words = re.findall(r"[a-z0-9']+", sentence)
            for i in range(len(words) - k + 1):
                if words[i:i + k] == kw_tokens:
                    lo = max(0, i - window)
                    hi = min(len(words), i + k + window)
                    neighborhood = words[lo:hi]

                    if any(tok in self.negation_patterns_single for tok in neighborhood):
                        return 0.0

                    neighborhood_str = ' '.join(neighborhood)
                    if any(phrase in neighborhood_str for phrase in self.negation_patterns_multi):
                        return 0.0

        return 1.0
