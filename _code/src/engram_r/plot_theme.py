"""Matplotlib/Seaborn theme anchored to _code/styles/STYLE_GUIDE.md + PLOT_DESIGN.md.

Provides consistent styling for all Python-generated figures in the
co-scientist system. Constants and helpers match the R theme_research().

Palettes are loaded from ``_code/styles/palettes.yaml`` when available, with
hardcoded fallbacks for offline / CI use.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import matplotlib as mpl
import matplotlib.pyplot as plt
import seaborn as sns

logger = logging.getLogger(__name__)

# -- Palette loading -----------------------------------------------------------

# Hardcoded fallback palettes (used when YAML is unavailable).
# Only universal (domain-agnostic) palettes live here. Domain-specific
# palettes (sex, dx, labs) are loaded from domain profiles.
_FALLBACK_BINARY: dict[str, str] = {"Control": "#4DAF4A", "Case": "#E41A1C"}
_FALLBACK_DIRECTION: dict[str, str] = {
    "Up": "#E41A1C",
    "Down": "#377EB8",
    "NS": "#999999",
}
_FALLBACK_SIG: dict[str, str] = {"sig": "#E41A1C", "not sig": "#999999"}


def _find_palettes_yaml() -> Path | None:
    """Locate ``_code/styles/palettes.yaml`` relative to this file."""
    # _code/src/engram_r/plot_theme.py -> _code/ is 3 levels up
    code_dir = Path(__file__).resolve().parent.parent.parent
    candidate = code_dir / "styles" / "palettes.yaml"
    if candidate.is_file():
        return candidate
    return None


def load_palettes(yaml_path: Path | None = None) -> dict[str, Any]:
    """Load palettes from YAML, falling back to hardcoded defaults.

    Args:
        yaml_path: Explicit path to palettes.yaml. If None, auto-detects
            from vault structure.

    Returns:
        Dict with keys: ``semantic``, ``labs``, ``diverging``, ``sequential``.
    """
    path = yaml_path or _find_palettes_yaml()
    if path is not None and path.is_file():
        try:
            import yaml

            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                logger.debug("Loaded palettes from %s", path)
                return data
        except Exception:
            logger.warning("Failed to load %s, using fallback palettes", path)
    return {
        "semantic": {
            "binary": _FALLBACK_BINARY,
            "direction": _FALLBACK_DIRECTION,
            "sig": _FALLBACK_SIG,
        },
        "diverging": "RdBu_r",
        "sequential": "Blues",
    }


_PALETTES = load_palettes()

# -- Color constants (matching _code/styles/STYLE_GUIDE.md) --------------------

_SEM = _PALETTES.get("semantic", {})

# -- Semantic palettes (universal) --------------------------------------------

BINARY_COLORS: dict[str, str] = _SEM.get("binary", _FALLBACK_BINARY)
DIRECTION_COLORS: dict[str, str] = _SEM.get("direction", _FALLBACK_DIRECTION)
SIG_COLORS: dict[str, str] = _SEM.get("sig", _FALLBACK_SIG)

SEMANTIC_PALETTES: dict[str, dict[str, str]] = {
    "binary": BINARY_COLORS,
    "direction": DIRECTION_COLORS,
    "sig": SIG_COLORS,
}

CATEGORICAL_PALETTE: str = _PALETTES.get("categorical", "Set1")
DIVERGING_PALETTE: str = _PALETTES.get("diverging", "RdBu_r")
SEQUENTIAL_PALETTE: str = _PALETTES.get("sequential", "Blues")

# -- Lab-specific categorical palettes -----------------------------------------

LAB_PALETTES: dict[str, list[str]] = _PALETTES.get("labs", {})

# -- Standard figure sizes (inches) -------------------------------------------

FIGURE_SIZES: dict[str, tuple[float, float]] = {
    "box_grouped": (8, 6),
    "box_single": (6, 6),
    "violin_grouped": (8, 6),
    "violin_single": (6, 6),
    "scatter_multi": (18, 7),
    "scatter_single": (14, 8),
    "scatter_bivar": (10, 6),
    "heatmap": (10, 6),
    "forest": (10, 8),
    "volcano": (10, 8),
    "roc": (7, 7),
    "bar": (8, 6),
}

# -- Theme constants -----------------------------------------------------------

BASE_FONT_SIZE: int = 14
TITLE_WEIGHT: str = "bold"
STRIP_BG_COLOR: str = "#E5E5E5"  # grey90
LEGEND_POSITION: str = "bottom"


def get_lab_palette(lab: str, n: int | None = None) -> list[str]:
    """Get a lab-specific categorical color palette.

    Args:
        lab: Lab name (e.g. "your-lab"), case-insensitive.
        n: Number of colors to return (default: all 8).

    Returns:
        List of hex color strings.

    Raises:
        ValueError: If lab name is unknown or n exceeds palette size.
    """
    lab_lower = lab.lower()
    if lab_lower not in LAB_PALETTES:
        if not LAB_PALETTES:
            msg = (
                "No lab palettes configured. "
                "Load a domain profile or define labs in palettes.yaml."
            )
        else:
            valid = ", ".join(LAB_PALETTES.keys())
            msg = f"Unknown lab: '{lab}'. Choose from: {valid}"
        raise ValueError(msg)
    palette = LAB_PALETTES[lab_lower]
    if n is not None:
        if n > len(palette):
            msg = f"Requested {n} colors but palette has only {len(palette)}"
            raise ValueError(msg)
        return palette[:n]
    return list(palette)


def get_figure_size(plot_type: str) -> tuple[float, float]:
    """Get canonical figure size for a plot type.

    Args:
        plot_type: Key from FIGURE_SIZES (e.g. "box_grouped", "volcano").

    Returns:
        Tuple of (width, height) in inches.

    Raises:
        ValueError: If plot_type is not recognized.
    """
    if plot_type not in FIGURE_SIZES:
        valid = ", ".join(FIGURE_SIZES.keys())
        msg = f"Unknown plot type: '{plot_type}'. Choose from: {valid}"
        raise ValueError(msg)
    return FIGURE_SIZES[plot_type]


def apply_research_theme(font_size: int = BASE_FONT_SIZE) -> None:
    """Apply the canonical research theme to matplotlib/seaborn.

    Sets rcParams to match _code/styles/STYLE_GUIDE.md: classic base, bold titles,
    bottom legend, grey90 strip backgrounds (approximated via figure facecolor).

    Args:
        font_size: Base font size (default 14).
    """
    plt.style.use("classic")

    rc_updates: dict[str, Any] = {
        # Font
        "font.size": font_size,
        "axes.titleweight": TITLE_WEIGHT,
        "axes.titlesize": font_size + 2,
        "axes.labelsize": font_size,
        # Clean look (classic base)
        "axes.grid": False,
        "axes.spines.top": False,
        "axes.spines.right": False,
        # Legend at bottom
        "legend.loc": "lower center",
        "legend.frameon": False,
        # Figure
        "figure.facecolor": "white",
        "figure.dpi": 150,
        "savefig.dpi": 300,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.1,
        # Lines
        "lines.linewidth": 0.8,
    }
    mpl.rcParams.update(rc_updates)
    sns.set_palette(CATEGORICAL_PALETTE)
    logger.info("Applied research theme (font_size=%d)", font_size)


def save_figure(
    fig: plt.Figure,
    path: str | Path,
    *,
    fmt: str = "pdf",
    dpi: int = 300,
    close: bool = True,
    sidecar_text: str | None = None,
) -> Path:
    """Save a figure to disk with canonical settings.

    Always saves as vector PDF by default. Never calls plt.show().

    Args:
        fig: Matplotlib figure to save.
        path: Output file path (extension will be appended if missing).
        fmt: Output format -- "pdf" (default), "png", "svg", "tiff".
        dpi: Resolution for raster formats (default 300).
        close: Whether to close the figure after saving.
        sidecar_text: Optional text to write as a _pvalues.txt sidecar file.

    Returns:
        Path to saved figure file.
    """
    path = Path(path)
    if not path.suffix:
        path = path.with_suffix(f".{fmt}")

    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, format=fmt, dpi=dpi, bbox_inches="tight")
    logger.info("Saved figure: %s", path)

    if sidecar_text is not None:
        sidecar_path = path.with_name(path.stem + "_pvalues.txt")
        sidecar_path.write_text(sidecar_text, encoding="utf-8")
        logger.info("Saved sidecar: %s", sidecar_path)

    if close:
        plt.close(fig)

    return path
