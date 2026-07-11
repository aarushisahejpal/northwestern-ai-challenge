(function () {
  const app = document.getElementById("app");
  statTiles(app, DATA.kpis);

  /* Player map */
  {
    const { box, cardEl } = card(app, "The player map — who lobbies on healthcare",
      "Top " + DATA.players.length + " clients with health-coded filings, sized by total federal lobbying spend 2022–2026Q1 (all issues, canonical). Color = how much of the organization's lobbying activity is health-coded.",
      "The biggest bubbles split into two species: health pure-plays (PhRMA, American Hospital Association, AHIP, AMA) whose activity is mostly health-coded, and diversified giants (U.S. Chamber, Amazon, AARP) for whom health is one desk among many. Hover for each player's health-activity share.");
    const lg = legend(cardEl, [
      { name: "Health-focused (≥50% of activities)", color: SLOT[0] },
      { name: "Mixed (20–50%)", color: SLOT[1] },
      { name: "Health is a side desk (<20%)", color: SLOT[2] }
    ]);
    cardEl.insertBefore(lg, box);
    bubblePack(box, {
      items: DATA.players.map(p => ({
        label: p.name, short: p.short, r0: p.spend || 200000, slot: p.cls, extra: p
      })),
      height: 470, fmtSize: "$",
      ttRows: d => [
        { color: SLOT[d.slot], value: fmtMoney(d.extra.spend), name: "total lobbying spend (all issues)" },
        { color: null, value: d.extra.share + "%", name: "share of activities that are health-coded" },
        { color: null, value: fmtNum(d.extra.filings), name: "health-coded senate filings" }
      ]
    });
    tableView(cardEl, ["Player", "Health filings", "Health share of activities %", "Total spend (all issues)"],
      DATA.players.map(p => [p.name, p.filings, p.share, p.spend]), ["s", "#", "%", "$"]);
  }

  /* Trend */
  {
    const { box, cardEl } = card(app, "A massive, stable machine — with a 2025 uptick",
      "Health-coded senate filings and distinct client organizations per quarter (amendment-deduped).",
      "Healthcare lobbying is an installed base: ~4,000 filings and ~2,950 clients every quarter for three straight years, then a visible 2025 rise (+9%) during the reconciliation Medicaid fight. Compare crypto's +60% breakout: healthcare doesn't surge because it never left.");
    const lg = legend(cardEl, [{ name: "Health-coded filings", color: SLOT[0] }, { name: "Distinct clients", color: SLOT[1] }], "line");
    cardEl.insertBefore(lg, box);
    linePanel(box, {
      x: DATA.trend.q, fmt: "#",
      series: [
        { name: "Health-coded filings", values: DATA.trend.filings },
        { name: "Distinct clients", values: DATA.trend.clients }
      ]
    });
    tableView(cardEl, ["Quarter", "Filings", "Clients", "Canonical spend of active clients (all-issue)"],
      DATA.trend.q.map((q, i) => [q, DATA.trend.filings[i], DATA.trend.clients[i], DATA.trend.spend[i]]),
      ["s", "#", "#", "$"]);
  }

  /* Issue mix */
  {
    const { box, cardEl } = card(app, "What kind of healthcare lobbying",
      "Health-coded filings per quarter by issue code (a filing can carry several codes).",
      "General health issues (HCR) dominate; Medicare/Medicaid (MMM) is the second pillar; pharmacy (PHA) and medical research (MED) are steady specialist lanes.");
    const lg = legend(cardEl, [
      { name: "HCR — health issues", color: SLOT[0] },
      { name: "MMM — Medicare/Medicaid", color: SLOT[1] },
      { name: "PHA — pharmacy", color: SLOT[2] },
      { name: "MED — medical research", color: SLOT[4] }
    ], "line");
    cardEl.insertBefore(lg, box);
    linePanel(box, {
      x: DATA.codeTrend.q, fmt: "#",
      series: [
        { name: "HCR — health issues", values: DATA.codeTrend.HCR, color: SLOT[0] },
        { name: "MMM — Medicare/Medicaid", values: DATA.codeTrend.MMM, color: SLOT[1] },
        { name: "PHA — pharmacy", values: DATA.codeTrend.PHA, color: SLOT[2] },
        { name: "MED — medical research", values: DATA.codeTrend.MED, color: SLOT[4] }
      ]
    });
    tableView(cardEl, ["Quarter", "HCR", "MMM", "PHA", "MED"],
      DATA.codeTrend.q.map((q, i) => [q, DATA.codeTrend.HCR[i], DATA.codeTrend.MMM[i], DATA.codeTrend.PHA[i], DATA.codeTrend.MED[i]]),
      ["s", "#", "#", "#", "#"]);
  }

  /* Press coupling */
  {
    const { box, cardEl } = card(app, "Congress talks healthcare constantly — and 2025 set records",
      "Share of all member press releases tagged to a health issue code, by quarter.",
      "Healthcare holds 14–22% of congressional messaging in a normal quarter — then climbs through 2025 to 28.8% in Q4 (reconciliation Medicaid cuts + ACA subsidy-cliff fight). Note the asymmetry with the money: press attention swings with the political calendar; the filing base barely moves. (Same divergence the ledger logged as L026.)");
    linePanel(box, {
      x: DATA.press.q, fmt: "%",
      series: [{ name: "Health share of member press releases", values: DATA.press.share, color: SLOT[5] }],
      height: 210
    });
    tableView(cardEl, ["Quarter", "Health-tagged releases", "All releases", "Share %"],
      DATA.press.q.map((q, i) => [q, DATA.press.n[i], DATA.press.all[i], DATA.press.share[i]]),
      ["s", "#", "#", "%"]);
  }

  /* Bills */
  {
    const { box, cardEl } = card(app, "The bills the industry crowds onto",
      "Bills most-named in health-coded filings, ranked by distinct clients lobbying them.",
      null);
    hbars(box, {
      items: DATA.topBills.map(d => ({ label: d.bill + (d.hint ? " — " + d.hint : ""), value: d.clients, note: fmtNum(d.filings) + " filings" })),
      fmt: "#", labelW: 380, valueName: "distinct clients"
    });
    tableView(cardEl, ["Bill", "Distinct clients", "Filings"],
      DATA.topBills.map(d => [d.bill, d.clients, d.filings]), ["s", "#", "#"]);
  }

  /* Giving */
  {
    const { box, cardEl } = card(app, "Who healthcare gives money to (disclosed LD-203) — health-focused vs mixed givers",
      "Disclosed LD-203 giving by the top-150 health lobbying organizations: " + fmtMoney(DATA.givingTotal) + " total 2022–2025, split into HEALTH-FOCUSED givers (≥50% of their lobbying activity is health-coded: AHA, AMA, ADA, PhRMA…) vs MIXED/diversified givers (<50%: AARP, Altria, insurers with big non-health books…).",
      "Organization-level attribution: the split shows WHO funds each recipient, not whether the motive was a health issue — a mixed org's giving is not health-specific. Party/state from the corpus members table; retired members hand-mapped and flagged. Raw variants in data/hc_ld203_recipients_split.csv. Election-year cadence: 2022 $28.3M · 2023 $23.8M · 2024 $32.4M · 2025 $23.3M.");
    const lg = legend(cardEl, [
      { name: "Health-focused giver (≥50% health activities)", color: SLOT[0] },
      { name: "Mixed/diversified giver (<50%)", color: SLOT[2] }
    ]);
    cardEl.insertBefore(lg, box);
    div("sub", box, "Top giving organizations (color = giver type)");
    hbars(div(null, box), {
      items: DATA.givingOrgs.map(d => ({ label: d.name, value: d.total, color: d.focused ? SLOT[0] : SLOT[2] })),
      fmt: "$", labelW: 300, rowH: 27, valueName: "disclosed giving"
    });
    div("sub", box, "Top recipients overall — split by giver type");
    groupedHBars(div(null, box), {
      items: DATA.givingTop.map(d => ({ label: d.name, a: d.a, b: d.b })),
      aName: "from health-focused orgs", bName: "from mixed/diversified orgs",
      aColor: SLOT[0], bColor: SLOT[2], labelW: 330
    });
    div("sub", box, "Members of Congress — split by giver type");
    groupedHBars(div(null, box), {
      items: DATA.givingMembers.map(d => ({ label: d.name, a: d.a, b: d.b })),
      aName: "from health-focused orgs", bName: "from mixed/diversified orgs",
      aColor: SLOT[0], bColor: SLOT[2], labelW: 330
    });
    tableView(cardEl, ["Recipient", "From health-focused", "From mixed/diversified"],
      DATA.givingTop.concat(DATA.givingMembers).map(d => [d.name, d.a, d.b]), ["s", "$", "$"]);
  }

  /* Caveats */
  {
    const c = div("card", app);
    const h = document.createElement("h2"); h.textContent = "How to read this (caveats that matter)"; c.appendChild(h);
    const ul = document.createElement("ul"); ul.className = "caveats"; c.appendChild(ul);
    DATA.caveats.forEach(t => { const li = document.createElement("li"); li.textContent = t; ul.appendChild(li); });
  }
})();
