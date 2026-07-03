"""
generate_dashboard.py — Generates dashboard.html (Financial Monitor Research)
Usage: py generate_dashboard.py
Output: dashboard.html (open in browser)
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path
from typing import Dict
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import urllib3
import pandas as pd

# Disable SSL warnings for corporate proxies.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
os.environ.setdefault("CURL_CA_BUNDLE", "")

# Reuse the existing data collection logic.
from finance_stocks import collect_rsi_data
from onchain import (
    classify_mvrv_btc,
    classify_mvrv_eth,
    coinmetrics_price_realized_mvrv,
)

OUTPUT_FILE = Path(__file__).parent / "dashboard.html"
SAO_PAULO_TZ = "America/Sao_Paulo"

# Display order for coverage groups.
GROUP_ORDER = ["Indices", "Cripto", "EUA", "Brasil", "Moeda"]
GROUP_TITLES = {
    "Indices": "Global Indices",
    "Cripto": "Crypto Assets",
    "EUA": "U.S. Market",
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
  grid-template-columns:repeat(2,minmax(0,1fr));
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
  min-width:840px;
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
.research-v2 .t-assets th:nth-child(7),
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
.research-v2.profile-field-v2 .kpi-strip,
.research-v2.profile-field-v2 .main,
.research-v2.profile-field-v2 .footer{
  position:relative;
  z-index:1;
}

.research-v2.profile-field-v2 .brief-copy,
.research-v2.profile-field-v2 .market-read,
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
  const searchInput = document.getElementById('globalSearch');
  const globalEmpty = document.getElementById('globalEmpty');

  const state = {
    signal: 'all',
    market: 'all',
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

  function rowMatches(row) {
    const signalMatch = state.signal === 'all' || row.dataset.signal === state.signal;
    const marketMatch = state.market === 'all' || row.dataset.market === state.market;
    const textMatch = !state.query ||
      normalize(row.dataset.ticker).includes(state.query) ||
      normalize(row.dataset.name).includes(state.query);
    return signalMatch && marketMatch && textMatch;
  }

  function setSummary(item, count, singular, plural) {
    if(!item) return;
    item.textContent = `${count} ${count === 1 ? singular : plural}`;
    item.hidden = state.signal !== 'all' && count === 0;
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
      const shouldShowPanel = state.market === 'all' ? visibleRows > 0 : panelName === state.market;
      panel.classList.toggle('active', shouldShowPanel);
      updatePanelSummary(panel, visibleCounts);

      const empty = panel.querySelector('.empty-state');
      if(empty) empty.classList.toggle('is-visible', shouldShowPanel && visibleRows === 0);
    });

    if(globalEmpty) globalEmpty.classList.toggle('is-visible', totalVisible === 0);
  }

  function applyViewState() {
    syncPanels();
  }

  signalBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      signalBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      state.signal = btn.dataset.filter;
      applyViewState();
    });
  });

  marketBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      marketBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      state.market = btn.dataset.market;
      applyViewState();
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
        let va = a.children[col]?.textContent.trim() || '';
        let vb = b.children[col]?.textContent.trim() || '';
        const na = parseFloat(va.replace(/[^0-9.\-]/g, ''));
        const nb = parseFloat(vb.replace(/[^0-9.\-]/g, ''));
        if(!isNaN(na) && !isNaN(nb)) return (na - nb) * dir;
        return va.localeCompare(vb, 'pt-BR') * dir;
      });

      tableRows.forEach(r => tbody.appendChild(r));
    });
  });

  document.querySelectorAll('.rsi-pill').forEach(pill => {
    const v = parseInt(pill.dataset.rsi);
    if(v <= 30) pill.dataset.zone = 'deep';
    else if(v <= 40) pill.dataset.zone = 'value';
    else if(v <= 50) pill.dataset.zone = 'watch';
    else if(v >= 70) pill.dataset.zone = 'hot';
    else if(v >= 60) pill.dataset.zone = 'warm';
    else pill.dataset.zone = 'neutral';
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


# ==============================================================
# DATA FETCHING
# ==============================================================
def fetch_rsi_data() -> pd.DataFrame:
    """Fetch weekly/monthly RSI for all assets and return a DataFrame."""
    return collect_rsi_data(remove_crypto_suffix=True)


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
          <p class="oc-na">Data unavailable — retry outside the corporate network</p>
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
        <span class="oc-action-label">Action:</span>
        <span class="oc-action-val">{escape(data["action"])}</span>
        <span class="oc-risk-pill">Risk: {escape(data["risk"])}</span>
      </div>
    </div>'''


def _build_sector_rows(df_sector: pd.DataFrame, market_key: str) -> str:
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
            drawdown = float(r.get("Drawdown_Pct", 0.0))
            dd_cls = _drawdown_class(drawdown)
            peak_date = _format_peak_date(r.get("Peak_Date"))
            peak_meta = f"Top close: {_format_price(float(r.get('Peak_Close', r['Weekly_Close'])))}"
            if peak_date:
                peak_meta += f" | Date: {peak_date}"
            rows_html += f'''
            <tr class="asset-row" data-signal="{r['Signal']}" data-market="{escape(market_key)}" data-ticker="{escape(str(r['Ticker']).lower())}" data-name="{escape(str(r['Name']).lower())}">
              <td class="col-tk"><span class="tk-badge">{escape(str(r['Ticker']))}</span></td>
              <td class="col-name">{escape(str(r['Name']))}</td>
              <td class="col-price">{_format_price(r['Weekly_Close'])}</td>
              <td class="col-rsi"><span class="rsi-pill" data-rsi="{rsi_w}">{rsi_w}</span></td>
              <td class="col-rsi"><span class="rsi-pill" data-rsi="{rsi_m}">{rsi_m}</span></td>
              <td class="col-dd"><span class="dd-pill {dd_cls}" title="{escape(peak_meta, quote=True)}">{_format_percent(drawdown)}</span></td>
              <td class="col-sig"><span class="signal-badge {sig_cls}">{sig_lbl}</span></td>
            </tr>'''
    return rows_html


def generate_html(df: pd.DataFrame, onchain: Dict) -> str:
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

        rows = _build_sector_rows(sub, grupo.lower())
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
                <th class="th-sort th-r" data-col="2">Price</th>
                <th class="th-sort th-r" data-col="3">RSI W</th>
                <th class="th-sort th-r" data-col="4">RSI M</th>
                <th class="th-sort th-r" data-col="5">DD %</th>
                <th>Signal</th>
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
</style>
</head>
<body class="research-v2 profile-field-v2">

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

<!-- EXECUTIVE BRIEF -->
<section class="executive-board" aria-label="Executive summary">
  <div class="brief-copy">
    <div class="eyebrow">Multi-asset research desk</div>
    <h1>Institutional dashboard for momentum, on-chain value, and risk zones.</h1>
    <p>Consolidated view of crypto, global indices, global equities, Brazilian equities, and currency markets focused on weekly RSI, monthly RSI, and MVRV.</p>
  </div>
  <aside class="market-read" aria-label="Signal distribution">
    <h2>Signal Allocation</h2>
    <div class="mix-row"><span>Ultra Buy</span><strong>{ub}</strong><div class="mix-bar"><span style="--w:{ub_pct:.1f}%;--c:var(--rm-green)"></span></div></div>
    <div class="mix-row"><span>Buy</span><strong>{b}</strong><div class="mix-bar"><span style="--w:{b_pct:.1f}%;--c:var(--rm-green)"></span></div></div>
    <div class="mix-row"><span>Neutral</span><strong>{n}</strong><div class="mix-bar"><span style="--w:{n_pct:.1f}%;--c:var(--rm-blue)"></span></div></div>
    <div class="mix-row"><span>Sell</span><strong>{s}</strong><div class="mix-bar"><span style="--w:{s_pct:.1f}%;--c:var(--rm-red)"></span></div></div>
  </aside>
</section>

<!-- KPI STRIP -->
<div class="kpi-strip" aria-label="Key indicators">
  <div class="kpi-cell"><div class="kpi-num" style="color:var(--rm-cyan)">{total}</div><div class="kpi-label">Assets in coverage</div></div>
  <div class="kpi-cell"><div class="kpi-num" style="color:var(--rm-green)">{ub}</div><div class="kpi-label">Extreme asymmetry</div></div>
  <div class="kpi-cell"><div class="kpi-num" style="color:var(--rm-green)">{b}</div><div class="kpi-label">Buy zone</div></div>
  <div class="kpi-cell"><div class="kpi-num" style="color:var(--rm-blue)">{n}</div><div class="kpi-label">Neutral</div></div>
  <div class="kpi-cell"><div class="kpi-num" style="color:var(--rm-red)">{s}</div><div class="kpi-label">Overbought</div></div>
</div>

<div class="main">

  <!-- ON-CHAIN -->
  <h2 class="section-title">On-Chain Valuation Desk</h2>
  <div class="oc-grid">
    {btc_card}
    {eth_card}
  </div>

  <!-- RSI MONITOR -->
  <h2 class="section-title">RSI Opportunity Matrix</h2>

  <!-- Filter -->
  <div class="filter-strip">
    <div class="filter-group">
      <label>Filter Signal</label>
      <button class="fbtn active" data-filter="all">All <span class="fc">{total}</span></button>
      <button class="fbtn" data-filter="UltraBuy">Ultra Buy <span class="fc">{ub}</span></button>
      <button class="fbtn" data-filter="Buy">Buy <span class="fc">{b}</span></button>
      <button class="fbtn" data-filter="Neutral">Neutral <span class="fc">{n}</span></button>
      <button class="fbtn" data-filter="Sell">Sell <span class="fc">{s}</span></button>
    </div>
    <div class="filter-group">
      <label>Filter Market</label>
      {market_buttons}
    </div>
  </div>

  <!-- Panels -->
  {sector_panels}
  <div class="global-empty-state" id="globalEmpty">No assets match the current filters.</div>

</div>

<div class="footer">
  Financial Monitor Research · Updated <a>{now}</a> · Data: Yahoo Finance + CoinMetrics · Static research dashboard
</div>

<script>
{RESEARCH_V2_SCRIPT}
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

    print("\n[1/3] Fetching on-chain data (BTC + ETH)...")
    onchain = fetch_onchain_data()

    print("[2/3] Fetching RSI for all assets...")
    df = fetch_rsi_data()

    if df.empty:
        print("  [ERROR] No data returned. Check the connection or yfinance.")
        sys.exit(1)

    print(f"  [OK] {len(df)} assets processed")

    print("[3/3] Generating dashboard HTML...")
    html = generate_html(df, onchain)
    OUTPUT_FILE.write_text(html, encoding="utf-8")
    print(f"  [OK] Saved to: {OUTPUT_FILE}")
    print(f"\n  Open in browser: file:///{OUTPUT_FILE.as_posix()}")
    print("=" * 60)


if __name__ == "__main__":
    main()
