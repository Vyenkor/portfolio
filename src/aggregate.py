import requests, csv, json
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"; DATA.mkdir(exist_ok=True)
CFG = ROOT / "config" / "assets.json"

AGG = DATA / "agg_latest.csv"      # 最新快照（Excel 订阅它）
HIST = DATA / "history.csv"        # 历史累计（每天/每小时追加）

def load_cfg():
    with open(CFG, "r", encoding="utf-8") as f:
        return json.load(f)

# ---------- Fund helpers (天天基金/DoctorXiong) ----------
def fetch_fund_doctorxiong(code):
    url = f"https://api.doctorxiong.club/v1/fund?code={code}"
    r = requests.get(url, timeout=12)
    if r.ok:
        jd = r.json(); d = jd.get("data") or {}
        if d:
            return {
                "type":"fund", "id":code,
                "name": d.get("name") or d.get("fund_name"),
                "nav_date": d.get("jzrq") or d.get("date"),
                "nav": d.get("dwjz") or d.get("net_value"),
                "est_nav": d.get("gsz") or d.get("estimate"),
                "est_chg_24h_pct": d.get("gszzl") or d.get("percent")
            }

def fetch_fund_fundgz(code):
    url = f"https://fundgz.1234567.com.cn/js/{code}.js"
    r = requests.get(url, timeout=12)
    t = r.text.strip()
    if t.startswith("jsonpgz(") and t.endswith(");"):
        body = t[t.find("(")+1:-2].strip()
        if body and body != "{}":
            d = json.loads(body)
            return {
                "type":"fund", "id":code,
                "name": d.get("name"),
                "nav_date": d.get("jzrq"),
                "nav": d.get("dwjz"),
                "est_nav": d.get("gsz"),
                "est_chg_24h_pct": d.get("gszzl")
            }

def fetch_funds(codes):
    out=[]
    for c in codes:
        it = fetch_fund_doctorxiong(c) or fetch_fund_fundgz(c)
        if it: out.append(it)
    return out

# ---------- CoinGecko helpers ----------
def cg_markets(ids, vs):
    url = ("https://api.coingecko.com/api/v3/coins/markets"
           f"?vs_currency={vs}&ids={','.join(ids)}"
           "&price_change_percentage=1h,24h,7d,30d&precision=full")
    r = requests.get(url, timeout=20); r.raise_for_status()
    return r.json()

def merge_vs(rows_by_vs):
    bag = defaultdict(dict)
    for vs, arr in rows_by_vs.items():
        for it in arr:
            cid = it["id"]; bag[cid]["id"]=cid; bag[cid]["name"]=it["name"]
            bag[cid][f"price_{vs}"] = it.get("current_price")
            def g(k): return it.get(f"price_change_percentage_{k}_in_currency")
            bag[cid][f"chg_1h_pct_{vs}"]  = g("1h")
            bag[cid][f"chg_24h_pct_{vs}"] = g("24h")
            bag[cid][f"chg_7d_pct_{vs}"]  = g("7d")
            bag[cid][f"chg_30d_pct_{vs}"] = g("30d")
    return list(bag.values())

# ---------- write CSVs ----------
def ensure_hist_header():
    if not HIST.exists():
        with open(HIST,"w",newline="",encoding="utf-8") as f:
            csv.writer(f).writerow([
                "ts_utc","kind","id","name","nav_date_or_ts",
                "nav_or_price","chg_24h_pct","vs"
            ])

def write_latest(fund_rows, coin_rows_by_vs):
    headers = [
        "kind","id","name","nav_date_or_ts",
        "nav_or_price","chg_24h_pct","vs","ts_utc"
    ]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    with open(AGG,"w",newline="",encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(headers)
        # funds（估算净值优先）
        for r in fund_rows:
            w.writerow(["fund", r["id"], r.get("name"), r.get("nav_date"),
                        r.get("est_nav") or r.get("nav"), r.get("est_chg_24h_pct"), "", now])
        # coins（按 vs 写多行）
        for vs, arr in coin_rows_by_vs.items():
            for it in arr:
                w.writerow(["crypto", it["id"], it["name"], now,
                            it.get("current_price"), it.get("price_change_percentage_24h_in_currency"),
                            vs, now])

def append_history(fund_rows, coin_rows_by_vs):
    ensure_hist_header()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    with open(HIST,"a",newline="",encoding="utf-8") as f:
        w = csv.writer(f)
        for r in fund_rows:
            w.writerow([now,"fund",r["id"],r.get("name"),r.get("nav_date"),
                        r.get("est_nav") or r.get("nav"), r.get("est_chg_24h_pct"), "" ])
        for vs, arr in coin_rows_by_vs.items():
            for it in arr:
                w.writerow([now,"crypto",it["id"],it["name"],now,
                            it.get("current_price"), it.get("price_change_percentage_24h_in_currency"), vs])

def main():
    cfg = load_cfg()
    funds = fetch_funds(cfg.get("funds",[]))
    coin_rows_by_vs={}
    for vs in cfg.get("vs",["usd"]):
        coin_rows_by_vs[vs]=cg_markets(cfg.get("coins",[]), vs)
    write_latest(funds, coin_rows_by_vs)
    append_history(funds, coin_rows_by_vs)
    print("OK: agg_latest.csv & history.csv written/appended.")

if __name__=="__main__":
    main()
