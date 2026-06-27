"""
setup_db.py
============
프로젝트 DB(MySQL) 초기화 스크립트 (스키마 v4 - MySQL 전환).

변경 이력
---------
v4 (MySQL 전환)
  · SQLite → MySQL 전면 전환 (db_config.py 사용)
  · persona_cars 에 img_data(LONGBLOB)·img_mime 컬럼 추가
      → 크롤링한 차량 이미지 바이너리를 DB에 직접 적재
  · "아우디" 브랜드 표기 오타(아udi) 정정
v3
  · Car-BTI 3번째 축: 프리미엄(P)/가성비(B) → 남(M)/여(W)
  · persona_cars: persona_type(4자리) 기준 추천 차량 64건 (16유형 × 4대)
  · company_faq: company 컬럼 추가 → 추천 차량 브랜드별 FAQ 연동
"""

from db_config import ensure_database, get_config, get_connection

# ──────────────────────────────────────
# 0. 데이터베이스 + 연결 준비
# ──────────────────────────────────────
ensure_database()
conn = get_connection()
cur = conn.cursor()
print(f"[OK] MySQL 연결 완료 → {get_config()['database']}")

# ──────────────────────────────────────
# 1. 테이블 초기화 (재실행 안전)
# ──────────────────────────────────────
# region_stats 는 prepare_data.py + load_to_mysql.py 가 소유/적재한다 (실제 등록 통계).
# 여기서는 건드리지 않는다.
cur.execute("DROP TABLE IF EXISTS persona_cars")
cur.execute("DROP TABLE IF EXISTS company_faq")

cur.execute("""
CREATE TABLE persona_cars (
    car_id        INT AUTO_INCREMENT PRIMARY KEY,
    persona_type  VARCHAR(4) NOT NULL,
    brand         VARCHAR(40),
    car_model     VARCHAR(60),
    price         VARCHAR(40),
    reason        TEXT,
    img_url       VARCHAR(500),
    img_data      LONGBLOB,
    img_mime      VARCHAR(40),
    INDEX idx_persona (persona_type),
    INDEX idx_brand (brand)
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
""")

cur.execute("""
CREATE TABLE company_faq (
    faq_id        INT AUTO_INCREMENT PRIMARY KEY,
    company       VARCHAR(40),
    car_category  VARCHAR(40),
    question      TEXT,
    answer        TEXT,
    persona_tags  VARCHAR(40),
    INDEX idx_company (company)
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
""")

print("[OK] persona_cars / company_faq 테이블 생성 완료 (MySQL)")
print("[INFO] region_stats 는 prepare_data.py → load_to_mysql.py 로 적재하세요")

# ──────────────────────────────────────
# 2. persona_cars 초기 데이터 (16유형 × 4대 = 64건)
#    각 유형은 4축(친환경/크기/성별/국외)을 모두 충족하는 차량으로 구성
# ──────────────────────────────────────
PERSONA_CARS = {
    "ESMD": [
        ("현대", "아이오닉 5", "5,000만원~", "800V 충전·V2L을 갖춘 국산 EV 대표, 남성 1인·2인 가구 인기"),
        ("기아", "EV6", "4,900만원~", "스포티 디자인과 510km 주행거리, 도심형 EV 세단/SUV"),
        ("현대", "코나 일렉트릭", "4,800만원~", "컴팩트 SUV EV, 도심 주차·출퇴근에 최적"),
        ("기아", "니로 EV", "4,700만원~", "실용적 국산 전기 SUV, 합리적 가격대"),
    ],
    "ESMI": [
        ("테슬라", "Model 3", "5,200만원~", "글로벌 EV 베스트셀러, 남성 운전자 선호 1위 수입 EV"),
        ("BMW", "i4", "6,500만원~", "스포티 전기 그란투리스모, 수입 EV 세단의 대표"),
        ("벤츠", "EQB", "6,800만원~", "프리미엄 전기 SUV, 도심·가족 겸용"),
        ("아우디", "Q4 e-tron", "6,200만원~", "콤팩트 프리미엄 전기 SUV, 젊은 남성층 인기"),
    ],
    "ESFD": [
        ("현대", "아이오닉 6", "5,300만원~", "유선형 디자인의 국산 전기 세단, 여성 운전자 선호"),
        ("기아", "EV6", "4,900만원~", "감각적 인테리어와 편의 사양, 여성 1인 가구 인기"),
        ("현대", "아이오닉 5", "5,000만원~", "넓은 실내·직관적 UI, 가족·여성 운전자 친화"),
        ("쉐보레", "볼트 EUV", "4,500만원~", "합리적 가격의 소형 전기 SUV"),
    ],
    "ESFI": [
        ("테슬라", "Model Y", "5,900만원~", "실용적 수입 전기 SUV, 여성 운전자 비중 높음"),
        ("볼보", "XC40 Recharge", "6,500만원~", "안전·디자인 중시 여성층 인기 수입 EV"),
        ("미니", "Cooper SE", "5,400만원~", "감각적 도심형 전기 해치백, 여성 1인 가구"),
        ("벤츠", "EQA", "6,000만원~", "프리미엄 소형 전기 SUV, 도심 출퇴근 최적"),
    ],
    "ELMD": [
        ("현대", "아이오닉 7", "6,500만원~", "7인승 대형 전기 SUV, 패밀리·남성 운전자"),
        ("기아", "EV9", "7,000만원~", "3열 대형 전기 SUV, 레저·캠핑 겸용"),
        ("제네시스", "Electrified GV70", "8,500만원~", "프리미엄 전기 SUV, 국산 고급 EV"),
        ("현대", "넥쏘", "7,500만원~", "수소 SUV, 친환경 대형차 선호층"),
    ],
    "ELMI": [
        ("테슬라", "Model X", "1억원~", "대형 전기 SUV, 수입 EV 플래그십"),
        ("BMW", "iX", "1.1억원~", "프리미엄 대형 전기 SUV, 남성 고소득층"),
        ("벤츠", "EQS SUV", "1.3억원~", "럭셔리 전기 SUV, 수입 대형 EV 대표"),
        ("아우디", "e-tron", "9,500만원~", "대형 프리미엄 전기 SUV, 레저·출장 겸용"),
    ],
    "ELFD": [
        ("기아", "EV9", "7,000만원~", "넓은 실내·편의 사양, 여성 패밀리카로 인기"),
        ("현대", "아이오닉 7", "6,500만원~", "7인승 전기 SUV, 가족·여성 운전자 친화"),
        ("제네시스", "Electrified GV70", "8,500만원~", "프리미엄 전기 SUV, 안전·편의 중시"),
        ("볼보", "XC40 Recharge", "6,500만원~", "안전 중심 수입 전기 SUV"),
    ],
    "ELFI": [
        ("테슬라", "Model Y", "5,900만원~", "실용적 대형 전기 SUV, 여성 운전자 선호"),
        ("볼보", "XC60 Recharge", "8,000만원~", "안전·스칸디 디자인, 여성 패밀리 SUV"),
        ("벤츠", "EQB", "6,800만원~", "프리미엄 전기 SUV, 도심·가족 겸용"),
        ("BMW", "iX1", "6,200만원~", "콤팩트 프리미엄 전기 SUV"),
    ],
    "GSMD": [
        ("현대", "아반떼 N Line", "2,500만원~", "스포티 국산 준중형, 남성 20~30대 인기"),
        ("기아", "K5", "2,700만원~", "스포티 디자인 국산 중형 세단"),
        ("제네시스", "G70", "4,500만원~", "국산 후륜구동 스포츠 세단, 남성 운전자"),
        ("현대", "쏘나타", "2,800만원~", "검증된 국산 중형 세단, 실용·신뢰성"),
    ],
    "GSMI": [
        ("BMW", "3 Series", "5,800만원~", "남성 운전자 1위 수입 세단, 스포티 주행감"),
        ("벤츠", "C-Class", "6,200만원~", "도심 출퇴근 프리미엄 수입 세단"),
        ("아우디", "A3", "4,500만원~", "컴팩트 수입 세단, 젊은 남성층 인기"),
        ("볼보", "S60", "5,500만원~", "안전·디자인 중시 수입 세단"),
    ],
    "GSFD": [
        ("현대", "아반떼", "1,900만원~", "국내 1위 준중형, 여성 첫차·출퇴근용"),
        ("기아", "K3", "1,800만원~", "합리적 가격 국산 세단, 여성 1인 가구"),
        ("현대", "캐스퍼", "1,400만원~", "SUV 감성 경차, 여성 도심 운전자 인기"),
        ("기아", "모닝", "1,200만원~", "경차 중 가성비, 주차·유지비 부담 최소"),
    ],
    "GSFI": [
        ("미니", "Cooper", "4,200만원~", "감각적 도심형 수입 해치백, 여성 운전자"),
        ("벤츠", "A-Class", "4,800만원~", "프리미엄 소형 수입 세단, 여성 1인 가구"),
        ("BMW", "1 Series", "4,500만원~", "컴팩트 수입 해치백, 도심 주행"),
        ("아우디", "A1", "3,900만원~", "스타일리시 소형 수입차, 여성층 선호"),
    ],
    "GLMD": [
        ("현대", "팰리세이드", "4,000만원~", "7~8인승 대형 SUV, 남성 패밀리·레저"),
        ("기아", "쏘렌토", "3,500만원~", "국산 중형 SUV 베스트셀러, 남성 운전자"),
        ("제네시스", "GV80", "6,800만원~", "국산 럭셔리 대형 SUV"),
        ("기아", "카니발", "3,500만원~", "다인승·캠핑 겸용, 남성 운전자"),
    ],
    "GLMI": [
        ("BMW", "X5", "9,500만원~", "대형 프리미엄 SUV, 남성 고소득층 1위"),
        ("벤츠", "GLE", "1억원~", "럭셔리 대형 SUV, 수입 SUV 대표"),
        ("아우디", "Q7", "9,800만원~", "3열 대형 수입 SUV, 레저·출장"),
        ("볼보", "XC90", "9,500만원~", "안전·대형 SUV, 남성 패밀리카"),
    ],
    "GLFD": [
        ("기아", "카니발", "3,500만원~", "국민 미니밴, 여성·가족 다인승"),
        ("현대", "팰리세이드", "4,000만원~", "넓은 실내·편의, 여성 패밀리 SUV"),
        ("기아", "쏘렌토", "3,500만원~", "실용적 국산 SUV, 여성 운전자"),
        ("현대", "스타리아", "3,800만원~", "다목적 RV, 가족·여성 운전자"),
    ],
    "GLFI": [
        ("볼보", "XC60", "7,000만원~", "안전·스칸디 디자인, 여성 SUV 1위"),
        ("벤츠", "GLC", "7,500만원~", "프리미엄 중형 SUV, 여성 운전자"),
        ("BMW", "X3", "6,800만원~", "콤팩트 프리미엄 SUV, 도심·레저"),
        ("아우디", "Q5", "6,500만원~", "균형 잡힌 수입 SUV, 여성 패밀리"),
    ],
}

persona_cars_rows = []
for persona_type, cars in PERSONA_CARS.items():
    for brand, model, price, reason in cars:
        persona_cars_rows.append((persona_type, brand, model, price, reason))

cur.executemany(
    "INSERT INTO persona_cars (persona_type, brand, car_model, price, reason) "
    "VALUES (%s,%s,%s,%s,%s)",
    persona_cars_rows,
)
print(f"[OK] persona_cars: {len(persona_cars_rows)}건 주입 완료 (16유형 x 4대)")

print("[INFO] company_faq 는 크롤러로만 적재합니다:")
print("       python crawler/crawl_brand_faq.py  (브랜드 공식 FAQ)")
print("       python crawler/crawl_faq.py      (K Car 옥션 FAQ)")
print("[INFO] 차량 이미지는 crawler/crawl_car_images.py 실행 시 적재됩니다")

conn.commit()
cur.close()
conn.close()
