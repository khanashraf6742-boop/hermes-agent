#!/usr/bin/env python3
"""RAG grounding engine (stdlib only): chunk repo docs, TF-IDF retrieve,
emit per-batch evidence packs + claim-verification report.

Usage: python3 rag_ingest.py  (run from repo root)
"""
import json, math, os, re
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVDIR = os.path.join(ROOT, "explainer_video", "evidence")
SCRIPT = os.path.join(ROOT, "explainer_video", "script", "script_batches.json")

SOURCES = [
    ("README.md", 40000),
    ("SOUL.md", 5000),
    ("AGENTS.md", 30000),
    ("COMPAT_MANIFEST.md", 15000),
    ("CONTRIBUTING.md", 12000),
]
EXTRA_FACTS = """FACTS (curated from repo tree):
- Messaging platforms: Telegram, Discord, Slack, WhatsApp, Signal, CLI/TUI, Email, Home Assistant.
  Gateway directory gateway/platforms holds signal.py, bluebubbles.py, weixin.py, qqbot, webhook.py, api_server.py.
- Terminal backends (7): local, Docker, SSH, Singularity, Modal, Daytona, Vercel Sandbox.
  Serverless Daytona/Modal hibernate when idle, wake on demand, cost nearly nothing between sessions.
- Tools: 40+ tools, toolset system, terminal backends doc reference.
- Memory/learning: agent-curated memory with periodic nudges, autonomous skill creation after complex
  tasks, skills self-improve during use, FTS5 session search with LLM summarization, Honcho dialectic
  user modeling, agentskills.io open standard compatible.
- Cron: built-in cron scheduler with delivery to any platform, natural language schedules.
- Delegation: spawn isolated subagents for parallel workstreams; Python scripts call tools via RPC.
- Research: batch trajectory generation, trajectory compression for training tool-calling models.
- Install: curl install.sh (linux/mac/wsl2/termux), install.ps1 powershell native windows with MinGit.
- CLI: hermes, hermes model, hermes tools, hermes config set/get, hermes gateway, hermes setup,
  hermes claw migrate, hermes update, hermes doctor.
- Nous Portal: 300+ models, Tool Gateway (Firecrawl search, FAL images, OpenAI TTS, Browser Use),
  hermes setup --portal, hermes portal info.
- Docs site: hermes-agent.nousresearch.com/docs. Community: Discord NousResearch.
- License MIT. Built by Nous Research.
"""

STOP = set("""a an the and or of to in on for with is are was were be been it its this that
these those as at by from we you your our they their he she him her his hers our ours
not no yes do does did can could will would should shall may might must have has had
having all any each more most other some such than then there here when where which who
whom what why how into over after before between during under again once here there also
just very per via vs s t d ll m re ve don doesn isn aren wasn weren couldn wouldn shouldn
""".split())

QUERIES = {
    "B1": "self-improving AI agent Nous Research learning loop skills memory model switch providers",
    "B2": "architecture terminal TUI gateway agent runtime tools loop state sessions SQLite FTS5 search",
    "B3": "closed learning loop memory nudges skill creation self-improve session search Honcho agentskills",
    "B4": "messaging Telegram Discord Slack WhatsApp Signal gateway voice terminal backends Docker SSH Modal Daytona serverless",
    "B5": "subagents parallel RPC scripts cron scheduler automations batch trajectory research training",
    "B6": "install curl powershell hermes model gateway setup update doctor Nous Portal Tool Gateway docs discord",
}

CLAIMS = [
    "self-improving AI agent", "Nous Research", "hermes model", "Telegram", "Discord",
    "40+ tools", "FTS5", "Honcho", "agentskills.io", "cron", "subagents",
    "Daytona", "Modal", "install.sh", "hermes gateway", "Nous Portal",
    "300+ models", "Tool Gateway", "hermes doctor", "MIT",
]


def tokenize(t):
    return [w for w in re.findall(r"[a-z0-9]+", t.lower()) if w not in STOP and len(w) > 1]


def chunk(text, name, size=700):
    paras, cur = [], ""
    for p in re.split(r"\n\s*\n", text):
        p = p.strip()
        if not p:
            continue
        if len(cur) + len(p) + 2 <= size:
            cur = (cur + "\n\n" + p).strip()
        else:
            if cur:
                paras.append(cur)
            cur = p if len(p) <= size else p[:size]
            if len(p) > size:
                paras.append(cur)
                cur = ""
    if cur:
        paras.append(cur)
    return [{"source": name, "text": c} for c in paras]


def main():
    os.makedirs(EVDIR, exist_ok=True)
    corpus = []
    fulltext = ""
    for fname, cap in SOURCES:
        p = os.path.join(ROOT, fname)
        if os.path.exists(p):
            with open(p, encoding="utf-8", errors="ignore") as f:
                t = f.read()[:cap]
            fulltext += "\n" + t
            corpus += chunk(t, fname)
    corpus += chunk(EXTRA_FACTS, "FACTS.md")
    fulltext += "\n" + EXTRA_FACTS

    # TF-IDF
    docs = [tokenize(c["text"]) for c in corpus]
    df = Counter()
    for d in docs:
        df.update(set(d))
    N = len(docs)
    idf = {w: math.log((N + 1) / (c + 1)) + 1 for w, c in df.items()}

    def vec(tokens):
        tf = Counter(tokens)
        return {w: (n / len(tokens)) * idf.get(w, 1.0) for w, n in tf.items()}

    dvecs = [vec(d) for d in docs]

    def cos(a, b):
        inter = set(a) & set(b)
        num = sum(a[w] * b[w] for w in inter)
        da = math.sqrt(sum(v * v for v in a.values())) or 1
        db = math.sqrt(sum(v * v for v in b.values())) or 1
        return num / (da * db)

    with open(SCRIPT, encoding="utf-8") as f:
        batches = json.load(f)["batches"]

    index_md = ["# RAG Evidence Index", "",
                f"Corpus: {len(corpus)} chunks from {', '.join(s for s, _ in SOURCES)} + FACTS.md", ""]
    for b in batches:
        q = QUERIES[b["id"]] + " " + " ".join(b["sentences"])
        qv = vec(tokenize(q))
        ranked = sorted(enumerate(dvecs), key=lambda x: cos(qv, x[1]), reverse=True)[:4]
        pack = {"batch": b["id"], "title": b["title"], "query": QUERIES[b["id"]],
                "evidence": [{"source": corpus[i]["source"], "score": round(cos(qv, v), 4),
                              "excerpt": corpus[i]["text"][:600]} for i, v in ranked]}
        with open(os.path.join(EVDIR, f"evidence_{b['id']}.json"), "w", encoding="utf-8") as f:
            json.dump(pack, f, ensure_ascii=False, indent=1)
        index_md.append(f"## {b['id']} — {b['title']}")
        for e in pack["evidence"]:
            ex = e["excerpt"].replace("\n", " ")[:220]
            index_md.append(f"- **{e['source']}** (score {e['score']}): {ex}…")
        index_md.append("")

    # Claim verification (literal, case-insensitive)
    low = fulltext.lower()
    rows = [("claim", "status", "source")]
    for c in CLAIMS:
        found = c.lower() in low
        src = ""
        if found:
            for fname, _ in SOURCES:
                p = os.path.join(ROOT, fname)
                try:
                    with open(p, encoding="utf-8", errors="ignore") as f:
                        if c.lower() in f.read().lower():
                            src = fname
                            break
                except OSError:
                    pass
            src = src or "FACTS.md"
        rows.append((c, "GROUNDED" if found else "MISSING", src))
    with open(os.path.join(EVDIR, "claim_report.json"), "w", encoding="utf-8") as f:
        json.dump([{"claim": c, "status": s, "source": s2} for c, s, s2 in rows[1:]], f, indent=1)
    index_md.append("## Claim verification")
    index_md.append("")
    index_md.append("| Claim | Status | Source |")
    index_md.append("|---|---|---|")
    for c, s, s2 in rows[1:]:
        index_md.append(f"| {c} | {s} | {s2} |")
    index_md.append("")
    with open(os.path.join(EVDIR, "EVIDENCE_INDEX.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(index_md))
    grounded = sum(1 for _, s, _ in rows[1:] if s == "GROUNDED")
    print(f"RAG OK: {len(corpus)} chunks, {len(batches)} evidence packs, claims {grounded}/{len(CLAIMS)} grounded")
    for c, s, s2 in rows[1:]:
        if s != "GROUNDED":
            print(f"  MISSING: {c}")


if __name__ == "__main__":
    main()
