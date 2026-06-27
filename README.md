# SKN34-1st-3Team

3팀
김대호
노민환
이홍규
전진영

---

## 전국 Car-BTI 대시보드

지역별 자동차 소비 성향을 MBTI 형식의 4축(총 16유형)으로 표현하는 Streamlit 대시보드입니다.

### Car-BTI 4축


| 축   | 코드  | 의미               | 코드  | 의미    |
| --- | --- | ---------------- | --- | ----- |
| 친환경 | `E` | 친환경(전기/수소/하이브리드) | `G` | 내연기관  |
| 크기  | `L` | 대형/SUV           | `S` | 소형/세단 |
| 성별  | `F` | 여성 강세            | `M` | 남성 강세 |
| 국·외 | `I` | 수입               | `D` | 국산    |


> 페르소나 코드 4자리 순서: `[E/G][L/S][F/M][I/D]`
> 예) `GSMI` = 내연기관 · 소형/세단 · 남성 · 수입 → BMW 3시리즈, 벤츠 C-Class, 아우디 A3, 볼보 S60

### 데이터 저장소

모든 데이터는 **MySQL**(`car_bti` DB)에 적재됩니다.

- `region_stats` — 국토부 자동차 등록 통계(xlsx)에서 추출한 **시도별 실제 4축 비율 + persona_code** (`prepare_data.py` → `load_to_mysql.py`)
- `persona_cars` — 16유형 × 4대(=64) 추천 차량 + 차량 이미지 BLOB
- `company_faq` — 브랜드/K Car FAQ (크롤링 우선, 일부 해외 브랜드는 대표 FAQ 시드)

### 사전 준비 — MySQL 접속 정보

프로젝트 루트에 `.env` 파일을 만듭니다(`.env.example` 참고). `db_config.py`가 자동으로 읽습니다.

```
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=본인비밀번호
MYSQL_DATABASE=car_bti
```

MySQL에 DB가 없으면 먼저 생성:

```sql
CREATE DATABASE car_bti CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 설치 & 실행

```powershell
pip install -r requirements.txt

# 1) 지역 통계 적재 (국토부 xlsx → CSV → MySQL region_stats)
python prepare_data.py
python load_to_mysql.py

# 2) 추천 차량 시드 (persona_cars, company_faq 테이블 생성)
python setup_db.py

# 3) 브랜드 공식 FAQ 크롤링 → MySQL (현대·기아·제네시스 API/HTML, BMW·MINI Salesforce 등)
python crawler/crawl_brand_faq.py

# 4) K Car 옥션 FAQ 크롤링 (Chrome 필요)
python crawler/crawl_faq.py

# 5) 차량 이미지 크롤링 → MySQL 적재 (누락분만, 전체 재수집은 인자 all)
python crawler/crawl_car_images.py

# 6) 대시보드 실행
streamlit run app.py
```

### MySQL 테이블

- `region_stats` — 시도별 등록 통계 + persona_code (`prepare_data.py`+`load_to_mysql.py`가 소유)
- `persona_cars` — 16유형 × 4대(=64) 추천 차량 (`img_data` LONGBLOB에 크롤링 이미지 저장)
- `company_faq` — 브랜드/맞춤형 FAQ (`company` 기준으로 추천 차량 기업 FAQ 연동)

### FAQ 데이터 출처

| 기업 | 크롤러 | 수집 방식 | 대략적 규모 |
| --- | --- | --- | --- |
| 제네시스 | `crawl_brand_faq.py` | 공식 FAQ HTML | ~230건 |
| 현대 | `crawl_brand_faq.py` | 고객센터 FAQ REST API | ~280건 |
| 기아 | `crawl_brand_faq.py` | FAQ 검색 API | ~220건 |
| BMW | `crawl_brand_faq.py` | Salesforce FAQ 포털 (Selenium) | ~5건 |
| 미니 | `crawl_brand_faq.py` | Salesforce FAQ 포털 (Selenium) | ~5건 |
| K Car 옥션 | `crawl_faq.py` | K Car FAQ 페이지 (Selenium) | 8건 (사이트 전체) |
| **벤츠·테슬라·볼보·아우디·쉐보레** | `crawl_brand_faq.py` | 크롤링 시도 → **실패 시 시드** | 각 2~4건 |

### 크롤링 불가 브랜드 (벤츠·테슬라·볼보·아우디·쉐보레)

아래 5개 브랜드는 **공식 FAQ 페이지에 자동 접근이 차단**되어 크롤링으로는 수집할 수 없습니다.

| 브랜드 | 시도 URL (예) | 차단 유형 |
| --- | --- | --- |
| 벤츠 | `mercedes-benz.co.kr` FAQ | 404 / timeout |
| 테슬라 | `tesla.com/ko_KR/support` | **403 Access Denied** |
| 볼보 | `volvocars.com/kr/support` | **403 Access Denied** |
| 아우디 | `audi.co.kr` FAQ | **503** / timeout |
| 쉐보레 | `chevrolet.co.kr` FAQ | 404 / Access Denied |

`requests`와 Selenium(Chrome) 모두 시도했으나 FAQ 본문을 가져오지 못했습니다.  
따라서 `crawler/faq_fallback.py`에 **대표 FAQ 시드**를 두었고, `crawl_brand_faq.py` 실행 시 크롤링 결과가 0건이면 자동으로 DB에 적재합니다.

```
[BRAND] 벤츠 크롤링 중...
  [FALLBACK] 벤츠: 크롤링 불가 → 대표 FAQ 4건 적재
```

> 공식 FAQ URL/API가 열리면 `crawl_brand_faq.py`의 `BRAND_CRAWLERS`에 크롤러를 추가하면 시드 대신 실시간 수집으로 전환됩니다.


> 차량 이미지는 전 브랜드 위키피디아 크롤링(`crawl_car_images.py`)으로 MySQL에 적재됩니다.

### 크롤링 데이터가 Streamlit에서 보이는 위치

크롤러가 MySQL에 적재한 데이터는 대시보드에서 다음과 같이 노출됩니다.


| 크롤링 데이터                   | 적재 위치                                         | 화면에서 보이는 곳     | 표시 방식                                      |
| ------------------------- | --------------------------------------------- | -------------- | ------------------------------------------ |
| 차량 이미지 (위키피디아)            | `persona_cars.img_data` (BLOB)                | "완벽한 매칭 차량" 카드 | 추천 차량 4대의 사진으로 표시 (64대 전부 보유)              |
| 제네시스 공식 FAQ | `company_faq` (`company='제네시스'`) | "페르소나 매칭 FAQ" | 제네시스 추천 페르소나에서 노출 |
| K Car 옥션 FAQ | `company_faq` (`company='K Car 옥션'`) | "페르소나 매칭 FAQ" | 페르소나 3축 이상 일치 시 보조 노출 |
| 현대·기아·제네시스·BMW·미니 FAQ | `company_faq` | "페르소나 매칭 FAQ" | 추천 브랜드별 라운드로빈 노출 |
| 벤츠·테슬라·볼보·아우디·쉐보레 FAQ | `company_faq` (크롤링 실패 시 `faq_fallback.py` 시드) | "페르소나 매칭 FAQ" | 해당 수입차 추천 페르소나에서 노출 |


**FAQ 표시 규칙**

- 한 페르소나 화면에는 FAQ가 **최대 6개**(`top_n=6`)만 표시됩니다.
- 추천 차량 **기업별 라운드로빈** 정렬이라, 현대·기아·제네시스가 번갈아 노출됩니다.
(따라서 제네시스 232건이 한 화면에 모두 뜨는 것이 아니라, DB에 전량 저장된 상태에서 페르소나별로 상위 일부만 노출)
- 적재 전수 확인은 `python check_db.py` 또는 MySQL Workbench/DBeaver로 가능합니다.

### 트러블슈팅

개발 중 실제로 겪은 이슈와 해결 방법입니다.


| 증상                                                                   | 원인                                                    | 해결                                                                     |
| -------------------------------------------------------------------- | ----------------------------------------------------- | ---------------------------------------------------------------------- |
| `TypeError: image() got an unexpected keyword 'use_container_width'` | Streamlit 1.32에는 `use_container_width` 미지원 (1.43+ 부터) | `st.image(..., use_column_width=True)` 로 변경                            |
| `No secrets files found` 경고 반복                                       | `secrets.toml` 없이 `st.secrets` 접근                     | `db_config.py`에서 `secrets.toml` 존재 여부를 먼저 확인 후 접근                      |
| `ModuleNotFoundError: No module named 'sqlalchemy'`                  | DB 커넥터 미설치                                            | `pip install -r requirements.txt` (PyMySQL·SQLAlchemy·cryptography 포함) |
| 차량 이미지가 1KB대 깨진 placeholder로 저장됨                                     | 위키 원본/썸네일 응답이 빈 이미지                                   | 500px 업스케일 우선 시도 + 실패 시 원본 폴백, `len < 2000` 바이트는 폐기                    |
| 이미지 크롤링 중 `429 Too Many Requests` / `ReadTimeout`                    | `upload.wikimedia.org` 레이트리밋                          | 재시도 3회 + 백오프, `Referer` 헤더 추가, 요청 간 1초 sleep                           |
| 현대·기아 FAQ 크롤링 | 고객센터 REST API (`hyundai.com/kr/ko/gw/...`, `kia.com/.../faq.search`) | `crawl_brand_faq.py`에서 API 크롤링으로 전환 |
| 해외 브랜드(벤츠·테슬라·볼보·아우디·쉐보레) FAQ 크롤링 실패 | 공식 사이트 403/timeout/404 | `faq_fallback.py` 대표 FAQ 시드 자동 적재 (`[FALLBACK]` 로그) |
| MySQL 한글 깨짐                                                          | 기본 charset 불일치                                        | 커넥션/테이블을 `utf8mb4`로 통일                                                 |
| `region_stats 로드 실패/비어있음` 에러로 앱 중단                                   | region_stats 미적재                                      | `python prepare_data.py` → `python load_to_mysql.py` 먼저 실행             |
| 성별 축 코드 불일치(`W` vs `F`)                                              | 팀 저장소는 `F/M`(F=여성), 초기 버전은 `M/W`                      | 전 코드/데이터를 팀 기준 `F/M`으로 통일 (여성=`F`)                                     |


