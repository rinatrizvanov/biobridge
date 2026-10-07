// BioBridge page behaviour: job progress polling and chart tooltips. No external code.
(function () {
  "use strict";

  // --- Job progress -------------------------------------------------------------------
  const job = document.getElementById("bb-job");
  if (job && job.dataset.status === "running") {
    const text = document.getElementById("bb-progress-text");
    const bar = document.getElementById("bb-progress-bar");
    const poll = async () => {
      try {
        const response = await fetch(`/jobs/${job.dataset.job}/status`, { credentials: "same-origin", cache: "no-store" });
        if (response.ok) {
          const s = await response.json();
          if (s.status !== "running") { window.location.reload(); return; }
          text.textContent = s.message;
          if (s.total) { bar.max = s.total; bar.value = s.done || 0; } else { bar.removeAttribute("value"); }
        }
      } catch (error) { /* keep polling; the server may be busy */ }
      window.setTimeout(poll, 700);
    };
    window.setTimeout(poll, 400);
  }

  // --- Chart tooltips (the same values are in the table under each chart) -------------
  const MARGIN = 8;   // distance from the window edges
  const GAP = 10;     // distance from the event being described
  const tip = document.createElement("div");
  tip.className = "bb-tooltip";
  tip.hidden = true;
  tip.setAttribute("role", "status");
  document.addEventListener("DOMContentLoaded", () => document.body.appendChild(tip));

  function row(keyClass, value, label) {
    const div = document.createElement("div");
    div.className = "bb-tip-row";
    const key = document.createElement("span");
    key.className = `bb-key ${keyClass}`;
    const strong = document.createElement("span");
    strong.className = "bb-tip-value";
    strong.textContent = value;
    const name = document.createElement("span");
    name.className = "bb-tip-sub";
    name.textContent = label;
    div.append(key, strong, name);
    return div;
  }

  let active = null;   // the event whose values are showing

  function show(mark) {
    active = mark;
    tip.replaceChildren();
    const title = document.createElement("div");
    title.className = "bb-tip-title";
    title.textContent = mark.dataset.event;
    const where = document.createElement("div");
    where.className = "bb-tip-sub";
    where.textContent = mark.dataset.position;
    tip.append(title, row("bb-key-1", mark.dataset.masked, "masked"), row("bb-key-2", mark.dataset.raw, "raw"), where);
    tip.hidden = false;
    place(mark);
  }

  function place(mark) {
    const box = mark.getBoundingClientRect();
    const width = tip.offsetWidth, height = tip.offsetHeight;
    const left = Math.min(window.innerWidth - width - MARGIN, Math.max(MARGIN, box.left + box.width / 2 - width / 2));
    let top = box.top - height - GAP;                       // above the event if it fits
    if (top < MARGIN) top = Math.min(box.bottom + GAP, window.innerHeight - height - MARGIN);
    tip.style.left = `${Math.max(MARGIN, left)}px`;
    tip.style.top = `${Math.max(MARGIN, top)}px`;
  }

  function hide() { tip.hidden = true; active = null; }
  // The tooltip is fixed to the window, so follow the event when the page scrolls or resizes.
  const follow = () => { if (active && !tip.hidden) place(active); };

  document.addEventListener("pointerover", (e) => { const m = e.target.closest(".bb-mark"); if (m) show(m); });
  document.addEventListener("pointerout", (e) => { if (e.target.closest(".bb-mark")) hide(); });
  document.addEventListener("focusin", (e) => { const m = e.target.closest(".bb-mark"); if (m) show(m); });
  document.addEventListener("focusout", (e) => { if (e.target.closest(".bb-mark")) hide(); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") hide(); });
  window.addEventListener("scroll", follow, { passive: true });
  window.addEventListener("resize", follow);
})();
