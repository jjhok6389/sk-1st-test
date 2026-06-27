"""
crawl_brand_faq.py
==================
추천 차량 브랜드의 공식 FAQ를 크롤링해 MySQL company_faq 에 적재한다.

크롤링 소스
-----------
- 제네시스 : 공식 FAQ HTML (requests)
- 현대     : 고객센터 FAQ REST API
- 기아     : FAQ 검색 API (searchTag=kwp:kr/faq)
- BMW/미니 : BMW Group Salesforce FAQ 포털 (Selenium)
- 벤츠·테슬라·볼보·아우디·쉐보레 : 공식 사이트 크롤링 시도 → 실패 시 faq_fallback.py 시드
"""

import os
import sys
import time

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from crawler.faq_common import auto_tag, categorize, clean, strip_html  # noqa: E402
from crawler.faq_fallback import FALLBACK_BRANDS, get_fallback_rows  # noqa: E402
from db_config import get_connection  # noqa: E402

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9",
}

HYUNDAI_LIST_URL = (
    "https://www.hyundai.com/kr/ko/gw/customer-support/v1/customer-support/faq/list"
)
KIA_FAQ_URL = "https://www.kia.com/kr/services/ko/faq.search?searchTag=kwp:kr/faq"
GENESIS_FAQ_URL = "https://www.genesis.com/kr/ko/support/faq.html"

HEADLESS = True


def _configure_stdout() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass


def _row(company: str, question: str, answer: str) -> tuple | None:
    q, a = clean(question), clean(answer)
    if len(q) < 5 or len(a) < 10:
        return None
    return (company, categorize(q, a), q, a, auto_tag(q, a, company))


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
    return webdriver.Chrome(options=opts)


def accept_cookies(driver: webdriver.Chrome) -> None:
    for label in ("모두 수락", "Accept All", "Accept"):
        try:
            btn = driver.find_element(By.XPATH, f"//button[contains(text(), '{label}')]")
            driver.execute_script("arguments[0].click();", btn)
            time.sleep(1)
            return
        except Exception:
            continue


def crawl_genesis() -> list[tuple]:
    company = "제네시스"
    rows = []
    try:
        r = requests.get(GENESIS_FAQ_URL, headers=HEADERS, timeout=30)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for item in soup.select("div.cp-faq__accordion-item"):
            title = item.select_one("p.accordion-title")
            panel = item.select_one("div.accordion-panel-inner")
            if not title or not panel:
                continue
            row = _row(company, title.get_text(" ", strip=True), panel.get_text(" ", strip=True))
            if row:
                rows.append(row)
    except Exception as exc:
        print(f"  [ERROR] 제네시스: {type(exc).__name__}: {exc}")
    return rows


def crawl_hyundai() -> list[tuple]:
    company = "현대"
    rows = []
    try:
        body = {
            "siteTypeCode": "H",
            "faqCategoryCode": "",
            "faqCode": "",
            "faqSeq": "",
            "searchKeyword": "",
            "pageNo": 1,
            "pageSize": "500",
            "externalYn": "",
        }
        r = requests.post(
            HYUNDAI_LIST_URL,
            headers={
                **HEADERS,
                "Content-Type": "application/json",
                "Referer": "https://www.hyundai.com/kr/ko/e/customer/center/faq",
            },
            json=body,
            timeout=30,
        )
        r.raise_for_status()
        for item in (r.json().get("data") or {}).get("list") or []:
            row = _row(company, item.get("faqQuestion", ""), strip_html(item.get("faqAnswer", "")))
            if row:
                rows.append(row)
    except Exception as exc:
        print(f"  [ERROR] 현대: {type(exc).__name__}: {exc}")
    return rows


def crawl_kia() -> list[tuple]:
    company = "기아"
    rows = []
    try:
        r = requests.get(
            KIA_FAQ_URL,
            headers={**HEADERS, "Referer": "https://www.kia.com/kr/customer-service/center/faq"},
            timeout=30,
        )
        r.raise_for_status()
        items = r.json().get("data", {}).get("faqList", {}).get("items") or []
        for item in items:
            row = _row(
                company,
                item.get("question", ""),
                strip_html((item.get("answer") or {}).get("html", "")),
            )
            if row:
                rows.append(row)
    except Exception as exc:
        print(f"  [ERROR] 기아: {type(exc).__name__}: {exc}")
    return rows


def _extract_sf_answer(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    best = ""
    for sel in (
        "lightning-formatted-rich-text",
        ".slds-rich-text-editor__output",
        "[class*='article-body']",
        "article",
    ):
        for el in soup.select(sel):
            text = clean(el.get_text(" ", strip=True))
            if len(text) > len(best):
                best = text
    return best


def _parse_sf_homepage(html: str) -> list[tuple[str, str]]:
    """Salesforce FAQ 홈(인기 도움말) HTML에서 Q/A 추출."""
    soup = BeautifulSoup(html, "html.parser")
    pairs: list[tuple[str, str]] = []
    for preview in soup.select("div.article-preview"):
        h2 = preview.find_previous("h2")
        if not h2:
            continue
        q = clean(h2.get_text(" ", strip=True))
        if not q or q == "인기 도움말":
            continue
        a_el = preview.select_one("lightning-formatted-rich-text, .article-body")
        a = clean(a_el.get_text(" ", strip=True)) if a_el else ""
        if len(q) > 10 and len(a) > 10:
            pairs.append((q, a))
    return pairs


def crawl_salesforce_portal(company: str, start_url: str) -> list[tuple]:
    """BMW Group Salesforce FAQ 포털 (BMW·MINI)."""
    rows = []
    driver = None
    try:
        driver = build_driver(headless=HEADLESS)
        driver.set_page_load_timeout(45)
        driver.get(start_url)
        time.sleep(12)
        accept_cookies(driver)
        time.sleep(4)

        seen: set[str] = set()
        for q, a in _parse_sf_homepage(driver.page_source):
            if q in seen:
                continue
            seen.add(q)
            row = _row(company, q, a)
            if row:
                rows.append(row)
    except Exception as exc:
        print(f"  [ERROR] {company}(Salesforce): {type(exc).__name__}: {exc}")
    finally:
        if driver is not None:
            driver.quit()
    return rows


def crawl_with_selenium(company: str, url: str, wait_sec: int = 6) -> list[tuple]:
    """SPA/봇 차단 페이지 Selenium 시도."""
    rows = []
    driver = None
    try:
        driver = build_driver(headless=HEADLESS)
        driver.set_page_load_timeout(40)
        driver.get(url)
        time.sleep(wait_sec)
        accept_cookies(driver)
        soup = BeautifulSoup(driver.page_source, "html.parser")
        if "access denied" in soup.get_text(" ", strip=True).lower():
            return rows
        for item in soup.select(
            "div.cp-faq__accordion-item, .accordion-item, details, [class*='faq'] li"
        ):
            q_el = item.select_one("p.accordion-title, .accordion-title, summary, h3, h4, dt")
            a_el = item.select_one("div.accordion-panel-inner, .accordion-body, dd, p")
            if not q_el:
                continue
            row = _row(
                company,
                q_el.get_text(" ", strip=True),
                a_el.get_text(" ", strip=True) if a_el else item.get_text(" ", strip=True),
            )
            if row:
                rows.append(row)
    except Exception as exc:
        print(f"  [ERROR] {company}(Selenium): {type(exc).__name__}: {exc}")
    finally:
        if driver is not None:
            driver.quit()
    return rows


BRAND_CRAWLERS = {
    "제네시스": crawl_genesis,
    "현대": crawl_hyundai,
    "기아": crawl_kia,
    "BMW": lambda: crawl_salesforce_portal("BMW", "https://www.bmw.co.kr/kr/s/?language=ko"),
    "미니": lambda: crawl_salesforce_portal("미니", "https://faq.mini.co.kr/s/?language=ko"),
    "벤츠": lambda: crawl_with_selenium(
        "벤츠", "https://www.mercedes-benz.co.kr/passengercars/ko/mercedes-me/faq.html"
    ),
    "볼보": lambda: crawl_with_selenium("볼보", "https://www.volvocars.com/kr/support"),
    "아우디": lambda: crawl_with_selenium(
        "아우디", "https://www.audi.co.kr/ko/web/ko/tools/support/faq.html"
    ),
    "테슬라": lambda: crawl_with_selenium("테슬라", "https://www.tesla.com/ko_KR/support"),
    "쉐보레": lambda: crawl_with_selenium(
        "쉐보레", "https://www.chevrolet.co.kr/purchase/offers-faq.gm"
    ),
}


def save_to_db(company: str, rows: list[tuple]) -> int:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM company_faq WHERE company = %s", (company,))
    if rows:
        cur.executemany(
            "INSERT INTO company_faq (company, car_category, question, answer, persona_tags) "
            "VALUES (%s,%s,%s,%s,%s)",
            rows,
        )
    conn.commit()
    cur.close()
    conn.close()
    return len(rows)


def cleanup_legacy_faq() -> None:
    """하드코딩 시드/구버전 FAQ 잔여 데이터 제거."""
    legacy_companies = ("Car-BTI 맞춤형 FAQ", "르노코리아")
    conn = get_connection()
    cur = conn.cursor()
    total = 0
    for company in legacy_companies:
        cur.execute("DELETE FROM company_faq WHERE company = %s", (company,))
        total += cur.rowcount
    conn.commit()
    cur.close()
    conn.close()
    if total:
        print(f"[CLEAN] 구버전 FAQ {total}건 삭제")


def main() -> None:
    _configure_stdout()
    print("[START] 브랜드 FAQ 크롤링 → MySQL")
    cleanup_legacy_faq()
    total = 0
    for company, fn in BRAND_CRAWLERS.items():
        print(f"\n[BRAND] {company} 크롤링 중...")
        rows = fn()
        if not rows and company in FALLBACK_BRANDS:
            rows = get_fallback_rows(company)
            n = save_to_db(company, rows)
            print(f"  [FALLBACK] {company}: 크롤링 불가 → 대표 FAQ {n}건 적재")
        else:
            n = save_to_db(company, rows)
            if n:
                print(f"  [SAVE] {company}: {n}건 적재")
            else:
                print(f"  [WARN] {company}: 수집 0건")
        total += n
    print(f"\n[DONE] 총 {total}건 적재 완료")


if __name__ == "__main__":
    main()
