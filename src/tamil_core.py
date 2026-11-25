# -*- coding: utf-8 -*-
"""Pure input logic for the custom Tamil keyboard layout.

No IBus / GTK / X11 dependencies live here, so the whole layout can be
unit-tested (see tests/test_tamil_core.py) on any machine.

Model
-----
* Base layer  : one qwerty key -> one Tamil letter.
* Next key    : a vowel pressed *right after* a consonant becomes that
                consonant's vowel sign (matra).  ச + இ -> சி
                Pressing அ after a consonant gives the virama: ச + அ -> ச்
* Caps Lock   : long vowel (நெடில்).  Caps + அ -> ஆ, and after a
                consonant it becomes the long sign: வ + Caps+அ -> வா
* Shift       : grantha / rare letters (ஸ ஷ ஜ ஹ க்ஷ) and a lone virama.
* Doubling    : the same short vowel twice gives the long one.
                அ + அ -> ஆ, இ + இ -> ஈ, க + இ + இ -> கீ, ள + ஒ + ஒ -> ளோ
                The virama doubles too: க + அ + அ -> கா
"""

VIRAMA = "\u0BCD"          # ்
TAMIL_EE = "\u0BC0"        # ீ
TAMIL_AA = "\u0BBE"        # ா
TAMIL_UU = "\u0BC2"        # ூ
TAMIL_EE_SIGN = TAMIL_EE
TAMIL_AI = "\u0BC8"        # ை
TAMIL_AU = "\u0BCC"        # ௌ
TAMIL_E_LONG = "\u0BC7"    # ே
TAMIL_O_LONG = "\u0BCB"    # ோ

AYTHAM = "\u0B83"          # ஃ

# --------------------------------------------------------------- base layer
# qwerty -> Tamil (the mapping the layout was designed around)
BASE = {
    # top row
    "q": "\u0BB5",  # வ
    "w": "\u0BB4",  # ழ
    "e": "\u0BB3",  # ள
    "r": "\u0B99",  # ங
    "t": "\u0B9E",  # ஞ
    "y": "\u0BA3",  # ண
    "u": "\u0BA8",  # ந
    "i": "\u0BAE",  # ம
    "o": "\u0BA9",  # ன
    "p": AYTHAM,    # ஃ
    # home row
    "a": "\u0B95",  # க
    "s": "\u0B9A",  # ச
    "d": "\u0B9F",  # ட
    "f": "\u0BA4",  # த
    "g": "\u0BAA",  # ப
    "h": "\u0BB1",  # ற
    "j": "\u0BAF",  # ய
    "k": "\u0BB0",  # ர
    "l": "\u0BB2",  # ல
    # bottom row
    "z": "\u0B85",  # அ
    "x": "\u0B87",  # இ
    "c": "\u0B89",  # உ
    "v": "\u0B8E",  # எ
    "b": "\u0B92",  # ஒ
    "n": "\u0B90",  # ஐ
    "m": "\u0B94",  # ஔ
}

# Shift layer: grantha letters + a lone virama
SHIFT = {
    "a": "\u0B95\u0BCD\u0BB7",  # க்ஷ
    "s": "\u0BB8",              # ஸ
    "d": "\u0BB7",              # ஷ
    "f": "\u0B9C",              # ஜ
    "g": "\u0BB9",              # ஹ
    "z": VIRAMA,                # ்  (stand-alone pulli)
}

# Short / long independent vowels  (long = Caps Lock on)
INDEPENDENT = {
    "z": ("\u0B85", "\u0B86"),  # அ  ஆ
    "x": ("\u0B87", "\u0B88"),  # இ  ஈ
    "c": ("\u0B89", "\u0B8A"),  # உ  ஊ
    "v": ("\u0B8E", "\u0B8F"),  # எ  ஏ
    "b": ("\u0B92", "\u0B93"),  # ஒ  ஓ
    "n": ("\u0B90", "\u0B90"),  # ஐ  ஐ
    "m": ("\u0B94", "\u0B94"),  # ஔ  ஔ
}

# Vowel sign used after a consonant: (short, long)
SIGNS = {
    "z": (VIRAMA, TAMIL_AA),        # ச + அ -> ச்   |  ச + ஆ -> சா
    "x": ("\u0BBF", TAMIL_EE),      # ச + இ -> சி   |  ச + ஈ -> சீ
    "c": ("\u0BC1", TAMIL_UU),      # ச + உ -> சு   |  ச + ஊ -> சூ
    "v": ("\u0BC6", TAMIL_E_LONG),  # ச + எ -> செ   |  ச + ஏ -> சே
    "b": ("\u0BCA", TAMIL_O_LONG),  # ச + ஒ -> சொ   |  ச + ஓ -> சோ
    "n": (TAMIL_AI, TAMIL_AI),      # ச + ஐ -> சை   |  ச + ஐ -> சை
    "m": (TAMIL_AU, TAMIL_AU),      # ச + ஔ -> சௌ   |  ச + ஔ -> சௌ
}

VOWEL_KEYS = tuple(INDEPENDENT.keys())

# Every letter the layout can emit as a "consonant" (things a vowel sign
# may attach to).
CONSONANTS = tuple(
    value for key, value in BASE.items() if key not in INDEPENDENT and value != AYTHAM
) + ("\u0B95\u0BCD\u0BB7", "\u0BB8", "\u0BB7", "\u0B9C", "\u0BB9")


def is_consonant(text):
    return text in CONSONANTS


class Step(object):
    """What the engine should do for one key press.

    discard  clear the held preedit without committing it (the doubling case)
    flush    commit the held preedit first
    text     the text to output
    preedit  True: hold ``text`` in the preedit; False: commit it
    """

    __slots__ = ("discard", "flush", "text", "preedit")

    def __init__(self, discard, flush, text, preedit):
        self.discard = discard
        self.flush = flush
        self.text = text
        self.preedit = preedit

    def __repr__(self):
        return "Step(discard=%r, flush=%r, text=%r, preedit=%r)" % (
            self.discard, self.flush, self.text, self.preedit)


class Composer(object):
    """Turns single latin key presses into Tamil text.

    ``feed()`` returns a :class:`Step`, or ``None`` when the key is not part
    of the layout (space, digits, arrows, ...) and should be passed through
    to the application untouched.
    """

    def __init__(self):
        self.pending = None  # consonant the next vowel sign may attach to
        self.held = None     # (key, short, long) currently sitting in preedit

    def reset(self):
        self.pending = None
        self.held = None

    # -- main entry point ---------------------------------------------------
    def feed(self, key, caps=False, shift=False):
        if not key or len(key) != 1:
            return None
        k = key.lower()
        if not ("a" <= k <= "z"):
            return None

        # --- the same short vowel again: promote it to the long form
        if self.held is not None and k == self.held[0] and not shift:
            long_form = self.held[2]
            self.held = None
            self.pending = None
            return Step(discard=True, flush=False, text=long_form, preedit=False)

        # --- Shift layer: grantha letters and the lone virama
        if shift and k in SHIFT:
            out = SHIFT[k]
            self.held = None
            self.pending = None if out == VIRAMA else out
            return Step(discard=False, flush=True, text=out, preedit=False)

        if k not in BASE:
            return None

        # --- a vowel key
        if k in INDEPENDENT:
            want_long = bool(caps)

            if self.pending is not None:
                # attach to the consonant: sign, long sign, or the virama
                sign = SIGNS[k][1 if want_long else 0]
                self.pending = None
                if want_long:
                    # க + Caps அ = கா
                    self.held = None
                    return Step(False, True, sign, False)
                self.held = (k, sign, SIGNS[k][1])
                return Step(False, True, sign, True)

            if want_long:
                self.held = None
                return Step(False, True, INDEPENDENT[k][1], False)

            self.held = (k, INDEPENDENT[k][0], INDEPENDENT[k][1])
            return Step(False, True, INDEPENDENT[k][0], True)

        # --- a consonant (or aytham, which nothing can attach to)
        out = BASE[k]
        self.held = None
        self.pending = None if out == AYTHAM else out
        return Step(False, True, out, False)


def type_text(keys, caps=False):
    """Helper used by the tests / chart builder.

    ``keys`` is a latin string; ``^`` toggles Caps Lock inside the string and
    ``~`` toggles Shift.  Everything else is fed to the composer.
    """
    composer = Composer()
    out = []
    cap_state = caps
    shift_state = False
    for ch in keys:
        if ch == "^":
            cap_state = not cap_state
            continue
        if ch == "~":
            shift_state = not shift_state
            continue
        step = composer.feed(ch, caps=cap_state, shift=shift_state)
        if step is None:
            composer.reset()
            out.append(ch)
        else:
            if step.discard and out:
                out.pop()          # the held vowel is replaced, not kept
            out.append(step.text)
        shift_state = False
    return "".join(out)
