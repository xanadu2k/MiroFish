#!/usr/bin/env python3
"""
Export a Zep standalone graph (via local backend API) to local disk.

This avoids embedding Zep credentials in the script: it calls the running backend:
  GET /api/graph/data/<graph_id>

Usage:
  python backend/scripts/export_graph_snapshot.py --graph-id mirofish_xxx
  python backend/scripts/export_graph_snapshot.py --graph-id mirofish_xxx --api-base http://127.0.0.1:5556
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Export graph snapshot to backend/uploads/graphs/<graph_id>/")
    p.add_argument("--graph-id", required=True, help="Graph id, e.g. mirofish_a9640b9b61e944ba")
    p.add_argument("--api-base", default="http://127.0.0.1:5556", help="Backend base URL")
    p.add_argument(
        "--output-root",
        default="backend/uploads/graphs",
        help="Output root dir (relative to repo root by default)",
    )
    p.add_argument("--include-history", action="store_true", help="Try to attach project/sim/report linkage from history API")
    return p.parse_args()


def http_get_json(url: str, timeout: float = 10.0) -> dict:
    req = Request(url, headers={"Accept": "application/json"})
    with urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
    return json.loads(raw)


def main() -> int:
    args = parse_args()
    graph_id = args.graph_id.strip()
    if not graph_id:
        raise SystemExit("graph_id cannot be empty")

    repo_root = Path(__file__).resolve().parents[2]
    out_root = (repo_root / args.output_root).resolve()
    out_dir = out_root / graph_id
    out_dir.mkdir(parents=True, exist_ok=True)

    graph_url = f"{args.api_base.rstrip('/')}/api/graph/data/{graph_id}"
    try:
        payload = http_get_json(graph_url, timeout=30.0)
    except URLError as e:
        raise SystemExit(
            "Cannot reach backend API.\n"
            f"- url: {graph_url}\n"
            f"- reason: {e}\n"
            "Please start backend first (e.g. `npm run dev`) and retry."
        )
    if not payload.get("success", False):
        err = payload.get("error") or "unknown error"
        raise SystemExit(f"Backend returned error: {err}")

    graph_data = payload.get("data") or {}
    (out_dir / "graph.json").write_text(json.dumps(graph_data, ensure_ascii=False, indent=2), encoding="utf-8")

    meta: dict = {
        "graph_id": graph_id,
        "exported_at": datetime.now().isoformat(),
        "api_base": args.api_base,
        "node_count": graph_data.get("node_count"),
        "edge_count": graph_data.get("edge_count"),
    }

    if args.include_history:
        try:
            hist_url = f"{args.api_base.rstrip('/')}/api/simulation/history?limit=50"
            hist = http_get_json(hist_url, timeout=10.0)
            items = hist.get("data") or []
            matches = [i for i in items if i.get("graph_id") == graph_id]
            # Prefer running, else newest by created_at
            matches.sort(
                key=lambda x: (
                    0 if x.get("runner_status") == "running" else 1,
                    x.get("created_at") or "",
                )
            )
            if matches:
                meta["linkage"] = {
                    "project_id": matches[0].get("project_id"),
                    "simulation_id": matches[0].get("simulation_id"),
                    "report_id": matches[0].get("report_id"),
                    "runner_status": matches[0].get("runner_status"),
                    "created_at": matches[0].get("created_at"),
                }
        except Exception:
            # Best-effort only; do not fail export.
            pass

    (out_dir / "export_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[OK] Exported graph to: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

