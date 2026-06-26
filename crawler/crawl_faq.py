"""
crawl_faq.py
============
K Car 옥션(자동차 경매 기업) FAQ 크롤러 (스키마 v2 대응).

전략:
  1) Selenium(Headless Chrome)으로 페이지를 렌더링 → 봇 차단 우회 + 동적 콘텐츠 처리
  2) BeautifulSoup으로 page_source를 정확히 파싱 → 가독성/유지보수성 확보
  3) FAQ 본문에서 키워드를 보고 Car-BTI 4축 태그(E/G/L/S/P/B/I/D)를 자동 부여 ★ v2
  4) (카테고리, 질문, 답변, persona_tags)로 정제하여 SQLite DB에 저장
  5) 실패 시에도 프로젝트가 중단되지 않도록 fallback 데이터 자동 주입

대상 사이트: https://www.kcarauction.com/kcar/board/faq_list.do
"""

import os
import re
import sqlite3
import time

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

# ───────────────────────────────────────────────
# 설정
# ───────────────────────────────────────────────
TARGET_URL = "https://www.kcarauction.com/kcar/board/faq_list.do"
DB_PATH = "db/car_bti.db"
HEADLESS = True   # 디버깅/시연 시 False 로 두면 실제 브라우저 창이 뜸

# 케이카 옥션의 카테고리 → 우리 시스템(전기차/중고차/일반) 매핑
CATEGORY_MAP = {
    "참여": "일반",
    "회원": "일반",
    "출품": "중고차",
    "정산": "중고차",
    "클레임": "중고차",
}

EV_KEYWORDS = ("전기차", "EV", "배터리", "충전", "친환경", "하이브리드")

# ★ v2.1: Car-BTI 4축 자동 태깅용 키워드 사전 (풍부화)
#   FAQ 본문에 다음 키워드가 등장하면 해당 자리수 태그를 부여
#   K Car 옥션 FAQ 에서 자주 등장하는 단어들을 적극 반영
AXIS_KEYWORDS = {
    "E": ["전기차", "EV", "배터리", "충전", "친환경", "하이브리드", "수소", "에코", "보조금", "충전소"],
    "G": ["엔진", "가솔린", "디젤", "내연기관", "LPG", "주유", "유류비"],
    "L": ["SUV", "캠핑", "화물", "버스", "대형", "레저", "다목적", "미니밴",
          "패밀리", "다인승", "출품", "차종", "승용차", "RV"],
    "S": ["세단", "소형", "경차", "도심", "주차", "준중형", "통근", "1인"],
    "P": ["프리미엄", "고급", "럭셔리", "최신", "옵션", "기능"],
    "B": ["가성비", "경매", "경제", "중고", "합리", "저렴", "낙찰", "할인", "유지비",
          "혜택", "정산", "수수료", "가상계좌", "시세", "희망가"],
    "I": ["수입", "외제", "BMW", "벤츠", "아우디", "테슬라", "볼보", "딜러"],
    "D": ["국산", "현대", "기아", "제네시스", "쌍용", "등록증", "서류", "위임장",
          "양도", "명의", "이전", "신청", "인감", "지방세"],
}

# 케이카 옥션 FAQ의 본질적 색채 (모든 키워드가 안 잡힐 때 사용)
DEFAULT_TAGS = ["B", "D"]   # 가성비 + 국산 (경매·중고 거래 특성)


# ───────────────────────────────────────────────
# Selenium 드라이버 빌더
# ───────────────────────────────────────────────
def build_driver(headless: bool = True) -> webdriver.Chrome:
    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--window-size=1280,900")
    opts.add_argument("--lang=ko-KR")
    opts.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    # 자동화 흔적 숨기기
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)

    driver = webdriver.Chrome(options=opts)
    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    return driver


# ───────────────────────────────────────────────
# 파싱 유틸
# ───────────────────────────────────────────────
def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def classify_category(default_cat: str, question: str, answer: str) -> str:
    body = f"{question} {answer}"
    if any(kw in body for kw in EV_KEYWORDS):
        return "전기차"
    return CATEGORY_MAP.get(default_cat, "일반")


def auto_tag(question: str, answer: str) -> str:
    """★ v2: 본문 키워드를 보고 Car-BTI 자리수 태그를 자동 부여."""
    body = f"{question} {answer}"
    matched = [axis for axis, kws in AXIS_KEYWORDS.items() if any(k in body for k in kws)]
    if not matched:
        matched = DEFAULT_TAGS
    return ",".join(matched)


def parse_faq(html: str) -> list[tuple[str, str, str, str]]:
    """
    K Car 옥션 FAQ 테이블 파싱 → (카테고리, 질문, 답변, persona_tags) 튜플 리스트.

    구조(2행 1쌍):
        [카테고리, "Q", 질문문장, ...]
        ["",       "A 답변 본문 ...",      ...]
    """
    soup = BeautifulSoup(html, "html.parser")
    cats = set(CATEGORY_MAP.keys())
    parsed: list[tuple[str, str, str, str]] = []

    for table in soup.find_all("table"):
        current_cat: str | None = None
        current_q: str | None = None

        for tr in table.find_all("tr"):
            cells = [clean(td.get_text(" ")) for td in tr.find_all(["td", "th"])]
            content = [c for c in cells if c]
            if not content:
                continue

            # ─ 질문 행: 첫 셀이 카테고리명 ─
            if content[0] in cats:
                current_cat = content[0]
                candidates = [c for c in content[1:] if c.upper() != "Q"]
                if candidates:
                    current_q = max(candidates, key=len)
                    current_q = re.sub(r"^Q[\.\s:]*", "", current_q).strip()
                continue

            # ─ 답변 행 ─
            if current_q is None:
                continue

            answer_cell = next(
                (c for c in content if c.startswith(("A", "A "))), None
            )
            if not answer_cell:
                if len(content) >= 2 and content[0].upper() == "A":
                    answer_cell = " ".join(content[1:])
            if not answer_cell:
                continue

            answer = clean(re.sub(r"^A[\.\s:]*", "", answer_cell))
            if len(answer) < 10:
                continue

            cat = classify_category(current_cat or "", current_q, answer)
            tags = auto_tag(current_q, answer)           # ★ v2 자동 태깅
            parsed.append((cat, current_q, answer, tags))
            print(f"   ✔ [{cat:^3} | {tags:<7}] Q. {current_q[:50]}")

            current_q = None

    return parsed


# ───────────────────────────────────────────────
# 크롤링 본체
# ───────────────────────────────────────────────
def crawl() -> list[tuple[str, str, str, str]]:
    print("🚀 K Car 옥션 FAQ 크롤러를 시작합니다")
    print(f"   ▸ 대상 URL : {TARGET_URL}")
    print(f"   ▸ 모드     : {'headless' if HEADLESS else 'visible browser'}")

    driver = None
    try:
        driver = build_driver(headless=HEADLESS)
        driver.get(TARGET_URL)

        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table"))
        )
        time.sleep(2)

        rows = parse_faq(driver.page_source)
        print(f"\n✅ 파싱 완료: {len(rows)}건")
        return rows

    except Exception as e:
        print(f"❌ 크롤링 중 오류: {type(e).__name__}: {e}")
        return []
    finally:
        if driver is not None:
            driver.quit()


# ───────────────────────────────────────────────
# DB 저장
# ───────────────────────────────────────────────
FALLBACK_DATA = [
    ("전기차",
     "전기차 중고 거래 시 배터리 보증은 어떻게 되나요?",
     "제조사별로 다르지만 보통 10년/16만km를 보증합니다. 반드시 공식 서비스센터 진단서를 확인하세요.",
     "E,B"),
    ("중고차",
     "침수차를 피하는 확실한 방법이 있나요?",
     "카히스토리 무료 조회, 안전벨트를 끝까지 당겨 흙먼지 확인, 퓨즈박스 내부의 진흙 흔적을 반드시 체크하세요.",
     "B,D"),
    ("일반",
     "차량 명의 이전 시 필요한 서류는 무엇인가요?",
     "양도인과 양수인의 신분증, 자동차 등록증 원본, 양수인 명의의 책임보험 가입 증명서가 필수입니다.",
     "B,D"),
]


def save_to_db(rows: list[tuple[str, str, str, str]]) -> None:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("DELETE FROM company_faq")
    cur.execute("DELETE FROM sqlite_sequence WHERE name='company_faq'")

    target = rows if rows else FALLBACK_DATA
    cur.executemany(
        "INSERT INTO company_faq (car_category, question, answer, persona_tags) VALUES (?,?,?,?)",
        target,
    )

    if rows:
        print(f"\n💾 DB 저장 완료: 크롤링 데이터 {len(rows)}건 ({DB_PATH})")
    else:
        print(f"\n⚠️  크롤링 결과 0건 → fallback {len(FALLBACK_DATA)}건 저장 ({DB_PATH})")

    conn.commit()
    conn.close()


# ───────────────────────────────────────────────
# 엔트리 포인트
# ───────────────────────────────────────────────
if __name__ == "__main__":
    rows = crawl()
    save_to_db(rows)
    print("\n🎉 작업 완료! Streamlit 앱을 재실행하면 새 FAQ + persona_tags 가 반영됩니다.")