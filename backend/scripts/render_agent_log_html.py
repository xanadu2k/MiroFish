#!/usr/bin/env python3
"""
Render report agent_log.jsonl to a chat-like HTML file.

Usage:
  python backend/scripts/render_agent_log_html.py \
    --input backend/uploads/reports/<report_id>/agent_log.jsonl \
    --output backend/uploads/reports/<report_id>/agent_log.html
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
from typing import Any, Dict, Iterable, List, Optional, Tuple


def _safe_str(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    return json.dumps(v, ensure_ascii=False, indent=2)


def _parse_ts(ts: str) -> str:
    # Keep original if parsing fails
    try:
        return dt.datetime.fromisoformat(ts).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ts


def _read_jsonl(path: str) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError:
                # Keep raw line as a fallback
                items.append(
                    {
                        "timestamp": "",
                        "elapsed_seconds": None,
                        "action": "raw_line",
                        "stage": "",
                        "section_title": None,
                        "section_index": None,
                        "details": {"raw": line},
                    }
                )
    return items


def _classify(action: str) -> Tuple[str, str]:
    """
    Returns (speaker_label, bubble_class)
    """
    action = (action or "").lower()
    if action in {"tool_call", "tool_result"}:
        return ("工具", "tool")
    if action in {"llm_response", "react_thought", "section_content"}:
        return ("智能体", "agent")
    if action.endswith("start") or action.endswith("complete") or action in {"report_start", "planning_start", "planning_complete"}:
        return ("系统", "system")
    return ("系统", "system")


def _render_details(details: Dict[str, Any], bubble_class: str) -> str:
    # Prefer a "message" as compact summary
    message = _safe_str(details.get("message")) if isinstance(details, dict) else ""

    # For tool events, highlight tool name if present
    tool_name = ""
    if isinstance(details, dict):
        tool_name = _safe_str(details.get("tool_name") or details.get("toolName") or details.get("name"))

    # Extract main payload text candidates (may be large)
    payload_parts: List[Tuple[str, str]] = []
    if isinstance(details, dict):
        for k in ("response", "thought", "result", "content", "outline", "parameters", "context", "raw"):
            if k in details and details[k] is not None and details[k] != "":
                payload_parts.append((k, _safe_str(details[k])))

    # Build HTML: summary + collapsible payload
    summary_bits: List[str] = []
    if tool_name and bubble_class == "tool":
        summary_bits.append(f"<span class='badge'>tool</span> <b>{html.escape(tool_name)}</b>")
    if message:
        summary_bits.append(html.escape(message))

    summary_html = "<div class='summary'>" + " · ".join(summary_bits) + "</div>" if summary_bits else ""

    # Render payload as collapsible blocks to avoid huge page
    blocks: List[str] = []
    for key, text in payload_parts:
        escaped = html.escape(text)
        # Keep long payloads collapsed by default
        open_attr = "" if len(text) > 800 else " open"
        blocks.append(
            f"<details{open_attr}><summary>{html.escape(key)}</summary><pre>{escaped}</pre></details>"
        )
    payload_html = "<div class='payload'>" + "".join(blocks) + "</div>" if blocks else ""

    return summary_html + payload_html


def render_html(items: List[Dict[str, Any]], title: str) -> str:
    rows: List[str] = []
    for it in items:
        ts = _parse_ts(_safe_str(it.get("timestamp")))
        elapsed = it.get("elapsed_seconds")
        action = _safe_str(it.get("action"))
        stage = _safe_str(it.get("stage"))
        section_title = _safe_str(it.get("section_title"))
        section_index = it.get("section_index")
        details = it.get("details") or {}

        speaker, bubble_class = _classify(action)
        header_bits: List[str] = []
        if ts:
            header_bits.append(ts)
        if elapsed is not None:
            header_bits.append(f"+{elapsed}s")
        if stage:
            header_bits.append(stage)
        if section_title:
            idx = f"{int(section_index):02d}" if isinstance(section_index, int) else ""
            header_bits.append(f"第{idx}章 {section_title}".strip())

        header = " | ".join(header_bits)

        rows.append(
            "\n".join(
                [
                    f"<div class='row {bubble_class}'>",
                    f"  <div class='meta'><span class='speaker'>{html.escape(speaker)}</span><span class='header'>{html.escape(header)}</span><span class='action'>{html.escape(action)}</span></div>",
                    f"  <div class='bubble'>{_render_details(details, bubble_class)}</div>",
                    f"</div>",
                ]
            )
        )

    css = """
    :root { --bg:#0b1020; --panel:#101a33; --text:#e7ecff; --muted:#9aa7d8; --border:#24335f;
            --system:#1b2a4f; --agent:#143a2a; --tool:#3a2a14; }
    body { margin:0; font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial, "PingFang SC", "Hiragino Sans GB", "Microsoft Yahei", sans-serif;
           background: var(--bg); color: var(--text); }
    .top { position: sticky; top:0; background: rgba(11,16,32,0.9); backdrop-filter: blur(8px);
           border-bottom: 1px solid var(--border); padding: 14px 18px; z-index: 10; }
    .top h1 { margin:0; font-size: 16px; }
    .top .hint { margin-top:6px; color: var(--muted); font-size: 12px; }
    .wrap { max-width: 1100px; margin: 0 auto; padding: 18px; }
    .row { margin: 14px 0; padding: 12px; border: 1px solid var(--border); border-radius: 12px; background: var(--panel); }
    .row.system { border-left: 6px solid #6ea8ff; }
    .row.agent  { border-left: 6px solid #65d9a6; }
    .row.tool   { border-left: 6px solid #ffcd6e; }
    .meta { display:flex; gap: 10px; align-items: baseline; flex-wrap: wrap; color: var(--muted); font-size: 12px; }
    .speaker { padding: 2px 8px; border-radius: 999px; border:1px solid var(--border); color: var(--text); font-weight: 600; }
    .action { margin-left: auto; opacity: 0.9; }
    .bubble { margin-top: 10px; }
    .summary { color: var(--text); font-size: 13px; line-height: 1.45; }
    .badge { display:inline-block; padding: 1px 6px; border-radius: 6px; border:1px solid var(--border); color: var(--muted); font-size: 11px; }
    details { margin-top: 8px; border: 1px solid var(--border); border-radius: 10px; overflow: hidden; background: rgba(255,255,255,0.02); }
    summary { cursor: pointer; padding: 8px 10px; color: var(--muted); user-select:none; }
    pre { margin:0; padding: 10px; overflow: auto; background: rgba(0,0,0,0.25); color: var(--text); font-size: 12px; line-height: 1.4; }
    a { color: #9bc2ff; }
    """

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>{html.escape(title)}</title>
  <style>{css}</style>
</head>
<body>
  <div class="top">
    <h1>{html.escape(title)}</h1>
    <div class="hint">提示：每条记录按 action 分类显示；长字段默认折叠，可展开查看完整内容。</div>
  </div>
  <div class="wrap">
    {''.join(rows)}
  </div>
</body>
</html>
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="agent_log.jsonl path")
    ap.add_argument("--output", required=True, help="output html path")
    args = ap.parse_args()

    items = _read_jsonl(args.input)
    title = os.path.basename(args.input).replace(".jsonl", "") + "（聊天记录视图）"
    out = render_html(items, title=title)

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

