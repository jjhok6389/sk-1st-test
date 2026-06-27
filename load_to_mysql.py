"""
load_to_mysql.py
================
prepare_data.py가 만든 region_stats.csv → MySQL `region_stats` 테이블 적재.
"""

import os
import sys

from dotenv import load_dotenv
import pandas as pd
import pymysql

# ──────────────────────────────────────────────
load_dotenv()   

MYSQL_CONFIG = {
    "host":     os.getenv("MYSQL_HOST", "localhost"),
    "port":     int(os.getenv("MYSQL_PORT", 3306)),
    "user":     os.getenv("MYSQL_USER", "root"),
    "password": os.getenv("MYSQL_PASSWORD", ""),
    "database": os.getenv("MYSQL_DATABASE", "car_bti"),
    "charset":  "utf8mb4",
}

CSV_PATH = "data/region_stats.csv"
TABLE    = "region_stats"

DDL_DROP = f"DROP TABLE IF EXISTS {TABLE};"

DDL_CREATE = f"""
CREATE TABLE {TABLE} (
    region        VARCHAR(10) NOT NULL PRIMARY KEY COMMENT '시도명',
    eco_count     INT          COMMENT '친환경(전기·수소·하이브리드) 등록 대수',
    eco_total     INT          COMMENT '연료기준 전체 등록 대수',
    eco_ratio     DECIMAL(5,2) COMMENT '친환경 비율 (%)',
    large_count   INT          COMMENT '대형 승용차 등록 대수',
    large_total   INT          COMMENT '승용차 전체 등록 대수',
    large_ratio   DECIMAL(5,2) COMMENT '대형 승용차 비율 (%)',
    female_count  INT          COMMENT '여성 명의 등록 대수',
    male_count    INT          COMMENT '남성 명의 등록 대수',
    female_ratio  DECIMAL(5,2) COMMENT '여성 비율 (%, 기타 제외)',
    import_count  INT          COMMENT '수입차 등록 대수',
    import_total  INT          COMMENT '전체 등록 대수',
    import_ratio  DECIMAL(5,2) COMMENT '수입차 비율 (%)',
    persona_code  CHAR(4) NOT NULL COMMENT 'Car-BTI 4글자: [E/G][L/S][F/M][I/D]',
    INDEX idx_persona (persona_code)
) ENGINE=InnoDB CHARACTER SET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='시도별 자동차 등록 통계 + Car-BTI 페르소나 코드';
"""

INSERT_SQL = f"""
INSERT INTO {TABLE} (
    region, eco_count, eco_total, eco_ratio,
    large_count, large_total, large_ratio,
    female_count, male_count, female_ratio,
    import_count, import_total, import_ratio,
    persona_code
) VALUES (
    %s, %s, %s, %s,
    %s, %s, %s,
    %s, %s, %s,
    %s, %s, %s,
    %s
);
"""

INSERT_COLS = [
    "region", "eco_count", "eco_total", "eco_ratio",
    "large_count", "large_total", "large_ratio",
    "female_count", "male_count", "female_ratio",
    "import_count", "import_total", "import_ratio",
    "persona_code",
]


def main():
    if not os.path.exists(CSV_PATH):
        print(f"❌ CSV 파일이 없습니다: {CSV_PATH}")
        print("   → 먼저 prepare_data.py 를 실행하세요.")
        sys.exit(1)

    df = pd.read_csv(CSV_PATH)
    print(f"📂 CSV 로드: {len(df)}개 시도 ({CSV_PATH})")

    try:
        conn = pymysql.connect(**MYSQL_CONFIG)
        print(f"🔌 MySQL 연결 성공: "
              f"{MYSQL_CONFIG['user']}@{MYSQL_CONFIG['host']}:{MYSQL_CONFIG['port']}"
              f"/{MYSQL_CONFIG['database']}")
    except pymysql.MySQLError as e:
        print(f"❌ MySQL 연결 실패: {e}")
        print("   → MYSQL_CONFIG / DB 생성 / pymysql 설치 여부를 확인하세요.")
        sys.exit(1)

    try:
        with conn.cursor() as cur:
            cur.execute(DDL_DROP)
            cur.execute(DDL_CREATE)
            print(f"✅ 테이블 재생성: {TABLE}")

            rows = df[INSERT_COLS].values.tolist()
            cur.executemany(INSERT_SQL, rows)
            print(f"✅ INSERT 완료: {cur.rowcount}건")

        conn.commit()

        with conn.cursor() as cur:
            print("\n🔍 검증 1) 시도별 페르소나 코드:")
            cur.execute(
                f"SELECT region, eco_ratio, large_ratio, female_ratio, "
                f"import_ratio, persona_code FROM {TABLE} ORDER BY region"
            )
            print(f"   {'region':<6}{'eco%':>8}{'large%':>10}{'female%':>10}"
                  f"{'import%':>10}{'persona':>10}")
            for row in cur.fetchall():
                r, e, l, f, i, p = row
                print(f"   {r:<6}{e:>8}{l:>10}{f:>10}{i:>10}{p:>10}")

            print("\n🔍 검증 2) 페르소나 코드 분포:")
            cur.execute(
                f"SELECT persona_code, COUNT(*) AS cnt FROM {TABLE} "
                f"GROUP BY persona_code ORDER BY cnt DESC, persona_code"
            )
            for p, c in cur.fetchall():
                print(f"   {p} : {c}개 시도")

    finally:
        conn.close()

    print("\n🎉 적재 완료!")
    print("   DBeaver 에서 다음 쿼리로 확인:")
    print(f"   SELECT * FROM {TABLE} ORDER BY region;")


if __name__ == "__main__":
    main()