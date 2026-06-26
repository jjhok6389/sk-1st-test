"""
crawl_car_images.py  (v3 — BeautifulSoup 단일 방식)
===================================================
BeautifulSoup 으로 위키피디아 페이지를 직접 파싱해 이미지를 다운로드한다.
위키피디아 API (403 차단 회피).

수집 전략
---------
  1) requests + BeautifulSoup 으로 위키 페이지 직접 접근
  2) infobox 테이블에서 첫 이미지 추출
  3) 이미지를 로컬 ./db/images/{car_id}.jpg 로 다운로드
  4) DB 의 img_url 에 로컬 경로 저장
"""

import os
import sqlite3
import time

import requests
from bs4 import BeautifulSoup

DB_PATH = "db/car_bti.db"
IMAGES_DIR = "db/images"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}

WIKI_MAPPING = {
    ("현대",       "아이오닉 5"):       "Hyundai_Ioniq_5",
    ("기아",       "EV6"):              "Kia_EV6",
    ("테슬라",     "Model 3"):          "Tesla_Model_3",
    ("현대",       "쏘나타"):           "Hyundai_Sonata",
    ("기아",       "K5"):               "Kia_K5",
    ("르노코리아", "QM6 LPG"):          "Renault_Koleos",
    ("현대",       "팰리세이드"):       "Hyundai_Palisade",
    ("기아",       "카니발"):           "Kia_Carnival",
    ("제네시스",   "GV80"):             "Genesis_GV80",
    ("현대",       "아반떼"):           "Hyundai_Elantra",
    ("기아",       "K3"):               "Kia_Forte",
    ("현대",       "캐스퍼"):           "Hyundai_Casper",
    ("제네시스",   "G80"):              "Genesis_G80",
    ("벤츠",       "E-Class"):          "Mercedes-Benz_E-Class",
    ("BMW",        "5 Series"):         "BMW_5_Series",
    ("쉐보레",     "트레일블레이저"):    "Chevrolet_Trailblazer",
    ("기아",       "모닝"):             "Kia_Picanto",
    ("벤츠",       "C-Class"):          "Mercedes-Benz_C-Class",
    ("BMW",        "3 Series"):         "BMW_3_Series",
    ("볼보",       "XC60"):             "Volvo_XC60",
    ("기아",       "쏘렌토"):           "Kia_Sorento",
    ("제네시스",   "G70"):              "Genesis_G70",
}


def get_image_from_wiki(wiki_title: str) -> str | None:
    """위키피디아 페이지에서 infobox 첫 이미지의 직접 URL 추출."""
    url = f"https://en.wikipedia.org/wiki/{wiki_title}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return None
        soup = BeautifulSoup(r.text, "html.parser")
        # infobox 찾기
        infobox = soup.find("table", class_=lambda c: c and "infobox" in c)
        if not infobox:
            return None
        # infobox 안의 첫 img 찾기
        img = infobox.find("img")
        if not img or not img.get("src"):
            return None
        src = img["src"]
        if src.startswith("//"):
            src = "https:" + src
        # 썸네일은 사용 못 함 — "File:" 페이지로 가서 원본 찾기
        if "/thumb/" in src:
            file_link = infobox.find("a", href=lambda h: h and h.startswith("/wiki/File:"))
            if file_link:
                file_page_url = "https://en.wikipedia.org" + file_link["href"]
                r2 = requests.get(file_page_url, headers=HEADERS, timeout=15)
                if r2.status_code == 200:
                    soup2 = BeautifulSoup(r2.text, "html.parser")
                    orig_img = soup2.find("img", class_="mw-file-element")
                    if orig_img and orig_img.get("src"):
                        src = orig_img["src"]
                        if src.startswith("//"):
                            src = "https:" + src
        return src
    except Exception as e:
        return None


def download_image(url: str, save_path_base: str) -> str | None:
    """이미지 다운로드 후 로컬 저장. 파일 크기가 100 bytes 이상이어야 유효."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return None
        # 확장자 결정
        ct = r.headers.get("Content-Type", "").lower()
        if   "png"  in ct: ext = "png"
        elif "webp" in ct: ext = "webp"
        elif "gif"  in ct: ext = "gif"
        else:              ext = "jpg"
        
        save_path = f"{save_path_base}.{ext}"
        with open(save_path, "wb") as f:
            f.write(r.content)
        
        size = os.path.getsize(save_path)
        if size < 100:
            os.remove(save_path)
            return None
        return save_path
    except Exception:
        return None


def main():
    print("🚀 위키피디아 차량 이미지 크롤러 v3 (BeautifulSoup 직접 파싱)")
    print(f"   ▸ 저장 경로 : ./{IMAGES_DIR}/")
    print(f"   ▸ 전략      : HTML 직접 파싱 → 원본 이미지 → 로컬 저장\n")

    os.makedirs(IMAGES_DIR, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("PRAGMA table_info(persona_cars)")
    cols = [c[1] for c in cur.fetchall()]
    if "img_url" not in cols:
        cur.execute("ALTER TABLE persona_cars ADD COLUMN img_url TEXT")

    cur.execute("SELECT car_id, brand, car_model FROM persona_cars ORDER BY car_id")
    cars = cur.fetchall()
    print(f"   ▸ {len(cars)}대 차량 이미지 수집\n" + "─" * 60)

    success = unmapped = url_failed = dl_failed = 0
    for car_id, brand, model in cars:
        wiki_title = WIKI_MAPPING.get((brand, model))
        if not wiki_title:
            print(f"   ⚠️  매핑 없음     : [{car_id:>2}] {brand:<10} {model}")
            unmapped += 1
            continue

        # 1) 위키피디아 페이지에서 이미지 URL 추출
        img_url = get_image_from_wiki(wiki_title)
        if not img_url:
            print(f"   ❌  이미지 못 찾음 : [{car_id:>2}] {brand:<10} {model}")
            url_failed += 1
            continue

        # 2) 로컬 다운로드
        save_base = os.path.join(IMAGES_DIR, str(car_id))
        local_path = download_image(img_url, save_base)
        if not local_path:
            print(f"   ❌  다운로드 실패 : [{car_id:>2}] {brand:<10} {model}")
            dl_failed += 1
            continue

        # 3) DB 저장 (POSIX 슬래시로 통일)
        db_path = local_path.replace(os.sep, "/")
        cur.execute("UPDATE persona_cars SET img_url=? WHERE car_id=?", (db_path, car_id))
        print(f"   ✔️  완료          : [{car_id:>2}] {brand:<10} {model:<15} → {db_path}")
        success += 1
        time.sleep(0.3)

    conn.commit()
    conn.close()

    print("─" * 60)
    print(f"✅ 성공          : {success}건")
    if unmapped:   print(f"⚠️  매핑 없음     : {unmapped}건")
    if url_failed: print(f"❌ 이미지 못 찾음 : {url_failed}건")
    if dl_failed:  print(f"❌ 다운로드 실패  : {dl_failed}건")
    print(f"\n🎉 완료! Streamlit 새로고침 후 사진이 표시됩니다.")


if __name__ == "__main__":
    main()