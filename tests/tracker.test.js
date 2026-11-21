// Loads the tracker page from the running server in jsdom and walks the six-stage flow in all three views.
const { JSDOM, VirtualConsole } = require("jsdom");

const BASE = process.env.BASE || "http://localhost:8000";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const errors = [];

async function until(fn, label, ms = 8000) {
  const end = Date.now() + ms;
  while (Date.now() < end) { const v = fn(); if (v) return v; await sleep(50); }
  throw new Error("timed out waiting for: " + label);
}

(async () => {
  const vc = new VirtualConsole();
  vc.on("jsdomError", (e) => errors.push(String(e.message || e)));
  vc.on("error", (e) => errors.push(String(e)));
  const dom = await JSDOM.fromURL(BASE + "/tracker", {
    runScripts: "dangerously", pretendToBeVisual: true, virtualConsole: vc,
    beforeParse(window) {
      window.fetch = (url, opts) => fetch(new URL(url, BASE), opts);
      window.TextDecoder = TextDecoder;
      window.Element.prototype.scrollIntoView = () => {};
    },
  });
  const { document } = dom.window, $ = (id) => document.getElementById(id);
  const click = (el) => el.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
  const type = (el, v) => { el.value = v; el.dispatchEvent(new dom.window.Event("input", { bubbles: true })); };
  const check = (el) => { el.checked = true; el.dispatchEvent(new dom.window.Event("change", { bubbles: true })); };
  const btn = (label) => until(() => [...document.querySelectorAll("#main button.btn")].find((x) => x.textContent.includes(label) && !x.disabled), label);
  const press = async (label) => click(await btn(label));
  const view = (name) => click(document.querySelector(`[data-persona="${name}"]`));
  const stamp = () => document.querySelector(".stamp").firstChild.textContent;
  const heading = () => document.querySelector(".phone h1").textContent;
  const out = [];

  // Stage 1 Refer: draft, follow-up questions, consent, approval, insurance
  await until(() => document.querySelector(".queue button"), "PCP queue");
  await until(() => !/Checking/.test($("claudeMode").textContent), "mode");
  out.push("mode: " + $("claudeMode").textContent);
  out.push("selected: " + document.querySelector("#main h1").textContent + " | " + document.querySelector(".eyebrow").textContent);
  click($("draftBtn"));
  await until(() => $("packet").value.length > 50, "draft");
  click($("askBtn"));
  await until(() => $("fu0"), "follow-up questions");
  type($("fu0"), "No hypoglycemia reported");
  click($("updateBtn"));
  await until(() => /No hypoglycemia reported/.test($("packet").value), "packet update");
  type($("packet"), $("packet").value.replace("[suggested - confirm] ", "").replace(/TO CONFIRM BEFORE SENDING[\s\S]*?(?=\n\nADDITIONAL|$)/, "").trim());
  check($("reviewed")); check($("pcpOk"));
  out.push("approve without consent: " + ($("approve").disabled ? "blocked" : "ALLOWED (wrong)"));
  check($("consent"));
  out.push("approve with consent: " + ($("approve").disabled ? "BLOCKED (wrong)" : "allowed"));
  for (const label of ["Approve packet", "Check eligibility", "Submit HMO referral", "Send referral"]) await press(label);
  out.push("after send: " + stamp() + " | " + document.querySelector(".eyebrow").textContent.split(" · ").slice(0, 2).join(" · "));

  // Stage 2 Send: the patient holds a referral code
  view("patient");
  await until(() => $("refCode"), "referral code");
  const code = $("refCode").textContent;
  out.push("patient referral code: " + code);

  // Stage 3 Review: decline, redirect, then more info, then accept
  view("endo");
  click(await until(() => [...document.querySelectorAll(".board .card")].find((x) => x.textContent.includes("Forest")), "Forest card"));
  await press("Confirm receipt");
  type(await until(() => $("declineWhy"), "decline box"), "Not taking new patients before March");
  await press("Decline");
  view("patient");
  out.push("patient sees on decline: " + heading() + " / stamp " + stamp());
  view("pcp");
  click(await until(() => [...document.querySelectorAll(".queue button")].find((x) => x.textContent.includes("Forest")), "Forest in queue"));
  out.push("PCP queue status: " + [...document.querySelectorAll(".queue button")].find((x) => x.textContent.includes("Forest")).querySelector(".st").textContent);
  await press("Send to Lakeside");
  view("endo");
  click(await until(() => [...document.querySelectorAll(".board .card")].find((x) => x.textContent.includes("Forest")), "Forest card again"));
  await press("Confirm receipt");
  type(await until(() => $("infoAsk"), "info box"), "Please send the latest lipid panel");
  await press("Request");
  view("patient");
  out.push("patient sees on info request: " + heading());
  view("pcp");
  type(await until(() => $("infoReply"), "info reply box"), "Lipid panel attached");
  await press("Send reply to Endo office");
  view("endo");
  await press("Accept referral");
  out.push("after accept: " + stamp());

  // Stage 4 Book: pick a time, ask for another, pick again
  view("patient");
  await until(() => document.querySelector(".slots button"), "slots");
  click(document.querySelector(".slots button"));
  await until(() => $("otherTime"), "booked");
  const first = document.querySelector(".phone .chip.accent").textContent;
  click($("otherTime"));
  await until(() => document.querySelector(".slots button"), "new slots");
  click(document.querySelector(".slots button"));
  await until(() => $("otherTime"), "rebooked");
  out.push("booked: " + first + " -> asked for another time -> " + document.querySelector(".phone .chip.accent").textContent);

  // Stage 5 Visit: check in by QR code
  view("endo");
  await press("Scan QR code + check in");
  out.push("after check-in: " + stamp());
  view("patient");
  out.push("patient sees at visit: " + heading());

  // Stage 6 Reply: findings and plan, patient summary, PCP reads reply
  view("endo");
  await press("Send reply + close the loop");
  view("patient");
  out.push("patient after reply: " + heading() + " | " + document.querySelector(".phone .lead").textContent.slice(0, 60));
  view("pcp");
  out.push("PCP sees reply: " + !![...document.querySelectorAll("#main .lbl")].find((x) => x.textContent.startsWith("Reply from Lakeside")));

  // Patient messages: status question answered, health question to a nurse
  view("patient");
  for (const text of ["Did the office get my referral?", "My sugar is high, should I take more metformin?"]) {
    const before = document.querySelectorAll(".msgs li").length;
    type($("ask"), text);
    click([...document.querySelectorAll(".phone button")].find((x) => x.textContent === "Send"));
    await until(() => document.querySelectorAll(".msgs li").length >= before + 2 && !$("ask").disabled, "reply to: " + text);
    out.push("message route: " + [...document.querySelectorAll(".msgs li")].pop().querySelector("small").textContent);
  }

  // Off track: a booked patient (Pandora) misses the visit
  for (let i = 0; i < 16; i++) click($("advance"));
  view("pcp");
  click([...document.querySelectorAll("#main .tabs button")].find((x) => x.textContent.startsWith("All")));
  const row = await until(() => [...document.querySelectorAll(".queue button")].find((x) => x.textContent.includes("Pandora")), "Pandora in queue");
  out.push("missed visit status: " + row.querySelector(".st").textContent);
  click(row);
  await press("Called the patient");
  out.push("after rebook offer: " + stamp());

  // A scanned code opens the patient page for that referral
  const dom2 = new JSDOM("", { url: BASE + "/tracker?ref=" + code + "#patient" });
  out.push("QR link target: " + dom2.window.location.search + dom2.window.location.hash);

  console.log(out.join("\n"));
  console.log(errors.length ? "PAGE ERRORS:\n" + errors.join("\n") : "no page errors");
  process.exit(errors.length ? 1 : 0);
})().catch((e) => { console.error("TEST FAILED:", e.message, "\n", errors.join("\n")); process.exit(1); });
