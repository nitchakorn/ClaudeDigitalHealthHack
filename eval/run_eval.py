"""Referral Note Eval runner: three Claude models write each note, three Claude models judge it.

Framework: the Referral Note Eval doc (rubric copied into rubric.py). The drafter's own code builds
every prompt (app/llm.py SYSTEM and build_context, app/data.py chart extract), so the eval cannot
drift from the app. Differences from the app's live call, on purpose: no streaming and no refusal
fallback (a fallback would silently swap the model being compared), and a 16,000-token ceiling
instead of 64,000 (a note that hits it is recorded as truncated, not scored).

Run with the project's Python from the repo root:
  .venv/Scripts/python.exe eval/run_eval.py selftest        offline checks, no API call
  .venv/Scripts/python.exe eval/run_eval.py check           is the key accepted (free)
  .venv/Scripts/python.exe eval/run_eval.py plan            counts and projected cost
  .venv/Scripts/python.exe eval/run_eval.py pilot           3 build cases, live, plus judge probes
  .venv/Scripts/python.exe eval/run_eval.py write --stage build     submit a half-price batch
  .venv/Scripts/python.exe eval/run_eval.py collect [--wait]        fetch finished batches
  .venv/Scripts/python.exe eval/run_eval.py judge --stage build
  .venv/Scripts/python.exe eval/run_eval.py score --stage build

The API key is read from a file outside the repo (KEY_FILE) and never printed.
"""
from __future__ import annotations

import argparse
import hashlib
import inspect
import itertools
import json
import re
import statistics
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

import anthropic  # noqa: E402
from anthropic.types.message_create_params import MessageCreateParamsNonStreaming  # noqa: E402
from anthropic.types.messages.batch_create_params import Request  # noqa: E402

import rubric  # noqa: E402
from app import llm  # noqa: E402
from app.data import Chart  # noqa: E402

KEY_FILE = Path.home() / ".referral-eval" / "anthropic-key.txt"
MODELS = {"opus": "claude-opus-5-5", "sonnet": "claude-sonnet-5-5", "haiku": "claude-haiku-5-5"}
WRITERS = ["opus", "sonnet", "haiku"]
JUDGES = ["opus", "sonnet", "haiku"]
PRICES = {"opus": (4.00, 20.00), "sonnet": (2.00, 10.00), "haiku": (0.10, 0.50)}  # $/MTok (in, out), checked 2026-11-21
BATCH_DISCOUNT = 0.5
BUDGET_USD = 50.0
WRITER_EFFORT = llm.EFFORT   # the app's own setting
JUDGE_EFFORT = "high"
MAX_TOKENS = 16000
WRITE_SUFFIX = "\n\nWrite the referral note."   # the same words app/llm.py draft() appends; selftest checks this
REPS = {"build": 1, "carry": 1, "test": 3}
PILOT_CASES = ["cardiac-7208c12f", "cardiac-ab51950f", "cardiac-d50b22fc"]
ASSUMED = {"write": (4000, 4000), "judge": (5600, 7000)}  # high-side tokens (in, out) until something is measured
LOCK = threading.Lock()
CONFIG = hashlib.sha256(json.dumps(
    [llm.SYSTEM, WRITER_EFFORT, WRITE_SUFFIX, rubric.GRADER_SYSTEM, rubric.FAILURES, rubric.CRITERIA,
     rubric.SPECIALIST_NEEDS, JUDGE_EFFORT, MODELS], sort_keys=True).encode()).hexdigest()[:10]


# ---------- files ----------
def run_dir(name: str) -> Path:
    d = HERE / "runs" / name
    (d / "traces").mkdir(parents=True, exist_ok=True)
    return d


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def append_jsonl(path: Path, row: dict) -> None:
    with LOCK, open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ---------- key and client ----------
def load_key() -> str:
    raw = KEY_FILE.read_text(encoding="utf-8-sig") if KEY_FILE.exists() else ""
    key = raw.strip().strip("\"'")
    if key.upper().startswith("ANTHROPIC_API_KEY="):
        key = key.split("=", 1)[1].strip()
    if not key:
        sys.exit(f"No API key yet. Paste it into {KEY_FILE} and save.")
    return key


def client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=load_key(), max_retries=4, timeout=900.0)


# ---------- cases and prompts ----------
class Cases:
    def __init__(self) -> None:
        self.chart = Chart()
        self.meta = json.loads((HERE / "cases.json").read_text(encoding="utf-8"))
        self.by_id: dict[str, dict] = {}
        for c in self.meta["cases"]:
            prefix = c["id"].split("-", 1)[1]
            pids = [p for p in self.chart.patients if p.startswith(prefix)]
            if len(pids) != 1:
                sys.exit(f"{c['id']}: expected one patient with id starting {prefix}, found {len(pids)}")
            c["patient_id"] = pids[0]
            self.by_id[c["id"]] = c
        self._extracts: dict[str, dict] = {}

    def extract(self, case: dict) -> dict:
        if case["id"] not in self._extracts:
            self._extracts[case["id"]] = self.chart.extract(case["patient_id"], case["condition"])
        return self._extracts[case["id"]]

    def stage(self, stage: str) -> list[dict]:
        if stage == "pilot":
            return [self.by_id[i] for i in PILOT_CASES]
        return [c for c in self.by_id.values() if c["split"] == stage]


def writer_params(cs: Cases, case: dict, writer: str) -> dict:
    prompt = llm.build_context(cs.extract(case), case["question"], case["urgency"], case["notes"]) + WRITE_SUFFIX
    return {"model": MODELS[writer], "max_tokens": MAX_TOKENS, "system": llm.SYSTEM,
            "output_config": {"effort": WRITER_EFFORT}, "messages": [{"role": "user", "content": prompt}]}


def judge_params(cs: Cases, case: dict, note: str, judge: str) -> dict:
    return {"model": MODELS[judge], "max_tokens": MAX_TOKENS, "system": rubric.GRADER_SYSTEM,
            "output_config": {"effort": JUDGE_EFFORT, "format": {"type": "json_schema", "schema": rubric.JUDGE_SCHEMA}},
            "messages": [{"role": "user", "content": rubric.judge_user_message(cs.extract(case)["text"], case, note)}]}


# ---------- program checks (C8 format, F4 urgency) ----------
MARKDOWN = re.compile(r"(\*\*[^*\n]+\*\*|__[^_\n]+__|^#{1,6}\s|`[^`\n]+`|^\s*\|.*\|\s*$|\[[^\]\n]+\]\([^)\n]+\))", re.M)
GREETING = re.compile(r"^\s*(dear\b|hi\b|hello\b|to whom)|\b(sincerely|kind regards|best regards|yours (truly|faithfully|sincerely)"
                      r"|thank you for seeing)\b", re.I | re.M)
LEVEL = r"(routine|urgent|emergent)"
URGENCY_PATTERNS = [rf"urgency\W{{0,12}}{LEVEL}\b", rf"\b{LEVEL}\s+(?:referral|priority|review|assessment|appointment|basis|consultation|evaluation)",
                    rf"referr\w+\s+(?:as|on an?|for)\s+(?:an?\s+)?{LEVEL}\b", rf"\(\s*{LEVEL}\s*\)", rf"\b{LEVEL}ly\s+referr"]


def check_format(note: str) -> dict:
    lines = [line.strip() for line in note.splitlines()]
    pos = [next((i for i, line in enumerate(lines) if line.rstrip(":").strip() == h), None) for h in rubric.HEADINGS]
    missing = [h for h, p in zip(rubric.HEADINGS, pos) if p is None]
    words = len(re.findall(r"\S*[A-Za-z0-9]\S*", note))   # a bare bullet dash is not a word
    first = next((line for line in lines if line), "")
    major, minor = [], []
    if missing:
        major.append("missing headings: " + ", ".join(missing))
    elif pos != sorted(pos):
        major.append("headings out of order")
    if words < 200 or words > 480:
        major.append(f"{words} words, well outside 250 to 400")
    elif words < 250 or words > 400:
        minor.append(f"{words} words, outside 250 to 400")
    if MARKDOWN.search(note):
        minor.append("markdown")
    if first.rstrip(":").strip() != rubric.HEADINGS[0] or GREETING.search(note):
        minor.append("greeting, sign-off or text before the first heading")
    return {"c8": 0 if major else (1 if minor else 2), "words": words, "issues": major + minor}


def check_urgency(note: str, selected: str) -> str:
    low = note.lower().replace("non-urgent", "routine").replace("urgent care", "urgent-care")
    stated = {m.group(1) for pat in URGENCY_PATTERNS for m in re.finditer(pat, low)}
    if not stated:
        return "not_stated"
    if stated == {selected}:
        return "match"
    return "mixed" if selected in stated else "mismatch"


# ---------- cost ----------
def usage_dict(u) -> dict:
    return {k: getattr(u, k, 0) or 0 for k in ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")}


def cost_usd(model_key: str, u: dict, batch: bool) -> float:
    pin, pout = PRICES[model_key]
    c = (u["input_tokens"] * pin + u["cache_creation_input_tokens"] * pin * 1.25 + u["cache_read_input_tokens"] * pin * 0.1
         + u["output_tokens"] * pout) / 1e6
    return c * (BATCH_DISCOUNT if batch else 1.0)


def rows(run: Path, kind: str) -> list[dict]:
    return read_jsonl(run / {"write": "notes.jsonl", "judge": "judgments.jsonl", "probe": "probes.jsonl"}[kind])


def spent(run: Path) -> float:
    return sum(r.get("cost_usd", 0) for k in ("write", "judge", "probe") for r in rows(run, k)) + \
        sum(r.get("cost_usd", 0) for r in read_jsonl(run / "errors.jsonl"))


def per_call(run: Path, kind: str, model_key: str, batch: bool) -> tuple[float, bool]:
    """Projected dollars for one call; measured from this run's own rows when there are any."""
    done = [r for r in rows(run, kind) if r["model_key"] == model_key and r.get("usage")]
    if done:
        u = {k: statistics.mean(r["usage"][k] for r in done) for k in done[0]["usage"]}
        return cost_usd(model_key, u, batch), True
    i, o = ASSUMED[kind]
    return cost_usd(model_key, {"input_tokens": i, "output_tokens": o, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}, batch), False


def batches(run: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for r in read_jsonl(run / "batches.jsonl"):
        out.setdefault(r["id"], {}).update(r)
    return out


def guard(run: Path, jobs: list[tuple[str, str]], batch: bool, force: bool) -> float:
    projected = sum(per_call(run, kind, mk, batch)[0] for kind, mk in jobs)
    pending = sum(b.get("projected_usd", 0) for b in batches(run).values() if not b.get("collected"))
    total = spent(run) + pending + projected
    print(f"Spent so far ${spent(run):.2f}, waiting in batches ${pending:.2f}, this step about ${projected:.2f}: total ${total:.2f} of ${BUDGET_USD:.0f}.")
    if total > BUDGET_USD and not force:
        sys.exit("That would pass the budget. Nothing was sent. (--force overrides.)")
    return projected


# ---------- recording results ----------
def text_of(msg) -> str:
    return "".join(b.text for b in msg.content if b.type == "text").strip()


def status_of(msg) -> str:
    return {"end_turn": "ok", "max_tokens": "truncated", "refusal": "refusal"}.get(msg.stop_reason, str(msg.stop_reason))


def note_id(case_id: str, writer: str, rep: int) -> str:
    return f"{case_id}__{writer}__r{rep}"


def record_note(run: Path, cs: Cases, nid: str, msg, batch: bool) -> None:
    case_id, writer, rep = nid.split("__")
    case = cs.by_id[case_id]
    u, text = usage_dict(msg.usage), text_of(msg)
    if not msg.model.startswith(MODELS[writer]):
        return record_error(run, nid, "write", f"served by {msg.model}, asked for {MODELS[writer]}", writer, u, batch)
    row = {"id": nid, "case_id": case_id, "split": case["split"], "condition": case["condition"], "writer": writer,
           "model_key": writer, "model": msg.model, "rep": int(rep[1:]), "status": status_of(msg), "stop_reason": msg.stop_reason,
           "text": text, "format": check_format(text), "urgency_check": check_urgency(text, case["urgency"]),
           "usage": u, "cost_usd": cost_usd(writer, u, batch), "batch": batch, "config": CONFIG, "at": now()}
    params = writer_params(cs, case, writer)
    (run / "traces" / f"{nid}.json").write_text(json.dumps(
        [{"role": "system", "content": params["system"]}, {"role": "user", "content": params["messages"][0]["content"]},
         {"role": "assistant", "content": text}], ensure_ascii=False, indent=1), encoding="utf-8")
    append_jsonl(run / "notes.jsonl", row)


def record_judgment(run: Path, jid: str, msg, batch: bool, probe: str | None = None) -> None:
    nid, judge = jid.rsplit("__j-", 1)
    u, text, status = usage_dict(msg.usage), text_of(msg), status_of(msg)
    if not msg.model.startswith(MODELS[judge]):
        return record_error(run, jid, "judge", f"served by {msg.model}, asked for {MODELS[judge]}", judge, u, batch)
    out = None
    if status == "ok":
        try:
            out = json.loads(text)
            failures = {k: out["critical_failures"][k]["verdict"] for k in rubric.FAILURES}
            scores = {k: int(out["criteria"][k]["score"]) for k in rubric.CRITERIA}
        except (ValueError, KeyError, TypeError) as e:
            return record_error(run, jid, "judge", f"unreadable judge output: {type(e).__name__}", judge, u, batch)
    if out is None:
        return record_error(run, jid, "judge", f"judge output {status}", judge, u, batch)
    row = {"id": jid, "note_id": nid, "judge": judge, "model_key": judge, "model": msg.model, "status": "ok",
           "failures": failures, "scores": scores, "n_statements": len(out["statements"]),
           "n_no_source": sum(1 for s in out["statements"] if s["source"].strip().lower().startswith("no source")),
           "usage": u, "cost_usd": cost_usd(judge, u, batch), "batch": batch, "config": CONFIG, "at": now()}
    if probe:
        row["probe"] = probe
    (run / "traces" / f"{jid}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    append_jsonl(run / ("probes.jsonl" if probe else "judgments.jsonl"), row)


def record_error(run: Path, item: str, kind: str, error: str, model_key: str = "", usage: dict | None = None, batch: bool = False) -> None:
    row = {"id": item, "kind": kind, "error": error, "at": now()}
    if usage:
        row.update(usage=usage, cost_usd=cost_usd(model_key, usage, batch))
    append_jsonl(run / "errors.jsonl", row)
    print(f"  ! {item}: {error}")


# ---------- work lists ----------
def write_jobs(run: Path, cs: Cases, stage: str) -> list[str]:
    have = {r["id"] for r in rows(run, "write")}
    reps = 1 if stage == "pilot" else REPS[stage]
    return [nid for c in cs.stage(stage) for w in WRITERS for k in range(reps)
            if (nid := note_id(c["id"], w, k)) not in have]


def judge_jobs(run: Path, cs: Cases, stage: str) -> list[tuple[str, dict]]:
    have = {r["id"] for r in rows(run, "judge")}
    ids = {c["id"] for c in cs.stage(stage)}
    return [(jid, n) for n in rows(run, "write") if n["case_id"] in ids and n["status"] == "ok"
            for j in JUDGES if (jid := f"{n['id']}__j-{j}") not in have]


def call(cl: anthropic.Anthropic, run: Path, item: str, kind: str, params: dict):
    """One live call. Returns the message, or None after writing the failure to errors.jsonl."""
    try:
        return cl.messages.create(**params)
    except anthropic.BadRequestError as e:
        record_error(run, item, kind, f"bad request: {e.message}")
    except (anthropic.AuthenticationError, anthropic.PermissionDeniedError) as e:
        record_error(run, item, kind, f"key problem: {e.message}")
    except anthropic.RateLimitError:
        record_error(run, item, kind, "rate limited after retries")
    except anthropic.APIStatusError as e:
        record_error(run, item, kind, f"API error {e.status_code}: {e.message}")
    except anthropic.APIConnectionError as e:
        record_error(run, item, kind, f"network: {type(e).__name__}")
    return None


def do_writes(run: Path, cs: Cases, ids: list[str], batch: bool, stage: str, projected: float) -> None:
    cl = client()
    params = {nid: writer_params(cs, cs.by_id[nid.split("__")[0]], nid.split("__")[1]) for nid in ids}
    if batch:
        return submit(cl, run, "write", stage, params, projected)

    def one(nid: str) -> None:
        msg = call(cl, run, nid, "write", params[nid])
        if msg is not None:
            record_note(run, cs, nid, msg, False)
    with ThreadPoolExecutor(3) as pool:
        list(pool.map(one, ids))


def do_judging(run: Path, cs: Cases, jobs: list[tuple[str, dict, str, str | None]], batch: bool, stage: str, projected: float) -> None:
    """jobs: (judgment id, case, note text, probe name or None)."""
    cl = client()
    params = {jid: judge_params(cs, case, text, jid.rsplit("__j-", 1)[1]) for jid, case, text, _ in jobs}
    if batch:
        return submit(cl, run, "judge", stage, params, projected)

    def one(job) -> None:
        jid, _, _, probe = job
        msg = call(cl, run, jid, "judge", params[jid])
        if msg is not None:
            record_judgment(run, jid, msg, False, probe)
    with ThreadPoolExecutor(3) as pool:
        list(pool.map(one, jobs))


def submit(cl: anthropic.Anthropic, run: Path, kind: str, stage: str, params: dict[str, dict], projected: float) -> None:
    b = cl.messages.batches.create(requests=[Request(custom_id=i, params=MessageCreateParamsNonStreaming(**p)) for i, p in params.items()])
    append_jsonl(run / "batches.jsonl", {"id": b.id, "kind": kind, "stage": stage, "n": len(params), "projected_usd": round(projected, 2), "at": now()})
    print(f"Batch {b.id} submitted: {len(params)} {kind} calls. Fetch it later with: collect")


def collect(run: Path, cs: Cases, wait: bool) -> bool:
    cl = client()
    pending = [b for b in batches(run).values() if not b.get("collected")]
    if not pending:
        print("No batches waiting.")
        return True
    all_done = True
    for b in pending:
        while True:
            info = cl.messages.batches.retrieve(b["id"])
            c = info.request_counts
            print(f"{b['id']} ({b['kind']}, {b['stage']}): {info.processing_status}; done {c.succeeded}, failed {c.errored}, in progress {c.processing}")
            if info.processing_status == "ended" or not wait:
                break
            time.sleep(30)
        if info.processing_status != "ended":
            all_done = False
            continue
        for r in cl.messages.batches.results(b["id"]):
            if r.result.type == "succeeded":
                (record_note(run, cs, r.custom_id, r.result.message, True) if b["kind"] == "write"
                 else record_judgment(run, r.custom_id, r.result.message, True))
            else:
                detail = getattr(getattr(r.result, "error", None), "type", "") or ""
                record_error(run, r.custom_id, b["kind"], f"batch result {r.result.type} {detail}".strip())
        append_jsonl(run / "batches.jsonl", {"id": b["id"], "collected": True, "collected_at": now()})
    return all_done


# ---------- scoring ----------
def kappa(a: list[bool], b: list[bool]) -> float | None:
    n = len(a)
    if not n:
        return None
    po = sum(x == y for x, y in zip(a, b)) / n
    pa, pb = sum(a) / n, sum(b) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    return None if pe == 1 else (po - pe) / (1 - pe)


def score_notes(notes: list[dict], judgments: list[dict]) -> list[dict]:
    """One scored row per usable note. A judge fails a note when it marks any critical failure 'yes'."""
    by_note: dict[str, dict[str, dict]] = {}
    for j in judgments:
        by_note.setdefault(j["note_id"], {})[j["judge"]] = j
    out = []
    for n in notes:
        js = by_note.get(n["id"], {})
        if n["status"] != "ok" or not js:
            continue
        fails = {j: [f for f, v in r["failures"].items() if v == "yes"] for j, r in js.items()}
        review = {j: [f for f, v in r["failures"].items() if v == "for clinician review"] for j, r in js.items()}
        n_fail = sum(1 for f in fails.values() if f)
        program_f4 = n["urgency_check"] == "mismatch"
        totals = {j: sum(r["scores"].values()) for j, r in js.items()}
        out.append({**{k: n[k] for k in ("id", "case_id", "split", "condition", "writer")}, "judges": sorted(js),
                    "fails": fails, "review": review, "n_fail": n_fail, "program_f4": program_f4,
                    "confirmed": n_fail >= 2 or program_f4, "single_flag": n_fail == 1 and not program_f4,
                    "for_review": any(review.values()), "judge_totals": totals, "c8": n["format"]["c8"],
                    "criteria": {c: statistics.mean(r["scores"][c] for r in js.values()) for c in rubric.CRITERIA},
                    "score": statistics.mean(totals.values()) + n["format"]["c8"]})
    return out


def scorecard(run: Path, cs: Cases, stage: str) -> str:
    ids = {c["id"] for c in cs.stage(stage)}
    notes = [n for n in rows(run, "write") if n["case_id"] in ids]
    for n in notes:   # re-run the program checks, so a rule change applies to notes already written
        n["format"] = check_format(n["text"])
        n["urgency_check"] = check_urgency(n["text"], cs.by_id[n["case_id"]]["urgency"])
    scored = score_notes(notes, rows(run, "judge"))
    L = [f"# Scorecard: {stage} ({len(ids)} cases, {len(notes)} notes, {len(scored)} scored)", ""]
    if len({n["config"] for n in notes}) > 1:
        L += ["WARNING: these notes were made under more than one prompt or rubric version.", ""]
    partial = [s["id"] for s in scored if len(s["judges"]) < len(JUDGES)]
    if partial:
        L += [f"WARNING: {len(partial)} notes have fewer than {len(JUDGES)} judgments.", ""]
    L += ["## Per writer model", "",
          "| Writer | Notes | Critical failure (2+ judges or program) | Flagged by 1 judge | For clinician review | Mean score /16 (no critical failure) | Mean /16 (all) | Lowest note |",
          "|---|---|---|---|---|---|---|---|"]
    for w in WRITERS:
        s = [x for x in scored if x["writer"] == w]
        if not s:
            continue
        clean = [x["score"] for x in s if not x["confirmed"]]
        L.append(f"| {w} | {len(s)} | {sum(x['confirmed'] for x in s)} | {sum(x['single_flag'] for x in s)} | {sum(x['for_review'] for x in s)} | "
                 f"{statistics.mean(clean):.1f} | {statistics.mean(x['score'] for x in s):.1f} | {min(x['score'] for x in s):.1f} |" if clean else
                 f"| {w} | {len(s)} | {sum(x['confirmed'] for x in s)} | {sum(x['single_flag'] for x in s)} | {sum(x['for_review'] for x in s)} | none clean | "
                 f"{statistics.mean(x['score'] for x in s):.1f} | {min(x['score'] for x in s):.1f} |")
    if stage == "test":
        L += ["", "## Pass bar (no critical failure in any note; mean at least 13; no note below 10)", "",
              "| Writer | Group | Notes | Critical failures | Mean /16 | Lowest | Verdict |", "|---|---|---|---|---|---|---|"]
        for w in WRITERS:
            for label, keep in (("all", lambda x: True), ("cardiology", lambda x: x["condition"] == "cardiac"),
                                ("other two", lambda x: x["condition"] != "cardiac")):
                s = [x for x in scored if x["writer"] == w and keep(x)]
                if s:
                    nf, mean, low = sum(x["confirmed"] for x in s), statistics.mean(x["score"] for x in s), min(x["score"] for x in s)
                    L.append(f"| {w} | {label} | {len(s)} | {nf} | {mean:.1f} | {low:.1f} | {'PASS' if nf == 0 and mean >= 13 and low >= 10 else 'FAIL'} |")
    L += ["", "## Criteria, mean 0 to 2 (C1 to C7 from judges, C8 from the format program)", "",
          "| Writer | " + " | ".join(list(rubric.CRITERIA) + ["C8"]) + " |", "|---|" + "---|" * 8]
    for w in WRITERS:
        s = [x for x in scored if x["writer"] == w]
        if s:
            L.append(f"| {w} | " + " | ".join(f"{statistics.mean(x['criteria'][c] for x in s):.2f}" for c in rubric.CRITERIA)
                     + f" | {statistics.mean(x['c8'] for x in s):.2f} |")
    L += ["", "## Which critical failures (number of notes where that judge said yes)", "",
          "| Judge | " + " | ".join(rubric.FAILURES) + " | Notes failed |", "|---|" + "---|" * 8]
    for j in JUDGES:
        s = [x for x in scored if j in x["fails"]]
        if s:
            L.append(f"| {j} | " + " | ".join(str(sum(f in x["fails"][j] for x in s)) for f in rubric.FAILURES)
                     + f" | {sum(bool(x['fails'][j]) for x in s)} of {len(s)} |")
    L += ["", "## Do the judges agree, and does a judge favour its own model?", "",
          "Mean C1 to C7 total (out of 14) each judge gave each writer; the diagonal is a judge scoring its own model.", "",
          "| Judge | " + " | ".join(f"writer {w}" for w in WRITERS) + " |", "|---|" + "---|" * len(WRITERS)]
    for j in JUDGES:
        cells = []
        for w in WRITERS:
            v = [x["judge_totals"][j] for x in scored if x["writer"] == w and j in x["judge_totals"]]
            cells.append(f"{statistics.mean(v):.1f}" if v else "-")
        L.append(f"| {j} | " + " | ".join(cells) + " |")
    L += ["", "| Judge pair | Notes | Agree on fail or not | Kappa | Mean gap in total (of 14) |", "|---|---|---|---|---|"]
    for a, b in itertools.combinations(JUDGES, 2):
        s = [x for x in scored if a in x["fails"] and b in x["fails"]]
        if s:
            fa, fb = [bool(x["fails"][a]) for x in s], [bool(x["fails"][b]) for x in s]
            k = kappa(fa, fb)
            L.append(f"| {a} and {b} | {len(s)} | {100 * sum(x == y for x, y in zip(fa, fb)) / len(s):.0f}% | "
                     f"{'n/a' if k is None else f'{k:.2f}'} | {statistics.mean(abs(x['judge_totals'][a] - x['judge_totals'][b]) for x in s):.1f} |")
    bad = [n for n in notes if n["status"] != "ok"]
    L += ["", f"Notes not usable (cut off or refused): {len(bad)}. Failed calls logged: {len(read_jsonl(run / 'errors.jsonl'))}. "
          f"Spent so far: ${spent(run):.2f} of ${BUDGET_USD:.0f}.", "",
          "## Notes for a clinician to read first", ""]
    flagged = sorted((x for x in scored if x["confirmed"] or x["single_flag"] or x["for_review"]), key=lambda x: (-x["n_fail"], x["id"]))
    for x in flagged:
        why = "; ".join(f"{j}: {', '.join(f)}" for j, f in x["fails"].items() if f) or "no judge said yes"
        rev = "; ".join(f"{j}: {', '.join(f)}" for j, f in x["review"].items() if f)
        L.append(f"- `{x['id']}` score {x['score']:.1f}. Failures: {why}." + (f" Unsure: {rev}." if rev else "")
                 + (" Program: urgency differs from the one selected." if x["program_f4"] else ""))
    if not flagged:
        L.append("- None flagged.")
    return "\n".join(L)


# ---------- commands ----------
def cmd_check(_) -> None:
    ids = {m.id for m in client().models.list(limit=100)}
    print("Key accepted.", ", ".join(f"{m}: {'available' if m in ids else 'NOT LISTED'}" for m in MODELS.values()))


def cmd_plan(a) -> None:
    run, cs = run_dir(a.run), Cases()
    print(f"Run '{a.run}', config {CONFIG}. Writers and judges: {', '.join(MODELS.values())}. Writer effort {WRITER_EFFORT}, judge effort {JUDGE_EFFORT}.")
    total = 0.0
    for stage in ("build", "carry", "test"):
        w, j = write_jobs(run, cs, stage), len(cs.stage(stage)) * REPS[stage] * len(WRITERS) * len(JUDGES)
        j_left = j - sum(1 for r in rows(run, "judge") if r["note_id"].split("__")[0] in {c["id"] for c in cs.stage(stage)})
        est = sum(per_call(run, "write", nid.split("__")[1], True)[0] for nid in w) + j_left / len(JUDGES) * sum(per_call(run, "judge", k, True)[0] for k in JUDGES)
        total += est
        print(f"  {stage:5s}: {len(cs.stage(stage))} cases x {REPS[stage]} draft(s): {len(w)} notes and {j_left} judgments still to run, about ${est:.2f} by batch")
    measured = all(per_call(run, k, m, True)[1] for k in ("write", "judge") for m in MODELS)
    print(f"Still to spend about ${total:.2f}; spent ${spent(run):.2f}; budget ${BUDGET_USD:.0f}. Basis: {'measured token use from this run' if measured else 'assumed high-side token use (nothing measured yet for some models)'}.")


def usage_table(run: Path) -> None:
    print("\nMeasured token use per call (mean, range) and live price per call:")
    for kind in ("write", "judge"):
        for m in MODELS:
            r = [x for x in rows(run, kind) + (rows(run, "probe") if kind == "judge" else []) if x["model_key"] == m]
            if r:
                i, o = [x["usage"]["input_tokens"] for x in r], [x["usage"]["output_tokens"] for x in r]
                print(f"  {kind:5s} {m:6s} n={len(r):2d} in {statistics.mean(i):6.0f} ({min(i)}-{max(i)})  out {statistics.mean(o):6.0f} ({min(o)}-{max(o)})"
                      f"  ${statistics.mean(cost_usd(m, x['usage'], False) for x in r):.4f}")


def cmd_pilot(a) -> None:
    run, cs = run_dir(a.run), Cases()
    w = write_jobs(run, cs, "pilot")
    n_probe = 4 * len(JUDGES)
    guard(run, [("write", nid.split("__")[1]) for nid in w] + [("judge", j) for j in JUDGES for _ in range(len(PILOT_CASES) * len(WRITERS))]
          + [("judge", j) for j in JUDGES for _ in range(4)], False, a.force)
    t0 = time.time()
    if w:
        print(f"Writing {len(w)} notes live...")
        do_writes(run, cs, w, False, "pilot", 0)
    jobs = [(jid, cs.by_id[n["case_id"]], n["text"], None) for jid, n in judge_jobs(run, cs, "pilot")]
    if jobs:
        print(f"Judging: {len(jobs)} judgments live...")
        do_judging(run, cs, jobs, False, "pilot", 0)
    notes = {n["id"]: n for n in rows(run, "write") if n["status"] == "ok"}
    a_note = next((notes[i] for i in (note_id(PILOT_CASES[0], w_, 0) for w_ in WRITERS) if i in notes), None)
    b_note = next((notes[i] for i in (note_id(PILOT_CASES[1], w_, 0) for w_ in WRITERS) if i in notes), None)
    if a_note and b_note:
        target = cs.by_id[PILOT_CASES[0]]
        invented = a_note["text"].replace("RELEVANT HISTORY\n", "RELEVANT HISTORY\nReports crushing central chest pain at rest last night "
                                          "radiating to the left arm, with vomiting. Examination today found a pansystolic murmur and bilateral basal crackles.\n", 1)
        probes = {"empty": "", "idk": "I don't know.", "invented": invented, "wrongpatient": b_note["text"]}
        have = {r["id"] for r in rows(run, "probe")}
        pj = [(f"probe-{name}__j-{j}", target, text, name) for name, text in probes.items() for j in JUDGES if f"probe-{name}__j-{j}" not in have]
        if pj:
            print(f"Judge probes: {len(pj)} judgments of known-bad notes...")
            do_judging(run, cs, pj, False, "pilot", 0)
        print("\nKnown-bad notes: did each judge catch them?")
        expect = {"empty": None, "idk": None, "invented": {"F1"}, "wrongpatient": {"F1", "F2", "F3", "F5"}}
        for r in sorted(rows(run, "probe"), key=lambda r: r["id"]):
            yes = {f for f, v in r["failures"].items() if v == "yes"}
            want = expect[r["probe"]]
            caught = bool(yes & want) if want else (bool(yes) or sum(r["scores"].values()) <= 3)
            print(f"  {r['probe']:12s} {r['judge']:6s} {'CAUGHT' if caught else 'MISSED'}  said yes to: {', '.join(sorted(yes)) or 'nothing'}; C total {sum(r['scores'].values())}")
    print(f"\nPilot took {time.time() - t0:.0f} s.")
    usage_table(run)
    print()
    print(scorecard(run, cs, "pilot"))
    print()
    cmd_plan(a)


def cmd_write(a) -> None:
    run, cs = run_dir(a.run), Cases()
    if a.stage == "test" and not a.unseal:
        sys.exit("The test set is sealed until the prompt and rubric are frozen. Add --unseal when they are.")
    ids = write_jobs(run, cs, a.stage)
    if not ids:
        return print("Nothing to write: every note for this stage exists.")
    projected = guard(run, [("write", i.split("__")[1]) for i in ids], not a.sync, a.force)
    do_writes(run, cs, ids, not a.sync, a.stage, projected)


def cmd_judge(a) -> None:
    run, cs = run_dir(a.run), Cases()
    jobs = [(jid, cs.by_id[n["case_id"]], n["text"], None) for jid, n in judge_jobs(run, cs, a.stage)]
    if not jobs:
        return print("Nothing to judge: no unjudged notes for this stage.")
    projected = guard(run, [("judge", jid.rsplit("__j-", 1)[1]) for jid, *_ in jobs], not a.sync, a.force)
    do_judging(run, cs, jobs, not a.sync, a.stage, projected)


def cmd_collect(a) -> None:
    collect(run_dir(a.run), Cases(), a.wait)


def cmd_score(a) -> None:
    run, cs = run_dir(a.run), Cases()
    text = scorecard(run, cs, a.stage)
    (run / f"scorecard-{a.stage}.md").write_text(text, encoding="utf-8")
    print(text)


def cmd_selftest(_) -> None:
    ok = True

    def expect(name: str, got, want) -> None:
        nonlocal ok
        good = got == want
        ok &= good
        print(f"  {'ok  ' if good else 'FAIL'} {name}" + ("" if good else f": got {got!r}, wanted {want!r}"))

    body = " ".join(["word"] * 33)
    good = "\n\n".join(f"{h}\n{body}" for h in rubric.HEADINGS)   # 8 x (heading words + 33)
    expect("well-formed note scores 2", check_format(good)["c8"], 2)
    expect("missing heading scores 0", check_format(good.replace("KEY RESULTS\n", ""))["c8"], 0)
    swapped = good.replace("KEY RESULTS", "@@").replace("RELEVANT HISTORY", "KEY RESULTS").replace("@@", "RELEVANT HISTORY")
    expect("reordered headings score 0", check_format(swapped)["c8"], 0)
    expect("far too long scores 0", check_format(good + " " + " ".join(["word"] * 250))["c8"], 0)
    expect("slightly long scores 1", check_format(good + " " + " ".join(["word"] * 120))["c8"], 1)
    expect("markdown scores 1", check_format(good.replace("word word", "**word** word", 1))["c8"], 1)
    expect("greeting scores 1", check_format("Dear colleague,\n" + good)["c8"], 1)
    expect("empty note scores 0", check_format("")["c8"], 0)
    expect("urgency match", check_urgency("Routine referral for review.", "routine"), "match")
    expect("urgency mismatch", check_urgency("This is an urgent referral.", "routine"), "mismatch")
    expect("urgency not stated", check_urgency("Seen in urgent care twice; routine bloods normal.", "routine"), "not_stated")
    expect("urgency in brackets", check_urgency("Referred to cardiology (urgent).", "urgent"), "match")

    def note(i, w, text_ok=True, urg="match"):
        return {"id": i, "case_id": "c", "split": "build", "condition": "cardiac", "writer": w, "status": "ok" if text_ok else "truncated",
                "format": {"c8": 2}, "urgency_check": urg, "config": "x"}

    def jud(nid, j, fails=(), score=2):
        return {"note_id": nid, "judge": j, "failures": {f: ("yes" if f in fails else "no") for f in rubric.FAILURES},
                "scores": {c: score for c in rubric.CRITERIA}}
    notes = [note("n1", "opus"), note("n2", "opus"), note("n3", "sonnet"), note("n4", "haiku", urg="mismatch"), note("n5", "haiku", text_ok=False)]
    js = [jud("n1", j) for j in JUDGES] + [jud("n2", "opus", ["F1"]), jud("n2", "sonnet", ["F3"]), jud("n2", "haiku", score=1)] \
        + [jud("n3", "opus", ["F6"], 1), jud("n3", "sonnet", score=1), jud("n3", "haiku", score=1)] + [jud("n4", j) for j in JUDGES]
    s = {x["id"]: x for x in score_notes(notes, js)}
    expect("perfect note scores 16", s["n1"]["score"], 16)
    expect("two judges failing (different failures) confirms", s["n2"]["confirmed"], True)
    expect("mixed judge totals average", round(s["n2"]["score"], 2), round((14 + 14 + 7) / 3 + 2, 2))
    expect("one judge failing is a single flag", (s["n3"]["confirmed"], s["n3"]["single_flag"]), (False, True))
    expect("program urgency mismatch confirms", s["n4"]["confirmed"], True)
    expect("truncated note is not scored", "n5" in s, False)
    expect("kappa of identical raters", kappa([True, False, True, False], [True, False, True, False]), 1.0)

    cs = Cases()
    split = {k: sum(1 for c in cs.by_id.values() if c["split"] == k) for k in ("build", "carry", "test")}
    expect("33 cases split 15 / 8 / 10", split, {"build": 15, "carry": 8, "test": 10})
    expect("test set is 5 cardiology, 2 kidney, 3 joint", [sum(1 for c in cs.stage("test") if c["condition"] == k) for k in ("cardiac", "dkd", "oa")], [5, 2, 3])
    expect("build set is all cardiology", {c["condition"] for c in cs.stage("build")}, {"cardiac"})
    expect("every case names the chart's patient", all(cs.extract(c)["patient"]["name"] == c["patient"] for c in cs.by_id.values()), True)
    expect("every case states a reason", all(c["notes"].startswith("Reason for referral now:") for c in cs.by_id.values()), True)
    expect("urgency values valid", {c["urgency"] for c in cs.by_id.values()} <= {"routine", "urgent", "emergent"}, True)
    expect("no held-out patient outside test", {c["patient"] for c in cs.stage("test")} & {c["patient"] for c in cs.by_id.values() if c["split"] != "test"}, set())
    ids = [f"{note_id(c['id'], w, 2)}__j-{j}" for c in cs.by_id.values() for w in WRITERS for j in JUDGES]
    expect("batch ids valid", all(re.fullmatch(r"[A-Za-z0-9_-]{1,64}", i) for i in ids), True)
    expect("app still appends the same closing instruction", WRITE_SUFFIX.strip() in inspect.getsource(llm.draft), True)
    p = writer_params(cs, cs.by_id[PILOT_CASES[0]], "opus")
    expect("writer prompt carries chart, PCP notes and system prompt",
           ("CHART EXTRACT" in p["messages"][0]["content"], "Reason for referral now" in p["messages"][0]["content"], p["system"] == llm.SYSTEM), (True, True, True))
    q = judge_params(cs, cs.by_id[PILOT_CASES[0]], "NOTE-TEXT", "haiku")["messages"][0]["content"]
    expect("judge prompt carries note, chart, all failures and criteria",
           all(t in q for t in ["NOTE-TEXT", "CHART EXTRACT", "F7:", "C7 ", "<specialist_needs>"]), True)
    expect("judge prompt does not name the writer model", any(m in q + rubric.GRADER_SYSTEM for m in list(MODELS) + list(MODELS.values())), False)
    print("\nSELFTEST", "PASSED" if ok else "FAILED")
    sys.exit(0 if ok else 1)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--run", default="run1", help="name of the results folder under eval/runs")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, fn in (("selftest", cmd_selftest), ("check", cmd_check), ("plan", cmd_plan), ("pilot", cmd_pilot), ("write", cmd_write),
                     ("judge", cmd_judge), ("collect", cmd_collect), ("score", cmd_score)):
        p = sub.add_parser(name)
        p.set_defaults(fn=fn)
        if name in ("write", "judge", "score"):
            p.add_argument("--stage", required=True, choices=["pilot", "build", "carry", "test"])
        if name in ("write", "judge"):
            p.add_argument("--sync", action="store_true", help="call live at full price instead of a half-price batch")
        if name == "write":
            p.add_argument("--unseal", action="store_true", help="allow the held-out test set")
        if name in ("write", "judge", "pilot"):
            p.add_argument("--force", action="store_true", help="go past the budget guard")
        if name == "collect":
            p.add_argument("--wait", action="store_true", help="keep checking until every batch has ended")
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
