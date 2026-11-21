"""Loads the Synthea CSV export and builds a per-patient chart extract for a referral.

The extract is what the model sees. It is curated per referral condition: the
labs, procedures and history a given specialist cares about, not the whole chart.
"""
from __future__ import annotations

import csv
import re
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "synthea"

# LOINC codes shown for every referral.
COMMON_PANEL = {
    "Systolic BP (mmHg)": ["8480-6"],
    "Diastolic BP (mmHg)": ["8462-4"],
    "Heart rate (/min)": ["8867-4"],
    "BMI (kg/m2)": ["39156-5"],
    "Weight (kg)": ["29463-7"],
    "Tobacco smoking status": ["72166-2"],
}

CONDITIONS = {
    "dkd": {
        "label": "Diabetic kidney disease (type 2 diabetes with CKD)",
        "specialty": "Nephrology",
        # A patient is in the cohort if they have an active condition matching this.
        "cohort": r"Chronic kidney disease|Disorder of kidney due to diabetes",
        # Already under nephrology care (dialysis or transplant), so not a new PCP referral.
        "exclude": r"dialysis|transplant",
        # Problems, medications and encounters matching this are shown as referral-relevant.
        "related": r"kidney|renal|diabet|albuminuria|proteinuria|hypertension|anemia|hyperglycemia"
                   r"|metabolic syndrome|triglycerid|lipid|retinopathy|neuropathy|dialysis",
        "procedures": r"dialysis|renal|kidney|transplant|fistula|biopsy",
        "panel": {
            "eGFR (mL/min/1.73m2)": ["33914-3"],
            "Creatinine (mg/dL)": ["2160-0", "38483-4"],
            "Urine albumin/creatinine ratio (mg/g)": ["14959-1"],
            "Urine protein, dipstick (mg/dL)": ["5804-0"],
            "HbA1c (%)": ["4548-4"],
            "Potassium (mmol/L)": ["2823-3", "6298-4"],
            "Urea nitrogen (mg/dL)": ["3094-0", "6299-2"],
            "Bicarbonate/total CO2 (mmol/L)": ["2028-9", "20565-8"],
            "Calcium (mg/dL)": ["17861-6", "49765-1"],
            "Phosphate (mg/dL)": ["2777-1"],
            "Hemoglobin (g/dL)": ["718-7"],
            "Albumin (g/dL)": ["1751-7"],
            "Diabetic retinopathy severity, left eye": ["71490-7"],
            "Diabetic retinopathy severity, right eye": ["71491-5"],
        },
        "guidance": (
            "The nephrologist will want: CKD stage and how fast eGFR is falling (give first and "
            "latest values with dates), degree of albuminuria, blood pressure control, glycemic "
            "control, whether the patient is on an ACE inhibitor/ARB or SGLT2 inhibitor, "
            "nephrotoxic or renally-cleared medications (metformin, NSAIDs), potassium, "
            "bicarbonate, hemoglobin and bone-mineral labs, and other diabetic complications "
            "(retinopathy, neuropathy)."
        ),
    },
    "cardiac": {
        "label": "Ischemic heart disease / chronic heart failure",
        "specialty": "Cardiology",
        "cohort": r"Ischemic heart disease|congestive heart failure",
        "related": r"heart|cardiac|coronary|myocardial|infarction|hypertension|lipid|atrial|stroke"
                   r"|diabet|metabolic syndrome|triglycerid|kidney|embolism|bypass",
        "procedures": r"cardi|coronary|echo|electrocard|angio|stent|bypass|catheter|percutaneous"
                      r"|stress|defibrillat|pacemaker",
        "panel": {
            "LV ejection fraction (%)": ["10230-1"],
            "NT-proBNP (pg/mL)": ["33762-6"],
            "Troponin I, high sensitivity (pg/mL)": ["89579-7"],
            "LDL cholesterol (mg/dL)": ["18262-6"],
            "Total cholesterol (mg/dL)": ["2093-3"],
            "HDL cholesterol (mg/dL)": ["2085-9"],
            "Triglycerides (mg/dL)": ["2571-8"],
            "HbA1c (%)": ["4548-4"],
            "eGFR (mL/min/1.73m2)": ["33914-3"],
            "Creatinine (mg/dL)": ["2160-0", "38483-4"],
            "Potassium (mmol/L)": ["2823-3", "6298-4"],
            "Sodium (mmol/L)": ["2951-2", "2947-0"],
            "Hemoglobin (g/dL)": ["718-7"],
            "Oxygen saturation (%)": ["2708-6"],
        },
        "guidance": (
            "The cardiologist will want: the cardiac diagnoses with dates, prior events and "
            "interventions (MI, PCI, CABG, heart failure admissions), latest ejection fraction "
            "and cardiac imaging, current cardiac medications (antiplatelet, statin, beta "
            "blocker, ACE inhibitor/ARB, diuretic) and obvious gaps in them, blood pressure and "
            "heart rate, lipid and glycemic control, renal function and potassium, recent "
            "emergency or inpatient encounters, and smoking status."
        ),
    },
    "oa": {
        "label": "Osteoarthritis of the knee or hip",
        "specialty": "Orthopedic surgery",
        "cohort": r"Osteoarthritis of (knee|hip)",
        "related": r"osteoarthritis|arthritis|joint|knee|hip|chronic pain|obes|osteopor|fracture",
        "procedures": r"knee|hip|joint|replacement|arthro|injection|physical therapy|radiograph"
                      r"|x-ray|exercise",
        "panel": {
            "Pain severity, 0-10 (reported)": ["72514-3"],
            "HbA1c (%)": ["4548-4"],
            "eGFR (mL/min/1.73m2)": ["33914-3"],
            "Creatinine (mg/dL)": ["2160-0", "38483-4"],
            "Hemoglobin (g/dL)": ["718-7"],
            "Platelets (10*3/uL)": ["777-3"],
            "INR": ["6301-6"],
        },
        "guidance": (
            "The orthopedic surgeon will want: which joint and how long since diagnosis, "
            "conservative treatment tried so far (analgesics, NSAIDs, injections, physical "
            "therapy, weight management) and for how long, pain scores over time, imaging of the "
            "joint, BMI, and the comorbidities that affect fitness for surgery: diabetes control, "
            "cardiac disease, kidney function, anticoagulant or antiplatelet use, anemia, "
            "smoking status."
        ),
    },
    "endo": {
        "label": "Type 2 diabetes (without kidney disease)",
        "specialty": "Endocrinology",
        "cohort": r"Diabetes mellitus type 2",
        # Diabetic kidney disease goes to nephrology (the "dkd" condition above).
        "exclude": r"kidney|dialysis|transplant",
        "related": r"diabet|glyc|obes|body mass index|metabolic syndrome|triglycerid|lipid|hypertension"
                   r"|retinopathy|neuropathy|heart|coronary|foot",
        "procedures": r"diabet|foot|eye|retin|nutrition|education|glucose|hemoglobin a1c",
        "panel": {
            "HbA1c (%)": ["4548-4"],
            "Glucose (mg/dL)": ["2345-7", "2339-0"],
            "eGFR (mL/min/1.73m2)": ["33914-3"],
            "Creatinine (mg/dL)": ["2160-0", "38483-4"],
            "Urine albumin/creatinine ratio (mg/g)": ["14959-1"],
            "LDL cholesterol (mg/dL)": ["18262-6"],
            "Total cholesterol (mg/dL)": ["2093-3"],
            "HDL cholesterol (mg/dL)": ["2085-9"],
            "Triglycerides (mg/dL)": ["2571-8"],
            "Diabetic retinopathy severity, left eye": ["71490-7"],
            "Diabetic retinopathy severity, right eye": ["71491-5"],
        },
        "guidance": (
            "The endocrinologist will want: when type 2 diabetes was diagnosed, the HbA1c trend "
            "(first and latest values with dates) and whether it is at goal, every glucose-lowering "
            "medication tried with dates and why any were stopped, hypoglycemia, weight and BMI "
            "trend, blood pressure and lipids, kidney function and urine albumin, complications "
            "(retinopathy, neuropathy, foot problems), cardiovascular disease, and whether diabetes "
            "education or nutrition counseling has happened."
        ),
    },
}


def _read(table: str) -> list[dict]:
    with open(DATA_DIR / f"{table}.csv", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _by_patient(rows: list[dict]) -> dict[str, list[dict]]:
    out = defaultdict(list)
    for r in rows:
        out[r["PATIENT"]].append(r)
    return out


def _d(s: str) -> str:
    """Synthea timestamps are ISO strings; the date part sorts and compares as text."""
    return s[:10]


def _clean(description: str) -> str:
    return re.sub(r"\s*\((disorder|finding|situation|procedure|regime/therapy|morphologic abnormality|record artifact)\)$",
                  "", description).strip()


class Chart:
    def __init__(self) -> None:
        self.patients = {p["Id"]: p for p in _read("patients")}
        self.conditions = _by_patient(_read("conditions"))
        self.encounters = _by_patient(_read("encounters"))
        self.medications = _by_patient(_read("medications"))
        self.observations = _by_patient(_read("observations"))
        self.procedures = _by_patient(_read("procedures"))
        self.careplans = _by_patient(_read("careplans"))
        self.allergies = _by_patient(_read("allergies"))
        self.imaging = _by_patient(_read("imaging_studies"))
        # Synthetic data ends on the day it was generated; treat that as "today".
        self.today = date.fromisoformat(
            max(_d(e["START"]) for rows in self.encounters.values() for e in rows))

    # ---- cohorts -------------------------------------------------------------

    def _in_cohort(self, pid: str, key: str) -> bool:
        rx = CONDITIONS[key]["cohort"]
        exclude = CONDITIONS[key].get("exclude")
        if exclude and any(re.search(exclude, r["DESCRIPTION"], re.I)
                           for r in self.conditions.get(pid, []) + self.procedures.get(pid, [])):
            return False
        return any(not c["STOP"] and re.search(rx, c["DESCRIPTION"], re.I)
                   for c in self.conditions.get(pid, []))

    def cohort(self, key: str) -> list[dict]:
        out = []
        for pid, p in self.patients.items():
            if p["DEATHDATE"] or not self._in_cohort(pid, key):
                continue
            out.append({**self._header(pid), "headline": self._headline(pid, key)})
        return sorted(out, key=lambda r: r["name"])

    def _header(self, pid: str) -> dict:
        p = self.patients[pid]
        born = date.fromisoformat(p["BIRTHDATE"])
        age = self.today.year - born.year - ((self.today.month, self.today.day) < (born.month, born.day))
        name = " ".join(re.sub(r"\d+", "", p[k]) for k in ("FIRST", "LAST"))
        return {"id": pid, "name": name, "age": age, "sex": {"M": "male", "F": "female"}.get(p["GENDER"], p["GENDER"])}

    def _latest(self, pid: str, codes: list[str]) -> dict | None:
        rows = [o for o in self.observations.get(pid, []) if o["CODE"] in codes]
        return max(rows, key=lambda o: o["DATE"]) if rows else None

    def _headline(self, pid: str, key: str) -> str:
        active = [_clean(c["DESCRIPTION"]) for c in self.conditions[pid]
                  if not c["STOP"] and re.search(CONDITIONS[key]["cohort"], c["DESCRIPTION"], re.I)]
        staged = sorted(a for a in set(active) if "stage" in a)
        parts = [staged[-1] if staged else sorted(set(active))[0]]
        metric = {"dkd": ("eGFR", ["33914-3"]), "cardiac": ("LVEF", ["10230-1"]), "oa": ("BMI", ["39156-5"]),
                  "endo": ("HbA1c", ["4548-4"])}[key]
        latest = self._latest(pid, metric[1])
        if latest:
            parts.append(f"{metric[0]} {_fmt(latest['VALUE'])}")
        return " · ".join(parts)

    # ---- chart extract -------------------------------------------------------

    def extract(self, pid: str, key: str) -> dict:
        if pid not in self.patients:
            raise KeyError(pid)
        cfg = CONDITIONS[key]
        related = re.compile(cfg["related"], re.I)
        head = self._header(pid)
        since_2y = (self.today - timedelta(days=730)).isoformat()

        # Problems: one line per distinct description, earliest onset.
        onset: dict[str, str] = {}
        resolved = Counter()
        resolved_last: dict[str, str] = {}
        for c in self.conditions.get(pid, []):
            desc = c["DESCRIPTION"]
            if c["STOP"]:
                resolved[desc] += 1
                resolved_last[desc] = max(resolved_last.get(desc, ""), c["STOP"])
            else:
                onset[desc] = min(onset.get(desc, "9999"), c["START"])
        clinical = {k: v for k, v in onset.items() if "(disorder)" in k or related.search(k)}
        relevant = sorted(((v, _clean(k)) for k, v in clinical.items() if related.search(k)))
        other = sorted(((v, _clean(k)) for k, v in clinical.items() if not related.search(k)))
        social = sorted(_clean(k) for k in onset if k not in clinical)
        past = sorted(((resolved_last[k], _clean(k), n) for k, n in resolved.items()
                       if related.search(k)), reverse=True)

        # Medications.
        active_meds: dict[str, dict] = {}
        past_meds: dict[str, dict] = {}
        for m in self.medications.get(pid, []):
            target = past_meds if m["STOP"] else active_meds
            cur = target.setdefault(m["DESCRIPTION"], {"start": m["START"], "stop": m["STOP"],
                                                       "reason": _clean(m["REASONDESCRIPTION"])})
            cur["start"] = min(cur["start"], m["START"])
            cur["stop"] = max(cur["stop"], m["STOP"])
        past_related = {k: v for k, v in past_meds.items()
                        if k not in active_meds and v["reason"] and related.search(v["reason"])}

        # Results: latest value plus up to five earlier ones for the trend.
        results = []
        for label, codes in {**cfg["panel"], **COMMON_PANEL}.items():
            rows = sorted((o for o in self.observations.get(pid, []) if o["CODE"] in codes),
                          key=lambda o: o["DATE"])
            if not rows:
                continue
            # Several readings can share a day (e.g. inpatient stays); keep the last per day.
            per_day = {_d(o["DATE"]): _clean(_fmt(o["VALUE"])) for o in rows}
            series = list(per_day.items())
            if rows[-1]["TYPE"] == "text" and len(set(per_day.values())) == 1:
                series = series[-1:]
            results.append({"label": label, "latest": series[-1], "earlier": series[-6:-1],
                            "first": series[0], "count": len(series)})

        # Procedures tied to this condition, grouped.
        proc_rx = re.compile(cfg["procedures"], re.I)
        procs: dict[str, dict] = {}
        for p in self.procedures.get(pid, []):
            if re.search(r"dental|teeth|tooth|gingiv|oral health|plaque", p["DESCRIPTION"], re.I):
                continue
            if not (proc_rx.search(p["DESCRIPTION"]) or (p["REASONDESCRIPTION"] and related.search(p["REASONDESCRIPTION"]))):
                continue
            cur = procs.setdefault(_clean(p["DESCRIPTION"]), {"n": 0, "first": _d(p["START"]), "last": _d(p["START"])})
            cur["n"] += 1
            cur["first"] = min(cur["first"], _d(p["START"]))
            cur["last"] = max(cur["last"], _d(p["START"]))
        proc_list = sorted(procs.items(), key=lambda kv: kv[1]["last"], reverse=True)

        # Imaging: one line per modality + body site (the export has a row per image).
        studies: dict[tuple, set] = defaultdict(set)
        for i in self.imaging.get(pid, []):
            studies[(i["MODALITY_DESCRIPTION"], _clean(i["BODYSITE_DESCRIPTION"]))].add(_d(i["DATE"]))
        imaging = sorted(((max(d), mod, site, len(d)) for (mod, site), d in studies.items()
                          if not re.search(r"mouth|tooth|teeth|dental", site, re.I)), reverse=True)

        # Encounters.
        encs = sorted(self.encounters.get(pid, []), key=lambda e: e["START"], reverse=True)
        recent = [e for e in encs if _d(e["START"]) >= since_2y]
        acute = [e for e in recent if e["ENCOUNTERCLASS"] in ("emergency", "inpatient", "urgentcare")]
        cond_visits = [e for e in encs if e["REASONDESCRIPTION"] and related.search(e["REASONDESCRIPTION"])]

        plans = sorted({(_clean(c["DESCRIPTION"]), _clean(c["REASONDESCRIPTION"]))
                        for c in self.careplans.get(pid, []) if not c["STOP"]})
        allergies = sorted({_clean(a["DESCRIPTION"]) for a in self.allergies.get(pid, []) if not a["STOP"]})

        data = {
            "patient": head, "condition": key, "as_of": self.today.isoformat(),
            "relevant_problems": relevant, "other_problems": other, "social": social,
            "past_related": past, "active_meds": active_meds, "past_related_meds": past_related,
            "allergies": allergies, "results": results, "procedures": proc_list,
            "imaging": imaging, "recent_class_counts": Counter(e["ENCOUNTERCLASS"] for e in recent),
            "acute": acute, "condition_visits": cond_visits, "careplans": plans,
        }
        data["text"] = _render(data)
        return data


def _fmt(value: str) -> str:
    try:
        return f"{float(value):.1f}".rstrip("0").rstrip(".")
    except ValueError:
        return value


def _render(d: dict) -> str:
    p = d["patient"]
    L = [f"CHART EXTRACT (synthetic Synthea record) as of {d['as_of']}",
         f"Patient: {p['name']}, {p['age']}-year-old {p['sex']}", ""]

    def section(title: str, lines: list[str], empty: str = "None recorded") -> None:
        L.append(title)
        L.extend(f"  - {x}" for x in lines) if lines else L.append(f"  {empty}")
        L.append("")

    section("ACTIVE PROBLEMS RELEVANT TO THIS REFERRAL (onset)",
            [f"{name} ({_d(start)})" for start, name in d["relevant_problems"]])
    section("OTHER ACTIVE PROBLEMS (onset)",
            [f"{name} ({_d(start)})" for start, name in d["other_problems"]])
    section("RESOLVED RELATED CONDITIONS (last resolved, episodes)",
            [f"{name} ({_d(stop)}, x{n})" for stop, name, n in d["past_related"]])
    section("ACTIVE MEDICATIONS (started; indication if recorded)",
            [f"{name} (since {_d(m['start'])}{'; for ' + m['reason'] if m['reason'] else ''})"
             for name, m in sorted(d["active_meds"].items())])
    section("STOPPED MEDICATIONS FOR RELATED CONDITIONS",
            [f"{name} ({_d(m['start'])} to {_d(m['stop'])}; for {m['reason']})"
             for name, m in sorted(d["past_related_meds"].items())])
    section("ALLERGIES", d["allergies"], "No allergies recorded")

    res = []
    for r in d["results"]:
        line = f"{r['label']}: {r['latest'][1]} on {r['latest'][0]}"
        if r["earlier"]:
            line += "; earlier: " + ", ".join(f"{v} ({dt})" for dt, v in r["earlier"])
        if r["count"] > 6:
            line += f"; first recorded: {r['first'][1]} ({r['first'][0]}); {r['count']} readings in total"
        res.append(line)
    section("RESULTS AND VITALS (latest first, then earlier values oldest to newest)", res)

    shown = d["procedures"][:25]
    section(f"RELATED PROCEDURES ({len(shown)} of {len(d['procedures'])} distinct, most recent first)",
            [f"{name}: x{v['n']}, {v['first']} to {v['last']}" if v["n"] > 1 else f"{name}: {v['last']}"
             for name, v in shown])
    section("IMAGING (latest study date; number of study dates)",
            [f"{mod}, {site}: {last} ({n} dates)" for last, mod, site, n in d["imaging"][:12]])

    counts = ", ".join(f"{k} {v}" for k, v in sorted(d["recent_class_counts"].items()))
    L += ["ENCOUNTERS, LAST 24 MONTHS", f"  Counts by type: {counts or 'none'}"]
    acute = d["acute"][:15]
    L.append(f"  Emergency / inpatient / urgent care ({len(acute)} of {len(d['acute'])} shown):" if d["acute"]
             else "  No emergency, inpatient or urgent care encounters")
    L += [f"  - {_d(e['START'])} {e['ENCOUNTERCLASS']}: {_clean(e['DESCRIPTION'])}"
          f"{' for ' + _clean(e['REASONDESCRIPTION']) if e['REASONDESCRIPTION'] else ''}" for e in acute]
    L.append("")
    section("MOST RECENT VISITS FOR RELATED CONDITIONS",
            [f"{_d(e['START'])} {e['ENCOUNTERCLASS']}: {_clean(e['DESCRIPTION'])} for {_clean(e['REASONDESCRIPTION'])}"
             for e in d["condition_visits"][:6]])
    section("ACTIVE CARE PLANS",
            [f"{name}{' (for ' + why + ')' if why else ''}" for name, why in d["careplans"]])
    section("OTHER FINDINGS (clinical and social)", d["social"])
    L.append("NOT IN THIS EXTRACT: free-text notes, symptoms, physical examination, "
             "patient preferences, report text for imaging.")
    return "\n".join(L)
