/* facet_page.js — generic facet-lens dashboard for industry-review-packager.
   All card copy comes from DATA.copy (carried by the package spec); every widget
   renders only if its data is present. Widgets: KPI tiles, player bubble map,
   engagements (optional), quarterly trend, issue-code scatter, vocabulary,
   registrant firms, top spenders (optional), LD-203 giving (optional),
   press share, caveats. */
(function () {
  const app = document.getElementById("app");
  const QI = DATA.queryInfo || {};
  const C = DATA.copy || {};
  const W = (k) => C[k] || {};   // per-widget card copy from the spec
  moreOptions(statTiles(app, DATA.kpis), QI.kpis);

  function recPanel(cardEl, box, hint) {
    const panel = div("filings-panel", null);
    cardEl.insertBefore(panel, box.nextSibling);
    panel.textContent = hint;
    return {
      show(title, note, groups) {
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
  const CLS_NAME = DATA.classes;                       // null → single-class map
  const CLS_SLOT = DATA.classSlots || [0, 1, 2, 4];

  /* Player map */
  {
    const w = W("players");
    const { box, cardEl } = card(app, w.title || "The player map",
      (w.sub || "All {n} client-side players, sized by tagged filing count. Click a bubble to list its filings.")
        .replace("{n}", DATA.players.length),
      w.foot || "");
    moreOptions(cardEl, QI.players);
    if (CLS_NAME) {
      const lg = legend(cardEl, CLS_NAME.map((n, i) => ({ name: n, color: SLOT[CLS_SLOT[i]] })));
      cardEl.insertBefore(lg, box);
    }
    bubblePack(box, {
      items: DATA.players.map(p => ({
        label: p.name, short: p.short, r0: p.filings,
        slot: CLS_NAME ? CLS_SLOT[p.cls] : 0, extra: p
      })),
      height: 450, fmtSize: "#",
      ttRows: d => {
        const rows = [];
        if (CLS_NAME) rows.push({ color: SLOT[d.slot], value: CLS_NAME[d.extra.cls], name: "class (hand-triaged)" });
        rows.push({ color: null, value: fmtNum(d.extra.filings), name: "tagged senate filings" });
        rows.push({ color: null, value: fmtMoney(d.extra.spend), name: "total lobbying spend (ALL issues)" });
        rows.push({ color: null, value: "click", name: "list this player's tagged filings" });
        return rows;
      },
      onClick: d => showFilings(d.extra)
    });
    const filingsPanel = div("filings-panel", null);
    cardEl.insertBefore(filingsPanel, box.nextSibling);
    filingsPanel.textContent =
      "Click a bubble to list that player's tagged filings here — each links to the raw record on lda.senate.gov.";
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
        "Raw records on lda.senate.gov (needs internet); Ctrl-F the matched phrase on the linked page " +
        "to see the tagged language in context. Same list offline in the package's data/ CSVs.");
    }
    const cols = ["Player", "Tagged filings", "Years", "Total spend (all issues)"];
    const rows = DATA.players.map(p => {
      const r = [p.name, p.filings, p.y0 + "–" + p.y1, p.spend];
      if (CLS_NAME) { r.splice(1, 0, CLS_NAME[p.cls]); r.push(p.note); }
      return r;
    });
    if (CLS_NAME) { cols.splice(1, 0, "Class"); cols.push("Class note"); }
    tableView(cardEl, cols, rows, CLS_NAME ? ["s", "s", "#", "s", "$", "s"] : ["s", "#", "s", "$"]);
  }

  /* Engagements (optional) */
  if (DATA.engagements) {
    const w = W("engagements");
    const { box, cardEl } = card(app, w.title || "Engagements — and what they billed",
      w.sub || "Every engagement (client × lobbying firm pair with tagged filings), ranked by reported billings in the tagged quarters. Color = whether the engagement has a DECLARED termination filing. Click a bar for the filings and the engagement's own declared language.",
      w.foot || "Dollars are the engagement's full reported billing for the quarters where the tagged language appears — filing-level disclosure cannot split dollars by issue. Termination is declared only (senate filing_type termination family), never inferred from silence.");
    moreOptions(cardEl, QI.engagements);
    const lg = legend(cardEl, [
      { name: "Active (no termination filed)", color: SLOT[0] },
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
        "Raw records on lda.senate.gov. Full engagement table incl. declared text in the package's data/ CSVs.",
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
    const w = W("trend");
    const { box, cardEl } = card(app, w.title || "Quarterly trend",
      w.sub || "Tagged senate filings and distinct clients per quarter (amendment-deduped, registrations excluded). Click a quarter to list exactly the filings it counts.",
      w.foot || "");
    moreOptions(cardEl, QI.trend);
    const lg = legend(cardEl, [{ name: "Tagged filings", color: SLOT[0] }, { name: "Distinct clients", color: SLOT[1] }], "line");
    cardEl.insertBefore(lg, box);
    const tPanel = recPanel(cardEl, box,
      "Click a quarter on the chart to list the deduped filings behind it — the list reconciles with the plotted number (a mismatch fails the package build).");
    linePanel(box, {
      x: DATA.trend.q, fmt: "#",
      series: [
        { name: "Tagged filings", values: DATA.trend.filings },
        { name: "Distinct clients", values: DATA.trend.clients }
      ],
      onClick: (i, q) => {
        const rows = (DATA.trendFilings && DATA.trendFilings[q]) || [];
        tPanel.show(q + " — " + rows.length + " deduped tagged filings",
          "Same dedup semantics as the chart (latest amendment per registrant × client × quarter; registrations excluded).",
          [["", rows.map(r => ({ href: LDA_F(r[0]), text: r[1],
            tail: " · " + regDisp(r[1], r[2]) + (r[3] != null ? " · " + fmtMoney(r[3]) : "") + kwDisp(r[4]) }))]]);
      }
    });
    tableView(cardEl, ["Quarter", "Tagged filings", "Distinct clients"],
      DATA.trend.q.map((q, i) => [q, DATA.trend.filings[i], DATA.trend.clients[i]]), ["s", "#", "#"]);
  }

  /* Issue-code scatter */
  {
    const w = W("scatter");
    const { box, cardEl } = card(app, w.title || "Where the text actually files — issue-code scatter",
      w.sub || "Issue codes the registrants filed their tagged free-text under (senate + house text blocks).",
      w.foot || "");
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
    const w = W("keywords");
    const { box, cardEl } = card(app, w.title || "Which words carried the signal",
      w.sub || "Distinct filings matched by each curated lexicon phrase (whole-word, case-insensitive).",
      w.foot || "");
    moreOptions(cardEl, QI.keywords);
    hbars(box, {
      items: DATA.keywords.map(d => ({ label: d.kw, value: d.filings })),
      fmt: "#", labelW: 240, valueName: "distinct filings matched"
    });
  }

  /* Registrant firms */
  {
    const w = W("registrants");
    const { box, cardEl } = card(app, w.title || "The firms doing the work",
      w.sub || "Outside lobbying firms on tagged filings (self-filers excluded), ranked by tagged filings.",
      w.foot || "Reported amounts are ranking signals summed over tagged filings, not exact issue dollars.");
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

  /* Top spenders (optional — players ranked by canonical all-issue spend) */
  if (W("spendTop").show) {
    const w = W("spendTop");
    const items = DATA.players.filter(p => p.spend)
      .sort((a, b) => b.spend - a.spend).slice(0, 12);
    const { box, cardEl } = card(app, w.title || "The biggest lobbying budgets on the map",
      w.sub || "Mapped players ranked by TOTAL federal lobbying spend across all issues (canonical, double-count-corrected) — a size signal, not issue dollars.",
      w.foot || "");
    moreOptions(cardEl, QI.players);
    hbars(box, {
      items: items.map(p => ({ label: p.name, value: p.spend, note: fmtNum(p.filings) + " tagged filings" })),
      fmt: "$", labelW: 360, valueName: "canonical all-issue spend"
    });
  }

  /* LD-203 giving (optional) */
  if (DATA.giving) {
    const w = W("giving");
    const { box, cardEl } = card(app, w.title || "Disclosed LD-203 giving",
      w.sub || "The roster organizations' own disclosed LD-203 giving (registrant-filed regime; amendment-deduped). NOT Super-PAC money — that lives in FEC data and never sums with this.",
      w.foot || (DATA.giving.total != null ? "Roster total: " + fmtMoney(DATA.giving.total) + " (deduplicated)." : ""));
    moreOptions(cardEl, QI.giving);
    const half = div("two-col", box);
    const left = div("", half), right = div("", half);
    div("filings-group", left, "Top giving organizations");
    hbars(left, {
      items: DATA.giving.orgs.map(o => ({ label: o.name, value: o.total, note: o.items + " items" })),
      fmt: "$", labelW: 300, valueName: "disclosed LD-203 giving"
    });
    if (DATA.giving.members && DATA.giving.members.length) {
      div("filings-group", right, "Member rollup (variants + support committees merged; JFC/multi-honoree stay unallocated)");
      hbars(right, {
        items: DATA.giving.members.map(m => ({
          label: m.name, value: m.total,
          note: "direct " + fmtMoney(m.direct)
            + (m.campaign ? " · campaign " + fmtMoney(m.campaign) : "")
            + (m.ldpac ? " · ldpac " + fmtMoney(m.ldpac) : "")
            + (m.jfc ? " · +jfc " + fmtMoney(m.jfc) + " unalloc" : "")
            + (m.inferred ? " · ⚠inferred" : "")
        })),
        fmt: "$", labelW: 300, valueName: "attributable member support"
      });
    } else {
      div("filings-group", right, "Top raw recipients (filed strings, lightly normalized)");
      hbars(right, {
        items: DATA.giving.recipients.map(o => ({ label: o.name, value: o.total, note: o.items + " items" })),
        fmt: "$", labelW: 300, valueName: "disclosed LD-203 giving"
      });
    }
  }

  /* Press share */
  {
    const w = W("press");
    const { box, cardEl } = card(app, w.title || "The say side — member press releases",
      w.sub || "Share of ALL member press releases matching the vocabulary, by quarter. Click a quarter to list the releases.",
      w.foot || "");
    moreOptions(cardEl, QI.press);
    const pPanel = recPanel(cardEl, box,
      "Click a quarter to list its matching member press releases (with links).");
    linePanel(box, {
      x: DATA.press.q, fmt: "%",
      series: [{ name: "Share of member releases", values: DATA.press.share, color: SLOT[5] }],
      height: 210,
      onClick: (i, q) => {
        const rows = (DATA.pressReleases && DATA.pressReleases[q]) || [];
        pPanel.show(q + " — " + rows.length + " matching member releases",
          "Whole-word regex over title + text; offline list carries src_file:src_line citation keys.",
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
})();
