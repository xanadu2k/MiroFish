#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PROJECTS_DIR="${SCRIPT_DIR}/backend/uploads/projects"
SIMS_DIR="${SCRIPT_DIR}/backend/uploads/simulations"
REPORTS_DIR="${SCRIPT_DIR}/backend/uploads/reports"
GRAPHS_DIR="${SCRIPT_DIR}/backend/uploads/graphs"

echo "HTML-ize a project (best-effort, local files)"
echo

DEFAULT_PROJECT_ID="$(
  python3 - <<'PY' 2>/dev/null || true
import os
import pathlib

root = pathlib.Path("backend/uploads/projects")
if not root.exists():
    raise SystemExit(0)

def key(p: pathlib.Path):
    meta = p / "project.json"
    try:
        return meta.stat().st_mtime
    except Exception:
        try:
            return p.stat().st_mtime
        except Exception:
            return 0

projects = [p for p in root.iterdir() if p.is_dir() and p.name.startswith("proj_")]
projects.sort(key=key, reverse=True)
if projects:
    print(projects[0].name)
PY
)"

if [[ -n "${DEFAULT_PROJECT_ID}" ]]; then
  read -r -p "Enter project_id (default ${DEFAULT_PROJECT_ID}): " PROJECT_ID_INPUT
  PROJECT_ID="${PROJECT_ID_INPUT:-$DEFAULT_PROJECT_ID}"
else
  read -r -p "Enter project_id (e.g. proj_f9cb08844f4d): " PROJECT_ID
fi

if [[ -z "${PROJECT_ID}" ]]; then
  echo "Error: project_id cannot be empty."
  exit 1
fi

echo
echo "Project: ${PROJECT_ID}"
echo

if [[ ! -d "${PROJECTS_DIR}/${PROJECT_ID}" ]]; then
  echo "Error: project directory not found: ${PROJECTS_DIR}/${PROJECT_ID}"
  exit 1
fi

PY_OUTPUT="$(PROJECT_ID="${PROJECT_ID}" python3 - <<'PY'
import json
import os
import pathlib

project_id = os.environ["PROJECT_ID"]
root = pathlib.Path(".")
sims_dir = root / "backend/uploads/simulations"
reports_dir = root / "backend/uploads/reports"

sim_ids = []
if sims_dir.exists():
    for sim_dir in sims_dir.iterdir():
        if not sim_dir.is_dir() or not sim_dir.name.startswith("sim_"):
            continue
        state = sim_dir / "state.json"
        if not state.exists():
            continue
        try:
            data = json.loads(state.read_text("utf-8"))
        except Exception:
            continue
        if data.get("project_id") == project_id:
            sim_ids.append(sim_dir.name)

report_ids = []
if reports_dir.exists():
    for rep_dir in reports_dir.iterdir():
        if not rep_dir.is_dir() or not rep_dir.name.startswith("report_"):
            continue
        meta = rep_dir / "meta.json"
        if not meta.exists():
            continue
        try:
            m = json.loads(meta.read_text("utf-8"))
        except Exception:
            continue
        if m.get("simulation_id") in set(sim_ids):
            report_ids.append(rep_dir.name)

print(json.dumps({"sim_ids": sim_ids, "report_ids": report_ids}, ensure_ascii=False))
PY
)"

python3 - <<PY
import json
data=json.loads('''${PY_OUTPUT}''')
print("Detected:")
print(f"  simulations: {len(data.get('sim_ids') or [])}")
for s in data.get("sim_ids") or []:
    print(f"    - {s}")
print(f"  reports: {len(data.get('report_ids') or [])}")
for r in data.get("report_ids") or []:
    print(f"    - {r}")
PY

SIM_IDS="$(python3 - <<PY
import json
data=json.loads('''${PY_OUTPUT}''')
print("\\n".join(data.get("sim_ids") or []))
PY
)"

REPORT_IDS="$(python3 - <<PY
import json
data=json.loads('''${PY_OUTPUT}''')
print("\\n".join(data.get("report_ids") or []))
PY
)"

HUB_DIR="${SCRIPT_DIR}/backend/uploads/html_review/${PROJECT_ID}"
MANIFEST_PATH="${HUB_DIR}/manifest.tsv"
mkdir -p "${HUB_DIR}"
: > "${MANIFEST_PATH}"

record_artifact() {
  local label="$1"
  local src="$2"
  local rel="$3"
  echo "${label}"$'\t'"${rel}" >> "${MANIFEST_PATH}"
}

copy_to_hub() {
  local src="$1"
  local rel="$2"
  local dst="${HUB_DIR}/${rel}"
  mkdir -p "$(dirname "${dst}")"
  cp "${src}" "${dst}"
}

render_json_html() {
  local input_json="$1"
  local output_html="$2"
  local title="$3"
  python3 - "${input_json}" "${output_html}" "${title}" <<'PY'
import html
import json
import os
import pathlib
import sys

in_path = pathlib.Path(sys.argv[1])
out_path = pathlib.Path(sys.argv[2])
title = sys.argv[3]

try:
    data = json.loads(in_path.read_text("utf-8"))
except Exception as e:
    data = {"_error": f"Failed to parse JSON: {e}"}

pretty = json.dumps(data, ensure_ascii=False, indent=2)

doc = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>{html.escape(title)}</title>
  <style>
    :root {{ --bg:#0b1020; --panel:#101a33; --text:#e7ecff; --muted:#9aa7d8; --border:#24335f; }}
    body {{ margin:0; background:var(--bg); color:var(--text); font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; }}
    .top {{ position: sticky; top:0; background: rgba(11,16,32,0.92); border-bottom: 1px solid var(--border); padding: 12px 16px; }}
    .top h1 {{ margin:0; font-size:16px; }}
    .top .sub {{ margin-top:6px; font-size:12px; color:var(--muted); }}
    .wrap {{ max-width: 1100px; margin: 0 auto; padding: 16px; }}
    pre {{ margin:0; white-space: pre-wrap; word-break: break-word; background: var(--panel); border:1px solid var(--border); border-radius:10px; padding:12px; line-height:1.45; font-size:12px; }}
  </style>
</head>
<body>
  <div class="top">
    <h1>{html.escape(title)}</h1>
    <div class="sub">{html.escape(str(in_path))}</div>
  </div>
  <div class="wrap"><pre>{html.escape(pretty)}</pre></div>
</body>
</html>
"""
out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(doc, encoding="utf-8")
PY
}

echo
echo "Rendering project-level JSON -> HTML"
PROJECT_JSON="${PROJECTS_DIR}/${PROJECT_ID}/project.json"
if [[ -f "${PROJECT_JSON}" ]]; then
  PROJECT_HTML="${PROJECTS_DIR}/${PROJECT_ID}/project.html"
  render_json_html "${PROJECT_JSON}" "${PROJECT_HTML}" "${PROJECT_ID} / project.json"
  REL="projects/${PROJECT_ID}/project.html"
  copy_to_hub "${PROJECT_HTML}" "${REL}"
  record_artifact "project_meta" "${PROJECT_HTML}" "${REL}"
  echo "  OK  ${PROJECT_HTML}"
fi

echo
echo "Rendering simulation JSON / actions -> HTML"
if [[ -z "${SIM_IDS}" ]]; then
  echo "(no simulations found for this project)"
else
  while IFS= read -r SIM_ID; do
    [[ -z "${SIM_ID}" ]] && continue

    for NAME in state run_state simulation_config reddit_profiles; do
      IN_JSON="${SIMS_DIR}/${SIM_ID}/${NAME}.json"
      OUT_HTML="${SIMS_DIR}/${SIM_ID}/${NAME}.html"
      if [[ -f "${IN_JSON}" ]]; then
        render_json_html "${IN_JSON}" "${OUT_HTML}" "${SIM_ID} / ${NAME}.json"
        REL="simulations/${SIM_ID}/${NAME}.html"
        copy_to_hub "${OUT_HTML}" "${REL}"
        record_artifact "sim_json" "${OUT_HTML}" "${REL}"
        echo "  OK  ${OUT_HTML}"
      fi
    done

    for PLATFORM in twitter reddit; do
      IN_PATH="${SIMS_DIR}/${SIM_ID}/${PLATFORM}/actions.jsonl"
      OUT_PATH="${SIMS_DIR}/${SIM_ID}/${PLATFORM}/actions.html"
      if [[ -f "${IN_PATH}" ]]; then
        python3 "${SCRIPT_DIR}/backend/scripts/render_sim_actions_html.py" \
          --input "${IN_PATH}" \
          --output "${OUT_PATH}" \
          --title "${SIM_ID} / ${PLATFORM} 对话记录" \
          --subtitle "从 actions.jsonl 渲染（聊天视图）"
        REL="simulations/${SIM_ID}/${PLATFORM}/actions.html"
        copy_to_hub "${OUT_PATH}" "${REL}"
        record_artifact "sim_actions" "${OUT_PATH}" "${REL}"
        echo "  OK  ${OUT_PATH}"
      fi
    done
  done <<< "${SIM_IDS}"
fi

echo
echo "Rendering report JSON / logs -> HTML"
if [[ -z "${REPORT_IDS}" ]]; then
  echo "(no reports found for this project)"
else
  while IFS= read -r REPORT_ID; do
    [[ -z "${REPORT_ID}" ]] && continue
    for NAME in meta progress; do
      IN_JSON="${REPORTS_DIR}/${REPORT_ID}/${NAME}.json"
      OUT_HTML="${REPORTS_DIR}/${REPORT_ID}/${NAME}.html"
      if [[ -f "${IN_JSON}" ]]; then
        render_json_html "${IN_JSON}" "${OUT_HTML}" "${REPORT_ID} / ${NAME}.json"
        REL="reports/${REPORT_ID}/${NAME}.html"
        copy_to_hub "${OUT_HTML}" "${REL}"
        record_artifact "report_json" "${OUT_HTML}" "${REL}"
        echo "  OK  ${OUT_HTML}"
      fi
    done

    IN_PATH="${REPORTS_DIR}/${REPORT_ID}/agent_log.jsonl"
    OUT_PATH="${REPORTS_DIR}/${REPORT_ID}/agent_log.html"
    if [[ -f "${IN_PATH}" ]]; then
      python3 "${SCRIPT_DIR}/backend/scripts/render_agent_log_html.py" \
        --input "${IN_PATH}" \
        --output "${OUT_PATH}"
      REL="reports/${REPORT_ID}/agent_log.html"
      copy_to_hub "${OUT_PATH}" "${REL}"
      record_artifact "report_agent_log" "${OUT_PATH}" "${REL}"
      echo "  OK  ${OUT_PATH}"
    fi
  done <<< "${REPORT_IDS}"
fi

echo
echo "Rendering graph metadata JSON -> HTML (if available)"
if [[ -n "${SIM_IDS}" ]]; then
  while IFS= read -r SIM_ID; do
    [[ -z "${SIM_ID}" ]] && continue
    GRAPH_ID="$(python3 - "${SIMS_DIR}/${SIM_ID}/state.json" <<'PY'
import json
import pathlib
import sys
p = pathlib.Path(sys.argv[1])
if not p.exists():
    raise SystemExit(0)
try:
    d = json.loads(p.read_text("utf-8"))
except Exception:
    raise SystemExit(0)
gid = d.get("graph_id") or ""
if gid:
    print(gid)
PY
)"
    [[ -z "${GRAPH_ID}" ]] && continue
    for NAME in export_meta graph; do
      IN_JSON="${GRAPHS_DIR}/${GRAPH_ID}/${NAME}.json"
      OUT_HTML="${GRAPHS_DIR}/${GRAPH_ID}/${NAME}.html"
      if [[ -f "${IN_JSON}" ]]; then
        render_json_html "${IN_JSON}" "${OUT_HTML}" "${GRAPH_ID} / ${NAME}.json"
        REL="graphs/${GRAPH_ID}/${NAME}.html"
        copy_to_hub "${OUT_HTML}" "${REL}"
        record_artifact "graph_json" "${OUT_HTML}" "${REL}"
        echo "  OK  ${OUT_HTML}"
      fi
    done
  done <<< "${SIM_IDS}"
fi

echo
echo "Building hub index"
python3 - "${PROJECT_ID}" "${HUB_DIR}" "${MANIFEST_PATH}" <<'PY'
import html
import pathlib
import sys

project_id = sys.argv[1]
hub_dir = pathlib.Path(sys.argv[2])
manifest = pathlib.Path(sys.argv[3])

items = []
if manifest.exists():
    for line in manifest.read_text("utf-8").splitlines():
        if not line.strip():
            continue
        parts = line.split("\t", 1)
        if len(parts) != 2:
            continue
        label, rel = parts
        items.append((label, rel))

rows = []
for label, rel in items:
    rows.append(f"<tr><td>{html.escape(label)}</td><td><a href='{html.escape(rel)}'>{html.escape(rel)}</a></td></tr>")

doc = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>{html.escape(project_id)} / HTML Review Hub</title>
  <style>
    :root {{ --bg:#0b1020; --panel:#101a33; --text:#e7ecff; --muted:#9aa7d8; --border:#24335f; }}
    body {{ margin:0; background:var(--bg); color:var(--text); font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; }}
    .wrap {{ max-width: 980px; margin: 0 auto; padding: 18px; }}
    h1 {{ margin:0 0 8px 0; font-size: 20px; }}
    .sub {{ color: var(--muted); margin-bottom: 14px; }}
    table {{ width:100%; border-collapse: collapse; background:var(--panel); border:1px solid var(--border); border-radius: 10px; overflow: hidden; }}
    th, td {{ text-align:left; padding:10px 12px; border-bottom:1px solid var(--border); font-size: 13px; vertical-align: top; }}
    tr:last-child td {{ border-bottom: none; }}
    a {{ color:#9bc2ff; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
  </style>
</head>
<body>
  <div class="wrap">
    <h1>{html.escape(project_id)} / HTML Review Hub</h1>
    <div class="sub">集中浏览入口（由 mirofish_htmlize_project.sh 自动生成）</div>
    <table>
      <thead><tr><th>type</th><th>file</th></tr></thead>
      <tbody>
        {''.join(rows)}
      </tbody>
    </table>
  </div>
</body>
</html>
"""
(hub_dir / "index.html").write_text(doc, encoding="utf-8")
PY

echo "Done."
echo "Hub: ${HUB_DIR}"

