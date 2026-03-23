from __future__ import annotations

import sys
import types
from pathlib import Path


def _install_matplotlib_stub() -> None:
    if "matplotlib" in sys.modules:
        return

    class _DummyAxes:
        def plot(self, *args, **kwargs):
            return []

        def bar(self, *args, **kwargs):
            return []

        def axhline(self, *args, **kwargs):
            return None

        def set_title(self, *args, **kwargs):
            return None

        def set_ylabel(self, *args, **kwargs):
            return None

        def set_xlabel(self, *args, **kwargs):
            return None

        def legend(self, *args, **kwargs):
            return None

    class _DummyFigure:
        def tight_layout(self):
            return None

        def savefig(self, path, *args, **kwargs):
            target = Path(path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("", encoding="utf-8")

    pyplot = types.ModuleType("matplotlib.pyplot")
    pyplot.subplots = lambda *args, **kwargs: (_DummyFigure(), _DummyAxes())
    pyplot.close = lambda *args, **kwargs: None
    pyplot.Figure = _DummyFigure
    pyplot.Axes = _DummyAxes

    matplotlib = types.ModuleType("matplotlib")
    matplotlib.use = lambda *args, **kwargs: None
    matplotlib.pyplot = pyplot

    sys.modules["matplotlib"] = matplotlib
    sys.modules["matplotlib.pyplot"] = pyplot


_install_matplotlib_stub()
