"""
crawl_car_images.py
===================
persona_cars(MySQL) 테이블의 차량 이미지를 위키피디아에서 수집해
MySQL에 직접 적재한다. (img_data: LONGBLOB, img_mime, img_url)

- Selenium/다나와 의존 없이 requests + BeautifulSoup 만 사용
- 로컬 백업본도 db/images/<car_id>.<ext> 로 함께 저장
"""

import os
import sys
import time

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db_config import get_connection  # noqa: E402

IMAGES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "db", "images")
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    # upload.wikimedia.org는 Referer 없이는 종종 차단/지연됨
    "Referer": "https://en.wikipedia.org/",
}

# (브랜드, 모델) → 위키피디아 영문 문서 제목
WIKI_MAPPING = {
    ("현대", "아이오닉 5"): "Hyundai_Ioniq_5",
    ("현대", "코나 일렉트릭"): "Hyundai_Kona",
    ("현대", "아이오닉 6"): "Hyundai_Ioniq_6",
    ("현대", "아이오닉 7"): "Hyundai_Ioniq_9",
    ("현대", "넥쏘"): "Hyundai_Nexo",
    ("현대", "아반떼 N Line"): "Hyundai_Elantra",
    ("현대", "아반떼"): "Hyundai_Elantra",
    ("현대", "쏘나타"): "Hyundai_Sonata",
    ("현대", "캐스퍼"): "Hyundai_Casper",
    ("현대", "팰리세이드"): "Hyundai_Palisade",
    ("현대", "스타리아"): "Hyundai_Staria",
    ("기아", "EV6"): "Kia_EV6",
    ("기아", "니로 EV"): "Kia_Niro",
    ("기아", "EV9"): "Kia_EV9",
    ("기아", "K5"): "Kia_K5",
    ("기아", "K3"): "Kia_Forte",
    ("기아", "모닝"): "Kia_Morning",
    ("기아", "쏘렌토"): "Kia_Sorento",
    ("기아", "카니발"): "Kia_Carnival",
    ("제네시스", "Electrified GV70"): "Genesis_Electrified_GV70",
    ("제네시스", "G70"): "Genesis_G70",
    ("제네시스", "GV80"): "Genesis_GV80",
    ("테슬라", "Model 3"): "Tesla_Model_3",
    ("테슬라", "Model Y"): "Tesla_Model_Y",
    ("테슬라", "Model X"): "Tesla_Model_X",
    ("BMW", "i4"): "BMW_i4",
    ("BMW", "iX"): "BMW_iX",
    ("BMW", "iX1"): "BMW_iX1",
    ("BMW", "3 Series"): "BMW_3_Series",
    ("BMW", "1 Series"): "BMW_1_Series",
    ("BMW", "X5"): "BMW_X5",
    ("BMW", "X3"): "BMW_X3",
    ("벤츠", "EQB"): "Mercedes-Benz_EQB",
    ("벤츠", "EQA"): "Mercedes-Benz_EQA",
    ("벤츠", "EQS SUV"): "Mercedes-Benz_EQS",
    ("벤츠", "C-Class"): "Mercedes-Benz_C-Class",
    ("벤츠", "A-Class"): "Mercedes-Benz_A-Class",
    ("벤츠", "GLE"): "Mercedes-Benz_GLE",
    ("벤츠", "GLC"): "Mercedes-Benz_GLC",
    ("아우디", "Q4 e-tron"): "Audi_Q4_e-tron",
    ("아우디", "e-tron"): "Audi_Q8_e-tron",
    ("아우디", "A3"): "Audi_A3",
    ("아우디", "A1"): "Audi_A1",
    ("아우디", "Q7"): "Audi_Q7",
    ("아우디", "Q5"): "Audi_Q5",
    ("볼보", "XC40 Recharge"): "Volvo_XC40",
    ("볼보", "XC60 Recharge"): "Volvo_XC60",
    ("볼보", "XC60"): "Volvo_XC60",
    ("볼보", "XC90"): "Volvo_XC90",
    ("볼보", "S60"): "Volvo_S60",
    ("미니", "Cooper SE"): "Mini_Electric",
    ("미니", "Cooper"): "Mini_Hatch",
    ("쉐보레", "볼트 EUV"): "Chevrolet_Bolt_EUV",
}

MIME_BY_EXT = {"png": "image/png", "webp": "image/webp", "gif": "image/gif", "jpg": "image/jpeg"}


def _configure_stdout() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass


def get_image_from_wiki(wiki_title: str) -> str | None:
    url = f"https://en.wikipedia.org/wiki/{wiki_title}"
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        if response.status_code != 200:
            return None

        soup = BeautifulSoup(response.text, "html.parser")
        infobox = soup.find("table", class_=lambda css: css and "infobox" in css)
        if not infobox:
            return None

        img = infobox.find("img")
        if not img or not img.get("src"):
            return None

        src = img["src"]
        if src.startswith("//"):
            src = "https:" + src
        return src
    except Exception:
        return None


def upscale_thumb(src: str, px: int = 500) -> str | None:
    """썸네일 URL을 더 큰 해상도로 치환. thumb가 아니면 None."""
    if "/thumb/" not in src:
        return None
    import re as _re

    new = _re.sub(r"/\d+px-([^/]+)$", rf"/{px}px-\1", src)
    return new if new != src else None


def fetch_image_bytes(url: str, retries: int = 3) -> tuple[bytes, str] | None:
    """이미지 URL → (바이너리, 확장자). 실패 시 None. (네트워크 지연 대비 재시도)"""
    for attempt in range(retries):
        try:
            response = requests.get(url, headers=HEADERS, timeout=30)
            if response.status_code in (429, 500, 502, 503, 504):
                # 레이트 리밋/일시 오류 → 백오프 후 재시도
                if attempt == retries - 1:
                    return None
                time.sleep(3.0 * (attempt + 1))
                continue
            if response.status_code != 200:
                return None

            content_type = response.headers.get("Content-Type", "").lower()
            if "png" in content_type:
                ext = "png"
            elif "webp" in content_type:
                ext = "webp"
            elif "gif" in content_type:
                ext = "gif"
            else:
                ext = "jpg"

            data = response.content
            if len(data) < 2000:  # 플레이스홀더/오류 응답 방지
                return None
            return data, ext
        except Exception:
            if attempt == retries - 1:
                return None
            time.sleep(1.0)
    return None


def main() -> None:
    _configure_stdout()
    print("[START] 위키피디아 차량 이미지 크롤러 → MySQL 적재")
    os.makedirs(IMAGES_DIR, exist_ok=True)

    conn = get_connection()
    cur = conn.cursor()

    # 전체 재수집 여부: "python crawl_car_images.py all" → 전체, 기본 → 누락분만
    force_all = len(sys.argv) > 1 and sys.argv[1].lower() in ("all", "--all", "-a")
    if force_all:
        cur.execute("SELECT car_id, brand, car_model FROM persona_cars ORDER BY car_id")
    else:
        cur.execute(
            "SELECT car_id, brand, car_model FROM persona_cars "
            "WHERE img_data IS NULL OR LENGTH(img_data) < 2000 ORDER BY car_id"
        )
    cars = cur.fetchall()
    mode = "전체 재수집" if force_all else "누락분만 수집"
    print(f"        대상 차량: {len(cars)}대 ({mode})\n")

    success = unmapped = url_failed = dl_failed = 0
    for car_id, brand, model in cars:
        wiki_title = WIKI_MAPPING.get((brand, model))
        if not wiki_title:
            print(f"  [SKIP] 매핑 없음: [{car_id:>2}] {brand} {model}")
            unmapped += 1
            continue

        img_url = get_image_from_wiki(wiki_title)
        if not img_url:
            print(f"  [FAIL] 이미지 URL 없음: [{car_id:>2}] {brand} {model}")
            url_failed += 1
            continue

        # 고해상도(500px) 우선 시도 → 실패 시 원본 썸네일로 폴백
        fetched = None
        upscaled = upscale_thumb(img_url, 500)
        for candidate in (upscaled, img_url):
            if not candidate:
                continue
            fetched = fetch_image_bytes(candidate)
            if fetched:
                img_url = candidate
                break

        if not fetched:
            print(f"  [FAIL] 다운로드 실패: [{car_id:>2}] {brand} {model}")
            dl_failed += 1
            continue

        data, ext = fetched
        mime = MIME_BY_EXT.get(ext, "image/jpeg")

        # 로컬 백업 저장
        local_path = os.path.join(IMAGES_DIR, f"{car_id}.{ext}")
        try:
            with open(local_path, "wb") as f:
                f.write(data)
            rel_path = f"db/images/{car_id}.{ext}"
        except Exception:
            rel_path = None

        # MySQL 적재 (바이너리 + URL + mime)
        cur.execute(
            "UPDATE persona_cars SET img_data=%s, img_mime=%s, img_url=%s WHERE car_id=%s",
            (data, mime, rel_path or img_url, car_id),
        )
        conn.commit()
        print(f"  [OK] [{car_id:>2}] {brand} {model} -> {len(data):,} bytes ({mime})")
        success += 1
        time.sleep(1.0)  # 레이트 리밋 회피

    cur.close()
    conn.close()

    print("\n[RESULT]")
    print(f"  성공(DB 적재): {success}건")
    if unmapped:
        print(f"  매핑 없음: {unmapped}건")
    if url_failed:
        print(f"  URL 실패: {url_failed}건")
    if dl_failed:
        print(f"  다운로드 실패: {dl_failed}건")
    print("\n[DONE] Streamlit 앱을 새로고침하면 이미지가 표시됩니다.")


if __name__ == "__main__":
    main()
