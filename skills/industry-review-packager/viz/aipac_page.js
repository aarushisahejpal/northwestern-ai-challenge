(function () {
  const app = document.getElementById("app");
  statTiles(app, DATA.kpis);

  /* Spend + press coupling: two panels, shared x (never a dual axis) */
  {
    const { box, cardEl } = card(app, "AIPAC's lobbying budget is a slow ratchet; the news cycle is not",
      "Top panel: AIPAC's reported quarterly lobbying amount (in-house LD-2 filings). Bottom panel: share of ALL congressional member press releases mentioning Israel/Gaza-related terms — same quarters, same x-axis.",
      "After October 7, 2023 the press share jumps 2.6% → 20.3% in one quarter (~8×). AIPAC's lobbying spend moves +6.6% that quarter and just keeps its steady ~9%/yr climb — $690K (2022-Q1) to a $974K peak (2025-Q4). Read: lobbying budgets are planned annual infrastructure, not news-reactive spending.");
    const sub1 = div("sub", null); sub1.textContent = "AIPAC reported lobbying amount per quarter";
    box.appendChild(sub1);
    const b1 = div(null, box);
    columns(b1, {
      x: DATA.coupling.q, fmt: "$", height: 220,
      series: [{ name: "AIPAC reported quarterly amount", values: DATA.coupling.amount, color: SLOT[0] }]
    });
    const sub2 = div("sub", null); sub2.textContent = "Israel-topic share of all member press releases (%)";
    box.appendChild(sub2);
    const b2 = div(null, box);
    linePanel(b2, {
      x: DATA.coupling.q, fmt: "%", height: 200,
      series: [{ name: "Israel-topic share of member releases", values: DATA.coupling.share, color: SLOT[5] }]
    });
    tableView(cardEl, ["Quarter", "AIPAC amount", "Israel-topic releases", "All releases", "Share %"],
      DATA.coupling.q.map((q, i) => [q, DATA.coupling.amount[i], DATA.coupling.rel[i], DATA.coupling.all[i], DATA.coupling.share[i]]),
      ["s", "$", "#", "#", "%"]);
  }

  /* Who is lobbied */
  {
    const { box, cardEl } = card(app, "Who AIPAC lobbies",
      "Government entities named on AIPAC's quarterly filings, 2022–2026Q1 (activity-level mentions).",
      "Beyond both chambers: DOD, DHS, State, Treasury, the NSC — and the Energy Department (civil-nuclear and Iran-sanctions issues ride with the security portfolio).");
    hbars(box, {
      items: DATA.govEntities.map(d => ({ label: d.name, value: d.n })),
      fmt: "#", labelW: 330, valueName: "mentions on filings"
    });
    tableView(cardEl, ["Entity", "Mentions"], DATA.govEntities.map(d => [d.name, d.n]), ["s", "#"]);
  }

  /* What they talk about: issue mix + bills note — table-forward card */
  {
    const { box, cardEl } = card(app, "What the filings talk about",
      "Every AIPAC activity is coded BUD (appropriations), FOR (foreign relations), or DEF (defense) — plus a handful of AGR/TRD/HOM entries. The activity text names specific bills: " + DATA.nBills + " distinct bills across 17 quarters.",
      "Recurring subjects: security assistance appropriations to Israel, Iran sanctions bills, U.S.-Israel defense-partnership acts, antisemitism-related resolutions. Full activity text (their own words, citable) is in data/aipac_activities.csv.");
    hbars(box, {
      items: DATA.topBills.map(d => ({ label: d.bill + (d.hint ? " — " + d.hint : ""), value: d.n, note: "quarterly filings naming it" })),
      fmt: "#", labelW: 380, valueName: "AIPAC filings naming the bill"
    });
    tableView(cardEl, ["Bill", "AIPAC filings", "First year", "Last year"],
      DATA.billsTable.map(d => [d.bill, d.n, d.y0, d.y1]), ["s", "#", "s", "s"]);
  }

  /* Co-lobbyists */
  {
    const { box, cardEl } = card(app, "Who else lobbies AIPAC's bills",
      "Organizations lobbying the same distinctive bills as AIPAC (bills with ≤200 lobbying engagements corpus-wide, so mega-bills like the NDAA don't drown the signal). Ranked by number of shared bills.",
      "Both camps show up: allied groups (FDD Action, Hadassah, Republican Jewish Coalition, Christians United for Israel) AND opposing ones (J Street, Friends Committee on National Legislation, ACLU, MoveOn, Amnesty). Sharing a bill means lobbying ON it, not necessarily the same side — the overlap maps the battlefield, not the alliance.");
    hbars(box, {
      items: DATA.coLobby.map(d => ({ label: d.name, value: d.bills, note: fmtNum(d.filings) + " filings on those bills" })),
      fmt: "#", labelW: 360, valueName: "shared distinctive bills"
    });
    tableView(cardEl, ["Organization", "Shared distinctive bills", "Filings on those bills"],
      DATA.coLobby.map(d => [d.name, d.bills, d.filings]), ["s", "#", "#"]);
  }

  /* Israel-policy field */
  {
    const { box, cardEl } = card(app, "The wider Israel-policy lobbying field",
      "Clients whose senate filing free-text mentions Israel/Gaza-related terms, ranked by matching filings (exploratory whole-word scan, ≥2 filings). Total lobbying spend (all issues) in the tooltip.",
      "AIPAC sits in a crowded field: ADL, Republican Jewish Coalition, J Street, FDD Action, CUFI, ZOA, Jewish Federations, Hadassah, AJC — plus non-obvious entries like Chevron (Eastern-Mediterranean gas leases) and terror-victim litigation estates. Exploratory scan, not the curated lexicon pipeline; promote to a lexicon facet before citing in a finding.");
    hbars(box, {
      items: DATA.israelPlayers.map(d => ({ label: d.name, value: d.n, note: "total all-issue spend " + fmtMoney(d.spend) })),
      fmt: "#", labelW: 360, valueName: "filings mentioning Israel terms"
    });
    tableView(cardEl, ["Client", "Israel-term filings", "Total spend (all issues)"],
      DATA.israelPlayers.map(d => [d.name, d.n, d.spend]), ["s", "#", "$"]);
  }

  /* Giving */
  {
    const ps = DATA.partySplit || {};
    const psLine = ["R", "D", "I"].filter(p => ps[p]).map(p =>
      fmtMoney(ps[p].total) + " to " + ps[p].n + " " + (p === "R" ? "Republicans" : p === "D" ? "Democrats" : "Independents")).join(" · ");
    const { box, cardEl } = card(app, "AIPAC's disclosed political giving (LD-203)",
      "Top recipients of AIPAC's disclosed LD-203 contributions, 2022–2025. Total: " + fmtMoney(DATA.givingTotal) + " (amendment-deduplicated), 100% FECA contributions, clear election-year cadence. Member-matched giving splits " + psLine + " — bipartisan, tilted Republican ~63:37 by dollars.",
      "Party/state brackets from the corpus members table (retired members hand-mapped, flagged in the CSV); committees, PACs and joint-fundraising entries carry no bracket. NOT shown here (different legal regime): AIPAC-affiliated Super-PAC spending (e.g. United Democracy Project) lives in FEC data, outside LD-203 — the same disclosure gap as crypto's Fairshake. LD-203 reports are registrant-filed; recipient strings lightly normalized.");
    hbars(box, {
      items: DATA.givingRecipients.map(d => ({ label: d.name, value: d.total, note: fmtNum(d.items) + " reported items" })),
      fmt: "$", labelW: 300, valueName: "disclosed LD-203 contributions"
    });
    const sub2 = div("sub", null); sub2.textContent = "By year — election-year cadence";
    cardEl.insertBefore(sub2, cardEl.querySelector(".foot"));
    const b2 = div(null, null); cardEl.insertBefore(b2, cardEl.querySelector(".foot"));
    columns(b2, {
      x: DATA.givingByYear.map(d => String(d.y)), fmt: "$", height: 170,
      series: [{ name: "Disclosed LD-203 giving", values: DATA.givingByYear.map(d => d.total), color: SLOT[1] }]
    });
    tableView(cardEl, ["Recipient", "Total", "Items"],
      DATA.givingRecipients.map(d => [d.name, d.total, d.items]), ["s", "$", "#"]);
  }

  /* The team */
  {
    const { box, cardEl } = card(app, "The in-house team",
      DATA.lobbyists.length + " registered in-house lobbyists across the window; no covered federal positions listed on the filings.", null);
    hbars(box, {
      items: DATA.lobbyists.map(d => ({ label: d.name, value: d.filings, note: d.years })),
      fmt: "#", labelW: 260, valueName: "quarterly filings appearing on", rowH: 26
    });
    tableView(cardEl, ["Lobbyist", "Filings", "Active years"],
      DATA.lobbyists.map(d => [d.name, d.filings, d.years]), ["s", "#", "s"]);
  }

  /* Caveats */
  {
    const c = div("card", app);
    const h = document.createElement("h2"); h.textContent = "How to read this (caveats that matter)"; c.appendChild(h);
    const ul = document.createElement("ul"); ul.className = "caveats"; c.appendChild(ul);
    DATA.caveats.forEach(t => { const li = document.createElement("li"); li.textContent = t; ul.appendChild(li); });
  }
})();
