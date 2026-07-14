(function () {
  const app = document.getElementById("app");
  const QI = DATA.queryInfo || {};
  moreOptions(statTiles(app, DATA.kpis), QI.kpis);

  /* shared underlying-records panel: click a mark -> the raw records behind it */
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
  const LDA_C = u => "https://lda.senate.gov/filings/public/contribution/" + u + "/print/";
  const regDisp = (player, reg) =>
    reg && player && reg.toUpperCase() === player.toUpperCase() ? "self-filed" : reg;
  const kwDisp = k => {
    if (!k) return "";
    const a = k.split("; ");
    return " · matched: \u201C" + a.slice(0, 2).join("\u201D, \u201C") + "\u201D"
      + (a.length > 2 ? " +" + (a.length - 2) + " more" : "");
  };

  /* Players map: spend × crypto-attention scatter (2026-07-11 intensity revision) */
  {
    const nUnplotted = DATA.players.filter(p => !(p.spend > 0) || p.share == null).length;
    const { box, cardEl } = card(app, "The player map — who lobbies on crypto, and how much of their attention it gets",
      DATA.players.length + " client-side players: the top 60 by crypto-tagged filings, plus core players (≥8 filings) with a top-15 all-issue lobbying budget — so the ambient giants are placed, not hidden. Across = total federal lobbying spend 2022–2026Q1, all issues, log scale (filing-level disclosure can't split dollars by issue). Up = crypto activity share: the % of the player's senate activity blocks that are crypto-tagged — the intensity signal that separates a dedicated crypto shop from a giant with a crypto side-desk. Dot size = crypto-tagged filings. Every plotted player has a sustained crypto filing record; an all-issue budget alone still doesn't buy a spot. Click a dot to list its raw filings.",
      "Reading it: top = crypto-dedicated (Coinbase, 94.8% share); bottom-right = ambient giants — the U.S. Chamber's $311.6M all-issue budget sits at 3.4% crypto share (19 of its 555 activity blocks; its C_TEC/CCMC arm files separately at 33%). Share is entity-grain: resolver-split families (Mastercard×3, Visa×2, a16z…) each carry their own share. Recall-first map: an organization appears if its filings' free-text names crypto vocabulary (43 curated phrases); most mapped players have no crypto term in their name." + (nUnplotted ? " " + nUnplotted + " selected player(s) with no reported spend or no non-registration activity blocks are in the table view, not plotted." : "") + " Full list in data/crypto_players.csv; every filing behind every player, with a public lda.senate.gov link, in data/crypto_player_filings.csv.");
    moreOptions(cardEl, QI.players);
    const lg = legend(cardEl, [
      { name: "Crypto-native (Coinbase, Kraken, Blockchain Assn…)", color: SLOT[0] },
      { name: "Diversified filer (PayPal, Visa, Fidelity, banks…)", color: SLOT[2] }
    ]);
    cardEl.insertBefore(lg, box);
    const filingsPanel = div("filings-panel", null);
    scatterXY(box, {
      items: DATA.players.map(p => ({
        label: p.name, short: p.short, x: p.spend || 0, y: p.share,
        size: p.filings, slot: p.vis ? 0 : 2, extra: p
      })),
      height: 480, yMax: 100, labelTop: 16,
      rules: [
        { y: 5, label: "ambient <5%", labelAt: 2 },
        { y: 25, label: "engaged 5–25%", labelAt: 14 },
        { y: 25, noLine: true, label: "dedicated ≥25%", labelAt: 60 }
      ],
      ttRows: d => [
        { color: SLOT[d.slot], value: fmtMoney(d.extra.spend), name: "total lobbying spend (all issues)" },
        { color: null, value: fmtPct(d.extra.share), name: "crypto activity share (" + fmtNum(d.extra.cblocks) + " of " + fmtNum(d.extra.ablocks) + " senate activity blocks)" },
        { color: null, value: fmtNum(d.extra.filings), name: "crypto-tagged senate filings" },
        { color: null, value: d.extra.tier + " · " + d.extra.band, name: "tier (filings) · intensity band (share)" },
        { color: null, value: "click", name: "list this player's raw filings" }
      ],
      onClick: d => showFilings(d.extra)
    });
    cardEl.insertBefore(filingsPanel, box.nextSibling);
    filingsPanel.textContent = "Click a dot to list that player's crypto-tagged filings here — each links to the raw record on lda.senate.gov and shows the matched phrase that tagged it.";
    function showFilings(p) {
      const rows = (DATA.playerFilings && DATA.playerFilings[p.name]) || null;
      filingsPanel.textContent = "";
      const h = document.createElement("strong");
      h.textContent = p.name + " — " + fmtNum(p.filings) + " crypto-tagged senate filings";
      filingsPanel.appendChild(h);
      if (!rows) {
        filingsPanel.appendChild(document.createTextNode(
          " · filing links for this player are in data/crypto_player_filings.csv (the dashboard embeds links for the top players only)."));
        return;
      }
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
          a.href = "https://lda.senate.gov/filings/public/filing/" + uuid + "/print/";
          a.target = "_blank"; a.rel = "noopener";
          a.textContent = label;
          li.appendChild(a);
          li.appendChild(document.createTextNode(
            " · " + regDisp(p.name, reg) + (amt != null ? " · " + fmtMoney(amt) : "") + kwDisp(kws)));
          ul.appendChild(li);
        }
        scroll.appendChild(ul);
      }
      div("note", filingsPanel,
        "Raw records on lda.senate.gov (needs internet). Same list offline: data/crypto_player_filings.csv.");
    }
    tableView(cardEl, ["Player", "Total spend (all issues)", "Crypto activity share %", "Intensity band", "Crypto filings (senate)", "Tier", "Crypto-native"],
      DATA.players.map(p => [p.name, p.spend, p.share, p.band, p.filings, p.tier, p.vis ? "yes" : "no"]),
      ["s", "$", "%", "s", "#", "s", "s"]);
  }

  /* Trend */
  {
    const { box, cardEl } = card(app, "2025 is the breakout year",
      "Crypto-tagged senate filings and distinct client organizations per quarter (amendment-deduped).",
      "Flat through 2022–2024 (~230 filings, ~175 clients a quarter), then +60% through 2025 as the GENIUS Act (stablecoins) and market-structure bills moved. 2026-Q1 holds the new plateau.");
    moreOptions(cardEl, QI.trend);
    const lg = legend(cardEl, [{ name: "Crypto-tagged filings", color: SLOT[0] }, { name: "Distinct clients", color: SLOT[1] }], "line");
    cardEl.insertBefore(lg, box);
    const tPanel = recPanel(cardEl, box,
      "Click a quarter on the chart to list that quarter's filings here — each links to the raw record on lda.senate.gov.");
    linePanel(box, {
      x: DATA.trend.q, fmt: "#",
      series: [
        { name: "Crypto-tagged filings", values: DATA.trend.filings },
        { name: "Distinct clients", values: DATA.trend.clients }
      ],
      onClick: (i, q) => {
        const rows = (DATA.trendFilings && DATA.trendFilings[q]) || [];
        tPanel.show(
          q + " — " + fmtNum(rows.length) + " crypto-tagged filings (amendment-deduped, registrations excluded — matches the chart) · " + fmtNum(DATA.trend.clients[i]) + " distinct clients",
          "Raw records on lda.senate.gov. Same list offline: data/crypto_trend_filings.csv. 'matched' = the exact curated phrase(s) found in the filing's issue text — Ctrl-F it on the linked page to see it in context. Per-filing amounts are reported income/expenses — ranking signals; spend aggregates use v_client_canonical_spend.",
          [["", rows.map(r => ({ href: LDA_F(r[0]), text: r[1],
            tail: " · " + regDisp(r[1], r[2]) + (r[3] != null ? " · " + fmtMoney(r[3]) : "") + kwDisp(r[4]) }))]]);
      }
    });
    tableView(cardEl, ["Quarter", "Filings", "Clients", "Canonical spend of active clients (all-issue)"],
      DATA.trend.q.map((q, i) => [q, DATA.trend.filings[i], DATA.trend.clients[i], DATA.trend.spend[i]]),
      ["s", "#", "#", "$"]);
  }

  /* Where it hides */
  {
    const { box, cardEl } = card(app, "Where crypto hides in the disclosure forms",
      "Share of crypto-tagged filing text by the general issue code the registrant filed it under.",
      "Only 43.7% sits under Financial Institutions (FIN). The rest scatters across banking, taxation, science/tech, computers, consumer safety, agriculture and 40+ more codes — an issue-code filter alone misses most of the industry. This is why the map is built from what filers SAY (free-text vocabulary), not the category they tick.");
    moreOptions(cardEl, QI.scatter);
    const scPanel = recPanel(cardEl, box,
      "Click a code's bar to list the senate filings whose crypto-tagged text was filed under it.");
    hbars(box, {
      items: DATA.issueScatter.map(d => ({ label: d.code + " — " + d.name, value: d.pct, note: fmtNum(d.docs) + " tagged text blocks" })),
      fmt: "%", labelW: 330, valueName: "share of crypto-tagged text",
      onClick: (d, i) => {
        const c = DATA.issueScatter[i];
        const sf = (DATA.scatterFilings && DATA.scatterFilings[c.code]) || { senBlocks: 0, nFilings: 0, rows: [] };
        scPanel.show(
          c.code + " — " + fmtNum(c.docs) + " tagged text blocks in the chart (both chambers) · " + fmtNum(sf.senBlocks) + " senate blocks across " + fmtNum(sf.nFilings) + " senate filings",
          (sf.nFilings > sf.rows.length ? "Top " + fmtNum(sf.rows.length) + " filings by reported amount shown; " : "") +
          "full list with every filing: data/crypto_issue_code_filings.csv. House copies are mirrors of these filings and carry no separate public URL.",
          [["", sf.rows.map(r => ({ href: LDA_F(r[0]), text: r[1],
            tail: " · " + regDisp(r[1], r[2]) + " · " + r[3] + (r[4] != null ? " · " + fmtMoney(r[4]) : "") + " · " + fmtNum(r[5]) + " block" + (r[5] > 1 ? "s" : "") + kwDisp(r[6]) }))]]);
      }
    });
    tableView(cardEl, ["Issue code", "Crypto-tagged text blocks", "Share %"],
      DATA.issueScatter.map(d => [d.code + " — " + d.name, d.docs, d.pct]), ["s", "#", "%"]);
  }

  /* Top spenders — native vs diversified, side by side */
  {
    const { box, cardEl } = card(app, "The money — two different industries lobby on crypto",
      "Total canonical lobbying spend 2022–2026Q1 (all issues). Left: crypto-native organizations — for them this is essentially crypto money. Right: diversified CRYPTO-FORWARD players (≥8 crypto filings AND ≥5% crypto activity share) whose budgets span many issues; crypto is one desk, but a real one.",
      "The comparison is the story: Coinbase's entire five-year lobbying budget ($15M) is smaller than what Visa ($39M) or Mastercard ($20M) spends across all its issues — but the crypto-native side is the one whose money is all-in on this fight. The ≥5% share gate keeps ambient giants out of this list: the U.S. Chamber ($311.6M all-issue, 3.4% crypto share) and AARP ($77.1M, 2.5%) are on the player map and in the CSVs, not here. Known name-variant families (Crypto.com/Foris, Kraken/Payward, a16z/AH Capital) are combined here; per-variant rows are in data/crypto_players.csv.");
    moreOptions(cardEl, QI.money);
    const mPanel = recPanel(cardEl, box,
      "Click a bar to see the quarter-by-quarter spend behind it (v_client_canonical_spend) and the player's crypto-tagged filings.");
    const showSpend = d => {
      const qs = (DATA.spendQuarters && DATA.spendQuarters[d.label]) || [];
      const fams = (DATA.barPlayers && DATA.barPlayers[d.label]) || [d.label];
      const multi = fams.length > 1;
      const groups = [[
        "Canonical-spend quarters (" + fmtNum(qs.length) + " rows — these sum to the bar)",
        qs.map(r => ({ text: r[0] + (multi ? " · " + r[1] : ""),
          tail: " — canonical " + fmtMoney(r[4]) + " (in-house " + fmtMoney(r[2]) + " / outside " + fmtMoney(r[3]) + ") · " + r[5] }))]];
      const fl = [];
      for (const pn of fams) {
        for (const f of ((DATA.playerFilings && DATA.playerFilings[pn]) || [])) {
          fl.push({ href: LDA_F(f[0]), text: f[1],
            tail: " · " + (multi ? pn + " · " : "") + regDisp(pn, f[2]) + (f[3] != null ? " · " + fmtMoney(f[3]) : "") + (f[4] ? " · LD-1 registration" : "") + kwDisp(f[5]) });
        }
      }
      groups.push(["Crypto-tagged filings — raw records (" + fmtNum(fl.length) + ")", fl]);
      mPanel.show(d.label + " — " + fmtMoney(d.value) + " total lobbying spend (all issues)",
        "Quarter rows: data/crypto_spend_quarters.csv (they sum to the bar). Filings link to raw records on lda.senate.gov; the spend covers ALL the player's lobbying, the filings listed are its crypto-tagged ones.",
        groups);
    };
    const grid = div("two-col", box);
    const left = div(null, grid), right = div(null, grid);
    div("sub", left, "Crypto-native");
    hbars(div(null, left), {
      items: DATA.nativeSpend.map(d => ({ label: d.name, value: d.spend, note: fmtNum(d.filings) + " crypto-tagged filings" })),
      fmt: "$", labelW: 190, rowH: 27, width: 480, color: SLOT[0], valueName: "total lobbying spend",
      onClick: showSpend
    });
    div("sub", right, "Diversified crypto-forward (≥8 crypto filings & ≥5% crypto share)");
    hbars(div(null, right), {
      items: DATA.diversSpend.map(d => ({ label: d.name, value: d.spend, note: fmtNum(d.filings) + " crypto-tagged filings" })),
      fmt: "$", labelW: 190, rowH: 27, width: 480, color: SLOT[2], valueName: "total lobbying spend (all issues)",
      onClick: showSpend
    });
    tableView(cardEl, ["Crypto-native", "Spend", "", "Diversified", "Spend (all issues)"],
      DATA.nativeSpend.map((d, i) => [d.name, d.spend, "",
        DATA.diversSpend[i] ? DATA.diversSpend[i].name : "",
        DATA.diversSpend[i] ? DATA.diversSpend[i].spend : null]),
      ["s", "$", "s", "s", "$"]);
  }

  /* Giving — LD-203, three-tier giver split (>=5% intensity gate, 2026-07-11) */
  {
    const { box, cardEl } = card(app, "Who gets the money — and whether it comes from crypto natives or the incumbents (disclosed LD-203)",
      "Every recipient shows two bars: giving by 105 hand-triaged crypto-NATIVE organizations (exchanges, protocols, miners, crypto VCs, trade groups) vs giving by the 147 CRYPTO-FORWARD diversified players — banks, card networks, asset managers with a sustained crypto record AND ≥5% crypto activity share. Giving by the 15 AMBIENT core players below the gate (AARP, U.S. Chamber, Amazon, Meta, Wells Fargo…) is deliberately NOT drawn as a bar in a crypto chart — it shows in the hover, the click-through list, the table view, and the CSV. 2022–2025, amendment-deduplicated.",
      "Attribution caveat: LD-203 giving is organization-level — a bank PAC's contribution to a Financial Services member is not necessarily crypto-motivated; the split shows WHO funds each recipient, not why. The 5% gate is an editorial cut (disclosed here and in the README); the ambient slice totals $38.8M of the old $110.7M \"diversified\" figure and is dominated by non-crypto money (AARP's caucus and Capitol-fund giving alone). Disclosed LD-203 only (Fairshake Super-PAC money is the next chart). Party/state from the corpus members table; retired members hand-mapped and flagged in the CSV. Person-name and Trump-inaugural variants combined; raw variants in data/crypto_ld203_recipients_split.csv.");
    moreOptions(cardEl, QI.giving);
    const lg = legend(cardEl, [
      { name: "From crypto-native orgs", color: SLOT[0] },
      { name: "From crypto-forward diversified (≥5% crypto share)", color: SLOT[2] }
    ]);
    cardEl.insertBefore(lg, box);
    const gPanel = recPanel(cardEl, box,
      "Click a recipient's bars to list the LD-203 items behind them — each links to the filed contribution report on lda.senate.gov.");
    const AMB = "ambient <5%-share givers (not charted)";
    const showItems = d => {
      const e = (DATA.givingItems && DATA.givingItems[d.label]) || { native: [], forward: [], ambient: [] };
      const mk = rows => rows.map(r => ({ href: LDA_C(r[0]), text: r[1],
        tail: " · " + (r[3] != null ? fmtMoney(r[3]) : "·") + " [" + r[4] + "] " + (r[2] || "·") + (r[5] > 1 ? " · " + r[5] + " versions collapsed" : "") }));
      gPanel.show(
        d.label + " — " + fmtMoney(d.a) + " crypto-native + " + fmtMoney(d.b) + " crypto-forward (chart figures) + " + fmtMoney(d.c || 0) + " ambient (context, not charted)",
        "Amendment-deduplicated LD-203 items; link opens the filed report (one version where amendments collapsed). As-filed recipient strings + full detail: data/crypto_ld203_items.csv.",
        [["From crypto-native orgs (" + fmtNum(e.native.length) + " items)", mk(e.native)],
         ["From crypto-forward diversified, ≥5% share (" + fmtNum(e.forward.length) + " items)", mk(e.forward)],
         ["From ambient <5%-share givers — context, not charted (" + fmtNum(e.ambient.length) + " items)", mk(e.ambient)]]);
    };
    div("sub", box, "Top recipients overall (ranked by charted giving: native + crypto-forward)");
    groupedHBars(div(null, box), {
      items: DATA.givingTop.map(d => ({ label: d.name, a: d.a, b: d.b, c: d.c })),
      aName: "from crypto-native orgs", bName: "from crypto-forward diversified (≥5% share)",
      cName: AMB,
      aColor: SLOT[0], bColor: SLOT[2], labelW: 330,
      onClick: showItems
    });
    div("sub", box, "Members of Congress — the two funding worlds, side by side");
    const mgrid = div("two-col", box);
    const mleft = div(null, mgrid), mright = div(null, mgrid);
    div("sub", mleft, "Top by CRYPTO-NATIVE giving");
    groupedHBars(div(null, mleft), {
      items: DATA.givingMembersNative.map(d => ({ label: d.name, a: d.a, b: d.b, c: d.c })),
      aName: "from crypto-native orgs", bName: "from crypto-forward diversified (≥5% share)",
      cName: AMB,
      aColor: SLOT[0], bColor: SLOT[2], labelW: 185, width: 480,
      onClick: showItems
    });
    div("sub", mright, "Top by CRYPTO-FORWARD diversified giving");
    groupedHBars(div(null, mright), {
      items: DATA.givingMembersDiv.map(d => ({ label: d.name, a: d.a, b: d.b, c: d.c })),
      aName: "from crypto-native orgs", bName: "from crypto-forward diversified (≥5% share)",
      cName: AMB,
      aColor: SLOT[0], bColor: SLOT[2], labelW: 185, width: 480,
      onClick: showItems
    });
    tableView(cardEl, ["Recipient", "From crypto-native", "From crypto-forward diversified (≥5% share)", "From ambient <5%-share givers (not charted)"],
      DATA.givingRecipientsRaw.map(d => [d.name, d.a, d.b, d.c]), ["s", "$", "$", "$"]);
  }

  /* FEC vs LD-203 */
  {
    const { box, cardEl } = card(app, "The disclosed-lobbying view understates the political money ~60×",
      "Same players, two disclosure regimes: contributions into the Fairshake Super-PAC network (FEC, 2024+2026 cycles) vs their disclosed LD-203 giving.",
      "Fairshake + Defend American Jobs + Protect Progress (committees resolved live from openFEC; itemized line-11 contributions only, memo/attribution rows and crypto-sale proceeds excluded). FEC↔LDA name matches are candidates for human confirmation, shown as reported. LD-203 legally cannot capture Super-PAC money — the gap is the point, not an error. One more thing this chart shows: because the Fairshake network is single-issue, it is the ONLY issue-attributable crypto money on this page — and every nonzero network contributor is crypto-NATIVE. No bank, card network, or trade-association mega-filer appears; the diversified slice's giving is organization-level and never crypto-attributable.");
    moreOptions(cardEl, QI.fec);
    const lg = legend(cardEl, [
      { name: "FEC Super-PAC contributions (Fairshake network)", color: SLOT[0] },
      { name: "Disclosed LD-203 giving", color: SLOT[1] }
    ]);
    cardEl.insertBefore(lg, box);
    const fPanel = recPanel(cardEl, box,
      "Click a player to see its matched FEC contributor names, sample transaction ids, and filtered links into the FEC receipts browser.");
    groupedHBars(box, {
      items: DATA.fec.map(d => ({ label: d.name, a: d.fec, b: d.ld203 })),
      aName: "FEC Super-PAC (Fairshake network)", bName: "Disclosed LD-203 giving", labelW: 250,
      onClick: d => {
        const e = (DATA.fecDetail && DATA.fecDetail[d.label]) || null;
        if (!e) return;
        fPanel.show(
          d.label + " — " + fmtMoney(d.a) + " into the Fairshake network (FEC) vs " + fmtMoney(d.b) + " disclosed LD-203",
          "FEC transactions live in FEC data, not the LDA corpus: the links open the FEC receipts browser pre-filtered to the three network committees + the matched contributor name (itemized rows, browsable to each transaction). Raw API responses with transaction ids are cached in out/fec_cache/ — the citeable evidence. Name matches are candidates (confidence: " + e.conf + "), never auto-merged.",
          [["Matched FEC contributor names → receipts browser", e.links.map(l => ({ href: l[1], text: l[0], tail: " → FEC receipts (filtered)" }))],
           ["Committees", [{ text: e.committees }]],
           ["Sample FEC transaction ids (in the cached raw JSON)", [{ text: e.tids }]]]);
      }
    });
    tableView(cardEl, ["Player", "FEC Super-PAC", "LD-203 disclosed", "Match confidence"],
      DATA.fec.map(d => [d.name, d.fec, d.ld203, d.conf]), ["s", "$", "$", "s"]);
  }

  /* Press coupling */
  {
    const { box, cardEl } = card(app, "Congress talks about crypto more too — but less than it files",
      "Share of member press releases mentioning crypto terms, by quarter (crypto share of ~141K releases).",
      "Peaks at 1.35% in 2025-Q2 — the GENIUS Act floor fight — up from ~0.3–0.5% in 2022–2024. Even at peak, crypto is a small share of congressional messaging while the filing side has grown 60%: the lobbying build-out is bigger than the public conversation.");
    moreOptions(cardEl, QI.press);
    const pPanel = recPanel(cardEl, box,
      "Click a quarter to list that quarter's crypto-mentioning member releases.");
    linePanel(box, {
      x: DATA.press.q, fmt: "%",
      series: [{ name: "Crypto share of member press releases", values: DATA.press.share }],
      height: 210,
      onClick: (i, q) => {
        const rows = (DATA.pressReleases && DATA.pressReleases[q]) || [];
        pPanel.show(
          q + " — " + fmtNum(rows.length) + " crypto-mentioning releases (matches the chart) of " + fmtNum(DATA.press.all[i]) + " total",
          "Links are the original release URLs and may rot — the scraped text in the corpus is the evidence; citation keys (src_file:src_line) are in data/crypto_press_releases.csv.",
          [["", rows.map(r => ({ href: r[5], text: r[0],
            tail: " · " + r[1] + " (" + r[2] + "-" + r[3] + ") · " + r[4] }))]]);
      }
    });
    tableView(cardEl, ["Quarter", "Crypto releases", "All releases", "Share %"],
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
