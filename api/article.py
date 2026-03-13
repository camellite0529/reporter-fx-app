from __future__ import annotations

import math
import os
from datetime import datetime, timedelta
from typing import Any, Dict
from zoneinfo import ZoneInfo

import requests
import yfinance as yf
from flask import Flask, jsonify, request

app = Flask(__name__)

SEOUL_TZ = ZoneInfo("Asia/Seoul")
BOK_KEYSTAT_URL = "https://ecos.bok.or.kr/api/KeyStatisticList/{key}/json/kr/1/20"
REQUEST_TIMEOUT = 10
DISPLAY_DELAY_MINUTES = int(os.getenv("DISPLAY_DELAY_MINUTES", "20"))

ARTICLE_TYPE_LABELS = {
    "intraday": "장중 기사",
    "opening": "개장 기사",
    "weekly_close": "주간 종가 기사",
}


def safe_float(value: Any) -> float:
    if value is None:
        return float("nan")
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).replace(",", "").strip()
    if not text:
        return float("nan")
    try:
        return float(text)
    except ValueError:
        return float("nan")


def has_value(value: float) -> bool:
    return not math.isnan(value)


def format_number(value: float, digits: int = 2) -> str:
    if not has_value(value):
        return "[데이터 없음]"
    return f"{value:.{digits}f}"


def format_signed_abs(value: float, digits: int = 2) -> str:
    if not has_value(value):
        return "[데이터 없음]"
    return format_number(abs(value), digits)


def get_time_labels(now: datetime) -> Dict[str, str]:
    am_pm = "오전" if now.hour < 12 else "오후"
    session = "초반" if now.hour < 12 else "후반"
    hour_12 = now.hour % 12
    if hour_12 == 0:
        hour_12 = 12
    time_text = f"{am_pm} {hour_12}시{now.minute}분"
    return {
        "day_text": f"{now.day}일",
        "time_text": time_text,
        "session": session,
    }


def percent_band(percent: float) -> str:
    if not has_value(percent):
        return "[등락률 없음]"
    return f"{int(abs(percent))}%대"


def tone_label(percent: float) -> str:
    if not has_value(percent):
        return "[방향 없음]"
    if abs(percent) < 0.1:
        return "보합세"
    return "강세" if percent > 0 else "약세"


def change_words(value: float) -> Dict[str, str]:
    if not has_value(value):
        return {
            "up_down": "[방향 없음]",
            "rose_fell": "[방향 없음]",
            "opened": "[방향 없음]",
            "trend": "[방향 없음]",
        }
    if abs(value) < 1e-9:
        return {
            "up_down": "보합",
            "rose_fell": "보합",
            "opened": "보합인",
            "trend": "보합",
        }
    return {
        "up_down": "오른" if value > 0 else "내린",
        "rose_fell": "올랐다" if value > 0 else "내렸다",
        "opened": "상승한" if value > 0 else "하락한",
        "trend": "상승" if value > 0 else "하락",
    }


def get_manual_field(name: str, default: str) -> str:
    value = request.args.get(name, "").strip()
    return value if value else default


def get_manual_inputs() -> Dict[str, str]:
    return {
        "foreigner_amount": get_manual_field("foreigner_amount", "[외국인 금액]"),
        "foreigner_flow": get_manual_field("foreigner_flow", "sell"),
        "individual_amount": get_manual_field("individual_amount", "[개인 금액]"),
        "individual_flow": get_manual_field("individual_flow", "buy"),
        "institution_amount": get_manual_field("institution_amount", "[기관 금액]"),
        "institution_flow": get_manual_field("institution_flow", "sell"),
    }


def flow_text(flow: str, actor: str) -> str:
    normalized = flow.lower()
    if actor == "individual":
        if normalized == "sell":
            return "팔고"
        return "사들이고"
    if normalized == "buy":
        return "순매수"
    return "순매도"


def flow_text_past(flow: str, actor: str) -> str:
    normalized = flow.lower()
    if actor == "individual":
        if normalized == "sell":
            return "팔았다"
        return "사들였다"
    if normalized == "buy":
        return "순매수"
    return "순매도"


def institution_advantage_text(flow: str) -> str:
    return "매수" if flow.lower() == "buy" else "매도"


def get_article_type() -> str:
    article_type = request.args.get("article_type", "").strip().lower()
    if article_type not in ARTICLE_TYPE_LABELS:
        raise ValueError("기사 유형을 선택해 주세요.")
    return article_type


def fetch_bok_reference() -> Dict[str, Any]:
    api_key = os.getenv("BOK_API_KEY", "").strip()
    if not api_key:
        return {"enabled": False, "error": "BOK_API_KEY 환경변수가 없습니다."}

    url = BOK_KEYSTAT_URL.format(key=api_key)
    response = requests.get(url, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    payload = response.json()
    rows = payload.get("KeyStatisticList", {}).get("row", [])

    lookup = {}
    for row in rows:
        name = row.get("KEYSTAT_NAME", "")
        lookup[name] = {
            "value": safe_float(row.get("DATA_VALUE")),
            "date": row.get("CYCLE"),
            "unit": row.get("UNIT_NAME"),
        }

    return {
        "enabled": True,
        "usdkrw": lookup.get("원/달러 환율(종가)"),
        "jpy100krw": lookup.get("원/엔(100엔) 환율(매매기준율)"),
        "cnykrw": lookup.get("원/위안 환율(종가)"),
    }


def fetch_yf_quote(symbol: str) -> Dict[str, float]:
    ticker = yf.Ticker(symbol)
    daily = ticker.history(period="5d", interval="1d", auto_adjust=False, repair=False)
    intraday = ticker.history(period="1d", interval="1m", auto_adjust=False, repair=False, prepost=False)

    if daily.empty:
        raise ValueError(f"No daily data for {symbol}")

    daily = daily.dropna(how="all")
    intraday = intraday.dropna(how="all")

    current = safe_float(intraday["Close"].dropna().iloc[-1]) if not intraday.empty else safe_float(daily["Close"].dropna().iloc[-1])
    open_price = safe_float(daily["Open"].dropna().iloc[-1])

    close_series = daily["Close"].dropna()
    latest_close = safe_float(close_series.iloc[-1])

    if len(close_series) >= 2:
        prev_close = safe_float(close_series.iloc[-2])
    else:
        prev_close = latest_close

    last_change = latest_close - prev_close
    last_pct = ((latest_close - prev_close) / prev_close * 100) if prev_close else float("nan")

    return {
        "symbol": symbol,
        "current": current,
        "open": open_price,
        "prev_close": prev_close,
        "change": current - prev_close,
        "pct": ((current - prev_close) / prev_close * 100) if prev_close else float("nan"),
        "open_change": open_price - prev_close,
        "open_pct": ((open_price - prev_close) / prev_close * 100) if prev_close else float("nan"),
        "intraday_change": current - open_price,
        "last_close": latest_close,
        "last_change": last_change,
        "last_pct": last_pct,
    }


def collect_market_data() -> Dict[str, Any]:
    kospi = fetch_yf_quote("^KS11")
    kosdaq = fetch_yf_quote("^KQ11")
    usdkrw = fetch_yf_quote("USDKRW=X")
    jpykrw = fetch_yf_quote("JPYKRW=X")
    cnykrw = fetch_yf_quote("CNYKRW=X")

    jpy100 = {
        **jpykrw,
        "current": jpykrw["current"] * 100,
        "open": jpykrw["open"] * 100,
        "prev_close": jpykrw["prev_close"] * 100,
        "last_close": jpykrw["last_close"] * 100,
    }
    jpy100["change"] = jpy100["current"] - jpy100["prev_close"]
    jpy100["pct"] = ((jpy100["current"] - jpy100["prev_close"]) / jpy100["prev_close"] * 100) if jpy100["prev_close"] else float("nan")
    jpy100["open_change"] = jpy100["open"] - jpy100["prev_close"]
    jpy100["open_pct"] = ((jpy100["open"] - jpy100["prev_close"]) / jpy100["prev_close"] * 100) if jpy100["prev_close"] else float("nan")
    jpy100["intraday_change"] = jpy100["current"] - jpy100["open"]
    jpy100["last_change"] = jpy100["last_close"] - jpy100["prev_close"]
    jpy100["last_pct"] = ((jpy100["last_close"] - jpy100["prev_close"]) / jpy100["prev_close"] * 100) if jpy100["prev_close"] else float("nan")

    return {
        "kospi": kospi,
        "kosdaq": kosdaq,
        "usdkrw": usdkrw,
        "jpy100krw": jpy100,
        "cnykrw": cnykrw,
    }


def build_intraday_article(data: Dict[str, Any], manual: Dict[str, str]) -> str:
    now = data["now"]
    labels = get_time_labels(now)

    kospi = data["markets"]["kospi"]
    kosdaq = data["markets"]["kosdaq"]
    usdkrw = data["markets"]["usdkrw"]
    jpy100 = data["markets"]["jpy100krw"]
    cnykrw = data["markets"]["cnykrw"]

    kospi_words = change_words(kospi["change"])
    kospi_open_words = change_words(kospi["open_change"])
    kosdaq_words = change_words(kosdaq["change"])
    usd_words = change_words(usdkrw["change"])
    usd_open_words = change_words(usdkrw["open_change"])
    usd_intraday_words = change_words(usdkrw["intraday_change"])
    jpy_words = change_words(jpy100["change"])

    return f"""코스피지수가 장 {labels['session']} {percent_band(kospi['pct'])} {tone_label(kospi['pct'])}를 기록하고 있다.
{labels['day_text']} {labels['time_text']} 현재 코스피는 전일 대비 {format_signed_abs(kospi['change'], 2)}포인트({format_signed_abs(kospi['pct'], 2)}%) {kospi_words['up_down']} {format_number(kospi['current'], 2)}를 기록 중이다.
이날 코스피는 전 거래일보다 {format_signed_abs(kospi['open_change'], 2)}포인트({format_signed_abs(kospi['open_pct'], 2)}%) {kospi_open_words['opened']} {format_number(kospi['open'], 2)}에 개장했다.
유가증권시장에서는 외국인이 {manual['foreigner_amount']}억원을 {flow_text(manual['foreigner_flow'], 'foreigner')} 중이다. 개인은 {manual['individual_amount']}억원어치를 {flow_text(manual['individual_flow'], 'individual')} 있다. 기관은 {manual['institution_amount']}억원을 {flow_text(manual['institution_flow'], 'institution')} 중이다.
같은 시각 코스닥지수는 전 거래일보다 {format_signed_abs(kosdaq['change'], 2)}포인트({format_signed_abs(kosdaq['pct'], 2)}%) {kosdaq_words['up_down']} {format_number(kosdaq['current'], 2)}를 기록 중이다.
서울외환시장에서 미국 달러화 대비 원화 환율은 전 거래일 종가보다 {format_signed_abs(usdkrw['change'], 1)}원 {usd_words['up_down']} {format_number(usdkrw['current'], 1)}원을 나타내고 있다. 환율은 전날보다 {format_signed_abs(usdkrw['open_change'], 1)}원 {usd_open_words['up_down']} {format_number(usdkrw['open'], 1)}원으로 출발해 {usd_intraday_words['trend']}했다.
원·엔 재정환율은 100엔당 {format_number(jpy100['current'], 2)}원으로 전날 종가보다 {format_signed_abs(jpy100['change'], 2)}원 {jpy_words['rose_fell']}.
같은 시각 원·위안 환율은 {format_number(cnykrw['current'], 2)}원이다."""


def build_opening_article(data: Dict[str, Any], manual: Dict[str, str]) -> str:
    usdkrw = data["markets"]["usdkrw"]
    usd_open_words = change_words(usdkrw["open_change"])

    return f"""미국 달러 대비 원화 환율은 이날 {format_number(usdkrw['open'], 1)}원에 개장했다. 전 거래일보다 {format_signed_abs(usdkrw['open_change'], 1)}원 {usd_open_words['rose_fell']}."""


def build_weekly_close_article(data: Dict[str, Any], manual: Dict[str, str]) -> str:
    now = data["now"]
    labels = get_time_labels(now)

    kospi = data["markets"]["kospi"]
    kosdaq = data["markets"]["kosdaq"]
    usdkrw = data["markets"]["usdkrw"]

    kospi_close_words = change_words(kospi["last_change"])
    kosdaq_close_words = change_words(kosdaq["last_change"])
    usd_close_words = change_words(usdkrw["last_change"])

    return f"""코스피지수는 {labels['day_text']} 전 거래일 대비 {format_signed_abs(kospi['last_change'], 2)}포인트({format_number(kospi['last_pct'], 2)}%) {kospi_close_words['opened']} {format_number(kospi['last_close'], 2)}로 마감했다.
외국인이 {manual['foreigner_amount']}억원을 {flow_text_past(manual['foreigner_flow'], 'foreigner')}했다. 개인은 {manual['individual_amount']}억원어치를 {flow_text_past(manual['individual_flow'], 'individual')}다. 기관은 {manual['institution_amount']}억원 {institution_advantage_text(manual['institution_flow'])} 우위를 보였다.
코스닥은 전 거래일 대비 {format_signed_abs(kosdaq['last_change'], 2)}포인트({format_number(kosdaq['last_pct'], 2)}%) {kosdaq_close_words['opened']} {format_number(kosdaq['last_close'], 2)}으로 마감했다.
달러·원 환율은 오후 3시30분 주간 종가 기준 전 거래일보다 {format_signed_abs(usdkrw['last_change'], 1)}원 {usd_close_words['up_down']} {format_number(usdkrw['last_close'], 1)}원으로 마감했다."""


def build_article(article_type: str, data: Dict[str, Any], manual: Dict[str, str]) -> str:
    if article_type == "intraday":
        return build_intraday_article(data, manual)
    if article_type == "opening":
        return build_opening_article(data, manual)
    if article_type == "weekly_close":
        return build_weekly_close_article(data, manual)
    raise ValueError("지원하지 않는 기사 유형입니다.")


@app.route("/api/article", methods=["GET"])
def article() -> Any:
    now = datetime.now(SEOUL_TZ)
    display_now = now - timedelta(minutes=DISPLAY_DELAY_MINUTES)
    manual = get_manual_inputs()

    try:
        article_type = get_article_type()
    except ValueError as exc:
        return (
            jsonify(
                {
                    "ok": False,
                    "generated_at": now.isoformat(),
                    "displayed_at": display_now.isoformat(),
                    "error": str(exc),
                }
            ),
            400,
        )

    try:
        markets = collect_market_data()
        bok_reference = fetch_bok_reference()

        article_text = build_article(
            article_type,
            {"now": display_now, "markets": markets},
            manual,
        )

        payload = {
            "ok": True,
            "article_type": article_type,
            "article_type_label": ARTICLE_TYPE_LABELS[article_type],
            "generated_at": now.isoformat(),
            "displayed_at": display_now.isoformat(),
            "display_delay_minutes": DISPLAY_DELAY_MINUTES,
            "data_notes": [
                "장중 현재값·개장가·전일 종가는 yfinance(Yahoo Finance 기반)에서 계산합니다.",
                f"표시 시각은 실제 생성 시각보다 {DISPLAY_DELAY_MINUTES}분 앞당겨 표기합니다.",
                "한국은행 ECOS KeyStatisticList는 공식 환율 참고값으로 함께 조회합니다.",
                "외국인/개인/기관 수급은 현재 수동 입력 칸을 통해 넣도록 했습니다.",
            ],
            "article": article_text,
            "markets": markets,
            "bok_reference": bok_reference,
            "manual": manual,
        }
        return jsonify(payload)
    except Exception as exc:
        return (
            jsonify(
                {
                    "ok": False,
                    "generated_at": now.isoformat(),
                    "displayed_at": display_now.isoformat(),
                    "error": str(exc),
                }
            ),
            500,
        )


@app.route("/")
def root() -> Any:
    return jsonify({"ok": True, "message": "Use /api/article"})


if __name__ == "__main__":
    app.run(debug=True)
    
