"""The short pitch shown on the public landing page, below the demo links and the team.

A condensed version of the pitch deck. The one external figure is from the only source that
was read in full; the deck's other figures are left out until they have been checked.
"""

PITCH_CSS = """
  :root { --soft:#F3E0D5; --warm:#EDE8DA; }
  @media (prefers-color-scheme: dark) { :root { --soft:#4A342B; --warm:#3A3A37; } }
  main { max-width:980px; }
  .sec { border-top:1px solid var(--line); padding-top:26px; display:flex; flex-direction:column; gap:14px; }
  .sec h2 { font-size:1.5rem; line-height:1.2; margin:0; max-width:26ch; text-wrap:balance; }
  .sec > p { max-width:68ch; }
  .stat { display:grid; grid-template-columns:auto 1fr; gap:6px 20px; align-items:center; background:var(--soft); border-radius:10px; padding:18px 22px; }
  .stat .num { font-family: Georgia, serif; font-size:2.8rem; font-weight:500; line-height:1; color:var(--accent); font-variant-numeric:tabular-nums; }
  .stat small { grid-column:1 / -1; color:var(--muted); }
  .stat a, .sec a { color:var(--accent); }
  .stages { list-style:none; margin:0; padding:0; display:grid; grid-template-columns:repeat(auto-fit, minmax(150px, 1fr)); gap:10px; counter-reset:stage; }
  .stages li { counter-increment:stage; background:var(--panel); border:1px solid var(--line); border-radius:10px; padding:14px; display:flex; flex-direction:column; gap:6px; }
  .stages li::before { content:counter(stage); font-weight:700; color:var(--accent); font-size:.9rem; }
  .stages b { font-size:1.05rem; }
  .stages span { color:var(--muted); font-size:.92rem; }
  .stages em { font-style:normal; font-size:.85rem; margin-top:auto; padding-top:6px; border-top:1px dashed var(--line); }
  .three { display:grid; grid-template-columns:repeat(auto-fit, minmax(220px, 1fr)); gap:12px; }
  .three div, .rules div { background:var(--panel); border:1px solid var(--line); border-radius:10px; padding:16px; }
  .three b, .rules b { display:block; margin-bottom:4px; }
  .three span, .rules span { color:var(--muted); font-size:.95rem; }
  .scroll { overflow-x:auto; }
  table { border-collapse:collapse; width:100%; min-width:560px; font-size:.95rem; }
  th, td { text-align:left; vertical-align:top; padding:9px 12px; border-bottom:1px solid var(--line); }
  th { font-size:.8rem; letter-spacing:.05em; text-transform:uppercase; color:var(--muted); }
  td:first-child { font-weight:600; white-space:nowrap; }
  .rules { display:grid; grid-template-columns:repeat(auto-fit, minmax(250px, 1fr)); gap:12px; }
  .two { display:grid; grid-template-columns:repeat(auto-fit, minmax(280px, 1fr)); gap:14px; }
  .two div { border-radius:10px; padding:16px 18px; }
  .two .yes { background:var(--soft); }
  .two .no { background:var(--warm); }
  .two ul, .next { margin:8px 0 0; padding-left:20px; display:flex; flex-direction:column; gap:6px; }
  .next li::marker { color:var(--accent); font-weight:700; }
"""

PITCH_HTML = """  <section class="sec">
    <p class="eyebrow">The problem</p>
    <h2>Once a referral leaves the primary care office, nobody can see where it is.</h2>
    <p>The primary care office sends the referral and loses sight of it. The specialist office receives a packet that may lack what it needs to triage. The patient waits without knowing whether anything is happening. When a referral stalls, nothing tells anyone.</p>
    <div class="stat">
      <span class="num">34.8%</span>
      <span>of 103,737 referral scheduling attempts in one large health system ended in a documented completed appointment.</span>
      <small>Source: <a href="https://pmc.ncbi.nlm.nih.gov/articles/PMC5910374" rel="noopener">Patel et al., Journal of General Internal Medicine, 2018</a> (24 primary care sites, 2015&ndash;16). One setting; it does not measure Referral Tracker.</small>
    </div>
  </section>

  <section class="sec">
    <p class="eyebrow">How it works</p>
    <h2>Six stages, one shared record</h2>
    <p>Every handoff updates the same record. The line under each stage says who decides.</p>
    <ol class="stages">
      <li><b>Refer</b><span>The agent drafts the packet from the chart and asks follow-up questions. Patient consent is recorded.</span><em>Coordinator and doctor approve</em></li>
      <li><b>Send</b><span>The packet goes out with its urgency. The patient gets a QR code that holds only a referral number.</span><em>Coordinator sends</em></li>
      <li><b>Review</b><span>The specialist office accepts with a triage priority, asks for more information, or declines.</span><em>Specialist decides</em></li>
      <li><b>Book</b><span>The patient picks an offered appointment time or asks for another.</span><em>Patient chooses</em></li>
      <li><b>Visit</b><span>The patient shows the QR code at the front desk and is checked in.</span><em>Specialist office</em></li>
      <li><b>Reply</b><span>The specialist writes findings and a plan. Primary care is notified and the patient sees a summary.</span><em>Specialist writes</em></li>
    </ol>
  </section>

  <section class="sec">
    <p class="eyebrow">Three views</p>
    <h2>Each person sees the part that is theirs</h2>
    <div class="three">
      <div><b>Patient</b><span>A plain-language status and timeline, an appointment picker, the QR code, and messaging. Stalls and the clinical packet are deliberately not shown.</span></div>
      <div><b>Primary care office</b><span>A referral queue filtered to &ldquo;needs you&rdquo;, the packet editor with open items marked, and an activity log of every update.</span></div>
      <div><b>Specialist office</b><span>A board from incoming to closed, where the specialist triages, asks for what is missing, and writes the reply.</span></div>
    </div>
  </section>

  <section class="sec">
    <p class="eyebrow">AI and people</p>
    <h2>The agent drafts and flags. People decide and send.</h2>
    <div class="scroll">
      <table>
        <tr><th>Task</th><th>What the AI agent does</th><th>What a person decides</th></tr>
        <tr><td>Referral packet</td><td>Drafts it from the chart, lists what it could not confirm, asks follow-up questions.</td><td>The coordinator reviews it; the doctor confirms the clinical question and urgency.</td></tr>
        <tr><td>Stalled referral</td><td>Flags it and drafts a nudge or a booking reminder.</td><td>The coordinator reviews the draft and sends it.</td></tr>
        <tr><td>Patient messages</td><td>Answers clear status or scheduling questions, only from the tracker&rsquo;s status.</td><td>A nurse handles anything about health and anything unclear.</td></tr>
        <tr><td>Visit</td><td>Sends visit preparation notes; alerts the clinic if the visit is missed.</td><td>Staff check the patient in; someone calls to rebook a missed visit.</td></tr>
        <tr><td>Specialist reply</td><td>Matches the reply to the referral and notifies the primary care doctor.</td><td>The specialist writes the findings and the plan.</td></tr>
      </table>
    </div>
  </section>

  <section class="sec">
    <p class="eyebrow">Safety and trust</p>
    <h2>Design rules that limit what can go wrong</h2>
    <div class="rules">
      <div><b>No medical advice</b><span>Any message about symptoms, medicines, doses or results goes to a nurse with no automatic answer.</span></div>
      <div><b>A keyword rule comes before any AI</b><span>Health messages are caught by a plain rule first. Unclear messages also go to a nurse.</span></div>
      <div><b>Unconfirmed facts are named</b><span>The agent lists what it could not confirm. A packet with open placeholders cannot be approved.</span></div>
      <div><b>The QR code carries no medical details</b><span>It holds a referral number only, on a phone or on paper.</span></div>
      <div><b>The model sees a curated extract</b><span>Each specialty gets the part of the chart that specialist needs, not the whole record.</span></div>
      <div><b>Not yet reviewed</b><span>These are design choices in a prototype. It has not been through a clinical safety or security review.</span></div>
    </div>
  </section>

  <section class="sec">
    <p class="eyebrow">Where it stands</p>
    <h2>A prototype, not a product</h2>
    <div class="two">
      <div class="yes"><b>What works</b>
        <ul>
          <li>The six-stage flow runs end to end for type 2 diabetes, primary care to endocrinology.</li>
          <li>Three views in one app: patient, primary care office, specialist office.</li>
          <li>With an API key, Claude drafts the packet, asks follow-up questions, revises the draft and routes patient messages.</li>
          <li>Note drafting also covers nephrology, cardiology and orthopedic surgery referrals.</li>
        </ul>
      </div>
      <div class="no"><b>What is simulated or missing</b>
        <ul>
          <li>All patients are synthetic. No real patient data has been used.</li>
          <li>Office, insurer and specialist actions are simulated. There is no EHR, payer or scheduling integration.</li>
          <li>Demo state lives in one browser; a record shared across sites is not built.</li>
          <li>Not clinically validated. No pilot, no customers, no outcomes data.</li>
        </ul>
      </div>
    </div>
  </section>

  <section class="sec">
    <p class="eyebrow">What comes next</p>
    <h2>Five steps to a first pilot</h2>
    <ol class="next">
      <li><b>EHR integration through FHIR.</b> Read the chart from a real record system.</li>
      <li><b>A shared multi-site record.</b> One record both offices and the patient reach.</li>
      <li><b>Real payer checks.</b> Live eligibility and referral approval.</li>
      <li><b>Clinical safety review.</b> Independent review of the drafting and message rules before real patients.</li>
      <li><b>Pilot.</b> One clinic and one specialist group, measuring time to scheduled, loop closure and coordinator workload.</li>
    </ol>
    <p>No dates are committed, and the order is a proposal.</p>
  </section>

"""
