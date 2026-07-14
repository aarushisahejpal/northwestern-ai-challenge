(function () {
  const app = document.getElementById("app");
  const QI = DATA.queryInfo || {};
  moreOptions(statTiles(app, DATA.kpis), QI.kpis);
  const LDA_F = u => "https://lda.senate.gov/filings/public/filing/" + u + "/print/";

  /* shared underlying-records panel (same pattern as the crypto/pardons dashboards) */
  function recPanel(cardEl, box, hint) {
    const panel = div("filings-panel", null);
    cardEl.insertBefore(panel, box.nextSibling);
    panel.textContent = hint;
    return {
      show(title, note, groups) { // groups = [[label, items]], item = {href?, text, tail?}
        panel.textContent = "";
        const h = document.createElement("strong");
        h.textContent = title; panel.appendChild(h);
        const scroll = div("filings-scroll", panel);
        for (const [gname, items] of groups) {
          if (!items.length) continue;
          if (gname) div("filings-group", scroll, gname);
          const ul = document.createElement("ul");
          ul.className = "filings-list";
          for (const it of items) {
            const li = document.createElement("li");
            if (it.href) {
              const a = document.createElement("a");
              a.href = it.href; a.target = "_blank"; a.rel = "noopener";
              a.textContent = it.text;
              li.appendChild(a);
            } else {
              li.appendChild(document.createTextNode(it.text));
            }
            if (it.tail) li.appendChild(document.createTextNode(it.tail));
            ul.appendChild(li);
          }
          scroll.appendChild(ul);
        }
        if (note) div("note", panel, note);
      }
    };
  }
  const capNote = (shown, total, csv) => total > shown
    ? "Showing the top " + fmtNum(shown) + " by reported amount of " + fmtNum(total) + " total — full list: " + csv + ". "
    : "";

  /* Player map */
  {
    const { box, cardEl } = card(app, "The player map — who lobbies on healthcare",
      "Top " + DATA.players.length + " clients with health-coded filings, sized by total federal lobbying spend 2022–2026Q1 (all issues, canonical). Color = how much of the organization's lobbying activity is health-coded. Click a bubble to list its filings.",
      "The biggest bubbles split into two species: health pure-plays (PhRMA, American Hospital Association, AHIP, AMA) whose activity is mostly health-coded, and diversified giants (U.S. Chamber, Amazon, AARP) for whom health is one desk among many. Hover for each player's health-activity share.");
    moreOptions(cardEl, QI.players);
    const lg = legend(cardEl, [
      { name: "Health-focused (≥50% of activities)", color: SLOT[0] },
      { name: "Mixed (20–50%)", color: SLOT[1] },
      { name: "Health is a side desk (<20%)", color: SLOT[2] }
    ]);
    cardEl.insertBefore(lg, box);
    const pPanel = recPanel(cardEl, box,
      "Click a bubble to list that player's health-coded filings here — each links to the raw record on lda.senate.gov.");
    bubblePack(box, {
      items: DATA.players.map(p => ({
        label: p.name, short: p.short, r0: p.spend || 200000, slot: p.cls, extra: p
      })),
      height: 470, fmtSize: "$",
      ttRows: d => [
        { color: SLOT[d.slot], value: fmtMoney(d.extra.spend), name: "total lobbying spend (all issues)" },
        { color: null, value: d.extra.share + "%", name: "share of activities that are health-coded" },
        { color: null, value: fmtNum(d.extra.filings), name: "health-coded senate filings" },
        { color: null, value: "click", name: "list this player's filings" }
      ],
      onClick: d => {
        const p = d.extra;
        const rows = (DATA.playerFilings && DATA.playerFilings[p.name]) || [];
        const total = (DATA.playerFilingsTotal && DATA.playerFilingsTotal[p.name]) || rows.length;
        pPanel.show(p.name + " — " + fmtNum(total) + " health-coded filings",
          capNote(rows.length, total, "data/hc_player_filings.csv") + "Raw records on lda.senate.gov.",
          [["", rows.map(r => ({ href: LDA_F(r[0]), text: r[1],
              tail: " · " + r[2] + (r[3] != null ? " · " + fmtMoney(r[3]) : "") + (r[4] ? " · " + r[4] : "") }))]]);
      }
    });
    tableView(cardEl, ["Player", "Health filings", "Health share of activities %", "Total spend (all issues)"],
      DATA.players.map(p => [p.name, p.filings, p.share, p.spend]), ["s", "#", "%", "$"]);
  }

  /* Trend */
  {
    const { box, cardEl } = card(app, "A massive, stable machine — with a 2025 uptick",
      "Health-coded senate filings and distinct client organizations per quarter (amendment-deduped). Click a quarter to list its filings.",
      "Healthcare lobbying is an installed base: ~4,000 filings and ~2,950 clients every quarter for three straight years, then a visible 2025 rise (+9%) during the reconciliation Medicaid fight. Compare crypto's +60% breakout: healthcare doesn't surge because it never left.");
    moreOptions(cardEl, QI.trend);
    const lg = legend(cardEl, [{ name: "Health-coded filings", color: SLOT[0] }, { name: "Distinct clients", color: SLOT[1] }], "line");
    cardEl.insertBefore(lg, box);
    const tPanel = recPanel(cardEl, box,
      "Click a quarter to list the deduped filings behind it here — the list reconciles with the plotted number.");
    linePanel(box, {
      x: DATA.trend.q, fmt: "#",
      series: [
        { name: "Health-coded filings", values: DATA.trend.filings },
        { name: "Distinct clients", values: DATA.trend.clients }
      ],
      onClick: (i, q) => {
        const rows = (DATA.trendFilings && DATA.trendFilings[q]) || [];
        const total = (DATA.trendFilingsTotal && DATA.trendFilingsTotal[q]) || rows.length;
        tPanel.show(q + " — " + fmtNum(total) + " deduped health-coded filings",
          capNote(rows.length, total, "data/hc_trend_filings.csv") + "Offline: data/hc_trend_filings.csv.",
          [["", rows.map(r => ({ href: LDA_F(r[0]), text: r[1],
              tail: " · " + r[2] + (r[3] != null ? " · " + fmtMoney(r[3]) : "") + (r[4] ? " · " + r[4] : "") }))]]);
      }
    });
    tableView(cardEl, ["Quarter", "Filings", "Clients", "Canonical spend of active clients (all-issue)"],
      DATA.trend.q.map((q, i) => [q, DATA.trend.filings[i], DATA.trend.clients[i], DATA.trend.spend[i]]),
      ["s", "#", "#", "$"]);
  }

  /* Issue mix */
  {
    const { box, cardEl } = card(app, "What kind of healthcare lobbying",
      "Health-coded filings per quarter by issue code (a filing can carry several codes). Click a quarter to list the filings behind each code.",
      "General health issues (HCR) dominate; Medicare/Medicaid (MMM) is the second pillar; pharmacy (PHA) and medical research (MED) are steady specialist lanes.");
    moreOptions(cardEl, QI.codeTrend);
    const lg = legend(cardEl, [
      { name: "HCR — health issues", color: SLOT[0] },
      { name: "MMM — Medicare/Medicaid", color: SLOT[1] },
      { name: "PHA — pharmacy", color: SLOT[2] },
      { name: "MED — medical research", color: SLOT[4] }
    ], "line");
    cardEl.insertBefore(lg, box);
    const cPanel = recPanel(cardEl, box,
      "Click a quarter to list the filings behind each issue code that quarter.");
    const CODE_NM = { HCR: "health issues", MMM: "Medicare/Medicaid", PHA: "pharmacy", MED: "medical research" };
    linePanel(box, {
      x: DATA.codeTrend.q, fmt: "#",
      series: [
        { name: "HCR — health issues", values: DATA.codeTrend.HCR, color: SLOT[0] },
        { name: "MMM — Medicare/Medicaid", values: DATA.codeTrend.MMM, color: SLOT[1] },
        { name: "PHA — pharmacy", values: DATA.codeTrend.PHA, color: SLOT[2] },
        { name: "MED — medical research", values: DATA.codeTrend.MED, color: SLOT[4] }
      ],
      onClick: (i, q) => {
        const e = (DATA.codeTrendFilings && DATA.codeTrendFilings[q]) || { HCR: [], MMM: [], PHA: [], MED: [] };
        const groups = ["HCR", "MMM", "PHA", "MED"].map(code => {
          const rows = e[code] || [];
          const total = (DATA.codeTrendFilingsTotal && DATA.codeTrendFilingsTotal[q + "|" + code]) || rows.length;
          return [code + " — " + CODE_NM[code] + " (" + fmtNum(total) + (total > rows.length ? ", top " + rows.length + " shown" : "") + ")",
            rows.map(r => ({ href: LDA_F(r[0]), text: r[1], tail: " · " + r[2] + (r[3] != null ? " · " + fmtMoney(r[3]) : "") }))];
        });
        cPanel.show(q + " — health-coded filings by issue code",
          "Full lists: data/hc_code_trend_filings.csv.", groups);
      }
    });
    tableView(cardEl, ["Quarter", "HCR", "MMM", "PHA", "MED"],
      DATA.codeTrend.q.map((q, i) => [q, DATA.codeTrend.HCR[i], DATA.codeTrend.MMM[i], DATA.codeTrend.PHA[i], DATA.codeTrend.MED[i]]),
      ["s", "#", "#", "#", "#"]);
  }

  /* Press coupling */
  {
    const { box, cardEl } = card(app, "Congress talks healthcare constantly — and 2025 set records",
      "Share of all member press releases tagged to a health issue code, by quarter. Click a quarter to list the releases.",
      "Healthcare holds 14–22% of congressional messaging in a normal quarter — then climbs through 2025 to 28.8% in Q4 (reconciliation Medicaid cuts + ACA subsidy-cliff fight). Note the asymmetry with the money: press attention swings with the political calendar; the filing base barely moves. (Same divergence the ledger logged as L026.)");
    moreOptions(cardEl, QI.press);
    const prPanel = recPanel(cardEl, box,
      "Click a quarter to list its matching member press releases (with links).");
    linePanel(box, {
      x: DATA.press.q, fmt: "%",
      series: [{ name: "Health share of member press releases", values: DATA.press.share, color: SLOT[5] }],
      height: 210,
      onClick: (i, q) => {
        const rows = (DATA.pressReleases && DATA.pressReleases[q]) || [];
        const total = (DATA.pressReleasesTotal && DATA.pressReleasesTotal[q]) || rows.length;
        prPanel.show(q + " — " + fmtNum(total) + " matching member releases",
          capNote(rows.length, total, "data/hc_press_releases.csv") + "Offline: data/hc_press_releases.csv.",
          [["", rows.map(r => ({ href: r[5] || undefined,
              text: r[0] + " · " + (r[1] || "(member unknown)") + (r[2] ? " (" + r[2] + (r[3] ? "-" + r[3] : "") + ")" : ""),
              tail: " — " + (r[4] || "") }))]]);
      }
    });
    tableView(cardEl, ["Quarter", "Health-tagged releases", "All releases", "Share %"],
      DATA.press.q.map((q, i) => [q, DATA.press.n[i], DATA.press.all[i], DATA.press.share[i]]),
      ["s", "#", "#", "%"]);
  }

  /* Bills */
  {
    const { box, cardEl } = card(app, "The bills the industry crowds onto",
      "Bills most-named in health-coded filings, ranked by distinct clients lobbying them. Click a bar to list the filings naming that bill.",
      null);
    moreOptions(cardEl, QI.bills);
    const bPanel = recPanel(cardEl, box,
      "Click a bar to list the health-coded filings naming that bill.");
    hbars(box, {
      items: DATA.topBills.map(d => ({ label: d.bill + (d.hint ? " — " + d.hint : ""), value: d.clients,
        note: fmtNum(d.filings) + " filings", extra: d })),
      fmt: "#", labelW: 380, valueName: "distinct clients",
      onClick: d => {
        const bill = d.extra.bill;
        const rows = (DATA.billFilings && DATA.billFilings[bill]) || [];
        const total = (DATA.billFilingsTotal && DATA.billFilingsTotal[bill]) || rows.length;
        bPanel.show(bill + (d.extra.hint ? " — " + d.extra.hint : "") + " — " + fmtNum(total) + " health-coded filings",
          capNote(rows.length, total, "data/hc_bill_filings.csv") + "Offline: data/hc_bill_filings.csv.",
          [["", rows.map(r => ({ href: LDA_F(r[0]), text: r[1],
              tail: " · " + r[2] + (r[3] != null ? " · " + fmtMoney(r[3]) : "") }))]]);
      }
    });
    tableView(cardEl, ["Bill", "Distinct clients", "Filings"],
      DATA.topBills.map(d => [d.bill, d.clients, d.filings]), ["s", "#", "#"]);
  }

  /* Giving */
  {
    const { box, cardEl } = card(app, "Who healthcare gives money to (disclosed LD-203) — health-focused vs mixed givers",
      "Disclosed LD-203 giving by the top-150 health lobbying organizations: " + fmtMoney(DATA.givingTotal) + " total 2022–2025, split into HEALTH-FOCUSED givers (≥50% of their lobbying activity is health-coded: AHA, AMA, ADA, PhRMA…) vs MIXED/diversified givers (<50%: AARP, Altria, insurers with big non-health books…). Click any bar for the underlying LD-203 items.",
      "Organization-level attribution: the split shows WHO funds each recipient, not whether the motive was a health issue — a mixed org's giving is not health-specific. Party/state from the corpus members table; retired members hand-mapped and flagged. Raw variants in data/hc_ld203_recipients_split.csv. Election-year cadence: 2022 $28.3M · 2023 $23.8M · 2024 $32.4M · 2025 $23.3M.");
    moreOptions(cardEl, QI.giving);
    const lg = legend(cardEl, [
      { name: "Health-focused giver (≥50% health activities)", color: SLOT[0] },
      { name: "Mixed/diversified giver (<50%)", color: SLOT[2] }
    ]);
    cardEl.insertBefore(lg, box);
    const gPanel = recPanel(cardEl, box,
      "Click any bar below for the amendment-deduped LD-203 items behind it — each links to the filed report on lda.senate.gov.");
    div("sub", box, "Top giving organizations (color = giver type)");
    hbars(div(null, box), {
      items: DATA.givingOrgs.map(d => ({ label: d.name, value: d.total, color: d.focused ? SLOT[0] : SLOT[2], extra: d })),
      fmt: "$", labelW: 300, rowH: 27, valueName: "disclosed giving",
      onClick: d => {
        const org = d.extra;
        const rows = (DATA.givingOrgItems && DATA.givingOrgItems[org.raw]) || [];
        gPanel.show(org.name + " — " + fmtMoney(org.total) + " disclosed giving",
          "Amendment-deduped LD-203 items; sums reconcile with the bar. Offline: data/hc_giving_org_items.csv.",
          [["", rows.map(r => ({ href: "https://lda.senate.gov/filings/public/contribution/" + r[0] + "/print/",
              text: r[1], tail: " · " + r[2] + " · " + fmtMoney(r[3]) + " · " + r[4] }))]]);
      }
    });
    div("sub", box, "Top recipients overall — split by giver type");
    const showRecipItems = (d) => {
      const e = (DATA.givingRecipientItems && DATA.givingRecipientItems[d.label]) || { health_focused: [], mixed_diversified: [] };
      gPanel.show(d.label + " — " + fmtMoney((d.a || 0) + (d.b || 0)) + " disclosed giving",
        "Amendment-deduped LD-203 items; sums reconcile with the bars. Offline: data/hc_giving_recipient_items.csv.",
        [["From health-focused givers", e.health_focused.map(r => ({ href: "https://lda.senate.gov/filings/public/contribution/" + r[0] + "/print/",
            text: r[1], tail: " · " + r[2] + " · " + fmtMoney(r[3]) + " · " + r[4] }))],
         ["From mixed/diversified givers", e.mixed_diversified.map(r => ({ href: "https://lda.senate.gov/filings/public/contribution/" + r[0] + "/print/",
            text: r[1], tail: " · " + r[2] + " · " + fmtMoney(r[3]) + " · " + r[4] }))]]);
    };
    groupedHBars(div(null, box), {
      items: DATA.givingTop.map(d => ({ label: d.name, a: d.a, b: d.b })),
      aName: "from health-focused orgs", bName: "from mixed/diversified orgs",
      aColor: SLOT[0], bColor: SLOT[2], labelW: 330,
      onClick: d => showRecipItems(d)
    });
    div("sub", box, "Members of Congress — split by giver type");
    groupedHBars(div(null, box), {
      items: DATA.givingMembers.map(d => ({ label: d.name, a: d.a, b: d.b })),
      aName: "from health-focused orgs", bName: "from mixed/diversified orgs",
      aColor: SLOT[0], bColor: SLOT[2], labelW: 330,
      onClick: d => showRecipItems(d)
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

  findingsCard(app, DATA.findings);
})();
