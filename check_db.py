"""DB 적재 상태 빠른 점검 스크립트.  실행:  python check_db.py"""
import os
import pymysql

conn = pymysql.connect(
    host=os.getenv("MYSQL_HOST", "localhost"),
    port=int(os.getenv("MYSQL_PORT", "3306")),
    user=os.getenv("MYSQL_USER", "root"),
    password=os.getenv("MYSQL_PASSWORD", "1234"),
    database=os.getenv("MYSQL_DATABASE", "car_bti"),
    charset="utf8mb4",
)
cur = conn.cursor()

print("=" * 50)
print(" [1] 테이블 목록")
cur.execute("SHOW TABLES")
for (t,) in cur.fetchall():
    cur.execute(f"SELECT COUNT(*) FROM `{t}`")
    print(f"   - {t}: {cur.fetchone()[0]} rows")

print("=" * 50)
print(" [2] 차량 이미지 적재 현황 (persona_cars)")
cur.execute(
    "SELECT COUNT(*), "
    "SUM(img_data IS NOT NULL AND LENGTH(img_data) > 2000) "
    "FROM persona_cars"
)
total, with_img = cur.fetchone()
print(f"   전체 차량 {total}대 중 이미지 보유 {with_img}대")

print("=" * 50)
print(" [3] FAQ 기업별 건수 (company_faq)")
cur.execute("SELECT company, COUNT(*) FROM company_faq GROUP BY company ORDER BY 2 DESC")
for comp, n in cur.fetchall():
    print(f"   - {comp}: {n}")

print("=" * 50)
print(" [4] 제네시스 크롤링 FAQ 샘플 3건")
cur.execute(
    "SELECT question, LEFT(answer, 50) FROM company_faq "
    "WHERE company='제네시스' LIMIT 3"
)
for q, a in cur.fetchall():
    print(f"   Q. {q}")
    print(f"      A. {a}...")

cur.close()
conn.close()
print("=" * 50)
print(" 점검 완료 ✅")
