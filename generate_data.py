"""
generate_data.py  —  Real-data snapshot for the HSBC Life ILP Fund Selector (yfinance)
=====================================================================================
Run this LOCALLY (yfinance reaches Yahoo from your machine, not from a browser and
not from a locked-down sandbox). It writes funds-data.json next to index.html.
index.html loads that file and uses real series where available, falling back to its
built-in simulated series for any fund left unmapped.

WHAT YAHOO GIVES YOU (and what it doesn't)
  - NAV history  ............ yes, for the *underlying* fund's listed share class.
  - 1y/3y/5y + vol .......... computed here from that history.
  - Sector / asset split .... often yes (Ticker.funds_data) for larger funds.
  - Geographic split ........ usually NO from Yahoo -> page falls back + labels it.
  - Analyst buy/sell ........ N/A for funds (only single stocks). The page's signal
                              is a technical read computed from the NAV series.

IMPORTANT HONESTY FLAG
  Yahoo lists the UNDERLYING fund (often a USD/EUR base share class), not the
  SGD-hedged ILP sub-fund the policy actually credits. Returns will be close but
  not identical. Output is marked "proxy": true and the page labels it as such.

USAGE
  1. pip install yfinance pandas
  2. Fill FUND_MAP below: each fund code -> an ISIN (auto-resolved to a Yahoo symbol)
     OR a Yahoo symbol directly (use this when auto-resolve misses, e.g. "0P00012ABC.F").
  3. Optionally tune BENCHMARK_SYMBOLS (ETF proxies for each index).
  4. python generate_data.py
  5. Commit funds-data.json next to index.html.
"""

import json
import datetime as dt
import time

try:
    import yfinance as yf
    import pandas as pd
except ImportError:
    raise SystemExit("Install deps first:  pip install yfinance pandas")

YEARS = 5

# ---------------------------------------------------------------------------
# 1) FUND CODE -> ISIN or Yahoo symbol.   Fill in the ones you care about.
#    - Put an ISIN ("LU000...")  -> script resolves it to a Yahoo symbol via search.
#    - Put a Yahoo symbol ("0P0001ABC.F" / "IUSA.L") -> used directly (more reliable).
#    - Leave as None / omit       -> page keeps its simulated series for that fund.
#    The example entries below are placeholders — replace with your real values.
# ---------------------------------------------------------------------------
FUND_MAP = {
    # "ZAGA": "LU1548497426",   # ISIN -> auto-resolve
    # "ZAAI": "0P0000ABCD.F",   # Yahoo symbol -> direct
    # "ZBWG": "IE00B5MTWD60",
    # ... add the codes you want live data for ...
}

# ---------------------------------------------------------------------------
# 2) Benchmark index -> Yahoo symbol (liquid ETF/index proxies). Edit freely.
#    None => skipped (page will rebase only the fund line).
# ---------------------------------------------------------------------------
BENCHMARK_SYMBOLS = {
    "S&P 500":                          "^GSPC",
    "MSCI ACWI":                        "ACWI",
    "MSCI World Information Tech":       "IXN",
    "MSCI World Health Care":           "IXJ",
    "NASDAQ Biotechnology":             "IBB",
    "NYSE Arca Gold Miners":            "GDX",
    "MSCI Europe":                      "IEV",
    "MSCI China":                       "MCHI",
    "MSCI AC Asia Pac ex-Japan":        "AAXJ",
    "MSCI Emerging Markets":            "EEM",
    "MSCI AC ASEAN":                    "ASEA",
    "MSCI India":                       "INDA",
    "Straits Times Index":              "ES3.SI",
    "Bloomberg US Aggregate":           "AGG",
    "Bloomberg Global Aggregate":       "BNDW",
    "Bloomberg Global High Yield":      "HYG",
    "JPM EMBI Global":                  "EMB",
    "Bloomberg Global Agg 1-3Y":        "ISTB",
    "JPM Asia Credit (JACI)":           "EMB",     # rough proxy; swap if you have better
    "Markit iBoxx SGD":                 None,       # no clean Yahoo proxy
    "60/40 Global (ACWI / Global Agg)": "AOR",      # iShares Core 60/40
}

# ---------------------------------------------------------------------------
# 3) Fund code -> benchmark NAME (kept in sync with index.html's benchmarkFor()).
# ---------------------------------------------------------------------------
FUND_BENCHMARK = {
    "ZAAI": "Bloomberg US Aggregate", "YAAI": "Bloomberg US Aggregate",
    "ZAIH": "MSCI World Health Care", "YAIH": "MSCI World Health Care",
    "ZASG": "MSCI ACWI", "YASG": "MSCI ACWI",
    "ZALC": "MSCI China", "YALC": "MSCI China",
    "ZAGA": "MSCI World Information Tech", "YAGA": "MSCI World Information Tech",
    "ZAIG": "60/40 Global (ACWI / Global Agg)", "YAIG": "60/40 Global (ACWI / Global Agg)",
    "ZBAT": "JPM Asia Credit (JACI)", "YBAT": "JPM Asia Credit (JACI)",
    "ZBEE": "MSCI Europe", "YBEE": "MSCI Europe",
    "ZBGA": "60/40 Global (ACWI / Global Agg)", "YBGA": "60/40 Global (ACWI / Global Agg)",
    "ZBGH": "Bloomberg Global High Yield", "YBGH": "Bloomberg Global High Yield",
    "ZBWG": "NYSE Arca Gold Miners", "YBWG": "NYSE Arca Gold Miners",
    "ZCGG": "Bloomberg Global High Yield", "YCGG": "Bloomberg Global High Yield",
    "ZCGN": "MSCI ACWI", "YCGN": "MSCI ACWI",
    "ZFSB": "60/40 Global (ACWI / Global Agg)",
    "ZFBD": "NASDAQ Biotechnology", "YFBD": "NASDAQ Biotechnology",
    "ZFIF": "60/40 Global (ACWI / Global Agg)", "YFIF": "60/40 Global (ACWI / Global Agg)",
    "ZFTF": "MSCI World Information Tech", "FTEC": "MSCI World Information Tech",
    "ZFUO": "S&P 500", "YFUO": "S&P 500",
    "ZFDA": "MSCI AC Asia Pac ex-Japan", "YFDA": "MSCI AC Asia Pac ex-Japan",
    "ZFSR": "MSCI China", "YFSR": "MSCI China",
    "ZHAJ": "MSCI AC Asia Pac ex-Japan", "YHAP": "MSCI AC Asia Pac ex-Japan",
    "ZHGE": "MSCI ACWI", "YHGE": "MSCI ACWI",
    "ZHGH": "Bloomberg Global High Yield", "YHGH": "Bloomberg Global High Yield",
    "ZHGS": "Bloomberg Global Agg 1-3Y", "YHGS": "Bloomberg Global Agg 1-3Y",
    "ZHMS": "60/40 Global (ACWI / Global Agg)", "YHMS": "60/40 Global (ACWI / Global Agg)",
    "ZHSD": "Markit iBoxx SGD", "YHSD": "Markit iBoxx SGD",
    "HIEF": "MSCI India", "YHIE": "MSCI India",
    "ZHW1": "60/40 Global (ACWI / Global Agg)", "YHW1": "60/40 Global (ACWI / Global Agg)",
    "ZHW2": "60/40 Global (ACWI / Global Agg)", "YHW2": "60/40 Global (ACWI / Global Agg)",
    "ZHW3": "60/40 Global (ACWI / Global Agg)", "YHW3": "60/40 Global (ACWI / Global Agg)",
    "ZHW4": "60/40 Global (ACWI / Global Agg)", "YHW4": "60/40 Global (ACWI / Global Agg)",
    "ZHW5": "60/40 Global (ACWI / Global Agg)", "YHW5": "60/40 Global (ACWI / Global Agg)",
    "ZDNA": "MSCI ACWI", "YDNA": "MSCI ACWI",
    "ZJTL": "MSCI World Information Tech", "YJTL": "MSCI World Information Tech",
    "ZJAE": "MSCI AC ASEAN", "YJAE": "MSCI AC ASEAN",
    "ZPEM": "JPM EMBI Global", "YPEM": "JPM EMBI Global",
    "PGIF": "Bloomberg Global Aggregate", "YPIF": "Bloomberg Global Aggregate",
    "ZSAG": "MSCI AC Asia Pac ex-Japan", "YSAG": "MSCI AC Asia Pac ex-Japan",
    "ZSIE": "60/40 Global (ACWI / Global Agg)", "YSIE": "60/40 Global (ACWI / Global Agg)",
    "ZSEM": "MSCI Emerging Markets", "YSEM": "MSCI Emerging Markets",
    "ZSIS": "60/40 Global (ACWI / Global Agg)", "YSIS": "60/40 Global (ACWI / Global Agg)",
    "ZSST": "Straits Times Index", "YSST": "Straits Times Index",
}

SECTOR_PRETTY = {
    "realestate": "Real Estate", "consumer_cyclical": "Consumer Cyclical",
    "basic_materials": "Basic Materials", "consumer_defensive": "Consumer Defensive",
    "technology": "Technology", "communication_services": "Communication Svcs",
    "financial_services": "Financial Services", "utilities": "Utilities",
    "industrials": "Industrials", "energy": "Energy", "healthcare": "Healthcare",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
_search_cache = {}

def is_isin(s):
    return isinstance(s, str) and len(s) == 12 and s[:2].isalpha() and s[2:].isalnum()

def resolve_symbol(key):
    """key is an ISIN or a Yahoo symbol. Return a Yahoo symbol or None."""
    if not key:
        return None
    if not is_isin(key):
        return key  # already a symbol
    if key in _search_cache:
        return _search_cache[key]
    sym = None
    try:
        res = yf.Search(key, max_results=8, raise_errors=False)
        quotes = getattr(res, "quotes", []) or []
        # prefer mutual funds / ETFs, then anything
        for want in ("MUTUALFUND", "ETF", "EQUITY", None):
            for q in quotes:
                if want is None or q.get("quoteType") == want:
                    sym = q.get("symbol")
                    break
            if sym:
                break
    except Exception as e:
        print(f"      search failed for {key}: {e}")
    _search_cache[key] = sym
    return sym

def fetch_history(symbol):
    """Return a pandas Series of adjusted close indexed by date, ~5y daily."""
    t = yf.Ticker(symbol)
    df = t.history(period=f"{YEARS}y", interval="1d", auto_adjust=True)
    if df is None or df.empty or "Close" not in df:
        return None, t
    s = df["Close"].dropna()
    s.index = s.index.tz_localize(None)
    return s, t

def fund_currency(t):
    for getter in (lambda: t.fast_info.get("currency"),
                   lambda: t.info.get("currency")):
        try:
            c = getter()
            if c:
                return c
        except Exception:
            pass
    return None

def compute_returns(s):
    import math
    v = s.values
    def back(days):
        i = max(0, len(v) - 1 - days)
        return round((v[-1] / v[i] - 1) * 100, 1)
    rets = [math.log(v[i] / v[i - 1]) for i in range(1, len(v)) if v[i - 1] > 0]
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / len(rets)
    vol = round((var * 252) ** 0.5 * 100, 1)
    return {"1y": back(252), "3y": back(756), "5y": back(min(len(v) - 1, 1299)), "vol": vol}

def fetch_allocations(t):
    """Return (sector_dict, asset_dict). Geo is not available from Yahoo."""
    sector, asset = {}, {}
    try:
        fd = t.funds_data
        sw = getattr(fd, "sector_weightings", None) or {}
        sector = {SECTOR_PRETTY.get(k, k.replace("_", " ").title()): round(v * 100, 1)
                  for k, v in sw.items() if v and v > 0}
        ac = getattr(fd, "asset_classes", None) or {}
        labels = {"stockPosition": "Equities", "bondPosition": "Fixed Income",
                  "cashPosition": "Cash", "preferredPosition": "Preferred",
                  "convertiblePosition": "Convertibles", "otherPosition": "Other"}
        asset = {labels.get(k, k): round(v * 100, 1)
                 for k, v in ac.items() if v and v > 0}
    except Exception as e:
        print(f"      allocations unavailable: {e}")
    return sector, asset

def align_benchmark(fund_series, bench_series):
    """Reindex benchmark onto fund dates (forward-fill). Return list aligned to fund."""
    bs = bench_series.reindex(fund_series.index, method="ffill").bfill()
    return [round(float(x), 4) for x in bs.values]

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    asof = dt.date.today().strftime("%Y-%m-%d")
    out = {}
    bench_cache = {}

    if not FUND_MAP:
        print("FUND_MAP is empty — fill in at least one code -> ISIN/symbol. Nothing to do.")
        return

    for code, key in FUND_MAP.items():
        if not key:
            continue
        print(f"[{code}] resolving {key} ...")
        symbol = resolve_symbol(key)
        if not symbol:
            print(f"      no Yahoo symbol found -> page will use simulated data")
            continue
        series, t = fetch_history(symbol)
        if series is None or len(series) < 60:
            print(f"      no usable history for {symbol} -> skipped")
            continue

        rec = {
            "proxy": True,
            "symbol": symbol,
            "isin": key if is_isin(key) else None,
            "currency": fund_currency(t),
            "asof": asof,
            "nav": {
                "dates": [d.strftime("%Y-%m-%d") for d in series.index],
                "values": [round(float(x), 4) for x in series.values],
            },
            "returns": compute_returns(series),
        }

        sector, asset = fetch_allocations(t)
        if sector:
            rec["sector"] = sector
        elif asset:
            rec["sector"] = asset      # multi-asset funds: show the asset split
        rec["geo"] = {}                # Yahoo doesn't provide it; page falls back

        # benchmark
        bname = FUND_BENCHMARK.get(code)
        bsym = BENCHMARK_SYMBOLS.get(bname) if bname else None
        if bsym:
            if bsym not in bench_cache:
                bser, _ = fetch_history(bsym)
                bench_cache[bsym] = bser
            bser = bench_cache[bsym]
            if bser is not None and not bser.empty:
                rec["benchmark"] = {"name": bname, "symbol": bsym,
                                    "values": align_benchmark(series, bser)}
        if bname and "benchmark" not in rec:
            rec["benchmark"] = {"name": bname, "symbol": None, "values": None}

        out[code] = rec
        print(f"      OK  {symbol}  {len(series)} pts  "
              f"1y={rec['returns']['1y']}%  ccy={rec['currency']}  "
              f"sector={'y' if rec.get('sector') else 'n'}  "
              f"bench={'y' if rec.get('benchmark',{}).get('values') else 'n'}")
        time.sleep(0.4)  # be gentle with Yahoo

    with open("funds-data.json", "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nWrote funds-data.json — {len(out)} funds (as of {asof}).")
    print("Commit it next to index.html. Unmapped funds keep the simulated series.")

if __name__ == "__main__":
    main()
