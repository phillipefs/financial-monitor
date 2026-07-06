from __future__ import annotations

import os
import tempfile
import time
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


def round_rsi_or_nan(n) -> float:
    """Round an RSI to an int, or return NaN when the series is too short.

    Assets with < 15 bars for a given interval yield a NaN RSI (Wilder needs
    window+1 points). Instead of crashing on ``int(NaN)``, we keep NaN so the
    asset can still render the interval it *does* have (e.g. CRCL has a valid
    weekly RSI but not enough months yet)."""
    if n is None or pd.isna(n):
        return float("nan")
    return float(round_half_up(n))


def _fmt_rsi(v) -> str:
    """Console/text-table RSI: integer string, or 'n/a' when missing."""
    return "n/a" if v is None or pd.isna(v) else str(int(v))


def _compute_rsi_row(df: pd.DataFrame, window: int) -> pd.Series:
    """Compute the RSI/peak/drawdown/volume snapshot from an already-fetched
    OHLCV DataFrame.

    Shared by the per-ticker fetch (:func:`calculate_rsi`) and the batched fetch
    (:func:`collect_rsi_data`) so both paths produce identical results given the
    same price data — the only difference between them is how the bars arrive.
    """
    df = df.dropna()
    if df.empty:
        raise ValueError("no price data returned")

    df = df.copy()
    df["RSI"] = RSIIndicator(close=df["Close"], window=window).rsi()

    peak_date = df["Close"].idxmax()
    peak_close = float(df.loc[peak_date, "Close"])
    current_close = float(df["Close"].iloc[-1])
    drawdown_pct = ((current_close / peak_close) - 1.0) * 100.0 if peak_close else 0.0

    df["Peak_Close"] = peak_close
    df["Peak_Date"] = peak_date
    df["Drawdown_Pct"] = drawdown_pct

    # Volume: última semana FECHADA vs média das 4 anteriores.
    # A última barra (iloc[-1]) pode ser a semana em andamento (parcial). Ela só
    # é considerada fechada a partir do sábado (>=5 dias após a segunda de
    # início do bar). Durante seg-sex usamos iloc[-2] (última semana completa);
    # no fim de semana usamos iloc[-1] (a semana que acabou de fechar), evitando
    # tanto ler uma semana parcial quanto ficar 1 semana atrasado no fim de semana.
    volume = df["Volume"] if "Volume" in df.columns else None
    if volume is not None and len(volume) >= 6:
        last_start = volume.index[-1].date()
        days_since_start = (datetime.now().date() - last_start).days
        idx = -1 if days_since_start >= 5 else -2
        vol_last = float(volume.iloc[idx])
        vol_prev4_mean = float(volume.iloc[idx - 4:idx].mean())
    else:
        vol_last = float("nan")
        vol_prev4_mean = float("nan")
    df["Vol_Last"] = vol_last
    df["Vol_Prev4Mean"] = vol_prev4_mean

    return df[[
        "Close", "RSI", "Peak_Close", "Peak_Date", "Drawdown_Pct",
        "Vol_Last", "Vol_Prev4Mean",
    ]].iloc[-1]


def calculate_rsi(ticker_symbol: str, interval: str, window: int, period: str) -> pd.Series:
    """Fetch one ticker's history (single HTTP request) and compute its snapshot."""
    df = yf.Ticker(ticker_symbol).history(interval=interval, period=period)
    return _compute_rsi_row(df, window)


def _download_batch(
    tickers: List[str],
    interval: str,
    period: str,
    chunk_size: int = 40,
    retries: int = 3,
) -> Dict[str, pd.DataFrame]:
    """Bulk-download OHLCV for many tickers — one HTTP batch per chunk instead of
    one request per ticker.

    Returns ``{ticker: DataFrame}``. Tickers that come back empty are simply
    omitted from the dict so the caller can fall back to a single-ticker fetch
    (that fallback is what keeps assets from silently disappearing when Yahoo
    throttles a batch).
    """
    out: Dict[str, pd.DataFrame] = {}
    for i in range(0, len(tickers), chunk_size):
        chunk = tickers[i:i + chunk_size]
        data = None
        for attempt in range(1, retries + 1):
            try:
                data = yf.download(
                    chunk, interval=interval, period=period, group_by="ticker",
                    auto_adjust=True, threads=True, progress=False,
                )
                if data is not None and not data.empty:
                    break
            except Exception as exc:  # network / parsing hiccup on the whole chunk
                print(f"[WARN] batch {interval} chunk {i // chunk_size + 1} "
                      f"attempt {attempt}/{retries}: {exc}")
            if attempt < retries:
                time.sleep(attempt * 5)

        if data is None or data.empty:
            continue

        multi = isinstance(data.columns, pd.MultiIndex)
        for tk in chunk:
            try:
                sub = data[tk] if multi else data
                sub = sub.dropna(how="all")
                if not sub.empty and "Close" in sub.columns and sub["Close"].notna().any():
                    out[tk] = sub
            except (KeyError, IndexError):
                pass  # ticker absent from this batch → caller will single-fetch it
    return out


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
        rsiw = _fmt_rsi(r["Weekly_RSI"]).rjust(5)
        rsim = _fmt_rsi(r["Monthly_RSI"]).rjust(5)
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

        rsiw = _fmt_rsi(r["Weekly_RSI"]).rjust(5)
        rsim = _fmt_rsi(r["Monthly_RSI"]).rjust(5)

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
        w = _fmt_rsi(r["Weekly_RSI"]).rjust(3)
        m = _fmt_rsi(r["Monthly_RSI"]).rjust(3)

        sig = sig_map.get(str(r.get("Signal", "")), "      ")
        sig = sig[:6].ljust(6)

        lines.append(f"{tick} {name} {close} {w} {m} {sig}")

    return "```\n" + "\n".join(lines) + "\n```"


# ==========================================================
# GRUPOS / ORDEM
# ==========================================================
INDEX_NAMES_ORDER = ["Ibovespa", "S&P 500", "Nasdaq 100", "Dow Jones", "DAX"]
INDEX_NAME_SET = set(INDEX_NAMES_ORDER)

GROUP_ORDER = ["Indices", "Cripto", "EUA", "ETF", "Commodities", "Brasil", "Moeda"]


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
    {"ticker": "HYPE32196-USD", "display_ticker": "HYPE", "name": "Hyperliquid", "buy": 30, "sell": 70, "ultra": 45, "setor": "Cripto"},

    # EUA
    {"ticker": "AMZN", "name": "Amazon", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA", "industria": "Consumer"},
    {"ticker": "GOOGL", "name": "Google", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA", "industria": "Technology"},
    {"ticker": "AAPL", "name": "Apple", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA", "industria": "Technology"},
    {"ticker": "MSFT", "name": "Microsoft", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA", "industria": "Technology"},
    {"ticker": "TSLA", "name": "Tesla", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA", "industria": "Consumer"},
    {"ticker": "MSTR", "name": "Strategy", "buy": 25, "sell": 70, "ultra": 40, "setor": "EUA", "industria": "Technology"},
    {"ticker": "TM", "name": "Toyota", "buy": 25, "sell": 70, "ultra": 40, "setor": "EUA", "industria": "Consumer"},
    {"ticker": "BLK", "name": "BlackRock", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA", "industria": "Financials"},
    {"ticker": "JPM", "name": "JP Morgan", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA", "industria": "Financials"},
    {"ticker": "CAT", "name": "Caterpillar", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA", "industria": "Industrials"},
    {"ticker": "V", "name": "Visa", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA", "industria": "Financials"},
    {"ticker": "MA", "name": "Mastercard", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA", "industria": "Financials"},
    {"ticker": "SPGI", "name": "S&P Global", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA", "industria": "Financials"},
    {"ticker": "MCO", "name": "Moody's", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA", "industria": "Financials"},
    {"ticker": "LIN", "name": "Linde", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA", "industria": "Materials"},
    {"ticker": "UNH", "name": "UnitedHealth", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA", "industria": "Healthcare"},
    {"ticker": "NVDA", "name": "Nvidia", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA", "industria": "Semiconductors"},
    {"ticker": "AVGO", "name": "Broadcom", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA", "industria": "Semiconductors"},
    {"ticker": "META", "name": "Meta", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA", "industria": "Technology"},
    {"ticker": "BRK-B", "name": "Berkshire", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA", "industria": "Financials"},
    {"ticker": "COST", "name": "Costco", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA", "industria": "Consumer"},
    {"ticker": "WMT", "name": "Walmart", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA", "industria": "Consumer"},
    {"ticker": "LLY", "name": "Eli Lilly", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA", "industria": "Healthcare"},
    {"ticker": "XOM", "name": "Exxon", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA", "industria": "Energy"},
    {"ticker": "AMD", "name": "AMD", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA", "industria": "Semiconductors"},
    {"ticker": "INTC", "name": "Intel", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA", "industria": "Semiconductors"},
    {"ticker": "MU", "name": "Micron", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA", "industria": "Semiconductors"},
    {"ticker": "ORCL", "name": "Oracle", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA", "industria": "Technology"},
    {"ticker": "NOW", "name": "ServiceNow", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA", "industria": "Technology"},
    {"ticker": "PANW", "name": "Palo Alto", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA", "industria": "Technology"},
    {"ticker": "AMAT", "name": "Applied Mat", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA", "industria": "Semiconductors"},
    {"ticker": "TSM", "name": "TSMC", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA", "industria": "Semiconductors"},
    {"ticker": "ASML", "name": "ASML", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA", "industria": "Semiconductors"},
    {"ticker": "SMH", "name": "Semis ETF", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA", "industria": "Semiconductors"},
    {"ticker": "PLTR", "name": "Palantir", "buy": 30, "sell": 75, "ultra": 40, "setor": "EUA", "industria": "Technology"},
    {"ticker": "APP", "name": "AppLovin", "buy": 30, "sell": 75, "ultra": 40, "setor": "EUA", "industria": "Technology"},
    {"ticker": "NFLX", "name": "Netflix", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA", "industria": "Telecom & Media"},
    {"ticker": "ANET", "name": "Arista", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA", "industria": "Technology"},
    {"ticker": "KLAC", "name": "KLA", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA", "industria": "Semiconductors"},
    {"ticker": "LRCX", "name": "Lam Research", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA", "industria": "Semiconductors"},
    {"ticker": "QCOM", "name": "Qualcomm", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA", "industria": "Semiconductors"},
    {"ticker": "NU", "name": "Nubank", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA", "industria": "Financials"},
    {"ticker": "HD", "name": "Home Depot", "buy": 35, "sell": 70, "ultra": 45, "setor": "EUA", "industria": "Consumer"},
    {"ticker": "JNJ", "name": "J&J", "buy": 35, "sell": 70, "ultra": 45, "setor": "EUA", "industria": "Healthcare"},
    {"ticker": "PG", "name": "P&G", "buy": 35, "sell": 70, "ultra": 45, "setor": "EUA", "industria": "Consumer"},
    {"ticker": "ADBE", "name": "Adobe", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA", "industria": "Technology"},
    {"ticker": "UNP", "name": "Union Pacific", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA", "industria": "Industrials"},
    {"ticker": "MELI", "name": "MercadoLibre", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA", "industria": "Consumer"},
    {"ticker": "DDOG", "name": "Datadog", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA", "industria": "Technology"},
    {"ticker": "CRWV", "name": "CoreWeave", "buy": 30, "sell": 75, "ultra": 40, "setor": "EUA", "industria": "Technology"},
    {"ticker": "GEV", "name": "GE Vernova", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA", "industria": "Industrials"},
    {"ticker": "VRT", "name": "Vertiv", "buy": 30, "sell": 70, "ultra": 40, "setor": "EUA", "industria": "Industrials"},
    {"ticker": "RKLB", "name": "Rocket Lab", "buy": 30, "sell": 75, "ultra": 40, "setor": "EUA", "industria": "Industrials"},
    {"ticker": "ASTS", "name": "AST SpaceMobile", "buy": 30, "sell": 75, "ultra": 40, "setor": "EUA", "industria": "Telecom & Media"},
    {"ticker": "HOOD", "name": "Robinhood", "buy": 30, "sell": 75, "ultra": 40, "setor": "EUA", "industria": "Financials"},
    {"ticker": "COIN", "name": "Coinbase", "buy": 30, "sell": 75, "ultra": 40, "setor": "EUA", "industria": "Financials"},
    {"ticker": "CRCL", "name": "Circle", "buy": 30, "sell": 75, "ultra": 40, "setor": "EUA", "industria": "Financials"},
    {"ticker": "SPCX", "name": "SpaceX (proxy)", "buy": 30, "sell": 75, "ultra": 40, "setor": "EUA", "industria": "Industrials"},


    # ETFs
    {"ticker": "XBI", "name": "Biotech ETF", "buy": 32, "sell": 70, "ultra": 40, "setor": "ETF"},
    {"ticker": "SPY", "name": "S&P 500 ETF", "buy": 30, "sell": 70, "ultra": 40, "setor": "ETF"},
    {"ticker": "QQQ", "name": "Nasdaq 100 ETF", "buy": 30, "sell": 70, "ultra": 40, "setor": "ETF"},
    {"ticker": "IWM", "name": "Russell 2000 ETF", "buy": 30, "sell": 70, "ultra": 40, "setor": "ETF"},
    # --- Commodities (metais, energia e agrícolas) ---
    {"ticker": "GLD", "name": "Gold", "buy": 35, "sell": 70, "ultra": 45, "setor": "Commodities"},
    {"ticker": "SLV", "name": "Silver", "buy": 32, "sell": 70, "ultra": 40, "setor": "Commodities"},
    {"ticker": "CPER", "name": "Copper", "buy": 35, "sell": 70, "ultra": 45, "setor": "Commodities"},
    {"ticker": "CL=F", "name": "WTI Oil", "buy": 32, "sell": 70, "ultra": 40, "setor": "Commodities"},
    {"ticker": "WEAT", "name": "Wheat", "buy": 32, "sell": 70, "ultra": 40, "setor": "Commodities"},
    {"ticker": "SOYB", "name": "Soybean", "buy": 32, "sell": 70, "ultra": 40, "setor": "Commodities"},


    # Moeda
    {"ticker": "BRL=X", "name": "Dolar", "buy": 32, "sell": 70, "ultra": 45, "setor": "Moeda"},

    # Brasil
    {"ticker": "ABEV3.SA", "name": "Ambev", "buy": 35, "sell": 70, "ultra": 40, "setor": "Brasil", "industria": "Consumer"},
    {"ticker": "ALUP11.SA", "name": "Alupar", "buy": 30, "sell": 70, "ultra": 40, "setor": "Brasil", "industria": "Utilities"},
    {"ticker": "CMIG4.SA", "name": "Cemig", "buy": 30, "sell": 70, "ultra": 40, "setor": "Brasil", "industria": "Utilities"},
    {"ticker": "CPFE3.SA", "name": "CPFL Energia", "buy": 30, "sell": 70, "ultra": 40, "setor": "Brasil", "industria": "Utilities"},
    {"ticker": "EGIE3.SA", "name": "Engie Brasil", "buy": 30, "sell": 70, "ultra": 40, "setor": "Brasil", "industria": "Utilities"},
    {"ticker": "TAEE11.SA", "name": "Taesa", "buy": 30, "sell": 70, "ultra": 40, "setor": "Brasil", "industria": "Utilities"},
    {"ticker": "ISAE4.SA", "name": "ISA Energia Brasil PFD", "buy": 30, "sell": 70, "ultra": 40, "setor": "Brasil", "industria": "Utilities"},
    {"ticker": "ISAE3.SA", "name": "ISA Energia Brasil ON", "buy": 30, "sell": 70, "ultra": 40, "setor": "Brasil", "industria": "Utilities"},
    {"ticker": "CPLE3.SA", "name": "Copel", "buy": 30, "sell": 70, "ultra": 40, "setor": "Brasil", "industria": "Utilities"},
    {"ticker": "EQTL3.SA", "name": "Equatorial", "buy": 30, "sell": 70, "ultra": 40, "setor": "Brasil", "industria": "Utilities"},
    {"ticker": "INBR32.SA", "name": "Banco Inter", "buy": 35, "sell": 70, "ultra": 45, "setor": "Brasil", "industria": "Financials"},
    {"ticker": "BBAS3.SA", "name": "Banco do Brasil", "buy": 30, "sell": 70, "ultra": 40, "setor": "Brasil", "industria": "Financials"},
    {"ticker": "BPAC11.SA", "name": "BTG Pactual", "buy": 30, "sell": 70, "ultra": 40, "setor": "Brasil", "industria": "Financials"},
    {"ticker": "BRSR6.SA", "name": "Banrisul", "buy": 30, "sell": 70, "ultra": 40, "setor": "Brasil", "industria": "Financials"},
    {"ticker": "BBDC4.SA", "name": "Bradesco", "buy": 30, "sell": 70, "ultra": 40, "setor": "Brasil", "industria": "Financials"},
    {"ticker": "ITUB4.SA", "name": "Itaú", "buy": 30, "sell": 70, "ultra": 40, "setor": "Brasil", "industria": "Financials"},
    {"ticker": "SANB11.SA", "name": "Santander", "buy": 30, "sell": 70, "ultra": 40, "setor": "Brasil", "industria": "Financials"},
    {"ticker": "ITSA4.SA", "name": "Itaúsa", "buy": 30, "sell": 70, "ultra": 40, "setor": "Brasil", "industria": "Financials"},
    {"ticker": "VALE3.SA", "name": "Vale", "buy": 30, "sell": 70, "ultra": 40, "setor": "Brasil", "industria": "Materials"},
    {"ticker": "PETR4.SA", "name": "Petrobras", "buy": 30, "sell": 70, "ultra": 40, "setor": "Brasil", "industria": "Energy"},
    {"ticker": "PRIO3.SA", "name": "Prio", "buy": 30, "sell": 70, "ultra": 40, "setor": "Brasil", "industria": "Energy"},
    {"ticker": "PINE4.SA", "name": "Banco Pine", "buy": 30, "sell": 70, "ultra": 40, "setor": "Brasil", "industria": "Financials"},
    {"ticker": "RANI3.SA", "name": "Irani", "buy": 30, "sell": 70, "ultra": 40, "setor": "Brasil", "industria": "Materials"},
    {"ticker": "SUZB3.SA", "name": "Suzano", "buy": 30, "sell": 70, "ultra": 40, "setor": "Brasil", "industria": "Materials"},
    {"ticker": "PSSA3.SA", "name": "Porto Seguro", "buy": 30, "sell": 70, "ultra": 40, "setor": "Brasil", "industria": "Financials"},
    {"ticker": "BBSE3.SA", "name": "BB Seguridade", "buy": 30, "sell": 70, "ultra": 40, "setor": "Brasil", "industria": "Financials"},
    {"ticker": "CXSE3.SA", "name": "Caixa Seguros", "buy": 30, "sell": 70, "ultra": 40, "setor": "Brasil", "industria": "Financials"},
    {"ticker": "CSMG3.SA", "name": "Copasa", "buy": 30, "sell": 70, "ultra": 40, "setor": "Brasil", "industria": "Utilities"},
    {"ticker": "SAPR11.SA", "name": "Sanepar", "buy": 30, "sell": 70, "ultra": 40, "setor": "Brasil", "industria": "Utilities"},
    {"ticker": "SBSP3.SA", "name": "Sabesp", "buy": 30, "sell": 70, "ultra": 40, "setor": "Brasil", "industria": "Utilities"},
    {"ticker": "VIVT3.SA", "name": "Vivo", "buy": 30, "sell": 70, "ultra": 40, "setor": "Brasil", "industria": "Telecom & Media"},
    {"ticker": "RADL3.SA", "name": "Droga Raia", "buy": 32, "sell": 70, "ultra": 40, "setor": "Brasil", "industria": "Consumer"},
    {"ticker": "WEGE3.SA", "name": "WEG", "buy": 30, "sell": 70, "ultra": 40, "setor": "Brasil", "industria": "Industrials"},
    {"ticker": "TOTS3.SA", "name": "Totvs", "buy": 30, "sell": 70, "ultra": 40, "setor": "Brasil", "industria": "Technology"},
    {"ticker": "B3SA3.SA", "name": "B3", "buy": 30, "sell": 70, "ultra": 40, "setor": "Brasil", "industria": "Financials"},
    {"ticker": "RENT3.SA", "name": "Localiza", "buy": 30, "sell": 70, "ultra": 40, "setor": "Brasil", "industria": "Industrials"},
    {"ticker": "SOJA3.SA", "name": "Boa Safra", "buy": 30, "sell": 70, "ultra": 40, "setor": "Brasil", "industria": "Agribusiness"},
    {"ticker": "KLBN4.SA", "name": "Klabin", "buy": 35, "sell": 70, "ultra": 45, "setor": "Brasil", "industria": "Materials"},
    {"ticker": "GGBR4.SA", "name": "Gerdau", "buy": 32, "sell": 70, "ultra": 40, "setor": "Brasil", "industria": "Materials"},
    {"ticker": "MULT3.SA", "name": "Multiplan", "buy": 35, "sell": 70, "ultra": 45, "setor": "Brasil", "industria": "Real Estate"},
    {"ticker": "AGRO3.SA", "name": "BrasilAgro", "buy": 35, "sell": 70, "ultra": 40, "setor": "Brasil", "industria": "Agribusiness"},
    {"ticker": "SLCE3.SA", "name": "SLC Agricola", "buy": 30, "sell": 70, "ultra": 40, "setor": "Brasil", "industria": "Agribusiness"},
    {"ticker": "FLRY3.SA", "name": "Fleury", "buy": 32, "sell": 70, "ultra": 40, "setor": "Brasil", "industria": "Healthcare"},
]


# ==========================================================
# MAIN
# ==========================================================
def _normalize_ticker(ticker: str, remove_crypto_suffix: bool = False) -> str:
    normalized = ticker.replace(".SA", "").replace("^", "")
    if remove_crypto_suffix:
        normalized = normalized.replace("-USD", "")
    return normalized


def _build_asset_row(
    asset: Dict[str, object],
    weekly: pd.Series,
    monthly: pd.Series,
    remove_crypto_suffix: bool = False,
) -> Dict[str, object]:
    """Assemble the output row from precomputed weekly/monthly snapshots.

    Independent of how the snapshots were fetched (single request or batch), so
    both paths yield identical rows."""
    ticker = str(asset["ticker"])
    weekly_rsi = round_rsi_or_nan(weekly["RSI"])
    monthly_rsi = round_rsi_or_nan(monthly["RSI"])

    # The weekly RSI is the primary signal; without it there is nothing to show
    # (e.g. a ticker with < 15 weeks of history). Skip such assets — they enter
    # automatically once enough history accrues. A missing MONTHLY RSI, however,
    # is tolerated: the asset still renders with its weekly reading.
    if pd.isna(weekly_rsi):
        raise ValueError("insufficient history for weekly RSI")

    # get_signal handles a NaN monthly gracefully: NaN comparisons are False, so
    # UltraBuy (which needs the monthly confirmation) simply can't trigger.
    signal = get_signal(
        float(weekly_rsi),
        float(monthly_rsi),
        int(asset["buy"]),
        int(asset["sell"]),
        int(asset["ultra"]),
    )

    # Confirmação por volume: semana fechada vs média das 4 anteriores.
    vol_last = float(weekly["Vol_Last"])
    vol_prev4 = float(weekly["Vol_Prev4Mean"])
    if vol_last > 0 and vol_prev4 > 0:
        vol_ratio: Optional[float] = round(vol_last / vol_prev4, 2)
        vol_high: Optional[bool] = bool(vol_ratio > 1.0)
    else:
        vol_ratio = None  # sem volume confiável (ex.: câmbio) ou histórico curto
        vol_high = None

    display_ticker = asset.get("display_ticker")
    norm_ticker = (
        str(display_ticker)
        if display_ticker
        else _normalize_ticker(ticker, remove_crypto_suffix=remove_crypto_suffix)
    )

    return {
        "Ticker": norm_ticker,
        "Yahoo_Ticker": ticker,
        "Name": asset["name"],
        "Weekly_Close": float(round(weekly["Close"], 2)),
        "Weekly_RSI": weekly_rsi,
        "Monthly_RSI": monthly_rsi,
        "Drawdown_Pct": float(round(weekly["Drawdown_Pct"], 2)),
        "Peak_Close": float(round(weekly["Peak_Close"], 2)),
        "Peak_Date": weekly["Peak_Date"],
        "Signal": signal,
        # Per-asset thresholds carried through so the dashboard's Watch-zone can
        # measure each asset's distance to its OWN buy/sell trigger (not a generic
        # 30/70). Buy fires at RSI<=buy; Sell fires at RSI>=sell.
        "Buy_Threshold": int(asset["buy"]),
        "Sell_Threshold": int(asset["sell"]),
        "Vol_Ratio": vol_ratio,
        "Vol_High": vol_high,
        "Setor": asset.get("setor", ""),
        "Industria": str(asset.get("industria", "")),
    }


def fetch_asset_rsi(asset: Dict[str, object], remove_crypto_suffix: bool = False) -> Dict[str, object]:
    """Fetch a single asset (weekly + monthly, two HTTP requests) and build its row.

    Used as the per-ticker fallback when the bulk download misses a ticker, and
    directly by callers that need one asset in isolation."""
    ticker = str(asset["ticker"])
    weekly = calculate_rsi(ticker, interval="1wk", window=14, period="5y")
    monthly = calculate_rsi(ticker, interval="1mo", window=14, period="5y")
    return _build_asset_row(asset, weekly, monthly, remove_crypto_suffix=remove_crypto_suffix)


def collect_rsi_data(
    asset_list: Optional[List[Dict[str, object]]] = None,
    remove_crypto_suffix: bool = False,
) -> pd.DataFrame:
    """Fetch RSI/volume/drawdown snapshots for every asset.

    Fast path: two bulk downloads (all weekly bars, all monthly bars) instead of
    ~2 requests per asset, collapsing hundreds of round-trips to a handful. Any
    ticker missing from a batch falls back to a single-ticker fetch, so transient
    Yahoo throttling no longer silently drops assets from the universe.
    """
    asset_list = list(asset_list or assets)
    tickers = [str(a["ticker"]) for a in asset_list]

    weekly_batch = _download_batch(tickers, interval="1wk", period="5y")
    monthly_batch = _download_batch(tickers, interval="1mo", period="5y")

    results: List[Dict[str, object]] = []
    fallbacks = 0
    for asset in asset_list:
        ticker = str(asset["ticker"])
        wdf = weekly_batch.get(ticker)
        mdf = monthly_batch.get(ticker)

        # Fast path: both series arrived in the bulk download.
        if wdf is not None and mdf is not None:
            try:
                weekly = _compute_rsi_row(wdf, 14)
                monthly = _compute_rsi_row(mdf, 14)
                results.append(_build_asset_row(asset, weekly, monthly,
                                                 remove_crypto_suffix=remove_crypto_suffix))
                continue
            except ValueError as exc:
                # Genuinely too little history (e.g. a just-listed ticker) — no
                # point refetching, it would fail the same way.
                if "insufficient history" in str(exc):
                    print(f"[WARN] {ticker}: {exc}")
                    continue
                # Unexpected compute error → try a clean single fetch below.

        # Fallback: missing from a batch, or an unexpected batch compute error.
        try:
            results.append(fetch_asset_rsi(asset, remove_crypto_suffix=remove_crypto_suffix))
            fallbacks += 1
        except Exception as exc:
            print(f"[WARN] {ticker}: {exc}")

    if fallbacks:
        print(f"  [batch] {len(results)}/{len(asset_list)} assets "
              f"({fallbacks} recovered via single-fetch fallback)")
    return pd.DataFrame(results)


def main() -> None:
    df = collect_rsi_data()
    if df.empty:
        print("RSI Monitor\nSem dados hoje (yfinance retornou vazio).")
        return

    print(formatar_mensagem(df))


if __name__ == "__main__":
    main()
