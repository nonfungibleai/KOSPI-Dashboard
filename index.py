import os
import time
import datetime
from flask import Flask, jsonify, request
from flask_cors import CORS
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)
CORS(app)

# ── 환경변수 ──────────────────────────────────────────────────
APP_KEY      = os.environ.get("KIS_APP_KEY", "")
APP_SECRET   = os.environ.get("KIS_APP_SECRET", "")
ACCOUNT_NO   = os.environ.get("KIS_ACCOUNT_NO", "")
ACCOUNT_CODE = os.environ.get("KIS_ACCOUNT_CODE", "01")
TRADE_MODE   = os.environ.get("KIS_TRADE_MODE", "real")
BASE_URL     = "https://openapi.koreainvestment.com:9443"

NEWS_FEEDS = {
    "연합뉴스 경제": "https://www.yna.co.kr/rss/economy.xml",
    "머니투데이":    "https://rss.mt.co.kr/rss/sec.xml",
    "매일경제 증권": "https://www.mk.co.kr/rss/40300001/",
    "한국경제":      "https://www.hankyung.com/feed/economy",
    "이데일리":      "https://rss.edaily.co.kr/edaily/rss/finance.xml",
}

WATCHLIST = [
    {"code": "005930", "name": "삼성전자"},
    {"code": "000660", "name": "SK하이닉스"},
    {"code": "005380", "name": "현대자동차"},
    {"code": "012450", "name": "한화에어로스페이스"},
    {"code": "005490", "name": "POSCO홀딩스"},
    {"code": "373220", "name": "LG에너지솔루션"},
    {"code": "068270", "name": "셀트리온"},
    {"code": "006400", "name": "삼성SDI"},
    {"code": "028260", "name": "삼성물산"},
    {"code": "105560", "name": "KB금융지주"},
    {"code": "066570", "name": "LG전자"},
    {"code": "034020", "name": "두산에너빌리티"},
    {"code": "000270", "name": "기아"},
    {"code": "277810", "name": "레인보우로보틱스"},
    {"code": "329180", "name": "HD현대중공업"},
    {"code": "010140", "name": "삼성중공업"},
    {"code": "042660", "name": "한화오션"},
    {"code": "096770", "name": "SK이노베이션"},
    {"code": "196170", "name": "알테오젠"},
    {"code": "010120", "name": "LS ELECTRIC"},
    {"code": "267260", "name": "HD현대일렉트릭"},
    {"code": "051910", "name": "LG화학"},
    {"code": "087010", "name": "펩트론"},
    {"code": "214450", "name": "파마리서치"},
    {"code": "214150", "name": "클래시스"},
    {"code": "030530", "name": "원익IPS"},
    {"code": "095340", "name": "ISC"},
    {"code": "058470", "name": "리노공업"},
    {"code": "145020", "name": "휴젤"},
    {"code": "263750", "name": "펄어비스"},
    {"code": "278470", "name": "에이피알"},
    {"code": "000720", "name": "현대건설"},
    {"code": "259960", "name": "크래프톤"},
    {"code": "035420", "name": "NAVER"},
    {"code": "035720", "name": "카카오"},
]

# ── 토큰 캐시 ────────────────────────────────────────────────
_token_cache = {"access_token": None, "expires_at": 0}

def get_access_token():
    import requests as req
    now = time.time()
    if _token_cache["access_token"] and now < _token_cache["expires_at"] - 300:
        return _token_cache["access_token"]
    resp = req.post(
        f"{BASE_URL}/oauth2/tokenP",
        json={"grant_type": "client_credentials", "appkey": APP_KEY, "appsecret": APP_SECRET},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    _token_cache["access_token"] = data["access_token"]
    _token_cache["expires_at"]   = now + int(data.get("expires_in", 86400))
    return _token_cache["access_token"]

def kis_headers(tr_id_val):
    return {
        "authorization": f"Bearer {get_access_token()}",
        "appkey":        APP_KEY,
        "appsecret":     APP_SECRET,
        "tr_id":         tr_id_val,
        "custtype":      "P",
        "content-type":  "application/json; charset=utf-8",
    }

def tr_id(real_id, paper_id):
    return real_id if TRADE_MODE == "real" else paper_id

# ── API 1) 토큰 확인 ─────────────────────────────────────────
@app.route("/api/token")
def api_token():
    try:
        token     = get_access_token()
        remaining = int(_token_cache["expires_at"] - time.time())
        return jsonify({"ok": True, "mode": TRADE_MODE,
                        "token_preview": token[:12] + "...",
                        "expires_in_sec": remaining})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# ── API 2) 현재가 ─────────────────────────────────────────────
@app.route("/api/price")
def api_price():
    import requests as req
    ticker = request.args.get("ticker", "005930")
    try:
        resp = req.get(
            f"{BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-price",
            headers=kis_headers("FHKST01010100"),
            params={"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": ticker},
            timeout=10,
        )
        o = resp.json().get("output", {})
        return jsonify({
            "ok": True, "ticker": ticker,
            "price":      int(o.get("stck_prpr", 0)),
            "change":     int(o.get("prdy_vrss", 0)),
            "change_pct": float(o.get("prdy_ctrt", 0)),
            "open":       int(o.get("stck_oprc", 0)),
            "high":       int(o.get("stck_hgpr", 0)),
            "low":        int(o.get("stck_lwpr", 0)),
            "volume":     int(o.get("acml_vol", 0)),
            "market_cap": o.get("hts_avls", ""),
            "per":        o.get("per", ""),
            "pbr":        o.get("pbr", ""),
            "w52_high":   int(o.get("w52_hgpr", 0)),
            "w52_low":    int(o.get("w52_lwpr", 0)),
            "sign":       o.get("prdy_vrss_sign", "3"),
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# ── API 3) 차트 OHLCV ────────────────────────────────────────
PERIOD_MAP = {"1D":5,"3D":10,"1W":15,"1M":30,"3M":90,"6M":180,"1Y":365}

@app.route("/api/chart")
def api_chart():
    import yfinance as yf
    ticker = request.args.get("ticker", "005930")
    period = request.args.get("period", "1W")
    days   = PERIOD_MAP.get(period, 15)
    try:
        end_dt   = datetime.date.today()
        start_dt = end_dt - datetime.timedelta(days=days + 45)
        fmt      = "%Y-%m-%d"

        df = yf.download(ticker + ".KS", start=start_dt.strftime(fmt),
                         end=end_dt.strftime(fmt), progress=False, auto_adjust=True)
        if df.empty:
            df = yf.download(ticker + ".KQ", start=start_dt.strftime(fmt),
                             end=end_dt.strftime(fmt), progress=False, auto_adjust=True)
        if df.empty:
            return jsonify({"ok": False, "error": "데이터 없음"}), 404

        df = df.tail(days)
        if hasattr(df.columns, "levels"):
            df.columns = df.columns.get_level_values(0)

        closes = [round(float(v), 0) for v in df["Close"].tolist()]

        def ma(n):
            r = []
            for i in range(len(closes)):
                r.append(None if i < n-1 else round(sum(closes[i-n+1:i+1])/n, 0))
            return r

        return jsonify({
            "ok": True,
            "labels": [d.strftime("%m/%d") for d in df.index],
            "open":   [round(float(v), 0) for v in df["Open"].tolist()],
            "high":   [round(float(v), 0) for v in df["High"].tolist()],
            "low":    [round(float(v), 0) for v in df["Low"].tolist()],
            "close":  closes,
            "volume": [int(v) for v in df["Volume"].tolist()],
            "ma5": ma(5), "ma20": ma(20), "ma60": ma(60),
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# ── API 4) 포트폴리오 ────────────────────────────────────────
@app.route("/api/portfolio")
def api_portfolio():
    import requests as req
    try:
        resp = req.get(
            f"{BASE_URL}/uapi/domestic-stock/v1/trading/inquire-balance",
            headers=kis_headers(tr_id("TTTC8434R", "VTTC8434R")),
            params={
                "CANO": ACCOUNT_NO, "ACNT_PRDT_CD": ACCOUNT_CODE,
                "AFHR_FLPR_YN":"N","OFL_YN":"N","INQR_DVSN":"02",
                "UNPR_DVSN":"01","FUND_STTL_ICLD_YN":"N",
                "FNCG_AMT_AUTO_RDPT_YN":"N","PRCS_DVSN":"00",
                "CTX_AREA_FK100":"","CTX_AREA_NK100":"",
            },
            timeout=10,
        )
        data = resp.json()
        holdings = []
        for h in data.get("output1", []):
            qty = int(h.get("hldg_qty", 0))
            if qty == 0: continue
            eval_amt = float(h.get("evlu_amt", 0))
            buy_amt  = float(h.get("pchs_amt", 0))
            holdings.append({
                "ticker":    h.get("pdno",""),
                "name":      h.get("prdt_name",""),
                "qty":       qty,
                "buy_price": round(float(h.get("pchs_avg_pric",0))),
                "cur_price": round(float(h.get("prpr",0))),
                "buy_amt":   round(buy_amt),
                "eval_amt":  round(eval_amt),
                "pnl_amt":   round(eval_amt - buy_amt),
                "pnl_pct":   round(float(h.get("evlu_pfls_rt",0)), 2),
            })
        s         = data.get("output2",[{}])[0]
        total_buy = float(s.get("pchs_amt_smtl_amt",0))
        total_eval= float(s.get("tot_evlu_amt",0))
        total_pnl = total_eval - total_buy
        return jsonify({
            "ok": True, "holdings": holdings,
            "total_buy":  round(total_buy),
            "total_eval": round(total_eval),
            "total_pnl":  round(total_pnl),
            "total_pct":  round((total_pnl/total_buy*100) if total_buy else 0, 2),
            "cash":       round(float(s.get("dnca_tot_amt",0))),
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# ── API 5) 관심종목 (병렬 조회) ──────────────────────────────
@app.route("/api/watchlist")
def api_watchlist():
    import requests as req

    def fetch_one(item):
        try:
            resp = req.get(
                f"{BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-price",
                headers=kis_headers("FHKST01010100"),
                params={"FID_COND_MRKT_DIV_CODE":"J","FID_INPUT_ISCD":item["code"]},
                timeout=8,
            )
            o = resp.json().get("output", {})
            return {"code":item["code"],"name":item["name"],
                    "price":int(o.get("stck_prpr",0)),
                    "change_pct":float(o.get("prdy_ctrt",0)),
                    "sign":o.get("prdy_vrss_sign","3")}
        except Exception as e:
            return {"code":item["code"],"name":item["name"],
                    "price":0,"change_pct":0,"sign":"3","error":str(e)}

    with ThreadPoolExecutor(max_workers=8) as ex:
        results = list(ex.map(fetch_one, WATCHLIST))
    return jsonify({"ok": True, "watchlist": results})

# ── API 6) 시장 지수 ─────────────────────────────────────────
@app.route("/api/market")
def api_market():
    import yfinance as yf
    try:
        def get_index(symbol):
            df = yf.download(symbol, period="5d", progress=False, auto_adjust=True)
            if df.empty: return {"value":0,"change_pct":0}
            if hasattr(df.columns,"levels"):
                df.columns = df.columns.get_level_values(0)
            last = float(df["Close"].iloc[-1])
            prev = float(df["Close"].iloc[-2]) if len(df)>=2 else last
            return {"value":round(last,2), "change_pct":round((last-prev)/prev*100,2) if prev else 0}
        return jsonify({"ok":True,"kospi":get_index("^KS11"),"kosdaq":get_index("^KQ11")})
    except Exception as e:
        return jsonify({"ok":False,"error":str(e)}), 500

# ── API 7) 뉴스 RSS ──────────────────────────────────────────
@app.route("/api/news")
def api_news():
    import feedparser
    from dateutil import parser as dp
    count  = int(request.args.get("count", 5))
    name   = request.args.get("name", "").strip()
    fetch_n= count * 8 if name else count
    result = []

    def classify(title):
        for kw in ["급등","신고가","호재","계약","수주","상승","매수","상향","돌파","흑자","성장"]:
            if kw in title: return "pos"
        for kw in ["급락","하락","매도","악재","위기","손실","우려","하향","부진","적자","침체"]:
            if kw in title: return "neg"
        return "neu"

    def rel_time(pub_raw):
        try:
            delta = datetime.datetime.now(datetime.timezone.utc) - \
                    dp.parse(pub_raw).astimezone(datetime.timezone.utc)
            s = int(delta.total_seconds())
            if s < 60:      return f"{s}초 전"
            elif s < 3600:  return f"{s//60}분 전"
            elif s < 86400: return f"{s//3600}시간 전"
            else:           return f"{s//86400}일 전"
        except: return ""

    for src, url in NEWS_FEEDS.items():
        try:
            for e in feedparser.parse(url).entries[:fetch_n]:
                title = e.get("title","")
                if name and name not in title: continue
                pub = rel_time(getattr(e,"published","") or getattr(e,"updated",""))
                result.append({"source":src,"title":title,
                               "link":e.get("link",""),
                               "summary":e.get("summary","")[:120],
                               "pub":pub,"tag":classify(title)})
        except: pass
    return jsonify({"ok":True,"news":result})


# ── Vercel 경로 호환: /api/ 접두사 없는 버전 ─────────────────
# Vercel이 /api/ 접두사를 제거하고 Flask에 전달하는 경우 대비
app.add_url_rule("/token",     view_func=api_token)
app.add_url_rule("/price",     view_func=api_price)
app.add_url_rule("/chart",     view_func=api_chart)
app.add_url_rule("/portfolio", view_func=api_portfolio)
app.add_url_rule("/watchlist", view_func=api_watchlist)
app.add_url_rule("/market",    view_func=api_market)
app.add_url_rule("/news",      view_func=api_news)

if __name__ == "__main__":
    app.run(debug=True, port=5000)
