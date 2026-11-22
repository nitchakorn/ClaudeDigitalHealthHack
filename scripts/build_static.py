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
from scripts.pitch_section import PITCH_CSS, PITCH_HTML  # noqa: E402
from scripts import rubric_page  # noqa: E402

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
  :root { --bg:#F5F4EE; --panel:#FAF9F5; --line:#DDD8CA; --fg:#1F1E1D; --muted:#66635B; --accent:#B5502E; --brand:#D97757; }
  @media (prefers-color-scheme: dark) { :root { --bg:#262624; --panel:#30302E; --line:#4A4944; --fg:#FAF9F5; --muted:#B8B5A9; --accent:#E08A6D; --brand:#D97757; color-scheme:dark; } }
  * { box-sizing: border-box; }
  body { margin:0; background:var(--bg); color:var(--fg); font:16px/1.55 system-ui, "Segoe UI", sans-serif; padding:48px 20px; }
  main { max-width:820px; margin:0 auto; display:flex; flex-direction:column; gap:22px; }
  h1 { font-size:2.4rem; line-height:1.1; margin:0; }
  h1, h2 { font-family: Georgia, "Times New Roman", serif; font-weight:500; letter-spacing:-0.01em; }
  .event { display:flex; align-items:center; gap:14px; color:inherit; text-decoration:none; }
  .event img { width:56px; height:56px; border-radius:12px; flex:none; }
  .event b { display:block; }
  .event span span { display:block; color:var(--muted); font-size:.92rem; }
  p { margin:0; }
  .lede { color:var(--muted); font-size:1.1rem; max-width:62ch; }
  .cards { display:grid; grid-template-columns:repeat(auto-fit, minmax(260px, 1fr)); gap:16px; }
  a.card { display:block; background:var(--panel); border:1px solid var(--line); border-radius:10px; padding:20px; color:inherit; text-decoration:none; }
  a.card:hover, a.card:focus-visible { border-color:var(--accent); outline:none; }
  a.card b { display:block; font-size:1.15rem; margin-bottom:6px; color:var(--accent); }
  .live { background:var(--panel); border:1px dashed var(--accent); border-radius:10px; padding:18px 20px; display:flex; flex-direction:column; gap:8px; }
  .live h2 { margin:0; }
  .live ol { margin:0; padding-left:20px; display:flex; flex-direction:column; gap:4px; }
  .live a { color:var(--accent); overflow-wrap:anywhere; }
  .live .when { color:var(--muted); font-size:.95rem; }
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
  <a class="event" href="https://claudecommunitynyc.com" rel="noopener"><img src="brand/claude-community-new-york.png" alt="Claude Community New York" width="56" height="56"><span><b>Claude Impact Lab for Digital Health</b><span>with ElevenLabs &middot; Alterra Labs and Claude Community New York</span></span></a>
  <h1>Referral Tracker</h1>
  <p class="lede">Every handoff of a specialist referral writes to one shared record. The patient sees a plain status, each office sees its work queue, and an AI agent drafts the paperwork and flags stalls while people make every decision.</p>
  <div class="cards">
    <a class="card" href="tracker/"><b>Referral tracker</b>Follow one referral through six stages as the patient, the primary care office and the specialist office. Demo scenario: type 2 diabetes to endocrinology.</a>
    <a class="card" href="drafter/"><b>Referral note drafter</b>Pick a patient and a specialty, see the chart extract a specialist needs, and draft the referral note.</a>
<!--eval-card-->
  </div>
  <section class="live">
    <h2>Live AI demo, by arrangement</h2>
    <p class="when">This version runs the real model inside a mock record system on a teammate&rsquo;s computer, so it is only up when we switch it on. To see it, coordinate with us first: message any of us on LinkedIn (links under Team 3 below) and we will set a time.</p>
    <ol>
      <li>Open <a href="https://flaxseed-recital-remnant.ngrok-free.dev/ehr/login?next=/ehr/patients/7e069e5b-aad9-a17d-d819-e318d4421d52/referrals" rel="noopener">the live link</a>. If a notice from ngrok appears first, choose &ldquo;Visit Site&rdquo;.</li>
      <li>Click <b>Sign in as Dana</b>.</li>
      <li>Under <b>Have Fable do it</b>, leave the specialty as Endocrinology.</li>
      <li>Optionally type a question, such as &ldquo;Next step in glucose-lowering treatment?&rdquo;</li>
      <li>Press <b>Run Fable</b>.</li>
    </ol>
  </section>
  <section>
    <h2>Team 3</h2>
    <ul class="team">
      <li><img src="team/george.jpg" alt="George Kapitan" width="64" height="64"><div><b>George Kapitan</b><span>Builder</span><a href="https://www.linkedin.com/in/kapitgeo/" rel="noopener">LinkedIn</a></div></li>
      <li><img src="team/melissa.jpg" alt="Melissa Nguyen" width="64" height="64"><div><b>Melissa Nguyen</b><span>Product Designer</span><a href="https://www.linkedin.com/in/melissanguyennyc/" rel="noopener">LinkedIn</a></div></li>
      <li><img src="team/nitchee.png" alt="Nitchee Tangs, MD" width="64" height="64"><div><b>Nitchee Tangs, MD</b><span>Clinical Product Strategy</span><a href="https://www.linkedin.com/in/nitchakorn/" rel="noopener">LinkedIn</a></div></li>
      <li><img src="team/frank.jpg" alt="Frank Sheikh" width="64" height="64"><div><b>Frank Sheikh</b><span>AI Engineer</span><a href="https://www.linkedin.com/in/franksheikh/" rel="noopener">LinkedIn</a></div></li>
      <li><img src="team/xinyi.webp" alt="Xinyi Shi" width="64" height="64"><div><b>Xinyi Shi</b><span>AI for Mental Health Researcher</span><a href="https://www.linkedin.com/in/xinyi-shi-8a2086342/" rel="noopener">LinkedIn</a></div></li>
      <li><img class="mark" src="team/claude.svg" alt="Claude" width="64" height="64"><div><b>Claude Fable 5.2</b><span>Orchestrator (AI model)</span></div></li>
    </ul>
  </section>
  <p class="note">Prototype built at the Claude Impact Lab for Digital Health in New York. All patients are synthetic (Synthea); no real patient data is used. Office, insurer and specialist actions are simulated, and what you do stays in your own browser. This public demo has no AI model behind it: drafts are labelled templates. Not for clinical use. Code: <a href="https://github.com/nitchakorn/ClaudeDigitalHealthHack">github.com/nitchakorn/ClaudeDigitalHealthHack</a>. Website made by <a href="https://nitchakorn.com" rel="noopener">Nitchee Tangs</a>.</p>
</main>
</body>
</html>
"""


# Claude's cream, ink and orange, laid over each page's own colour tokens.
THEME_TRACKER = """
  :root { --bg:#F5F4EE; --panel:#FAF9F5; --raised:#FFFFFF; --line:#DDD8CA; --line-soft:#E9E5D9; --fg:#1F1E1D; --muted:#66635B;
          --accent:#B5502E; --accent-fg:#FFFFFF; --sel:#F3E0D5; --ctl:#8A867B; }
  @media (prefers-color-scheme: dark) { :root { --bg:#262624; --panel:#30302E; --raised:#3A3A37; --line:#4A4944; --line-soft:#3D3C38;
          --fg:#FAF9F5; --muted:#B8B5A9; --accent:#E08A6D; --accent-fg:#2A1A14; --sel:#4A342B; --ctl:#8C897F; } }
"""
THEME_DRAFTER = """
  :root { --bg:#F5F4EE; --panel:#FAF9F5; --line:#DDD8CA; --fg:#1F1E1D; --muted:#66635B; --accent:#B5502E; --accent-fg:#FFFFFF; --sel:#F3E0D5; }
  @media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { --bg:#262624; --panel:#30302E; --line:#4A4944; --fg:#FAF9F5;
          --muted:#B8B5A9; --accent:#E08A6D; --accent-fg:#2A1A14; --sel:#4A342B; } }
"""


def themed(page: str, theme: str) -> str:
    i = page.index("</style>")
    return page[:i] + theme + page[i:]


# The evaluation report is a page built by eval/build_report.py from the eval run's records
# (run that first to refresh it). When the file is absent the site is built without it.
EVAL_REPORT = ROOT / "eval" / "report" / "index.html"
EVAL_CARD = ('    <a class="card" href="eval/"><b>Note drafter evaluation</b>Three Claude models write the notes, three judge them '
             'against a rubric, and a program checks the format. The method, and what the pilot run found.</a>\n')

RUBRIC = ROOT / "docs" / "referral-note-eval.md"
RUBRIC_CARD = ('    <a class="card" href="eval/rubric/"><b>Evaluation rubric</b>The draft rules for judging a note: seven critical failures, '
               'eight scored criteria, what each specialist needs, and the pass bar. Clinicians are still editing it.</a>\n')


def main() -> None:
    if SITE.exists():
        shutil.rmtree(SITE)

    landing = replace_once(LANDING, "</style>", PITCH_CSS + "</style>")
    landing = replace_once(landing, "<!--eval-card-->\n", (EVAL_CARD if EVAL_REPORT.exists() else "") + RUBRIC_CARD)
    landing = replace_once(landing, '  <p class="note">', PITCH_HTML + '  <p class="note">')
    write(SITE / "index.html", landing)
    shutil.copytree(ROOT / "static" / "team", SITE / "team")
    shutil.copytree(ROOT / "static" / "brand", SITE / "brand")

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
    write(SITE / "tracker" / "index.html", themed(t, THEME_TRACKER))
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
    d = themed(d, THEME_DRAFTER)
    write(SITE / "drafter" / "index.html",
          '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
          '<meta name="viewport" content="width=device-width, initial-scale=1">\n</head>\n<body>\n' + d + "\n</body>\n</html>\n")
    write(SITE / "drafter" / "data.json", json.dumps({
        "system": llm.SYSTEM, "questions_system": llm.QUESTIONS_SYSTEM, "revise_task": llm.REVISE_TASK,
        "as_of": chart.today.isoformat(), "conditions": [condition(k, with_extract=True) for k in CONDITIONS],
    }, ensure_ascii=False))

    # ---- evaluation report: the standalone page, wrapped as a full document ----
    if EVAL_REPORT.exists():
        e = EVAL_REPORT.read_text(encoding="utf-8")
        e = replace_once(e, "<!--site:nav-->", '<a class="back" href="../">&larr; Referral Tracker</a> &nbsp;&middot;&nbsp; <a class="back" href="rubric/">Rubric</a>')
        e = replace_once(e, "</main>", '<p class="note">' + rubric_page.MADE_BY + "</p>\n</main>")
        write(SITE / "eval" / "index.html",
              '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
              '<meta name="viewport" content="width=device-width, initial-scale=1">\n</head>\n<body>\n' + e + "\n</body>\n</html>\n")

    # ---- evaluation rubric: the team's shared document, rendered from its markdown export ----
    write(SITE / "eval" / "rubric" / "index.html", rubric_page.build(RUBRIC.read_text(encoding="utf-8")))

    size = sum(f.stat().st_size for f in SITE.rglob("*") if f.is_file())
    print(f"built {SITE} ({size / 1024:.0f} KB, {sum(1 for f in SITE.rglob('*') if f.is_file())} files)")


if __name__ == "__main__":
    main()
