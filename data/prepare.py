"""UCI Online Retail II → 주간 발주 후보 200건 (스펙 §1)."""
import json
import random
import urllib.request
import zipfile

import pandas as pd

from agent.settings import DATA_WEEKS, DEMO_WEEKS, DEV_WEEK, N_ITEMS, ROOT, SEED, TEST_WEEKS

RAW = ROOT / "data" / "raw"
URL = "https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip"
XLSX = RAW / "online_retail_II.xlsx"
CODE_RE = r"^\d{5}[A-Z]?$"


def download():
    RAW.mkdir(parents=True, exist_ok=True)
    if XLSX.exists():
        return XLSX
    z = RAW / "online_retail_ii.zip"
    urllib.request.urlretrieve(URL, z)
    with zipfile.ZipFile(z) as f:
        f.extractall(RAW)
    return XLSX


def load_raw(path):
    text = {"Invoice": str, "StockCode": str, "Description": str, "Country": str}
    sheets = pd.read_excel(path, sheet_name=None, dtype=text)
    return pd.concat(sheets.values(), ignore_index=True)


def clean(df):
    df = df[(df.Quantity > 0) & (df.Price > 0)]
    df = df[~df.Invoice.str.startswith("C")]
    df = df[df.StockCode.str.match(CODE_RE, na=False)]
    return df.copy()


def weekly(df):
    df = df.assign(week=df.InvoiceDate.dt.to_period("W-SUN").dt.start_time)
    w = df.groupby(["StockCode", "week"]).Quantity.sum().unstack(fill_value=0)
    full = pd.date_range(w.columns.min(), w.columns.max(), freq="7D")   # 판매가 없던 주도 0으로
    w = w.reindex(columns=full, fill_value=0)
    price = df.groupby("StockCode").Price.median()
    names = (df.dropna(subset=["Description"]).groupby("StockCode").Description
               .agg(lambda s: s.mode().iat[0]))
    return w, price, names


def _col(w, week):
    return list(w.columns).index(pd.Timestamp(week))


def candidates(w, week):
    i = _col(w, week)
    hist = w.iloc[:, i - 8:i]
    return sorted(hist.index[(hist > 0).sum(axis=1) >= 6])


def build_week(w, price, names, week, n=N_ITEMS, seed=SEED):
    i = _col(w, week)
    codes = random.Random(seed).sample(candidates(w, week), n)
    items, actual = [], {}
    for code in codes:
        h = [int(x) for x in w.loc[code].iloc[i - 8:i]]
        s = pd.Series(h, dtype=float)
        mean8, std8 = float(s.mean()), float(s.std())
        items.append({"code": code, "name_en": str(names.get(code, code)).strip(),
                      "price_gbp": round(float(price[code]), 2), "hist8": h,
                      "mean8": round(mean8, 2), "std8": round(std8, 2),
                      "cv8": round(std8 / mean8, 3), "last_week": h[-1]})
        actual[code] = int(w.loc[code].iloc[i])
    return {"week": week, "items": items}, {"week": week, "actual": actual}


def main():
    df = clean(load_raw(download()))
    w, price, names = weekly(df)
    DATA_WEEKS.mkdir(parents=True, exist_ok=True)
    for week in (DEV_WEEK, *TEST_WEEKS, *DEMO_WEEKS):
        items, answers = build_week(w, price, names, week)
        (DATA_WEEKS / f"{week}.json").write_text(
            json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
        (DATA_WEEKS / f"{week}.answers.json").write_text(
            json.dumps(answers, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{week}: 후보 {len(candidates(w, week))}개 중 {len(items['items'])}건")


if __name__ == "__main__":
    main()
