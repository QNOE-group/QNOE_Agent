"""Shared loader for the grounding-validator regression tests.

These tests exercise the real plugin code against the LIVE QCoDeS registry, so
they must run where the registry SQLite files (grounding_validator.REGISTRY_DBS)
exist — i.e. on the DGX, or a staging copy that points AGENT_DATA_DIR at one.

Plugin-dir resolution order (first hit wins):
  1. $QNOE_PLUGIN_DIR        — point at a /tmp staging copy to test un-deployed
                               edits before `sudo cp` to /opt.
  2. repo layout             — redteam/grounding/ -> ../../hermes/plugins/qnoe_rag
  3. /opt/qnoe-agent/hermes/plugins/qnoe_rag  — the deployed copy.
"""
import importlib.util
import os
import sys
import types


def plugin_dir() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    for d in (
        os.environ.get("QNOE_PLUGIN_DIR"),
        os.path.abspath(os.path.join(here, "..", "..", "hermes", "plugins", "qnoe_rag")),
        "/opt/qnoe-agent/hermes/plugins/qnoe_rag",
    ):
        if d and os.path.exists(os.path.join(d, "grounding_validator.py")):
            return d
    raise RuntimeError(
        "qnoe_rag plugin dir not found — set QNOE_PLUGIN_DIR to a directory "
        "containing grounding_validator.py (+ __init__.py for the find_file test)."
    )


def _load(name: str, filename: str):
    path = os.path.join(plugin_dir(), filename)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_grounding_validator():
    """The standalone validator module (own regexes + DB paths, no heavy deps)."""
    return _load("gv_under_test", "grounding_validator.py")


def load_qnoe_rag():
    """The qnoe_rag package __init__ — stub its one non-stdlib top-level import
    (agent.memory_provider) so the find_file gate/extraction can load stdlib-only."""
    if "agent.memory_provider" not in sys.modules:
        mp = types.ModuleType("agent.memory_provider")

        class MemoryProvider:  # noqa: D401 — stub base class
            pass

        mp.MemoryProvider = MemoryProvider
        pkg = types.ModuleType("agent")
        pkg.__path__ = []
        sys.modules.setdefault("agent", pkg)
        sys.modules["agent.memory_provider"] = mp
    return _load("qnoe_rag_under_test", "__init__.py")
