# 每 4 小时 Agent 服务器架构雷达

每次运行先完整阅读本文件、`README.md`、`state/item-cache.json`、`state/seen-items.json`、`state/run-log.jsonl` 和 `index.md`，然后只执行一轮。周期由 Codex 自动化负责；本任务不得创建或修改其他自动化。

## 目标与成功标准

- 研究范围：能直接用于 Agent 服务器应用落地的系统/软件架构，包括 runtime、orchestrator、scheduler、tool gateway、identity、multi-tenancy、memory/state、artifact、client-server protocol、durable execution、observability、security、capacity 和 failure recovery。
- 时间窗口：以本轮开始时间为上界，向前滚动 30 个自然日。使用原始发布日期或可证明的实质性更新日期；抓取日期、聚合站更新时间和普通 SEO 更新不算。
- 每轮目标 5 篇此前未发布的 blog 或 paper。质量门槛高于数量；不足 5 篇时如实输出，不得用重复、旧文、营销稿或弱相关内容补齐。
- 每篇必须形成“具体故障 → 架构机制 → 落地设计 → 可验证不变量”的闭环，不能只翻译摘要或罗列产品功能。
- 报告使用中文，明确区分“来源事实/作者主张”和“本项目工程推断”。

## 来源门槛：“师出有名”

候选必须满足以下至少一类：

### E 类：权威工程来源

- 头部科技公司、云厂商、著名基础设施项目或其官方工程/研究博客；
- 页面有明确作者、原始发布日期和可检查的组件图、协议、代码、配置、实验或生产案例；
- 聚合站、转载、SEO 内容农场和没有技术证据的发布稿只能用于发现，不能入选。

### R 类：可信研究来源

- 已被正式 proceedings、出版社、会议官网或 OpenReview 决定页确认接收；或
- 作者来自知名研究机构/工业实验室，或包含可由官方机构页核验的公认研究者；
- arXiv 本身只证明预印本存在，不证明同行评审或机构声誉。预印本必须明确标注，不能写成已接收论文。

## 发现范围

优先查：

- Papers：arXiv 的 cs.DC、cs.OS、cs.SE、cs.CR、cs.AI、cs.MA、cs.HC，以及 ACM、IEEE、USENIX、OpenReview 和正式 proceedings。
- Blogs：OpenAI、Anthropic、Google/DeepMind/Google Cloud、Microsoft Research/Azure/Foundry、AWS、Meta、NVIDIA、Cloudflare、IBM Research、Temporal、LangChain/LangGraph 等官方工程或研究站点。
- 检索主题：agent runtime/server/serving、durable execution、checkpoint/resume、workflow state machine、tool discovery/gateway、identity delegation、multi-tenant isolation、memory lifecycle、artifact/completion contract、client-agent protocol、observability、sandbox、capacity、backpressure、failure recovery。

先用搜索引擎发现，再打开原始页面核验。技术结论只引用论文、正式文档、官方工程博客、官方代码仓库等一手来源。

## 去重与候选池

`state/item-cache.json` 是候选池唯一事实源。每个实际审阅过的候选都写入池中，即使最终拒绝。

规范化和去重优先级：

1. DOI / arXiv ID / OpenReview forum ID；
2. canonical URL（去除跟踪参数、片段和无意义尾斜杠）；
3. 小写、去标点和空白归一后的标题指纹；
4. 同一设计的论文、官方博客和产品公告形成一个 `topic_cluster`，默认只选证据最强的一篇，其他来源作为补充证据。

旧记录不能因以前是 eligible 就直接进入新报告；若来源发生实质性版本变化，重新核验并保存版本历史。已经发布过的条目不重复发布。

## 评分与硬门槛

每项满分 100：

| 维度 | 分值 | 判定 |
|---|---:|---|
| 来源可信度 | 25 | E/R 类证据是否明确、原始日期是否可核验 |
| 问题具体性 | 20 | 是否描述可观察故障、约束或失败模式 |
| 架构深度 | 25 | 是否给出组件关系、协议、状态或关键权衡 |
| 证据强度 | 15 | 是否有实验、生产数据、代码、配置或可复现实例 |
| Agent 服务端价值 | 15 | 是否能映射到明确子系统并形成落地动作 |

必须同时满足：

- 总分 `>= 80`；
- 来源可信度 `>= 20`；
- 架构深度 `>= 18`；
- Agent 服务端价值 `>= 12`；
- 时间窗口有效；
- 不属于纯模型能力、训练算法、benchmark 排名、提示技巧或泛趋势评论。

报告里的分数是本雷达的编辑判断，不冒充来源方评分。选择时在合格库存中优化问题覆盖和来源多样性；同一机构原则上不超过 2 篇，除非其他来源确实没有达到门槛，并在报告解释。

## 每篇的强制分析模板

1. **针对的问题**：可观察症状、根因和约束。
2. **原设计**：组件、协议、状态流、关键选择及替代方案；引用原始证据。
3. **对 Agent 服务器的采用设计**：对应子系统、最小实现、数据/控制流和部署边界。
4. **验收不变量**：至少一个故障注入测试、指标、SLO 或必须始终成立的状态不变量。
5. **边界与风险**：供应商偏差、预览状态、未独立验证、场景外推或维护成本。

## 每轮执行顺序

1. 读取状态，计算滚动窗口和已发布集合，恢复超过 4 小时仍停留在 `queued` 的条目。
2. 并行发现论文和官方工程博客；记录查询、来源和访问失败。搜索失败不等于没有结果。
3. 规范化、聚类和去重，先做标题/摘要/正文初筛，再深读高潜候选。
4. 核验发布日期、作者/机构、E/R 类证据、全文技术细节和相关代码/图表；记录无法验证的声明。
5. 为所有实际审阅的候选打分并写入 cache；不合格条目写明单一主要拒绝原因。
6. 从未发布合格库存选择最多 5 篇，覆盖至少 3 个不同生产问题；同分时优先更近、证据更强、来源更多样的条目。
7. 写 `reports/YYYY-MM-DD/YYYY-MM-DD_HH-mm.md` 和 `index.md`。先把入选条目标记为 `queued`。
8. 验证：所有链接非空、日期在窗口内、报告恰好引用选中条目、JSON/JSONL 可解析、无重复 canonical ID、每篇五个分析字段齐全。
9. 只有验证通过后，使用临时文件加原子替换把 `queued` 推进为 `published`，更新 `seen-items.json` 与 `run-log.jsonl`。失败时不得推进发布状态。
10. 成功发布后，如存在 `tools/build_index.py`，运行 `python3 tools/build_index.py` 重建离线首页和校验清单。首页是派生视图；重建失败时保留已经验证通过的发布状态，明确报告首页过期及失败原因，不得伪造成功或反向改写状态。
11. 用中文输出本轮篇数、最高推荐、覆盖的问题、报告绝对路径和失败/不足原因。

## 状态要求

- 时间使用带时区 ISO 8601。
- `state` 只允许 `discovered`、`eligible`、`rejected`、`queued`、`published`、`failed`。
- `run-log.jsonl` 每行是一个完整 JSON 对象，不写 Markdown。
- 写状态前先生成同目录临时文件，解析成功后再原子替换。
- 某个来源下载或访问失败时只隔离该候选，不能污染其他候选或把失败条目标记为已发布。
