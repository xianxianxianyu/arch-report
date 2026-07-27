# Ubuntu 迁移清单

## 刷机前

1. 确认当前自动化没有正在运行的任务。
2. 将整个 `portable-agent-architecture-radar` 文件夹复制到另一块磁盘或云端。
3. 同时保存根目录旁的压缩包；不要只保存 `index.html`。
4. 在 Linux、WSL 或 Git Bash 中用 `sha256sum -c SHA256SUMS.txt` 核对文件完整性。

## Ubuntu 恢复

1. 把文件夹放到一个长期不变的绝对路径，例如 `/home/<user>/research/agent-architecture-radar`。
2. 安装 Codex 后，以这个文件夹作为本地项目打开。
3. 阅读 `AUTOMATION_PROMPT.md`，将 Ubuntu 模板中的 `<PROJECT_DIR>` 替换为真实绝对路径。
4. 新建一个本地自动化：周一至周五每 4 小时、`gpt-5.6-sol`、高推理强度；如果需要周末运行，应明确改为每天。
5. 第一次自动运行前，执行：

   ```bash
   python3 tools/build_index.py --check
   ```

6. 每次产生新报告后执行：

   ```bash
   python3 tools/build_index.py
   ```

## 为什么要一起迁移状态

`reports/` 只是已经写出的结论。真正保证 loop 不重复、不把旧文章重新发布的，是：

- `state/item-cache.json`：候选事实源、评分和拒绝原因；
- `state/seen-items.json`：跨轮去重；
- `state/run-log.jsonl`：每轮搜索、筛选、发布与失败记录。

如果只迁移 Markdown，系统能阅读旧报告，但下一轮无法可靠判断哪些候选已经审阅或发布。

## 并发与恢复边界

- 不要让 Windows 和 Ubuntu 同时写同一份状态。
- 报告与状态复制必须来自同一个时间点。
- 如果发现 `queued` 条目，先按 `CODEX_TASK.md` 的恢复规则处理，不要直接标记为已发布。
- `index.html` 是可重建视图；`reports/` 和 `state/` 才是不可丢失的数据。
