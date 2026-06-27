"""FAQ 크롤러 공통 유틸."""

import re

from bs4 import BeautifulSoup

EV_KEYWORDS = ("전기차", "EV", "배터리", "충전", "친환경", "수소", "하이브리드")

AXIS_KEYWORDS = {
    "E": ["전기차", "EV", "배터리", "충전", "친환경", "수소", "하이브리드"],
    "G": ["엔진", "가솔린", "디젤", "내연기관", "LPG", "주유"],
    "L": ["SUV", "대형", "캠핑", "레저", "다목적", "패밀리", "GV80", "GV70"],
    "S": ["세단", "소형", "경차", "도심", "주차", "통근", "G70", "G80"],
    "M": ["남성", "스포츠", "주행감", "성능", "출퇴근"],
    "F": ["여성", "안전", "편의", "첫차", "가족"],
    "I": ["수입", "테슬라", "벤츠", "BMW", "포르쉐", "볼보", "폭스바겐", "미니", "아우디"],
    "D": ["국산", "현대", "기아", "제네시스", "쉐보레"],
}

BRAND_BASE_TAG = {
    "현대": "D",
    "기아": "D",
    "제네시스": "D",
    "쉐보레": "D",
    "BMW": "I",
    "벤츠": "I",
    "테슬라": "I",
    "볼보": "I",
    "아우디": "I",
    "미니": "I",
}


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def strip_html(html: str) -> str:
    if not html:
        return ""
    return clean(BeautifulSoup(html, "html.parser").get_text(" ", strip=True))


def auto_tag(question: str, answer: str, company: str = "") -> str:
    body = f"{question} {answer}"
    matched = {axis for axis, kws in AXIS_KEYWORDS.items() if any(k in body for k in kws)}
    base = BRAND_BASE_TAG.get(company, "")
    if base:
        matched.add(base)
    return ",".join(sorted(matched)) if matched else (base or "D")


def categorize(question: str, answer: str) -> str:
    body = f"{question}{answer}"
    if any(k in body for k in EV_KEYWORDS):
        return "전기차"
    if any(k in body for k in ("중고", "인증중고", "보증")):
        return "중고차"
    return "일반"
