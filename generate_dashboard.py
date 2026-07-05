"""
generate_dashboard.py — Generates dashboard.html (Financial Monitor Research)
Usage: py generate_dashboard.py
Output: dashboard.html (open in browser)
"""
from __future__ import annotations

import json
import math
import os
import sys
from datetime import date, datetime, timedelta, timezone
from html import escape
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import quote
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import urllib3
import pandas as pd
import yfinance as yf

# Disable SSL warnings for corporate proxies.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
os.environ.setdefault("CURL_CA_BUNDLE", "")

# Reuse the existing data collection logic.
from finance_stocks import collect_rsi_data, _download_batch
from onchain import (
    classify_mvrv_btc,
    classify_mvrv_eth,
    coinmetrics_price_realized_mvrv,
    fear_greed_index,
)

OUTPUT_FILE = Path(__file__).parent / "dashboard.html"
SAO_PAULO_TZ = "America/Sao_Paulo"

# Display order for coverage groups.
GROUP_ORDER = ["Indices", "Cripto", "EUA", "ETF", "Commodities", "Brasil", "Moeda"]
GROUP_TITLES = {
    "Indices": "Global Indices",
    "Cripto": "Crypto Assets",
    "EUA": "U.S. Market",
    "ETF": "ETFs",
    "Commodities": "Commodities",
    "Brasil": "Brazilian Market",
    "Moeda": "Currency",
}
SIGNAL_ORDER = ["UltraBuy", "Buy", "Neutral", "Sell"]


def sao_paulo_now() -> datetime:
    """Return the current timestamp in Brasilia/Sao Paulo time."""
    try:
        tz = ZoneInfo(SAO_PAULO_TZ)
    except ZoneInfoNotFoundError:
        tz = timezone(timedelta(hours=-3), name="BRT")
    return datetime.now(tz)

RESEARCH_V2_CSS = """
/* ===== RESEARCH THEME OVERRIDES ===== */
:root{
  --rm-bg:#07090b;
  --rm-bg-soft:#0d1116;
  --rm-surface:#111820;
  --rm-surface-2:#151e28;
  --rm-surface-3:#1a2531;
  --rm-line:#263241;
  --rm-line-soft:rgba(145,163,182,.16);
  --rm-text:#eef3f7;
  --rm-muted:#9cabb9;
  --rm-dim:#647181;
  --rm-cyan:#43d7e8;
  --rm-green:#35d08f;
  --rm-yellow:#f1bc4b;
  --rm-red:#f06f68;
  --rm-blue:#6fa8ff;
  --rm-shadow:0 24px 70px rgba(0,0,0,.35);
  --radius:8px;
  --radius-sm:6px;
  --radius-xs:4px;
}

body.research-v2,
.research-v2 *{
  letter-spacing:0;
}

body.research-v2{
  background:
    linear-gradient(180deg,rgba(67,215,232,.06),transparent 260px),
    linear-gradient(90deg,rgba(255,255,255,.025) 1px,transparent 1px),
    linear-gradient(180deg,rgba(255,255,255,.02) 1px,transparent 1px),
    var(--rm-bg);
  background-size:auto,48px 48px,48px 48px,auto;
  color:var(--rm-text);
  font-family:"Segoe UI",Inter,system-ui,-apple-system,BlinkMacSystemFont,sans-serif;
}

.research-v2 .topbar{
  min-height:72px;
  padding:14px clamp(16px,3vw,34px);
  background:rgba(7,9,11,.88);
  border-bottom:1px solid var(--rm-line);
  box-shadow:0 18px 50px rgba(0,0,0,.28);
  backdrop-filter:blur(18px);
}

.research-v2 .topbar-brand{
  min-width:260px;
  gap:12px;
}

.research-v2 .brand-dot{
  width:34px;
  height:34px;
  border-radius:8px;
  background:
    linear-gradient(135deg,rgba(67,215,232,.95),rgba(53,208,143,.78)),
    var(--rm-cyan);
  box-shadow:0 0 0 1px rgba(255,255,255,.14) inset,0 12px 28px rgba(67,215,232,.18);
  animation:none;
  position:relative;
}

.research-v2 .brand-dot::after{
  content:"FM";
  position:absolute;
  inset:0;
  display:grid;
  place-items:center;
  color:#051013;
  font-size:.68rem;
  font-weight:900;
  font-family:var(--mono);
}

.research-v2 .brand-name{
  display:block;
  color:var(--rm-text);
  font-size:1rem;
  font-weight:800;
}

.research-v2 .search-wrap{
  flex:1 1 340px;
  max-width:520px;
}

.research-v2 .search-input{
  height:42px;
  border-radius:8px;
  border-color:var(--rm-line);
  background:rgba(17,24,32,.92);
  color:var(--rm-text);
  font-size:.9rem;
  box-shadow:0 0 0 1px rgba(255,255,255,.02) inset;
}

.research-v2 .search-input::placeholder{color:var(--rm-dim)}
.research-v2 .search-input:focus{
  border-color:rgba(67,215,232,.7);
  box-shadow:0 0 0 3px rgba(67,215,232,.12);
}

.research-v2 .search-icon{
  color:var(--rm-cyan);
  font-size:1rem;
}

.research-v2 .topbar-meta{
  gap:8px;
  padding:8px 12px;
  margin-left:auto;
  border:1px solid var(--rm-line);
  border-radius:8px;
  background:rgba(17,24,32,.7);
  color:var(--rm-muted);
}

.research-v2 .topbar-meta time{
  color:var(--rm-text);
  font-size:.82rem;
}

.research-v2 .executive-board{
  max-width:1440px;
  margin:0 auto;
  padding:34px clamp(16px,3vw,34px) 22px;
  display:grid;
  grid-template-columns:minmax(0,1fr) minmax(300px,360px);
  gap:22px;
  align-items:stretch;
}

.research-v2 .brief-copy{
  min-height:190px;
  padding:28px 30px;
  border:1px solid var(--rm-line);
  border-radius:8px;
  background:
    linear-gradient(135deg,rgba(67,215,232,.13),transparent 36%),
    linear-gradient(180deg,rgba(255,255,255,.045),rgba(255,255,255,.012)),
    var(--rm-surface);
  box-shadow:var(--rm-shadow);
}

.research-v2 .eyebrow{
  color:var(--rm-cyan);
  font-size:.78rem;
  font-weight:800;
  text-transform:uppercase;
  margin-bottom:16px;
}

.research-v2 .brief-copy h1{
  max-width:none;
  margin:0 0 16px;
  color:var(--rm-text);
  font-size:clamp(1.2rem,1.5vw,1.55rem);
  line-height:1.08;
  font-weight:850;
  white-space:nowrap;
}

.research-v2 .brief-copy p{
  max-width:760px;
  color:var(--rm-muted);
  font-size:1.02rem;
}

.research-v2 .market-read{
  height:100%;
  padding:20px 22px;
  border:1px solid var(--rm-line);
  border-radius:8px;
  background:rgba(17,24,32,.86);
  box-shadow:var(--rm-shadow);
}

.research-v2 .market-read h2{
  margin:0 0 18px;
  color:var(--rm-cyan);
  font-size:.78rem;
  font-weight:800;
  text-transform:uppercase;
}

.research-v2 .mix-row{
  display:grid;
  grid-template-columns:82px 38px 1fr;
  align-items:center;
  gap:10px;
  min-height:34px;
  color:var(--rm-muted);
  font-size:.82rem;
}

.research-v2 .mix-row strong{
  color:var(--rm-text);
  font-family:var(--mono);
  text-align:right;
}

.research-v2 .mix-bar{
  height:8px;
  overflow:hidden;
  border-radius:999px;
  background:rgba(255,255,255,.07);
}

.research-v2 .mix-bar span{
  display:block;
  width:var(--w);
  height:100%;
  border-radius:inherit;
  background:var(--c);
}

.research-v2 .kpi-strip{
  max-width:1440px;
  margin:0 auto;
  padding:0 clamp(16px,3vw,34px) 28px;
  gap:12px;
  background:transparent;
  overflow:visible;
}

.research-v2 .kpi-cell{
  min-width:150px;
  padding:18px;
  text-align:left;
  border:1px solid var(--rm-line);
  border-radius:8px;
  background:linear-gradient(180deg,rgba(255,255,255,.04),rgba(255,255,255,.015)),var(--rm-surface);
  transition:border-color .18s ease,transform .18s ease,background .18s ease;
}

.research-v2 .kpi-cell:hover{
  border-color:rgba(67,215,232,.44);
  background:var(--rm-surface-2);
  transform:translateY(-2px);
}

.research-v2 .kpi-num{
  font-size:1.9rem;
  font-weight:850;
}

.research-v2 .kpi-label{
  margin-top:8px;
  color:var(--rm-muted);
  font-size:.76rem;
  text-transform:none;
  font-weight:700;
}

.research-v2 .main{
  max-width:1440px;
  padding:0 clamp(16px,3vw,34px) 42px;
}

.research-v2 .section-title{
  margin:12px 0 16px;
  color:var(--rm-text);
  font-size:1.08rem;
  font-weight:850;
}

.research-v2 .section-title::before{
  width:22px;
  height:2px;
  background:var(--rm-cyan);
}

.research-v2 .oc-grid{
  grid-template-columns:repeat(auto-fit,minmax(300px,1fr));
  gap:16px;
  margin-bottom:34px;
}

.research-v2 .oc-card{
  padding:22px;
  border-color:var(--rm-line);
  border-radius:8px;
  background:
    linear-gradient(120deg,rgba(67,215,232,.09),transparent 44%),
    var(--rm-surface);
  box-shadow:0 20px 45px rgba(0,0,0,.24);
}

.research-v2 .oc-card:hover{
  border-color:rgba(67,215,232,.48);
  box-shadow:0 24px 70px rgba(0,0,0,.36);
}

.research-v2 .oc-card-head{margin-bottom:18px}
.research-v2 .oc-icon{
  width:42px;
  height:42px;
  display:grid;
  place-items:center;
  border:1px solid var(--rm-line);
  border-radius:8px;
  background:rgba(7,9,11,.36);
  font-size:1.28rem;
}

.research-v2 .oc-title{font-size:1.24rem}
.research-v2 .badge-zone,
.research-v2 .signal-badge,
.research-v2 .oc-risk-pill,
.research-v2 .ps-item{border-radius:999px}

.research-v2 .oc-body{gap:24px}
.research-v2 .oc-gauge{flex-basis:150px}
.research-v2 .gauge-svg{filter:drop-shadow(0 16px 24px rgba(0,0,0,.26))}
.research-v2 .oc-row{padding:7px 0;border-color:var(--rm-line-soft)}
.research-v2 .oc-k{color:var(--rm-muted);font-size:.74rem;text-transform:none}
.research-v2 .oc-v{color:var(--rm-text)}
.research-v2 .oc-highlight{color:var(--rm-yellow)}
.research-v2 .pos{color:var(--rm-green)}
.research-v2 .neg{color:var(--rm-red)}

.research-v2 .filter-strip{
  position:sticky;
  top:72px;
  z-index:40;
  display:flex;
  flex-direction:column;
  padding:12px;
  margin-bottom:14px;
  border:1px solid var(--rm-line);
  border-radius:8px;
  background:rgba(13,17,22,.92);
  backdrop-filter:blur(16px);
  align-items:stretch;
  gap:10px;
}

.research-v2 .filter-group{
  display:flex;
  align-items:center;
  gap:8px;
  flex-wrap:wrap;
  width:100%;
}

.research-v2 .filter-group + .filter-group{
  padding-top:10px;
  border-top:1px solid var(--rm-line-soft);
}

.research-v2 .filter-group label{
  flex:0 0 104px;
  color:var(--rm-muted);
  text-transform:none;
  font-size:.78rem;
  font-weight:800;
}

.research-v2 .fbtn{
  min-height:34px;
  border-radius:6px;
  border-color:var(--rm-line);
  background:rgba(255,255,255,.03);
  color:var(--rm-muted);
  font-size:.72rem;
  font-weight:800;
  text-transform:none;
}

.research-v2 .fbtn:hover{
  color:var(--rm-text);
  border-color:rgba(67,215,232,.4);
}

.research-v2 .fbtn.active{
  box-shadow:0 0 0 2px rgba(255,255,255,.06) inset,0 0 0 1px currentColor;
}

.research-v2 .fbtn .fc{
  color:inherit;
  opacity:.78;
}

.research-v2 .fbtn[data-filter="UltraBuy"],
.research-v2 .fbtn[data-filter="Buy"]{
  color:var(--rm-green);
  background:rgba(53,208,143,.11);
  border-color:rgba(53,208,143,.38);
}

.research-v2 .fbtn[data-filter="Neutral"]{
  color:var(--rm-blue);
  background:rgba(111,168,255,.1);
  border-color:rgba(111,168,255,.28);
}

.research-v2 .fbtn[data-filter="Sell"]{
  color:var(--rm-red);
  background:rgba(240,111,104,.12);
  border-color:rgba(240,111,104,.34);
}

.research-v2 .fbtn[data-filter="all"],
.research-v2 .fbtn[data-market]{
  color:var(--rm-cyan);
  background:rgba(67,215,232,.09);
  border-color:rgba(67,215,232,.3);
}

.research-v2 .sector-nav{
  gap:8px;
  margin-bottom:14px;
  padding:0;
  border:0;
}

.research-v2 .sector-tab{
  min-height:38px;
  padding:8px 12px;
  border:1px solid var(--rm-line);
  border-radius:6px;
  background:rgba(17,24,32,.72);
  color:var(--rm-muted);
}

.research-v2 .sector-tab:hover{
  color:var(--rm-text);
  background:var(--rm-surface-2);
}

.research-v2 .sector-tab.active{
  color:var(--rm-text);
  border-color:rgba(67,215,232,.52);
  background:rgba(67,215,232,.11);
}

.research-v2 .tab-count{
  border-radius:999px;
  border-color:var(--rm-line);
  background:rgba(7,9,11,.36);
  color:var(--rm-text);
}

.research-v2 .panel-summary{gap:8px;margin-bottom:12px}
.research-v2 .ps-item{
  border-color:var(--rm-line);
  background:rgba(17,24,32,.74);
}
.research-v2 .ps-green{color:var(--rm-green)}
.research-v2 .ps-blue{color:var(--rm-blue)}
.research-v2 .ps-red{color:var(--rm-red)}

.research-v2 .table-wrap{
  border-color:var(--rm-line);
  border-radius:8px;
  overflow:auto;
  background:var(--rm-surface);
  box-shadow:0 18px 44px rgba(0,0,0,.22);
}

.research-v2 .t-assets{
  min-width:960px;
  font-size:.84rem;
}

.research-v2 .t-assets thead{background:#0b0f14}
.research-v2 .t-assets th{
  position:sticky;
  top:0;
  z-index:2;
  padding:12px 14px;
  border-color:var(--rm-line);
  background:#0b0f14;
  color:var(--rm-muted);
  font-size:.72rem;
  text-transform:none;
}

.research-v2 .th-sort::after{content:"↕";color:var(--rm-dim)}
.research-v2 .th-sort.asc::after{content:"↑";color:var(--rm-cyan)}
.research-v2 .th-sort.desc::after{content:"↓";color:var(--rm-cyan)}
.research-v2 .t-assets td{padding:11px 14px;border-color:var(--rm-line-soft)}
.research-v2 .t-assets tbody tr:hover td{background:rgba(67,215,232,.055)}
.research-v2 .tk-badge{
  border-color:var(--rm-line);
  border-radius:5px;
  background:#080b0f;
  color:var(--rm-text);
}
.research-v2 .col-name{color:var(--rm-muted)}
.research-v2 .th-r,
.research-v2 .t-assets th:nth-child(9),
.research-v2 .col-price,
.research-v2 .col-rsi,
.research-v2 .col-dd,
.research-v2 .col-sig{
  text-align:center;
}
.research-v2 .t-assets th:nth-child(3),
.research-v2 .t-assets th:nth-child(4),
.research-v2 .t-assets th:nth-child(5),
.research-v2 .t-assets th:nth-child(6),
.research-v2 .t-assets th:nth-child(7),
.research-v2 .t-assets th:nth-child(9),
.research-v2 .col-price,
.research-v2 .col-rsi,
.research-v2 .col-dd,
.research-v2 .col-sig{
  width:12%;
}
.research-v2 .col-price{
  color:var(--rm-text);
  font-variant-numeric:tabular-nums;
}
.research-v2 .col-rsi .rsi-pill,
.research-v2 .col-dd .dd-pill,
.research-v2 .col-sig .signal-badge{
  margin-inline:auto;
}

.research-v2 .rsi-pill{
  border-radius:5px;
  color:var(--rm-muted);
  background:#080b0f;
  border:1px solid var(--rm-line);
}

.research-v2 .rsi-pill[data-zone="deep"],
.research-v2 .rsi-pill[data-zone="value"]{
  color:var(--rm-green);
  background:rgba(53,208,143,.12);
  border-color:rgba(53,208,143,.34);
}

.research-v2 .rsi-pill[data-zone="watch"]{
  color:var(--rm-cyan);
  background:rgba(67,215,232,.1);
  border-color:rgba(67,215,232,.28);
}

.research-v2 .rsi-pill[data-zone="warm"]{
  color:var(--rm-yellow);
  background:rgba(241,188,75,.12);
  border-color:rgba(241,188,75,.3);
}

.research-v2 .rsi-pill[data-zone="hot"]{
  color:var(--rm-red);
  background:rgba(240,111,104,.12);
  border-color:rgba(240,111,104,.34);
}

.research-v2 .dd-pill{
  display:inline-block;
  min-width:58px;
  padding:3px 10px;
  border-radius:5px;
  border:1px solid var(--rm-line);
  background:#080b0f;
  color:var(--rm-muted);
  font-family:var(--mono);
  font-size:.76rem;
  font-weight:800;
  font-variant-numeric:tabular-nums;
  text-align:center;
  white-space:nowrap;
}

.research-v2 .dd-flat{
  color:var(--rm-cyan);
  background:rgba(67,215,232,.1);
  border-color:rgba(67,215,232,.28);
}

.research-v2 .dd-mild{
  color:var(--rm-yellow);
  background:rgba(241,188,75,.12);
  border-color:rgba(241,188,75,.3);
}

.research-v2 .dd-deep{
  color:var(--rm-red);
  background:rgba(240,111,104,.12);
  border-color:rgba(240,111,104,.34);
}

.research-v2 .dd-stress{
  color:#ff8aa0;
  background:rgba(244,63,94,.14);
  border-color:rgba(244,63,94,.38);
}

.research-v2 .sig-ultrabuy,
.research-v2 .sig-buy{
  color:var(--rm-green);
  background:rgba(53,208,143,.11);
  border-color:rgba(53,208,143,.38);
}

.research-v2 .sig-neutral{
  color:var(--rm-blue);
  background:rgba(111,168,255,.1);
  border-color:rgba(111,168,255,.28);
}

.research-v2 .sig-sell{
  color:var(--rm-red);
  background:rgba(240,111,104,.12);
  border-color:rgba(240,111,104,.34);
}

.research-v2 .desk-highlights{
  max-width:1440px;
  margin:0 auto;
  padding:0 clamp(16px,3vw,34px) 24px;
  display:grid;
  grid-template-columns:repeat(2,minmax(0,1fr));
  gap:22px;
}

.research-v2 .highlight-card{
  min-height:252px;
  padding:18px 20px 16px;
  border:1px solid var(--rm-line);
  border-radius:8px;
  background:rgba(17,24,32,.86);
  box-shadow:0 18px 44px rgba(0,0,0,.22);
}

.research-v2 .highlight-head{
  display:flex;
  align-items:flex-start;
  justify-content:space-between;
  gap:14px;
  margin-bottom:12px;
}

.research-v2 .highlight-head h2{
  margin:0;
  color:var(--rm-text);
  font-size:.98rem;
  font-weight:850;
}

.research-v2 .highlight-head span{
  color:var(--rm-dim);
  font-size:.72rem;
  font-family:var(--mono);
  font-weight:800;
  white-space:nowrap;
}

.research-v2 .highlight-card.opportunities h2{color:var(--rm-green)}
.research-v2 .highlight-card.risks h2{color:var(--rm-red)}

.research-v2 .highlight-list{
  display:grid;
  gap:0;
}

.research-v2 .highlight-row{
  display:grid;
  grid-template-columns:30px minmax(0,1fr) minmax(108px,auto);
  align-items:center;
  gap:12px;
  min-height:42px;
  padding:10px 0;
  border-top:1px solid var(--rm-line-soft);
}

.research-v2 .highlight-rank{
  color:var(--rm-dim);
  font-family:var(--mono);
  font-size:.72rem;
  font-weight:900;
}

.research-v2 .highlight-main{
  min-width:0;
}

.research-v2 .highlight-title{
  display:flex;
  align-items:center;
  gap:8px;
  min-width:0;
}

.research-v2 .highlight-title .tk-badge{
  flex:0 0 auto;
}

.research-v2 .highlight-name{
  overflow:hidden;
  color:var(--rm-text);
  font-size:.84rem;
  font-weight:750;
  text-overflow:ellipsis;
  white-space:nowrap;
}

.research-v2 .highlight-meta{
  display:flex;
  flex-wrap:wrap;
  gap:6px;
  margin-top:6px;
}

.research-v2 .highlight-chip{
  color:var(--rm-muted);
  background:rgba(8,11,15,.72);
  border:1px solid var(--rm-line-soft);
  border-radius:5px;
  padding:2px 7px;
  font-family:var(--mono);
  font-size:.68rem;
  font-weight:800;
  white-space:nowrap;
}

.research-v2 .highlight-signal{
  display:flex;
  justify-content:flex-end;
}

.research-v2 .empty-state{
  display:none;
  padding:26px;
  border-top:1px solid var(--rm-line);
  color:var(--rm-muted);
  background:rgba(7,9,11,.2);
  font-size:.88rem;
}

.research-v2 .empty-state.is-visible{display:block}
.research-v2 .global-empty-state{
  display:none;
  margin-top:14px;
  padding:26px;
  border:1px solid var(--rm-line);
  border-radius:8px;
  color:var(--rm-muted);
  background:rgba(17,24,32,.74);
  font-size:.88rem;
}
.research-v2 .global-empty-state.is-visible{display:block}
.research-v2 .footer{
  max-width:1440px;
  margin:20px auto 0;
  padding:24px clamp(16px,3vw,34px) 36px;
  border-color:var(--rm-line);
  color:var(--rm-dim);
  text-align:left;
}
.research-v2 .footer a{color:var(--rm-cyan)}

@media(max-width:1100px){
  .research-v2 .brief-copy h1{
    white-space:normal;
    font-size:clamp(1.45rem,3vw,2.15rem);
  }
}

@media(max-width:980px){
  .research-v2 .executive-board{grid-template-columns:1fr}
  .research-v2 .desk-highlights{grid-template-columns:1fr}
  .research-v2 .oc-grid{grid-template-columns:1fr}
  .research-v2 .topbar-brand{min-width:auto}
}

@media(max-width:720px){
  .research-v2 .topbar{min-height:auto}
  .research-v2 .search-wrap{
    flex-basis:100%;
    max-width:none;
    order:3;
  }
  .research-v2 .topbar-meta{
    width:100%;
    justify-content:space-between;
  }
  .research-v2 .brief-copy{
    min-height:auto;
    padding:22px;
  }
  .research-v2 .filter-group label{
    flex-basis:100%;
  }
  .research-v2 .kpi-strip{
    display:grid;
    grid-template-columns:repeat(2,minmax(0,1fr));
  }
  .research-v2 .kpi-cell{min-width:0}
  .research-v2 .filter-strip{position:static}
}

@media(max-width:480px){
  .research-v2 .executive-board,
  .research-v2 .desk-highlights,
  .research-v2 .main,
  .research-v2 .kpi-strip{
    padding-left:12px;
    padding-right:12px;
  }
  .research-v2 .kpi-strip{grid-template-columns:1fr}
  .research-v2 .oc-body{flex-direction:column}
  .research-v2 .oc-gauge{
    width:150px;
    flex-basis:auto;
  }
}

/* ===== PROFILE-INSPIRED BACKGROUND ===== */
body.research-v2.profile-field-v2{
  position:relative;
  isolation:isolate;
  overflow-x:hidden;
  background:
    conic-gradient(from 218deg at 14% -12%, rgba(85,166,255,.36), transparent 22%, rgba(48,214,181,.16) 34%, transparent 50%),
    conic-gradient(from 36deg at 92% 6%, rgba(255,104,72,.24), transparent 27%, rgba(85,166,255,.15) 46%, transparent 66%),
    linear-gradient(132deg, rgba(85,166,255,.18), transparent 34rem),
    linear-gradient(228deg, rgba(255,104,72,.15), transparent 36rem),
    linear-gradient(180deg,#050607 0%,#081013 46%,#040506 100%);
  background-attachment:fixed;
  background-size:150% 150%,150% 150%,100% 100%,100% 100%,100% 100%;
  animation:profileAmbientField 16s ease-in-out infinite alternate;
}

body.research-v2.profile-field-v2::before,
body.research-v2.profile-field-v2::after{
  content:"";
  position:fixed;
  inset:0;
  pointer-events:none;
  z-index:0;
}

body.research-v2.profile-field-v2::before{
  background:
    radial-gradient(circle, rgba(85,166,255,.34) 0 1.15px, transparent 1.55px),
    radial-gradient(circle, rgba(48,214,181,.22) 0 1px, transparent 1.35px),
    linear-gradient(rgba(255,255,255,.046) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255,255,255,.04) 1px, transparent 1px),
    linear-gradient(rgba(85,166,255,.09) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255,104,72,.07) 1px, transparent 1px);
  background-size:42px 42px,84px 84px,126px 126px,126px 126px,28px 28px,28px 28px;
  -webkit-mask-image:linear-gradient(180deg, rgba(0,0,0,.76), rgba(0,0,0,.48) 58%, transparent 96%);
  mask-image:linear-gradient(180deg, rgba(0,0,0,.76), rgba(0,0,0,.48) 58%, transparent 96%);
  mix-blend-mode:screen;
  opacity:.58;
  animation:profileDataGrid 13s linear infinite;
}

body.research-v2.profile-field-v2::after{
  background:
    repeating-linear-gradient(116deg, transparent 0 4.2rem, rgba(85,166,255,.13) 4.2rem 4.28rem, transparent 4.28rem 8.4rem),
    repeating-linear-gradient(64deg, transparent 0 5.8rem, rgba(48,214,181,.09) 5.8rem 5.88rem, transparent 5.88rem 10.8rem),
    repeating-linear-gradient(180deg, transparent 0 8.75rem, rgba(255,255,255,.045) 8.75rem 8.82rem, transparent 8.82rem 11.5rem),
    linear-gradient(116deg, transparent 0 11%, rgba(85,166,255,.2) 11% 11.18%, transparent 11.18% 46%, rgba(255,104,72,.16) 46% 46.16%, transparent 46.16% 100%),
    linear-gradient(244deg, transparent 0 58%, rgba(48,214,181,.13) 58% 58.16%, transparent 58.16% 100%);
  background-size:220px 220px,300px 300px,100% 18rem,100% 100%,100% 100%;
  -webkit-mask-image:linear-gradient(180deg, rgba(0,0,0,.68), rgba(0,0,0,.42) 54%, transparent 94%);
  mask-image:linear-gradient(180deg, rgba(0,0,0,.68), rgba(0,0,0,.42) 54%, transparent 94%);
  mix-blend-mode:screen;
  opacity:.64;
  animation:profileDataStream 10s ease-in-out infinite alternate;
}

.research-v2.profile-field-v2 .topbar{
  z-index:100;
  background:
    linear-gradient(90deg, rgba(85,166,255,.1), transparent 28%, rgba(255,104,72,.07) 78%, transparent),
    rgba(5,8,12,.82);
  border-bottom-color:rgba(125,177,255,.22);
  box-shadow:0 18px 58px rgba(0,0,0,.36);
}

.research-v2.profile-field-v2 .executive-board,
.research-v2.profile-field-v2 .desk-highlights,
.research-v2.profile-field-v2 .kpi-strip,
.research-v2.profile-field-v2 .main,
.research-v2.profile-field-v2 .footer{
  position:relative;
  z-index:1;
}

.research-v2.profile-field-v2 .brief-copy,
.research-v2.profile-field-v2 .market-read,
.research-v2.profile-field-v2 .highlight-card,
.research-v2.profile-field-v2 .kpi-cell,
.research-v2.profile-field-v2 .oc-card,
.research-v2.profile-field-v2 .filter-strip,
.research-v2.profile-field-v2 .table-wrap,
.research-v2.profile-field-v2 .global-empty-state{
  border-color:rgba(125,177,255,.22);
  background:
    linear-gradient(145deg, rgba(85,166,255,.08), transparent 38%, rgba(255,104,72,.055)),
    rgba(9,15,23,.82);
  box-shadow:0 22px 54px rgba(0,0,0,.32);
  backdrop-filter:blur(18px) saturate(1.14);
}

.research-v2.profile-field-v2 .brief-copy{
  background:
    linear-gradient(125deg, rgba(85,166,255,.16), transparent 36%, rgba(255,104,72,.09)),
    rgba(9,15,23,.78);
}

.research-v2.profile-field-v2 .market-read h2,
.research-v2.profile-field-v2 .eyebrow,
.research-v2.profile-field-v2 .section-title::before{
  filter:drop-shadow(0 0 14px rgba(85,166,255,.28));
}

.research-v2.profile-field-v2 .filter-strip{
  background:
    linear-gradient(90deg, rgba(85,166,255,.07), transparent 38%, rgba(255,104,72,.045)),
    rgba(6,10,15,.86);
}

.research-v2.profile-field-v2 .t-assets thead,
.research-v2.profile-field-v2 .t-assets th{
  background:rgba(6,10,15,.92);
}

.research-v2.profile-field-v2 .t-assets td{
  background:rgba(9,15,23,.28);
}

.research-v2.profile-field-v2 .t-assets tbody tr:hover td{
  background:rgba(85,166,255,.075);
}

.research-v2.profile-field-v2 .footer{
  background:linear-gradient(90deg, transparent, rgba(85,166,255,.05), rgba(255,104,72,.035), transparent);
}

@keyframes profileAmbientField{
  from{background-position:0 0,100% 0,0 0,0 0,0 0}
  to{background-position:16% 7%,84% 10%,0 0,0 0,0 0}
}

@keyframes profileDataGrid{
  to{background-position:84px 42px,-84px 84px,126px 126px,126px 126px,28px 28px,28px 28px}
}

@keyframes profileDataStream{
  from{background-position:0 0,0 0,0 0,0 0,0 0;opacity:.52}
  to{background-position:120px -72px,-96px 84px,0 9rem,0 0,0 0;opacity:.72}
}

@media(prefers-reduced-motion:reduce){
  body.research-v2.profile-field-v2,
  body.research-v2.profile-field-v2::before,
  body.research-v2.profile-field-v2::after,
  body.research-v2.profile-field-v2 *{
    animation:none!important;
    transition:none!important;
    scroll-behavior:auto!important;
  }
}
"""

RESEARCH_V2_SCRIPT = r"""
(function(){
  "use strict";

  const panels = document.querySelectorAll('.sector-panel');
  const rows = document.querySelectorAll('.asset-row');
  const signalBtns = document.querySelectorAll('.fbtn[data-filter]');
  const marketBtns = document.querySelectorAll('.fbtn[data-market]');
  const signalGroup = document.querySelector('.signal-filter');
  const marketGroup = document.querySelector('.market-filter');
  const sectorGroup = document.querySelector('.sector-filter');
  const sectorChips = document.querySelectorAll('.sec-chip');
  const sectorCards = document.querySelectorAll('.sec-card');
  const searchInput = document.getElementById('globalSearch');
  const globalEmpty = document.getElementById('globalEmpty');

  const state = {
    signals: new Set(),
    markets: new Set(),
    sectors: new Set(),
    query: ''
  };

  panels.forEach(panel => {
    if(!panel.querySelector('.empty-state')) {
      const empty = document.createElement('div');
      empty.className = 'empty-state';
      empty.textContent = 'No assets match the current filters.';
      panel.appendChild(empty);
    }
  });

  function normalize(value) {
    return (value || '').toLowerCase().trim();
  }

  function selectedMatches(selected, value) {
    return selected.size === 0 || selected.has(value);
  }

  function toggleSelection(selected, value) {
    if(value === 'all') {
      selected.clear();
      return;
    }
    if(selected.has(value)) selected.delete(value);
    else selected.add(value);
  }

  function syncButtonGroup(group, buttons, selected, dataKey) {
    const focused = selected.size > 0;
    if(group) group.classList.toggle('has-selection', focused);
    buttons.forEach(btn => {
      const value = btn.dataset[dataKey];
      const active = value === 'all' ? !focused : selected.has(value);
      btn.classList.toggle('active', active);
      btn.classList.toggle('is-muted', focused && !active);
    });
  }

  function rowMatches(row) {
    const signalMatch = selectedMatches(state.signals, row.dataset.signal);
    const marketMatch = selectedMatches(state.markets, row.dataset.market);
    const sectorMatch = selectedMatches(state.sectors, row.dataset.sector);
    const textMatch = !state.query ||
      normalize(row.dataset.ticker).includes(state.query) ||
      normalize(row.dataset.name).includes(state.query);
    return signalMatch && marketMatch && sectorMatch && textMatch;
  }

  function syncSectorUI() {
    sectorCards.forEach(c => {
      const active = state.sectors.has(c.dataset.sectorCard);
      c.classList.toggle('active', active);
      c.classList.toggle('dimmed', state.sectors.size > 0 && !active);
    });
  }

  function setSummary(item, count, singular, plural) {
    if(!item) return;
    item.textContent = `${count} ${count === 1 ? singular : plural}`;
    item.hidden = state.signals.size > 0 && count === 0;
  }

  function updatePanelSummary(panel, counts) {
    setSummary(panel.querySelector('.ps-green'), counts.opportunities, 'opportunity', 'opportunities');
    setSummary(panel.querySelector('.ps-blue'), counts.neutral, 'neutral', 'neutral');
    setSummary(panel.querySelector('.ps-red'), counts.overbought, 'overbought', 'overbought');
  }

  function syncPanels() {
    let totalVisible = 0;

    panels.forEach(panel => {
      const panelName = panel.id.replace('panel-', '');
      const visibleCounts = {
        opportunities: 0,
        neutral: 0,
        overbought: 0
      };

      let visibleRows = 0;
      panel.querySelectorAll('.asset-row').forEach(row => {
        const isVisible = rowMatches(row);
        row.hidden = !isVisible;
        if(isVisible) {
          visibleRows += 1;
          if(row.dataset.signal === 'UltraBuy' || row.dataset.signal === 'Buy') visibleCounts.opportunities += 1;
          else if(row.dataset.signal === 'Neutral') visibleCounts.neutral += 1;
          else if(row.dataset.signal === 'Sell') visibleCounts.overbought += 1;
        }
      });

      totalVisible += visibleRows;
      const shouldShowPanel = state.markets.size === 0 ? visibleRows > 0 : state.markets.has(panelName);
      panel.classList.toggle('active', shouldShowPanel);
      updatePanelSummary(panel, visibleCounts);

      const empty = panel.querySelector('.empty-state');
      if(empty) empty.classList.toggle('is-visible', shouldShowPanel && visibleRows === 0);
    });

    if(globalEmpty) globalEmpty.classList.toggle('is-visible', totalVisible === 0);
  }

  function syncFilterButtons() {
    syncButtonGroup(signalGroup, signalBtns, state.signals, 'filter');
    syncButtonGroup(marketGroup, marketBtns, state.markets, 'market');
    syncButtonGroup(sectorGroup, sectorChips, state.sectors, 'sector');
  }

  function applyViewState() {
    syncFilterButtons();
    syncSectorUI();
    syncPanels();
  }

  signalBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      toggleSelection(state.signals, btn.dataset.filter);
      applyViewState();
    });
  });

  marketBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      toggleSelection(state.markets, btn.dataset.market);
      applyViewState();
    });
  });

  sectorChips.forEach(chip => {
    chip.addEventListener('click', () => {
      toggleSelection(state.sectors, chip.dataset.sector);
      applyViewState();
    });
  });

  sectorCards.forEach(card => {
    const go = () => {
      toggleSelection(state.sectors, card.dataset.sectorCard);
      applyViewState();
    };
    card.addEventListener('click', go);
    card.addEventListener('keydown', e => {
      if(e.key === 'Enter' || e.key === ' '){ e.preventDefault(); go(); }
    });
  });

  if(searchInput) {
    searchInput.addEventListener('input', () => {
      state.query = normalize(searchInput.value);
      applyViewState();
    });
  }

  document.querySelectorAll('.th-sort').forEach(th => {
    th.addEventListener('click', () => {
      const table = th.closest('table');
      const tbody = table.querySelector('tbody');
      const col = parseInt(th.dataset.col);
      const tableRows = Array.from(tbody.querySelectorAll('tr'));
      const isAsc = th.classList.contains('asc');

      th.closest('thead').querySelectorAll('.th-sort').forEach(h => {
        h.classList.remove('asc','desc');
      });

      th.classList.add(isAsc ? 'desc' : 'asc');
      const dir = isAsc ? -1 : 1;

      tableRows.sort((a, b) => {
        let va = a.children[col]?.dataset.sort || a.children[col]?.textContent.trim() || '';
        let vb = b.children[col]?.dataset.sort || b.children[col]?.textContent.trim() || '';
        const na = parseFloat(va.replace(/[^0-9.\-]/g, ''));
        const nb = parseFloat(vb.replace(/[^0-9.\-]/g, ''));
        if(!isNaN(na) && !isNaN(nb)) return (na - nb) * dir;
        return va.localeCompare(vb, 'pt-BR') * dir;
      });

      tableRows.forEach(r => tbody.appendChild(r));
    });
  });

  document.addEventListener('keydown', (e) => {
    if(e.key === '/' && searchInput && document.activeElement !== searchInput) {
      e.preventDefault();
      searchInput.focus();
    }
    if(e.key === 'Escape' && searchInput) {
      searchInput.value = '';
      state.query = '';
      applyViewState();
      searchInput.blur();
    }
  });

  rows.forEach(row => row.hidden = false);
  applyViewState();
})();
"""


RESEARCH_V3_CSS = """
/* ===== V3 ENHANCEMENTS ===== */

/* Typography */
body.research-v2{font-family:Inter,"Segoe UI",system-ui,-apple-system,BlinkMacSystemFont,sans-serif}
.research-v2 .brief-copy h1,.research-v2 .brand-name,.research-v2 .section-title{letter-spacing:-.02em}
.research-v2 .col-price,.research-v2 .col-dd,.research-v2 .highlight-chip{font-variant-numeric:tabular-nums}

/* Radius unification */
.research-v2 .brief-copy,.research-v2 .market-read,.research-v2 .kpi-cell,.research-v2 .oc-card,
.research-v2 .highlight-card,.research-v2 .table-wrap,.research-v2 .filter-strip{border-radius:12px}

/* KPI deltas */
.research-v2 .kpi-delta{display:flex;align-items:baseline;gap:6px;margin-top:8px;font-family:var(--mono);font-size:.68rem;font-weight:700}
.research-v2 .kpi-delta .d-good{color:var(--rm-green)}
.research-v2 .kpi-delta .d-bad{color:var(--rm-red)}
.research-v2 .kpi-delta .d-flat{color:var(--rm-muted)}
.research-v2 .kpi-delta .d-ctx{color:var(--rm-dim);font-family:var(--font);font-weight:600}

/* Signal Allocation — reuse the signal-badge look, KPI-style count */
.research-v2 .market-read .mix-row{grid-template-columns:auto 1fr auto;gap:14px;min-height:40px}
.research-v2 .market-read .mix-row .signal-badge{min-width:84px;text-align:center;justify-self:start}
.research-v2 .market-read .mix-row .mix-bar{height:8px}
.research-v2 .market-read .mix-row strong{font-size:1.05rem;font-weight:850;color:var(--rm-text)}

/* RSI position meters */
.research-v2 .rsi-meter{display:inline-flex;flex-direction:column;align-items:center;gap:6px;min-width:64px}
.research-v2 .rsi-meter .rsi-pill{background:transparent;border:0;padding:0;min-width:0;font-size:.8rem}
.research-v2 .rsi-track{position:relative;width:64px;height:4px;border-radius:999px;background:rgba(148,163,184,.16)}
.research-v2 .rsi-track::before{content:"";position:absolute;inset:0;border-radius:inherit;opacity:.4;
  background:linear-gradient(90deg,rgba(53,208,143,.55) 0 30%,transparent 30% 70%,rgba(240,111,104,.55) 70% 100%)}
.research-v2 .rsi-tick{position:absolute;top:-2px;bottom:-2px;width:1px;background:rgba(148,163,184,.38)}
.research-v2 .rsi-dot{position:absolute;top:50%;width:9px;height:9px;border-radius:50%;transform:translate(-50%,-50%);
  background:var(--rm-muted);box-shadow:0 0 0 2px var(--rm-surface)}
.research-v2 .rsi-meter[data-zone="deep"] .rsi-dot,.research-v2 .rsi-meter[data-zone="value"] .rsi-dot{background:var(--rm-green)}
.research-v2 .rsi-meter[data-zone="watch"] .rsi-dot{background:var(--rm-cyan)}
.research-v2 .rsi-meter[data-zone="warm"] .rsi-dot{background:var(--rm-yellow)}
.research-v2 .rsi-meter[data-zone="hot"] .rsi-dot{background:var(--rm-red)}
.research-v2 .rsi-meter[data-zone="na"] .rsi-pill{color:var(--rm-muted);font-style:italic;opacity:.7}
.research-v2 .rsi-meter[data-zone="na"] .rsi-track{opacity:.4}

/* Gauges */
.research-v2 .gauge-svg{overflow:visible}
.research-v2 .gauge-svg .g-tick{stroke:var(--rm-surface)}
.research-v2 .gauge-svg .g-lab{fill:var(--rm-dim);font-weight:700;font-family:var(--mono)}
.research-v2 .gauge-svg .g-val{font-family:var(--mono)}
.research-v2 .g-arc{stroke-dasharray:var(--arc) 100}
@media (prefers-reduced-motion:no-preference){
  @keyframes gaugeGrow{from{stroke-dasharray:0 100}}
  .research-v2 .g-arc{animation:gaugeGrow 1.1s cubic-bezier(.25,.75,.3,1)}
}

/* Expandable rows */
.research-v2 .asset-row{cursor:pointer}
.research-v2 .asset-row .col-tk{white-space:nowrap}
.research-v2 .asset-row .col-tk::before{content:"\\203a";display:inline-block;margin-right:8px;color:var(--rm-dim);
  font-weight:800;transition:transform .2s ease,color .2s ease}
.research-v2 .asset-row.expanded .col-tk::before{transform:rotate(90deg);color:var(--rm-cyan)}
.research-v2 .asset-detail td{padding:0;border-bottom:1px solid var(--rm-line-soft);background:rgba(67,215,232,.035)}
.research-v2 .detail-inner{display:flex;flex-wrap:wrap;align-items:center;gap:22px;padding:14px 18px 14px 44px}
.research-v2 .detail-item{display:flex;flex-direction:column;gap:3px}
.research-v2 .detail-item .k{font-size:.6rem;font-weight:800;color:var(--rm-dim);text-transform:uppercase;letter-spacing:.5px}
.research-v2 .detail-item .v{font-family:var(--mono);font-size:.82rem;font-weight:700;color:var(--rm-text)}
.research-v2 .detail-links{margin-left:auto;display:flex;gap:10px;flex-wrap:wrap}
.research-v2 .detail-link{display:inline-flex;align-items:center;gap:6px;padding:7px 14px;border-radius:8px;
  border:1px solid rgba(67,215,232,.35);background:rgba(67,215,232,.08);color:var(--rm-cyan);
  font-size:.72rem;font-weight:800;text-decoration:none;transition:.2s;white-space:nowrap}
.research-v2 .detail-link:hover{background:rgba(67,215,232,.16)}

/* Entrance motion */
@media (prefers-reduced-motion:no-preference){
  @keyframes v3Up{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:none}}
  .research-v2 .brief-copy,.research-v2 .market-read,.research-v2 .kpi-cell,
  .research-v2 .oc-card,.research-v2 .highlight-card{animation:v3Up .6s cubic-bezier(.22,.7,.3,1) both}
  .research-v2 .market-read{animation-delay:.08s}
  .research-v2 .kpi-cell:nth-child(2){animation-delay:.05s}
  .research-v2 .kpi-cell:nth-child(3){animation-delay:.1s}
  .research-v2 .kpi-cell:nth-child(4){animation-delay:.15s}
  .research-v2 .kpi-cell:nth-child(5){animation-delay:.2s}
  .research-v2 .oc-card:nth-child(2){animation-delay:.08s}
  .research-v2 .oc-card:nth-child(3){animation-delay:.16s}
  .research-v2 .highlight-card:nth-child(2){animation-delay:.1s}
}

/* Focus visibility */
.research-v2 .fbtn:focus-visible,.research-v2 .sector-tab:focus-visible,.research-v2 .asset-row:focus-visible,
.research-v2 .theme-btn:focus-visible,.research-v2 .detail-link:focus-visible,.research-v2 .search-input:focus-visible{
  outline:2px solid var(--rm-cyan);outline-offset:2px}

/* Theme toggle button */
.research-v2 .theme-btn{display:inline-flex;align-items:center;justify-content:center;width:30px;height:30px;border-radius:8px;
  border:1px solid var(--rm-line);background:transparent;color:var(--rm-muted);cursor:pointer;font-size:.9rem;transition:.2s}
.research-v2 .theme-btn:hover{color:var(--rm-cyan);border-color:rgba(67,215,232,.5)}

/* ===== LIGHT THEME ===== */
body.research-v2.theme-light{
  --rm-bg:#eef2f6;--rm-bg-soft:#e9eef4;--rm-surface:#ffffff;--rm-surface-2:#f4f7fa;--rm-surface-3:#e9eef4;
  --rm-line:#d9e1e9;--rm-line-soft:rgba(22,32,42,.12);
  --rm-text:#16202a;--rm-muted:#48586a;--rm-dim:#7b8a99;
  --rm-cyan:#0e7490;--rm-green:#087f5b;--rm-yellow:#b45309;--rm-red:#c92a2a;--rm-blue:#1d4ed8;
  --rm-shadow:0 18px 44px rgba(15,30,45,.1);
  --teal:#0e7490;--green:#087f5b;--red:#c92a2a;--yellow:#b45309;--blue:#1d4ed8;--orange:#c2410c;
  --txt:#16202a;--muted:#48586a;--dim:#7b8a99;--line:#d9e1e9;--glow-teal:rgba(14,116,144,.14);
  color:var(--rm-text);
}
body.research-v2.profile-field-v2.theme-light{
  background:linear-gradient(160deg,#f7fafc 0%,#eef2f6 45%,#e7edf3 100%);
  background-attachment:fixed;animation:none;
}
body.research-v2.profile-field-v2.theme-light::before,
body.research-v2.profile-field-v2.theme-light::after{display:none}
.research-v2.theme-light .topbar{background:rgba(255,255,255,.88);border-bottom-color:var(--rm-line);box-shadow:0 10px 30px rgba(15,30,45,.06)}
.research-v2.theme-light .brief-copy,
.research-v2.theme-light .market-read,
.research-v2.theme-light .highlight-card,
.research-v2.theme-light .kpi-cell,
.research-v2.theme-light .oc-card,
.research-v2.theme-light .filter-strip,
.research-v2.theme-light .table-wrap,
.research-v2.theme-light .global-empty-state{
  border-color:var(--rm-line);background:#fff;box-shadow:0 14px 34px rgba(15,30,45,.08);backdrop-filter:none;
}
.research-v2.theme-light .brief-copy{background:linear-gradient(135deg,rgba(14,116,144,.06),transparent 40%),#fff}
.research-v2.theme-light .oc-card{background:linear-gradient(120deg,rgba(14,116,144,.04),transparent 44%),#fff}
.research-v2.theme-light .oc-card:hover{border-color:rgba(14,116,144,.4);box-shadow:0 18px 44px rgba(15,30,45,.12)}
.research-v2.theme-light .kpi-cell:hover{background:#f4f7fa;border-color:rgba(14,116,144,.4)}
.research-v2.theme-light .search-input,
.research-v2.theme-light .topbar-meta,
.research-v2.theme-light .sector-tab,
.research-v2.theme-light .ps-item,
.research-v2.theme-light .empty-state{background:#fff;border-color:var(--rm-line)}
.research-v2.theme-light .oc-icon{background:#f4f7fa;border-color:var(--rm-line)}
.research-v2.theme-light .t-assets thead,
.research-v2.theme-light .t-assets th{background:#f4f7fa;border-color:var(--rm-line)}
.research-v2.theme-light .t-assets td{background:transparent}
.research-v2.theme-light .t-assets tbody tr:hover td{background:rgba(14,116,144,.05)}
.research-v2.theme-light .tk-badge,
.research-v2.theme-light .dd-pill{background:#f2f5f8}
.research-v2.theme-light .rsi-meter .rsi-pill{background:transparent}
.research-v2.theme-light .fbtn{background:#fff}
.research-v2.theme-light .fbtn[data-filter="UltraBuy"],.research-v2.theme-light .fbtn[data-filter="Buy"]{background:rgba(8,127,91,.08)}
.research-v2.theme-light .fbtn[data-filter="Neutral"]{background:rgba(29,78,216,.07)}
.research-v2.theme-light .fbtn[data-filter="Sell"]{background:rgba(201,42,42,.07)}
.research-v2.theme-light .fbtn[data-filter="all"],.research-v2.theme-light .fbtn[data-market]{background:rgba(14,116,144,.07)}
.research-v2.theme-light .highlight-chip{background:#f2f5f8;border-color:var(--rm-line);color:var(--rm-muted)}
.research-v2.theme-light .mix-bar{background:rgba(22,32,42,.1)}
.research-v2.theme-light .rsi-track{background:rgba(22,32,42,.1)}
.research-v2.theme-light .rsi-dot{box-shadow:0 0 0 2px #fff}
.research-v2.theme-light .asset-detail td{background:rgba(14,116,144,.04)}
.research-v2.theme-light .detail-link{background:rgba(14,116,144,.07);border-color:rgba(14,116,144,.3)}
.research-v2.theme-light .gauge-svg{filter:none}
.research-v2.theme-light .footer{background:none}
.research-v2.theme-light .market-read h2,
.research-v2.theme-light .eyebrow,
.research-v2.theme-light .section-title::before{filter:none}

/* ===== V3 OFFICIAL LAYOUT ===== */
body.research-v2.profile-field-v3{
  --rm-bg:#040507;
  --rm-bg-soft:#07090d;
  --rm-surface:#0a0d12;
  --rm-surface-2:#0e1219;
  --rm-surface-3:#131824;
  --rm-line:#1a2130;
  --rm-line-soft:rgba(148,170,200,.10);
  --rm-text:#e8edf5;
  --rm-muted:#94a2b8;
  --rm-dim:#5d6b80;
  --rm-green:#2ee6a6;
  --rm-red:#ff6472;
  --rm-blue:#7aa2ff;
  --rm-cyan:#26d0e8;
  --rm-yellow:#f5c34b;
  --rm-shadow:0 24px 70px rgba(0,0,0,.5);
  --bg:var(--rm-bg);
  --bg2:var(--rm-surface);
  --card:var(--rm-surface-2);
  --card2:var(--rm-surface-3);
  --txt:var(--rm-text);
  --muted:var(--rm-muted);
  --dim:var(--rm-dim);
  --line:var(--rm-line);
  --green:var(--rm-green);
  --red:var(--rm-red);
  --blue:var(--rm-blue);
  --teal:var(--rm-cyan);
  --yellow:var(--rm-yellow);
  --radius:14px;
  --radius-sm:10px;
  --radius-xs:7px;
  --spectrum:linear-gradient(90deg,var(--rm-cyan),var(--rm-green) 32%,var(--rm-yellow) 66%,var(--rm-red));
  position:relative;
  isolation:isolate;
  overflow-x:hidden;
  background:
    conic-gradient(from 218deg at 10% -14%,rgba(122,162,255,.24),transparent 22%,rgba(46,230,166,.12) 36%,transparent 58%),
    conic-gradient(from 42deg at 94% 2%,rgba(255,100,114,.15),transparent 24%,rgba(38,208,232,.12) 46%,transparent 68%),
    linear-gradient(132deg,rgba(122,162,255,.13),transparent 34rem),
    linear-gradient(228deg,rgba(255,100,114,.09),transparent 38rem),
    linear-gradient(180deg,#030506 0%,#071017 48%,#030506 100%);
  background-attachment:fixed;
  background-size:155% 155%,150% 150%,100% 100%,100% 100%,100% 100%;
  animation:v3AmbientField 18s ease-in-out infinite alternate;
}
body.research-v2.profile-field-v3::before,
body.research-v2.profile-field-v3::after{
  content:"";
  position:fixed;
  inset:0;
  z-index:0;
  pointer-events:none;
}
body.research-v2.profile-field-v3::before{
  background:
    linear-gradient(rgba(148,170,200,.052) 1px,transparent 1px),
    linear-gradient(90deg,rgba(148,170,200,.044) 1px,transparent 1px),
    radial-gradient(circle,rgba(122,162,255,.28) 0 1px,transparent 1.45px),
    radial-gradient(circle,rgba(46,230,166,.18) 0 .9px,transparent 1.3px);
  background-size:72px 72px,72px 72px,36px 36px,108px 108px;
  -webkit-mask-image:linear-gradient(180deg,rgba(0,0,0,.74),rgba(0,0,0,.48) 56%,transparent 94%);
          mask-image:linear-gradient(180deg,rgba(0,0,0,.74),rgba(0,0,0,.48) 56%,transparent 94%);
  mix-blend-mode:screen;
  opacity:.56;
  animation:v3DataGrid 16s linear infinite;
}
body.research-v2.profile-field-v3::after{
  background:
    repeating-linear-gradient(116deg,transparent 0 4.6rem,rgba(122,162,255,.12) 4.6rem 4.68rem,transparent 4.68rem 9.2rem),
    repeating-linear-gradient(64deg,transparent 0 6.4rem,rgba(46,230,166,.08) 6.4rem 6.48rem,transparent 6.48rem 12rem),
    linear-gradient(180deg,transparent 0%,rgba(3,5,6,.22) 72%,rgba(3,5,6,.62) 100%);
  -webkit-mask-image:linear-gradient(180deg,rgba(0,0,0,.62),rgba(0,0,0,.34) 52%,transparent 92%);
          mask-image:linear-gradient(180deg,rgba(0,0,0,.62),rgba(0,0,0,.34) 52%,transparent 92%);
  mix-blend-mode:screen;
  opacity:.48;
  animation:v3DataStream 12s ease-in-out infinite alternate;
}
.research-v2.profile-field-v3 .topbar,
.research-v2.profile-field-v3 .v2nav,
.research-v2.profile-field-v3 .executive-board,
.research-v2.profile-field-v3 .kpi-strip,
.research-v2.profile-field-v3 .desk-highlights,
.research-v2.profile-field-v3 .main,
.research-v2.profile-field-v3 .footer{
  position:relative;
  z-index:1;
}
.research-v2.profile-field-v3 .topbar{
  z-index:120;
  background:rgba(5,7,10,.92);
  border-bottom-color:rgba(125,177,255,.18);
}
.research-v2.profile-field-v3 .topbar.scrolled{
  background:rgba(5,7,10,.96);
  box-shadow:0 12px 34px rgba(0,0,0,.45);
}
.research-v2.profile-field-v3 .brand-dot{
  width:9px;
  height:9px;
  border-radius:50%;
  flex:0 0 auto;
  background:var(--rm-cyan);
  box-shadow:0 0 0 3px rgba(38,208,232,.16),0 0 14px rgba(38,208,232,.55);
  animation:pulseDot 2.6s var(--ease,cubic-bezier(.22,.61,.36,1)) infinite;
}
.research-v2.profile-field-v3 .brand-dot::after{
  content:none;
  display:none;
}
@keyframes pulseDot{
  0%,100%{box-shadow:0 0 0 3px rgba(38,208,232,.16),0 0 14px rgba(38,208,232,.55)}
  50%{box-shadow:0 0 0 5px rgba(38,208,232,.07),0 0 5px rgba(38,208,232,.25)}
}
.research-v2.profile-field-v3 .topbar-brand{
  min-width:auto;
  gap:11px;
}
.research-v2.profile-field-v3 .v2nav{
  position:relative;
  top:auto;
  z-index:110;
  display:flex;
  align-items:center;
  gap:8px;
  padding:10px clamp(16px,3vw,40px);
  overflow-x:auto;
  background:rgba(15,23,33,.62);
  border-bottom:1px solid rgba(148,170,200,.12);
  backdrop-filter:blur(16px) saturate(1.25);
  -webkit-backdrop-filter:blur(16px) saturate(1.25);
  transition:box-shadow .25s ease,background .25s ease;
}
.research-v2.profile-field-v3 .v2nav.scrolled{
  background:rgba(15,23,33,.76);
  box-shadow:0 10px 26px rgba(0,0,0,.24);
}
.research-v2.profile-field-v3 .v2nav-link{
  color:var(--rm-cyan);
  text-decoration:none;
  white-space:nowrap;
  padding:6px 13px;
  border:1px solid rgba(38,208,232,.24);
  border-radius:8px;
  background:rgba(38,208,232,.09);
  font-family:var(--font);
  font-size:.78rem;
  font-weight:750;
  line-height:1;
  letter-spacing:0;
  text-transform:none;
  transition:color .2s ease,background .2s ease,border-color .2s ease;
}
.research-v2.profile-field-v3 .v2nav-link:hover{
  color:var(--rm-text);
  background:rgba(38,208,232,.14);
  border-color:rgba(38,208,232,.34);
}
.research-v2.profile-field-v3 .v2nav-link.active{
  color:var(--rm-cyan);
  background:rgba(38,208,232,.12);
  border-color:rgba(38,208,232,.32);
  box-shadow:0 0 18px rgba(38,208,232,.08);
}
.research-v2.profile-field-v3 #overview,
.research-v2.profile-field-v3 #onchain,
.research-v2.profile-field-v3 #sectors,
.research-v2.profile-field-v3 #matrix{
  scroll-margin-top:calc(var(--chrome-h,120px) + 12px);
}
.research-v2.profile-field-v3 .executive-board,
.research-v2.profile-field-v3 .kpi-strip,
.research-v2.profile-field-v3 .desk-highlights,
.research-v2.profile-field-v3 .main,
.research-v2.profile-field-v3 .footer{
  max-width:1500px;
}
.research-v2.profile-field-v3 .executive-board{
  grid-template-columns:minmax(0,1.62fr) minmax(340px,420px);
  gap:30px;
  padding:42px clamp(22px,2.6vw,40px) 34px;
}
.research-v2.profile-field-v3 .kpi-strip,
.research-v2.profile-field-v3 .desk-highlights,
.research-v2.profile-field-v3 .main,
.research-v2.profile-field-v3 .footer{
  padding-left:clamp(22px,2.6vw,40px);
  padding-right:clamp(22px,2.6vw,40px);
}
.research-v2.profile-field-v3 .kpi-strip{gap:16px}
.research-v2.profile-field-v3 .desk-highlights{gap:18px;padding-top:24px}
.research-v2.profile-field-v3 .main{padding-top:34px}
.research-v2.profile-field-v3 .brief-copy{
  min-height:0;
  padding:0;
  border:0;
  border-radius:0;
  background:transparent;
  box-shadow:none;
}
.research-v2.profile-field-v3 .brief-copy h1{
  max-width:none;
  margin:0 0 14px;
  font-size:clamp(1.65rem,3.1vw,2.5rem);
  line-height:1.14;
  font-weight:900;
  letter-spacing:-1.1px;
  white-space:normal;
  color:#fff;
  background:linear-gradient(135deg,#fff 22%,#b9c7dd 78%);
  -webkit-background-clip:text;
  background-clip:text;
  -webkit-text-fill-color:transparent;
}
.research-v2.profile-field-v3 .brief-copy p{
  max-width:56ch;
  color:var(--rm-muted);
  font-size:.92rem;
}
.research-v2.profile-field-v3 .eyebrow{
  display:inline-flex;
  align-items:center;
  gap:10px;
  margin-bottom:16px;
  color:var(--rm-cyan);
  font-family:var(--mono);
  font-size:.64rem;
  font-weight:600;
  letter-spacing:2.2px;
  text-transform:uppercase;
}
.research-v2.profile-field-v3 .eyebrow::before{
  content:"";
  width:26px;
  height:1px;
  background:var(--rm-cyan);
  opacity:.7;
}
.research-v2.profile-field-v3 .market-read,
.research-v2.profile-field-v3 .kpi-cell,
.research-v2.profile-field-v3 .highlight-card,
.research-v2.profile-field-v3 .oc-card,
.research-v2.profile-field-v3 .filter-strip,
.research-v2.profile-field-v3 .table-wrap,
.research-v2.profile-field-v3 .global-empty-state{
  border-color:var(--rm-line);
  background:var(--rm-surface);
  box-shadow:none;
  backdrop-filter:none;
}
.research-v2.profile-field-v3 .market-read{
  height:auto;
  padding:20px 22px;
  border-radius:var(--radius);
  background:linear-gradient(160deg,var(--rm-surface) 0%,var(--rm-surface-2) 100%);
  box-shadow:0 18px 50px rgba(0,0,0,.35);
  position:relative;
  overflow:hidden;
}
.research-v2.profile-field-v3 .market-read::before{
  content:"";
  position:absolute;
  left:0;
  right:0;
  top:0;
  height:2px;
  background:var(--spectrum);
  opacity:.55;
}
.research-v2.profile-field-v3 .market-read h2{
  margin:0 0 15px;
  color:var(--rm-dim);
  font-family:var(--mono);
  font-size:.64rem;
  font-weight:700;
  letter-spacing:2px;
  text-transform:uppercase;
  filter:none;
}
.research-v2.profile-field-v3 .market-read .mix-row{
  display:flex;
  grid-template-columns:none;
  align-items:center;
  gap:12px;
  min-height:0;
  padding:6px 0;
  color:inherit;
  font-size:inherit;
}
.research-v2.profile-field-v3 .market-read .mix-row+.mix-row{
  border-top:1px solid var(--rm-line-soft);
}
.research-v2.profile-field-v3 .market-read .mix-row .signal-badge{
  flex:0 0 92px;
  min-width:0;
  justify-content:center;
  justify-self:auto;
  text-align:center;
}
.research-v2.profile-field-v3 .market-read .mix-row .mix-bar{
  flex:1;
  height:6px;
  border-radius:4px;
  background:var(--rm-surface-3);
}
.research-v2.profile-field-v3 .market-read .mix-row strong{
  flex:0 0 34px;
  color:var(--rm-text);
  font-family:var(--mono);
  font-size:.88rem;
  font-weight:700;
  text-align:right;
}
.research-v2.profile-field-v3 .kpi-cell{
  position:relative;
  overflow:hidden;
  border-radius:var(--radius-sm);
  background:var(--rm-surface);
  box-shadow:none;
  transition:transform .25s var(--ease),border-color .25s ease,box-shadow .25s ease,background .25s ease;
}
.research-v2.profile-field-v3 .kpi-cell:hover{
  transform:translateY(-3px);
  border-color:#243048;
  background:var(--rm-surface-2);
  box-shadow:0 14px 34px rgba(0,0,0,.40);
}
.research-v2.profile-field-v3 .highlight-card{
  position:relative;
  overflow:hidden;
  border-radius:var(--radius);
  background:var(--rm-surface);
  box-shadow:none;
  transition:transform .25s var(--ease),border-color .25s ease,box-shadow .25s ease,background .25s ease;
}
.research-v2.profile-field-v3 .highlight-card:hover{
  transform:translateY(-2px);
  border-color:#243048;
  box-shadow:0 18px 44px rgba(0,0,0,.42);
}
.research-v2.profile-field-v3 .highlight-card::before{
  content:"";
  position:absolute;
  left:0;
  right:0;
  top:0;
  height:2px;
}
.research-v2.profile-field-v3 .highlight-card.opportunities::before{
  background:linear-gradient(90deg,var(--rm-green),transparent 80%);
}
.research-v2.profile-field-v3 .highlight-card.risks::before{
  background:linear-gradient(90deg,var(--rm-red),transparent 80%);
}
.research-v2.profile-field-v3 .oc-card{
  position:relative;
  overflow:hidden;
  background:linear-gradient(165deg,var(--rm-surface) 0%,var(--rm-surface-2) 100%);
  box-shadow:none;
  transition:transform .28s var(--ease),border-color .28s ease,box-shadow .28s ease;
}
.research-v2.profile-field-v3 .oc-card::before{
  content:"";
  position:absolute;
  top:-60px;
  right:-60px;
  width:180px;
  height:180px;
  border-radius:50%;
  background:radial-gradient(closest-side,rgba(38,208,232,.09),transparent);
  pointer-events:none;
}
.research-v2.profile-field-v3 .oc-card:hover{
  transform:translateY(-3px);
  border-color:#243048;
  box-shadow:0 18px 48px rgba(0,0,0,.45);
}
.research-v2.profile-field-v3 .filter-strip{
  position:relative;
  top:auto;
  z-index:auto;
  background:var(--rm-surface);
  box-shadow:none;
}
.research-v2.profile-field-v3 .t-assets{
  width:100%;
  min-width:1440px;
  table-layout:fixed;
}
.research-v2.profile-field-v3 .t-assets th,
.research-v2.profile-field-v3 .t-assets td{
  box-sizing:border-box;
}
.research-v2.profile-field-v3 .t-assets th:nth-child(1),
.research-v2.profile-field-v3 .t-assets td:nth-child(1){width:86px}
.research-v2.profile-field-v3 .t-assets th:nth-child(2),
.research-v2.profile-field-v3 .t-assets td:nth-child(2){width:320px}
.research-v2.profile-field-v3 .t-assets th:nth-child(3),
.research-v2.profile-field-v3 .t-assets td:nth-child(3){width:160px}
.research-v2.profile-field-v3 .t-assets th:nth-child(4),
.research-v2.profile-field-v3 .t-assets td:nth-child(4){width:122px}
.research-v2.profile-field-v3 .t-assets th:nth-child(5),
.research-v2.profile-field-v3 .t-assets td:nth-child(5),
.research-v2.profile-field-v3 .t-assets th:nth-child(6),
.research-v2.profile-field-v3 .t-assets td:nth-child(6){width:132px}
.research-v2.profile-field-v3 .t-assets th:nth-child(7),
.research-v2.profile-field-v3 .t-assets td:nth-child(7){width:106px}
.research-v2.profile-field-v3 .t-assets th:nth-child(8),
.research-v2.profile-field-v3 .t-assets td:nth-child(8){width:116px}
.research-v2.profile-field-v3 .t-assets th:nth-child(9),
.research-v2.profile-field-v3 .t-assets td:nth-child(9){width:128px}
.research-v2.profile-field-v3 .t-assets th:nth-child(10),
.research-v2.profile-field-v3 .t-assets td:nth-child(10){width:138px}
.research-v2.profile-field-v3 .t-assets th:nth-child(4),
.research-v2.profile-field-v3 .col-price{
  text-align:right;
}
.research-v2.profile-field-v3 .t-assets th:nth-child(5),
.research-v2.profile-field-v3 .t-assets th:nth-child(6),
.research-v2.profile-field-v3 .t-assets th:nth-child(7),
.research-v2.profile-field-v3 .col-rsi,
.research-v2.profile-field-v3 .col-dd{
  text-align:right;
}
.research-v2.profile-field-v3 .t-assets th:nth-child(8),
.research-v2.profile-field-v3 .t-assets th:nth-child(9),
.research-v2.profile-field-v3 .t-assets th:nth-child(10),
.research-v2.profile-field-v3 .col-chart,
.research-v2.profile-field-v3 .col-sig,
.research-v2.profile-field-v3 .col-vol{
  text-align:center;
}
.research-v2.profile-field-v3 .col-rsi .rsi-meter,
.research-v2.profile-field-v3 .col-dd .dd-pill{
  margin-left:auto;
  margin-right:0;
}
.research-v2.profile-field-v3 .col-chart .dd-ico,
.research-v2.profile-field-v3 .col-sig .signal-badge,
.research-v2.profile-field-v3 .col-vol .vol-badge{
  margin-left:auto;
  margin-right:auto;
}
.research-v2.profile-field-v3 .name-cell{
  display:block;
  min-width:0;
}
.research-v2.profile-field-v3 .name-cell .cn-txt{
  display:block;
  min-width:0;
}
.research-v2.profile-field-v3 .col-sector{
  color:var(--rm-muted);
}
.research-v2.profile-field-v3 .col-sector .sec-tag{
  margin-left:0;
  max-width:100%;
}
.research-v2.profile-field-v3 .sec-na{
  color:var(--rm-dim);
  font-family:var(--mono);
  font-size:.72rem;
}
.research-v2.profile-field-v3 .fbtn{
  --btn-accent:var(--rm-cyan);
  color:var(--btn-accent);
  border-color:color-mix(in srgb,var(--btn-accent) 30%,transparent);
  background:color-mix(in srgb,var(--btn-accent) 7%,transparent);
  transition:opacity .18s ease,filter .18s ease,background .18s ease,border-color .18s ease,color .18s ease;
}
.research-v2.profile-field-v3 .fbtn:hover{
  color:var(--rm-text);
  border-color:color-mix(in srgb,var(--btn-accent) 50%,transparent);
  background:color-mix(in srgb,var(--btn-accent) 12%,transparent);
}
.research-v2.profile-field-v3 .fbtn.active{
  color:var(--btn-accent);
  border-color:color-mix(in srgb,var(--btn-accent) 58%,transparent);
  background:color-mix(in srgb,var(--btn-accent) 14%,transparent);
  box-shadow:0 0 18px color-mix(in srgb,var(--btn-accent) 10%,transparent);
}
.research-v2.profile-field-v3 .filter-group.has-selection .fbtn.is-muted{
  opacity:.34;
  filter:saturate(.55);
}
.research-v2.profile-field-v3 .filter-group.has-selection .fbtn.is-muted:hover{
  opacity:.72;
  filter:saturate(.9);
}
.research-v2.profile-field-v3 .fbtn[data-filter="all"],
.research-v2.profile-field-v3 .fbtn[data-market="all"]{--btn-accent:var(--rm-cyan)}
.research-v2.profile-field-v3 .fbtn[data-filter="UltraBuy"],
.research-v2.profile-field-v3 .fbtn[data-filter="Buy"]{--btn-accent:var(--rm-green)}
.research-v2.profile-field-v3 .fbtn[data-filter="Neutral"]{--btn-accent:var(--rm-blue)}
.research-v2.profile-field-v3 .fbtn[data-filter="Sell"]{--btn-accent:var(--rm-red)}
.research-v2.profile-field-v3 .fbtn[data-market="indices"]{--btn-accent:#7aa2ff}
.research-v2.profile-field-v3 .fbtn[data-market="cripto"]{--btn-accent:#f5c34b}
.research-v2.profile-field-v3 .fbtn[data-market="eua"]{--btn-accent:#26d0e8}
.research-v2.profile-field-v3 .fbtn[data-market="etf"]{--btn-accent:#a78bfa}
.research-v2.profile-field-v3 .fbtn[data-market="commodities"]{--btn-accent:#ff8a5c}
.research-v2.profile-field-v3 .fbtn[data-market="brasil"]{--btn-accent:#2ee6a6}
.research-v2.profile-field-v3 .fbtn[data-market="moeda"]{--btn-accent:#e879a0}
.research-v2.profile-field-v3 .fbtn.sec-chip{
  --btn-accent:var(--sc,var(--rm-cyan));
}
.research-v2.profile-field-v3 .vol-high{
  color:var(--rm-green);
  background:rgba(46,230,166,.11);
  border-color:rgba(46,230,166,.36);
}
.research-v2.profile-field-v3 .vol-low{
  color:var(--rm-red);
  background:rgba(255,100,114,.10);
  border-color:rgba(255,100,114,.34);
}
.research-v2.profile-field-v3 .oc-grid{
  grid-template-columns:repeat(3,minmax(0,1fr));
  gap:18px;
}
.research-v2.profile-field-v3 .oc-card{min-width:0}
.research-v2.profile-field-v3 .fg-card .oc-body{gap:18px}
.research-v2.profile-field-v3 .fg-card .oc-gauge{flex:0 0 136px}
.research-v2.profile-field-v3 .fg-card .oc-metrics{min-width:0;gap:4px}
.research-v2.profile-field-v3 .fg-card .oc-row{gap:14px}
.research-v2.profile-field-v3 .fg-card .oc-k{flex:0 0 auto}
.research-v2.profile-field-v3 .fg-card .oc-v{
  min-width:0;
  text-align:right;
  overflow-wrap:anywhere;
}
.research-v2.profile-field-v3 .fg-card .oc-footer{
  justify-content:space-between;
  gap:12px;
}
.research-v2.profile-field-v3 .fg-card .oc-action-val{
  text-align:right;
  overflow-wrap:anywhere;
}
.research-v2.profile-field-v3 .sig-neutral{
  color:#8eb6ff;
  background:rgba(111,168,255,.16);
  border-color:rgba(111,168,255,.46);
  box-shadow:0 0 12px rgba(111,168,255,.12);
}
.research-v2.profile-field-v3 .oc-risk-pill{
  font-family:var(--mono);
  color:var(--rm-muted);
  border:1px solid var(--rm-line-soft);
  background:rgba(148,170,200,.07);
}
.research-v2.profile-field-v3 .oc-risk-pill.risk-low{
  color:var(--rm-green);
  border-color:color-mix(in srgb,var(--rm-green) 40%,transparent);
  background:color-mix(in srgb,var(--rm-green) 10%,transparent);
}
.research-v2.profile-field-v3 .oc-risk-pill.risk-medium{
  color:var(--rm-yellow);
  border-color:color-mix(in srgb,var(--rm-yellow) 44%,transparent);
  background:color-mix(in srgb,var(--rm-yellow) 10%,transparent);
  box-shadow:0 0 16px color-mix(in srgb,var(--rm-yellow) 13%,transparent);
}
.research-v2.profile-field-v3 .oc-risk-pill.risk-medium-high{
  color:#ffb86c;
  border-color:rgba(255,184,108,.44);
  background:rgba(255,184,108,.10);
  box-shadow:0 0 16px rgba(255,184,108,.12);
}
.research-v2.profile-field-v3 .oc-risk-pill.risk-high{
  color:var(--rm-red);
  border-color:color-mix(in srgb,var(--rm-red) 42%,transparent);
  background:color-mix(in srgb,var(--rm-red) 10%,transparent);
}
.research-v2.profile-field-v3 .highlight-row{
  position:relative;
  gap:12px;
  transition:background .2s ease,transform .2s var(--ease);
}
.research-v2.profile-field-v3 .highlight-row::before{
  content:"";
  position:absolute;
  left:0;
  top:0;
  bottom:0;
  width:2px;
  background:transparent;
  transition:background .2s ease;
}
.research-v2.profile-field-v3 .highlight-row:hover{
  background:var(--rm-surface-2);
}
.research-v2.profile-field-v3 .opportunities .highlight-row:hover::before{
  background:var(--rm-green);
}
.research-v2.profile-field-v3 .risks .highlight-row:hover::before{
  background:var(--rm-red);
}
.research-v2.profile-field-v3 .highlight-rank{
  flex:0 0 30px;
  width:30px;
  height:24px;
  display:inline-grid;
  place-items:center;
  -webkit-text-stroke:0;
  border:1px solid var(--rm-line-soft);
  border-radius:999px;
  background:rgba(148,170,200,.055);
  font-family:var(--mono);
  font-size:.62rem;
  font-weight:850;
  line-height:1;
  letter-spacing:0;
  opacity:.9;
}
.research-v2.profile-field-v3 .opportunities .highlight-rank{
  color:var(--rm-green);
  border-color:color-mix(in srgb,var(--rm-green) 28%,transparent);
  background:color-mix(in srgb,var(--rm-green) 8%,transparent);
}
.research-v2.profile-field-v3 .risks .highlight-rank{
  color:var(--rm-red);
  border-color:color-mix(in srgb,var(--rm-red) 28%,transparent);
  background:color-mix(in srgb,var(--rm-red) 8%,transparent);
}
.research-v2.profile-field-v3 .highlight-chip.chip-market{
  color:var(--rm-cyan);
  border-color:rgba(67,215,232,.28);
  background:rgba(67,215,232,.08);
}
.research-v2.profile-field-v3 .highlight-chip.rz-green{color:var(--rm-green);border-color:color-mix(in srgb,var(--rm-green) 30%,transparent);background:color-mix(in srgb,var(--rm-green) 9%,transparent)}
.research-v2.profile-field-v3 .highlight-chip.rz-teal{color:var(--rm-cyan);border-color:color-mix(in srgb,var(--rm-cyan) 30%,transparent);background:color-mix(in srgb,var(--rm-cyan) 9%,transparent)}
.research-v2.profile-field-v3 .highlight-chip.rz-blue{color:var(--rm-blue);border-color:color-mix(in srgb,var(--rm-blue) 30%,transparent);background:color-mix(in srgb,var(--rm-blue) 9%,transparent)}
.research-v2.profile-field-v3 .highlight-chip.rz-yellow{color:var(--rm-yellow);border-color:color-mix(in srgb,var(--rm-yellow) 30%,transparent);background:color-mix(in srgb,var(--rm-yellow) 9%,transparent)}
.research-v2.profile-field-v3 .highlight-chip.rz-red{color:var(--rm-red);border-color:color-mix(in srgb,var(--rm-red) 30%,transparent);background:color-mix(in srgb,var(--rm-red) 9%,transparent)}
.research-v2.profile-field-v3 .highlight-chip.rz-na{color:var(--rm-dim);border-color:var(--rm-line-soft);background:rgba(148,170,200,.055)}
.research-v2.profile-field-v3 .highlight-chip.dd-flat{color:var(--rm-cyan);border-color:rgba(67,215,232,.28);background:rgba(67,215,232,.08)}
.research-v2.profile-field-v3 .highlight-chip.dd-mild{color:var(--rm-yellow);border-color:rgba(241,188,75,.32);background:rgba(241,188,75,.09)}
.research-v2.profile-field-v3 .highlight-chip.dd-deep,
.research-v2.profile-field-v3 .highlight-chip.dd-stress{color:var(--rm-red);border-color:rgba(240,111,104,.32);background:rgba(240,111,104,.09)}
.research-v2.profile-field-v3 .sector-grid{
  grid-template-columns:repeat(4,minmax(0,1fr));
  gap:16px;
}
.research-v2.profile-field-v3 .sec-card{padding:16px 18px}
.research-v2.profile-field-v3 .sc-name{font-size:.96rem}
.research-v2.profile-field-v3 .sc-n{font-size:.82rem}
.research-v2.profile-field-v3 .sc-stats{
  display:grid;
  grid-template-columns:repeat(2,minmax(0,1fr));
  gap:7px 10px;
  align-items:center;
  margin-bottom:10px;
  font-size:.78rem;
}
.research-v2.profile-field-v3 .sc-stats b{font-size:.95rem}
.research-v2.profile-field-v3 .rz-na{color:var(--rm-dim)}
.research-v2.profile-field-v3 .sc-stats span{min-width:0;white-space:nowrap}
.research-v2.profile-field-v3 .sc-flow{
  grid-column:1/-1;
  padding-top:2px;
  color:var(--rm-dim);
}
body.research-v2.profile-field-v3.theme-light{
  background:
    conic-gradient(from 218deg at 10% -14%,rgba(13,127,158,.12),transparent 24%,rgba(10,143,99,.08) 38%,transparent 60%),
    conic-gradient(from 42deg at 94% 2%,rgba(211,58,70,.08),transparent 25%,rgba(13,127,158,.08) 48%,transparent 68%),
    linear-gradient(180deg,#f5f7fb 0%,#eef2f7 52%,#e8edf4 100%);
}
body.research-v2.profile-field-v3.theme-light::before{
  background:
    linear-gradient(rgba(30,45,70,.05) 1px,transparent 1px),
    linear-gradient(90deg,rgba(30,45,70,.04) 1px,transparent 1px),
    radial-gradient(circle,rgba(13,127,158,.22) 0 1px,transparent 1.45px);
  background-size:72px 72px,72px 72px,42px 42px;
  mix-blend-mode:multiply;
  opacity:.34;
}
body.research-v2.profile-field-v3.theme-light::after{
  opacity:.16;
  mix-blend-mode:multiply;
}
.research-v2.profile-field-v3.theme-light .topbar{
  background:rgba(255,255,255,.9);
}
.research-v2.profile-field-v3.theme-light .v2nav{
  background:rgba(255,255,255,.72);
  border-bottom-color:var(--rm-line);
}
.research-v2.profile-field-v3.theme-light .v2nav.scrolled{
  background:rgba(255,255,255,.84);
  box-shadow:0 10px 24px rgba(15,30,45,.1);
}
.research-v2.profile-field-v3.theme-light .v2nav-link.active{
  background:rgba(14,116,144,.1);
  border-color:rgba(14,116,144,.3);
}
.research-v2.profile-field-v3.theme-light .sig-neutral{
  color:var(--rm-blue);
  background:rgba(29,78,216,.1);
  border-color:rgba(29,78,216,.28);
  box-shadow:none;
}
@keyframes v3AmbientField{
  from{background-position:0 0,100% 0,0 0,0 0,0 0}
  to{background-position:16% 8%,84% 9%,0 0,0 0,0 0}
}
@keyframes v3DataGrid{
  to{background-position:72px 72px,72px 72px,36px 36px,-108px 108px}
}
@keyframes v3DataStream{
  from{background-position:0 0,0 0,0 0;opacity:.42}
  to{background-position:130px -84px,-108px 96px,0 0;opacity:.58}
}
@media (max-width:1320px){
  .research-v2.profile-field-v3 .sector-grid{grid-template-columns:repeat(3,minmax(0,1fr))}
}
@media (max-width:1180px){
  .research-v2.profile-field-v3 .executive-board{grid-template-columns:1fr}
  .research-v2.profile-field-v3 .oc-grid{grid-template-columns:1fr}
  .research-v2.profile-field-v3 .fg-card .oc-gauge{flex-basis:150px}
}
@media (max-width:1000px){
  .research-v2.profile-field-v3 .sector-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
}
@media (max-width:760px){
  .research-v2.profile-field-v3 .executive-board,
  .research-v2.profile-field-v3 .kpi-strip,
  .research-v2.profile-field-v3 .desk-highlights,
  .research-v2.profile-field-v3 .main,
  .research-v2.profile-field-v3 .footer{
    padding-left:16px;
    padding-right:16px;
  }
  .research-v2.profile-field-v3 .v2nav{padding-left:16px;padding-right:16px}
  .research-v2.profile-field-v3 .executive-board{padding-top:30px}
  .research-v2.profile-field-v3 .sector-grid{grid-template-columns:1fr}
  .research-v2.profile-field-v3 .sc-stats{grid-template-columns:repeat(2,minmax(0,1fr))}
  .research-v2.profile-field-v3 .highlight-rank{flex-basis:28px;width:28px}
}
@media (prefers-reduced-motion:reduce){
  body.research-v2.profile-field-v3,
  body.research-v2.profile-field-v3::before,
  body.research-v2.profile-field-v3::after{
    animation:none!important;
  }
}
"""


RESEARCH_V3_SCRIPT = r"""
(function(){
  "use strict";

  /* ---- Theme toggle (persisted in localStorage) ---- */
  const metaBox = document.querySelector('.topbar-meta');
  const themeBtn = document.createElement('button');
  themeBtn.className = 'theme-btn';
  themeBtn.type = 'button';
  themeBtn.title = 'Toggle light/dark theme';
  themeBtn.setAttribute('aria-label', 'Toggle light/dark theme');
  function applyTheme(t){
    document.body.classList.toggle('theme-light', t === 'light');
    themeBtn.textContent = t === 'light' ? '☾' : '☀';
  }
  const themeKey = 'fm-theme-official';
  let theme = 'dark';
  try { theme = localStorage.getItem(themeKey) || 'dark'; } catch(e){}
  applyTheme(theme);
  themeBtn.addEventListener('click', function(){
    theme = theme === 'light' ? 'dark' : 'light';
    try { localStorage.setItem(themeKey, theme); } catch(e){}
    applyTheme(theme);
  });
  if(metaBox) metaBox.appendChild(themeBtn);

  /* ---- topbar / quick-nav elevation and scrollspy ---- */
  const topbar = document.querySelector('.topbar');
  const nav = document.querySelector('.v2nav');
  function setChromeVars(){
    const topbarH = topbar ? topbar.offsetHeight : 72;
    const navH = nav ? nav.offsetHeight : 0;
    document.documentElement.style.setProperty('--topbar-h', topbarH + 'px');
    document.documentElement.style.setProperty('--chrome-h', (topbarH + navH) + 'px');
  }
  function onChromeScroll(){
    const scrolled = window.scrollY > 8;
    if(topbar) topbar.classList.toggle('scrolled', scrolled);
    if(nav) nav.classList.toggle('scrolled', scrolled);
  }
  window.addEventListener('resize', setChromeVars, {passive:true});
  window.addEventListener('scroll', onChromeScroll, {passive:true});
  setChromeVars();
  onChromeScroll();

  const navLinks = Array.prototype.slice.call(document.querySelectorAll('.v2nav-link'));
  const navTargets = navLinks
    .map(function(link){ return document.querySelector(link.getAttribute('href')); })
    .filter(Boolean);
  function targetTop(el){ return el.getBoundingClientRect().top + window.scrollY; }
  function updateNavSpy(){
    if(!navTargets.length) return;
    const marker = window.scrollY + 170;
    let current = navTargets[0];
    navTargets.forEach(function(target){
      if(targetTop(target) <= marker) current = target;
    });
    navLinks.forEach(function(link){
      link.classList.toggle('active', link.getAttribute('href') === '#' + current.id);
    });
  }
  window.addEventListener('scroll', updateNavSpy, {passive:true});
  updateNavSpy();

  /* ---- Expandable asset rows ---- */
  function closeDetail(row){
    row.classList.remove('expanded');
    row.setAttribute('aria-expanded', 'false');
    if(row._detail && row._detail.parentNode) row._detail.parentNode.removeChild(row._detail);
    row._detail = null;
  }
  function closeAllDetails(){
    document.querySelectorAll('.asset-row.expanded').forEach(closeDetail);
  }
  function openDetail(row){
    const d = row.dataset;
    const yahoo = d.yahoo ? '<a class="detail-link" target="_blank" rel="noopener" href="' + d.yahoo + '">Yahoo Finance ↗</a>' : '';
    const tv = d.tv ? '<a class="detail-link" target="_blank" rel="noopener" href="' + d.tv + '">TradingView ↗</a>' : '';
    const tr = document.createElement('tr');
    tr.className = 'asset-detail';
    tr.innerHTML = '<td colspan="' + row.children.length + '"><div class="detail-inner">'
      + '<span class="detail-item"><span class="k">Peak close</span><span class="v">' + (d.peakClose || '—') + '</span></span>'
      + '<span class="detail-item"><span class="k">Peak date</span><span class="v">' + (d.peakDate || '—') + '</span></span>'
      + '<span class="detail-item"><span class="k">From peak</span><span class="v">' + (d.dd || '—') + '</span></span>'
      + '<span class="detail-links">' + yahoo + tv + '</span>'
      + '</div></td>';
    row.after(tr);
    row._detail = tr;
    row.classList.add('expanded');
    row.setAttribute('aria-expanded', 'true');
  }
  document.querySelectorAll('.asset-row').forEach(function(row){
    row.tabIndex = 0;
    row.setAttribute('aria-expanded', 'false');
    row.addEventListener('click', function(e){
      if(e.target.closest('a')) return;
      if(row.classList.contains('expanded')) closeDetail(row); else openDetail(row);
    });
    row.addEventListener('keydown', function(e){
      if(e.key === 'Enter' || e.key === ' '){ e.preventDefault(); row.click(); }
    });
  });
  // Sorting re-appends every <tr>; close details first (capture runs before the sort handler).
  document.addEventListener('click', function(e){
    if(e.target.closest && e.target.closest('.th-sort')) closeAllDetails();
  }, true);
  // Filters toggle [hidden] on rows; close the detail of any row that disappears.
  const mo = new MutationObserver(function(muts){
    muts.forEach(function(m){
      const el = m.target;
      if(el.classList && el.classList.contains('asset-row') && el.hidden && el._detail) closeDetail(el);
    });
  });
  document.querySelectorAll('.t-assets tbody').forEach(function(tb){
    mo.observe(tb, {attributes: true, subtree: true, attributeFilter: ['hidden']});
  });
})();
"""


# ==============================================================
# DRAWDOWN MODAL — inline chart of historical drawdown per asset
# ==============================================================
DRAWDOWN_CSS = """
/* ===== DRAWDOWN ICON + MODAL ===== */
.research-v2 .cn-txt{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.research-v2 .th-c{text-align:center}
.research-v2 .col-chart{text-align:center;white-space:nowrap}
.research-v2 .dd-na{color:var(--rm-dim);opacity:.5}
/* ===== WEEKLY VOLUME BADGE ===== */
.research-v2 .col-vol{text-align:center;white-space:nowrap}
.research-v2 .vol-badge{display:inline-flex;align-items:center;gap:5px;font-weight:800;font-size:.72rem;
  font-variant-numeric:tabular-nums;padding:3px 9px;border-radius:5px;border:1px solid transparent}
.research-v2 .vol-badge small{font-weight:600;font-size:.68rem;opacity:.9}
.research-v2 .vol-high{color:var(--rm-cyan);background:rgba(67,215,232,.1);border-color:rgba(67,215,232,.28)}
.research-v2 .vol-low{color:var(--rm-muted);background:rgba(148,171,182,.08);border-color:var(--rm-line)}
.research-v2 .vol-na{color:var(--rm-dim);opacity:.5}
.research-v2 .dd-ico{width:26px;height:26px;display:inline-grid;place-items:center;cursor:pointer;
  border:1px solid color-mix(in srgb,var(--rm-red) 28%,var(--rm-line));border-radius:7px;
  background:color-mix(in srgb,var(--rm-red) 5%,transparent);color:var(--rm-red);padding:0;transition:.16s}
.research-v2 .dd-ico:hover{color:#fff;border-color:var(--rm-red);
  background:linear-gradient(150deg,var(--rm-red),var(--rm-yellow));transform:translateY(-1px)}
.research-v2.theme-light .dd-ico:hover{color:#fff}
.research-v2 .dd-ico svg{width:14px;height:14px}

.dd-modal{border:none;padding:0;background:transparent;max-width:min(940px,94vw);width:100%;color:var(--rm-text)}
.dd-modal::backdrop{background:rgba(4,7,11,.66);backdrop-filter:blur(4px)}
.dd-card{position:relative;border-radius:16px;overflow:hidden;background:var(--rm-surface);
  border:1px solid var(--rm-line);box-shadow:var(--rm-shadow);
  font-family:"Segoe UI",Inter,system-ui,-apple-system,sans-serif}
.dd-card::before{content:"";position:absolute;inset:0 0 auto 0;height:3px;
  background:linear-gradient(90deg,var(--rm-red),var(--rm-yellow))}
.dd-head{display:flex;align-items:center;justify-content:space-between;gap:14px;padding:18px 22px 10px}
.dd-title{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;min-width:0}
.dd-title .nm{font-size:1.15rem;font-weight:800;letter-spacing:-.01em;color:#fff}
.dd-title .tk{font-size:.7rem;font-weight:700;color:var(--rm-muted);border:1px solid var(--rm-line);border-radius:6px;padding:3px 7px}
.dd-title .src{font-size:.7rem;color:var(--rm-dim)}
.research-v2.theme-light .dd-title .nm{color:var(--rm-text)}
.dd-x{flex:none;cursor:pointer;width:32px;height:32px;border-radius:8px;border:1px solid var(--rm-line);
  background:transparent;color:var(--rm-muted);font-size:1.2rem;line-height:1;display:grid;place-items:center;transition:.15s}
.dd-x:hover{color:var(--rm-text);border-color:var(--rm-red)}
.dd-chips{display:flex;flex-wrap:wrap;gap:8px;padding:2px 22px 4px}
.dd-chip{border:1px solid var(--rm-line);background:var(--rm-surface-2);border-radius:10px;padding:7px 11px;min-width:92px}
.dd-chip .k{display:block;font-size:.6rem;text-transform:uppercase;letter-spacing:.05em;color:var(--rm-dim);margin-bottom:2px}
.dd-chip .v{font-size:.95rem;font-weight:800;font-variant-numeric:tabular-nums}
.dd-chip .v small{font-size:.68rem;font-weight:600;color:var(--rm-muted);margin-left:3px}
.dd-chip .v.neg{color:var(--rm-red)} .dd-chip .v.pos{color:var(--rm-green)} .dd-chip .v.warn{color:var(--rm-yellow)}
.dd-plot{padding:4px 12px 6px}
.dd-plot h4{margin:12px 10px 0;font-size:.66rem;font-weight:700;color:var(--rm-muted);text-transform:uppercase;letter-spacing:.06em}
svg.dd-chart{display:block;width:100%;height:auto;overflow:visible}
.dd-gl{stroke:var(--rm-line-soft);stroke-width:1}
.dd-ax{fill:var(--rm-dim);font-size:11px}
.dd-ln{fill:none;stroke:var(--rm-red);stroke-width:2;stroke-linejoin:round}
.dd-zero{stroke:var(--rm-muted);stroke-width:1;opacity:.5}
.dd-pct{stroke-width:1;stroke-dasharray:5 4;opacity:.85}
.dd-pctx{font-size:10.5px;font-weight:700}
.dd-pl{fill:none;stroke:var(--rm-cyan);stroke-width:1.7}
.dd-al{fill:none;stroke:var(--rm-dim);stroke-width:1;stroke-dasharray:4 3;opacity:.7}
.dd-dot{stroke:#fff;stroke-width:1.4}
.dd-mklbl{font-size:10.5px;font-weight:800}
.dd-cross{stroke:var(--rm-muted);stroke-width:1;opacity:.55;stroke-dasharray:3 3}
.dd-hov{fill:var(--rm-red);stroke:#fff;stroke-width:1.5}
.dd-tip{position:fixed;pointer-events:none;z-index:99999;background:var(--rm-surface-3);color:var(--rm-text);
  border:1px solid var(--rm-line);border-radius:8px;padding:6px 9px;font-size:.72rem;
  box-shadow:var(--rm-shadow);opacity:0;transition:opacity .1s;white-space:nowrap;
  font-family:"Segoe UI",Inter,system-ui,sans-serif}
.dd-tip .td{color:var(--rm-dim);font-size:.62rem} .dd-tip b{font-variant-numeric:tabular-nums}
@keyframes ddDraw{to{stroke-dashoffset:0}}

/* ===== SECTOR PULSE + SECTOR FILTER ===== */
.research-v2 .section-title .sp-hint{font-size:.68rem;font-weight:600;color:var(--rm-dim);
  text-transform:none;letter-spacing:0;margin-left:2px}
.research-v2 .sector-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(248px,1fr));
  gap:13px;margin-bottom:34px}
.research-v2 .sec-card{position:relative;overflow:hidden;cursor:pointer;padding:13px 15px;
  border:1px solid var(--rm-line);border-radius:11px;background:var(--rm-surface);transition:.16s}
.research-v2 .sec-card::before{content:"";position:absolute;inset:0 auto 0 0;width:3px;background:var(--sc)}
.research-v2 .sec-card:hover{transform:translateY(-2px);border-color:var(--sc);box-shadow:var(--rm-shadow)}
.research-v2 .sec-card.active{border-color:var(--sc);
  background:color-mix(in srgb,var(--sc) 10%,var(--rm-surface))}
.research-v2 .sec-card.dimmed{opacity:.38}
.research-v2 .sc-head{display:flex;align-items:center;gap:8px;margin-bottom:9px}
.research-v2 .sc-ico{font-size:1.02rem}
.research-v2 .sc-name{font-weight:800;font-size:.88rem}
.research-v2 .sc-n{margin-left:auto;font-family:var(--mono);font-size:.76rem;font-weight:800;
  color:var(--sc);border:1px solid var(--rm-line);border-radius:6px;padding:1px 8px}
.research-v2 .sc-bar{display:flex;height:6px;gap:2px;border-radius:4px;overflow:hidden;
  margin-bottom:9px;background:rgba(148,171,182,.08)}
.research-v2 .seg-g{background:var(--rm-green)}
.research-v2 .seg-b{background:#3f5b82}
.research-v2 .seg-r{background:var(--rm-red)}
.research-v2 .sc-stats{display:flex;justify-content:space-between;font-size:.7rem;
  color:var(--rm-muted);margin-bottom:8px}
.research-v2 .sc-stats b{font-family:var(--mono);font-size:.82rem}
.research-v2 .sc-foot{display:flex;justify-content:space-between;font-size:.68rem;color:var(--rm-dim);
  border-top:1px solid var(--rm-line);padding-top:8px}
.research-v2 .sc-best b{color:var(--rm-text);font-family:var(--mono)}
.research-v2 .sc-best i{font-style:normal;font-family:var(--mono);font-weight:800}
.research-v2 .rz-green{color:var(--rm-green)} .research-v2 .rz-teal{color:var(--rm-cyan)}
.research-v2 .rz-blue{color:var(--rm-blue)} .research-v2 .rz-yellow{color:var(--rm-yellow)}
.research-v2 .rz-red{color:var(--rm-red)}
/* sector filter chips (extend .fbtn accent) */
.research-v2 .sec-chip.active{color:var(--rm-text);border-color:var(--sc);
  background:color-mix(in srgb,var(--sc) 14%,transparent)}
.research-v2 .sec-chip.active .fc{color:var(--sc)}
/* inline sector tag in the Name cell */
.research-v2 .sec-tag{display:inline-flex;align-items:center;gap:4px;margin-left:8px;
  font-size:.62rem;font-weight:700;padding:2px 7px;border-radius:999px;white-space:nowrap;
  color:var(--sc);border:1px solid color-mix(in srgb,var(--sc) 34%,transparent);
  background:color-mix(in srgb,var(--sc) 9%,transparent)}
"""


DRAWDOWN_SCRIPT = r"""
(function(){
  "use strict";
  const DATA = window.DD_DATA || {};
  const fmtPct = (v,d)=> (d===undefined?(d=1):0, (v>0?"+":"")+Number(v).toFixed(d)+"%");
  const fmtNum = v => Number(v).toLocaleString("en-US",{maximumFractionDigits:2});
  const W=1000, PADL=52, PADR=58;
  const xOf=(i,n)=> PADL + (n<2?0:i/(n-1))*(W-PADL-PADR);

  function cummax(a){ let m=-Infinity, o=new Array(a.length); for(let i=0;i<a.length;i++){ if(a[i]>m)m=a[i]; o[i]=m; } return o; }
  function dateAt(baseMs,i){ return new Date(baseMs + i*7*86400000); }
  function yearTicks(baseMs,n){
    const out=[]; let last=null;
    for(let i=0;i<n;i++){ const y=dateAt(baseMs,i).getFullYear(); if(y!==last){ out.push({i,y}); last=y; } }
    const step=Math.ceil(out.length/9);
    return out.filter((_,k)=>k%step===0);
  }

  /* ---- lazy modal + tooltip ---- */
  let modal, card, tip;
  function ensureUI(){
    if(modal) return;
    modal=document.createElement("dialog"); modal.className="dd-modal";
    card=document.createElement("div"); card.className="dd-card"; modal.appendChild(card);
    document.body.appendChild(modal);
    tip=document.createElement("div"); tip.className="dd-tip"; document.body.appendChild(tip);
    modal.addEventListener("click",e=>{ if(e.target===modal) modal.close(); });
    modal.addEventListener("close",()=>{ tip.style.opacity=0; });
  }

  function open(key){
    const a=DATA[key]; if(!a) return;
    ensureUI();
    const p=a.p, n=p.length, ath=cummax(p);
    const dd=p.map((v,i)=>(v/ath[i]-1)*100);
    const s=a.st, moeda=a.moeda||"";
    card.innerHTML =
      '<div class="dd-head"><div class="dd-title">'+
        '<span class="nm">'+a.name+'</span><span class="tk">'+a.tk+'</span>'+
        '<span class="src">'+a.years+'y · source '+(a.fonte||"Yahoo")+'</span>'+
      '</div><button class="dd-x" aria-label="Close">&times;</button></div>'+
      '<div class="dd-chips">'+
        chip("Current price", moeda+" "+fmtNum(s.pn), "")+
        chip("Current drawdown", fmtPct(s.cd), s.cd<-15?"neg":"warn")+
        chip("Worst drawdown", fmtPct(s.md)+'<small>'+s.mdd+'</small>', "neg")+
        chip("P95", fmtPct(s.p95), "")+
        chip("Underwater", Math.round(s.uw)+"%", "")+
        chip("CAGR", fmtPct(s.cagr), s.cagr>=0?"pos":"neg")+
      '</div>'+
      '<div class="dd-plot">'+
        '<h4>Price and all-time high (log scale)</h4><div id="ddSp"></div>'+
        '<h4>Drawdown — decline from all-time high</h4><div id="ddMain"></div>'+
      '</div>';
    card.querySelector(".dd-x").onclick=()=>modal.close();
    const baseMs=Date.parse(a.start+"T00:00:00");
    drawSpark(card.querySelector("#ddSp"), p, ath, baseMs, n);
    drawDD(card.querySelector("#ddMain"), a, dd, baseMs, n);
    if(!modal.open) modal.showModal();
  }
  function chip(k,v,cls){ return '<div class="dd-chip"><span class="k">'+k+'</span><span class="v '+cls+'">'+v+'</span></div>'; }

  /* ---- main underwater chart ---- */
  function drawDD(host,a,dd,baseMs,n){
    const s=a.st, H=330, PADT=14, PADB=26;
    const minv=Math.min.apply(null,dd), dHi=Math.max(Math.max.apply(null,dd),0);
    const domHi=dHi>0?dHi*1.15:0.6, domLo=minv*1.06;
    const yOf=v=> PADT + (domHi-v)/(domHi-domLo)*(H-PADT-PADB);
    const worst=dd.indexOf(minv), yZero=yOf(0).toFixed(2);
    let grid="";
    for(let g=0; g>=domLo; g-=20){ if(g>domHi) continue; const y=yOf(g).toFixed(1);
      grid+='<line class="dd-gl" x1="'+PADL+'" x2="'+(W-PADR)+'" y1="'+y+'" y2="'+y+'"/>'+
            '<text class="dd-ax" x="'+(PADL-8)+'" y="'+(+y+3.5)+'" text-anchor="end">'+g+'%</text>'; }
    let xl=""; yearTicks(baseMs,n).forEach(t=>{ const x=xOf(t.i,n).toFixed(1);
      xl+='<text class="dd-ax" x="'+x+'" y="'+(H-6)+'" text-anchor="middle">'+t.y+'</text>'; });
    let line=""; for(let i=0;i<n;i++){ line+=(i?"L":"M")+xOf(i,n).toFixed(1)+" "+yOf(dd[i]).toFixed(2)+" "; }
    const area="M"+PADL+" "+yZero+" "+dd.map((v,i)=>"L"+xOf(i,n).toFixed(1)+" "+yOf(v).toFixed(2)).join(" ")+" L"+(W-PADR)+" "+yZero+" Z";
    let pct="";
    [["P75","--rm-blue",s.p75],["P90","--rm-yellow",s.p90],["P95","--rm-red",s.p95]].forEach(x=>{
      const val=x[2]; if(val<domLo||val>domHi) return; const y=yOf(val).toFixed(1);
      pct+='<line class="dd-pct" x1="'+PADL+'" x2="'+(W-PADR)+'" y1="'+y+'" y2="'+y+'" stroke="var('+x[1]+')"/>'+
           '<text class="dd-pctx" x="'+(W-PADR+4)+'" y="'+(+y+3.5)+'" fill="var('+x[1]+')">'+x[0]+" "+fmtPct(val)+'</text>'; });
    const wx=xOf(worst,n).toFixed(1), wy=yOf(minv).toFixed(1);
    const cx=xOf(n-1,n).toFixed(1), cy=yOf(dd[n-1]).toFixed(1), L=2800;
    host.innerHTML=
      '<svg class="dd-chart" viewBox="0 0 '+W+' '+H+'" preserveAspectRatio="none">'+
      '<defs><linearGradient id="ddg" x1="0" y1="'+yZero+'" x2="0" y2="'+yOf(domLo)+'" gradientUnits="userSpaceOnUse">'+
        '<stop offset="0" stop-color="var(--rm-red)" stop-opacity="0.05"/>'+
        '<stop offset="1" stop-color="var(--rm-red)" stop-opacity="0.45"/></linearGradient></defs>'+
      grid+xl+
      '<path d="'+area+'" fill="url(#ddg)"/>'+
      '<line class="dd-zero" x1="'+PADL+'" x2="'+(W-PADR)+'" y1="'+yZero+'" y2="'+yZero+'"/>'+pct+
      '<path class="dd-ln" d="'+line+'" style="stroke-dasharray:'+L+';stroke-dashoffset:'+L+';animation:ddDraw 1s ease-out forwards"/>'+
      '<circle class="dd-dot" cx="'+wx+'" cy="'+wy+'" r="4.5" fill="var(--rm-red)"/>'+
      '<text class="dd-mklbl" x="'+wx+'" y="'+(+wy+16)+'" fill="var(--rm-red)" text-anchor="'+(worst>n*0.7?"end":"middle")+'">Worst '+fmtPct(minv)+' · '+s.mdd+'</text>'+
      '<circle class="dd-dot" cx="'+cx+'" cy="'+cy+'" r="4" fill="var(--rm-yellow)"/>'+
      '<line class="dd-cross" id="ddC" y1="'+PADT+'" y2="'+(H-PADB)+'" style="opacity:0"/>'+
      '<circle class="dd-hov" id="ddH" r="4.5" style="opacity:0"/>'+
      '<rect id="ddHit" x="'+PADL+'" y="0" width="'+(W-PADL-PADR)+'" height="'+H+'" fill="transparent" style="cursor:crosshair"/>'+
      '</svg>';
    const svg=host.querySelector("svg"), hit=host.querySelector("#ddHit");
    const cross=host.querySelector("#ddC"), hov=host.querySelector("#ddH");
    hit.addEventListener("pointermove",ev=>{
      const r=svg.getBoundingClientRect(); const vx=(ev.clientX-r.left)/r.width*W;
      let i=Math.round((vx-PADL)/(W-PADL-PADR)*(n-1)); i=Math.max(0,Math.min(n-1,i));
      const px=xOf(i,n), py=yOf(dd[i]);
      cross.setAttribute("x1",px); cross.setAttribute("x2",px); cross.style.opacity=1;
      hov.setAttribute("cx",px); hov.setAttribute("cy",py); hov.style.opacity=1;
      const d=dateAt(baseMs,i);
      tip.innerHTML='<span class="td">'+d.toLocaleDateString("en-GB")+'</span><br><b>'+fmtPct(dd[i])+'</b> from ATH';
      tip.style.opacity=1; tip.style.left=(ev.clientX+14)+"px"; tip.style.top=(ev.clientY-10)+"px";
      if(window._ddSync) window._ddSync(i);
    });
    hit.addEventListener("pointerleave",()=>{ cross.style.opacity=0; hov.style.opacity=0; tip.style.opacity=0;
      if(window._ddSync) window._ddSync(-1); });
  }

  /* ---- price + ATH sparkline (log) ---- */
  function drawSpark(host,p,ath,baseMs,n){
    const H=124, PADT=10, PADB=18;
    const lp=p.map(Math.log), la=ath.map(Math.log);
    const lo=Math.min.apply(null,lp), hi=Math.max.apply(null,la), pad=(hi-lo)*0.06||0.1;
    const yOf=v=> PADT + (hi+pad-Math.log(v))/((hi+pad)-(lo-pad))*(H-PADT-PADB);
    const mk=arr=>arr.map((v,i)=>(i?"L":"M")+xOf(i,n).toFixed(1)+" "+yOf(v).toFixed(2)).join(" ");
    let xl=""; yearTicks(baseMs,n).forEach(t=>{ const x=xOf(t.i,n).toFixed(1);
      xl+='<text class="dd-ax" x="'+x+'" y="'+(H-4)+'" text-anchor="middle">'+t.y+'</text>'; });
    const fill="M"+ath.map((v,i)=>xOf(i,n).toFixed(1)+" "+yOf(v).toFixed(2)).join(" L")+
               " L"+p.map((v,i)=>xOf(i,n).toFixed(1)+" "+yOf(v).toFixed(2)).reverse().join(" L")+" Z";
    host.innerHTML=
      '<svg class="dd-chart" viewBox="0 0 '+W+' '+H+'" preserveAspectRatio="none">'+
      '<defs><linearGradient id="ddsp" x1="0" y1="0" x2="0" y2="1">'+
        '<stop offset="0" stop-color="var(--rm-cyan)" stop-opacity=".14"/>'+
        '<stop offset="1" stop-color="var(--rm-cyan)" stop-opacity="0"/></linearGradient></defs>'+
      xl+'<path d="'+fill+'" fill="url(#ddsp)"/>'+
      '<path class="dd-al" d="'+mk(ath)+'"/><path class="dd-pl" d="'+mk(p)+'"/>'+
      '<line class="dd-cross" id="spC" y1="'+PADT+'" y2="'+(H-PADB)+'" style="opacity:0"/>'+
      '<circle class="dd-hov" id="spH" r="3.6" fill="var(--rm-cyan)" style="opacity:0"/>'+
      '</svg>';
    const cross=host.querySelector("#spC"), hov=host.querySelector("#spH");
    window._ddSync=i=>{ if(i<0){cross.style.opacity=0;hov.style.opacity=0;return;}
      const px=xOf(i,n); cross.setAttribute("x1",px);cross.setAttribute("x2",px);cross.style.opacity=1;
      hov.setAttribute("cx",px);hov.setAttribute("cy",yOf(p[i]));hov.style.opacity=1; };
  }

  /* ---- delegated icon click (capture: beat the row-expand handler) ---- */
  document.addEventListener("click",function(e){
    const b=e.target.closest && e.target.closest(".dd-ico");
    if(!b) return;
    e.stopPropagation(); e.preventDefault();
    open(b.getAttribute("data-dd"));
  }, true);
  document.addEventListener("keydown",function(e){
    if((e.key==="Enter"||e.key===" ") && document.activeElement && document.activeElement.classList.contains("dd-ico")){
      e.preventDefault(); e.stopPropagation(); open(document.activeElement.getAttribute("data-dd"));
    }
  }, true);
})();
"""


# ==============================================================
# SIGNAL CHANGES ("What changed") — daily per-asset signal history
# ==============================================================
SIGNAL_CHANGES_CSS = """
/* ===== SIGNAL CHANGES (What changed) + WATCH-ZONE + SIGNAL TIMELINE ===== */
.research-v2.profile-field-v3 #changes{scroll-margin-top:calc(var(--chrome-h,120px) + 12px)}
.research-v2 .wc-section{padding-top:24px;padding-bottom:0}
.research-v2 .wc-card{min-height:0}
/* three cards side by side on wide screens; Near Trigger drops full-width at the
   2-col breakpoint, everything stacks below 980px (inherits desk-highlights 1fr) */
@media(min-width:1301px){.research-v2 .wc-section{grid-template-columns:repeat(3,minmax(0,1fr))}}
@media(min-width:981px) and (max-width:1300px){
  .research-v2 .wc-section{grid-template-columns:repeat(2,minmax(0,1fr))}
  .research-v2 .wc-card.wc-neartrigger{grid-column:1/-1}
}
.research-v2 .wc-card.wc-today h2{color:var(--rm-cyan)}
.research-v2 .wc-card.wc-week h2{color:var(--rm-blue)}
.research-v2 .wc-card.wc-neartrigger h2{color:var(--rm-yellow)}
.research-v2.profile-field-v3 .wc-card.wc-today::before{background:linear-gradient(90deg,var(--rm-cyan),transparent 80%)}
.research-v2.profile-field-v3 .wc-card.wc-week::before{background:linear-gradient(90deg,var(--rm-blue),transparent 80%)}
.research-v2.profile-field-v3 .wc-card.wc-neartrigger::before{background:linear-gradient(90deg,var(--rm-yellow),transparent 80%)}
.research-v2 .wc-row{grid-template-columns:44px minmax(0,1fr) minmax(108px,auto)}
.research-v2 .wc-row .highlight-rank{width:auto;min-width:38px;padding:0 7px;justify-self:start}
.research-v2.profile-field-v3 .wc-today .highlight-rank{color:var(--rm-cyan);border-color:rgba(38,208,232,.28);background:rgba(38,208,232,.08)}
.research-v2.profile-field-v3 .wc-week .highlight-rank{color:var(--rm-blue);border-color:rgba(122,162,255,.28);background:rgba(122,162,255,.08)}
.research-v2.profile-field-v3 .wc-neartrigger .highlight-rank{color:var(--rm-yellow);border-color:rgba(245,195,75,.32);background:rgba(245,195,75,.09)}
.research-v2 .wc-transition{display:flex;align-items:center;gap:5px;justify-content:flex-end;flex-wrap:nowrap}
.research-v2 .wc-transition .signal-badge{font-size:.58rem;padding:3px 7px}
.research-v2 .wc-transition .signal-badge:first-child{opacity:.55;filter:saturate(.6)}
.research-v2 .wc-arr{color:var(--rm-dim);font-weight:800;font-family:var(--mono);margin:0 -1px}
.research-v2 .wc-since{color:var(--rm-dim)}
/* ticker + name mirror Top Opportunities; market stays in the metadata line */
.research-v2 .wc-row .highlight-title .tk-badge{flex:0 0 auto}
.research-v2 .wc-row .highlight-title .highlight-name{flex:1 1 auto;min-width:0}
.research-v2 .wc-row .highlight-meta{flex-wrap:wrap}
.research-v2 .nt-dist{font-weight:800;font-size:.76rem;white-space:nowrap}
.research-v2 .nt-dist.nt-buy{color:var(--rm-green)}
.research-v2 .nt-dist.nt-sell{color:var(--rm-red)}
.research-v2 .wc-empty{padding:16px 2px;color:var(--rm-muted);font-size:.85rem}
.research-v2 .wc-foot{margin-top:10px;padding-top:10px;border-top:1px solid var(--rm-line-soft);color:var(--rm-dim);font-size:.68rem;line-height:1.45}
/* fixed equal-height lists with internal scroll + bottom fade when more remains */
.research-v2 .wc-scrollwrap{position:relative}
.research-v2 .wc-scrollwrap .highlight-list{display:block;height:432px;overflow-y:auto;padding-right:8px;scrollbar-width:thin;scrollbar-color:var(--rm-line) transparent}
.research-v2 .wc-scrollwrap .highlight-list::-webkit-scrollbar{width:8px}
.research-v2 .wc-scrollwrap .highlight-list::-webkit-scrollbar-track{background:transparent}
.research-v2 .wc-scrollwrap .highlight-list::-webkit-scrollbar-thumb{background:var(--rm-line);border-radius:8px}
.research-v2 .wc-scrollwrap .highlight-list::-webkit-scrollbar-thumb:hover{background:var(--rm-dim)}
.research-v2 .wc-scrollwrap::after{content:"";position:absolute;left:0;right:8px;bottom:0;height:46px;border-radius:0 0 8px 8px;background:linear-gradient(180deg,transparent,var(--rm-surface) 86%);pointer-events:none;opacity:0;transition:opacity .2s}
.research-v2 .wc-scrollwrap.has-more::after{opacity:1}
/* clickable locate rows (Signal Changes + Watch-zone + Top Opportunities/Risks) */
.research-v2 .highlight-row[data-goto]{cursor:pointer}
.research-v2 .wc-flash td{background:rgba(38,208,232,.16)!important}
.research-v2.profile-field-v3 .wc-today .highlight-row:hover::before{background:var(--rm-cyan)}
.research-v2.profile-field-v3 .wc-week .highlight-row:hover::before{background:var(--rm-blue)}
.research-v2.profile-field-v3 .wc-neartrigger .highlight-row:hover::before{background:var(--rm-yellow)}
/* --- signal timeline inside the expanded asset row --- */
.research-v2 .wc-tl{display:inline-flex;align-items:center;gap:3px}
.research-v2 .wc-tl-cell{width:11px;height:11px;border-radius:3px;background:var(--rm-surface-3);border:1px solid var(--rm-line-soft)}
.research-v2 .wc-tl-cell.s-ub{background:var(--rm-green);border-color:var(--rm-green);box-shadow:0 0 6px rgba(46,230,166,.5)}
.research-v2 .wc-tl-cell.s-b{background:rgba(46,230,166,.55);border-color:rgba(46,230,166,.7)}
.research-v2 .wc-tl-cell.s-n{background:rgba(122,162,255,.28);border-color:rgba(122,162,255,.34)}
.research-v2 .wc-tl-cell.s-s{background:rgba(255,100,114,.6);border-color:rgba(255,100,114,.75)}
.research-v2 .wc-tl-cell:last-child{outline:1.5px solid var(--rm-text);outline-offset:1px}
@media (max-width:980px){.research-v2 .wc-transition{justify-content:flex-start}}
@media (max-width:560px){
  .research-v2 #changes .highlight-head{
    align-items:flex-start;
    flex-wrap:wrap;
    gap:7px 10px;
  }
  .research-v2 #changes .highlight-head h2{
    flex:1 1 100%;
    line-height:1.18;
  }
  .research-v2 #changes .highlight-head span{
    white-space:normal;
    text-align:left;
  }
  .research-v2 .wc-row{
    grid-template-columns:38px minmax(0,1fr);
    align-items:start;
    gap:8px 10px;
  }
  .research-v2 .wc-row .highlight-signal{
    grid-column:2;
    grid-row:2;
    justify-content:flex-start;
    min-width:0;
    margin-top:1px;
  }
  .research-v2 .wc-row .highlight-name{
    white-space:normal;
    display:-webkit-box;
    -webkit-line-clamp:2;
    -webkit-box-orient:vertical;
    line-height:1.25;
  }
  .research-v2 .wc-row .highlight-meta{gap:5px}
  .research-v2 .wc-transition{flex-wrap:wrap}
  .research-v2 .nt-dist{white-space:normal;line-height:1.25}
}
"""

SIGNAL_CHANGES_SCRIPT = r"""
(function(){
  "use strict";

  /* ---- click any [data-goto] row (Signal Changes, Top Opportunities,
     Top Risks) -> scroll to the asset in the RSI Matrix and flash it ---- */
  document.addEventListener('click', function(e){
    var el = e.target.closest && e.target.closest('[data-goto]');
    if(!el) return;
    if(e.target.closest('a')) return;
    var tk = (el.getAttribute('data-goto')||'').toLowerCase();
    var target = null, fallback = null;
    document.querySelectorAll('.asset-row').forEach(function(row){
      if((row.dataset.ticker||'') !== tk) return;
      if(!fallback) fallback = row;
      if(!target && !row.hidden) target = row;
    });
    target = target || fallback;
    if(!target) return;
    target.scrollIntoView({behavior:'smooth', block:'center'});
    target.classList.add('wc-flash');
    setTimeout(function(){ target.classList.remove('wc-flash'); }, 1800);
  });

  /* ---- daily signal timeline inside the expanded row detail ----
     window.SIGNAL_HISTORY = { TICKER: [["YYYY-MM-DD","Signal"], ...] } */
  var HIST = window.SIGNAL_HISTORY || {};
  var TL_DAYS = 14;
  var CLS = {UltraBuy:'s-ub', Buy:'s-b', Neutral:'s-n', Sell:'s-s'};
  function injectTimeline(row){
    var d = row._detail;
    if(!d || d.querySelector('.wc-detail')) return;
    var tkEl = row.querySelector('.tk-badge');
    var seq = HIST[tkEl ? tkEl.textContent.trim() : ''];
    if(!seq || !seq.length) return;
    var cells = '';
    var shown = seq.slice(-TL_DAYS);
    for(var i = shown.length; i < TL_DAYS; i++)
      cells += '<span class="wc-tl-cell" title="no data"></span>';
    shown.forEach(function(p){
      cells += '<span class="wc-tl-cell '+(CLS[p[1]]||'')+'" title="'+p[0]+' &middot; '+p[1]+'"></span>';
    });
    var wrap = document.createElement('span');
    wrap.className = 'detail-item wc-detail';
    wrap.innerHTML = '<span class="k">Signal &middot; last '+TL_DAYS+'d</span>'
                   + '<span class="v wc-tl">'+cells+'</span>';
    var inner = d.querySelector('.detail-inner');
    if(inner) inner.insertBefore(wrap, inner.querySelector('.detail-links'));
  }
  /* runs after the row's own expand handler (document bubble phase) */
  document.addEventListener('click', function(e){
    var row = e.target.closest && e.target.closest('.asset-row');
    if(row && row.classList.contains('expanded')) injectTimeline(row);
  });

  /* ---- fixed-height card lists: toggle the bottom fade while more remains ---- */
  document.querySelectorAll('#changes .wc-scrollwrap').forEach(function(wrap){
    var list = wrap.querySelector('.highlight-list');
    if(!list) return;
    function sync(){
      var more = list.scrollHeight - list.scrollTop - list.clientHeight > 4;
      wrap.classList.toggle('has-more', more);
    }
    list.addEventListener('scroll', sync, {passive:true});
    window.addEventListener('resize', sync, {passive:true});
    sync();
  });
})();
"""


# ==============================================================
# DATA FETCHING
# ==============================================================
def fetch_rsi_data() -> pd.DataFrame:
    """Fetch weekly/monthly RSI for all assets and return a DataFrame."""
    return collect_rsi_data(remove_crypto_suffix=True)


# ==============================================================
# DRAWDOWN HISTORY (per-asset) — powers the inline chart modal
# ==============================================================
_DD_ICON = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" '
    'stroke-linecap="round" stroke-linejoin="round"><path d="M3 3v18h18"/>'
    '<path d="M7 14l3.5-4.5 3 2.5L20 7"/></svg>'
)
_MONTH_ABBR = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _yahoo_symbol(ticker: str, setor: str) -> str:
    """Rebuild the raw Yahoo symbol from the normalized ticker + group.

    Mirrors :func:`_asset_links`; the DataFrame ticker is normalized
    (``.SA``/``^``/``-USD`` stripped), so the raw symbol is reconstructed here.
    """
    tk = str(ticker).upper()
    if setor == "Indices":
        return "^" + tk
    if setor == "Cripto":
        return tk + "-USD"
    if setor == "Brasil":
        return tk + ".SA"
    return tk  # EUA, ETF, Moeda (BRL=X) e afins usam o símbolo direto


def _dd_currency(setor: str) -> str:
    if setor in ("Brasil", "Moeda"):
        return "R$"
    if setor == "Indices":
        return "pts"
    return "US$"


def _round_px(v: float) -> float:
    v = float(v)
    a = abs(v)
    if a >= 1000:
        return round(v, 1)
    if a >= 10:
        return round(v, 2)
    return round(v, 4)


def _build_dd_entry(close: pd.Series, key: str, name: str, setor: str,
                    anos: int, min_points: int) -> Optional[dict]:
    """Build one drawdown payload entry from a raw weekly Close series.

    Returns ``None`` when the history is too short. Pure computation — shared by
    the batched and single-fetch paths so both yield identical entries."""
    close = close.dropna()
    close = close[close > 0]
    if len(close) < min_points:
        return None
    # Limita à janela dos últimos `anos` (bounda o tamanho do payload).
    cutoff = close.index[-1] - pd.DateOffset(years=anos)
    trimmed = close[close.index >= cutoff]
    if len(trimmed) >= min_points:
        close = trimmed

    ath = close.cummax()
    dd = (close / ath - 1.0) * 100.0

    max_dd = float(dd.min())
    max_dd_ts = dd.idxmin()
    cur_dd = float(dd.iloc[-1])
    years = max((close.index[-1] - close.index[0]).days / 365.25, 0.01)
    cagr = (float(close.iloc[-1]) / float(close.iloc[0])) ** (1.0 / years) - 1.0

    return {
        "name": name,
        "tk": key,
        "moeda": _dd_currency(setor),
        "fonte": "Yahoo",
        "years": round(years, 1),
        "start": close.index[0].strftime("%Y-%m-%d"),
        "p": [_round_px(v) for v in close.values],
        "st": {
            "pn": round(float(close.iloc[-1]), 2),
            "cd": round(cur_dd, 1),
            "md": round(max_dd, 1),
            "mdd": f"{_MONTH_ABBR[max_dd_ts.month]}/{max_dd_ts.year}",
            "p75": round(float(dd.quantile(0.25)), 1),
            "p90": round(float(dd.quantile(0.10)), 1),
            "p95": round(float(dd.quantile(0.05)), 1),
            "uw": round(float((dd < -0.1).mean() * 100), 0),
            "cagr": round(cagr * 100, 1),
        },
    }


def build_drawdown_data(df: pd.DataFrame, anos: int = 20, min_points: int = 40) -> Dict[str, dict]:
    """Bulk-download long weekly history for every asset and build the drawdown payload.

    Returns a dict keyed by the normalized ticker (matching ``df['Ticker']``).
    Uses one batched download (a few HTTP calls) instead of one request per
    asset, with a single-fetch fallback for any symbol the batch misses. Only
    the price series + precomputed stats are stored; the browser derives the ATH
    (cummax) and drawdown curve from the prices to keep the payload small.
    """
    # (normalized_key, setor, yahoo_symbol, name) for each asset row.
    specs = []
    for _, r in df.iterrows():
        key = str(r["Ticker"])
        setor = str(r.get("Setor", ""))
        yahoo_symbol = str(r.get("Yahoo_Ticker") or _yahoo_symbol(key, setor))
        specs.append((key, setor, yahoo_symbol, str(r["Name"])))

    batch = _download_batch([s[2] for s in specs], interval="1wk", period="max")

    data: Dict[str, dict] = {}
    total = len(specs)
    fallbacks = 0
    for pos, (key, setor, sym, name) in enumerate(specs, start=1):
        try:
            sub = batch.get(sym)
            if sub is not None and "Close" in sub.columns:
                close = sub["Close"]
            else:
                # Missing from the batch → single-ticker retry (keeps the chart
                # icon from vanishing on a transient batch hiccup).
                close = yf.Ticker(sym).history(period="max", interval="1wk")["Close"]
                fallbacks += 1

            entry = _build_dd_entry(close, key, name, setor, anos, min_points)
            if entry is None:
                print(f"  [skip] {sym}: histórico curto")
                continue
            data[key] = entry
            print(f"  [ok] ({pos}/{total}) {sym}: {len(entry['p'])} pts")
        except Exception as exc:
            print(f"  [WARN] drawdown {sym}: {exc}")

    if fallbacks:
        print(f"  [batch] drawdown: {fallbacks} via single-fetch fallback")
    return data


def fetch_onchain_data() -> Dict:
    """Fetch on-chain MVRV for BTC and ETH."""
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

    # Fear & Greed Index (não bloqueia caso a API falhe → None).
    data["FNG"] = fear_greed_index(verify_ssl=False)

    return data


# ==============================================================
# HTML GENERATION — V2 Professional Financial Terminal
# ==============================================================
def _signal_class(signal: str) -> str:
    return {"UltraBuy": "sig-ultrabuy", "Buy": "sig-buy", "Neutral": "sig-neutral", "Sell": "sig-sell"}.get(signal, "sig-neutral")


def _signal_label(signal: str) -> str:
    return {"UltraBuy": "ULTRA BUY", "Buy": "BUY", "Neutral": "NEUTRAL", "Sell": "OVERBOUGHT"}.get(signal, signal)


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


def _risk_class(risk: str) -> str:
    r = (risk or "").lower().replace(" ", "")
    if "medium/high" in r or ("medium" in r and "high" in r):
        return "risk-medium-high"
    if "high" in r:
        return "risk-high"
    if "medium" in r:
        return "risk-medium"
    if "low" in r:
        return "risk-low"
    return "risk-neutral"


def _format_price(val: float) -> str:
    if val >= 1000:
        return f"{val:,.0f}"
    if val >= 1:
        return f"{val:,.2f}"
    return f"{val:,.4f}"


def _format_percent(val: float) -> str:
    value = float(val)
    if abs(value) < 0.05:
        value = 0.0
    return f"{value:.1f}%"


def _format_peak_date(value: object) -> str:
    try:
        if pd.isna(value):
            return ""
        return pd.Timestamp(value).strftime("%d/%m/%Y")
    except Exception:
        return ""


def _drawdown_class(value: float) -> str:
    if value >= -10:
        return "dd-flat"
    if value >= -25:
        return "dd-mild"
    if value >= -50:
        return "dd-deep"
    return "dd-stress"


# Monotonic id so each gauge's <linearGradient> gets a unique document id.
_gauge_gid = 0


def _gauge_svg(pct, value_text, color, grad_stops, ticks_pct, lab_min, lab_max, gid) -> str:
    """Semicircular gauge: gradient track, zone-threshold ticks, min/max labels,
    and a value arc that animates in via CSS (see ``.g-arc`` in RESEARCH_V3_CSS)."""
    pct = max(0.0, min(100.0, float(pct)))

    ticks = ""
    for tp in ticks_pct:
        a = math.pi * (1 + tp / 100.0)
        x1, y1 = 60 + 44 * math.cos(a), 60 + 44 * math.sin(a)
        x2, y2 = 60 + 56 * math.cos(a), 60 + 56 * math.sin(a)
        ticks += (f'<line class="g-tick" x1="{x1:.1f}" y1="{y1:.1f}" '
                  f'x2="{x2:.1f}" y2="{y2:.1f}" stroke-width="2.5"/>')

    last = len(grad_stops) - 1
    stops = "".join(
        f'<stop offset="{round(i / last * 100)}%" stop-color="{c}"/>'
        for i, c in enumerate(grad_stops)
    )

    return f'''<svg viewBox="0 0 120 80" class="gauge-svg" role="img">
      <defs><linearGradient id="{gid}" x1="0" y1="0" x2="1" y2="0">{stops}</linearGradient></defs>
      <path d="M 10 60 A 50 50 0 0 1 110 60" fill="none" stroke="url(#{gid})" stroke-opacity=".22" stroke-width="8" stroke-linecap="round"/>
      <path class="g-arc" style="--arc:{pct:.1f}" d="M 10 60 A 50 50 0 0 1 110 60" pathLength="100" fill="none" stroke="{color}" stroke-width="8" stroke-linecap="round"/>
      {ticks}
      <text x="60" y="54" text-anchor="middle" fill="{color}" font-size="15" font-weight="800" class="g-val">{value_text}</text>
      <text x="12" y="76" text-anchor="middle" class="g-lab" font-size="7">{lab_min}</text>
      <text x="108" y="76" text-anchor="middle" class="g-lab" font-size="7">{lab_max}</text>
    </svg>'''


def _mvrv_gauge_svg(mvrv: float, coin: str) -> str:
    """SVG semicircular gauge for MVRV (green = undervalued, red = overvalued)."""
    global _gauge_gid
    lo, hi = (0.5, 3.5) if coin == "BTC" else (0.4, 2.7)
    pct = max(0.0, min(100.0, (mvrv - lo) / (hi - lo) * 100))
    if pct < 25:
        color = "#35d08f"
    elif pct < 50:
        color = "#33c6b7"
    elif pct < 75:
        color = "#f1bc4b"
    else:
        color = "#f06f68"
    _gauge_gid += 1
    return _gauge_svg(
        pct, f"{mvrv:.3f}", color,
        ["#35d08f", "#33c6b7", "#f1bc4b", "#f06f68"],
        [25, 50, 75], f"{lo:g}", f"{hi:g}", f"g{_gauge_gid}",
    )


def _build_onchain_card(coin: str, data: Dict) -> str:
    if data is None:
        return f'''
        <div class="oc-card oc-unavailable">
          <div class="oc-card-head"><span class="oc-icon">{"₿" if coin == "BTC" else "Ξ"}</span><span class="oc-title">{coin}</span></div>
          <p class="oc-na">Data unavailable — retry outside the corporate network</p>
        </div>'''

    zone_cls = _zone_class(data["zone"])
    risk_cls = _risk_class(data["risk"])
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
        <span class="oc-action-label">Action:</span>
        <span class="oc-action-val">{escape(data["action"])}</span>
        <span class="oc-risk-pill {risk_cls}">Risk: {escape(data["risk"])}</span>
      </div>
    </div>'''


def _fng_gauge_svg(value) -> str:
    """SVG semicircular gauge for the Fear & Greed Index (red = fear, green = greed)."""
    global _gauge_gid
    if value is None:
        return '''<svg viewBox="0 0 120 80" class="gauge-svg" role="img">
      <path d="M 10 60 A 50 50 0 0 1 110 60" fill="none" stroke="#2c3650" stroke-width="8" stroke-linecap="round"/>
      <text x="60" y="54" text-anchor="middle" fill="#64748b" font-size="15" font-weight="800" class="g-val">-</text>
    </svg>'''

    v = max(0, min(100, int(value)))
    if v < 25:
        color = "#f06f68"
    elif v < 46:
        color = "#ff7a45"
    elif v < 55:
        color = "#f1bc4b"
    elif v < 76:
        color = "#35d08f"
    else:
        color = "#4ade80"

    _gauge_gid += 1
    return _gauge_svg(
        float(v), str(v), color,
        ["#f06f68", "#ff7a45", "#f1bc4b", "#35d08f", "#4ade80"],
        [25, 46, 55, 76], "0", "100", f"g{_gauge_gid}",
    )


def _fng_class(value, classification: str) -> str:
    c = (classification or "").lower()
    if "extreme fear" in c:
        return "fg-extreme-fear"
    if "extreme greed" in c:
        return "fg-extreme-greed"
    if "fear" in c:
        return "fg-fear"
    if "greed" in c:
        return "fg-greed"
    if "neutral" in c:
        return "fg-neutral"
    # Fallback por valor caso a classificação venha vazia.
    if value is None:
        return "fg-neutral"
    v = int(value)
    if v < 25:
        return "fg-extreme-fear"
    if v < 46:
        return "fg-fear"
    if v < 55:
        return "fg-neutral"
    if v < 76:
        return "fg-greed"
    return "fg-extreme-greed"


def _fng_signal(value) -> str:
    if value is None:
        return "-"
    v = int(value)
    if v < 25:
        return "Contrarian accumulation zone"
    if v < 46:
        return "Cautious accumulation"
    if v < 55:
        return "Balanced sentiment"
    if v < 76:
        return "Momentum — stay alert"
    return "Distribution / take profit"


def _build_fng_card(data) -> str:
    """Fear & Greed card. Falls back to '-' placeholders when unavailable."""
    if not data:
        return f'''
    <div class="oc-card fg-card">
      <div class="oc-card-head">
        <span class="oc-icon">&#9878;</span>
        <span class="oc-title">Fear &amp; Greed</span>
        <span class="badge-zone fg-neutral">-</span>
      </div>
      <div class="oc-body">
        <div class="oc-gauge">{_fng_gauge_svg(None)}</div>
        <div class="oc-metrics">
          <div class="oc-row"><span class="oc-k">Index</span><span class="oc-v oc-highlight">-</span></div>
          <div class="oc-row"><span class="oc-k">Classification</span><span class="oc-v">-</span></div>
          <div class="oc-row"><span class="oc-k">7D Avg</span><span class="oc-v">-</span></div>
          <div class="oc-row"><span class="oc-k">Trend</span><span class="oc-v">-</span></div>
        </div>
      </div>
      <div class="oc-footer">
        <span class="oc-action-label">Signal:</span>
        <span class="oc-action-val">-</span>
      </div>
    </div>'''

    value = int(data["value"])
    classification = str(data.get("classification", ""))
    avg_7d = data.get("avg_7d", "-")
    delta = int(data.get("delta_7d", 0))
    fg_cls = _fng_class(value, classification)

    if delta > 0:
        trend_html = f'<span class="oc-v pos">&#9650; +{delta} vs last week</span>'
    elif delta < 0:
        trend_html = f'<span class="oc-v neg">&#9660; {delta} vs last week</span>'
    else:
        trend_html = '<span class="oc-v">&#8594; flat vs last week</span>'

    return f'''
    <div class="oc-card fg-card">
      <div class="oc-card-head">
        <span class="oc-icon">&#9878;</span>
        <span class="oc-title">Fear &amp; Greed</span>
        <span class="badge-zone {fg_cls}">{escape(classification.upper()) if classification else "-"}</span>
      </div>
      <div class="oc-body">
        <div class="oc-gauge">{_fng_gauge_svg(value)}</div>
        <div class="oc-metrics">
          <div class="oc-row"><span class="oc-k">Index</span><span class="oc-v oc-highlight">{value} / 100</span></div>
          <div class="oc-row"><span class="oc-k">Classification</span><span class="oc-v">{escape(classification) if classification else "-"}</span></div>
          <div class="oc-row"><span class="oc-k">7D Avg</span><span class="oc-v">{avg_7d}</span></div>
          <div class="oc-row"><span class="oc-k">Trend</span>{trend_html}</div>
        </div>
      </div>
      <div class="oc-footer">
        <span class="oc-action-label">Signal:</span>
        <span class="oc-action-val">{escape(_fng_signal(value))}</span>
      </div>
    </div>'''


def _market_title(market: object) -> str:
    return GROUP_TITLES.get(str(market), str(market))


def _opportunity_rank(row: pd.Series) -> tuple:
    signal_rank = {"UltraBuy": 0, "Buy": 1, "Neutral": 2, "Sell": 3}
    return (
        signal_rank.get(str(row.get("Signal", "")), 9),
        float(row.get("Weekly_RSI", 100)),
        100.0 if pd.isna(row.get("Monthly_RSI")) else float(row.get("Monthly_RSI", 100)),
        float(row.get("Drawdown_Pct", 0.0)),
    )


def _risk_rank(row: pd.Series) -> tuple:
    signal_rank = {"Sell": 0, "Neutral": 1, "Buy": 2, "UltraBuy": 3}
    return (
        signal_rank.get(str(row.get("Signal", "")), 9),
        -float(row.get("Weekly_RSI", 0)),
        -(0.0 if pd.isna(row.get("Monthly_RSI")) else float(row.get("Monthly_RSI", 0))),
        -float(row.get("Drawdown_Pct", -100.0)),
    )


def _highlight_rsi_chip(label: str, value) -> str:
    if value is None or pd.isna(value):
        return f'<span class="highlight-chip chip-rsi rz-na">{label} n/a</span>'
    v = int(value)
    return f'<span class="highlight-chip chip-rsi {_rsi_zone_cls(v)}">{label} {v}</span>'


def _build_highlight_rows(df_ranked: pd.DataFrame, rank_kind: str) -> str:
    rows_html = ""
    for index, (_, r) in enumerate(df_ranked.iterrows(), start=1):
        sig_cls = _signal_class(r["Signal"])
        sig_lbl = _signal_label(r["Signal"])
        drawdown = float(r.get("Drawdown_Pct", 0.0))
        rows_html += f'''
      <div class="highlight-row rank-{rank_kind}" data-goto="{escape(str(r["Ticker"]), quote=True)}" title="Click to locate in the RSI Matrix">
        <div class="highlight-rank">{index}</div>
        <div class="highlight-main">
          <div class="highlight-title">
            <span class="tk-badge">{escape(str(r["Ticker"]))}</span>
            <span class="highlight-name">{escape(str(r["Name"]))}</span>
          </div>
          <div class="highlight-meta">
            <span class="highlight-chip chip-market">{escape(_market_title(r.get("Setor", "")))}</span>
            {_highlight_rsi_chip("RSI W", r["Weekly_RSI"])}
            {_highlight_rsi_chip("RSI M", r["Monthly_RSI"])}
            <span class="highlight-chip chip-dd {_drawdown_class(drawdown)}">DD {_format_percent(drawdown)}</span>
          </div>
        </div>
        <div class="highlight-signal">
          <span class="signal-badge {sig_cls}">{sig_lbl}</span>
        </div>
      </div>'''
    return rows_html


def _build_executive_rankings(df: pd.DataFrame) -> str:
    opportunity = df.copy()
    opportunity["__rank"] = opportunity.apply(_opportunity_rank, axis=1)
    opportunity = opportunity.sort_values("__rank").head(5).drop(columns="__rank")

    risk = df.copy()
    risk["__rank"] = risk.apply(_risk_rank, axis=1)
    risk = risk.sort_values("__rank").head(5).drop(columns="__rank")

    return f'''
<section class="desk-highlights" aria-label="Executive rankings">
  <article class="highlight-card opportunities">
    <div class="highlight-head">
      <h2>Top Opportunities</h2>
      <span>TOP 5</span>
    </div>
    <div class="highlight-list">{_build_highlight_rows(opportunity, "opportunity")}
    </div>
  </article>
  <article class="highlight-card risks">
    <div class="highlight-head">
      <h2>Top Risks</h2>
      <span>TOP 5</span>
    </div>
    <div class="highlight-list">{_build_highlight_rows(risk, "risk")}
    </div>
  </article>
</section>'''


def _rsi_zone(v: int) -> str:
    """RSI zone bucket (mirrors the former client-side logic)."""
    if v <= 30:
        return "deep"
    if v <= 40:
        return "value"
    if v <= 50:
        return "watch"
    if v >= 70:
        return "hot"
    if v >= 60:
        return "warm"
    return "neutral"


def _rsi_meter(v) -> str:
    """RSI value + a 0-100 position track with 30/70 markers and a zone-colored dot.

    Renders a neutral 'n/a' pill when the RSI is missing (NaN) — e.g. a recently
    listed asset without enough months yet for the monthly reading."""
    if v is None or pd.isna(v):
        return (
            '<span class="rsi-meter" data-zone="na">'
            '<span class="rsi-pill" data-zone="na" title="Not enough history">n/a</span>'
            '<span class="rsi-track"><span class="rsi-tick" style="left:30%"></span>'
            '<span class="rsi-tick" style="left:70%"></span></span></span>'
        )
    v = int(v)
    zone = _rsi_zone(v)
    pos = max(3, min(97, v))
    return (
        f'<span class="rsi-meter" data-zone="{zone}">'
        f'<span class="rsi-pill" data-rsi="{v}" data-zone="{zone}">{v}</span>'
        f'<span class="rsi-track">'
        f'<span class="rsi-tick" style="left:30%"></span>'
        f'<span class="rsi-tick" style="left:70%"></span>'
        f'<span class="rsi-dot" style="left:{pos}%"></span>'
        f'</span></span>'
    )


# TradingView symbols for indices can't be reconstructed by rule — map the 5 covered.
_TV_INDEX_MAP = {
    "BVSP": "BMFBOVESPA:IBOV",
    "GSPC": "SP:SPX",
    "NDX": "NASDAQ:NDX",
    "DJI": "DJ:DJI",
    "GDAXI": "XETR:DAX",
}


def _asset_links(ticker: str, setor: str, yahoo_symbol: object = None) -> tuple:
    """Build Yahoo Finance and TradingView URLs from display ticker + group.

    The DataFrame ticker is normalized for display, while ``Yahoo_Ticker`` keeps
    the raw symbol for special cases such as HYPE32196-USD.
    """
    tk = str(ticker).upper()
    raw_symbol = str(yahoo_symbol or "").strip()

    if setor == "Indices":
        yahoo_symbol_out = raw_symbol or ("^" + tk)
        tv_sym = _TV_INDEX_MAP.get(tk)
    elif setor == "Cripto":
        yahoo_symbol_out = raw_symbol or (tk + "-USD")
        tv_sym = f"{tk}USD"
    elif setor == "Brasil":
        yahoo_symbol_out = raw_symbol or (tk + ".SA")
        tv_sym = f"BMFBOVESPA:{tk}"
    elif setor == "Moeda":
        yahoo_symbol_out = raw_symbol or tk
        tv_sym = "FX_IDC:USDBRL" if tk == "BRL=X" else None
    else:  # EUA and anything else: plain symbol
        yahoo_symbol_out = raw_symbol or tk
        tv_sym = tk.replace("-", ".")

    yahoo = f"https://finance.yahoo.com/quote/{quote(yahoo_symbol_out, safe='')}"
    tv_url = None
    if tv_sym:
        tv_url = f"https://www.tradingview.com/chart/?symbol={quote(tv_sym, safe='')}"
    return yahoo, tv_url


def _volume_badge(vol_high: object, vol_ratio: object) -> str:
    """Weekly-volume confirmation badge: last closed week vs mean of prior 4 weeks."""
    if vol_ratio is None or pd.isna(vol_ratio):
        return '<span class="vol-na">—</span>'
    ratio_txt = f"{float(vol_ratio):.1f}×"
    if bool(vol_high):
        return f'<span class="vol-badge vol-high">▲ High <small>{ratio_txt}</small></span>'
    return f'<span class="vol-badge vol-low">▼ Low <small>{ratio_txt}</small></span>'


# Industry-sector presentation metadata: icon + accent color per sector.
SECTOR_META = {
    "Technology":      ("💻", "#43d7e8"),
    "Semiconductors":  ("🔬", "#6fa8ff"),
    "Financials":      ("🏦", "#35d08f"),
    "Healthcare":      ("🩺", "#f472b6"),
    "Consumer":        ("🛒", "#f1bc4b"),
    "Industrials":     ("⚙️", "#a78bfa"),
    "Energy":          ("🛢️", "#ff8a5c"),
    "Utilities":       ("⚡", "#facc15"),
    "Materials":       ("🪨", "#94a3b8"),
    "Telecom & Media": ("📡", "#22d3ee"),
    "Agribusiness":    ("🌾", "#84cc16"),
    "Real Estate":     ("🏢", "#e879a0"),
}


def _sector_badge(industria: str) -> str:
    """Compact inline sector pill for the Name cell (equities only)."""
    if not industria:
        return ""
    icon, color = SECTOR_META.get(industria, ("📦", "#94a3b8"))
    return (f'<span class="sec-tag" style="--sc:{color}">{icon} '
            f'{escape(industria)}</span>')


def _rsi_zone_cls(v: int) -> str:
    if v <= 30:
        return "rz-green"
    if v <= 45:
        return "rz-teal"
    if v < 65:
        return "rz-blue"
    if v < 70:
        return "rz-yellow"
    return "rz-red"


def _build_sector_pulse(df: pd.DataFrame) -> tuple:
    """Build the Sector Pulse card grid + sector filter chips for BR/US equities.

    Returns (pulse_section_html, sector_filter_html). Empty strings if there are
    no equities with sector metadata.
    """
    eq = df[df["Setor"].isin(["Brasil", "EUA"]) & (df.get("Industria", "") != "")].copy()
    if eq.empty:
        return "", ""

    order = eq.groupby("Industria").size().sort_values(ascending=False).index.tolist()

    cards = ""
    for sec in order:
        sub = eq[eq["Industria"] == sec]
        icon, color = SECTOR_META.get(sec, ("📦", "#94a3b8"))
        n = len(sub)
        counts = sub["Signal"].value_counts().to_dict()
        ops = counts.get("UltraBuy", 0) + counts.get("Buy", 0)
        neu = counts.get("Neutral", 0)
        sell = counts.get("Sell", 0)
        avg_rsi = int(round(sub["Weekly_RSI"].mean()))
        monthly_values = sub["Monthly_RSI"].dropna()
        avg_rsi_m = None if monthly_values.empty else int(round(monthly_values.mean()))
        avg_rsi_m_html = (
            '<b class="rz-na">n/a</b>'
            if avg_rsi_m is None
            else f'<b class="{_rsi_zone_cls(avg_rsi_m)}">{avg_rsi_m}</b>'
        )
        best = sub.sort_values("Weekly_RSI").iloc[0]
        n_br = int((sub["Setor"] == "Brasil").sum())
        n_us = n - n_br
        seg = ""
        for cnt, cls in ((ops, "seg-g"), (neu, "seg-b"), (sell, "seg-r")):
            if cnt:
                seg += f'<span class="{cls}" style="flex:{cnt}"></span>'
        mkt = ""
        if n_br:
            mkt += f'🇧🇷 {n_br} '
        if n_us:
            mkt += f'🇺🇸 {n_us}'
        cards += f'''
        <div class="sec-card" data-sector-card="{escape(sec)}" role="button" tabindex="0" style="--sc:{color}">
          <div class="sc-head"><span class="sc-ico">{icon}</span><span class="sc-name">{escape(sec)}</span><span class="sc-n">{n}</span></div>
          <div class="sc-bar">{seg}</div>
          <div class="sc-stats">
            <span><b class="{_rsi_zone_cls(avg_rsi)}">{avg_rsi}</b> avg RSI W</span>
            <span>{avg_rsi_m_html} avg RSI M</span>
            <span class="sc-flow"><b>{ops}</b> buy · <b>{sell}</b> overbought</span>
          </div>
          <div class="sc-foot">
            <span class="sc-mkt">{mkt.strip()}</span>
            <span class="sc-best">Lowest <b>{escape(str(best["Ticker"]))}</b> <i class="{_rsi_zone_cls(int(best["Weekly_RSI"]))}">{int(best["Weekly_RSI"])}</i></span>
          </div>
        </div>'''

    pulse = f'''
  <h2 class="section-title" id="sectors">Sector Pulse <span class="sp-hint">equities · click to filter</span></h2>
  <div class="sector-grid">{cards}</div>'''

    chips = ('<div class="filter-group sector-filter"><label>Filter Sector</label>'
             '<button class="fbtn sec-chip active" data-sector="all" style="--sc:var(--rm-cyan)">All Sectors</button>')
    for sec in order:
        icon, color = SECTOR_META.get(sec, ("📦", "#94a3b8"))
        chips += (f'<button class="fbtn sec-chip" data-sector="{escape(sec)}" style="--sc:{color}">'
                  f'{icon} {escape(sec)} <span class="fc">{len(eq[eq["Industria"]==sec])}</span></button>')
    chips += "</div>"

    return pulse, chips


def _build_sector_rows(df_sector: pd.DataFrame, market_key: str, dd_keys: set | None = None,
                       show_sector: bool = False) -> str:
    dd_keys = dd_keys or set()
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
            rsi_w = r["Weekly_RSI"]
            rsi_m = r["Monthly_RSI"]
            drawdown = float(r.get("Drawdown_Pct", 0.0))
            vol_ratio = r.get("Vol_Ratio")
            vol_sort = "-1" if vol_ratio is None or pd.isna(vol_ratio) else f"{float(vol_ratio):.6f}"
            dd_cls = _drawdown_class(drawdown)
            peak_date = _format_peak_date(r.get("Peak_Date"))
            peak_close = _format_price(float(r.get("Peak_Close", r["Weekly_Close"])))
            peak_meta = f"Top close: {peak_close}"
            if peak_date:
                peak_meta += f" | Date: {peak_date}"
            yahoo_url, tv_url = _asset_links(
                r["Ticker"],
                str(r.get("Setor", "")),
                r.get("Yahoo_Ticker"),
            )
            tkey = str(r["Ticker"])
            if tkey in dd_keys:
                chart_cell = (
                    f'<button class="dd-ico" type="button" data-dd="{escape(tkey, quote=True)}" '
                    f'title="Historical drawdown" aria-label="Historical drawdown of {escape(str(r["Name"]), quote=True)}">'
                    f'{_DD_ICON}</button>'
                )
            else:
                chart_cell = '<span class="dd-na">—</span>'
            industria = str(r.get("Industria", "")) if show_sector else ""
            sector_attr = f' data-sector="{escape(industria, quote=True)}"' if show_sector else ""
            name_inner = f'<span class="cn-txt">{escape(str(r["Name"]))}</span>'
            sector_html = _sector_badge(industria) if industria else '<span class="sec-na">-</span>'
            sector_sort = industria.lower() if industria else ""
            rows_html += f'''
            <tr class="asset-row" data-signal="{r['Signal']}" data-market="{escape(market_key)}"{sector_attr} data-ticker="{escape(str(r['Ticker']).lower())}" data-name="{escape(str(r['Name']).lower())}" data-peak-close="{escape(peak_close, quote=True)}" data-peak-date="{escape(peak_date, quote=True)}" data-dd="{escape(_format_percent(drawdown), quote=True)}" data-yahoo="{escape(yahoo_url, quote=True)}" data-tv="{escape(tv_url or '', quote=True)}">
              <td class="col-tk"><span class="tk-badge">{escape(str(r['Ticker']))}</span></td>
              <td class="col-name"><div class="name-cell">{name_inner}</div></td>
              <td class="col-sector" data-sort="{escape(sector_sort, quote=True)}">{sector_html}</td>
              <td class="col-price">{_format_price(r['Weekly_Close'])}</td>
              <td class="col-rsi">{_rsi_meter(rsi_w)}</td>
              <td class="col-rsi">{_rsi_meter(rsi_m)}</td>
              <td class="col-dd"><span class="dd-pill {dd_cls}" title="{escape(peak_meta, quote=True)}">{_format_percent(drawdown)}</span></td>
              <td class="col-chart">{chart_cell}</td>
              <td class="col-sig"><span class="signal-badge {sig_cls}">{sig_lbl}</span></td>
              <td class="col-vol" data-sort="{vol_sort}">{_volume_badge(r.get("Vol_High"), vol_ratio)}</td>
            </tr>'''
    return rows_html


SNAPSHOT_FILE = Path(__file__).parent / "snapshot_history.json"
SNAPSHOT_KEYS = ["total", "UltraBuy", "Buy", "Neutral", "Sell"]


def _load_snapshot_history() -> list:
    try:
        data = json.loads(SNAPSHOT_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (FileNotFoundError, ValueError, OSError):
        return []


def _count_signals(df: pd.DataFrame) -> dict:
    counts = df["Signal"].value_counts().to_dict()
    return {
        "total": int(len(df)),
        "UltraBuy": int(counts.get("UltraBuy", 0)),
        "Buy": int(counts.get("Buy", 0)),
        "Neutral": int(counts.get("Neutral", 0)),
        "Sell": int(counts.get("Sell", 0)),
    }


def _update_snapshot(df: pd.DataFrame) -> dict | None:
    """Append today's signal counts to a rolling history file and return day-over-day
    deltas vs the most recent snapshot from a *previous* calendar day (São Paulo tz).

    Returns None when there is no prior-day baseline yet (first run or same day).
    Writing/reading a small JSON is negligible next to the network fetches.
    """
    now = sao_paulo_now()
    today = now.strftime("%Y-%m-%d")
    counts = _count_signals(df)

    history = _load_snapshot_history()
    baseline = next(
        (s for s in reversed(history) if s.get("date") and s["date"] != today),
        None,
    )

    deltas = None
    if baseline:
        prev = baseline.get("counts", {})
        deltas = {k: counts[k] - int(prev.get(k, counts[k])) for k in SNAPSHOT_KEYS}

    history.append({"ts": now.isoformat(timespec="seconds"), "date": today, "counts": counts})
    history = history[-30:]
    try:
        SNAPSHOT_FILE.write_text(
            json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except OSError as exc:
        print(f"  [WARN] Could not write snapshot history: {exc}")

    return deltas


def _kpi_delta_html(key: str, deltas) -> str:
    """One '▲ +N vs yesterday' line under a KPI number, colored by signal semantics."""
    if not deltas or key not in deltas:
        return ('<div class="kpi-delta"><span class="d-flat">—</span>'
                '<span class="d-ctx">vs yesterday</span></div>')
    d = deltas[key]
    if d == 0:
        cls, txt = "d-flat", "= 0"
    else:
        arrow = "▲" if d > 0 else "▼"
        txt = f"{arrow} {d:+d}"
        if key in ("UltraBuy", "Buy"):
            cls = "d-good" if d > 0 else "d-bad"
        elif key == "Sell":
            cls = "d-bad" if d > 0 else "d-good"
        else:
            cls = "d-flat"
    return (f'<div class="kpi-delta"><span class="{cls}">{txt}</span>'
            f'<span class="d-ctx">vs yesterday</span></div>')


SIGNAL_HISTORY_FILE = Path(__file__).parent / "signal_history.json"
SIGNAL_HISTORY_DAYS = 90    # daily entries kept in the rolling file
TIMELINE_DAYS = 14          # per-asset timeline embedded in the page
WEEK_WINDOW_DAYS = 7        # "This Week" bucket: transitions up to N calendar days back


def _load_signal_history() -> list:
    try:
        data = json.loads(SIGNAL_HISTORY_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (FileNotFoundError, ValueError, OSError):
        return []


def _update_signal_history(df: pd.DataFrame) -> list:
    """Persist today's per-ticker signal/RSI snapshot and return the history.

    One entry per calendar day (São Paulo). Today's entry is OVERWRITTEN on
    every run so intraday runs always reflect the latest reading of the week
    in progress — signals are intentionally real-time, not close-confirmed.
    Past days keep the last state recorded for them.
    """
    today = sao_paulo_now().strftime("%Y-%m-%d")
    signals: Dict[str, str] = {}
    rsi_w: Dict[str, int] = {}
    for _, r in df.iterrows():
        tk = str(r["Ticker"])
        signals[tk] = str(r["Signal"])
        if not pd.isna(r["Weekly_RSI"]):
            rsi_w[tk] = int(r["Weekly_RSI"])

    history = [
        e for e in _load_signal_history()
        if isinstance(e, dict) and e.get("date") and e["date"] != today
    ]
    history.sort(key=lambda e: e["date"])
    history.append({"date": today, "signals": signals, "rsi_w": rsi_w})
    history = history[-SIGNAL_HISTORY_DAYS:]
    try:
        SIGNAL_HISTORY_FILE.write_text(
            json.dumps(history, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
    except OSError as exc:
        print(f"  [WARN] Could not write signal history: {exc}")
    return history


def _compute_signal_changes(history: list, df: pd.DataFrame) -> dict:
    """Diff current signals against the persisted daily history.

    Returns {"today": [...], "week": [...]}. "today" = the signal differs from
    the last previous-day snapshot; "week" = the current streak started 1..
    WEEK_WINDOW_DAYS calendar days ago (stable since). Buckets are mutually
    exclusive and sorted by significance (UltraBuy/Buy first, then Sell).
    """
    today_str = sao_paulo_now().strftime("%Y-%m-%d")
    prev_entries = sorted(
        (e for e in history
         if isinstance(e, dict) and e.get("date") and e["date"] < today_str),
        key=lambda e: e["date"],
    )
    out: dict = {"today": [], "week": []}
    if not prev_entries:
        return out
    today_date = date.fromisoformat(today_str)

    for _, r in df.iterrows():
        tk = str(r["Ticker"])
        cur = str(r["Signal"])
        series = [
            (e["date"], e["signals"][tk], e.get("rsi_w", {}).get(tk))
            for e in prev_entries
            if tk in e.get("signals", {})
        ]
        if not series:
            continue  # asset without recorded history yet
        cur_rsi = None if pd.isna(r["Weekly_RSI"]) else int(r["Weekly_RSI"])
        series.append((today_str, cur, cur_rsi))

        # Walk back to where the current signal streak started.
        i = len(series) - 1
        while i > 0 and series[i - 1][1] == cur:
            i -= 1
        if i == 0:
            continue  # stable across the whole recorded window
        days_ago = (today_date - date.fromisoformat(series[i][0])).days
        item = {
            "ticker": tk,
            "name": str(r["Name"]),
            "market": str(r.get("Setor", "")),
            "signal": cur,
            "prev": series[i - 1][1],
            "rsi": cur_rsi,
            "rsi_prev": series[i - 1][2],
            "days_ago": days_ago,
        }
        if days_ago == 0:
            out["today"].append(item)
        elif days_ago <= WEEK_WINDOW_DAYS:
            out["week"].append(item)

    order = {"UltraBuy": 0, "Buy": 1, "Sell": 2, "Neutral": 3}
    def _key(c):
        return (order.get(c["signal"], 9), c["rsi"] if c["rsi"] is not None else 50)
    out["today"].sort(key=_key)
    out["week"].sort(key=lambda c: (c["days_ago"],) + _key(c))
    return out


def _build_change_row(c: dict) -> str:
    when = "today" if c["days_ago"] == 0 else f"{c['days_ago']}d ago"
    rank = "NEW" if c["days_ago"] == 0 else f"{c['days_ago']}d"
    rsi_chip = ""
    if c.get("rsi_prev") is not None and c.get("rsi") is not None:
        rsi_chip = (f'<span class="highlight-chip">RSI W {int(c["rsi_prev"])} '
                    f'&rarr; {int(c["rsi"])}</span>')
    return f'''
      <div class="highlight-row wc-row" data-goto="{escape(c["ticker"], quote=True)}" title="Click to locate in the RSI Matrix">
        <div class="highlight-rank">{rank}</div>
        <div class="highlight-main">
          <div class="highlight-title">
            <span class="tk-badge">{escape(c["ticker"])}</span>
            <span class="highlight-name">{escape(c["name"])}</span>
          </div>
          <div class="highlight-meta">
            <span class="highlight-chip chip-market">{escape(_market_title(c["market"]))}</span>
            {rsi_chip}
            <span class="highlight-chip wc-since">{when}</span>
          </div>
        </div>
        <div class="highlight-signal wc-transition">
          <span class="signal-badge {_signal_class(c["prev"])}">{_signal_label(c["prev"])}</span>
          <span class="wc-arr">&rarr;</span>
          <span class="signal-badge {_signal_class(c["signal"])}">{_signal_label(c["signal"])}</span>
        </div>
      </div>'''


NEAR_TRIGGER_MAX = 4  # max RSI-W points from a buy/sell threshold to flag as "near"


def _compute_near_triggers(df: pd.DataFrame) -> list:
    """Neutral assets within NEAR_TRIGGER_MAX RSI-W points of their OWN buy/sell
    threshold. Buy candidates first, then Overbought; closest first within each.

    Uses each asset's real per-asset thresholds (carried in the DataFrame), so
    e.g. MSTR (buy=25) and HD (buy=35) are measured against their own lines, not
    a generic 30/70.
    """
    out: list = []
    for _, r in df.iterrows():
        if str(r["Signal"]) != "Neutral":
            continue
        rsi = r.get("Weekly_RSI")
        buy = r.get("Buy_Threshold")
        sell = r.get("Sell_Threshold")
        if rsi is None or pd.isna(rsi) or pd.isna(buy) or pd.isna(sell):
            continue
        rsi, buy, sell = int(rsi), int(buy), int(sell)
        d_buy = rsi - buy      # points above the buy line
        d_sell = sell - rsi    # points below the sell line
        # A Neutral asset sits strictly between the two lines; the nearer wins.
        if d_buy <= d_sell:
            direction, dist = "Buy", d_buy
        else:
            direction, dist = "Sell", d_sell
        if dist < 0 or dist > NEAR_TRIGGER_MAX:
            continue
        out.append({
            "ticker": str(r["Ticker"]),
            "name": str(r["Name"]),
            "market": str(r.get("Setor", "")),
            "rsi": rsi,
            "dist": dist,
            "direction": direction,
        })

    dir_order = {"Buy": 0, "Sell": 1}
    out.sort(key=lambda c: (dir_order[c["direction"]], c["dist"], c["rsi"]))
    return out


def _build_near_trigger_row(c: dict, index: int) -> str:
    is_sell = c["direction"] == "Sell"
    cls = "nt-sell" if is_sell else "nt-buy"
    arrow = "&uarr;" if is_sell else "&darr;"
    to_label = "OVERBOUGHT" if is_sell else "Buy"
    plural = "" if c["dist"] == 1 else "s"
    return f'''
      <div class="highlight-row wc-row" data-goto="{escape(c["ticker"], quote=True)}" title="Click to locate in the RSI Matrix">
        <div class="highlight-rank">{index}</div>
        <div class="highlight-main">
          <div class="highlight-title">
            <span class="tk-badge">{escape(c["ticker"])}</span>
            <span class="highlight-name">{escape(c["name"])}</span>
          </div>
          <div class="highlight-meta">
            <span class="highlight-chip chip-market">{escape(_market_title(c["market"]))}</span>
            <span class="highlight-chip">RSI W {c["rsi"]}</span>
          </div>
        </div>
        <div class="highlight-signal">
          <span class="nt-dist {cls}">{arrow} {c["dist"]} pt{plural} to {to_label}</span>
        </div>
      </div>'''


def _wc_card(kind: str, title: str, span: str, count: int, rows_html: str,
             empty_msg: str, foot: str) -> str:
    """One Signal-Changes/Watch-zone card. Non-empty lists go in a fixed-height
    scroller (equal card heights, internal scroll + bottom fade); empty lists
    show a placeholder and let the grid stretch the card to match its siblings."""
    if rows_html:
        body = (f'<div class="wc-scrollwrap"><div class="highlight-list">'
                f'{rows_html}</div></div>')
    else:
        body = f'<div class="wc-empty">{empty_msg}</div>'
    return f'''
  <article class="highlight-card wc-card wc-{kind}">
    <div class="highlight-head">
      <h2>{title} ({count})</h2>
      <span>{span}</span>
    </div>
    {body}
    <div class="wc-foot">{foot}</div>
  </article>'''


def _build_signal_changes_section(changes: dict, near_triggers: list) -> str:
    today_card = _wc_card(
        "today", "Signal Changes — Today", "VS LAST SESSION",
        len(changes["today"]),
        "".join(_build_change_row(c) for c in changes["today"]),
        "No signal changes vs the last session.",
        "Zone transitions vs the previous daily snapshot. Readings use the "
        "week in progress and refresh on every run.",
    )
    week_card = _wc_card(
        "week", "Signal Changes — This Week", f"LAST {WEEK_WINDOW_DAYS} DAYS",
        len(changes["week"]),
        "".join(_build_change_row(c) for c in changes["week"]),
        "No signal changes in the window. History builds up from daily runs.",
        "Click any row to locate the asset in the RSI Matrix. Expand a table "
        "row to see its signal timeline.",
    )
    nt_card = _wc_card(
        "neartrigger", "Watch-zone — Near Trigger", "&le;4 PTS · BUY FIRST",
        len(near_triggers),
        "".join(_build_near_trigger_row(c, i)
                for i, c in enumerate(near_triggers, start=1)),
        "No asset within 4 points of a buy/sell trigger.",
        f"Neutral assets within {NEAR_TRIGGER_MAX} RSI-W points of their own buy/"
        "sell threshold — buy candidates first, then overbought, closest first.",
    )
    return f'''
<section class="desk-highlights wc-section" id="changes" aria-label="Signal changes and watch-zone">{today_card}{week_card}{nt_card}
</section>'''


def _build_signal_timeline_payload(history: list) -> Dict[str, list]:
    """Per-ticker [["YYYY-MM-DD", "Signal"], ...] for the last TIMELINE_DAYS
    daily entries — powers the mini timeline in the expanded asset row."""
    entries = sorted(
        (e for e in history if isinstance(e, dict) and e.get("date")),
        key=lambda e: e["date"],
    )[-TIMELINE_DAYS:]
    payload: Dict[str, list] = {}
    for e in entries:
        for tk, sig in e.get("signals", {}).items():
            payload.setdefault(tk, []).append([e["date"], sig])
    return payload


def generate_html(df: pd.DataFrame, onchain: Dict, deltas: dict | None = None,
                  dd_data: dict | None = None, with_sectors: bool = True,
                  signal_history: list | None = None) -> str:
    dd_data = dd_data or {}
    dd_keys = set(dd_data.keys())
    dd_data_json = json.dumps(dd_data, separators=(",", ":"), ensure_ascii=False)
    sector_pulse_html, sector_filter_html = (
        _build_sector_pulse(df) if with_sectors else ("", ""))
    now = sao_paulo_now().strftime("%d/%m/%Y %H:%M BRT")
    counts = df["Signal"].value_counts().to_dict()
    total = len(df)
    ub = counts.get("UltraBuy", 0)
    b = counts.get("Buy", 0)
    n = counts.get("Neutral", 0)
    s = counts.get("Sell", 0)
    ub_pct = (ub / total * 100) if total else 0
    b_pct = (b / total * 100) if total else 0
    n_pct = (n / total * 100) if total else 0
    s_pct = (s / total * 100) if total else 0

    # Build on-chain section
    btc_card = _build_onchain_card("BTC", onchain.get("BTC")) if onchain else ""
    eth_card = _build_onchain_card("ETH", onchain.get("ETH")) if onchain else ""
    fng_card = _build_fng_card(onchain.get("FNG") if onchain else None)
    executive_rankings = _build_executive_rankings(df)

    # Signal changes ("What changed") + Watch-zone + per-asset timeline payload
    signal_history = signal_history or []
    signal_changes_html = _build_signal_changes_section(
        _compute_signal_changes(signal_history, df),
        _compute_near_triggers(df))
    signal_hist_json = json.dumps(
        _build_signal_timeline_payload(signal_history),
        separators=(",", ":"), ensure_ascii=False)

    # Build market filter buttons + table content
    market_buttons = '''<button class="fbtn active" data-market="all">All</button>'''
    sector_panels = ""
    first = True
    for grupo in GROUP_ORDER:
        sub = df[df["Setor"] == grupo]
        if sub.empty:
            continue
        title = GROUP_TITLES.get(grupo, grupo)
        cnt = len(sub)

        s_counts = sub["Signal"].value_counts().to_dict()
        market_buttons += f'''<button class="fbtn" data-market="{grupo.lower()}">{title} <span class="fc">{cnt}</span></button>'''

        rows = _build_sector_rows(sub, grupo.lower(), dd_keys, show_sector=with_sectors)
        sector_panels += f'''
      <div class="sector-panel {"active" if first else ""}" id="panel-{grupo.lower()}">
        <div class="panel-summary">
          <span class="ps-item ps-green">{s_counts.get("UltraBuy", 0) + s_counts.get("Buy", 0)} opportunities</span>
          <span class="ps-item ps-blue">{s_counts.get("Neutral", 0)} neutral</span>
          <span class="ps-item ps-red">{s_counts.get("Sell", 0)} overbought</span>
        </div>
        <div class="table-wrap">
          <table class="t-assets">
            <thead>
              <tr>
                <th class="th-sort" data-col="0">Ticker</th>
                <th class="th-sort" data-col="1">Name</th>
                <th class="th-sort" data-col="2">Sector</th>
                <th class="th-sort th-r" data-col="3">Price</th>
                <th class="th-sort th-r" data-col="4">RSI W</th>
                <th class="th-sort th-r" data-col="5">RSI M</th>
                <th class="th-sort th-r" data-col="6">DD %</th>
                <th class="th-c">DD Chart</th>
                <th>Signal</th>
                <th class="th-sort th-c" data-col="9">Volume</th>
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
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Financial Monitor Research — Dashboard</title>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800;900&family=JetBrains+Mono:wght@400;600;700;800&display=swap" rel="stylesheet"/>
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

/* FEAR & GREED BADGES */
.fg-extreme-fear{{background:rgba(248,113,113,.12);color:var(--red);border:1px solid rgba(248,113,113,.35)}}
.fg-fear{{background:rgba(255,95,70,.12);color:var(--orange);border:1px solid rgba(255,95,70,.35)}}
.fg-neutral{{background:rgba(96,165,250,.1);color:var(--blue);border:1px solid rgba(96,165,250,.3)}}
.fg-greed{{background:rgba(52,211,153,.1);color:var(--green);border:1px solid rgba(52,211,153,.3)}}
.fg-extreme-greed{{background:rgba(52,211,153,.16);color:var(--green);border:1px solid rgba(52,211,153,.45);box-shadow:0 0 8px rgba(52,211,153,.15)}}

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
.col-dd{{text-align:right}}
.col-sig{{text-align:center}}

/* RSI PILLS */
.rsi-pill{{display:inline-block;font-family:var(--mono);font-size:.78rem;font-weight:700;padding:3px 10px;border-radius:var(--radius-xs);min-width:36px;text-align:center}}
.dd-pill{{display:inline-block;font-family:var(--mono);font-size:.76rem;font-weight:800;padding:3px 10px;border-radius:var(--radius-xs);min-width:58px;text-align:center;white-space:nowrap}}
.dd-flat{{color:var(--teal);background:rgba(34,211,238,.12);border:1px solid rgba(34,211,238,.3)}}
.dd-mild{{color:var(--yellow);background:rgba(251,191,36,.12);border:1px solid rgba(251,191,36,.3)}}
.dd-deep{{color:var(--red);background:rgba(248,113,113,.12);border:1px solid rgba(248,113,113,.3)}}
.dd-stress{{color:#ff8aa0;background:rgba(244,63,94,.14);border:1px solid rgba(244,63,94,.38)}}

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
}}
{RESEARCH_V2_CSS}
{RESEARCH_V3_CSS}
{DRAWDOWN_CSS}
{SIGNAL_CHANGES_CSS}
</style>
</head>
<body class="research-v2 profile-field-v3">

<!-- TOPBAR -->
<header class="topbar">
  <div class="topbar-brand">
    <span class="brand-dot" aria-hidden="true"></span>
    <span class="brand-name">Financial Monitor Research</span>
  </div>
  <div class="search-wrap" role="search">
    <span class="search-icon">&#8981;</span>
    <input type="text" class="search-input" id="globalSearch" placeholder="Search ticker, asset, or name" autocomplete="off"/>
  </div>
  <div class="topbar-meta">
    <span>Research snapshot</span>
    <time>{now}</time>
  </div>
</header>

<!-- QUICK NAV -->
<nav class="v2nav" aria-label="Sections">
  <a href="#overview" class="v2nav-link active">Overview</a>
  <a href="#changes" class="v2nav-link">Changes</a>
  <a href="#onchain" class="v2nav-link">On-Chain</a>
  <a href="#sectors" class="v2nav-link">Sector Pulse</a>
  <a href="#matrix" class="v2nav-link">RSI Matrix</a>
</nav>

<!-- EXECUTIVE BRIEF -->
<section class="executive-board" id="overview" aria-label="Executive summary">
  <div class="brief-copy">
    <div class="eyebrow">Multi-asset research desk</div>
    <h1>Institutional dashboard for momentum, on-chain value, and risk zones.</h1>
    <p>Consolidated view of crypto, global indices, global equities, Brazilian equities, and currency markets focused on weekly RSI, monthly RSI, and MVRV.</p>
  </div>
  <aside class="market-read" aria-label="Signal distribution">
    <h2>Signal Allocation</h2>
    <div class="mix-row"><span class="signal-badge sig-ultrabuy">Ultra Buy</span><div class="mix-bar"><span style="--w:{ub_pct:.1f}%;--c:var(--rm-green)"></span></div><strong>{ub}</strong></div>
    <div class="mix-row"><span class="signal-badge sig-buy">Buy</span><div class="mix-bar"><span style="--w:{b_pct:.1f}%;--c:var(--rm-green)"></span></div><strong>{b}</strong></div>
    <div class="mix-row"><span class="signal-badge sig-neutral">Neutral</span><div class="mix-bar"><span style="--w:{n_pct:.1f}%;--c:var(--rm-blue)"></span></div><strong>{n}</strong></div>
    <div class="mix-row"><span class="signal-badge sig-sell">OVERBOUGHT</span><div class="mix-bar"><span style="--w:{s_pct:.1f}%;--c:var(--rm-red)"></span></div><strong>{s}</strong></div>
  </aside>
</section>

<!-- KPI STRIP -->
<div class="kpi-strip" aria-label="Key indicators">
  <div class="kpi-cell"><div class="kpi-num" style="color:var(--rm-cyan)">{total}</div><div class="kpi-label">Assets in coverage</div>{_kpi_delta_html("total", deltas)}</div>
  <div class="kpi-cell"><div class="kpi-num" style="color:var(--rm-green)">{ub}</div><div class="kpi-label">Extreme asymmetry</div>{_kpi_delta_html("UltraBuy", deltas)}</div>
  <div class="kpi-cell"><div class="kpi-num" style="color:var(--rm-green)">{b}</div><div class="kpi-label">Buy zone</div>{_kpi_delta_html("Buy", deltas)}</div>
  <div class="kpi-cell"><div class="kpi-num" style="color:var(--rm-blue)">{n}</div><div class="kpi-label">Neutral</div>{_kpi_delta_html("Neutral", deltas)}</div>
  <div class="kpi-cell"><div class="kpi-num" style="color:var(--rm-red)">{s}</div><div class="kpi-label">Overbought</div>{_kpi_delta_html("Sell", deltas)}</div>
</div>

{signal_changes_html}

{executive_rankings}

<div class="main">

  <!-- ON-CHAIN -->
  <h2 class="section-title" id="onchain">On-Chain Valuation Desk</h2>
  <div class="oc-grid">
    {btc_card}
    {eth_card}
    {fng_card}
  </div>

  {sector_pulse_html}

  <!-- RSI MONITOR -->
  <h2 class="section-title" id="matrix">RSI Opportunity Matrix</h2>

  <!-- Filter -->
  <div class="filter-strip">
    <div class="filter-group signal-filter">
      <label>Filter Signal</label>
      <button class="fbtn active" data-filter="all">All <span class="fc">{total}</span></button>
      <button class="fbtn" data-filter="UltraBuy">Ultra Buy <span class="fc">{ub}</span></button>
      <button class="fbtn" data-filter="Buy">Buy <span class="fc">{b}</span></button>
      <button class="fbtn" data-filter="Neutral">Neutral <span class="fc">{n}</span></button>
      <button class="fbtn" data-filter="Sell">OVERBOUGHT <span class="fc">{s}</span></button>
    </div>
    <div class="filter-group market-filter">
      <label>Filter Market</label>
      {market_buttons}
    </div>
    {sector_filter_html}
  </div>

  <!-- Panels -->
  {sector_panels}
  <div class="global-empty-state" id="globalEmpty">No assets match the current filters.</div>

</div>

<div class="footer">
  Financial Monitor Research · Updated <a>{now}</a> · Data: Yahoo Finance + CoinMetrics · Static research dashboard
</div>

<script>window.DD_DATA={dd_data_json};window.SIGNAL_HISTORY={signal_hist_json};</script>
<script>
{RESEARCH_V2_SCRIPT}
</script>
<script>
{RESEARCH_V3_SCRIPT}
</script>
<script>
{DRAWDOWN_SCRIPT}
</script>
<script>
{SIGNAL_CHANGES_SCRIPT}
</script>
</body>
</html>'''


# ==============================================================
# MAIN
# ==============================================================
def main():
    print("=" * 60)
    print("  FINANCIAL MONITOR RESEARCH — Dashboard Generator")
    print("=" * 60)

    print("\n[1/4] Fetching on-chain data (BTC + ETH)...")
    onchain = fetch_onchain_data()

    print("[2/4] Fetching RSI for all assets...")
    df = fetch_rsi_data()

    if df.empty:
        print("  [ERROR] No data returned. Check the connection or yfinance.")
        sys.exit(1)

    print(f"  [OK] {len(df)} assets processed")

    deltas = _update_snapshot(df)
    signal_history = _update_signal_history(df)

    print("[3/4] Building drawdown history (long weekly series)...")
    dd_data = build_drawdown_data(df)
    print(f"  [OK] drawdown ready for {len(dd_data)}/{len(df)} assets")

    print("[4/4] Generating dashboard HTML...")
    html = generate_html(df, onchain, deltas, dd_data, signal_history=signal_history)
    OUTPUT_FILE.write_text(html, encoding="utf-8")
    print(f"  [OK] Saved to: {OUTPUT_FILE}")
    print(f"\n  Open in browser: file:///{OUTPUT_FILE.as_posix()}")
    print("=" * 60)


if __name__ == "__main__":
    main()
