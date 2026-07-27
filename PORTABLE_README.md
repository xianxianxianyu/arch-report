# Portable Agent Architecture Radar

这是 Agent 服务器架构雷达的可搬运快照，可直接复制到 Ubuntu。它同时保留研究报告、自动化 prompt、质量规则、去重状态和离线文章首页。

## 直接使用

- 双击或用浏览器打开 `index.html`，按标题、故障、来源或主题搜索 45 篇已收录文章。
- 阅读 `AUTOMATION_PROMPT.md` 恢复 loop。
- 按 `MIGRATION.md` 完成 Ubuntu 迁移。
- 新报告产生后运行 `python3 tools/build_index.py` 重建首页。

## 目录

```text
portable-agent-architecture-radar/
├── index.html                 # 离线文章级首页
├── AUTOMATION_PROMPT.md       # 当前 prompt 与 Ubuntu 模板
├── CODEX_TASK.md              # 每轮质量门槛与原子发布流程
├── README.md                  # 雷达项目原始说明（供 loop 读取）
├── PORTABLE_README.md         # 本说明
├── MIGRATION.md               # 刷机与恢复清单
├── index.md                   # 原始轮次索引
├── reports/                   # 9 轮、45 篇 Markdown 原件
├── state/                     # 候选池、去重记录、运行日志
├── tools/build_index.py       # 纯标准库首页生成与验证器
└── SHA256SUMS.txt             # 完整性校验清单
```

## 数据边界

离线首页不加载远程字体、脚本或样式；搜索和筛选全部在浏览器本地完成。首页是派生视图，可以重建；迁移时必须优先保护 `reports/`、`state/`、`CODEX_TASK.md` 和 `AUTOMATION_PROMPT.md`。
