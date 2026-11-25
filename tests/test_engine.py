# -*- coding: utf-8 -*-
"""Drive the real engine against a fake IBus, so the key handling can be
tested without a desktop.

Run:  python3 tests/test_engine.py
"""

import importlib.util
import os
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

ENGINE = os.path.join(ROOT, "src", "ibus-engine-tamil-custom")


# --------------------------------------------------------------------- fake
class FakeText(object):
    def __init__(self, text):
        self.text = text

    @staticmethod
    def new_from_string(text):
        return FakeText(text)


class ModifierType(object):
    RELEASE_MASK = 1 << 30
    CONTROL_MASK = 1 << 2
    MOD1_MASK = 1 << 3
    SUPER_MASK = 1 << 26
    SHIFT_MASK = 1 << 0
    LOCK_MASK = 1 << 1


class FakeEngineSimple(object):
    """Records what the engine does to the document."""

    def __init__(self, **kwargs):
        self.ops = []

    def commit_text(self, text):
        self.ops.append(("commit", text.text))

    def delete_surrounding_text(self, offset, n_chars):
        self.ops.append(("delete", offset, n_chars))

    def update_preedit_string(self, *args, **kwargs):
        pass


fake_ibus = types.SimpleNamespace(
    ModifierType=ModifierType,
    Text=FakeText,
    EngineSimple=FakeEngineSimple,
)


def load_engine():
    # the engine has no .py suffix, so give it an explicit loader
    from importlib.machinery import SourceFileLoader

    loader = SourceFileLoader("eluthu_engine", ENGINE)
    spec = importlib.util.spec_from_loader("eluthu_engine", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def run(keys, caps=False, shift=False):
    """Feed latin keys through the real handler, return the final document."""
    module = load_engine()
    cls = module.build_engine_class(fake_ibus)
    engine = cls(bus=None, object_path="/fake")

    document = []
    for ch in keys:
        state = 0
        if caps:
            state |= ModifierType.LOCK_MASK
        if shift:
            state |= ModifierType.SHIFT_MASK
        handled = engine.do_process_key_event(ord(ch), 0, state)
        for op in engine.ops:
            if op[0] == "commit":
                document.append(op[1])
            elif op[0] == "delete" and document:
                document.pop()
        engine.ops = []
        if not handled:
            document.append(ch)
    return "".join(document)


FAILS = []


def check(label, got, want):
    if got != want:
        FAILS.append("%-22s got %r  want %r" % (label, got, want))


# ------------------------------------------------------------------- cases
check("a", run("a"), "க")
check("sx", run("sx"), "சி")
check("az", run("az"), "க்")
check("q^z", run("qz", caps=True), "வா")
check("caps+ka", run("az", caps=True), "கா")

# the doubling rule
check("zz", run("zz"), "ஆ")
check("xx", run("xx"), "ஈ")
check("azz", run("azz"), "கா")
check("sxx", run("sxx"), "சீ")
check("ebb", run("ebb"), "ளோ")
check("a^x", run("ax", caps=True), "கீ")
check("zzz", run("zzz"), "ஆஅ")

# pass-through
check("space", run("a z"), "க அ")
check("digits", run("1a"), "1க")

# delete must actually be used for the doubling
module = load_engine()
cls = module.build_engine_class(fake_ibus)
engine = cls(bus=None, object_path="/fake")
engine.do_process_key_event(ord("z"), 0, 0)
engine.ops = []
engine.do_process_key_event(ord("z"), 0, 0)
kinds = [op[0] for op in engine.ops]
check("doubling ops", kinds, ["delete", "commit"])

# ------------------------------------------------------------------ report
if FAILS:
    print("\n".join(FAILS))
    print("\n%d test(s) FAILED" % len(FAILS))
    sys.exit(1)
print("all engine checks passed")
