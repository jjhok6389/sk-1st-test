"""
crawl_faq.py
============
K Car 옥션 FAQ 크롤러 → MySQL company_faq 적재.
"""

import os
import re
import sys
import time

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from crawler.faq_common import auto_tag, categorize, clean  # noqa: E402
from db_config import get_connection  # noqa: E402

TARGET_URL = "https://www.kcarauction.com/kcar/board/faq_list.do"
HEADLESS = True
KCAA_COMPANY = "K Car 옥션"
FAQ_TABS = ["전체", "참여", "회원", "출품", "정산", "클레임"]

CATEGORY_MAP = {
    "참여": "일반",
    "회원": "일반",
    "출품": "중고차",
    "정산": "중고차",
    "클레임": "중고차",
}

EV_KEYWORDS = ("전기차", "EV", "배터리", "충전", "친환경", "하이브리드")


def _configure_stdout() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass


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
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)

    driver = webdriver.Chrome(options=opts)
    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    return driver


def is_calendar_table(table) -> bool:
    rows = table.find_all("tr")
    if len(rows) != 1:
        return False
    cells = [clean(td.get_text(" ")) for td in rows[0].find_all(["td", "th"])]
    return cells == ["일", "월", "화", "수", "목", "금", "토"]


def parse_faq(html: str) -> list[tuple[str, str, str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    cats = set(CATEGORY_MAP.keys())
    parsed: list[tuple[str, str, str, str]] = []

    for table in soup.find_all("table"):
        if is_calendar_table(table):
            continue

        current_cat = None
        current_q = None

        for tr in table.find_all("tr"):
            cells = [clean(td.get_text(" ")) for td in tr.find_all(["td", "th"])]
            content = [cell for cell in cells if cell]
            if not content:
                continue

            if content[0] in cats:
                current_cat = content[0]
                candidates = [cell for cell in content[1:] if cell.upper() != "Q"]
                if candidates:
                    current_q = re.sub(r"^Q[\.\s:]*", "", max(candidates, key=len)).strip()
                continue

            if current_q is None:
                continue

            answer_cell = next((cell for cell in content if cell.startswith(("A", "A "))), None)
            if not answer_cell and len(content) >= 2 and content[0].upper() == "A":
                answer_cell = " ".join(content[1:])
            if not answer_cell:
                continue

            answer = clean(re.sub(r"^A[\.\s:]*", "", answer_cell))
            if len(answer) < 10:
                continue

            tags = auto_tag(current_q, answer)
            category = (
                "전기차"
                if any(k in f"{current_q}{answer}" for k in EV_KEYWORDS)
                else CATEGORY_MAP.get(current_cat, "일반")
            )
            parsed.append((category, current_q, answer, tags))
            current_q = None

    return parsed


def click_tab(driver: webdriver.Chrome, tab_name: str) -> bool:
    for by, value in (
        (By.LINK_TEXT, tab_name),
        (By.PARTIAL_LINK_TEXT, tab_name),
        (By.XPATH, f"//a[normalize-space(text())='{tab_name}']"),
        (By.XPATH, f"//button[normalize-space(text())='{tab_name}']"),
    ):
        elements = driver.find_elements(by, value)
        if elements:
            driver.execute_script("arguments[0].click();", elements[0])
            return True
    return False


def crawl() -> list[tuple[str, str, str, str]]:
    _configure_stdout()
    print("[START] K Car 경매 FAQ 크롤링")

    driver = None
    collected: dict[str, tuple[str, str, str, str]] = {}

    try:
        driver = build_driver(headless=HEADLESS)
        driver.get(TARGET_URL)
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table"))
        )
        time.sleep(2)

        for tab_name in FAQ_TABS:
            if not click_tab(driver, tab_name):
                print(f"  [WARN] 탭을 찾지 못함: {tab_name}")
                continue

            time.sleep(1.5)
            rows = parse_faq(driver.page_source)
            before = len(collected)
            for row in rows:
                collected[row[1]] = row
            added = len(collected) - before
            print(f"  [TAB] {tab_name}: {len(rows)}건 파싱, {added}건 신규")

        result = list(collected.values())
        print(f"[OK] FAQ {len(result)}건 수집 완료")
        return result

    except Exception as exc:
        print(f"[ERROR] 크롤링 실패: {type(exc).__name__}: {exc}")
        return list(collected.values())
    finally:
        if driver is not None:
            driver.quit()


def save_to_db(crawled_rows: list[tuple[str, str, str, str]]) -> None:
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS company_faq (
            faq_id        INT AUTO_INCREMENT PRIMARY KEY,
            company       VARCHAR(40),
            car_category  VARCHAR(40),
            question      TEXT,
            answer        TEXT,
            persona_tags  VARCHAR(40),
            INDEX idx_company (company)
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """
    )

    cur.execute("DELETE FROM company_faq WHERE company = %s", (KCAA_COMPANY,))

    final_rows = [
        (KCAA_COMPANY, category, question, answer, tags)
        for category, question, answer, tags in crawled_rows
    ]

    if final_rows:
        cur.executemany(
            "INSERT INTO company_faq (company, car_category, question, answer, persona_tags) "
            "VALUES (%s,%s,%s,%s,%s)",
            final_rows,
        )

    print(f"[SAVE] {KCAA_COMPANY} FAQ {len(final_rows)}건 저장")
    conn.commit()
    cur.close()
    conn.close()


if __name__ == "__main__":
    rows = crawl()
    save_to_db(rows)
    print("[DONE] Streamlit 앱을 새로고침하면 FAQ가 반영됩니다.")
