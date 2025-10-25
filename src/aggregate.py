import requests, csv, json
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"; DATA.mkdir(exist_ok=True)
CFG = ROOT / "config" / "assets.json"

AGG = DATA / "agg_latest.csv"      # 最新快照（Excel 订阅它）
HIST = DATA / "history.csv"        # 历史累计（每天/每小时追加）

# 英/中文表头映射（顺序与当前CSV一致）
HEADERS_EN = ["kind","id","name","nav_date_or_ts","nav_or_price","chg_24h_pct","vs","ts_utc"]
HEADERS_ZH = ["类型","标的ID/代码","名称","净值日期/时间","价格/净值","24h涨跌幅(%)","计价币种","抓取时间(UTC)"]

def pick_headers(cfg):
    lang = (cfg.get("headers_lang", "en")).lower()  # 在 config/assets.json 里写 "headers_lang": "zh"
    return HEADERS_ZH if lang.startswith("zh") else HEADERS_EN


def load_cfg():
    with open(CFG, "r", encoding="utf-8") as f:
        return json.load(f)

# ---------- Fund helpers (天天基金/DoctorXiong) ----------
def fetch_fund_doctorxiong(code):
    url = f"https://api.doctorxiong.club/v1/fund?code={code}"
    try:
        r = requests.get(url, timeout=8, headers={"User-Agent":"Mozilla/5.0"})
        if r.ok:
            jd = r.json(); d = jd.get("data") or {}
            if d:
                return {
                    "type":"fund","id":code,
                    "name": d.get("name") or d.get("fund_name"),
                    "nav_date": d.get("jzrq") or d.get("date"),
                    "nav": d.get("dwjz") or d.get("net_value"),
                    "est_nav": d.get("gsz") or d.get("estimate"),
                    "est_chg_24h_pct": d.get("gszzl") or d.get("percent")
                }
    except Exception:
        return None
    return None


def fetch_fund_fundgz(code):
    url = f"https://fundgz.1234567.com.cn/js/{code}.js"
    try:
        r = requests.get(
            url, timeout=8,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://fund.eastmoney.com"
            }
        )
        t = r.text.strip()
        if t.startswith("jsonpgz(") and t.endswith(");"):
            body = t[t.find("(")+1:-2].strip()
            if body and body != "{}":
                d = json.loads(body)
                return {
                    "type":"fund","id":code,
                    "name": d.get("name"),
                    "nav_date": d.get("jzrq"),
                    "nav": d.get("dwjz"),
                    "est_nav": d.get("gsz"),
                    "est_chg_24h_pct": d.get("gszzl")
                }
    except Exception:
        return None
    return None

def fetch_funds(codes):
    out=[]
    for c in codes:
        # 先 fundgz（GitHub Actions 上更稳定），再 DoctorXiong
        it = fetch_fund_fundgz(c) or fetch_fund_doctorxiong(c)
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

def write_latest(cfg, fund_rows, coin_rows_by_vs):
    from datetime import datetime
    headers = pick_headers(cfg)
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    path = Path("data/agg_latest.csv")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as f:  # utf-8-sig 给Excel更友好
        w = csv.writer(f)
        w.writerow(headers)
        # 基金
        for r in fund_rows:
            w.writerow([
                r.get("type"), r.get("id"), r.get("name"),
                r.get("nav_date"), r.get("nav"),
                r.get("est_chg_24h_pct"), None, now
            ])
        # 加密币（逐个vs）
        for vs, arr in coin_rows_by_vs.items():
            for it in arr:
                w.writerow([
                    "crypto", it.get("id"), it.get("name"),
                    now, it.get("current_price"),
                    it.get("price_change_percentage_24h"),
                    vs, now
                ])

def append_history(cfg, fund_rows, coin_rows_by_vs):
    from datetime import datetime
    headers = pick_headers(cfg)
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    path = Path("data/history.csv")
    path.parent.mkdir(parents=True, exist_ok=True)
    file_exists = path.exists()
    with path.open("a", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        if not file_exists:
            w.writerow(headers)
        # 基金
        for r in fund_rows:
            w.writerow([
                r.get("type"), r.get("id"), r.get("name"),
                r.get("nav_date"), r.get("nav"),
                r.get("est_chg_24h_pct"), None, now
            ])
        # 加密币
        for vs, arr in coin_rows_by_vs.items():
            for it in arr:
                w.writerow([
                    "crypto", it.get("id"), it.get("name"),
                    now, it.get("current_price"),
                    it.get("price_change_percentage_24h"),
                    vs, now
                ])

def main():
    cfg = load_cfg()
    funds = fetch_funds(cfg.get("funds",[]))
    coin_rows_by_vs={}
    for vs in cfg.get("vs",["usd"]):
        coin_rows_by_vs[vs]=cg_markets(cfg.get("coins",[]), vs)
    write_latest(cfg, funds, coins_by_vs)
    append_history(cfg, funds, coins_by_vs)
    print("OK: agg_latest.csv & history.csv written/appended.")

if __name__=="__main__":
    main()



