"""Run the whole pipeline: ingest, models, analysis, skip model, export.

Usage:
    python -m src.run_all                    # your real data in data/raw
    python -m src.run_all --sample           # synthetic data (python -m src.make_sample first)
    python -m src.run_all --skip-ingest      # reuse the existing database
    python -m src.run_all --redact-tracks    # hash track and artist names on export
"""
import argparse
from pathlib import Path

from src import analysis, export, ingest, profile, run_models, skip_model
from src.config import RAW_DIR, SAMPLE_DIR


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, default=None)
    parser.add_argument("--sample", action="store_true")
    parser.add_argument("--skip-ingest", action="store_true")
    parser.add_argument("--redact-tracks", action="store_true")
    args = parser.parse_args()

    raw_dir = args.raw or (SAMPLE_DIR if args.sample else RAW_DIR)

    if not args.skip_ingest:
        print(f"\n[1/6] Ingest from {raw_dir}")
        ingest.ingest(raw_dir)
    print("\n[2/6] SQL models")
    run_models.run_models()
    print("\n[3/6] Profile")
    profile.run()
    print("\n[4/6] Decay survival curve and event overlay")
    analysis.run()
    print("\n[5/6] Skip model")
    skip_model.run()
    print("\n[6/6] Export public aggregates")
    export.export(args.redact_tracks)


if __name__ == "__main__":
    main()
