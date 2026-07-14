(function () {
  const app = document.getElementById("app");
  const QI = DATA.queryInfo || {};
  moreOptions(statTiles(app, DATA.kpis), QI.kpis);

  /* shared underlying-records panel (same pattern as the crypto dashboard) */
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
  const LDA_F = u => "https://lda.senate.gov/filings/public/filing/" + u + "/print/";
  const regDisp = (player, reg) =>
    reg && player && reg.toUpperCase() === player.toUpperCase() ? "self-filed" : reg;
  const kwDisp = k => k ? " · matched: “" + k + "”" : "";
  const CLS_NAME = ["Pardon seeker (individual as client)", "Seeker vehicle (org; engagement seeks a pardon)",
                    "Clemency-policy advocacy org", "Unclear"];
  const CLS_SLOT = [0, 1, 2, 4];

  /* Player map */
  {
    const { box, cardEl } = card(app, "The player map — who lobbies on pardons and clemency",
      "All " + DATA.players.length + " client-side players with pardon/clemency-tagged senate filings 2022–2026Q1, sized by tagged filing count. Color = hand-triaged client class: individuals buying pardon engagements, organizational vehicles for a named beneficiary, and policy advocacy organizations. Click a bubble to list its tagged filings.",
      "Two different populations share this vocabulary: a paid pardon-seeking MARKET (individuals and vehicles hiring firms — 'Granting of Pardon', 'Executive relief') and clemency-POLICY advocacy (Due Process Institute, ACLU, Aleph Institute, marijuana-pardon pushes, pardon-power constitutional amendments). The map keeps both; the class column separates them. Full list with class notes: data/pardons_players.csv.");
    moreOptions(cardEl, QI.players);
    const lg = legend(cardEl, CLS_NAME.map((n, i) => ({ name: n, color: SLOT[CLS_SLOT[i]] })));
    cardEl.insertBefore(lg, box);
    const filingsPanel = div("filings-panel", null);
    bubblePack(box, {
      items: DATA.players.map(p => ({
        label: p.name, short: p.short, r0: p.filings,
        slot: CLS_SLOT[p.cls], extra: p
      })),
      height: 450, fmtSize: "#",
      ttRows: d => [
        { color: SLOT[d.slot], value: CLS_NAME[d.extra.cls], name: "class (hand-triaged 2026-07-10)" },
        { color: null, value: fmtNum(d.extra.filings), name: "pardon/clemency-tagged senate filings" },
        { color: null, value: fmtMoney(d.extra.spend), name: "total lobbying spend (ALL issues — not pardon dollars)" },
        { color: null, value: "click", name: "list this player's tagged filings" }
      ],
      onClick: d => showFilings(d.extra)
    });
    cardEl.insertBefore(filingsPanel, box.nextSibling);
    filingsPanel.textContent = "Click a bubble to list that player's pardon/clemency-tagged filings here — each links to the raw record on lda.senate.gov.";
    function showFilings(p) {
      const rows = (DATA.playerFilings && DATA.playerFilings[p.name]) || [];
      filingsPanel.textContent = "";
      const h = document.createElement("strong");
      h.textContent = p.name + " — " + fmtNum(p.filings) + " tagged senate filings";
      filingsPanel.appendChild(h);
      const scroll = div("filings-scroll", filingsPanel);
      const groups = [
        ["LD-2 quarterly activity reports", rows.filter(r => !r[4])],
        ["LD-1 registrations", rows.filter(r => r[4])]
      ];
      for (const [gname, grows] of groups) {
        if (!grows.length) continue;
        div("filings-group", scroll, gname + " (" + fmtNum(grows.length) + ")");
        const ul = document.createElement("ul");
        ul.className = "filings-list";
        for (const [uuid, label, reg, amt, _isReg, kws] of grows) {
          const li = document.createElement("li");
          const a = document.createElement("a");
          a.href = LDA_F(uuid); a.target = "_blank"; a.rel = "noopener";
          a.textContent = label;
          li.appendChild(a);
          li.appendChild(document.createTextNode(
            " · " + regDisp(p.name, reg) + (amt != null ? " · " + fmtMoney(amt) : "") + kwDisp(kws)));
          ul.appendChild(li);
        }
        scroll.appendChild(ul);
      }
      div("note", filingsPanel,
        "Raw records on lda.senate.gov (needs internet); Ctrl-F the matched phrase on the linked page to see the tagged language in context. Same list offline: data/pardons_player_filings.csv.");
    }
    tableView(cardEl, ["Player", "Class", "Tagged filings", "Years", "Total spend (all issues)", "Class note"],
      DATA.players.map(p => [p.name, CLS_NAME[p.cls], p.filings, p.y0 + "–" + p.y1, p.spend, p.note]),
      ["s", "s", "#", "s", "$", "s"]);
  }

  /* The paid pardon-seeker market */
  {
    const { box, cardEl } = card(app, "The paid pardon-seeker market — engagements and what they billed",
      "Every seeker/vehicle engagement (client × lobbying firm pair with pardon/clemency-tagged filings), ranked by reported billings in the tagged quarters. Color = whether the engagement has a DECLARED termination filing. Click a bar for the filings and the engagement's own declared language.",
      "Dollars are the engagement's full reported billing for the quarters where the pardon/clemency language appears — filing-level disclosure cannot split dollars by issue (Binance's engagements also cover digital-asset lobbying). Termination is declared only (senate filing_type termination family), never inferred from silence; a termination filing marks the engagement closing — it does not say whether the ask landed. Missing bars = engagements whose tagged quarterlies report no income (self-reported data).");
    moreOptions(cardEl, QI.engagements);
    const lg = legend(cardEl, [
      { name: "Active (no termination filed through 2026-Q1)", color: SLOT[0] },
      { name: "Declared terminated", color: SLOT[3] }
    ]);
    cardEl.insertBefore(lg, box);
    const withTotal = DATA.engagements.filter(e => e.total != null);
    const ePanel = recPanel(cardEl, box,
      "Click an engagement bar to see its tagged filings and the exact language the filing declares.");
    hbars(box, {
      items: withTotal.map(e => ({
        label: e.player + "  ·  " + e.reg,
        value: e.total,
        color: e.term ? SLOT[3] : SLOT[0],
        note: (e.term ? "terminated " + (e.termQ || "") : "active") + " · " + e.q0 + "→" + e.q1,
        extra: e
      })),
      fmt: "$", labelW: 420, rowH: 27, valueName: "reported billings, tagged quarters",
      onClick: d => showEng(d.extra)
    });
    function showEng(e) {
      const rows = ((DATA.playerFilings && DATA.playerFilings[e.player]) || [])
        .filter(r => (r[2] || "").toUpperCase() === e.reg.toUpperCase());
      ePanel.show(e.player + " × " + e.reg +
        (e.total != null ? " — " + fmtMoney(e.total) : "") +
        (e.term ? " · TERMINATED " + (e.termQ || "") : " · active"),
        "Raw records on lda.senate.gov. Full engagement table incl. declared text: data/pardons_engagements.csv.",
        [["Declared in the filing free-text", [{ text: "“" + (e.text || "(no tagged text sample)") + "”" }]],
         ["Tagged filings (" + rows.length + ")", rows.map(r => ({
           href: LDA_F(r[0]), text: r[1],
           tail: " · " + regDisp(e.player, r[2]) + (r[3] != null ? " · " + fmtMoney(r[3]) : "") + kwDisp(r[5]) }))]]);
    }
    tableView(cardEl, ["Client", "Firm", "Class", "First→last tagged qtr", "Tagged qtrs", "Reported $ (tagged qtrs)", "Terminated", "Termination qtr", "Declared text (sample)"],
      DATA.engagements.map(e => [e.player, e.reg, e.cls, e.q0 + " → " + e.q1, e.nq, e.total, e.term ? "yes" : "no", e.termQ, e.text]),
      ["s", "s", "s", "s", "#", "$", "s", "s", "s"]);
  }

  /* Trend */
  {
    const { box, cardEl } = card(app, "A niche that doubled after the 2024 election",
      "Pardon/clemency-tagged senate filings and distinct clients per quarter (amendment-deduped, registrations excluded). Click a quarter to list exactly the filings it counts.",
      "Steady ~5–8 filings a quarter through 2022–2024Q3 — mostly the advocacy orgs — then 22 in 2024-Q4 (post-election: end-of-term clemency pushes and the first waves of the seeker market) and a sustained 13–18/quarter through 2025–2026Q1, when nearly all seeker engagements begin.");
    moreOptions(cardEl, QI.trend);
    const lg = legend(cardEl, [{ name: "Tagged filings", color: SLOT[0] }, { name: "Distinct clients", color: SLOT[1] }], "line");
    cardEl.insertBefore(lg, box);
    const tPanel = recPanel(cardEl, box,
      "Click a quarter on the chart to list the deduped filings behind it — the list reconciles with the plotted number.");
    linePanel(box, {
      x: DATA.trend.q, fmt: "#",
      series: [
        { name: "Tagged filings", values: DATA.trend.filings },
        { name: "Distinct clients", values: DATA.trend.clients }
      ],
      onClick: (i, q) => {
        const rows = (DATA.trendFilings && DATA.trendFilings[q]) || [];
        tPanel.show(q + " — " + rows.length + " deduped pardon/clemency-tagged filings",
          "Same dedup semantics as the chart (latest amendment per registrant × client × quarter; registrations excluded). Offline: data/pardons_trend_filings.csv.",
          [["", rows.map(r => ({ href: LDA_F(r[0]), text: r[1],
            tail: " · " + regDisp(r[1], r[2]) + (r[3] != null ? " · " + fmtMoney(r[3]) : "") + kwDisp(r[4]) }))]]);
      }
    });
    tableView(cardEl, ["Quarter", "Tagged filings", "Distinct clients"],
      DATA.trend.q.map((q, i) => [q, DATA.trend.filings[i], DATA.trend.clients[i]]), ["s", "#", "#"]);
  }

  /* Issue-code scatter */
  {
    const { box, cardEl } = card(app, "There is no 'pardons' issue code — where the text actually files",
      "Issue codes the registrants filed their pardon/clemency-tagged free-text under (senate + house text blocks).",
      "The ALI form has no clemency code, so the field scatters: less than half sits under Law Enforcement (LAW); the rest hides in Government Issues, Civil Rights, and a 30-code tail — the same 'hidden under other codes' problem the crypto map demonstrated, at boutique scale. Individuals' engagements are usually coded GOV or LAW with a one-line description.");
    moreOptions(cardEl, QI.scatter);
    hbars(box, {
      items: DATA.scatter.map(d => ({
        label: d.code + (d.name ? " — " + d.name : ""), value: d.docs,
        note: d.pct + "% of tagged text blocks"
      })),
      fmt: "#", labelW: 330, valueName: "tagged text blocks"
    });
    tableView(cardEl, ["Issue code", "Tagged text blocks", "% of tagged"],
      DATA.scatter.map(d => [d.code + (d.name ? " — " + d.name : ""), d.docs, d.pct]), ["s", "#", "%"]);
  }

  /* Vocabulary */
  {
    const { box, cardEl } = card(app, "Which words carried the signal",
      "Distinct filings matched by each of the 8 curated lexicon phrases (whole-word, case-insensitive; industry_lexicon.json v1.1 facet PARDONS).",
      "'Executive relief' is the market's own euphemism: in this corpus the whole phrase resolves to exactly three clients — Binance Holdings, Changpeng Zhao, and Fred Daibes. Verb forms (pardoned/pardoning) barely exist in filings but dominate press releases — the two sides speak differently.");
    moreOptions(cardEl, QI.keywords);
    hbars(box, {
      items: DATA.keywords.map(d => ({ label: d.kw, value: d.filings })),
      fmt: "#", labelW: 240, valueName: "distinct filings matched"
    });
  }

  /* Registrant firms */
  {
    const { box, cardEl } = card(app, "The firms that sell this service",
      "Outside lobbying firms on pardon/clemency-tagged filings (self-filing advocacy orgs excluded), ranked by tagged filings.",
      "J M Burkman & Associates alone collected ~$1.56M from two pardon-seekers (Hatch, Schwartz — ledger L034). The Vogel Group runs a small stable of clemency clients (Tierney, Patel, Magma Power, Healthicity); Baker & Hostetler and Checkmate carry the Binance/Zhao 'executive relief' work. Reported amounts are ranking signals summed over tagged filings.");
    moreOptions(cardEl, QI.registrants);
    hbars(box, {
      items: DATA.registrants.slice(0, 15).map(d => ({
        label: d.name, value: d.filings,
        note: (d.amt != null ? fmtMoney(d.amt) + " reported · " : "") + d.clients + " client(s)"
      })),
      fmt: "#", labelW: 340, valueName: "tagged filings"
    });
    tableView(cardEl, ["Firm", "Tagged filings", "Clients", "Reported amount (ranking signal)"],
      DATA.registrants.map(d => [d.name, d.filings, d.clients, d.amt]), ["s", "#", "#", "$"]);
  }

  /* Press coupling */
  {
    const { box, cardEl } = card(app, "Congress barely mentioned pardons — until 2025",
      "Share of ALL member press releases mentioning pardon/clemency vocabulary, by quarter. Click a quarter to list the releases.",
      "A near-zero baseline (0.02–0.3%) breaks at 2024-Q4 and spikes ~10× at 2025-Q1 (156 releases — the Jan-6 mass pardons and the preemptive-pardon fight) and again at 2026-Q1 (132). The say-side runs on the political calendar; the filing-side market it tracks is the quiet, paid one above.");
    moreOptions(cardEl, QI.press);
    const pPanel = recPanel(cardEl, box,
      "Click a quarter to list its matching member press releases (with links).");
    linePanel(box, {
      x: DATA.press.q, fmt: "%",
      series: [{ name: "Pardon/clemency share of member releases", values: DATA.press.share, color: SLOT[5] }],
      height: 210,
      onClick: (i, q) => {
        const rows = (DATA.pressReleases && DATA.pressReleases[q]) || [];
        pPanel.show(q + " — " + rows.length + " matching member releases",
          "Whole-word regex over title + text (incl. verb forms the filings never use). Offline with citation keys: data/pardons_press_releases.csv.",
          [["", rows.map(r => ({ href: r[5] || undefined,
            text: r[0] + " · " + (r[1] || "(member unknown)") + (r[2] ? " (" + r[2] + (r[3] ? "-" + r[3] : "") + ")" : ""),
            tail: " — " + (r[4] || "") }))]]);
      }
    });
    tableView(cardEl, ["Quarter", "Matching releases", "All releases", "Share %"],
      DATA.press.q.map((q, i) => [q, DATA.press.n[i], DATA.press.all[i], DATA.press.share[i]]),
      ["s", "#", "#", "%"]);
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
