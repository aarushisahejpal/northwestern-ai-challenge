(function () {
  const app = document.getElementById("app");
  const QI = DATA.queryInfo || {};
  moreOptions(statTiles(app, DATA.kpis), QI.kpis);
  const LDA_F = u => "https://lda.senate.gov/filings/public/filing/" + u + "/print/";
  const LDA_C = u => "https://lda.senate.gov/filings/public/contribution/" + u + "/print/";

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

  /* Spend + press coupling: two panels, shared x (never a dual axis) */
  {
    const { box, cardEl } = card(app, "AIPAC's lobbying budget is a slow ratchet; the news cycle is not",
      "Top panel: AIPAC's reported quarterly lobbying amount (in-house LD-2 filings) — click a bar for that filing. Bottom panel: share of ALL congressional member press releases mentioning Israel/Gaza-related terms — click a point for that quarter's releases. Same quarters, same x-axis.",
      "After October 7, 2023 the press share jumps 2.6% → 20.3% in one quarter (~8×). AIPAC's lobbying spend moves +6.6% that quarter and just keeps its steady ~9%/yr climb — $690K (2022-Q1) to a $974K peak (2025-Q4). Read: lobbying budgets are planned annual infrastructure, not news-reactive spending.");
    moreOptions(cardEl, QI.coupling);
    const sub1 = div("sub", null); sub1.textContent = "AIPAC reported lobbying amount per quarter";
    box.appendChild(sub1);
    const b1 = div(null, box);
    const cPanel = recPanel(cardEl, box,
      "Click a bar on the amount chart for that quarter's own filing, or a point on the press line for the matching releases.");
    columns(b1, {
      x: DATA.coupling.q, fmt: "$", height: 220,
      series: [{ name: "AIPAC reported quarterly amount", values: DATA.coupling.amount, color: SLOT[0] }],
      onClick: (i, q) => {
        const uuid = DATA.quarterFiling && DATA.quarterFiling[q];
        cPanel.show(q + " — AIPAC's own quarterly filing", "",
          [["", uuid ? [{ href: LDA_F(uuid), text: "LD-2 quarterly report, " + q,
              tail: " · " + fmtMoney(DATA.coupling.amount[i]) }] : []]]);
      }
    });
    const sub2 = div("sub", null); sub2.textContent = "Israel-topic share of all member press releases (%)";
    box.appendChild(sub2);
    const b2 = div(null, box);
    linePanel(b2, {
      x: DATA.coupling.q, fmt: "%", height: 200,
      series: [{ name: "Israel-topic share of member releases", values: DATA.coupling.share, color: SLOT[5] }],
      onClick: (i, q) => {
        const rows = (DATA.pressReleases && DATA.pressReleases[q]) || [];
        cPanel.show(q + " — " + fmtNum(rows.length) + " matching member releases",
          "Whole-word regex over title + text. Offline: data/aipac_press_releases.csv.",
          [["", rows.map(r => ({ href: r[5] || undefined,
              text: r[0] + " · " + (r[1] || "(member unknown)") + (r[2] ? " (" + r[2] + (r[3] ? "-" + r[3] : "") + ")" : ""),
              tail: " — " + (r[4] || "") }))]]);
      }
    });
    tableView(cardEl, ["Quarter", "AIPAC amount", "Israel-topic releases", "All releases", "Share %"],
      DATA.coupling.q.map((q, i) => [q, DATA.coupling.amount[i], DATA.coupling.rel[i], DATA.coupling.all[i], DATA.coupling.share[i]]),
      ["s", "$", "#", "#", "%"]);
  }

  /* Who is lobbied */
  {
    const { box, cardEl } = card(app, "Who AIPAC lobbies",
      "Government entities named on AIPAC's quarterly filings, 2022–2026Q1 (activity-level mentions). Click a bar to list the filings naming that entity.",
      "Beyond both chambers: DOD, DHS, State, Treasury, the NSC — and the Energy Department (civil-nuclear and Iran-sanctions issues ride with the security portfolio).");
    moreOptions(cardEl, QI.govEntities);
    const gPanel = recPanel(cardEl, box,
      "Click a bar to list AIPAC's filings naming that government entity.");
    hbars(box, {
      items: DATA.govEntities.map(d => ({ label: d.name, value: d.n, extra: d })),
      fmt: "#", labelW: 330, valueName: "mentions on filings",
      onClick: d => {
        const rows = (DATA.govEntityFilings && DATA.govEntityFilings[d.extra.name]) || [];
        gPanel.show(d.extra.name + " — " + fmtNum(rows.length) + " filings",
          "Offline: data/aipac_gov_entity_filings.csv.",
          [["", rows.map(r => ({ href: LDA_F(r[0]), text: r[1],
              tail: r[2] != null ? " · " + fmtMoney(r[2]) : "" }))]]);
      }
    });
    tableView(cardEl, ["Entity", "Mentions"], DATA.govEntities.map(d => [d.name, d.n]), ["s", "#"]);
  }

  /* What they talk about: issue mix + bills note — table-forward card */
  {
    const { box, cardEl } = card(app, "What the filings talk about",
      "Every AIPAC activity is coded BUD (appropriations), FOR (foreign relations), or DEF (defense) — plus a handful of AGR/TRD/HOM entries. The activity text names specific bills: " + DATA.nBills + " distinct bills across 17 quarters. Click a bar to list the filings naming that bill.",
      "Recurring subjects: security assistance appropriations to Israel, Iran sanctions bills, U.S.-Israel defense-partnership acts, antisemitism-related resolutions. Full activity text (their own words, citable) is in data/aipac_activities.csv.");
    moreOptions(cardEl, QI.bills);
    const bPanel = recPanel(cardEl, box,
      "Click a bar to list AIPAC's filings naming that bill.");
    hbars(box, {
      items: DATA.topBills.map(d => ({ label: d.bill + (d.hint ? " — " + d.hint : ""), value: d.n,
        note: "quarterly filings naming it", extra: d })),
      fmt: "#", labelW: 380, valueName: "AIPAC filings naming the bill",
      onClick: d => {
        const bill = d.extra.bill;
        const rows = (DATA.billFilings && DATA.billFilings[bill]) || [];
        bPanel.show(bill + (d.extra.hint ? " — " + d.extra.hint : "") + " — " + fmtNum(rows.length) + " filings",
          "Offline: data/aipac_bill_filings.csv.",
          [["", rows.map(r => ({ href: LDA_F(r[0]), text: r[1],
              tail: r[2] != null ? " · " + fmtMoney(r[2]) : "" }))]]);
      }
    });
    tableView(cardEl, ["Bill", "AIPAC filings", "First year", "Last year"],
      DATA.billsTable.map(d => [d.bill, d.n, d.y0, d.y1]), ["s", "#", "s", "s"]);
  }

  /* Co-lobbyists */
  {
    const { box, cardEl } = card(app, "Who else lobbies AIPAC's bills",
      "Organizations lobbying the same distinctive bills as AIPAC (bills with ≤200 lobbying engagements corpus-wide, so mega-bills like the NDAA don't drown the signal). Ranked by number of shared bills. Click a bar to list that client's filings on the shared bills.",
      "Both camps show up: allied groups (FDD Action, Hadassah, Republican Jewish Coalition, Christians United for Israel) AND opposing ones (J Street, Friends Committee on National Legislation, ACLU, MoveOn, Amnesty). Sharing a bill means lobbying ON it, not necessarily the same side — the overlap maps the battlefield, not the alliance.");
    moreOptions(cardEl, QI.coLobby);
    const clPanel = recPanel(cardEl, box,
      "Click a bar to list that client's filings on the bills it shares with AIPAC.");
    hbars(box, {
      items: DATA.coLobby.map(d => ({ label: d.name, value: d.bills, note: fmtNum(d.filings) + " filings on those bills", extra: d })),
      fmt: "#", labelW: 360, valueName: "shared distinctive bills",
      onClick: d => {
        const rows = (DATA.coLobbyFilings && DATA.coLobbyFilings[d.extra.raw]) || [];
        clPanel.show(d.extra.name + " — " + fmtNum(rows.length) + " filings on shared bills",
          "Offline: data/aipac_colobby_filings.csv.",
          [["", rows.map(r => ({ href: LDA_F(r[0]), text: r[1] + " — " + r[2],
              tail: " · " + r[3] + (r[4] != null ? " · " + fmtMoney(r[4]) : "") }))]]);
      }
    });
    tableView(cardEl, ["Organization", "Shared distinctive bills", "Filings on those bills"],
      DATA.coLobby.map(d => [d.name, d.bills, d.filings]), ["s", "#", "#"]);
  }

  /* Israel-policy field */
  {
    const { box, cardEl } = card(app, "The wider Israel-policy lobbying field",
      "Clients whose senate filing free-text mentions Israel/Gaza-related terms, ranked by matching filings (exploratory whole-word scan, ≥2 filings). Total lobbying spend (all issues) in the tooltip. Click a bar to list that player's filings.",
      "AIPAC sits in a crowded field: ADL, Republican Jewish Coalition, J Street, FDD Action, CUFI, ZOA, Jewish Federations, Hadassah, AJC — plus non-obvious entries like Chevron (Eastern-Mediterranean gas leases) and terror-victim litigation estates. Exploratory scan, not the curated lexicon pipeline; promote to a lexicon facet before citing in a finding.");
    moreOptions(cardEl, QI.israelPlayers);
    const ipPanel = recPanel(cardEl, box,
      "Click a bar to list that player's Israel-topic filings.");
    hbars(box, {
      items: DATA.israelPlayers.map(d => ({ label: d.name, value: d.n, note: "total all-issue spend " + fmtMoney(d.spend), extra: d })),
      fmt: "#", labelW: 360, valueName: "filings mentioning Israel terms",
      onClick: d => {
        const rows = (DATA.israelPlayerFilings && DATA.israelPlayerFilings[d.extra.raw]) || [];
        ipPanel.show(d.extra.name + " — " + fmtNum(rows.length) + " Israel-topic filings",
          "Offline: data/aipac_israel_player_filings.csv.",
          [["", rows.map(r => ({ href: LDA_F(r[0]), text: r[1],
              tail: " · " + r[2] + (r[3] != null ? " · " + fmtMoney(r[3]) : "") }))]]);
      }
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
      "Top recipients of AIPAC's disclosed LD-203 contributions, 2022–2025. Total: " + fmtMoney(DATA.givingTotal) + " (amendment-deduplicated), 100% FECA contributions, clear election-year cadence. Member-matched giving splits " + psLine + " — bipartisan, tilted Republican ~63:37 by dollars. Click any bar for the underlying items.",
      "Party/state brackets from the corpus members table (retired members hand-mapped, flagged in the CSV); committees, PACs and joint-fundraising entries carry no bracket. NOT shown here (different legal regime): AIPAC-affiliated Super-PAC spending (e.g. United Democracy Project) lives in FEC data, outside LD-203 — the same disclosure gap as crypto's Fairshake. LD-203 reports are registrant-filed; recipient strings lightly normalized.");
    moreOptions(cardEl, QI.giving);
    const givPanel = recPanel(cardEl, box,
      "Click a bar below for the amendment-deduped LD-203 items behind it — each links to the filed report on lda.senate.gov.");
    const showItems = (rows, title) => {
      givPanel.show(title, "Offline: data/aipac_giving_items.csv.",
        [["", rows.map(r => ({ href: LDA_C(r[0]), text: r[1], tail: " · " + r[2] + " · " + fmtMoney(r[3]) + " · " + r[4] }))]]);
    };
    hbars(box, {
      items: DATA.givingRecipients.map(d => ({ label: d.name, value: d.total, note: fmtNum(d.items) + " reported items", extra: d })),
      fmt: "$", labelW: 300, valueName: "disclosed LD-203 contributions",
      onClick: d => {
        const rows = (DATA.givingRecipientItems && DATA.givingRecipientItems[d.extra.name]) || [];
        showItems(rows, d.extra.name + " — " + fmtMoney(d.extra.total) + " disclosed giving");
      }
    });
    const sub2 = div("sub", null); sub2.textContent = "By year — election-year cadence";
    cardEl.insertBefore(sub2, cardEl.querySelector(".foot"));
    const b2 = div(null, null); cardEl.insertBefore(b2, cardEl.querySelector(".foot"));
    columns(b2, {
      x: DATA.givingByYear.map(d => String(d.y)), fmt: "$", height: 170,
      series: [{ name: "Disclosed LD-203 giving", values: DATA.givingByYear.map(d => d.total), color: SLOT[1] }],
      onClick: (i, y) => {
        const rows = (DATA.givingYearItems && DATA.givingYearItems[y]) || [];
        showItems(rows, y + " — " + fmtMoney(DATA.givingByYear[i].total) + " disclosed giving");
      }
    });
    tableView(cardEl, ["Recipient", "Total", "Items"],
      DATA.givingRecipients.map(d => [d.name, d.total, d.items]), ["s", "$", "#"]);
  }

  /* The team */
  {
    const { box, cardEl } = card(app, "The in-house team",
      DATA.lobbyists.length + " registered in-house lobbyists across the window; no covered federal positions listed on the filings. Click a bar to list that lobbyist's filings.", null);
    moreOptions(cardEl, QI.lobbyists);
    const lPanel = recPanel(cardEl, box,
      "Click a bar to list that lobbyist's filings.");
    hbars(box, {
      items: DATA.lobbyists.map(d => ({ label: d.name, value: d.filings, note: d.years, extra: d })),
      fmt: "#", labelW: 260, valueName: "quarterly filings appearing on", rowH: 26,
      onClick: d => {
        const rows = (DATA.lobbyistFilings && DATA.lobbyistFilings[d.extra.name]) || [];
        lPanel.show(d.extra.name + " — " + fmtNum(rows.length) + " filings",
          "Offline: data/aipac_lobbyist_filings.csv.",
          [["", rows.map(r => ({ href: LDA_F(r[0]), text: r[1] }))]]);
      }
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

  findingsCard(app, DATA.findings);
})();
