"""The evaluation rubric page of the public site.

Renders docs/referral-note-eval.md (an export of the team's Referral Note Eval document) to
HTML. The converter covers only what that document uses: headings, paragraphs, pipe tables,
bullet, numbered and task lists, fenced code, bold and links.
"""

from __future__ import annotations

import html
import re

MADE_BY = 'Website made by <a href="https://nitchakorn.com" rel="noopener">Nitchee Tangs</a>.'

CSS = """
  :root { --bg:#F5F4EE; --panel:#FAF9F5; --line:#DDD8CA; --fg:#1F1E1D; --muted:#66635B; --accent:#B5502E; --soft:#F3E0D5; }
  @media (prefers-color-scheme: dark) {
    :root:not([data-theme="light"]) { --bg:#262624; --panel:#30302E; --line:#4A4944; --fg:#FAF9F5; --muted:#B8B5A9; --accent:#E08A6D; --soft:#4A342B; color-scheme:dark; }
  }
  :root[data-theme="dark"] { --bg:#262624; --panel:#30302E; --line:#4A4944; --fg:#FAF9F5; --muted:#B8B5A9; --accent:#E08A6D; --soft:#4A342B; color-scheme:dark; }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--bg); color:var(--fg); font:16px/1.55 system-ui, -apple-system, "Segoe UI", sans-serif; }
  main { max-width:980px; margin:0 auto; padding:44px 20px 64px; display:flex; flex-direction:column; gap:16px; }
  h1, h2 { font-family:Georgia, "Times New Roman", serif; font-weight:500; letter-spacing:-0.01em; margin:0; text-wrap:balance; }
  h1 { font-size:2.4rem; line-height:1.1; }
  h2 { font-size:1.5rem; line-height:1.2; border-top:1px solid var(--line); padding-top:26px; margin-top:10px; }
  p, ul, ol { margin:0; max-width:72ch; }
  ul, ol { padding-left:22px; display:flex; flex-direction:column; gap:6px; }
  ol li::marker { color:var(--accent); font-weight:700; }
  ul.tasks { list-style:none; padding-left:0; }
  ul.tasks li { display:grid; grid-template-columns:16px 1fr; gap:10px; align-items:start; }
  ul.tasks li::before { content:""; width:14px; height:14px; margin-top:5px; border:1.5px solid var(--muted); border-radius:3px; }
  a { color:var(--accent); }
  .nav { display:flex; flex-wrap:wrap; gap:6px 18px; font-size:.95rem; }
  .nav a { text-decoration:none; }
  .nav a:hover { text-decoration:underline; }
  .eyebrow { font-size:.85rem; font-weight:600; letter-spacing:.06em; text-transform:uppercase; color:var(--accent); }
  .status { background:var(--panel); border:1px dashed var(--accent); border-radius:10px; padding:16px 20px; max-width:none; }
  .scroll { overflow-x:auto; }
  table { border-collapse:collapse; width:100%; min-width:620px; font-size:.95rem; }
  th, td { text-align:left; vertical-align:top; padding:9px 12px; border-bottom:1px solid var(--line); }
  th { font-size:.8rem; letter-spacing:.05em; text-transform:uppercase; color:var(--muted); font-weight:600; vertical-align:bottom; }
  td:first-child { font-weight:600; }
  td.fb { background:var(--soft); }
  pre { margin:0; background:var(--panel); border:1px solid var(--line); border-radius:10px; padding:14px 16px; overflow-x:auto;
        font:.84rem/1.65 ui-monospace, "Cascadia Mono", Consolas, "Courier New", monospace; }
  .note { border-top:1px solid var(--line); padding-top:16px; margin-top:10px; color:var(--muted); font-size:.95rem; max-width:none; }
"""

FEEDBACK_HEADERS = {"Clinician correction", "Clinician edit", "Keep, change or drop"}


def inline(text: str) -> str:
    text = text.replace("\\[", "[").replace("\\]", "]")
    text = html.escape(text, quote=False)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    return re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", r'<a href="\2" rel="noopener">\1</a>', text)


def table(rows: list[list[str]]) -> str:
    head, body = rows[0], rows[2:]
    keep = [i for i, h in enumerate(head) if h or any(i < len(r) and r[i] for r in body)]
    fb = {i for i in keep if head[i] in FEEDBACK_HEADERS}
    out = ['<div class="scroll"><table>', "<thead><tr>" + "".join(f"<th>{inline(head[i])}</th>" for i in keep) + "</tr></thead>", "<tbody>"]
    for r in body:
        cells = "".join(f'<td{" class=\"fb\"" if i in fb and r[i] else ""}>{inline(r[i])}</td>' for i in keep)
        out.append(f"<tr>{cells}</tr>")
    out.append("</tbody></table></div>")
    return "\n".join(out)


def render(md: str) -> str:
    lines = md.splitlines()
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
        elif line.startswith("```"):
            j = i + 1
            while not lines[j].startswith("```"):
                j += 1
            out.append("<pre>" + html.escape("\n".join(lines[i + 1:j]), quote=False) + "</pre>")
            i = j + 1
        elif line.startswith("## "):
            out.append(f"<h2>{inline(line[3:])}</h2>")
            i += 1
        elif line.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            out.append(table(rows))
        elif line.startswith("- "):
            items = []
            while i < len(lines) and lines[i].startswith("- "):
                items.append(lines[i][2:])
                i += 1
            tasks = all(t.startswith("[ ] ") for t in items)
            lis = "".join(f"<li><span>{inline(t[4:])}</span></li>" if tasks else f"<li>{inline(t)}</li>" for t in items)
            out.append(f'<ul class="tasks">{lis}</ul>' if tasks else f"<ul>{lis}</ul>")
        elif re.match(r"\d+\. ", line):
            items = []
            while i < len(lines) and re.match(r"\d+\. ", lines[i]):
                items.append(re.sub(r"^\d+\. ", "", lines[i]))
                i += 1
            out.append("<ol>" + "".join(f"<li>{inline(t)}</li>" for t in items) + "</ol>")
        else:
            out.append(f"<p>{inline(line)}</p>")
            i += 1
    return "\n".join(out)


def build(md: str) -> str:
    """The whole page. The document's own title and byline are replaced by the page header."""
    body = md.split("\n\n", 2)[2]
    # The source links to the team's private drafter artifact; the public page links to the public drafter.
    body = re.sub(r"\(https://claude\.ai/artifact/[^)]+\)", "(../../drafter/)", body, count=1)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Referral Note Eval Rubric</title>
<style>{CSS}</style>
</head>
<body>
<main>
  <p class="nav"><a href="../../">&larr; Referral Tracker</a><a href="../">Evaluation report</a></p>
  <p class="eyebrow">Evaluation &middot; rubric, draft of 21 November 2026</p>
  <h1>How we judge a referral note</h1>
  <p class="status">This is the team&rsquo;s working draft, copied from a shared document that clinicians are still editing. Shaded cells are clinician comments that have not been applied yet. The <a href="../">evaluation report</a> shows what the first run found.</p>
{render(body)}
  <p class="note">All patients are synthetic (Synthea); no real patient data is used. Not for clinical use. {MADE_BY}</p>
</main>
</body>
</html>
"""
