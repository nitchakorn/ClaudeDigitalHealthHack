# PCP input for the 33 eval cases

Written by Claude Fable 5.2 on 2026-11-21 from each chart. Clinician review: pending.

Each case gives the drafter three things a PCP would type: urgency, an optional clinical question, and notes that open with the reason for referral now.
A blank question is deliberate: the drafter must then propose one and mark it [suggested - confirm].

To change a case, edit eval/cases.json (this file is generated from it) or tell Claude what to change.

## Build (cardiology, 15 cases)

| # | Patient | To | Urgency | Clinical question | PCP notes |
|---|---|---|---|---|---|
| 1 | Bill Reynolds | Cardiology | routine | Does he need stress testing or repeat angiography, and should his anti-anginal therapy change? | Reason for referral now: over the past three months he has had chest tightness when climbing two flights of stairs that settles within five minutes of rest; no pain at rest. He has not seen cardiology since his stent. |
| 2 | Chas Legros | Cardiology | routine | (blank) | Reason for referral now: cardiology review is overdue; he says he has had no cardiology follow-up for several years. He reports no chest pain and walks daily. |
| 3 | Cleta Vandervort | Cardiology | routine | Is her current combination of cardiac medicines appropriate at her age, and can any be stopped? | Reason for referral now: two episodes of lightheadedness on standing in the past month, one with a near fall. Her daughter, who attends with her, asks whether her heart medicines can be simplified. |
| 4 | Eulah Kessler | Cardiology | routine | (blank) | Reason for referral now: new breathlessness on walking uphill over the past six weeks, with no chest pain, orthopnea or ankle swelling. Chest clear on examination today. |
| 5 | Freddy Hoppe | Cardiology | routine | Is he fit for elective hernia surgery from a cardiac standpoint, and how should clopidogrel be managed around it? | Reason for referral now: he is listed for an elective inguinal hernia repair and the surgical team has asked for a cardiology opinion first. He reports no chest pain or breathlessness. |
| 6 | Granville Heathcote | Cardiology | urgent | (blank) | Reason for referral now: three weeks of dizziness on standing and two near-faints; blood pressure in clinic today was low. No chest pain. |
| 7 | Jerrold Bartell | Cardiology | routine | Does he need ambulatory rhythm monitoring? | Reason for referral now: palpitations several times a week for the past two months, each lasting a few minutes, without fainting or chest pain. Pulse regular on examination today. |
| 8 | Justine Murphy | Cardiology | routine | What lipid-lowering treatment do you recommend given statin intolerance? | Reason for referral now: she stopped taking simvastatin about four months ago because of muscle aches and does not want to restart it. No chest pain since her stent. |
| 9 | Kam Harris | Cardiology | urgent | (blank) | Reason for referral now: worsening breathlessness over two weeks, now breathless after walking across a room, with new swelling of both ankles. She is sleeping on three pillows. |
| 10 | Leo Altenwerth | Cardiology | routine | Is repeat echocardiography or stress testing warranted? | Reason for referral now: over the past six months he tires more easily on his usual two-mile walk and has to stop once to rest. No chest pain, and no breathlessness at rest. |
| 11 | Orval Runolfsdottir | Cardiology | routine | (blank) | Reason for referral now: the dialysis unit reports that his blood pressure drops during sessions and has asked for a cardiology review. He describes chest heaviness near the end of some dialysis sessions. |
| 12 | Raúl Delatorre | Cardiology | routine | Is any change to his cardiac medicines advisable, given his age and his wish to avoid procedures? | Reason for referral now: his family asks whether any further cardiac tests or treatment are worthwhile at his age. He is comfortable at rest and walks indoors with a frame; he says he does not want hospital procedures. |
| 13 | Tama Moore | Cardiology | urgent | Does she need urgent angiography or a change in anti-anginal treatment? | Reason for referral now: she has used her nitroglycerin spray four or five times a week for the past month, up from about once a month, for chest pressure brought on by walking. No pain at rest. |
| 14 | Ulysses Dach | Cardiology | routine | (blank) | Reason for referral now: mild ankle swelling in the evenings for the past two months, and he now sleeps on two pillows. He says he has had no cardiology follow-up since his bypass surgery. |
| 15 | Walton Collier | Cardiology | routine | Does his heart function need reassessment, and is he a candidate for a defibrillator? | Reason for referral now: he asks whether he should have a defibrillator after reading about them. He reports no fainting, palpitations or chest pain and walks a mile daily without symptoms. |

## Carry-over check (8 cases)

| # | Patient | To | Urgency | Clinical question | PCP notes |
|---|---|---|---|---|---|
| 16 | Kam Harris | Nephrology | routine | Should metformin and her diuretic dose be changed at her current kidney function? | Reason for referral now: her kidney function has continued to fall and I would like advice on slowing it. She reports no change in urine output and no nausea or itching. |
| 17 | Raúl Delatorre | Nephrology | routine | (blank) | Reason for referral now: his family asks what to expect as his kidney function declines and whether dialysis would ever be considered. He has told me he would not want dialysis. |
| 18 | Tama Moore | Nephrology | urgent | Is the recent decline reversible, and which of her medicines should be stopped or adjusted? | Reason for referral now: over the past month she has had increasing ankle swelling, poor appetite and nausea most mornings. She takes naproxen daily for knee pain and I have asked her to stop. |
| 19 | Walton Collier | Nephrology | routine | (blank) | Reason for referral now: first nephrology referral; his kidney tests have worsened this year and he wants to know what he can do to avoid dialysis. He feels well and reports no swelling or change in urination. |
| 20 | Eulah Kessler | Orthopedics | routine | Is she a candidate for total knee replacement? | Reason for referral now: right knee pain now limits her to walking about 100 meters and wakes her at night, despite daily naproxen and a walking stick for the past year. She wants to know whether a knee replacement is an option. |
| 21 | Leo Altenwerth | Orthopedics | routine | (blank) | Reason for referral now: left knee pain and stiffness have worsened over six months; he can no longer manage stairs without holding the rail. A steroid injection in my clinic in August gave relief for only three weeks. |
| 22 | Orval Runolfsdottir | Orthopedics | routine | Is he a surgical candidate given his kidney disease, or should we pursue injections? | Reason for referral now: right knee pain limits him to short distances and he struggles to get in and out of the transport to his dialysis sessions. He has tried acetaminophen and a knee brace for about eight months without benefit. |
| 23 | Tama Moore | Orthopedics | routine | (blank) | Reason for referral now: both knees are painful but the left is worse, and she can no longer do her own shopping. She has had physical therapy twice in the past two years with little lasting benefit and asks about surgery. |

## Test, held out (10 cases)

| # | Patient | To | Urgency | Clinical question | PCP notes |
|---|---|---|---|---|---|
| 24 | Edward Baumbach | Cardiology | routine | Does he need non-invasive testing for ischemia? | Reason for referral now: chest discomfort on brisk walking for the past two months, relieved by slowing down; he has used his nitroglycerin spray twice. He does not recall ever having a stress test or angiogram. |
| 25 | Grover Swaniawski | Cardiology | routine | (blank) | Reason for referral now: yearly review after his stent; he feels well and cycles 30 minutes most days without symptoms. He asks whether he still needs clopidogrel. |
| 26 | Jamey McLaughlin | Cardiology | urgent | (blank) | Reason for referral now: repeated urgent care visits recently for breathlessness and fatigue; today she is breathless on minimal exertion with swelling to mid-shin. She lives with her son and wishes to stay at home rather than be admitted. |
| 27 | Marco Wisozk | Cardiology | routine | Should his blood pressure treatment be reduced, and how long should he continue clopidogrel? | Reason for referral now: follow-up after his stent in June; since then he reports lightheadedness most mornings and has skipped some doses of his blood pressure tablets because of it. No chest pain since the procedure. |
| 28 | Spencer Wunsch | Cardiology | urgent | Does he need urgent repeat angiography? | Reason for referral now: chest pain at rest lasting ten minutes on two occasions in the past week, relieved by nitroglycerin spray; pain-free in clinic today. He declined to go to the emergency department. |
| 29 | Jamey McLaughlin | Nephrology | routine | Which of her medicines should be reduced or stopped at this level of kidney function? | Reason for referral now: her kidney function has declined further and her son asks whether her medicines are still safe for her kidneys. She has had two falls at home in the past two months and eats little. |
| 30 | Marco Wisozk | Nephrology | routine | (blank) | Reason for referral now: he was told at an urgent care visit that his kidneys are failing and is very anxious about it; he asks to see a kidney specialist. He reports no urinary symptoms or swelling. |
| 31 | Grover Swaniawski | Orthopedics | routine | Is there a mechanical problem that needs imaging or arthroscopy? | Reason for referral now: his right knee gives way two or three times a week and locked once last month; pain is otherwise mild. He cycles regularly and wants to stay active. |
| 32 | Spencer Wunsch | Orthopedics | routine | (blank) | Reason for referral now: left hip pain has worsened over the past year; he now uses a cane, cannot put on his own socks and wakes most nights. Acetaminophen and naproxen no longer control it and he wants to discuss hip replacement. |
| 33 | Zula Donnelly | Orthopedics | routine | What non-surgical options remain, and when should surgery be considered? | Reason for referral now: right knee pain when climbing stairs and after standing for long periods; she completed a course of physical therapy a year ago with partial benefit. She is not sure she wants surgery and asks what else can be offered. |
