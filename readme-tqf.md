# TQF 本地扩展脚本说明

这个文档记录了本项目中 **TQF 定制新增** 的脚本，便于后续重复使用、交接和排错。

---

## 快速上手（30 秒）

首次安装（仅一次）：

```bash
./ops/launchd/install.sh
```

日常使用（任选其一）：

```bash
./mirofish_auto_archive_rounds.sh
./mirofish_export_graph.sh
```

健康检查（前后端是否在线）：

```bash
curl -s -o /dev/null -w "frontend:%{http_code}\n" http://127.0.0.1:5555/
curl -s -o /dev/null -w "backend:%{http_code}\n" "http://127.0.0.1:5556/api/simulation/history?limit=1"
```

看实时日志：

```bash
tail -f /tmp/mirofish-launchd.out.log /tmp/mirofish-launchd.err.log
```

停止服务（可选）：

```bash
launchctl bootout "gui/$(id -u)/com.mirofish.dev" || true
```

---

## 零、打火机能力（自动拉起服务）

这两条 `.sh` 都已经具备“打火机”能力：

- 会先检测后端 `5556` 是否可用
- 若不可用，会提示是否自动执行 `npm run dev`
- 你确认后会后台启动服务并等待 ready，再继续后续流程

这意味着你日常可以只记两条命令：

- `./mirofish_auto_archive_rounds.sh`
- `./mirofish_export_graph.sh`

不需要先手动启动服务。

---

## 零点五、持续监控与保活（launchd，推荐）

如果你希望 **关闭终端窗口后服务仍持续运行**，并且在异常退出后 **自动重启**，可以使用本仓库新增的 `launchd` 常驻任务。

### 安装并启动（一次性）

在项目根目录执行：

```bash
./ops/launchd/install.sh
```

默认会把服务托管为 `LaunchAgent`（用户登录态），并将日志写入：

- `/tmp/mirofish-launchd.out.log`
- `/tmp/mirofish-launchd.err.log`

### 持续看日志（本机实时）

```bash
tail -f /tmp/mirofish-launchd.out.log /tmp/mirofish-launchd.err.log
```

### 查看是否仍在运行（本机）

```bash
launchctl print gui/$(id -u)/com.mirofish.dev
```

判定基准（建议）：

- 输出中看到 `state = running`：表示服务处于运行态
- 若不是 running，可执行一次：

```bash
launchctl kickstart -k "gui/$(id -u)/com.mirofish.dev"
```

### 查看端口/进程（本机）

```bash
lsof -nP -iTCP:5555 -sTCP:LISTEN
lsof -nP -iTCP:5556 -sTCP:LISTEN
ps -ax | egrep "vite --host|npm run dev|uv run python run.py" | egrep -v egrep
```

### 端口冲突处理（本机）

若 `5555/5556` 已被其他程序占用：

1. 先定位占用者：

```bash
lsof -nP -iTCP:5555 -sTCP:LISTEN
lsof -nP -iTCP:5556 -sTCP:LISTEN
```

2. 确认不是当前 MiroFish 实例后，再终止对应 PID（示例）：

```bash
kill <PID>
```

3. 重新拉起 launchd 任务：

```bash
launchctl kickstart -k "gui/$(id -u)/com.mirofish.dev"
```

### 健康检查（本机）

```bash
curl -s -o /dev/null -w "frontend:%{http_code}\n" http://127.0.0.1:5555/
curl -s -o /dev/null -w "backend:%{http_code}\n" "http://127.0.0.1:5556/api/simulation/history?limit=1"
```

### 停止/卸载（可选）

停止并移除 launchd 任务：

```bash
launchctl bootout "gui/$(id -u)/com.mirofish.dev" || true
rm -f "${HOME}/Library/LaunchAgents/com.mirofish.dev.plist"
```

---

## 一、脚本总览（根目录）

### 1) `mirofish_auto_archive_rounds.sh`

**作用**  
在仿真运行过程中，自动按轮次/状态变化做本地快照归档。

**对应 Python 脚本**  
`backend/scripts/auto_archive_rounds.py`

**适用场景**
- 仿真可能跑很久，希望过程可追溯
- 防止中途中断导致过程数据丢失
- 需要按轮次留痕对比

---

### 2) `mirofish_export_graph.sh`

**作用**  
把 Zep 上的 `mirofish_*` 图谱拉回本地，保存为可离线留存的快照。

**对应 Python 脚本**  
`backend/scripts/export_graph_snapshot.py`

**适用场景**
- 项目完结后做最终归档
- 需要把云端图谱落本地备份
- 需要做跨项目图谱对比

---

## 二、脚本详细说明

## A. 自动归档脚本

### 文件
- Shell: `mirofish_auto_archive_rounds.sh`
- Python: `backend/scripts/auto_archive_rounds.py`

### 启动方式
在项目根目录运行：

```bash
./mirofish_auto_archive_rounds.sh
```

### 交互行为
1. 先检测后端是否可用；不可用时提示自动拉起 `npm run dev`。
2. 询问轮询间隔（`ARCHIVE_INTERVAL_SECONDS`），默认 `5` 秒，回车即用默认。
3. 自动探测当前正在运行的 `simulation_id` 作为默认值（若探测到）。
4. 你可直接回车使用默认 `simulation_id`，也可手动输入其他 `sim_*`。
5. 若没有默认且你也留空，脚本会报错退出（避免无意义归档）。

### 输出目录
按 simulation_id 存放：

`backend/uploads/archives/<simulation_id>/`

目录下会出现类似：
- `start_...`
- `round_013_...`
- `round_014_...`
- `status_completed_...`
- `final_...`

### 每个快照包含内容（按存在情况拷贝）
- `run_state.json`
- `state.json`
- `simulation_config.json`
- `reddit_profiles.json`
- `twitter_profiles.csv`
- `simulation.log`
- `twitter/actions.jsonl`
- `reddit/actions.jsonl`
- `twitter_simulation.db`
- `reddit_simulation.db`

### 结束行为
当检测到仿真状态为 `completed / stopped / failed / idle` 时，脚本会自动做 final 快照并退出。

---

## B. 图谱导出脚本

### 文件
- Shell: `mirofish_export_graph.sh`
- Python: `backend/scripts/export_graph_snapshot.py`

### 启动方式
在项目根目录运行：

```bash
./mirofish_export_graph.sh
```

### 交互行为
1. 先检测后端是否可用；不可用时提示自动拉起 `npm run dev`。
2. 脚本会尝试从本地后端 history 自动给出默认 `graph_id`：
   - 优先 `runner_status=running`
   - 其次最新 `runner_status=completed`
3. 你可以回车使用默认值，或手动输入 Zep 控制台里的 `mirofish_*`。
4. 若留空则报错退出。

### 导出原理
通过本地后端 API 拉取图谱数据（无需脚本单独配置 Zep key）：

`GET /api/graph/data/<graph_id>`

默认后端地址：
`http://127.0.0.1:5556`

### 输出目录
按 graph_id 存放：

`backend/uploads/graphs/<graph_id>/`

包含文件：
- `graph.json`：图谱完整快照（nodes/edges）
- `export_meta.json`：导出时间、节点边数量、尽力关联到的 project/sim/report 信息

---

## 三、推荐工作流（实操）

1. 正常完成项目流程：  
`proj -> graph -> sim -> report`

2. 仿真开始后尽快启动自动归档：  
`./mirofish_auto_archive_rounds.sh`

3. 项目完成后导出图谱快照：  
`./mirofish_export_graph.sh`

4. 最终备份目录建议包含：
- `backend/uploads/simulations/<sim_id>/`
- `backend/uploads/archives/<sim_id>/`
- `backend/uploads/reports/<report_id>/`
- `backend/uploads/graphs/<graph_id>/`

---

## 四、ID 关系速记

- `proj_*`：项目容器（上传文件、需求、构图上下文）
- `mirofish_*`：Zep 图谱 ID
- `sim_*`：仿真实例 ID
- `report_*`：报告 ID

关系链：

`project (proj) -> graph (mirofish) -> simulation (sim) -> report (report)`

---

## 五、常见问题

### Q1: `mirofish_export_graph.sh` 为什么拿不到默认 graph_id？
- 通常是 history 里暂无 running/completed 记录（后端未启动已可自动拉起）。
- 处理：脚本会先尝试自动拉起服务；若仍无默认值，请手工输入 `mirofish_*`。

### Q2: 自动归档为什么没生成新轮次目录？
- 可能仿真轮次没有推进（卡住/已结束）。
- 先检查 `run_state.json` 的 `current_round` 和 `runner_status`。

### Q3: 可以只在项目结束后再导出图谱吗？
- 可以。  
- 若没开图谱写回，影响不大；若开了图谱写回，建议至少在完结后导出一次“最终快照”。

### Q4: 长任务（尤其报告生成）期间可以重启 backend 吗？
- 不建议。当前报告生成属于后台线程任务，重启 backend 可能导致进行中的报告任务中断。
- 建议在任务完成前仅做监控，不做重启；若任务停滞，优先新开一个 `report_id` 并行兜底。

---

## 六、你当前已新增的脚本清单（确认）

- `mirofish_auto_archive_rounds.sh`
- `mirofish_export_graph.sh`
- `backend/scripts/auto_archive_rounds.py`
- `backend/scripts/export_graph_snapshot.py`
- `ops/launchd/install.sh`
- `ops/launchd/run.sh`
- `ops/launchd/com.mirofish.dev.plist`

