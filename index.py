"""
api/index.py – Vercel Serverless Function (Flask)
주식 대시보드 백엔드 – KIS API + yfinance
환경변수(Vercel Dashboard)에서 API 키를 읽습니다.
"""

import os
import time
import datetime
import feedparser
import requests
from flask import Flask, jsonify, request
from flask_cors import CORS
from concurrent.futures import ThreadPoolExecutor
# yfinance는 무거운 패키지라 함수 내부에서 lazy import 사용

app = Flask(__name__)
CORS(app)

# =============================================================
#  설정 – Vercel 환경변수에서 읽기
#  (Vercel Dashboard → Settings → Environment Variables)
# =============================================================
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

# =============================================================
#  토큰 관리 (Warm Start 재사용)
# =============================================================
_token_cache = {"access_token": None, "expires_at": 0}

def get_access_token() -> str:
    now = time.time()
    if _token_cache["access_token"] and now < _token_cache["expires_at"] - 300:
        return _token_cache["access_token"]
    url  = f"{BASE_URL}/oauth2/tokenP"
    body = {
        "grant_type": "client_credentials",
        "appkey":     APP_KEY,
        "appsecret":  APP_SECRET,
    }
    resp = requests.post(url, json=body, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    _token_cache["access_token"] = data["access_token"]
    _token_cache["expires_at"]   = now + int(data.get("expires_in", 86400))
    return _token_cache["access_token"]

def kis_headers(tr_id_val: str) -> dict:
    return {
        "authorization": f"Bearer {get_access_token()}",
        "appkey":        APP_KEY,
        "appsecret":     APP_SECRET,
        "tr_id":         tr_id_val,
        "custtype":      "P",
        "content-type":  "application/json; charset=utf-8",
    }

def tr_id(real_id: str, paper_id: str) -> str:
    return real_id if TRADE_MODE == "real" else paper_id

# =============================================================
#  API 1) 토큰 상태
# =============================================================
@app.route("/api/token")
def api_token_status():
    try:
        token     = get_access_token()
        remaining = int(_token_cache["expires_at"] - time.time())
        return jsonify({
            "ok": True,
            "mode": TRADE_MODE,
            "token_preview": token[:12] + "...",
            "expires_in_sec": remaining,
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# =============================================================
#  API 2) 현재가 (KIS)
# =============================================================
@app.route("/api/price")
def api_price():
    ticker = request.args.get("ticker", "005930")
    try:
        resp = requests.get(
            f"{BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-price",
            headers=kis_headers("FHKST01010100"),
            params={"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": ticker},
            timeout=10,
        )
        resp.raise_for_status()
        o = resp.json().get("output", {})
        return jsonify({
            "ok":         True,
            "ticker":     ticker,
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

# =============================================================
#  API 3) OHLCV 차트 (yfinance)
# =============================================================
PERIOD_MAP = {
    "1D":  5,  "3D": 10, "1W": 15,
    "1M": 30, "3M": 90, "6M": 180, "1Y": 365,
}

@app.route("/api/chart")
def api_chart():
    import yfinance as yf  # lazy import
    ticker = request.args.get("ticker", "005930")
    period = request.args.get("period", "1W")
    days   = PERIOD_MAP.get(period, 15)
    try:
        end_dt   = datetime.date.today()
        start_dt = end_dt - datetime.timedelta(days=days + 45)

        yf_ticker = ticker + ".KS"
        df = yf.download(yf_ticker,
                         start=start_dt.strftime("%Y-%m-%d"),
                         end=end_dt.strftime("%Y-%m-%d"),
                         progress=False, auto_adjust=True)
        if df.empty:
            yf_ticker = ticker + ".KQ"
            df = yf.download(yf_ticker,
                             start=start_dt.strftime("%Y-%m-%d"),
                             end=end_dt.strftime("%Y-%m-%d"),
                             progress=False, auto_adjust=True)
        if df.empty:
            return jsonify({"ok": False, "error": "데이터 없음"}), 404

        df = df.tail(days)
        if hasattr(df.columns, "levels"):
            df.columns = df.columns.get_level_values(0)

        closes = [round(float(v), 0) for v in df["Close"].tolist()]

        def ma(n):
            res = []
            for i in range(len(closes)):
                if i < n - 1: res.append(None)
                else: res.append(round(sum(closes[i-n+1:i+1]) / n, 0))
            return res

        return jsonify({
            "ok":     True,
            "labels": [d.strftime("%m/%d") for d in df.index],
            "open":   [round(float(v), 0) for v in df["Open"].tolist()],
            "high":   [round(float(v), 0) for v in df["High"].tolist()],
            "low":    [round(float(v), 0) for v in df["Low"].tolist()],
            "close":  closes,
            "volume": [int(v) for v in df["Volume"].tolist()],
            "ma5":    ma(5),
            "ma20":   ma(20),
            "ma60":   ma(60),
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# =============================================================
#  API 4) 포트폴리오 (KIS)
# =============================================================
@app.route("/api/portfolio")
def api_portfolio():
    try:
        resp = requests.get(
            f"{BASE_URL}/uapi/domestic-stock/v1/trading/inquire-balance",
            headers=kis_headers(tr_id("TTTC8434R", "VTTC8434R")),
            params={
                "CANO": ACCOUNT_NO, "ACNT_PRDT_CD": ACCOUNT_CODE,
                "AFHR_FLPR_YN": "N", "OFL_YN": "N", "INQR_DVSN": "02",
                "UNPR_DVSN": "01", "FUND_STTL_ICLD_YN": "N",
                "FNCG_AMT_AUTO_RDPT_YN": "N", "PRCS_DVSN": "00",
                "CTX_AREA_FK100": "", "CTX_AREA_NK100": "",
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

        holdings = []
        for h in data.get("output1", []):
            qty = int(h.get("hldg_qty", 0))
            if qty == 0: continue
            buy_price = float(h.get("pchs_avg_pric", 0))
            cur_price = float(h.get("prpr", 0))
            eval_amt  = float(h.get("evlu_amt", 0))
            buy_amt   = float(h.get("pchs_amt", 0))
            pnl_pct   = float(h.get("evlu_pfls_rt", 0))
            holdings.append({
                "ticker":    h.get("pdno", ""),
                "name":      h.get("prdt_name", ""),
                "qty":       qty,
                "buy_price": round(buy_price),
                "cur_price": round(cur_price),
                "buy_amt":   round(buy_amt),
                "eval_amt":  round(eval_amt),
                "pnl_amt":   round(eval_amt - buy_amt),
                "pnl_pct":   round(pnl_pct, 2),
            })

        summary    = data.get("output2", [{}])[0]
        total_buy  = float(summary.get("pchs_amt_smtl_amt", 0))
        total_eval = float(summary.get("tot_evlu_amt", 0))
        total_pnl  = total_eval - total_buy
        total_pct  = (total_pnl / total_buy * 100) if total_buy > 0 else 0
        cash       = float(summary.get("dnca_tot_amt", 0))

        return jsonify({
            "ok":         True,
            "holdings":   holdings,
            "total_buy":  round(total_buy),
            "total_eval": round(total_eval),
            "total_pnl":  round(total_pnl),
            "total_pct":  round(total_pct, 2),
            "cash":       round(cash),
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# =============================================================
#  API 5) 관심종목 일괄 현재가 – 병렬 조회 (Vercel 타임아웃 대응)
# =============================================================
@app.route("/api/watchlist")
def api_watchlist():
    def fetch_one(item):
        try:
            resp = requests.get(
                f"{BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-price",
                headers=kis_headers("FHKST01010100"),
                params={"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": item["code"]},
                timeout=8,
            )
            o = resp.json().get("output", {})
            return {
                "code":       item["code"],
                "name":       item["name"],
                "price":      int(o.get("stck_prpr", 0)),
                "change_pct": float(o.get("prdy_ctrt", 0)),
                "sign":       o.get("prdy_vrss_sign", "3"),
            }
        except Exception as e:
            return {
                "code": item["code"], "name": item["name"],
                "price": 0, "change_pct": 0, "sign": "3",
                "error": str(e),
            }

    # 최대 8개 스레드로 병렬 조회 → 35종목을 ~3초 내 처리
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(fetch_one, WATCHLIST))

    return jsonify({"ok": True, "watchlist": results})

# =============================================================
#  API 6) 시장 지수 (yfinance)
# =============================================================
@app.route("/api/market")
def api_market():
    import yfinance as yf  # lazy import
    try:
        def get_index(symbol):
            df = yf.download(symbol, period="5d", progress=False, auto_adjust=True)
            if df.empty: return {"value": 0, "change_pct": 0}
            if hasattr(df.columns, "levels"):
                df.columns = df.columns.get_level_values(0)
            last = float(df["Close"].iloc[-1])
            prev = float(df["Close"].iloc[-2]) if len(df) >= 2 else last
            chg  = round((last - prev) / prev * 100, 2) if prev else 0
            return {"value": round(last, 2), "change_pct": chg}

        return jsonify({
            "ok":     True,
            "kospi":  get_index("^KS11"),
            "kosdaq": get_index("^KQ11"),
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# =============================================================
#  API 7) 뉴스 RSS
# =============================================================
@app.route("/api/news")
def api_news():
    news_list   = []
    count       = int(request.args.get("count", 5))
    name        = request.args.get("name", "").strip()
    fetch_count = count * 8 if name else count

    for source_name, feed_url in NEWS_FEEDS.items():
        try:
            feed    = feedparser.parse(feed_url)
            entries = feed.entries[:fetch_count]
            for e in entries:
                title = e.get("title", "")
                if name and name not in title:
                    continue
                pub_raw = getattr(e, "published", "") or getattr(e, "updated", "")
                try:
                    from dateutil import parser as dp
                    pub_str = _relative_time(dp.parse(pub_raw))
                except Exception:
                    pub_str = pub_raw[:16] if pub_raw else ""
                news_list.append({
                    "source":  source_name,
                    "title":   title,
                    "link":    e.get("link", ""),
                    "summary": e.get("summary", "")[:120],
                    "pub":     pub_str,
                    "tag":     _classify_news(title),
                })
        except Exception as ex:
            print(f"[뉴스] {source_name} RSS 오류: {ex}")

    return jsonify({"ok": True, "news": news_list})

def _relative_time(dt: datetime.datetime) -> str:
    try:
        now   = datetime.datetime.now(datetime.timezone.utc)
        delta = now - dt.astimezone(datetime.timezone.utc)
        secs  = int(delta.total_seconds())
        if secs < 60:      return f"{secs}초 전"
        elif secs < 3600:  return f"{secs//60}분 전"
        elif secs < 86400: return f"{secs//3600}시간 전"
        else:              return f"{secs//86400}일 전"
    except Exception:
        return ""

def _classify_news(title: str) -> str:
    pos_kw = ["급등","신고가","호재","계약","수주","상승","매수","상향","돌파","흑자","최대","성장","강세"]
    neg_kw = ["급락","하락","매도","악재","위기","손실","우려","하향","부진","적자","침체","약세","리스크"]
    for kw in pos_kw:
        if kw in title: return "pos"
    for kw in neg_kw:
        if kw in title: return "neg"
    return "neu"

# Vercel은 이 모듈의 'app' 변수를 WSGI 앱으로 사용합니다
# (로컬 테스트: python api/index.py)
if __name__ == "__main__":
    app.run(debug=True, port=5000)
