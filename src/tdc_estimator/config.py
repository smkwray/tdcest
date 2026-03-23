from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


USER_AGENT = "tdc-estimator/0.1.0"
FRED_API_BASE = "https://api.stlouisfed.org/fred/series/observations"
FRED_GRAPH_CSV_BASE = "https://fred.stlouisfed.org/graph/fredgraph.csv"
TREASURY_API_BASE = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service"


@dataclass(frozen=True)
class ProjectPaths:
    root: Path
    raw: Path
    processed: Path
    figures: Path
    site: Path


def project_paths(root: Path | str = ".") -> ProjectPaths:
    root_path = Path(root).resolve()
    raw = root_path / "data" / "raw"
    processed = root_path / "data" / "processed"
    figures = root_path / "data" / "figures"
    site = root_path / "data" / "site"
    return ProjectPaths(root=root_path, raw=raw, processed=processed, figures=figures, site=site)


def ensure_project_dirs(paths: ProjectPaths) -> None:
    for path in [paths.raw, paths.processed, paths.figures, paths.site]:
        path.mkdir(parents=True, exist_ok=True)
