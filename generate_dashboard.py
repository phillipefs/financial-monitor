"""
generate_dashboard.py — Gera dashboard.html V2 (Financial Terminal)
Uso: py generate_dashboard.py
Saída: dashboard.html (abrir no browser)
"""
from __future__ import annotations

import os
import sys
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Dict

import urllib3
import pandas as pd

# Desabilita warnings de SSL (proxy corporativo)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
os.environ.setdefault("CURL_CA_BUNDLE", "")

# Importa lógica existente
from finance_stocks import collect_rsi_data
from onchain import (
    classify_mvrv_btc,
    classify_mvrv_eth,
    coinmetrics_price_realized_mvrv,
)

OUTPUT_FILE = Path(__file__).parent / "dashboard.html"

# Ordem dos setores
GROUP_ORDER = ["Indices", "Cripto", "EUA", "Brasil", "Moeda"]
GROUP_TITLES = {
    "Indices": "Índices Globais",
    "Cripto": "Criptomoedas",
    "EUA": "Mercado Americano",
    "Brasil": "Mercado Brasileiro",
    "Moeda": "Câmbio",
}
GROUP_ICONS = {
    "Indices": "📌",
    "Cripto": "🪙",
    "EUA": "🇺🇸",
    "Brasil": "🇧🇷",
    "Moeda": "💱",
}
SIGNAL_ORDER = ["UltraBuy", "Buy", "Neutral", "Sell"]


# ==============================================================
# DATA FETCHING
# ==============================================================
def fetch_rsi_data() -> pd.DataFrame:
    """Busca RSI semanal/mensal para todos os ativos e retorna DataFrame."""
    return collect_rsi_data(remove_crypto_suffix=True)


def fetch_onchain_data() -> Dict:
    """Busca MVRV on-chain para BTC e ETH."""
    data = {}
    for coin, classifier in [("BTC", classify_mvrv_btc), ("ETH", classify_mvrv_eth)]:
        try:
            price, realized, mvrv, cap, sply = coinmetrics_price_realized_mvrv(
                coin.lower(),
                verify_ssl=False,
            )
            cls = classifier(mvrv)
            data[coin] = {
                "price": price,
                "realized": realized,
                "mvrv": mvrv,
                "cap": cap,
                "supply": sply,
                "pct_above": (mvrv - 1.0) * 100.0,
                "zone": cls["zone"],
                "opportunity": cls["opportunity"],
                "risk": cls["risk"],
                "action": cls["action"],
            }
        except Exception as e:
            print(f"  [WARN] On-chain {coin}: {e}")
            data[coin] = None

    return data


# ==============================================================
# HTML GENERATION — V2 Professional Financial Terminal
# ==============================================================
def _signal_class(signal: str) -> str:
    return {"UltraBuy": "sig-ultrabuy", "Buy": "sig-buy", "Neutral": "sig-neutral", "Sell": "sig-sell"}.get(signal, "sig-neutral")


def _signal_label(signal: str) -> str:
    return {"UltraBuy": "ULTRA BUY", "Buy": "BUY", "Neutral": "NEUTRAL", "Sell": "SELL"}.get(signal, signal)


def _zone_class(zone: str) -> str:
    z = zone.lower()
    if any(w in z for w in ("capitulation", "historic", "deep value", "buy")):
        return "zone-buy"
    if any(w in z for w in ("value", "fair", "neutral")):
        return "zone-neutral"
    if any(w in z for w in ("premium", "high risk", "overheated")):
        return "zone-warn"
    if any(w in z for w in ("euphoria", "top")):
        return "zone-danger"
    return "zone-neutral"


def _format_price(val: float) -> str:
    if val >= 1000:
        return f"{val:,.0f}"
    if val >= 1:
        return f"{val:,.2f}"
    return f"{val:,.4f}"


def _mvrv_gauge_svg(mvrv: float, coin: str) -> str:
    """SVG semicircular gauge for MVRV."""
    if coin == "BTC":
        pct = max(0, min(100, (mvrv - 0.5) / 3.0 * 100))
    else:
        pct = max(0, min(100, (mvrv - 0.4) / 2.3 * 100))

    # Arc calculation (180 degrees)
    angle = 180 * (pct / 100)
    # Colors based on position
    if pct < 25:
        color = "#4ade80"
    elif pct < 50:
        color = "#33c6b7"
    elif pct < 75:
        color = "#ffc94d"
    else:
        color = "#f87171"

    # SVG arc path
    import math
    cx, cy, r = 60, 60, 50
    start_angle = math.radians(180)
    end_angle = math.radians(180 + angle)
    x1 = cx + r * math.cos(start_angle)
    y1 = cy + r * math.sin(start_angle)
    x2 = cx + r * math.cos(end_angle)
    y2 = cy + r * math.sin(end_angle)
    large_arc = 1 if angle > 180 else 0

    return f'''<svg viewBox="0 0 120 70" class="gauge-svg">
      <path d="M 10 60 A 50 50 0 0 1 110 60" fill="none" stroke="#2c3650" stroke-width="8" stroke-linecap="round"/>
      <path d="M {x1:.1f} {y1:.1f} A 50 50 0 {large_arc} 1 {x2:.1f} {y2:.1f}" fill="none" stroke="{color}" stroke-width="8" stroke-linecap="round"/>
      <text x="60" y="58" text-anchor="middle" fill="{color}" font-size="14" font-weight="800" font-family="monospace">{mvrv:.3f}</text>
    </svg>'''


def _build_onchain_card(coin: str, data: Dict) -> str:
    if data is None:
        return f'''
        <div class="oc-card oc-unavailable">
          <div class="oc-card-head"><span class="oc-icon">{"₿" if coin == "BTC" else "Ξ"}</span><span class="oc-title">{coin}</span></div>
          <p class="oc-na">Dados indisponíveis — execute fora da rede corporativa</p>
        </div>'''

    zone_cls = _zone_class(data["zone"])
    gauge = _mvrv_gauge_svg(data["mvrv"], coin)
    pct_sign = "+" if data["pct_above"] >= 0 else ""
    pct_cls = "pos" if data["pct_above"] >= 0 else "neg"

    return f'''
    <div class="oc-card">
      <div class="oc-card-head">
        <span class="oc-icon">{"₿" if coin == "BTC" else "Ξ"}</span>
        <span class="oc-title">{coin}</span>
        <span class="badge-zone {zone_cls}">{escape(data["zone"])}</span>
      </div>
      <div class="oc-body">
        <div class="oc-gauge">{gauge}</div>
        <div class="oc-metrics">
          <div class="oc-row"><span class="oc-k">Price</span><span class="oc-v">${_format_price(data["price"])}</span></div>
          <div class="oc-row"><span class="oc-k">Realized</span><span class="oc-v">${_format_price(data["realized"])}</span></div>
          <div class="oc-row"><span class="oc-k">MVRV</span><span class="oc-v oc-highlight">{data["mvrv"]:.4f}</span></div>
          <div class="oc-row"><span class="oc-k">vs Realized</span><span class="oc-v {pct_cls}">{pct_sign}{data["pct_above"]:.1f}%</span></div>
        </div>
      </div>
      <div class="oc-footer">
        <span class="oc-action-label">Ação:</span>
        <span class="oc-action-val">{escape(data["action"])}</span>
        <span class="oc-risk-pill">Risk: {escape(data["risk"])}</span>
      </div>
    </div>'''


def _build_sector_rows(df_sector: pd.DataFrame) -> str:
    rows_html = ""
    for sig in SIGNAL_ORDER:
        sub = df_sector[df_sector["Signal"] == sig].copy()
        if sub.empty:
            continue
        if sig in ["UltraBuy", "Buy"]:
            sub = sub.sort_values(["Weekly_RSI", "Monthly_RSI"], ascending=[True, True])
        elif sig == "Sell":
            sub = sub.sort_values(["Weekly_RSI", "Monthly_RSI"], ascending=[False, False])
        else:
            sub = sub.sort_values(["Weekly_RSI", "Monthly_RSI"], ascending=[True, True])

        for _, r in sub.iterrows():
            sig_cls = _signal_class(r["Signal"])
            sig_lbl = _signal_label(r["Signal"])
            rsi_w = int(r["Weekly_RSI"])
            rsi_m = int(r["Monthly_RSI"])
            rows_html += f'''
            <tr class="asset-row" data-signal="{r['Signal']}" data-ticker="{escape(str(r['Ticker']).lower())}" data-name="{escape(str(r['Name']).lower())}">
              <td class="col-tk"><span class="tk-badge">{escape(str(r['Ticker']))}</span></td>
              <td class="col-name">{escape(str(r['Name']))}</td>
              <td class="col-price">{_format_price(r['Weekly_Close'])}</td>
              <td class="col-rsi"><span class="rsi-pill" data-rsi="{rsi_w}">{rsi_w}</span></td>
              <td class="col-rsi"><span class="rsi-pill" data-rsi="{rsi_m}">{rsi_m}</span></td>
              <td class="col-sig"><span class="signal-badge {sig_cls}">{sig_lbl}</span></td>
            </tr>'''
    return rows_html


def generate_html(df: pd.DataFrame, onchain: Dict) -> str:
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    counts = df["Signal"].value_counts().to_dict()
    total = len(df)
    ub = counts.get("UltraBuy", 0)
    b = counts.get("Buy", 0)
    n = counts.get("Neutral", 0)
    s = counts.get("Sell", 0)

    # Build on-chain section
    btc_card = _build_onchain_card("BTC", onchain.get("BTC")) if onchain else ""
    eth_card = _build_onchain_card("ETH", onchain.get("ETH")) if onchain else ""

    # Build sector nav tabs + table content
    sector_tabs = ""
    sector_panels = ""
    first = True
    for grupo in GROUP_ORDER:
        sub = df[df["Setor"] == grupo]
        if sub.empty:
            continue
        title = GROUP_TITLES.get(grupo, grupo)
        icon = GROUP_ICONS.get(grupo, "")
        active_cls = "active" if first else ""
        cnt = len(sub)

        # Tab counts by signal
        s_counts = sub["Signal"].value_counts().to_dict()
        tab_info = ""
        if s_counts.get("UltraBuy", 0) + s_counts.get("Buy", 0) > 0:
            tab_info += f'<span class="tab-dot dot-green"></span>'
        if s_counts.get("Sell", 0) > 0:
            tab_info += f'<span class="tab-dot dot-red"></span>'

        sector_tabs += f'''<button class="sector-tab {active_cls}" data-panel="{grupo.lower()}">{icon} {title} <span class="tab-count">{cnt}</span>{tab_info}</button>'''

        rows = _build_sector_rows(sub)
        sector_panels += f'''
      <div class="sector-panel {"active" if first else ""}" id="panel-{grupo.lower()}">
        <div class="panel-summary">
          <span class="ps-item ps-green">{s_counts.get("UltraBuy", 0) + s_counts.get("Buy", 0)} oportunidades</span>
          <span class="ps-item ps-blue">{s_counts.get("Neutral", 0)} neutros</span>
          <span class="ps-item ps-red">{s_counts.get("Sell", 0)} sobrecomprados</span>
        </div>
        <div class="table-wrap">
          <table class="t-assets">
            <thead>
              <tr>
                <th class="th-sort" data-col="0">Ticker</th>
                <th class="th-sort" data-col="1">Nome</th>
                <th class="th-sort th-r" data-col="2">Preço</th>
                <th class="th-sort th-r" data-col="3">RSI W</th>
                <th class="th-sort th-r" data-col="4">RSI M</th>
                <th>Sinal</th>
              </tr>
            </thead>
            <tbody>{rows}
            </tbody>
          </table>
        </div>
      </div>'''
        first = False

    # Build full page
    return f'''<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Financial Monitor — Pro Dashboard</title>
<style>
/* ===== DESIGN TOKENS ===== */
:root{{
  --bg:#0a0e14;--bg2:#111827;--card:#151d2e;--card2:#1e293b;
  --orange:#ff5f46;--teal:#22d3ee;--purple:#a78bfa;--yellow:#fbbf24;
  --green:#34d399;--red:#f87171;--blue:#60a5fa;--pink:#f472b6;
  --txt:#f1f5f9;--muted:#94a3b8;--dim:#64748b;--line:#1e293b;
  --glow-teal:rgba(34,211,238,.12);--glow-green:rgba(52,211,153,.1);
  --radius:12px;--radius-sm:8px;--radius-xs:6px;
  --font:'Inter','Segoe UI',system-ui,-apple-system,sans-serif;
  --mono:'JetBrains Mono','Cascadia Code','Fira Code',monospace;
}}
*{{box-sizing:border-box;margin:0;padding:0}}
html{{scroll-behavior:smooth}}
body{{font-family:var(--font);background:var(--bg);color:var(--txt);line-height:1.5;-webkit-font-smoothing:antialiased;min-height:100vh}}

/* ===== TOPBAR ===== */
.topbar{{display:flex;align-items:center;padding:14px 24px;background:var(--bg2);border-bottom:1px solid var(--line);position:sticky;top:0;z-index:100;backdrop-filter:blur(12px);gap:16px;flex-wrap:wrap}}
.topbar-brand{{display:flex;align-items:center;gap:10px}}
.brand-dot{{width:10px;height:10px;border-radius:50%;background:var(--teal);animation:blink 2s infinite}}
@keyframes blink{{0%,100%{{opacity:1}}50%{{opacity:.4}}}}
.brand-name{{font-size:1.05rem;font-weight:800;letter-spacing:-.3px}}
.brand-tag{{font-size:.65rem;background:var(--card2);border:1px solid var(--line);padding:2px 8px;border-radius:12px;color:var(--teal);font-weight:700;letter-spacing:.5px;text-transform:uppercase}}
.topbar-meta{{margin-left:auto;display:flex;align-items:center;gap:14px;font-size:.78rem;color:var(--muted)}}
.topbar-meta time{{color:var(--teal);font-weight:700;font-family:var(--mono)}}

/* ===== SEARCH ===== */
.search-wrap{{flex:0 0 260px;position:relative}}
.search-input{{width:100%;background:var(--bg);border:1px solid var(--line);border-radius:20px;padding:8px 14px 8px 36px;color:var(--txt);font-size:.82rem;outline:none;transition:.25s}}
.search-input:focus{{border-color:var(--teal);box-shadow:0 0 0 3px var(--glow-teal)}}
.search-icon{{position:absolute;left:12px;top:50%;transform:translateY(-50%);color:var(--dim);font-size:.85rem;pointer-events:none}}

/* ===== KPI STRIP ===== */
.kpi-strip{{display:flex;gap:1px;background:var(--line);margin:0;overflow-x:auto}}
.kpi-cell{{flex:1;min-width:120px;background:var(--bg2);padding:16px 20px;text-align:center;transition:.2s}}
.kpi-cell:hover{{background:var(--card)}}
.kpi-num{{font-size:1.7rem;font-weight:800;line-height:1;font-family:var(--mono)}}
.kpi-label{{font-size:.68rem;color:var(--muted);text-transform:uppercase;letter-spacing:.8px;margin-top:5px;font-weight:600}}

/* ===== MAIN LAYOUT ===== */
.main{{max-width:1280px;margin:0 auto;padding:28px 24px}}
.section-title{{font-size:1.3rem;font-weight:800;margin-bottom:16px;display:flex;align-items:center;gap:10px}}
.section-title::before{{content:'';width:4px;height:22px;border-radius:4px;background:linear-gradient(180deg,var(--teal),var(--blue))}}

/* ===== ON-CHAIN GRID ===== */
.oc-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(360px,1fr));gap:20px;margin-bottom:40px}}
.oc-card{{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);padding:24px;transition:.3s}}
.oc-card:hover{{border-color:var(--teal);box-shadow:0 8px 32px rgba(0,0,0,.4),0 0 0 1px var(--glow-teal)}}
.oc-unavailable{{opacity:.6}}
.oc-na{{color:var(--dim);font-size:.85rem;margin-top:12px}}
.oc-card-head{{display:flex;align-items:center;gap:10px;margin-bottom:16px}}
.oc-icon{{font-size:1.6rem}}
.oc-title{{font-size:1.15rem;font-weight:800}}
.oc-body{{display:flex;align-items:center;gap:20px}}
.oc-gauge{{flex:0 0 120px}}
.gauge-svg{{width:100%;height:auto}}
.oc-metrics{{flex:1;display:flex;flex-direction:column;gap:8px}}
.oc-row{{display:flex;justify-content:space-between;align-items:center;padding:4px 0;border-bottom:1px solid rgba(30,41,59,.6)}}
.oc-row:last-child{{border:none}}
.oc-k{{font-size:.75rem;color:var(--muted);text-transform:uppercase;letter-spacing:.4px;font-weight:600}}
.oc-v{{font-size:.95rem;font-weight:700;font-family:var(--mono)}}
.oc-highlight{{color:var(--yellow);font-size:1.05rem}}
.pos{{color:var(--green)}}
.neg{{color:var(--red)}}
.oc-footer{{display:flex;align-items:center;gap:12px;margin-top:16px;padding-top:14px;border-top:1px solid var(--line);flex-wrap:wrap}}
.oc-action-label{{font-size:.72rem;color:var(--muted);font-weight:700;text-transform:uppercase}}
.oc-action-val{{font-size:.92rem;font-weight:800;color:var(--txt)}}
.oc-risk-pill{{margin-left:auto;font-size:.68rem;font-weight:700;padding:4px 12px;border-radius:20px;background:rgba(148,163,184,.1);border:1px solid var(--line);color:var(--muted)}}

/* ZONE BADGES */
.badge-zone{{font-size:.65rem;font-weight:800;padding:4px 10px;border-radius:14px;letter-spacing:.3px;text-transform:uppercase}}
.zone-buy{{background:rgba(52,211,153,.12);color:var(--green);border:1px solid rgba(52,211,153,.35)}}
.zone-neutral{{background:rgba(96,165,250,.1);color:var(--blue);border:1px solid rgba(96,165,250,.3)}}
.zone-warn{{background:rgba(251,191,36,.1);color:var(--yellow);border:1px solid rgba(251,191,36,.3)}}
.zone-danger{{background:rgba(248,113,113,.1);color:var(--red);border:1px solid rgba(248,113,113,.35)}}

/* ===== SECTOR TABS ===== */
.sector-nav{{display:flex;gap:6px;overflow-x:auto;padding-bottom:2px;margin-bottom:20px;border-bottom:1px solid var(--line)}}
.sector-tab{{background:none;border:none;color:var(--muted);padding:10px 16px;font-size:.82rem;font-weight:600;cursor:pointer;border-bottom:2px solid transparent;transition:.25s;white-space:nowrap;display:flex;align-items:center;gap:6px}}
.sector-tab:hover{{color:var(--txt);background:var(--card)}}
.sector-tab.active{{color:var(--teal);border-bottom-color:var(--teal)}}
.tab-count{{font-size:.65rem;background:var(--card2);border:1px solid var(--line);padding:1px 7px;border-radius:10px;font-family:var(--mono);font-weight:700}}
.tab-dot{{width:6px;height:6px;border-radius:50%;display:inline-block}}
.dot-green{{background:var(--green)}}
.dot-red{{background:var(--red)}}

/* ===== SECTOR PANELS ===== */
.sector-panel{{display:none;animation:fadeUp .35s ease}}
.sector-panel.active{{display:block}}
@keyframes fadeUp{{from{{opacity:0;transform:translateY(12px)}}to{{opacity:1;transform:none}}}}
.panel-summary{{display:flex;gap:16px;margin-bottom:14px;flex-wrap:wrap}}
.ps-item{{font-size:.76rem;font-weight:700;padding:5px 14px;border-radius:20px;background:var(--card2);border:1px solid var(--line)}}
.ps-green{{color:var(--green)}}
.ps-blue{{color:var(--blue)}}
.ps-red{{color:var(--red)}}

/* ===== TABLE ===== */
.table-wrap{{border-radius:var(--radius);border:1px solid var(--line);overflow:hidden;background:var(--card)}}
.t-assets{{width:100%;border-collapse:collapse;font-size:.84rem}}
.t-assets thead{{background:var(--bg2)}}
.t-assets th{{padding:11px 14px;text-align:left;font-size:.68rem;letter-spacing:.6px;text-transform:uppercase;color:var(--dim);font-weight:700;border-bottom:1px solid var(--line);user-select:none;white-space:nowrap}}
.th-sort{{cursor:pointer;transition:.2s}}
.th-sort:hover{{color:var(--teal)}}
.th-sort::after{{content:'⇅';margin-left:4px;opacity:.4;font-size:.7rem}}
.th-sort.asc::after{{content:'↑';opacity:1;color:var(--teal)}}
.th-sort.desc::after{{content:'↓';opacity:1;color:var(--teal)}}
.th-r{{text-align:right}}
.t-assets td{{padding:10px 14px;border-bottom:1px solid rgba(30,41,59,.5);transition:.15s}}
.t-assets tbody tr{{transition:.15s}}
.t-assets tbody tr:hover td{{background:rgba(34,211,238,.04)}}
.t-assets tbody tr:last-child td{{border-bottom:none}}
.col-tk{{width:90px}}
.tk-badge{{font-family:var(--mono);font-size:.78rem;font-weight:700;background:var(--bg);padding:3px 8px;border-radius:var(--radius-xs);border:1px solid var(--line)}}
.col-name{{color:var(--muted);font-size:.82rem}}
.col-price{{text-align:right;font-family:var(--mono);font-weight:600}}
.col-rsi{{text-align:right}}
.col-sig{{text-align:center}}

/* RSI PILLS */
.rsi-pill{{display:inline-block;font-family:var(--mono);font-size:.78rem;font-weight:700;padding:3px 10px;border-radius:var(--radius-xs);min-width:36px;text-align:center}}

/* SIGNAL BADGES */
.signal-badge{{display:inline-block;font-size:.64rem;font-weight:800;padding:4px 11px;border-radius:14px;letter-spacing:.4px;white-space:nowrap}}
.sig-ultrabuy{{background:rgba(52,211,153,.15);color:var(--green);border:1px solid rgba(52,211,153,.45);box-shadow:0 0 8px rgba(52,211,153,.15)}}
.sig-buy{{background:rgba(52,211,153,.08);color:var(--green);border:1px solid rgba(52,211,153,.3)}}
.sig-neutral{{background:rgba(96,165,250,.08);color:var(--blue);border:1px solid rgba(96,165,250,.25)}}
.sig-sell{{background:rgba(248,113,113,.1);color:var(--red);border:1px solid rgba(248,113,113,.35)}}

/* ===== SIGNAL FILTER BAR ===== */
.filter-strip{{display:flex;align-items:center;gap:8px;margin-bottom:20px;flex-wrap:wrap}}
.filter-strip label{{font-size:.72rem;color:var(--dim);font-weight:700;text-transform:uppercase;letter-spacing:.5px}}
.fbtn{{background:var(--bg2);border:1px solid var(--line);color:var(--muted);padding:6px 14px;border-radius:16px;cursor:pointer;font-size:.76rem;font-weight:700;transition:.2s;font-family:var(--font)}}
.fbtn:hover{{border-color:var(--teal);color:var(--txt)}}
.fbtn.active{{background:var(--glow-teal);border-color:var(--teal);color:var(--teal)}}
.fbtn .fc{{font-family:var(--mono);margin-left:4px;opacity:.7}}

/* ===== FOOTER ===== */
.footer{{text-align:center;padding:32px 20px;font-size:.72rem;color:var(--dim);border-top:1px solid var(--line);margin-top:48px}}
.footer a{{color:var(--teal);text-decoration:none}}

/* ===== RESPONSIVE ===== */
@media(max-width:768px){{
  .topbar{{padding:10px 14px}}
  .search-wrap{{flex:1 1 100%;order:10;margin-top:8px}}
  .kpi-cell{{min-width:90px;padding:12px 10px}}
  .kpi-num{{font-size:1.3rem}}
  .main{{padding:20px 14px}}
  .oc-grid{{grid-template-columns:1fr}}
  .oc-body{{flex-direction:column;align-items:stretch}}
  .oc-gauge{{flex:0;display:flex;justify-content:center}}
  .sector-nav{{gap:2px}}
  .sector-tab{{padding:8px 10px;font-size:.75rem}}
  .t-assets{{font-size:.76rem}}
  .t-assets th,.t-assets td{{padding:8px 10px}}
  .filter-strip{{gap:5px}}
}}
@media(max-width:480px){{
  .kpi-strip{{flex-wrap:wrap}}
  .kpi-cell{{min-width:48%;flex:1 1 48%}}
  .col-name{{display:none}}
}}
</style>
</head>
<body>

<!-- TOPBAR -->
<div class="topbar">
  <div class="topbar-brand">
    <span class="brand-dot"></span>
    <span class="brand-name">Financial Monitor</span>
    <span class="brand-tag">Pro v2</span>
  </div>
  <div class="search-wrap">
    <span class="search-icon">&#128269;</span>
    <input type="text" class="search-input" id="globalSearch" placeholder="Buscar ativo... (ticker ou nome)" autocomplete="off"/>
  </div>
  <div class="topbar-meta">
    <span>Atualizado</span>
    <time>{now}</time>
  </div>
</div>

<!-- KPI STRIP -->
<div class="kpi-strip">
  <div class="kpi-cell"><div class="kpi-num" style="color:var(--teal)">{total}</div><div class="kpi-label">Ativos</div></div>
  <div class="kpi-cell"><div class="kpi-num" style="color:var(--green)">{ub}</div><div class="kpi-label">Ultra Buy</div></div>
  <div class="kpi-cell"><div class="kpi-num" style="color:var(--green)">{b}</div><div class="kpi-label">Buy</div></div>
  <div class="kpi-cell"><div class="kpi-num" style="color:var(--blue)">{n}</div><div class="kpi-label">Neutral</div></div>
  <div class="kpi-cell"><div class="kpi-num" style="color:var(--red)">{s}</div><div class="kpi-label">Sell</div></div>
</div>

<div class="main">

  <!-- ON-CHAIN -->
  <h2 class="section-title">On-Chain Analytics</h2>
  <div class="oc-grid">
    {btc_card}
    {eth_card}
  </div>

  <!-- RSI MONITOR -->
  <h2 class="section-title">RSI Monitor</h2>

  <!-- Filter -->
  <div class="filter-strip">
    <label>Sinal:</label>
    <button class="fbtn active" data-filter="all">Todos <span class="fc">{total}</span></button>
    <button class="fbtn" data-filter="UltraBuy">Ultra Buy <span class="fc">{ub}</span></button>
    <button class="fbtn" data-filter="Buy">Buy <span class="fc">{b}</span></button>
    <button class="fbtn" data-filter="Neutral">Neutral <span class="fc">{n}</span></button>
    <button class="fbtn" data-filter="Sell">Sell <span class="fc">{s}</span></button>
  </div>

  <!-- Sector Tabs -->
  <div class="sector-nav">{sector_tabs}</div>

  <!-- Panels -->
  {sector_panels}

</div>

<div class="footer">
  Financial Monitor Pro v2.0 · Gerado em <a>{now}</a> · Dados: Yahoo Finance + CoinMetrics · Self-hosted
</div>

<script>
(function(){{
  "use strict";

  // === SECTOR TABS ===
  const tabs = document.querySelectorAll('.sector-tab');
  const panels = document.querySelectorAll('.sector-panel');
  tabs.forEach(tab => {{
    tab.addEventListener('click', () => {{
      tabs.forEach(t => t.classList.remove('active'));
      panels.forEach(p => p.classList.remove('active'));
      tab.classList.add('active');
      const panel = document.getElementById('panel-' + tab.dataset.panel);
      if(panel) panel.classList.add('active');
    }});
  }});

  // === SIGNAL FILTER ===
  const fbtns = document.querySelectorAll('.fbtn[data-filter]');
  fbtns.forEach(btn => {{
    btn.addEventListener('click', () => {{
      fbtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const f = btn.dataset.filter;
      document.querySelectorAll('.asset-row').forEach(row => {{
        row.style.display = (f === 'all' || row.dataset.signal === f) ? '' : 'none';
      }});
    }});
  }});

  // === GLOBAL SEARCH ===
  const searchInput = document.getElementById('globalSearch');
  searchInput.addEventListener('input', () => {{
    const q = searchInput.value.toLowerCase().trim();
    document.querySelectorAll('.asset-row').forEach(row => {{
      if(!q) {{ row.style.display = ''; return; }}
      const match = row.dataset.ticker.includes(q) || row.dataset.name.includes(q);
      row.style.display = match ? '' : 'none';
    }});
    // Show all panels during search
    if(q) {{
      panels.forEach(p => p.classList.add('active'));
      tabs.forEach(t => t.classList.add('active'));
    }} else {{
      // Restore tab state
      panels.forEach(p => p.classList.remove('active'));
      tabs.forEach(t => t.classList.remove('active'));
      const firstTab = tabs[0];
      if(firstTab) {{
        firstTab.classList.add('active');
        const fp = document.getElementById('panel-' + firstTab.dataset.panel);
        if(fp) fp.classList.add('active');
      }}
    }}
  }});

  // === TABLE SORT ===
  document.querySelectorAll('.th-sort').forEach(th => {{
    th.addEventListener('click', () => {{
      const table = th.closest('table');
      const tbody = table.querySelector('tbody');
      const col = parseInt(th.dataset.col);
      const rows = Array.from(tbody.querySelectorAll('tr'));
      const isAsc = th.classList.contains('asc');

      // Reset all sort indicators in this table
      th.closest('thead').querySelectorAll('.th-sort').forEach(h => {{
        h.classList.remove('asc','desc');
      }});

      th.classList.add(isAsc ? 'desc' : 'asc');
      const dir = isAsc ? -1 : 1;

      rows.sort((a, b) => {{
        let va = a.children[col]?.textContent.trim() || '';
        let vb = b.children[col]?.textContent.trim() || '';
        const na = parseFloat(va.replace(/[^0-9.\\-]/g, ''));
        const nb = parseFloat(vb.replace(/[^0-9.\\-]/g, ''));
        if(!isNaN(na) && !isNaN(nb)) return (na - nb) * dir;
        return va.localeCompare(vb) * dir;
      }});

      rows.forEach(r => tbody.appendChild(r));
    }});
  }});

  // === RSI PILL COLORING ===
  document.querySelectorAll('.rsi-pill').forEach(pill => {{
    const v = parseInt(pill.dataset.rsi);
    if(v <= 30) {{ pill.style.background = 'rgba(52,211,153,.15)'; pill.style.color = '#34d399'; pill.style.border = '1px solid rgba(52,211,153,.3)'; }}
    else if(v <= 40) {{ pill.style.background = 'rgba(34,211,238,.1)'; pill.style.color = '#22d3ee'; pill.style.border = '1px solid rgba(34,211,238,.25)'; }}
    else if(v >= 70) {{ pill.style.background = 'rgba(248,113,113,.12)'; pill.style.color = '#f87171'; pill.style.border = '1px solid rgba(248,113,113,.3)'; }}
    else if(v >= 60) {{ pill.style.background = 'rgba(251,191,36,.1)'; pill.style.color = '#fbbf24'; pill.style.border = '1px solid rgba(251,191,36,.25)'; }}
    else {{ pill.style.background = 'var(--bg)'; pill.style.color = 'var(--muted)'; pill.style.border = '1px solid var(--line)'; }}
  }});

  // === KEYBOARD SHORTCUT (/ to focus search) ===
  document.addEventListener('keydown', (e) => {{
    if(e.key === '/' && document.activeElement !== searchInput) {{
      e.preventDefault();
      searchInput.focus();
    }}
    if(e.key === 'Escape') {{
      searchInput.value = '';
      searchInput.dispatchEvent(new Event('input'));
      searchInput.blur();
    }}
  }});

}})();
</script>
</body>
</html>'''


# ==============================================================
# MAIN
# ==============================================================
def main():
    print("=" * 60)
    print("  FINANCIAL MONITOR PRO — Dashboard V2 Generator")
    print("=" * 60)

    print("\n[1/3] Buscando dados On-Chain (BTC + ETH)...")
    onchain = fetch_onchain_data()

    print("[2/3] Buscando RSI para todos os ativos...")
    df = fetch_rsi_data()

    if df.empty:
        print("  [ERRO] Nenhum dado retornado. Verifique conexão ou yfinance.")
        sys.exit(1)

    print(f"  [OK] {len(df)} ativos processados")

    print("[3/3] Gerando dashboard HTML...")
    html = generate_html(df, onchain)
    OUTPUT_FILE.write_text(html, encoding="utf-8")
    print(f"  [OK] Salvo em: {OUTPUT_FILE}")
    print(f"\n  Abra no browser: file:///{OUTPUT_FILE.as_posix()}")
    print("=" * 60)


if __name__ == "__main__":
    main()
