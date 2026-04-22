#!/usr/bin/env python3
"""
Auto-archive simulation artifacts on round updates.

Usage:
  python backend/scripts/auto_archive_rounds.py --simulation-id sim_xxx
  python backend/scripts/auto_archive_rounds.py --simulation-id sim_xxx --interval 3
"""

from __future__ import annotations

import argparse
import json
import shutil
import time
from datetime import datetime
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Archive simulation data per round.")
    parser.add_argument("--simulation-id", required=True, help="Simulation id, e.g. sim_xxx")
    parser.add_argument("--interval", type=float, default=2.0, help="Polling interval seconds")
    parser.add_argument(
        "--output-root",
        default="backend/uploads/archives",
        help="Archive root directory (default: backend/uploads/archives)",
    )
    return parser.parse_args()


def read_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def copy_if_exists(src: Path, dst: Path) -> None:
    if not src.exists():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def archive_snapshot(sim_dir: Path, out_root: Path, simulation_id: str, marker: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    snap_dir = out_root / simulation_id / f"{marker}_{stamp}"
    snap_dir.mkdir(parents=True, exist_ok=True)

    # Core state files
    copy_if_exists(sim_dir / "run_state.json", snap_dir / "run_state.json")
    copy_if_exists(sim_dir / "state.json", snap_dir / "state.json")
    copy_if_exists(sim_dir / "simulation_config.json", snap_dir / "simulation_config.json")
    copy_if_exists(sim_dir / "reddit_profiles.json", snap_dir / "reddit_profiles.json")
    copy_if_exists(sim_dir / "twitter_profiles.csv", snap_dir / "twitter_profiles.csv")

    # Runtime logs and db files
    copy_if_exists(sim_dir / "simulation.log", snap_dir / "simulation.log")
    copy_if_exists(sim_dir / "twitter" / "actions.jsonl", snap_dir / "twitter" / "actions.jsonl")
    copy_if_exists(sim_dir / "reddit" / "actions.jsonl", snap_dir / "reddit" / "actions.jsonl")
    copy_if_exists(sim_dir / "twitter_simulation.db", snap_dir / "twitter_simulation.db")
    copy_if_exists(sim_dir / "reddit_simulation.db", snap_dir / "reddit_simulation.db")

    return snap_dir


def main() -> int:
    args = parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    sim_dir = repo_root / "backend" / "uploads" / "simulations" / args.simulation_id
    out_root = repo_root / args.output_root

    if not sim_dir.exists():
        print(f"[ERR] Simulation directory not found: {sim_dir}")
        return 1

    run_state_file = sim_dir / "run_state.json"
    print(f"[INFO] Watching: {run_state_file}")
    print(f"[INFO] Archive root: {out_root / args.simulation_id}")
    print(f"[INFO] Poll interval: {args.interval}s")

    last_round = None
    last_status = None
    archived_markers: set[str] = set()

    # Always archive once at startup
    snap = archive_snapshot(sim_dir, out_root, args.simulation_id, "start")
    print(f"[ARCHIVE] start -> {snap}")
    archived_markers.add("start")

    while True:
        state = read_json(run_state_file)
        if state is None:
            time.sleep(args.interval)
            continue

        current_round = state.get("current_round", 0)
        status = state.get("runner_status", "unknown")

        if last_round is None:
            last_round = current_round
            last_status = status

        if current_round != last_round:
            marker = f"round_{int(current_round):03d}"
            snap = archive_snapshot(sim_dir, out_root, args.simulation_id, marker)
            print(f"[ARCHIVE] {marker} ({last_round} -> {current_round}) -> {snap}")
            last_round = current_round

        if status != last_status:
            marker = f"status_{status}"
            snap = archive_snapshot(sim_dir, out_root, args.simulation_id, marker)
            print(f"[ARCHIVE] {marker} ({last_status} -> {status}) -> {snap}")
            last_status = status
            archived_markers.add(marker)

        # Exit when simulation ends
        if status in {"completed", "stopped", "failed", "idle"}:
            if "final" not in archived_markers:
                snap = archive_snapshot(sim_dir, out_root, args.simulation_id, "final")
                print(f"[ARCHIVE] final -> {snap}")
            print(f"[DONE] Simulation finished with status={status}.")
            return 0

        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())

