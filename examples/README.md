# Examples

`make demo` (or `tdc demo`) runs the full estimation pipeline on synthetic inputs and writes the results to `examples/demo_build/`. It needs no network access or API key, and shows the shape of every output without downloading live data.

The demo directory contains:

- `data/raw/`: synthetic input series
- `data/processed/`: quarterly estimates and diagnostics
- `data/figures/`: figures
- `data/site/`: JSON and CSV export bundle
- `demo_summary.json`: a summary of the run

The values are synthetic and carry no economic meaning. The directory is generated locally and is not tracked.
