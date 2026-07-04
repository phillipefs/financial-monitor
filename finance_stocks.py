from __future__ import annotations

import os
import tempfile
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import yfinance as yf
from ta.momentum import RSIIndicator


def configure_yfinance_cache() -> None:
    cache_dir_env = os.getenv("YFINANCE_CACHE_DIR")
    cache_root = Path(cache_dir_env or os.getenv("RUNNER_TEMP") or tempfile.gettempdir())
    cache_dir = cache_root if cache_dir_env else cache_root / "financial-monitor" / "yfinance"

    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        yf.set_tz_cache_location(str(cache_dir))
    except OSError as exc:
        print(f"[WARN] Nao foi possivel configurar cache do yfinance: {exc}")


configure_yfinance_cache()


# ==========================================================
# RSI / SINAIS
# ==========================================================
def round_half_up(n) -> int:
    return int(Decimal(str(n)).quantize(0, rounding=ROUND_HALF_UP))


def calculate_rsi(ticker_symbol: str, interval: str, window: int, period: str) -> pd.Series:
    df = yf.Ticker(ticker_symbol).history(interval=interval, period=period)
    df.dropna(inplace=True)
    if df.empty:
        raise ValueError("no price data returned")

    rsi = RSIIndicator(close=df["Close"], window=window).rsi()
    df["RSI"] = rsi

    peak_date = df["Close"].idxmax()
    peak_close = float(df.loc[peak_date, "Close"])
    current_close = float(df["Close"].iloc[-1])
    drawdown_pct = ((current_close / peak_close) - 1.0) * 100.0 if peak_close else 0.0

    df["Peak_Close"] = peak_close
    df["Peak_Date"] = peak_date
    df["Drawdown_Pct"] = drawdown_pct

    return df[["Close", "RSI", "Peak_Close", "Peak_Date", "Drawdown_Pct"]].iloc[-1]


def get_signal(
    rsi_weekly: float,
    rsi_monthly: float,
    buy_threshold: int,
    sell_threshold: int,
    ultra_threshold: int,
) -> str:
    if rsi_weekly <= buy_threshold and rsi_monthly <= ultra_threshold:
        return "UltraBuy"
    if rsi_weekly <= buy_threshold:
        return "Buy"
    if rsi_weekly >= sell_threshold:
        return "Sell"
    return "Neutral"


def get_signal_emoji(signal: str) -> str:
    return {"UltraBuy": "🟢🟢", "Buy": "🟢", "Neutral": "🔵", "Sell": "🔴"}.get(signal, "⚪")


# ==========================================================
# TABELAS (Web + Mobile)
# ==========================================================
def _mk_table(df: pd.DataFrame) -> str:
    header = f"{'TICK':<8} {'NAME':<12} {'CLOSE':>9} {'RSIw':>5} {'RSIm':>5}"
    sep = "-" * len(header)
    lines = [header, sep]

    for _, r in df.iterrows():
        tick = str(r["Ticker"])[:8].ljust(8)
        name = str(r.get("Name", ""))[:12].ljust(12)
        close = f"{float(r['Weekly_Close']):.2f}".rjust(9)
        rsiw = str(int(r["Weekly_RSI"])).rjust(5)
        rsim = str(int(r["Monthly_RSI"])).rjust(5)
        lines.append(f"{tick} {name} {close} {rsiw} {rsim}")

    return "```\n" + "\n".join(lines) + "\n```"


def _mk_table_compact(df: pd.DataFrame) -> str:
    header = f"{'TICK':<7} {'NAME':<9} {'CLOSE':>9} {'RSIw':>5} {'RSIm':>5}"
    sep = "-" * len(header)
    lines = [header, sep]

    for _, r in df.iterrows():
        tick = str(r["Ticker"])[:7].ljust(7)
        name = str(r.get("Name", ""))[:9].ljust(9)

        close_txt = f"{float(r['Weekly_Close']):.2f}"
        close_txt = close_txt[:9].rjust(9)

        rsiw = str(int(r["Weekly_RSI"])).rjust(5)
        rsim = str(int(r["Monthly_RSI"])).rjust(5)

        lines.append(f"{tick} {name} {close_txt} {rsiw} {rsim}")

    return "```\n" + "\n".join(lines) + "\n```"


def _mk_table_indices(df: pd.DataFrame) -> str:
    header = f"{'TICK':<6} {'NAME':<12} {'CLOSE':>8} {'W':>3} {'M':>3} {'SIG':<6}"
    sep = "-" * len(header)
    lines = [header, sep]

    sig_map = {
        "UltraBuy": "🟢 UBuy",
        "Buy": "🟢 Buy ",
        "Neutral": "🔵 Neut",
        "Sell": "🔴 Sell",
    }

    for _, r in df.iterrows():
        tick = str(r["Ticker"])[:6].ljust(6)
        name = str(r.get("Name", ""))[:12].ljust(12)

        close = f"{float(r['Weekly_Close']):.0f}".rjust(8)
        w = str(int(r["Weekly_RSI"])).rjust(3)
        m = str(int(r["Monthly_RSI"])).rjust(3)

        sig = sig_map.get(str(r.get("Signal", "")), "      ")
        sig = sig[:6].ljust(6)

        lines.append(f"{tick} {name} {close} {w} {m} {sig}")

    return "```\n" + "\n".join(lines) + "\n```"


# ==========================================================
# GRUPOS / ORDEM
# ==========================================================
INDEX_NAMES_ORDER = ["Ibovespa", "S&P 500", "Nasdaq 100", "Dow Jones", "DAX"]
INDEX_NAME_SET = set(INDEX_NAMES_ORDER)

GROUP_ORDER = ["Indices", "Cripto", "EUA", "ETF", "Brasil", "Moeda"]


# ==========================================================
# FORMATAÇÃO DA MENSAGEM (NOVO LAYOUT POR MERCADO)
# ==========================================================
def _format_section(df_section: pd.DataFrame, title: str) -> List[str]:
    """Monta uma seção inteira (título + blocos Ultra/Buy/Neutral/Sell) já ordenados."""
    if df_section.empty:
        return []

    parts: List[str] = []
    parts.append("")
    parts.append(f"*{title} ({len(df_section)})*")

    ordem = ["UltraBuy", "Buy", "Neutral", "Sell"]
    cols = ["Ticker", "Name", "Weekly_Close", "Weekly_RSI", "Monthly_RSI"]

    for sig in ordem:
        sub = df_section[df_section["Signal"] == sig].copy()
        if sub.empty:
            continue

        # Ordenação inteligente por tipo de sinal
        if sig in ["UltraBuy", "Buy"]:
            sub = sub.sort_values(["Weekly_RSI", "Monthly_RSI"], ascending=[True, True])
        elif sig == "Sell":
            sub = sub.sort_values(["Weekly_RSI", "Monthly_RSI"], ascending=[False, False])
        else:
            sub = sub.sort_values(["Weekly_RSI", "Monthly_RSI"], ascending=[True, True])

        parts.append("")
        parts.append(f"*{get_signal_emoji(sig)} {sig} ({len(sub)})*")

        use_compact = (sig == "Buy") or (sub["Weekly_Close"].max() >= 10000)
        parts.append(_mk_table_compact(sub[cols]) if use_compact else _mk_table(sub[cols]))

    return parts


def formatar_mensagem(df_sorted: pd.DataFrame) -> str:
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    counts: Dict[str, int] = df_sorted["Signal"].value_counts().to_dict()

    def c(sig: str) -> int:
        return int(counts.get(sig, 0))

    msg: List[str] = []
    msg.append(f"*📊 RSI Monitor — {now}*")
    msg.append(
        f"UltraBuy: *{c('UltraBuy')}* | Buy: *{c('Buy')}* | Neutral: *{c('Neutral')}* | Sell: *{c('Sell')}*"
    )

    # ======================================================
    # 1) ÍNDICES (sempre primeiro, com tabela própria)
    # ======================================================
    indices = df_sorted[df_sorted["Name"].isin(INDEX_NAME_SET)].copy()
    if not indices.empty:
        indices["__ord"] = indices["Name"].map({n: i for i, n in enumerate(INDEX_NAMES_ORDER)})
        indices = indices.sort_values("__ord").drop(columns="__ord")

        msg.append("")
        msg.append(f"*📌 Indices ({len(indices)})*")

        counts_idx = indices["Signal"].value_counts().to_dict()
        legenda = (
            f"{get_signal_emoji('UltraBuy')} UltraBuy:{counts_idx.get('UltraBuy',0)}  "
            f"{get_signal_emoji('Buy')} Buy:{counts_idx.get('Buy',0)}  "
            f"{get_signal_emoji('Neutral')} Neutral:{counts_idx.get('Neutral',0)}  "
            f"{get_signal_emoji('Sell')} Sell:{counts_idx.get('Sell',0)}"
        )
        msg.append(legenda)
        msg.append(_mk_table_indices(indices[["Ticker", "Name", "Weekly_Close", "Weekly_RSI", "Monthly_RSI", "Signal"]]))

    # ======================================================
    # 2) NOVO LAYOUT: EUA x BRASIL (mesma mensagem)
    # ======================================================
    df_rest = df_sorted[~df_sorted["Name"].isin(INDEX_NAME_SET)].copy()

    # garante que "setor" existe
    if "Setor" not in df_rest.columns:
        df_rest["Setor"] = ""

    for grupo in GROUP_ORDER:
        sub = df_rest[df_rest["Setor"] == grupo].copy()
        if sub.empty:
            continue

        # títulos bonitos
        title_map = {
            "Cripto": "🪙 Cripto",
            "EUA": "🇺🇸 Mercado Americano",
            "ETF": "🧺 ETFs",
            "Brasil": "🇧🇷 Brasil",
            "Moeda": "💱 Moedas",
            "Indices": "📌 Indices",  # não deve cair aqui (já foi tratado)
        }
        msg.extend(_format_section(sub, title_map.get(grupo, grupo)))

    return "\n".join(msg)


# ==========================================================
# ASSETS
# ==========================================================
assets = [
    # Índices
    {"ticker": "^BVSP", "name": "Ibovespa", "buy": 30, "sell": 70, "ultra": 40, "setor": "Indices"},
    {"ticker": "^GSPC", "name": "S&P 500", "buy": 30, "sell": 70, "ultra": 40, "setor": "Indices"},
    {"ticker": "^NDX", "name": "Nasdaq 100", "buy": 30, "sell": 70, "ultra": 40, "setor": "Indices"},
    {"ticker": "^DJI", "name": "Dow Jones", "buy": 30, "sell": 70, "ultra": 40, "setor": "Indices"},
    {"ticker": "^GDAXI", "name": "DAX", "buy": 30, "sell": 70, "ultra": 40, "setor": "Indices"},

    # Cripto
    {"ticker": "BTC-USD", "name": "Bitcoin", "buy": 30, "sell": 70, "ultra": 45, "setor": "Cripto"},
    {"ticker": "ETH-USD", "name": "Ethereum", "buy": 30, "sell": 70, "ultra": 45, "setor": "Cripto"},
    {"ticker": "SOL-USD", "name": "Solana", "buy": 30, "sell": 70, "ultra": 45, "setor": "Cripto"},
    {"ticker": "AAVE-USD", "name": "Aave", "buy": 30, "sell": 70, "ultra": 45, "setor": "Cripto"},

    # EUA
    {"ticker": "AMZN", "name": "Amazon", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA"},
    {"ticker": "GOOGL", "name": "Google", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA"},
    {"ticker": "AAPL", "name": "Apple", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA"},
    {"ticker": "MSFT", "name": "Microsoft", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA"},
    {"ticker": "TSLA", "name": "Tesla", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA"},
    {"ticker": "MSTR", "name": "Strategy", "buy": 25, "sell": 70, "ultra": 40, "setor": "EUA"},
    {"ticker": "TM", "name": "Toyota", "buy": 25, "sell": 70, "ultra": 40, "setor": "EUA"},
    {"ticker": "BLK", "name": "BlackRock", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA"},
    {"ticker": "JPM", "name": "JP Morgan", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA"},
    {"ticker": "CAT", "name": "Caterpillar", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA"},
    {"ticker": "V", "name": "Visa", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA"},
    {"ticker": "MA", "name": "Mastercard", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA"},
    {"ticker": "SPGI", "name": "S&P Global", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA"},
    {"ticker": "MCO", "name": "Moody's", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA"},
    {"ticker": "LIN", "name": "Linde", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA"},
    {"ticker": "UNH", "name": "UnitedHealth", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA"},
    {"ticker": "NVDA", "name": "Nvidia", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA"},
    {"ticker": "AVGO", "name": "Broadcom", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA"},
    {"ticker": "META", "name": "Meta", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA"},
    {"ticker": "BRK-B", "name": "Berkshire", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA"},
    {"ticker": "COST", "name": "Costco", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA"},
    {"ticker": "WMT", "name": "Walmart", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA"},
    {"ticker": "LLY", "name": "Eli Lilly", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA"},
    {"ticker": "XOM", "name": "Exxon", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA"},
    {"ticker": "AMD", "name": "AMD", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA"},
    {"ticker": "INTC", "name": "Intel", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA"},
    {"ticker": "MU", "name": "Micron", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA"},
    {"ticker": "ORCL", "name": "Oracle", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA"},
    {"ticker": "NOW", "name": "ServiceNow", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA"},
    {"ticker": "PANW", "name": "Palo Alto", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA"},
    {"ticker": "AMAT", "name": "Applied Mat", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA"},
    {"ticker": "TSM", "name": "TSMC", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA"},
    {"ticker": "ASML", "name": "ASML", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA"},
    {"ticker": "SMH", "name": "Semis ETF", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA"},
    {"ticker": "PLTR", "name": "Palantir", "buy": 30, "sell": 75, "ultra": 40, "setor": "EUA"},
    {"ticker": "APP", "name": "AppLovin", "buy": 30, "sell": 75, "ultra": 40, "setor": "EUA"},
    {"ticker": "NFLX", "name": "Netflix", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA"},
    {"ticker": "ANET", "name": "Arista", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA"},
    {"ticker": "KLAC", "name": "KLA", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA"},
    {"ticker": "LRCX", "name": "Lam Research", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA"},
    {"ticker": "QCOM", "name": "Qualcomm", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA"},
    {"ticker": "NU", "name": "Nubank", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA"},
    {"ticker": "HD", "name": "Home Depot", "buy": 35, "sell": 70, "ultra": 45, "setor": "EUA"},
    {"ticker": "JNJ", "name": "J&J", "buy": 35, "sell": 70, "ultra": 45, "setor": "EUA"},
    {"ticker": "PG", "name": "P&G", "buy": 35, "sell": 70, "ultra": 45, "setor": "EUA"},
    {"ticker": "ADBE", "name": "Adobe", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA"},
    {"ticker": "UNP", "name": "Union Pacific", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA"},
    {"ticker": "MELI", "name": "MercadoLibre", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA"},


    # ETFs
    {"ticker": "XBI", "name": "Biotech ETF", "buy": 32, "sell": 70, "ultra": 40, "setor": "ETF"},
    {"ticker": "SPY", "name": "S&P 500 ETF", "buy": 30, "sell": 70, "ultra": 40, "setor": "ETF"},
    {"ticker": "QQQ", "name": "Nasdaq 100 ETF", "buy": 30, "sell": 70, "ultra": 40, "setor": "ETF"},
    {"ticker": "GLD", "name": "Gold ETF", "buy": 35, "sell": 70, "ultra": 45, "setor": "ETF"},
    {"ticker": "SLV", "name": "Silver ETF", "buy": 32, "sell": 70, "ultra": 40, "setor": "ETF"},


    # Moeda
    {"ticker": "BRL=X", "name": "Dolar", "buy": 32, "sell": 70, "ultra": 45, "setor": "Moeda"},

    # Brasil
    {"ticker": "ABEV3.SA", "name": "Ambev", "buy": 30, "sell": 70, "ultra": 40, "setor": "Brasil"},
    {"ticker": "ALUP11.SA", "name": "Alupar", "buy": 30, "sell": 70, "ultra": 40, "setor": "Brasil"},
    {"ticker": "CMIG4.SA", "name": "Cemig", "buy": 30, "sell": 70, "ultra": 40, "setor": "Brasil"},
    {"ticker": "CPFE3.SA", "name": "CPFL Energia", "buy": 30, "sell": 70, "ultra": 40, "setor": "Brasil"},
    {"ticker": "EGIE3.SA", "name": "Engie Brasil", "buy": 30, "sell": 70, "ultra": 40, "setor": "Brasil"},
    {"ticker": "TAEE11.SA", "name": "Taesa", "buy": 30, "sell": 70, "ultra": 40, "setor": "Brasil"},
    {"ticker": "ISAE4.SA", "name": "ISA Energia Brasil PFD", "buy": 30, "sell": 70, "ultra": 40, "setor": "Brasil"},
    {"ticker": "ISAE3.SA", "name": "ISA Energia Brasil ON", "buy": 30, "sell": 70, "ultra": 40, "setor": "Brasil"},
    {"ticker": "CPLE3.SA", "name": "Copel", "buy": 30, "sell": 70, "ultra": 40, "setor": "Brasil"},
    {"ticker": "EQTL3.SA", "name": "Equatorial", "buy": 30, "sell": 70, "ultra": 40, "setor": "Brasil"},
    {"ticker": "INBR32.SA", "name": "Banco Inter", "buy": 30, "sell": 70, "ultra": 45, "setor": "Brasil"},
    {"ticker": "BBAS3.SA", "name": "Banco do Brasil", "buy": 30, "sell": 70, "ultra": 40, "setor": "Brasil"},
    {"ticker": "BPAC11.SA", "name": "BTG Pactual", "buy": 30, "sell": 70, "ultra": 40, "setor": "Brasil"},
    {"ticker": "BRSR6.SA", "name": "Banrisul", "buy": 30, "sell": 70, "ultra": 40, "setor": "Brasil"},
    {"ticker": "BBDC4.SA", "name": "Bradesco", "buy": 30, "sell": 70, "ultra": 40, "setor": "Brasil"},
    {"ticker": "ITUB4.SA", "name": "Itaú", "buy": 30, "sell": 70, "ultra": 40, "setor": "Brasil"},
    {"ticker": "SANB11.SA", "name": "Santander", "buy": 30, "sell": 70, "ultra": 40, "setor": "Brasil"},
    {"ticker": "ITSA4.SA", "name": "Itaúsa", "buy": 30, "sell": 70, "ultra": 40, "setor": "Brasil"},
    {"ticker": "VALE3.SA", "name": "Vale", "buy": 30, "sell": 70, "ultra": 40, "setor": "Brasil"},
    {"ticker": "PETR4.SA", "name": "Petrobras", "buy": 30, "sell": 70, "ultra": 40, "setor": "Brasil"},
    {"ticker": "PRIO3.SA", "name": "Prio", "buy": 30, "sell": 70, "ultra": 40, "setor": "Brasil"},
    {"ticker": "PINE4.SA", "name": "Banco Pine", "buy": 30, "sell": 70, "ultra": 40, "setor": "Brasil"},
    {"ticker": "RANI3.SA", "name": "Irani", "buy": 30, "sell": 70, "ultra": 40, "setor": "Brasil"},
    {"ticker": "SUZB3.SA", "name": "Suzano", "buy": 30, "sell": 70, "ultra": 40, "setor": "Brasil"},
    {"ticker": "PSSA3.SA", "name": "Porto Seguro", "buy": 30, "sell": 70, "ultra": 40, "setor": "Brasil"},
    {"ticker": "BBSE3.SA", "name": "BB Seguridade", "buy": 30, "sell": 70, "ultra": 40, "setor": "Brasil"},
    {"ticker": "CXSE3.SA", "name": "Caixa Seguros", "buy": 30, "sell": 70, "ultra": 40, "setor": "Brasil"},
    {"ticker": "CSMG3.SA", "name": "Copasa", "buy": 30, "sell": 70, "ultra": 40, "setor": "Brasil"},
    {"ticker": "SAPR11.SA", "name": "Sanepar", "buy": 30, "sell": 70, "ultra": 40, "setor": "Brasil"},
    {"ticker": "SBSP3.SA", "name": "Sabesp", "buy": 30, "sell": 70, "ultra": 40, "setor": "Brasil"},
    {"ticker": "VIVT3.SA", "name": "Vivo", "buy": 30, "sell": 70, "ultra": 40, "setor": "Brasil"},
    {"ticker": "RADL3.SA", "name": "Droga Raia", "buy": 32, "sell": 70, "ultra": 40, "setor": "Brasil"},
    {"ticker": "WEGE3.SA", "name": "WEG", "buy": 30, "sell": 70, "ultra": 40, "setor": "Brasil"},
    {"ticker": "TOTS3.SA", "name": "Totvs", "buy": 30, "sell": 70, "ultra": 40, "setor": "Brasil"},
    {"ticker": "B3SA3.SA", "name": "B3", "buy": 30, "sell": 70, "ultra": 40, "setor": "Brasil"},
    {"ticker": "RENT3.SA", "name": "Localiza", "buy": 30, "sell": 70, "ultra": 40, "setor": "Brasil"},
    {"ticker": "SOJA3.SA", "name": "Boa Safra", "buy": 30, "sell": 70, "ultra": 40, "setor": "Brasil"},
    {"ticker": "KLBN4.SA", "name": "Klabin", "buy": 35, "sell": 70, "ultra": 45, "setor": "Brasil"},
    {"ticker": "GGBR4.SA", "name": "Gerdau", "buy": 32, "sell": 70, "ultra": 40, "setor": "Brasil"},
    {"ticker": "MULT3.SA", "name": "Multiplan", "buy": 35, "sell": 70, "ultra": 45, "setor": "Brasil"},
    {"ticker": "AGRO3.SA", "name": "BrasilAgro", "buy": 35, "sell": 70, "ultra": 40, "setor": "Brasil"},
    {"ticker": "SLCE3.SA", "name": "SLC Agricola", "buy": 30, "sell": 70, "ultra": 40, "setor": "Brasil"},
    {"ticker": "FLRY3.SA", "name": "Fleury", "buy": 32, "sell": 70, "ultra": 40, "setor": "Brasil"},
]


# ==========================================================
# MAIN
# ==========================================================
def _normalize_ticker(ticker: str, remove_crypto_suffix: bool = False) -> str:
    normalized = ticker.replace(".SA", "").replace("^", "")
    if remove_crypto_suffix:
        normalized = normalized.replace("-USD", "")
    return normalized


def fetch_asset_rsi(asset: Dict[str, object], remove_crypto_suffix: bool = False) -> Dict[str, object]:
    ticker = str(asset["ticker"])
    weekly = calculate_rsi(ticker, interval="1wk", window=14, period="5y")
    monthly = calculate_rsi(ticker, interval="1mo", window=14, period="5y")

    signal = get_signal(
        float(weekly["RSI"]),
        float(monthly["RSI"]),
        int(asset["buy"]),
        int(asset["sell"]),
        int(asset["ultra"]),
    )

    return {
        "Ticker": _normalize_ticker(ticker, remove_crypto_suffix=remove_crypto_suffix),
        "Name": asset["name"],
        "Weekly_Close": float(round(weekly["Close"], 2)),
        "Weekly_RSI": round_half_up(weekly["RSI"]),
        "Monthly_RSI": round_half_up(monthly["RSI"]),
        "Drawdown_Pct": float(round(weekly["Drawdown_Pct"], 2)),
        "Peak_Close": float(round(weekly["Peak_Close"], 2)),
        "Peak_Date": weekly["Peak_Date"],
        "Signal": signal,
        "Setor": asset.get("setor", ""),
    }


def collect_rsi_data(
    asset_list: Optional[List[Dict[str, object]]] = None,
    remove_crypto_suffix: bool = False,
) -> pd.DataFrame:
    results: List[Dict[str, object]] = []

    for asset in asset_list or assets:
        ticker = str(asset["ticker"])
        try:
            results.append(fetch_asset_rsi(asset, remove_crypto_suffix=remove_crypto_suffix))
        except Exception as exc:
            print(f"[WARN] {ticker}: {exc}")

    return pd.DataFrame(results)


def main() -> None:
    df = collect_rsi_data()
    if df.empty:
        print("RSI Monitor\nSem dados hoje (yfinance retornou vazio).")
        return

    print(formatar_mensagem(df))


if __name__ == "__main__":
    main()
