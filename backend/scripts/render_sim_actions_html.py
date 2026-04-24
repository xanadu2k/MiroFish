#!/usr/bin/env python3
"""Render simulation actions.jsonl to conversation-style HTML."""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
from typing import Any, Dict, List, Optional


def _safe(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    return json.dumps(v, ensure_ascii=False, indent=2)


def _fmt_ts(ts: str) -> str:
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
                items.append({"event_type": "raw", "timestamp": "", "raw": line})
    return items


def _shorten(text: str, max_len: int = 180) -> str:
    text = (text or "").strip().replace("\n", " ")
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "..."


def _action_label(action_type: str) -> str:
    mapping = {
        "CREATE_POST": "发言",
        "QUOTE_POST": "回复",
        "REPOST": "转发",
        "LIKE_POST": "点赞",
        "FOLLOW": "关注",
    }
    return mapping.get(action_type, action_type or "动作")


def _build_conversation(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    current_round: Optional[int] = None
    round_has_message = False

    for ev in events:
        et = ev.get("event_type")
        if et == "simulation_start":
            rows.append(
                {
                    "kind": "system",
                    "timestamp": ev.get("timestamp", ""),
                    "text": "模拟开始",
                }
            )
            continue
        if et == "simulation_end":
            rows.append(
                {
                    "kind": "system",
                    "timestamp": ev.get("timestamp", ""),
                    "text": f"模拟结束 · 总动作 {ev.get('total_actions', 0)}",
                }
            )
            continue
        if et == "round_start":
            current_round = ev.get("round")
            round_has_message = False
            continue
        if et == "round_end":
            current_round = ev.get("round")
            continue
        if et:
            continue

        action_type = _safe(ev.get("action_type"))
        args = ev.get("action_args") or {}
        agent = _safe(ev.get("agent_name")) or "Unknown"
        ts = _safe(ev.get("timestamp"))
        rnd = ev.get("round", current_round)

        if not round_has_message:
            rows.append(
                {
                    "kind": "divider",
                    "timestamp": ts,
                    "round": rnd,
                    "text": f"Round {rnd}" if isinstance(rnd, int) else "Round",
                }
            )
            round_has_message = True

        # Lightweight reaction rows.
        if action_type == "LIKE_POST":
            target = _safe(args.get("post_author_name"))
            snippet = _shorten(_safe(args.get("post_content")))
            rows.append(
                {
                    "kind": "reaction",
                    "timestamp": ts,
                    "agent_name": agent,
                    "action_type": action_type,
                    "text": f"{agent} 点赞了 @{target}",
                    "context": snippet,
                }
            )
            continue

        if action_type == "FOLLOW":
            target = _safe(args.get("target_user_name"))
            rows.append(
                {
                    "kind": "reaction",
                    "timestamp": ts,
                    "agent_name": agent,
                    "action_type": action_type,
                    "text": f"{agent} 关注了 @{target}",
                    "context": "",
                }
            )
            continue

        message = ""
        quote_context = ""
        if action_type == "CREATE_POST":
            message = _safe(args.get("content") or args.get("text") or args.get("message"))
        elif action_type == "QUOTE_POST":
            target = _safe(args.get("original_author_name"))
            message = _safe(args.get("quote_content") or args.get("content"))
            quote_context = f"回复 @{target}：{_shorten(_safe(args.get('original_content')))}"
        elif action_type == "REPOST":
            target = _safe(args.get("original_author_name"))
            quote_context = f"转发 @{target}：{_shorten(_safe(args.get('original_content')))}"
            message = _safe(args.get("comment") or "")
        else:
            message = _safe(args.get("content") or args.get("text") or args.get("message"))
            if not message:
                message = _safe(ev.get("result"))

        rows.append(
            {
                "kind": "message",
                "timestamp": ts,
                "round": rnd,
                "agent_name": agent,
                "action_type": action_type,
                "action_label": _action_label(action_type),
                "quote_context": quote_context,
                "text": message or f"[{action_type}]",
                "success": ev.get("success", True),
            }
        )
    return rows


def render_html(messages: List[Dict[str, Any]], title: str, subtitle: str) -> str:
    rows: List[str] = []
    for m in messages:
        kind = m["kind"]
        ts = _fmt_ts(_safe(m.get("timestamp")))
        if kind == "system":
            rows.append(
                f"""<div class='row system'>
  <div class='sys'>{html.escape(ts)} · {html.escape(_safe(m.get('text')))}</div>
</div>"""
            )
            continue
        if kind == "divider":
            rows.append(
                f"""<div class='row divider'>
  <div class='divline'>{html.escape(ts)} · {html.escape(_safe(m.get('text')))}</div>
</div>"""
            )
            continue
        if kind == "reaction":
            context = _safe(m.get("context"))
            context_html = (
                f"<div class='react-context'>{html.escape(context)}</div>" if context else ""
            )
            rows.append(
                f"""<div class='row reaction'>
  <div class='react'>{html.escape(_safe(m.get('text')))}</div>
  {context_html}
</div>"""
            )
            continue

        agent = _safe(m.get("agent_name"))
        action_type = _safe(m.get("action_label") or m.get("action_type"))
        success = m.get("success", True)
        status_badge = "OK" if success else "FAIL"
        badge_class = "ok" if success else "fail"
        text = html.escape(_safe(m.get("text")))
        quote_context = _safe(m.get("quote_context"))
        quote_html = (
            f"<div class='quote'>{html.escape(quote_context)}</div>" if quote_context else ""
        )
        header = " | ".join([x for x in [ts, action_type] if x])

        rows.append(
            f"""<div class='row user'>
  <div class='meta'>
    <span class='name'>{html.escape(agent)}</span>
    <span class='badge {badge_class}'>{status_badge}</span>
    <span class='header'>{html.escape(header)}</span>
  </div>
  <div class='bubble'>{quote_html}<pre>{text}</pre></div>
</div>"""
        )

    css = """
    :root { --bg:#0b1020; --panel:#101a33; --text:#e7ecff; --muted:#9aa7d8; --border:#24335f; }
    body { margin:0; font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial, "PingFang SC", "Hiragino Sans GB", "Microsoft Yahei", sans-serif;
           background: var(--bg); color: var(--text); }
    .top { position: sticky; top:0; background: rgba(11,16,32,0.92); backdrop-filter: blur(8px);
           border-bottom: 1px solid var(--border); padding: 14px 18px; z-index: 10; }
    .top h1 { margin:0; font-size: 16px; }
    .top .sub { margin-top:6px; color: var(--muted); font-size: 12px; }
    .wrap { max-width: 980px; margin: 0 auto; padding: 18px; }
    .row { margin: 10px 0; }
    .row.system { display:flex; justify-content:center; }
    .row.system .sys { color: var(--muted); font-size: 12px; border:1px dashed var(--border); padding: 6px 10px; border-radius: 999px; }
    .row.divider { display:flex; justify-content:center; margin: 16px 0 8px; }
    .row.divider .divline { color: var(--muted); font-size: 12px; padding: 4px 10px; border-radius:999px; background: rgba(255,255,255,0.04); border: 1px solid var(--border); }
    .row.reaction { display:flex; flex-direction:column; gap:6px; align-items:center; color: var(--muted); font-size:12px; }
    .react { padding:4px 10px; border-radius: 999px; background: rgba(255,255,255,0.04); border:1px solid var(--border); }
    .react-context { max-width: 900px; font-size: 12px; color: var(--muted); opacity: .95; }
    .row.user { border: 1px solid var(--border); border-radius: 12px; background: var(--panel); padding: 12px; }
    .meta { display:flex; gap:10px; align-items: baseline; flex-wrap: wrap; color: var(--muted); font-size: 12px; }
    .name { color: var(--text); font-weight: 700; }
    .badge { padding: 1px 8px; border-radius: 999px; border:1px solid var(--border); font-size: 11px; }
    .badge.ok { color:#65d9a6; }
    .badge.fail { color:#ff8fa3; }
    .bubble { margin-top: 10px; }
    .quote { margin-bottom:8px; border-left: 3px solid #3b5ea7; background: rgba(66,113,210,0.12); padding: 8px 10px; border-radius: 6px; font-size: 12px; color: #b9cdfa; white-space: pre-wrap; }
    pre { margin:0; white-space: pre-wrap; word-break: break-word; font-size: 13px; line-height: 1.5;
          background: rgba(0,0,0,0.22); padding: 10px; border-radius: 10px; border:1px solid rgba(255,255,255,0.06); }
    """

    rows_html = "\n".join(rows)

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
    <div class="sub">{html.escape(subtitle)}</div>
  </div>
  <div class="wrap">
    {rows_html}
  </div>
</body>
</html>
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--title", default="")
    ap.add_argument("--subtitle", default="")
    args = ap.parse_args()

    events = _read_jsonl(args.input)
    messages = _build_conversation(events)

    title = args.title or os.path.basename(args.input).replace(".jsonl", "")
    subtitle = args.subtitle or args.input
    out = render_html(messages, title=title, subtitle=subtitle)

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

