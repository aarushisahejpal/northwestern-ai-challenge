(function () {
  const app = document.getElementById("app");
  const LDA_F = u => "https://lda.senate.gov/filings/public/filing/" + u + "/print/";

  /* quarter switcher — one dashboard, one report quarter at a time.
     #2025-Q4 / #2026-Q1 in the URL selects the initial quarter. */
  const seg = div("seg", app);
  const host = div(null, app);
  const btns = {};
  for (const lbl of DATA.order) {
    const b = document.createElement("button");
    b.type = "button"; b.textContent = lbl;
    b.addEventListener("click", () => select(lbl));
    seg.appendChild(b); btns[lbl] = b;
  }
  function select(lbl) {
    for (const k in btns) btns[k].classList.toggle("active", k === lbl);
    try { history.replaceState(null, "", "#" + lbl); } catch (e) {}
    renderQuarter(lbl);
  }

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

  function renderQuarter(TQ) {
    const Q = DATA.quarters[TQ];
    const QI = Q.queryInfo || {};
    host.textContent = "";
    cavHost.textContent = "";
    {  /* per-quarter caveats live under the (static) pardon card */
      const c = div("card", cavHost);
      const h = document.createElement("h2"); h.textContent = "How to read this (caveats that matter)"; c.appendChild(h);
      const ul = document.createElement("ul"); ul.className = "caveats"; c.appendChild(ul);
      Q.caveats.forEach(t => { const li = document.createElement("li"); li.textContent = t; ul.appendChild(li); });
    }

    moreOptions(statTiles(host, Q.kpis), QI.kpis);
    if (Q.isLatest) {
      const w = div("filings-panel", host);
      w.textContent = TQ + " is the newest quarter in the DB — terminations post with a lag, " +
        "so its counts are a floor until the next corpus refresh, and the ±1-quarter swap window " +
        "can only reach backward.";
    }

    /* Quarterly trend (corpus-wide; foot reads the active quarter) */
    {
      const ti = DATA.trend.q.indexOf(TQ);
      const { box, cardEl } = card(host, "Churn is a rhythm — and Q4 is the churn quarter",
        "Declared terminations and first-ever engagements per quarter, 2022–2026Q1 (senate LD-2 termination filings; pairs grouped by resolved client entity).",
        "Every Q4 runs 22–43% above that year's other quarters — engagements are closed out at year-end, so a Q4 compares to prior Q4s, not to Q3. " +
        TQ + ": " + fmtNum(DATA.trend.term[ti]) + " terminations and " +
        (DATA.trend.nw[ti] == null ? "–" : fmtNum(DATA.trend.nw[ti])) + " new engagements. " +
        "2022-Q1 'new' is blank — the corpus starts there, so every pair would count as new. The last quarter is a floor: terminations post with a lag.");
      moreOptions(cardEl, QI.trend);
      const lg = legend(cardEl, [
        { name: "Declared terminations", color: SLOT[0] },
        { name: "New engagements", color: SLOT[1] }
      ], "line");
      cardEl.insertBefore(lg, box);
      const tPanel = recPanel(cardEl, box,
        "Click a quarter to list its biggest terminations and new engagements here — each links to the raw filing on lda.senate.gov.");
      linePanel(box, {
        x: DATA.trend.q, fmt: "#",
        series: [
          { name: "Declared terminations", values: DATA.trend.term },
          { name: "New engagements", values: DATA.trend.nw }
        ],
        onClick: (i, q) => {
          const e = (DATA.trendTop && DATA.trendTop[q]) || { term: [], hire: [] };
          tPanel.show(
            q + " — " + fmtNum(DATA.trend.term[i]) + " terminations · " + (DATA.trend.nw[i] == null ? "–" : fmtNum(DATA.trend.nw[i])) + " new engagements (chart figures)",
            "Top " + e.term.length + " of each shown by engagement income; full per-quarter lists: data/turnover_trend_top.csv (counts reconcile with this chart at export); full report-quarter lists: the per-quarter CSVs in data/.",
            [["Biggest terminations (trailing-4-quarter income)", e.term.map(r => ({
                href: LDA_F(r[0]), text: r[1], tail: " · ended w/ " + r[2] + (r[3] != null ? " · " + fmtMoney(r[3]) : "") }))],
             ["Biggest new engagements (first-quarter income)", e.hire.map(r => ({
                href: LDA_F(r[0]), text: r[1], tail: " · hired " + r[2] + (r[3] != null ? " · " + fmtMoney(r[3]) : "") }))]]);
        }
      });
      tableView(cardEl, ["Quarter", "Declared terminations", "New engagements"],
        DATA.trend.q.map((q, i) => [q, DATA.trend.term[i], DATA.trend.nw[i]]), ["s", "#", "#"]);
    }

    /* Biggest terminations */
    {
      const { box, cardEl } = card(host, "The books of business that ended in " + TQ,
        "Engagements with a declared termination filing in " + TQ + ", ranked by the income the engagement reported over its final four quarters — the book of business that walked out the door.",
        "A termination is the registrant's own filing (filing types 1T–4T and variants), never inferred from a client going quiet. RE-ENGAGED = the same pair files again in a later quarter (a pause, not an exit). ONE-QUARTER = hired and terminated inside " + TQ + ". Full list (" + fmtNum(Q.nTerm) + " terminations): data/turnover_" + TQ.replace("-", "") + "_terminations.csv.");
      moreOptions(cardEl, QI.terms);
      const hPanel = recPanel(cardEl, box,
        "Click a bar to see the quarter-by-quarter income rows that sum to it — every quarter links to its raw filing, plus the termination filing itself.");
      hbars(box, {
        items: Q.terms.map(d => ({
          label: d.client + " · " + d.regShort,
          value: d.trail4 || 0,
          note: d.nq + " quarters since " + d.first + (d.reeng ? " · RE-ENGAGED later" : "") + (d.newq ? " · ONE-QUARTER engagement" : "")
        })),
        fmt: "$", labelW: 330, valueName: "trailing-4-quarter income",
        onClick: (d, i) => {
          const e = Q.terms[i];
          const rows = (Q.termHistory && Q.termHistory[e.key]) || [];
          hPanel.show(
            e.client + " — ended with " + e.registrant + " · " + fmtMoney(e.trail4) + " trailing-4-quarter income (the bar)",
            "Amendment-deduped quarterly rows; the last-4-quarter rows (marked ●) sum to the bar — reconciled at export. Full audit: data/turnover_" + TQ.replace("-", "") + "_term_history.csv.",
            [["Termination filing", [{ href: LDA_F(e.uuid), text: "Termination report (" + TQ + ")", tail: " · filing " + e.uuid.slice(0, 8) }]],
             ["Engagement history (" + rows.length + " quarterly filings)", rows.map(r => ({
                href: LDA_F(r[2]), text: r[0], tail: " · " + (r[1] != null ? fmtMoney(r[1]) : "no income reported") + " · " + r[3] + (r[4] ? " ●" : "") }))]]);
        }
      });
      tableView(cardEl, ["Client", "Ended with", "Trailing-4q income", "Quarters", "Since", "Re-engaged", "One-quarter"],
        Q.terms.map(d => [d.client, d.registrant, d.trail4, d.nq, d.first, d.reeng ? "yes" : "", d.newq ? "yes" : ""]),
        ["s", "s", "$", "#", "s", "s", "s"]);
    }

    /* Biggest new engagements */
    {
      const { box, cardEl } = card(host, "The biggest new engagements of " + TQ,
        "Pairs whose first-ever filing (including the LD-1 registration) lands in " + TQ + ", ranked by first-quarter reported income.",
        "'New' is grouped by resolved client entity — a re-registration under a fresh client id does not count as a hire. Income blank = registration-only so far (the first quarterly wasn't due yet). Full list (" + fmtNum(Q.nNew) + "): data/turnover_" + TQ.replace("-", "") + "_new_engagements.csv.");
      moreOptions(cardEl, QI.hires);
      const nPanel = recPanel(cardEl, box,
        "Click a bar to list every " + TQ + " filing of that new engagement — registration and first quarterly, each linking to the raw record.");
      hbars(box, {
        items: Q.hires.map(d => ({
          label: d.client + " · " + d.regShort,
          value: d.income || 0,
          note: (d.termSameQ ? "TERMINATED the same quarter · " : "") + (d.regOnly ? "registration only so far" : "first-quarter income")
        })),
        fmt: "$", labelW: 330, color: SLOT[1], valueName: "first-quarter income",
        onClick: (d, i) => {
          const e = Q.hires[i];
          const rows = (Q.hireFilings && Q.hireFilings[e.key]) || [];
          nPanel.show(
            e.client + " — hired " + e.registrant + (e.income != null ? " · " + fmtMoney(e.income) + " in its first quarter" : " · registration only so far"),
            "All " + TQ + " filings for this pair. Full index: data/turnover_" + TQ.replace("-", "") + "_new_engagement_filings.csv.",
            [["", rows.map(r => ({ href: LDA_F(r[0]), text: r[1],
                tail: r[2] != null ? " · " + fmtMoney(r[2]) : "" }))]]);
        }
      });
      tableView(cardEl, ["Client", "Hired", "First-quarter income", "Registration only", "Terminated same qtr"],
        Q.hires.map(d => [d.client, d.registrant, d.income, d.regOnly ? "yes" : "", d.termSameQ ? "yes" : ""]),
        ["s", "s", "$", "s", "s"]);
    }

    /* Swaps + in-house moves */
    {
      const { box, cardEl } = card(host, "Who changed horses — firm swaps and in-house moves around " + TQ,
        "A client entity that terminated one registrant in " + TQ + " and first-filed with a different one within ±1 quarter. Left: clients that took the work in-house (or put it out). Right: the biggest firm-to-firm swappers, sized by the client's canonical lobbying spend in " + TQ + ".",
        "IN-HOUSE = the new (or old) registrant resolves to the client itself. A swap row is evidence of movement, not causation — the disclosure says who moved, not why. Client size uses v_client_canonical_spend (the double-count-corrected view), so a client's own in-house filing and its outside firms are never summed. All " + fmtNum(Q.nSwaps) + " rows: data/turnover_" + TQ.replace("-", "") + "_swaps.csv.");
      moreOptions(cardEl, QI.swaps);
      const sPanel = recPanel(cardEl, box,
        "Click a bar to open both sides of each move — the termination filing and the new engagement's first filing.");
      const dqText = dq => dq === 0 ? "same quarter" :
        Math.abs(dq) + " qtr" + (Math.abs(dq) > 1 ? "s" : "") + (dq > 0 ? " after" : " before");
      const showSwap = d => {
        const e = d.extra;
        sPanel.show(
          e.client + " — " + e.moves.length + " move" + (e.moves.length > 1 ? "s" : "") + " around " + TQ,
          "Each move pairs a termination with the new engagement's first filing; 'hire timing' is relative to the termination quarter. Full list: data/turnover_" + TQ.replace("-", "") + "_swaps.csv.",
          e.moves.map(m => [
            m.old_firm + " → " + m.new_firm + (m.move ? " (" + m.move.toUpperCase() + ")" : "") + " · hire " + dqText(m.dq),
            [{ href: LDA_F(m.term_uuid), text: "Termination filing — " + m.old_firm, tail: " · " + m.term_uuid.slice(0, 8) },
             { href: LDA_F(m.hire_uuid), text: "First filing — " + m.new_firm, tail: " · " + m.hire_uuid.slice(0, 8) }]]));
      };
      const moveNote = d => d.moves.length === 1
        ? d.moves[0].old_firm + " → " + d.moves[0].new_firm + (d.moves[0].move ? " · " + d.moves[0].move : "")
        : d.moves.length + " moves — click to list them";
      const grid = div("two-col", box);
      const left = div(null, grid), right = div(null, grid);
      div("sub", left, "In-house moves (" + Q.inhouse.length + " clients)");
      hbars(div(null, left), {
        items: Q.inhouse.map(d => ({ label: d.client, value: d.spend || 0,
          note: moveNote(d), extra: d })),
        fmt: "$", labelW: 185, rowH: 27, width: 480, color: SLOT[2],
        valueName: "client canonical spend, " + TQ,
        onClick: d => showSwap(d)
      });
      div("sub", right, "Biggest firm-to-firm swappers (top " + Q.swapsTop.length + " of " + fmtNum(Q.nSwapClients) + " clients)");
      hbars(div(null, right), {
        items: Q.swapsTop.map(d => ({ label: d.client, value: d.spend || 0,
          note: moveNote(d), extra: d })),
        fmt: "$", labelW: 185, rowH: 27, width: 480, color: SLOT[0],
        valueName: "client canonical spend, " + TQ,
        onClick: d => showSwap(d)
      });
      tableView(cardEl, ["Client", "Old firm", "New firm", "Move", "Hire Δq", "Client spend " + TQ],
        Q.swapsTable.map(d => [d.client, d.old_firm, d.new_firm, d.move, d.dq, d.spend]),
        ["s", "s", "s", "s", "#", "$"]);
    }

    /* Firm churn scoreboard */
    {
      const { box, cardEl } = card(host, "The firm scoreboard — who bled clients, who signed them",
        "Registrants ranked by gross churn in " + TQ + ": engagements lost (a declared termination) vs new engagements signed (first-ever filing).",
        "Both bars count client entities, not dollars — the tooltip carries the trailing income the lost engagements were paying. A firm high on BOTH bars is running normal portfolio turnover; lopsided bars are the story (a book walking out, or a signing spree). Full scoreboard (" + fmtNum(Q.nFirms) + " firms): data/turnover_" + TQ.replace("-", "") + "_firm_churn.csv.");
      moreOptions(cardEl, QI.churn);
      const lg = legend(cardEl, [
        { name: "Engagements lost (terminated)", color: SLOT[2] },
        { name: "New engagements signed", color: SLOT[0] }
      ]);
      cardEl.insertBefore(lg, box);
      const cPanel = recPanel(cardEl, box,
        "Click a firm to list the clients behind both bars — every row links to its filing.");
      groupedHBars(box, {
        items: Q.churn.map(d => ({ label: d.name, a: d.lost, b: d.signed })),
        aName: "engagements lost", bName: "new engagements signed",
        aColor: SLOT[2], bColor: SLOT[0], labelW: 300, fmt: "#",
        onClick: (d, i) => {
          const e = Q.churn[i];
          const lists = (Q.churnClients && Q.churnClients[e.name]) || { lost: [], signed: [] };
          cPanel.show(
            e.name + " — lost " + fmtNum(e.lost) + " (trailing income " + fmtMoney(e.lost4) + ") · signed " + fmtNum(e.signed),
            "Lists reconcile with the scoreboard counts at export. Full per-firm lists: data/turnover_" + TQ.replace("-", "") + "_churn_clients.csv.",
            [["Lost (" + lists.lost.length + ")", lists.lost.map(r => ({ href: LDA_F(r[0]), text: r[1],
                tail: r[2] != null ? " · " + fmtMoney(r[2]) + " trailing" : "" }))],
             ["Signed (" + lists.signed.length + ")", lists.signed.map(r => ({ href: LDA_F(r[0]), text: r[1],
                tail: r[2] != null ? " · " + fmtMoney(r[2]) : " · registration only" }))]]);
        }
      });
      tableView(cardEl, ["Registrant", "Lost", "Lost trailing-4q income", "Signed", "Net"],
        Q.churn.map(d => [d.name, d.lost, d.lost4, d.signed, d.net]), ["s", "#", "$", "#", "#"]);
    }
  }

  /* Candidate lead the lens surfaced (quarter-independent; spans 2025-Q3–2026-Q1) */
  {
    const c = div("card", app);
    const h = document.createElement("h2");
    h.textContent = "What the lens surfaced — individuals paying six figures to seek pardons (candidate lead L034, unverified)";
    c.appendChild(h);
    div("sub", c, "The termination lens crossed with individual-as-client filings: three people paying $600K–$960K for engagements whose own free-text says what they're for — and whose termination filings mark the engagements closing (two of them in 2026-Q1). Unverified team-review material: whether the asks landed (and when, vs the termination quarters) is the open verification step in the ledger.");
    const ul = document.createElement("ul");
    ul.className = "filings-list";
    for (const r of DATA.pardon) {
      const li = document.createElement("li");
      const a = document.createElement("a");
      a.href = LDA_F(r.uuid); a.target = "_blank"; a.rel = "noopener";
      a.textContent = r.text;
      li.appendChild(a);
      li.appendChild(document.createTextNode(" · " + r.tail));
      ul.appendChild(li);
    }
    c.appendChild(ul);
    div("foot", c, "Quoted phrases are the filings' own activity descriptions. Living persons with active clemency asks — editorial/legal-sensitivity review required before any use beyond team triage (LEDGER L034; same flag as L021). The full clemency-lobbying map is its own package: out/packages/pardons/.");
  }

  const cavHost = div(null, app);   // per-quarter caveats, refreshed by renderQuarter

  /* initial quarter: URL hash if valid, else the newest exported quarter */
  const fromHash = decodeURIComponent((location.hash || "").slice(1));
  select(DATA.order.includes(fromHash) ? fromHash : DATA.default);
})();
