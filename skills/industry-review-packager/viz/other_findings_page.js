/* other_findings_page.js — a single reference page for investigation-ledger
   leads that don't fall inside any shipped industry package. Reuses the same
   card/finding-item look as every package dashboard's "findings" section, but
   this page IS the whole thing (no charts, no CSVs) — copy comes straight
   from DATA (hand-curated from LEDGER.md, not auto-derived). */
(function () {
  const app = document.getElementById("app");
  statTiles(app, DATA.kpis);

  {
    const c = div("card", app);
    const h = document.createElement("h2");
    h.textContent = "Leads not covered by a package";
    c.appendChild(h);
    div("sub", c, "Each of these was investigated far enough to pass triage (a named actor, date, and record ID) but sits outside the five industry maps above — either a one-off lead in a field we haven't built a package for, or a thread the team parked or closed. Full history in LEDGER.md.");
    for (const f of DATA.findings) {
      const item = div("finding-item", c);
      const head = document.createElement("strong");
      head.textContent = f.id + " · " + f.status + " — " + f.title;
      item.appendChild(head);
      div(null, item, f.hypothesis);
      if (f.actors) div("note", item, "Named actors: " + f.actors);
      if (f.next) div("note", item, "Next action: " + f.next);
    }
  }

  {
    const c = div("card", app);
    const h = document.createElement("h2");
    h.textContent = "Entities checked and set aside";
    c.appendChild(h);
    div("sub", c, "Sat at the top of a lens ranking but were judged already-obvious or non-novel — recorded so the leads above are shown to come from underneath them, not instead of looking at them.");
    const cols = ["Entity", "Verdict", "Records examined", "Date"];
    tableView(c, cols, DATA.entitiesChecked.map(e => [e.entity, e.verdict, e.records, e.date]),
      ["s", "s", "s", "s"]);
  }

  {
    const c = div("card", app);
    const h = document.createElement("h2"); h.textContent = "How to read this"; c.appendChild(h);
    const ul = document.createElement("ul"); ul.className = "caveats"; c.appendChild(ul);
    DATA.caveats.forEach(t => { const li = document.createElement("li"); li.textContent = t; ul.appendChild(li); });
  }
})();
