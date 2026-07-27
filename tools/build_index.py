#!/usr/bin/env python3
"""Build and validate the portable Agent architecture radar homepage."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = ROOT / "reports"
OUTPUT_PATH = ROOT / "index.html"
MANIFEST_PATH = ROOT / "SHA256SUMS.txt"

ARTICLE_HEADING = re.compile(r"^##\s+(\d+)\.\s+(.+?)\s*$", re.MULTILINE)
LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")
MARKDOWN_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
SCORE = re.compile(r"(?:总分|评分)[：:]\s*\**(\d{2,3})\s*/\s*100", re.IGNORECASE)
TABLE_SCORE = re.compile(r"^\|.*\|\s*(\d{2,3})\s*\|\s*$")

TAG_RULES = {
    "文件与工件": (
        "文件", "file", "artifact", "对象", "object", "version", "版本",
        "同步", "s3", "link", "链接", "manifest",
    ),
    "状态与恢复": (
        "state", "状态", "checkpoint", "snapshot", "恢复", "resume",
        "durable", "耐久", "session", "工作流", "workflow", "队列", "cursor",
    ),
    "身份与权限": (
        "identity", "身份", "auth", "授权", "权限", "token", "tenant",
        "租户", "obo", "principal", "credential", "凭据", "支付",
    ),
    "安全与隔离": (
        "security", "安全", "sandbox", "注入", "guard", "risk", "attack",
        "恶意", "漏洞", "隔离", "waf", "privilege", "供应链",
    ),
    "工具与协议": (
        "tool", "工具", "mcp", "ag-ui", "protocol", "协议", "gateway",
        "schema", "elicitation", "wire", "api",
    ),
    "运行时与调度": (
        "runtime", "运行时", "scheduler", "调度", "slo", "capacity",
        "agentcore", "cloud run", "arca", "eks", "bedrock", "runner",
    ),
    "记忆与上下文": (
        "memory", "记忆", "context", "上下文", "knowledge", "知识",
        "检索", "retrieval", "prompt",
    ),
    "观测与评测": (
        "observability", "trace", "评测", "evaluation", "verifier",
        "检测", "proof", "证明", "receipt", "收据", "审计", "指标",
    ),
}


def manifest_file(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    excluded_parts = {".git", "__pycache__"}
    return (
        path.is_file()
        and path != MANIFEST_PATH
        and not excluded_parts.intersection(relative.parts)
        and path.suffix.lower() not in {".pyc", ".pyo"}
    )


def strip_markdown(value: str) -> str:
    value = MARKDOWN_LINK.sub(r"\1", value)
    value = re.sub(r"`([^`]+)`", r"\1", value)
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"[*_>#]", "", value)
    value = re.sub(r"^\s*[-+]\s+", "", value)
    return re.sub(r"\s+", " ", value).strip()


def summarize(value: str, limit: int = 190) -> str:
    value = strip_markdown(value)
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip("，。、；; ") + "…"


def extract_problem(section: str) -> str:
    lines = section.splitlines()
    for index, line in enumerate(lines):
        if re.match(r"^###\s+针对的问题\s*$", line.strip()):
            for candidate in lines[index + 1 :]:
                candidate = candidate.strip()
                if candidate and not candidate.startswith("#"):
                    return summarize(candidate)
        if "针对的问题。" in line or "针对的问题：**" in line:
            return summarize(line)
    for line in lines:
        if line.strip() and not line.startswith(("#", "- 原始来源", "- 首次公开")):
            return summarize(line)
    return "完整问题描述见 Markdown 报告。"


def extract_sources(section: str) -> list[dict[str, str]]:
    lines = section.splitlines()
    source_lines = [line for line in lines[:15] if "来源" in line and LINK.search(line)]
    candidates = source_lines if source_lines else lines[:15]
    seen: set[str] = set()
    sources: list[dict[str, str]] = []
    for line in candidates:
        for label, url in LINK.findall(line):
            if url in seen:
                continue
            seen.add(url)
            sources.append({"label": strip_markdown(label), "url": url})
    return sources[:4]


def infer_type(section: str, sources: list[dict[str, str]]) -> str:
    value = (section[:900] + " " + " ".join(s["url"] for s in sources)).lower()
    if any(token in value for token in ("arxiv.org", "openreview.net", "doi.org", "论文", "预印本")):
        return "Paper"
    return "Engineering"


def infer_tags(title: str, problem: str, section: str) -> list[str]:
    value = f"{title} {problem} {section[:1800]}".lower()
    ranked: list[tuple[int, int, str]] = []
    for order, (tag, keywords) in enumerate(TAG_RULES.items()):
        score = sum(value.count(keyword.lower()) for keyword in keywords)
        if score:
            ranked.append((-score, order, tag))
    ranked.sort()
    return [tag for _, _, tag in ranked[:3]] or ["其他架构"]


def parse_run_label(text: str, path: Path) -> str:
    first_line = text.splitlines()[0] if text.splitlines() else ""
    match = re.search(r"(20\d{2}-\d{2}-\d{2})[^\d]+(\d{2})[:\-](\d{2})", first_line)
    if match:
        return f"{match.group(1)} {match.group(2)}:{match.group(3)}"
    return path.stem.replace("_", " ")


def table_scores(preamble: str) -> list[int]:
    scores: list[int] = []
    for line in preamble.splitlines():
        match = TABLE_SCORE.match(line.strip())
        if match:
            score = int(match.group(1))
            if 80 <= score <= 100:
                scores.append(score)
    return scores[:5]


def parse_report(path: Path) -> tuple[dict[str, str], list[dict[str, object]]]:
    text = path.read_text(encoding="utf-8-sig")
    matches = list(ARTICLE_HEADING.finditer(text))
    if not matches:
        raise ValueError(f"No article headings found: {path}")

    first_line = text.splitlines()[0].lstrip("# ").strip()
    report_href = path.relative_to(ROOT).as_posix()
    run_label = parse_run_label(text, path)
    fallback_scores = table_scores(text[: matches[0].start()])
    articles: list[dict[str, object]] = []

    for offset, match in enumerate(matches):
        end = matches[offset + 1].start() if offset + 1 < len(matches) else len(text)
        section = text[match.start() : end]
        title = strip_markdown(match.group(2))
        problem = extract_problem(section)
        sources = extract_sources(section)
        score_match = SCORE.search(section)
        score = int(score_match.group(1)) if score_match else (
            fallback_scores[offset] if offset < len(fallback_scores) else None
        )
        tags = infer_tags(title, problem, section)
        article_id = f"{path.stem}-{offset + 1}"
        articles.append(
            {
                "id": article_id,
                "order": offset + 1,
                "title": title,
                "problem": problem,
                "score": score,
                "tags": tags,
                "type": infer_type(section, sources),
                "sources": sources,
                "report": report_href,
                "round": path.stem,
                "runLabel": run_label,
                "searchText": strip_markdown(section).lower(),
            }
        )

    return (
        {
            "title": first_line,
            "href": report_href,
            "round": path.stem,
            "runLabel": run_label,
            "count": len(articles),
        },
        articles,
    )


def build_data() -> dict[str, object]:
    paths = sorted(REPORTS_DIR.rglob("*.md"), reverse=True)
    if not paths:
        raise ValueError(f"No Markdown reports found under {REPORTS_DIR}")
    rounds: list[dict[str, str]] = []
    articles: list[dict[str, object]] = []
    for path in paths:
        report, report_articles = parse_report(path)
        rounds.append(report)
        articles.extend(report_articles)

    tag_counts = Counter(tag for article in articles for tag in article["tags"])
    generated = datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")
    return {
        "generated": generated,
        "roundCount": len(rounds),
        "articleCount": len(articles),
        "latestRun": rounds[0]["runLabel"],
        "rounds": rounds,
        "tagCounts": dict(tag_counts.most_common()),
        "articles": articles,
    }


HTML_TEMPLATE = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light">
  <title>Agent 服务器架构雷达</title>
  <style>
    :root {
      --ink: #14213d;
      --muted: #5c677d;
      --paper: #f4f1ea;
      --surface: #fffdf8;
      --line: #d9d4c8;
      --accent: #006d5b;
      --accent-soft: #dceee8;
      --orange: #c55a11;
      --shadow: 0 18px 50px rgba(20, 33, 61, .08);
    }
    * { box-sizing: border-box; }
    html { scroll-behavior: smooth; }
    body {
      margin: 0;
      color: var(--ink);
      background:
        radial-gradient(circle at 12% 2%, rgba(0,109,91,.10), transparent 28rem),
        linear-gradient(180deg, #faf8f3 0, var(--paper) 34rem);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont,
        "Segoe UI", "Noto Sans SC", sans-serif;
      line-height: 1.6;
    }
    a { color: inherit; }
    .shell { width: min(1180px, calc(100% - 32px)); margin: 0 auto; }
    .hero { padding: 64px 0 34px; }
    .eyebrow {
      display: inline-flex; align-items: center; gap: 8px;
      color: var(--accent); font-size: 13px; font-weight: 800;
      letter-spacing: .12em; text-transform: uppercase;
    }
    .eyebrow::before {
      content: ""; width: 26px; height: 3px; border-radius: 9px; background: var(--accent);
    }
    h1 {
      max-width: 850px; margin: 14px 0 18px;
      font-family: Georgia, "Noto Serif SC", serif;
      font-size: clamp(40px, 7vw, 76px); line-height: 1.02; letter-spacing: -.045em;
    }
    .lede { max-width: 760px; margin: 0; color: var(--muted); font-size: 18px; }
    .stats {
      display: grid; grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px; margin-top: 34px;
    }
    .stat {
      min-height: 112px; padding: 20px; border: 1px solid rgba(20,33,61,.10);
      border-radius: 18px; background: rgba(255,253,248,.78); box-shadow: var(--shadow);
    }
    .stat strong { display: block; font-size: 30px; line-height: 1.2; }
    .stat span { color: var(--muted); font-size: 13px; }
    .utility {
      display: flex; flex-wrap: wrap; gap: 10px; margin: 22px 0 0;
    }
    .utility a {
      padding: 8px 12px; border: 1px solid var(--line); border-radius: 999px;
      background: rgba(255,255,255,.58); text-decoration: none; font-size: 13px; font-weight: 700;
    }
    .utility a:hover { border-color: var(--accent); color: var(--accent); }
    .controls {
      position: sticky; top: 0; z-index: 10;
      margin: 24px 0 22px; padding: 16px;
      border: 1px solid var(--line); border-radius: 22px;
      background: rgba(255,253,248,.93); backdrop-filter: blur(16px);
      box-shadow: 0 12px 34px rgba(20,33,61,.08);
    }
    .control-row { display: grid; grid-template-columns: minmax(240px, 1fr) 230px; gap: 12px; }
    input, select {
      width: 100%; min-height: 46px; padding: 0 14px;
      border: 1px solid var(--line); border-radius: 12px;
      color: var(--ink); background: white; font: inherit; outline: none;
    }
    input:focus, select:focus { border-color: var(--accent); box-shadow: 0 0 0 3px rgba(0,109,91,.12); }
    .chips { display: flex; gap: 8px; overflow-x: auto; padding-top: 12px; scrollbar-width: thin; }
    .chip {
      flex: 0 0 auto; padding: 7px 11px; border: 0; border-radius: 999px;
      color: var(--muted); background: #ede9df; font: inherit; font-size: 12px; font-weight: 800;
      cursor: pointer;
    }
    .chip[aria-pressed="true"] { color: white; background: var(--accent); }
    .list-head { display: flex; justify-content: space-between; gap: 20px; align-items: end; margin: 26px 0 14px; }
    .list-head h2 { margin: 0; font-family: Georgia, "Noto Serif SC", serif; font-size: 30px; }
    .result-count { color: var(--muted); font-size: 14px; }
    .grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }
    .card {
      position: relative; display: flex; flex-direction: column; min-height: 320px;
      padding: 24px; border: 1px solid var(--line); border-radius: 20px;
      background: var(--surface); box-shadow: 0 10px 34px rgba(20,33,61,.05);
    }
    .card::before {
      content: ""; position: absolute; inset: 0 auto 0 0; width: 4px;
      border-radius: 20px 0 0 20px; background: var(--accent);
    }
    .meta { display: flex; justify-content: space-between; gap: 12px; color: var(--muted); font-size: 12px; }
    .score {
      color: var(--orange); font-weight: 900; font-variant-numeric: tabular-nums;
    }
    .card h3 { margin: 16px 0 10px; font-size: 21px; line-height: 1.32; letter-spacing: -.018em; }
    .problem { margin: 0 0 17px; color: #38445c; font-size: 14px; }
    .tags { display: flex; flex-wrap: wrap; gap: 6px; margin-top: auto; }
    .tag {
      padding: 4px 8px; border-radius: 7px; color: var(--accent);
      background: var(--accent-soft); font-size: 11px; font-weight: 800;
    }
    .actions { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 18px; }
    .actions a {
      text-decoration: none; font-size: 13px; font-weight: 800;
      border-bottom: 1px solid currentColor;
    }
    .actions a:first-child { color: var(--accent); }
    .empty {
      display: none; padding: 50px 22px; border: 1px dashed var(--line);
      border-radius: 20px; text-align: center; color: var(--muted); background: rgba(255,255,255,.45);
    }
    footer { padding: 52px 0 72px; color: var(--muted); font-size: 13px; }
    footer strong { color: var(--ink); }
    @media (max-width: 760px) {
      .hero { padding-top: 42px; }
      .stats { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .control-row, .grid { grid-template-columns: 1fr; }
      .controls { top: 8px; }
      .list-head { align-items: start; flex-direction: column; gap: 2px; }
    }
    @media (max-width: 430px) {
      .shell { width: min(100% - 20px, 1180px); }
      .stats { gap: 8px; }
      .stat { min-height: 96px; padding: 15px; }
      .stat strong { font-size: 25px; }
      .card { padding: 20px; }
    }
    @media print {
      .controls, .utility { display: none; }
      body { background: white; }
      .grid { display: block; }
      .card { break-inside: avoid; margin-bottom: 12px; box-shadow: none; }
    }
  </style>
</head>
<body>
  <header class="hero">
    <div class="shell">
      <div class="eyebrow">Portable research archive</div>
      <h1>Agent 服务器<br>架构雷达</h1>
      <p class="lede">面向 Agent 服务器落地的文章级索引：从具体生产故障出发，连接到架构机制、采用设计、验收不变量与边界风险。页面完全离线，不依赖网络资源。</p>
      <div class="stats" aria-label="资料统计">
        <div class="stat"><strong id="articleStat">—</strong><span>已收录文章</span></div>
        <div class="stat"><strong id="roundStat">—</strong><span>完整研究轮次</span></div>
        <div class="stat"><strong>4h</strong><span>当前运行周期（工作日）</span></div>
        <div class="stat"><strong id="latestStat">—</strong><span>最近报告</span></div>
      </div>
      <nav class="utility" aria-label="迁移与原始资料">
        <a href="PORTABLE_README.md">资料包说明</a>
        <a href="AUTOMATION_PROMPT.md">Loop prompt</a>
        <a href="MIGRATION.md">Ubuntu 迁移清单</a>
        <a href="index.md">Markdown 轮次索引</a>
        <a href="state/run-log.jsonl">运行日志</a>
      </nav>
    </div>
  </header>

  <main class="shell">
    <section class="controls" aria-label="文章筛选">
      <div class="control-row">
        <input id="search" type="search" placeholder="搜索标题、故障、来源或架构机制…" autocomplete="off">
        <select id="roundFilter" aria-label="按轮次筛选"><option value="">全部轮次</option></select>
      </div>
      <div class="chips" id="chips" aria-label="按主题筛选"></div>
    </section>

    <div class="list-head">
      <h2>文章索引</h2>
      <div class="result-count" id="resultCount" aria-live="polite"></div>
    </div>
    <section class="grid" id="articleGrid"></section>
    <div class="empty" id="emptyState">没有匹配的文章。请缩短关键词或清除主题筛选。</div>
  </main>

  <footer class="shell">
    <strong>可搬运原则：</strong>首页只是派生视图，真正需要备份的是 Markdown、状态文件、质量规则与自动化 prompt。<br>
    <span id="generatedAt"></span>
  </footer>

  <noscript><div class="shell">此离线索引需要浏览器启用 JavaScript；原始报告仍可从 reports/ 目录直接阅读。</div></noscript>
  <script>
    const DATA = __DATA__;
    const $ = (selector) => document.querySelector(selector);
    const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, ch => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    })[ch]);
    const state = { query: "", round: "", tag: "" };

    $("#articleStat").textContent = DATA.articleCount;
    $("#roundStat").textContent = DATA.roundCount;
    $("#latestStat").textContent = DATA.latestRun.slice(5);
    $("#generatedAt").textContent = `首页生成于 ${DATA.generated.replace("T", " ")}`;

    for (const round of DATA.rounds) {
      const option = document.createElement("option");
      option.value = round.round;
      option.textContent = `${round.runLabel} · ${round.count} 篇`;
      $("#roundFilter").append(option);
    }

    const chipEntries = [["", DATA.articleCount], ...Object.entries(DATA.tagCounts)];
    for (const [tag, count] of chipEntries) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "chip";
      button.dataset.tag = tag;
      button.setAttribute("aria-pressed", tag === "" ? "true" : "false");
      button.textContent = `${tag || "全部主题"} ${count}`;
      button.addEventListener("click", () => {
        state.tag = tag;
        document.querySelectorAll(".chip").forEach(item =>
          item.setAttribute("aria-pressed", String(item.dataset.tag === tag))
        );
        render();
      });
      $("#chips").append(button);
    }

    function card(article) {
      const primary = article.sources[0];
      const sourceLink = primary
        ? `<a href="${escapeHtml(primary.url)}" target="_blank" rel="noreferrer">原始来源 ↗</a>`
        : "";
      const score = article.score ? `<span class="score">${article.score}/100</span>` : "";
      return `<article class="card" id="${escapeHtml(article.id)}">
        <div class="meta"><span>${escapeHtml(article.runLabel)} · ${escapeHtml(article.type)}</span>${score}</div>
        <h3>${escapeHtml(article.title)}</h3>
        <p class="problem">${escapeHtml(article.problem)}</p>
        <div class="tags">${article.tags.map(tag => `<span class="tag">${escapeHtml(tag)}</span>`).join("")}</div>
        <div class="actions">${sourceLink}<a href="${escapeHtml(article.report)}">完整 Markdown →</a></div>
      </article>`;
    }

    function render() {
      const query = state.query.trim().toLocaleLowerCase("zh-CN");
      const filtered = DATA.articles.filter(article => {
        const queryMatch = !query || article.searchText.includes(query) ||
          article.title.toLocaleLowerCase("zh-CN").includes(query) ||
          article.problem.toLocaleLowerCase("zh-CN").includes(query);
        const roundMatch = !state.round || article.round === state.round;
        const tagMatch = !state.tag || article.tags.includes(state.tag);
        return queryMatch && roundMatch && tagMatch;
      });
      $("#articleGrid").innerHTML = filtered.map(card).join("");
      $("#resultCount").textContent = `显示 ${filtered.length} / ${DATA.articleCount} 篇`;
      $("#emptyState").style.display = filtered.length ? "none" : "block";
    }

    $("#search").addEventListener("input", event => {
      state.query = event.target.value;
      render();
    });
    $("#roundFilter").addEventListener("change", event => {
      state.round = event.target.value;
      render();
    });
    render();
  </script>
</body>
</html>
"""


def write_homepage(data: dict[str, object]) -> None:
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    OUTPUT_PATH.write_text(HTML_TEMPLATE.replace("__DATA__", payload), encoding="utf-8")


def write_manifest() -> None:
    entries: list[str] = []
    for path in sorted(p for p in ROOT.rglob("*") if manifest_file(p)):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        entries.append(f"{digest}  {path.relative_to(ROOT).as_posix()}")
    MANIFEST_PATH.write_text("\n".join(entries) + "\n", encoding="utf-8")


def queued_records(value: object, path: str = "$") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        if value.get("state") == "queued":
            found.append(str(value.get("canonical_id") or value.get("id") or path))
        for key, child in value.items():
            found.extend(queued_records(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(queued_records(child, f"{path}[{index}]"))
    return found


def validate_manifest() -> list[str]:
    errors: list[str] = []
    if not MANIFEST_PATH.is_file():
        return ["SHA256SUMS.txt is missing"]
    recorded: dict[str, str] = {}
    for number, line in enumerate(MANIFEST_PATH.read_text(encoding="utf-8").splitlines(), start=1):
        match = re.match(r"^([0-9a-f]{64})  (.+)$", line)
        if not match:
            errors.append(f"invalid SHA256SUMS.txt line {number}")
            continue
        digest, relative = match.groups()
        if relative in recorded:
            errors.append(f"duplicate manifest path: {relative}")
            continue
        recorded[relative] = digest
        path = ROOT / Path(relative)
        if not path.is_file():
            errors.append(f"manifest file is missing: {relative}")
            continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != digest:
            errors.append(f"manifest checksum mismatch: {relative}")
    expected = {
        path.relative_to(ROOT).as_posix()
        for path in ROOT.rglob("*")
        if manifest_file(path)
    }
    missing = sorted(expected - recorded.keys())
    extra = sorted(recorded.keys() - expected)
    if missing:
        errors.append(f"manifest omits {len(missing)} file(s): {', '.join(missing[:3])}")
    if extra:
        errors.append(f"manifest lists {len(extra)} extra file(s): {', '.join(extra[:3])}")
    return errors


def validate(data: dict[str, object], require_output: bool = True) -> list[str]:
    errors: list[str] = []
    articles = data["articles"]
    rounds = data["rounds"]
    if len(articles) != sum(int(round_["count"]) for round_ in rounds):
        errors.append("article count does not match round totals")
    if len({article["id"] for article in articles}) != len(articles):
        errors.append("duplicate article IDs")
    for article in articles:
        if not article["title"] or not article["problem"]:
            errors.append(f"incomplete article: {article['id']}")
        if not (ROOT / str(article["report"])).is_file():
            errors.append(f"missing report: {article['report']}")
        if not article["sources"]:
            errors.append(f"missing source link: {article['id']}")
        if article["score"] is None:
            errors.append(f"missing radar score: {article['id']}")
    cache_data: object | None = None
    for state_name in ("item-cache.json", "seen-items.json"):
        try:
            parsed = json.loads((ROOT / "state" / state_name).read_text(encoding="utf-8-sig"))
            if state_name == "item-cache.json":
                cache_data = parsed
        except Exception as exc:
            errors.append(f"invalid {state_name}: {exc}")
    if cache_data is not None:
        queued = queued_records(cache_data)
        if queued:
            errors.append(f"{len(queued)} queued record(s) make this snapshot unsafe: {', '.join(queued[:3])}")
    try:
        for number, line in enumerate(
            (ROOT / "state" / "run-log.jsonl").read_text(encoding="utf-8-sig").splitlines(),
            start=1,
        ):
            if line.strip():
                json.loads(line)
    except Exception as exc:
        errors.append(f"invalid run-log.jsonl at line {number}: {exc}")
    if require_output and not OUTPUT_PATH.is_file():
        errors.append("index.html is missing")
    if require_output and OUTPUT_PATH.is_file():
        output = OUTPUT_PATH.read_text(encoding="utf-8")
        if "__DATA__" in output:
            errors.append("index.html still contains the data placeholder")
        if re.search(r"<(?:script|link)\b[^>]*(?:src|href)=[\"']https?://", output, re.IGNORECASE):
            errors.append("index.html contains a remote script or stylesheet")
        local_links = re.findall(r"\bhref=[\"']([^\"']+)[\"']", output, re.IGNORECASE)
        for href in local_links:
            if "${" in href or href.startswith(("http://", "https://", "#", "mailto:")):
                continue
            local_path = ROOT / href.split("#", 1)[0]
            if not local_path.is_file():
                errors.append(f"broken local homepage link: {href}")
        for article in articles:
            if f'"id":"{article["id"]}"' not in output:
                errors.append(f"article data missing from index.html: {article['id']}")
    if require_output:
        errors.extend(validate_manifest())
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="validate reports and state without rewriting the homepage",
    )
    args = parser.parse_args()

    try:
        data = build_data()
        errors = validate(data, require_output=args.check)
        if errors:
            for error in errors:
                print(f"ERROR: {error}", file=sys.stderr)
            return 1
        if not args.check:
            write_homepage(data)
            write_manifest()
        print(
            f"OK: {data['roundCount']} rounds, {data['articleCount']} articles, "
            f"{len(data['tagCounts'])} topics"
        )
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
