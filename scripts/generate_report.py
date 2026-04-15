#!/usr/bin/env python3
"""
Generate Moyamoya disease daily report HTML using Zhipu AI (GLM-5.1).
Reads papers JSON, analyzes with AI, generates styled HTML.
"""

import json
import sys
import os
import time
import argparse
from datetime import datetime, timezone, timedelta

import httpx

API_BASE = os.environ.get(
    "ZHIPU_API_BASE", "https://open.bigmodel.cn/api/coding/paas/v4"
)
MODEL_NAME = os.environ.get("ZHIPU_MODEL", "GLM-5-Turbo")

SYSTEM_PROMPT = (
    "你是腦血管醫學與神經科學領域的資深研究員與科學傳播者，專精於 Moyamoya 病（毛毛樣腦血管疾病）研究。你的任務是：\n"
    "1. 從提供的醫學文獻中，篩選出最具臨床意義與研究價值的 Moyamoya 病相關論文\n"
    "2. 對每篇論文進行繁體中文摘要、分類、PICO 分析\n"
    "3. 評估其臨床實用性（高/中/低）\n"
    "4. 生成適合醫療專業人員閱讀的日報\n\n"
    "輸出格式要求：\n"
    "- 語言：繁體中文（台灣用語）\n"
    "- 專業但易懂\n"
    "- 每篇論文需包含：中文標題、一句話總結、PICO分析、臨床實用性、分類標籤\n"
    "- 最後提供今日精選 TOP 3（最重要/最影響臨床實踐的論文）\n"
    "回傳格式必須是純 JSON，不要用 markdown code block 包裹。"
)


def call_zhipu_api(api_key: str, messages: list, max_retries: int = 3) -> str:
    url = f"{API_BASE}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 8192,
    }
    models_to_try = [MODEL_NAME, "GLM-4.7", "GLM-4.7-Flash"]

    for model in models_to_try:
        payload["model"] = model
        for attempt in range(max_retries):
            try:
                print(
                    f"[INFO] Calling {model} (attempt {attempt + 1})...",
                    file=sys.stderr,
                )
                with httpx.Client(timeout=120) as client:
                    resp = client.post(url, headers=headers, json=payload)
                if resp.status_code == 429:
                    wait = 2**attempt * 5
                    print(f"[WARN] Rate limited, waiting {wait}s...", file=sys.stderr)
                    time.sleep(wait)
                    continue
                if resp.status_code >= 500:
                    print(
                        f"[WARN] Server error {resp.status_code}, retrying...",
                        file=sys.stderr,
                    )
                    time.sleep(3)
                    continue
                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                return content
            except httpx.HTTPStatusError as e:
                print(
                    f"[ERROR] HTTP {e.response.status_code}: {e.response.text[:200]}",
                    file=sys.stderr,
                )
            except Exception as e:
                print(f"[ERROR] API call failed: {e}", file=sys.stderr)
            time.sleep(2)
        print(f"[WARN] Model {model} failed, trying next...", file=sys.stderr)
    return ""


def parse_ai_response(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        for i, ch in enumerate(text):
            if ch == "{":
                for j in range(len(text), 0, -1):
                    if text[j - 1] == "}":
                        try:
                            return json.loads(text[i:j])
                        except json.JSONDecodeError:
                            break
                break
    return {"raw_analysis": text}


def generate_html(analysis: dict, date_str: str, paper_count: int) -> str:
    summary = analysis.get(
        "market_summary", analysis.get("summary", "本日無文獻趨勢摘要。")
    )
    top_picks = analysis.get("top_picks", analysis.get("top_papers", []))
    all_papers = analysis.get("all_papers", [])
    keywords = analysis.get("keywords", [])
    topic_dist = analysis.get("topic_distribution", [])

    def safe_str(v):
        if isinstance(v, str):
            return v
        if isinstance(v, dict):
            return "<br>".join(f"**{k}:** {safe_str(v2)}" for k, v2 in v.items())
        if isinstance(v, list):
            return ", ".join(safe_str(x) for x in v)
        return str(v)

    def esc(s):
        return (
            s.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )

    weekday_names = ["一", "二", "三", "四", "五", "六", "日"]
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d")
        weekday = weekday_names[d.weekday()]
        date_display = d.strftime("%Y年%-m月%-d日")
    except Exception:
        weekday = ""
        date_display = date_str

    top_cards = ""
    for idx, paper in enumerate(top_picks[:8], 1):
        title = esc(safe_str(paper.get("title", paper.get("chinese_title", ""))))
        summary_text = esc(
            safe_str(paper.get("summary", paper.get("one_line_summary", "")))
        )
        clinical = esc(
            safe_str(
                paper.get("clinical_utility", paper.get("clinical_relevance", "中"))
            )
        )
        pico = paper.get("pico", paper.get("PICO", {}))
        tags = paper.get("tags", paper.get("categories", []))
        if isinstance(tags, str):
            tags = [tags]
        tags_html = "".join(f'<span class="tag">{esc(t)}</span>' for t in tags[:4])
        p_html = (
            esc(
                safe_str(pico.get("P", pico.get("population", pico.get("patient", ""))))
            )
            if isinstance(pico, dict)
            else esc(safe_str(pico))
        )
        i_html = (
            esc(safe_str(pico.get("I", pico.get("intervention", ""))))
            if isinstance(pico, dict)
            else ""
        )
        c_html = (
            esc(safe_str(pico.get("C", pico.get("comparison", ""))))
            if isinstance(pico, dict)
            else ""
        )
        o_html = (
            esc(safe_str(pico.get("O", pico.get("outcome", ""))))
            if isinstance(pico, dict)
            else ""
        )
        rank_color = "#c0392b" if idx <= 3 else "#8c4f2b"
        rank_bg = "#fdf2f2" if idx <= 3 else "#fdf6f0"

        top_cards += f"""
        <div class="card top-card">
            <div class="rank-badge" style="background:{rank_color};">{idx}</div>
            <h3>{title}</h3>
            <p class="summary">{summary_text}</p>
            {"<div class='pico-grid'>" + "".join(f"<div class='pico-item'><strong>{k}</strong> {v}</div>" for k, v in [("P", p_html), ("I", i_html), ("C", c_html), ("O", o_html)] if v) + "</div>" if isinstance(pico, dict) and any([p_html, i_html, c_html, o_html]) else ""}
            <div class="card-footer">
                <div class="tags">{tags_html}</div>
                <span class="clinical clinical-{clinical}">臨床實用性：{clinical}</span>
            </div>
        </div>"""

    other_cards = ""
    for paper in all_papers:
        title = esc(safe_str(paper.get("title", paper.get("chinese_title", ""))))
        summary_text = esc(
            safe_str(paper.get("summary", paper.get("one_line_summary", "")))
        )
        clinical = esc(
            safe_str(
                paper.get("clinical_utility", paper.get("clinical_relevance", "中"))
            )
        )
        tags = paper.get("tags", paper.get("categories", []))
        if isinstance(tags, str):
            tags = [tags]
        tags_html = "".join(f'<span class="tag">{esc(t)}</span>' for t in tags[:3])
        other_cards += f"""
        <div class="card">
            <h3>{title}</h3>
            <p class="summary">{summary_text}</p>
            <div class="card-footer">
                <div class="tags">{tags_html}</div>
                <span class="clinical clinical-{clinical}">臨床實用性：{clinical}</span>
            </div>
        </div>"""

    topic_bars = ""
    if topic_dist:
        max_val = max(
            (t.get("count", t.get("percentage", 0)) for t in topic_dist), default=1
        )
        for t in topic_dist:
            name = esc(safe_str(t.get("topic", t.get("name", ""))))
            count = t.get("count", t.get("percentage", 0))
            pct = int(count / max_val * 100) if max_val else 0
            topic_bars += f"""
            <div class="topic-bar-row">
                <span class="topic-label">{name}</span>
                <div class="topic-bar-bg"><div class="topic-bar-fill" style="width:{pct}%"></div></div>
                <span class="topic-count">{count}</span>
            </div>"""

    keyword_pills = "".join(
        f'<span class="keyword-pill">{esc(k)}</span>' for k in keywords[:20]
    )

    return f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Moyamoya Brain - {date_display}（週{weekday}）</title>
<meta name="description" content="Moyamoya 病每日文獻日報 {date_display}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@300;400;500;700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
:root {{
    --bg: #f6f1e8;
    --card: #ffffff;
    --text: #2c1810;
    --text2: #6b5b50;
    --accent: #2c6fbb;
    --accent2: #8c4f2b;
    --border: #e8ddd0;
    --success: #27ae60;
    --warning: #f39c12;
    --danger: #c0392b;
    --radius: 12px;
    --shadow: 0 2px 12px rgba(44,24,16,0.07);
}}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{
    font-family: 'Inter', 'Noto Sans TC', sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.7;
    max-width: 900px;
    margin: 0 auto;
    padding: 20px 16px 60px;
}}
header {{
    text-align: center;
    padding: 40px 20px 30px;
    border-bottom: 2px solid var(--border);
    margin-bottom: 32px;
}}
.logo {{ font-size: 48px; margin-bottom: 8px; }}
h1 {{
    font-size: 28px;
    font-weight: 700;
    color: var(--accent);
    margin-bottom: 8px;
    letter-spacing: -0.5px;
}}
.header-badges {{ display: flex; gap: 10px; justify-content: center; flex-wrap: wrap; margin-top: 12px; }}
.badge {{
    display: inline-block;
    padding: 4px 14px;
    border-radius: 20px;
    font-size: 13px;
    font-weight: 500;
    background: #eef4fb;
    color: var(--accent);
}}
.badge.accent {{ background: #fdf6f0; color: var(--accent2); }}
.powered {{ font-size: 12px; color: var(--text2); margin-top: 10px; }}

.section {{ margin-bottom: 36px; }}
.section-title {{
    font-size: 20px;
    font-weight: 600;
    color: var(--accent2);
    margin-bottom: 16px;
    padding-bottom: 8px;
    border-bottom: 2px solid var(--border);
}}

.summary-card {{
    background: linear-gradient(135deg, #eef4fb 0%, #f6f1e8 100%);
    border-radius: var(--radius);
    padding: 24px;
    margin-bottom: 32px;
    border-left: 4px solid var(--accent);
    line-height: 1.8;
}}

.card {{
    background: var(--card);
    border-radius: var(--radius);
    padding: 20px 24px;
    margin-bottom: 16px;
    box-shadow: var(--shadow);
    border: 1px solid var(--border);
    position: relative;
}}
.top-card {{ border-left: 4px solid var(--accent2); }}
.rank-badge {{
    position: absolute;
    top: -8px;
    right: 16px;
    width: 32px;
    height: 32px;
    border-radius: 50%;
    color: white;
    font-weight: 700;
    font-size: 14px;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 2px 6px rgba(0,0,0,0.15);
}}
.card h3 {{
    font-size: 16px;
    font-weight: 600;
    margin-bottom: 8px;
    padding-right: 40px;
    line-height: 1.5;
}}
.summary {{ color: var(--text2); font-size: 14px; margin-bottom: 12px; }}

.pico-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 6px 16px;
    font-size: 13px;
    margin-bottom: 12px;
    background: #faf7f2;
    padding: 10px 14px;
    border-radius: 8px;
}}
.pico-item strong {{ color: var(--accent2); margin-right: 4px; }}

.card-footer {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 8px;
}}
.tags {{ display: flex; gap: 6px; flex-wrap: wrap; }}
.tag {{
    font-size: 11px;
    padding: 2px 10px;
    border-radius: 12px;
    background: #eef4fb;
    color: var(--accent);
}}
.clinical {{ font-size: 12px; font-weight: 500; padding: 2px 10px; border-radius: 12px; }}
.clinical-高 {{ background: #e8f8ef; color: var(--success); }}
.clinical-中 {{ background: #fef9e7; color: var(--warning); }}
.clinical-低 {{ background: #fdf2f2; color: var(--danger); }}

.topic-bar-row {{
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 8px;
}}
.topic-label {{ width: 160px; font-size: 13px; text-align: right; flex-shrink: 0; }}
.topic-bar-bg {{
    flex: 1;
    height: 20px;
    background: #e8ddd0;
    border-radius: 10px;
    overflow: hidden;
}}
.topic-bar-fill {{
    height: 100%;
    background: linear-gradient(90deg, var(--accent), var(--accent2));
    border-radius: 10px;
    transition: width 0.5s;
}}
.topic-count {{ font-size: 13px; color: var(--text2); width: 30px; }}

.keywords-section {{ margin-bottom: 32px; }}
.keyword-pill {{
    display: inline-block;
    padding: 4px 12px;
    margin: 3px;
    border-radius: 16px;
    font-size: 12px;
    background: var(--card);
    border: 1px solid var(--border);
    color: var(--text2);
}}

.clinic-banner {{
    background: linear-gradient(135deg, #2c6fbb, #1a4f8b);
    color: white;
    border-radius: var(--radius);
    padding: 28px 24px;
    text-align: center;
    margin: 36px 0 24px;
}}
.clinic-banner h3 {{ font-size: 18px; margin-bottom: 12px; }}
.clinic-banner p {{ font-size: 14px; opacity: 0.9; margin-bottom: 16px; }}
.clinic-links {{ display: flex; gap: 12px; justify-content: center; flex-wrap: wrap; }}
.clinic-links a {{
    display: inline-block;
    padding: 10px 24px;
    border-radius: 24px;
    font-weight: 500;
    font-size: 14px;
    text-decoration: none;
    transition: transform 0.2s, box-shadow 0.2s;
}}
.clinic-links a:hover {{ transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.2); }}
.btn-primary {{ background: white; color: #2c6fbb; }}
.btn-secondary {{ background: rgba(255,255,255,0.2); color: white; border: 1px solid rgba(255,255,255,0.4); }}

footer {{
    text-align: center;
    padding: 24px;
    font-size: 12px;
    color: var(--text2);
    border-top: 1px solid var(--border);
    margin-top: 20px;
}}
footer a {{ color: var(--accent); text-decoration: none; }}

.empty-msg {{
    text-align: center;
    color: var(--text2);
    padding: 40px 20px;
    font-size: 15px;
}}

@media (max-width: 600px) {{
    body {{ padding: 12px 10px 40px; }}
    header {{ padding: 24px 12px 20px; }}
    h1 {{ font-size: 22px; }}
    .card {{ padding: 16px; }}
    .pico-grid {{ grid-template-columns: 1fr; }}
    .topic-label {{ width: 100px; font-size: 12px; }}
    .clinic-links {{ flex-direction: column; align-items: center; }}
}}
</style>
</head>
<body>

<header>
    <div class="logo">🧠</div>
    <h1>Moyamoya Brain</h1>
    <p style="color:var(--text2);font-size:15px;">Moyamoya 病每日文獻日報</p>
    <div class="header-badges">
        <span class="badge">📅 {date_display}（週{weekday}）</span>
        <span class="badge accent">📄 {paper_count} 篇文獻</span>
    </div>
    <p class="powered">Powered by PubMed + Zhipu AI (GLM-5-Turbo)</p>
</header>

<div class="summary-card">
    <div class="section-title" style="border:none;padding:0;margin:0 0 8px;">📊 今日文獻趨勢</div>
    {summary}
</div>

{"<div class='section'><div class='section-title'>🏆 今日精選 TOP Picks</div>" + top_cards + "</div>" if top_picks else ""}

{"<div class='section'><div class='section-title'>📚 其他文獻</div>" + other_cards + "</div>" if all_papers else ""}

{"<div class='section'><div class='section-title'>📈 主題分佈</div>" + topic_bars + "</div>" if topic_bars else ""}

{"<div class='keywords-section'><div class='section-title'>🏷️ 關鍵字</div>" + keyword_pills + "</div>" if keywords else ""}

<div class="clinic-banner">
    <h3>🏥 李政洋身心診所</h3>
    <p>專業身心科醫療服務，關心您的心理健康</p>
    <div class="clinic-links">
        <a href="https://www.leepsyclinic.com/" target="_blank" class="btn-primary">🏠 診所首頁</a>
        <a href="https://blog.leepsyclinic.com/" target="_blank" class="btn-secondary">📧 訂閱電子報</a>
    </div>
</div>

<footer>
    <p>Moyamoya Brain &copy; {date_str[:4]} — 自動生成於 {datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M")} (CST) | Model: GLM-5-Turbo</p>
    <p style="margin-top:4px;"><a href="https://github.com/u8901006/moyamoya-brain" target="_blank">GitHub</a> · <a href="index.html">📋 歷史日報</a></p>
</footer>

</body>
</html>"""


def main():
    parser = argparse.ArgumentParser(description="Generate Moyamoya daily report HTML")
    parser.add_argument("--input", required=True, help="Papers JSON file")
    parser.add_argument("--output", required=True, help="Output HTML file")
    parser.add_argument(
        "--api-key", default="", help="Zhipu API key (or set ZHIPU_API_KEY env)"
    )
    args = parser.parse_args()

    api_key = args.api_key or os.environ.get("ZHIPU_API_KEY", "")
    if not api_key:
        print(
            "[ERROR] No API key provided. Set ZHIPU_API_KEY or use --api-key",
            file=sys.stderr,
        )
        sys.exit(1)

    with open(args.input, "r", encoding="utf-8") as f:
        data = json.load(f)

    papers = data.get("papers", [])
    date_str = data.get(
        "date", datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")
    )
    paper_count = data.get("count", len(papers))

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)

    if not papers:
        print("[WARN] No papers found, generating empty report...", file=sys.stderr)
        html = generate_html(
            {"market_summary": "今日尚未找到新的 Moyamoya 病相關文獻。"}, date_str, 0
        )
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"[INFO] Empty report saved to {args.output}", file=sys.stderr)
        return

    papers_text = ""
    for i, p in enumerate(papers, 1):
        papers_text += f"\n--- 論文 {i} ---\n"
        papers_text += f"標題: {p.get('title', '')}\n"
        papers_text += f"期刊: {p.get('journal', '')}\n"
        papers_text += f"日期: {p.get('date', '')}\n"
        papers_text += f"作者: {', '.join(p.get('authors', []))}\n"
        papers_text += f"摘要: {p.get('abstract', '')[:1500]}\n"
        papers_text += f"PMID: {p.get('pmid', '')}\n"
        papers_text += f"關鍵字: {', '.join(p.get('keywords', []))}\n"
        papers_text += f"連結: {p.get('url', '')}\n"

    user_prompt = f"""以下是今天從 PubMed 搜集到的 {paper_count} 篇 Moyamoya 病相關文獻：

{papers_text}

請分析以上文獻，並以以下 JSON 格式回傳（不要用 markdown code block 包裹）：
{{
    "market_summary": "今日文獻趨勢一段話總結（繁體中文，100-200字）",
    "top_picks": [
        {{
            "title": "繁體中文標題",
            "one_line_summary": "一句話總結",
            "pico": {{
                "P": "Patient/Population",
                "I": "Intervention/Indicator",
                "C": "Comparison",
                "O": "Outcome"
            }},
            "clinical_utility": "高/中/低",
            "tags": ["分類標籤1", "分類標籤2"]
        }}
    ],
    "all_papers": [
        {{
            "title": "繁體中文標題",
            "one_line_summary": "一句話總結",
            "clinical_utility": "高/中/低",
            "tags": ["分類標籤"]
        }}
    ],
    "topic_distribution": [
        {{"topic": "主題名稱", "count": 數量}}
    ],
    "keywords": ["關鍵字1", "關鍵字2"]
}}

注意：
- top_picks 放 5-8 篇最重要的論文
- all_papers 放其餘論文
- clinical_utility 只能是 高、中、低
- 分類標籤請用：腦血管外科手術、神經影像學、小兒神經學、認知功能、神經心理學、復健醫學、物理治療、職能治療、語言治療、生活品質、流行病學、基礎研究、病例報告、系統性回顧
- topic_distribution 統計各主題的論文數量"""

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    print("[INFO] Calling Zhipu AI for analysis...", file=sys.stderr)
    raw_response = call_zhipu_api(api_key, messages)

    if raw_response:
        analysis = parse_ai_response(raw_response)
        print(
            f"[INFO] AI analysis complete. Keys: {list(analysis.keys())}",
            file=sys.stderr,
        )
    else:
        print("[WARN] AI analysis failed, generating basic report...", file=sys.stderr)
        analysis = {
            "market_summary": f"今日共收錄 {paper_count} 篇 Moyamoya 病相關文獻，AI 分析暫時無法使用。",
            "all_papers": [
                {
                    "title": p.get("title", ""),
                    "one_line_summary": p.get("abstract", "")[:100],
                    "clinical_utility": "中",
                    "tags": ["Moyamoya 病"],
                }
                for p in papers
            ],
            "keywords": ["moyamoya disease", "cerebrovascular", "revascularization"],
        }

    html = generate_html(analysis, date_str, paper_count)

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[INFO] Report saved to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
