# Referral Tracker (hackathon prototype)

Two pages on one backend, both on synthetic Synthea patients:

- **Referral tracker** (`/tracker`): one shared referral record seen three ways. The patient
  sees a plain status page, the PCP office sees a work queue, the specialist office sees a
  board. Demo scenario: type 2 diabetes, primary care to endocrinology.
- **Note drafter** (`/`): pick a patient and a referral condition and Claude drafts the
  referral note, asks follow-up questions, and revises the note with the answers. Covers
  endocrinology, nephrology, cardiology and orthopedic surgery referrals.

## The referral flow

| Stage | What happens | Who decides |
|---|---|---|
| 1 Refer | Agent drafts the packet from the chart and asks follow-up questions. Consent, eligibility and the insurance referral are recorded. | Coordinator approves; the doctor confirms the question and urgency; the patient consents |
| 2 Send | Packet goes to the specialist office. The patient gets a referral QR code that holds only a referral number. | Coordinator sends |
| 3 Review | Specialist office confirms receipt, then accepts with a triage priority, asks for more information, or declines (the PCP office redirects it). | Specialist |
| 4 Book | Patient picks an offered time or asks for another. | Patient |
| 5 Visit | Patient shows the QR code and is checked in. | Specialist office |
| 6 Reply | Specialist writes findings and plan. The PCP is notified and the patient sees a summary. | Specialist |

The agent drafts and flags; people decide and send. It flags a referral with no receipt,
a patient who has not booked, and a missed visit, and drafts the nudge or reminder for the
coordinator to send. Patient messages about status or scheduling get an automatic answer
from the tracker status; anything about health, or unclear, goes to a nurse.

Office, payer and specialist actions are simulated, and tracker state is kept in the
browser. There is no EHR, payer or scheduling integration.

## Run

Needs Python 3.10+ and Node.js (Node is only used to run the scripts).

```
npm install     # creates .venv and installs the Python packages
npm run dev     # starts the server with reload
```

Open http://localhost:8000/tracker for the tracker or http://localhost:8000 for the note
drafter. To use another port: set the `PORT` environment variable.

`npm test` walks the six-stage flow in all three views against the running server.

The flow: **Draft note** writes the note from the chart, Claude then asks follow-up
questions about the draft, and **Update note with answers** revises it.

## Public demo

A static copy runs at https://referral-notes.nitchakorn.workers.dev with no server and no
AI model: drafts there are labelled templates. To rebuild and redeploy it:

```
npm run build:static
cf deploy site
```

## Going live

Copy `.env.example` to `.env`, paste the key after `ANTHROPIC_API_KEY=`, and restart the
server. The badge in the header switches from "Mock mode" to "Live". Without a key the
draft is a fixed template, not model output.

## Layout

- `app/data.py`: loads the Synthea CSVs, defines the three cohorts, builds the chart extract.
  Per-condition labs, relevance rules and specialist guidance live in `CONDITIONS`.
- `app/llm.py`: system prompt and the Claude API call (streaming).
- `app/main.py`: HTTP API. `POST /api/referrals` streams newline-delimited JSON events.
- `static/tracker.html`: the referral tracker (patient, PCP office, specialist office).
- `static/index.html`: the note drafter.
- `tests/tracker.test.js`: headless walk-through of the tracker.
- `data/synthea/`: Synthea sample export (120 synthetic patients, no real patient data).
