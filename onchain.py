from __future__ import annotations

import time
from datetime import datetime
from typing import Optional, Tuple, Dict, Callable

import requests

CM_BASE = "https://community-api.coinmetrics.io/v4"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/145 Safari/537.36"
)

DEBUG = False  # True = inclui cap/supply no quadro

MvrvSnapshot = Tuple[float, float, float, float, float]


# ==========================================================
# COINMETRICS
# ==========================================================
def coinmetrics_price_realized_mvrv(
    asset: str,
    retries: int = 3,
    wait_sec: int = 10,
    timeout: int = 30,
    verify_ssl: bool = True,
) -> MvrvSnapshot:
    """
    Retorna: (price, realized_price, mvrv, cap_mrkt_usd, supply)

    Observação:
      - price = CapMrktCurUSD / SplyCur
      - realized_price = price / CapMVRVCur  (porque CapMVRVCur = price/realized)
    """
    url = f"{CM_BASE}/timeseries/asset-metrics"
    params = {
        "assets": asset.lower(),
        "metrics": "CapMrktCurUSD,SplyCur,CapMVRVCur",
        "frequency": "1d",
        "page_size": 30,
    }

    last_exc: Optional[Exception] = None
    for attempt in range(1, retries + 1):
        try:
            r = requests.get(
                url,
                params=params,
                headers={"User-Agent": UA, "Accept": "application/json"},
                timeout=timeout,
                verify=verify_ssl,
            )
            if r.status_code != 200:
                raise RuntimeError(f"CoinMetrics HTTP {r.status_code}: {r.text[:500]}")

            js = r.json()
            rows = js.get("data", [])
            if not rows:
                raise RuntimeError("CoinMetrics retornou data vazio.")

            row = None
            for candidate in reversed(rows):
                if all(
                    candidate.get(k) not in (None, "", "NaN")
                    for k in ("CapMrktCurUSD", "SplyCur", "CapMVRVCur")
                ):
                    row = candidate
                    break
            if row is None:
                raise RuntimeError("Não achei linha válida com CapMrktCurUSD/SplyCur/CapMVRVCur.")

            cap = float(row["CapMrktCurUSD"])
            sply = float(row["SplyCur"])
            mvrv = float(row["CapMVRVCur"])

            if sply <= 0 or mvrv <= 0:
                raise RuntimeError(f"Valores inválidos: SplyCur={sply}, MVRV={mvrv}")

            price = cap / sply
            realized = price / mvrv

            return price, realized, mvrv, cap, sply

        except Exception as e:
            last_exc = e
            if attempt < retries:
                time.sleep(wait_sec)
            else:
                raise RuntimeError(
                    f"Falhou CoinMetrics ({asset}) após {retries} tentativas: {last_exc}"
                ) from last_exc

    raise RuntimeError(f"Falhou CoinMetrics ({asset}): {last_exc}")


# ==========================================================
# CLASSIFICAÇÃO
#   - BTC: sua regra original
#   - ETH: regra mais conservadora (baseada nos cenários)
# ==========================================================
def classify_mvrv_btc(mvrv: float) -> Dict[str, str]:
    if mvrv < 0.85:
        return {"zone": "CAPITULATION", "opportunity": "🟢⭐⭐⭐⭐⭐", "risk": "VERY LOW", "action": "BUY HEAVY"}
    if mvrv < 1.00:
        return {"zone": "DEEP VALUE", "opportunity": "🟢⭐⭐⭐⭐⭐", "risk": "LOW", "action": "ACCUMULATE STRONG"}
    if mvrv < 1.20:
        return {"zone": "BUY ZONE", "opportunity": "🟢⭐⭐⭐⭐", "risk": "MEDIUM", "action": "ACCUMULATE / DCA"}
    if mvrv < 2.00:
        return {"zone": "NEUTRAL", "opportunity": "🔵⭐⭐", "risk": "MEDIUM", "action": "HOLD / DCA"}
    if mvrv < 3.50:
        return {"zone": "HIGH RISK", "opportunity": "🟠⭐", "risk": "HIGH", "action": "REDUCE"}
    return {"zone": "EUPHORIA", "opportunity": "🔴☠", "risk": "EXTREME", "action": "TAKE PROFIT"}


def classify_mvrv_eth(mvrv: float) -> Dict[str, str]:
    if mvrv < 0.60:
        return {"zone": "HISTORIC ZONE", "opportunity": "🟢🟢⭐⭐⭐⭐⭐",
                "risk": "VERY LOW", "action": "BUY HEAVY"}

    if mvrv < 0.75:
        return {"zone": "EXTREME CAPITULATION", "opportunity": "🟢⭐⭐⭐⭐⭐",
                "risk": "LOW", "action": "BUY HEAVY"}

    if mvrv < 0.85:
        return {"zone": "CAPITULATION", "opportunity": "🟢⭐⭐⭐⭐",
                "risk": "HIGH", "action": "ACCUMULATE STRONG"}

    if mvrv < 0.90:
        return {"zone": "DEEP VALUE", "opportunity": "🟢⭐⭐⭐",
                "risk": "MEDIUM", "action": "ACCUMULATE"}

    if mvrv < 1.00:
        return {"zone": "VALUE (BELOW REALIZED)", "opportunity": "🟡⭐⭐⭐",
                "risk": "MEDIUM", "action": "FIRST BUY ZONE"}

    # ===== NÃO COMPRA =====
    if mvrv < 1.30:
        return {"zone": "FAIR VALUE", "opportunity": "🔵⭐⭐",
                "risk": "MEDIUM", "action": "HOLD"}

    if mvrv < 2.00:
        return {"zone": "PREMIUM", "opportunity": "🔵⭐",
                "risk": "MEDIUM/HIGH", "action": "STOP BUY"}

    # ===== RISCO ALTO =====
    if mvrv < 2.40:
        return {"zone": "OVERHEATED", "opportunity": "🟠⭐",
                "risk": "HIGH", "action": "REDUCE"}

    if mvrv < 2.70:
        return {"zone": "TOP ZONE", "opportunity": "🔴⭐",
                "risk": "VERY HIGH", "action": "DISTRIBUTE"}

    return {"zone": "EUPHORIA", "opportunity": "🔴☠",
            "risk": "EXTREME", "action": "TAKE PROFIT"}


CLASSIFIERS: Dict[str, Callable[[float], Dict[str, str]]] = {
    "BTC": classify_mvrv_btc,
    "ETH": classify_mvrv_eth,
}


# ==========================================================
# FORMATAÇÃO
# ==========================================================
def mk_block(
    asset_label: str,
    price: float,
    realized: float,
    mvrv: float,
    cap: float,
    sply: float,
) -> str:
    pct = (mvrv - 1.0) * 100.0
    classifier = CLASSIFIERS.get(asset_label.upper(), classify_mvrv_btc)
    cls = classifier(mvrv)

    lines = [
        f"{asset_label} (CoinMetrics)",
        "-------------------------",
        f"{'PRICE':<12}{price:>12,.0f}",
        f"{'REALIZED':<12}{realized:>12,.0f}",
        f"{'MVRV':<12}{mvrv:>12.4f}",
        f"{'ABOVE RP%':<12}{pct:>11.1f}%",
        f"{'ZONE':<12}{cls['zone']}",
        f"{'OPPORT':<12}{cls['opportunity']}",
        f"{'RISK':<12}{cls['risk']}",
        f"{'ACTION':<12}{cls['action']}",
    ]

    if DEBUG:
        lines += [
            "-----",
            f"{'CAPUSD':<12}{cap:>12,.0f}",
            f"{'SUPPLY':<12}{sply:>12,.0f}",
        ]

    return "\n".join(lines)


def mk_msg_combined(
    eth: MvrvSnapshot,
    btc: MvrvSnapshot,
) -> str:
    now = datetime.now().strftime("%d/%m/%Y %H:%M")

    eth_price, eth_realized, eth_mvrv, eth_cap, eth_sply = eth
    btc_price, btc_realized, btc_mvrv, btc_cap, btc_sply = btc

    body = "\n\n".join([
        mk_block("ETH", eth_price, eth_realized, eth_mvrv, eth_cap, eth_sply),
        mk_block("BTC", btc_price, btc_realized, btc_mvrv, btc_cap, btc_sply),
    ])

    return (
        f"*🧠 On-chain Monitor — {now}*\n"
        "```\n"
        f"{body}\n"
        "```"
    )


# ==========================================================
# MAIN
# ==========================================================
def main() -> None:
    eth = coinmetrics_price_realized_mvrv("eth")
    btc = coinmetrics_price_realized_mvrv("btc")

    print(mk_msg_combined(eth, btc))


if __name__ == "__main__":
    main()
