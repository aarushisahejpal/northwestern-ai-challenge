/* codes_page.js — generic issue_codes-lens dashboard for industry-review-packager.
   All card copy comes from DATA.copy (carried by the package spec); every widget
   renders only if its data is present. Widgets: KPI tiles, player spend×activity-
   share scatter, quarterly trend, per-code trend, registrant firms, bills,
   press-coupling (say vs pay), LD-203 giving (optional), caveats.

   Unlike the facet page (or the legacy bespoke healthcare/crypto builds), this
   generic page has NO per-filing click-through: this lens's exporter never
   produces the click-through indices (player_filings/trend_filings/press_releases)
   that back facet-lens click-through, so every widget here is a reconciled
   aggregate chart + table view only — same as the facet page's own registrants/
   keywords/giving widgets, which also ship without click-through. */
(function () {
  const app = document.getElementById("app");
  const QI = DATA.queryInfo || {};
  const C = DATA.copy || {};
  const W = (k) => C[k] || {};   // per-widget card copy from the spec
  moreOptions(statTiles(app, DATA.kpis), QI.kpis);

  /* Players — spend × activity-share scatter (log-x spend, y = share of the
     client's own senate activity tagged to this industry's codes). Size =
     tagged filings. A reduced, legible SELECTION drives the chart (top-150-by-
     filings ∪ top-30-by-spend, marked `inScatter` at export time); the table
     below carries the FULL roster. */
  {
    const w = W("players");
    const sel = DATA.players.filter(p => p.inScatter && p.spend);
    const { box, cardEl } = card(app, w.title || "The player map — spend vs. activity share",
      (w.sub || "{n} players (of {total} total) selected for legibility — top 150 by tagged filings ∪ top 30 by all-issue spend. X = total federal lobbying spend (all issues, log scale); Y = share of the client's OWN senate activity tagged to this industry's issue codes; dot size = tagged filings.")
        .replace("{n}", fmtNum(sel.length)).replace("{total}", fmtNum(DATA.players.length)),
      w.foot || "");
    moreOptions(cardEl, QI.players);
    scatterXY(box, {
      items: sel.map(p => ({ label: p.name, short: p.short, x: p.spend, y: p.sharePct,
        size: p.filings, slot: 0, extra: p })),
      xFmt: "$", yMax: 100, labelTop: 12, labelTopY: 4, labelTopSize: 2,
      rules: [{ y: 25, label: "25%" }, { y: 5, label: "5%" }],
      ttRows: d => [
        { color: SLOT[0], value: fmtMoney(d.extra.spend), name: "total lobbying spend (all issues)" },
        { color: null, value: (d.extra.sharePct == null ? "–" : d.extra.sharePct + "%"), name: "share of activities tagged to this industry" },
        { color: null, value: fmtNum(d.extra.filings), name: "tagged senate filings" },
        { color: null, value: d.extra.y0 + "–" + d.extra.y1, name: "years active" }
      ]
    });
    tableView(cardEl, ["Player", "Tagged filings", "Activity share %", "Total spend (all issues)", "Years"],
      DATA.players.map(p => [p.name, p.filings, p.sharePct, p.spend, p.y0 + "–" + p.y1]),
      ["s", "#", "%", "$", "s"]);
  }

  /* Trend */
  {
    const w = W("trend");
    const { box, cardEl } = card(app, w.title || "Quarterly trend",
      w.sub || "Tagged senate filings and distinct clients per quarter (amendment-deduped, registrations excluded).",
      w.foot || "");
    moreOptions(cardEl, QI.trend);
    const lg = legend(cardEl, [{ name: "Tagged filings", color: SLOT[0] }, { name: "Distinct clients", color: SLOT[1] }], "line");
    cardEl.insertBefore(lg, box);
    linePanel(box, {
      x: DATA.trend.q, fmt: "#",
      series: [
        { name: "Tagged filings", values: DATA.trend.filings },
        { name: "Distinct clients", values: DATA.trend.clients }
      ]
    });
    tableView(cardEl, DATA.trend.spend ? ["Quarter", "Tagged filings", "Distinct clients", "Canonical spend of tagged clients"]
                                        : ["Quarter", "Tagged filings", "Distinct clients"],
      DATA.trend.q.map((q, i) => DATA.trend.spend
        ? [q, DATA.trend.filings[i], DATA.trend.clients[i], DATA.trend.spend[i]]
        : [q, DATA.trend.filings[i], DATA.trend.clients[i]]),
      DATA.trend.spend ? ["s", "#", "#", "$"] : ["s", "#", "#"]);
  }

  /* Per-code trend */
  {
    const w = W("codeTrend");
    const { box, cardEl } = card(app, w.title || "What kind of lobbying — per issue code",
      w.sub || "Tagged filings per quarter by ALI issue code (a filing can carry more than one).",
      w.foot || "");
    moreOptions(cardEl, QI.codeTrend);
    const series = DATA.codeTrend.series;
    const lg = legend(cardEl, series.map((s, i) => ({ name: s.code + " — " + s.name, color: SLOT[i % SLOT.length] })), "line");
    cardEl.insertBefore(lg, box);
    linePanel(box, {
      x: DATA.codeTrend.q, fmt: "#",
      series: series.map((s, i) => ({ name: s.code + " — " + s.name, values: s.values, color: SLOT[i % SLOT.length] }))
    });
    tableView(cardEl, ["Quarter"].concat(series.map(s => s.code)),
      DATA.codeTrend.q.map((q, i) => [q].concat(series.map(s => s.values[i]))),
      ["s"].concat(series.map(() => "#")));
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

  /* Bills (optional) */
  if (DATA.bills && DATA.bills.length) {
    const w = W("bills");
    const { box, cardEl } = card(app, w.title || "The bills the industry crowds onto",
      w.sub || "Bills most-named in tagged filings' free-text, ranked by distinct clients lobbying them.",
      w.foot || "");
    moreOptions(cardEl, QI.bills);
    hbars(box, {
      items: DATA.bills.slice(0, 15).map(d => ({ label: d.bill, value: d.clients, note: fmtNum(d.filings) + " filings" })),
      fmt: "#", labelW: 300, valueName: "distinct clients"
    });
    tableView(cardEl, ["Bill", "Distinct clients", "Filings", "First year", "Last year"],
      DATA.bills.map(d => [d.bill, d.clients, d.filings, d.y0, d.y1]), ["s", "#", "#", "s", "s"]);
  }

  /* Press coupling — say vs pay */
  {
    const w = W("press");
    const { box, cardEl } = card(app, w.title || "The say side — member press releases",
      w.sub || "Share of ALL member press releases tagged to this industry's issue codes, by quarter.",
      w.foot || "");
    moreOptions(cardEl, QI.press);
    linePanel(box, {
      x: DATA.press.q, fmt: "%",
      series: [{ name: "Share of member releases", values: DATA.press.share, color: SLOT[5] }],
      height: 210
    });
    tableView(cardEl, DATA.press.spend ? ["Quarter", "Tagged releases", "All releases", "Share %", "Canonical spend of tagged clients"]
                                        : ["Quarter", "Tagged releases", "All releases", "Share %"],
      DATA.press.q.map((q, i) => DATA.press.spend
        ? [q, DATA.press.n[i], DATA.press.all[i], DATA.press.share[i], DATA.press.spend[i]]
        : [q, DATA.press.n[i], DATA.press.all[i], DATA.press.share[i]]),
      DATA.press.spend ? ["s", "#", "#", "%", "$"] : ["s", "#", "#", "%"]);
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

  /* Caveats */
  {
    const c = div("card", app);
    const h = document.createElement("h2"); h.textContent = "How to read this (caveats that matter)"; c.appendChild(h);
    const ul = document.createElement("ul"); ul.className = "caveats"; c.appendChild(ul);
    DATA.caveats.forEach(t => { const li = document.createElement("li"); li.textContent = t; ul.appendChild(li); });
  }

  findingsCard(app, DATA.findings);
})();
