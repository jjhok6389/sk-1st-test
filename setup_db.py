"""
setup_db.py
============
프로젝트 DB(SQLite) 초기화 스크립트 (스키마 v2).

변경 이력
---------
v2
  · company_faq 에 'persona_tags' 컬럼 신설
      → 각 FAQ에 Car-BTI 자리수 태그(E/G/L/S/P/B/I/D)를 콤마구분으로 저장
      → 지역 페르소나와의 매칭 점수 계산용 (예: "B,D" = 가성비+국산 페르소나에 친화적)
  · persona_cars 의 persona_type → persona_axis 로 컬럼 의미 명확화
      → Car-BTI 4자리 중 한 자리(E/G/L/S/P/B/I/D)에 매칭되는 추천 차량
  · persona_cars 에 reason(추천 이유) 컬럼 추가
  · persona_cars 초기 데이터 24건 주입 (각 자리수당 3건)
"""

import os
import sqlite3

# ──────────────────────────────────────
# 0. 준비
# ──────────────────────────────────────
os.makedirs("db", exist_ok=True)
conn = sqlite3.connect("db/car_bti.db")
cur = conn.cursor()

# ──────────────────────────────────────
# 1. 테이블 초기화 (재실행 안전)
# ──────────────────────────────────────
cur.execute("DROP TABLE IF EXISTS region_stats")
cur.execute("DROP TABLE IF EXISTS persona_cars")
cur.execute("DROP TABLE IF EXISTS company_faq")

# 지역별 통계 (참고용 — app.py 는 현재 하드코딩 데이터를 사용)
cur.execute("""
CREATE TABLE region_stats (
    region        TEXT PRIMARY KEY,
    ev_ratio      REAL,
    suv_ratio     REAL,
    persona_type  TEXT
)
""")

# 페르소나 축별 추천 차량
# img_url 은 비워둠 → crawler/crawl_car_images.py 가 위키피디아에서 채움
cur.execute("""
CREATE TABLE persona_cars (
    car_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    persona_axis  TEXT NOT NULL,
    brand         TEXT,
    car_model     TEXT,
    price         TEXT,
    reason        TEXT,
    img_url       TEXT
)
""")

# 기업 FAQ (persona_tags 컬럼 추가)
cur.execute("""
CREATE TABLE company_faq (
    faq_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    car_category  TEXT,
    question      TEXT,
    answer        TEXT,
    persona_tags  TEXT
)
""")

print("✅ 3개 테이블 생성 완료 (스키마 v2)")

# ──────────────────────────────────────
# 2. region_stats 더미 (참고용)
# ──────────────────────────────────────
dummy_stats = [
    ("서울", 15.2, 45.1, "GSPI"),
    ("제주", 35.8, 30.5, "ESBD"),
    ("경기", 12.5, 55.0, "GLBD"),
]
cur.executemany(
    "INSERT INTO region_stats (region, ev_ratio, suv_ratio, persona_type) VALUES (?,?,?,?)",
    dummy_stats,
)

# ──────────────────────────────────────
# 3. persona_cars 초기 데이터 (각 자리수당 3건, 총 24건)
# ──────────────────────────────────────
persona_cars_data = [
    # ── E: 친환경 ──
    ("E", "현대",   "아이오닉 5",   "5,000만원~", "800V 초고속 충전·V2L 기능을 갖춘 국산 EV의 대표주자"),
    ("E", "기아",   "EV6",         "4,900만원~", "스포티 디자인과 롱레인지 510km 주행거리를 갖춘 인기 전기차"),
    ("E", "테슬라", "Model 3",      "5,200만원~", "오토파일럿과 글로벌 EV 시장 리더십을 보유한 베스트셀러"),

    # ── G: 내연기관 ──
    ("G", "현대",       "쏘나타",  "2,800만원~", "국내 중형 세단 스테디셀러, 검증된 신뢰성과 정비 인프라"),
    ("G", "기아",       "K5",      "2,700만원~", "쏘나타의 강력한 라이벌, 스포티한 디자인이 강점"),
    ("G", "르노코리아", "QM6 LPG", "2,900만원~", "LPG 모델로 유지비 부담을 낮춘 합리적 패밀리 SUV"),

    # ── L: 대형/SUV ──
    ("L", "현대",     "팰리세이드", "4,000만원~", "7~8인승 대형 SUV의 베스트셀러, 패밀리·레저에 강점"),
    ("L", "기아",     "카니발",     "3,500만원~", "국민 미니밴, 캠핑·다인승 운송 양쪽에 최적"),
    ("L", "제네시스", "GV80",       "6,800만원~", "국산 럭셔리 대형 SUV의 자존심"),

    # ── S: 소형/세단 ──
    ("S", "현대", "아반떼",  "1,900만원~", "도심 출퇴근과 첫차로 가장 인기 있는 준중형 세단"),
    ("S", "기아", "K3",      "1,800만원~", "아반떼의 가장 강력한 가성비 대안"),
    ("S", "현대", "캐스퍼",  "1,400만원~", "경차이지만 SUV 감성을 살린 1인 가구 최적 모델"),

    # ── P: 프리미엄 ──
    ("P", "제네시스", "G80",       "6,300만원~", "국산 프리미엄 세단의 정점, 수입차에 견줄 정숙성"),
    ("P", "벤츠",     "E-Class",   "7,500만원~", "국내 수입차 판매 1위, 프리미엄 세단의 상징"),
    ("P", "BMW",      "5 Series",  "7,200만원~", "다이내믹한 주행감과 프리미엄 이미지의 대표 모델"),

    # ── B: 가성비 ──
    ("B", "현대",   "캐스퍼",          "1,400만원~", "신차 1,400만원대 진입, 경차 보조금 혜택까지"),
    ("B", "기아",   "모닝",            "1,200만원~", "경차 중 가장 저렴, 도심 주차/유지비가 압도적"),
    ("B", "쉐보레", "트레일블레이저",  "2,300만원~", "옵션 대비 가격이 합리적인 가성비 소형 SUV"),

    # ── I: 수입 ──
    ("I", "벤츠", "C-Class",   "6,200만원~", "입문용 프리미엄 수입 세단의 표준"),
    ("I", "BMW",  "3 Series",  "5,800만원~", "운전의 재미를 중시하는 수입차 매니아의 첫 선택"),
    ("I", "볼보", "XC60",      "7,000만원~", "안전과 스칸디나비안 디자인의 대표 수입 SUV"),

    # ── D: 국산 ──
    ("D", "현대",     "쏘나타",  "2,800만원~", "전국 어디서나 정비/부품 수급이 용이한 베스트 국산차"),
    ("D", "기아",     "쏘렌토",  "3,500만원~", "국내 중형 SUV 시장의 베스트셀러"),
    ("D", "제네시스", "G70",     "4,500만원~", "국산 후륜구동 스포츠 세단, 합리적 가격의 프리미엄"),
]

cur.executemany(
    "INSERT INTO persona_cars (persona_axis, brand, car_model, price, reason) VALUES (?,?,?,?,?)",
    persona_cars_data,
)
print(f"✅ persona_cars: 초기 {len(persona_cars_data)}건 주입 완료")
print("ℹ️  company_faq 는 다음 단계인 crawl_faq.py 실행 시 채워집니다")

conn.commit()
conn.close()