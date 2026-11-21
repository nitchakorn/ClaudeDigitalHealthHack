"""Builds site/: a static public demo that needs no server.

    .venv/Scripts/python scripts/build_static.py      (or: npm run build:static)

The tracker and the note drafter run entirely in the browser on bundled synthetic data.
There is no model behind them: drafts are labelled templates and patient messages are
routed by the keyword rule. The live app (npm run dev) is unchanged.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import llm  # noqa: E402
from app.data import CONDITIONS, Chart  # noqa: E402

SITE = ROOT / "site"
chart = Chart()


def patients(key: str, with_extract: bool) -> list[dict]:
    out = []
    for p in chart.cohort(key):
        e = chart.extract(p["id"], key)
        row = {
            **p,
            "problems": [name for _, name in e["relevant_problems"]],
            "meds": sorted(e["active_meds"]),
            "allergies": e["allergies"],
            "results": [[r["label"], r["latest"][1], r["latest"][0]] for r in e["results"][:8]],
        }
        if with_extract:
            row["extract"] = e["text"]
        out.append(row)
    return out


def condition(key: str, with_extract: bool) -> dict:
    cfg = CONDITIONS[key]
    return {
        "key": key, "label": cfg["label"], "specialty": cfg["specialty"], "guidance": cfg["guidance"],
        "fallback_questions": [{"question": q, "why": w} for q, w in llm.FALLBACK_QUESTIONS[key]],
        "patients": patients(key, with_extract),
    }


def replace_once(text: str, old: str, new: str) -> str:
    assert text.count(old) == 1, (old[:70], text.count(old))
    return text.replace(old, new)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


LANDING = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Referral Tracker</title>
<style>
  :root { --bg:#f3f6f8; --panel:#fff; --line:#c9d3dc; --fg:#16263a; --muted:#5a6b7d; --accent:#0b7a75; }
  @media (prefers-color-scheme: dark) { :root { --bg:#0f171e; --panel:#18232d; --line:#34444f; --fg:#e3ebf2; --muted:#93a4b5; --accent:#56c7c0; color-scheme:dark; } }
  * { box-sizing: border-box; }
  body { margin:0; background:var(--bg); color:var(--fg); font:16px/1.55 system-ui, "Segoe UI", sans-serif; padding:48px 20px; }
  main { max-width:820px; margin:0 auto; display:flex; flex-direction:column; gap:22px; }
  h1 { font-size:2rem; line-height:1.15; margin:0; }
  p { margin:0; }
  .lede { color:var(--muted); font-size:1.1rem; max-width:62ch; }
  .cards { display:grid; grid-template-columns:repeat(auto-fit, minmax(260px, 1fr)); gap:16px; }
  a.card { display:block; background:var(--panel); border:1px solid var(--line); border-radius:10px; padding:20px; color:inherit; text-decoration:none; }
  a.card:hover, a.card:focus-visible { border-color:var(--accent); outline:none; }
  a.card b { display:block; font-size:1.15rem; margin-bottom:6px; color:var(--accent); }
  .eyebrow { font-size:.85rem; font-weight:600; letter-spacing:.06em; text-transform:uppercase; color:var(--accent); }
  h2 { font-size:1.15rem; margin:0 0 10px; }
  .team { list-style:none; margin:0; padding:0; display:grid; grid-template-columns:repeat(auto-fit, minmax(230px, 1fr)); gap:10px 24px; }
  .team li { display:flex; align-items:center; gap:12px; border-top:1px solid var(--line); padding-top:10px; }
  .team img { width:64px; height:64px; border-radius:50%; object-fit:cover; flex:none; background:#e9eef2; }
  .team img.mark { object-fit:contain; padding:12px; background:#f6e3d2; }
  .team b { display:block; }
  .team span { display:block; color:var(--muted); font-size:.95rem; }
  .team a { color:var(--accent); font-size:.9rem; }
  .note { border-top:1px solid var(--line); padding-top:16px; color:var(--muted); font-size:.95rem; }
  .note a { color:var(--accent); }
</style>
</head>
<body>
<main>
  <p class="eyebrow">Claude Digital Health Hack</p>
  <h1>Referral Tracker</h1>
  <p class="lede">Every handoff of a specialist referral writes to one shared record. The patient sees a plain status, each office sees its work queue, and an AI agent drafts the paperwork and flags stalls while people make every decision.</p>
  <div class="cards">
    <a class="card" href="tracker/"><b>Referral tracker</b>Follow one referral through six stages as the patient, the primary care office and the specialist office. Demo scenario: type 2 diabetes to endocrinology.</a>
    <a class="card" href="drafter/"><b>Referral note drafter</b>Pick a patient and a specialty, see the chart extract a specialist needs, and draft the referral note.</a>
  </div>
  <section>
    <h2>Team</h2>
    <ul class="team">
      <li><img src="team/george.jpg" alt="George Kapitan" width="64" height="64"><div><b>George Kapitan</b><span>Growth and Marketing</span><a href="https://www.linkedin.com/in/kapitgeo/" rel="noopener">LinkedIn</a></div></li>
      <li><img src="team/melissa.jpg" alt="Melissa Nguyen" width="64" height="64"><div><b>Melissa Nguyen</b><span>Solution Design and Branding</span><a href="https://www.linkedin.com/in/melissanguyennyc/" rel="noopener">LinkedIn</a></div></li>
      <li><img src="team/nitchee.png" alt="Nitchee Tangs, MD" width="64" height="64"><div><b>Nitchee Tangs, MD</b><span>Clinical Product Strategy</span><a href="https://www.linkedin.com/in/nitchakorn/" rel="noopener">LinkedIn</a></div></li>
      <li><img src="team/frank.jpg" alt="Frank Sheikh" width="64" height="64"><div><b>Frank Sheikh</b><span>AI Engineer</span><a href="https://www.linkedin.com/in/franksheikh/" rel="noopener">LinkedIn</a></div></li>
      <li><img src="team/xinyi.webp" alt="Xinyi Shi, MD" width="64" height="64"><div><b>Xinyi Shi, MD</b><span>Evaluation</span><a href="https://www.linkedin.com/in/xinyi-shi-8a2086342/" rel="noopener">LinkedIn</a></div></li>
      <li><img class="mark" src="team/claude.svg" alt="Claude" width="64" height="64"><div><b>Claude Fable 5.2</b><span>Orchestrator (AI model)</span></div></li>
    </ul>
  </section>
  <p class="note">Hackathon prototype built at the Claude Digital Health Hack. All patients are synthetic (Synthea); no real patient data is used. Office, insurer and specialist actions are simulated, and what you do stays in your own browser. This public demo has no AI model behind it: drafts are labelled templates. Not for clinical use. Code: <a href="https://github.com/nitchakorn/ClaudeDigitalHealthHack">github.com/nitchakorn/ClaudeDigitalHealthHack</a></p>
</main>
</body>
</html>
"""


def main() -> None:
    if SITE.exists():
        shutil.rmtree(SITE)

    write(SITE / "index.html", LANDING)
    shutil.copytree(ROOT / "static" / "team", SITE / "team")

    # ---- tracker: same page as the live app, pointed at bundled files ----
    t = (ROOT / "static" / "tracker.html").read_text(encoding="utf-8")
    t = replace_once(t, "fetch('/api/tracker/data')", "fetch('data.json')")
    t = replace_once(t, "fetch('/api/health')", "fetch('health.json')")
    t = replace_once(t, '<a href="/" style="color:inherit">Open the note drafter</a>',
                     '<a href="../drafter/" style="color:inherit">Open the note drafter</a>')
    t = replace_once(t, "'Claude: no API key on the server, template drafts only'",
                     "'Public demo: template drafts, no AI model'")
    t = replace_once(t, "'No API key is set on the server, so this creates a labeled template from chart fields.'",
                     "'This public demo has no AI model, so this creates a labeled template from chart fields.'")
    write(SITE / "tracker" / "index.html", t)
    endo = condition("endo", with_extract=False)
    write(SITE / "tracker" / "data.json", json.dumps({"as_of": chart.today.isoformat(), "condition": endo}, ensure_ascii=False))
    write(SITE / "tracker" / "health.json", json.dumps({"mode": "mock", "model": "", "effort": ""}))

    # ---- drafter: the standalone page, wrapped as a full document ----
    d = (ROOT / "artifact" / "index.html").read_text(encoding="utf-8")
    d = replace_once(d, '<span id="mode" class="chip">Checking for Claude…</span>',
                     '<span id="mode" class="chip">Checking for Claude…</span>\n  <a class="sub" href="../tracker/">Referral tracker</a>')
    d = replace_once(d, "'Template only: Claude unavailable in this view'", "'Public demo: template drafts, no AI model'")
    d = replace_once(d, "'[TEMPLATE DRAFT: Claude is unavailable in this view, so this text is not model output]'",
                     "'[TEMPLATE DRAFT: this public demo has no AI model, so this text is not model output]'")
    write(SITE / "drafter" / "index.html",
          '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
          '<meta name="viewport" content="width=device-width, initial-scale=1">\n</head>\n<body>\n' + d + "\n</body>\n</html>\n")
    write(SITE / "drafter" / "data.json", json.dumps({
        "system": llm.SYSTEM, "questions_system": llm.QUESTIONS_SYSTEM, "revise_task": llm.REVISE_TASK,
        "as_of": chart.today.isoformat(), "conditions": [condition(k, with_extract=True) for k in CONDITIONS],
    }, ensure_ascii=False))

    size = sum(f.stat().st_size for f in SITE.rglob("*") if f.is_file())
    print(f"built {SITE} ({size / 1024:.0f} KB, {sum(1 for f in SITE.rglob('*') if f.is_file())} files)")


if __name__ == "__main__":
    main()
