"""
faq_fallback.py
===============
공식 FAQ 크롤링이 불가능한 브랜드(403/timeout/404)용 대표 FAQ 시드.

크롤링 0건일 때 crawl_brand_faq.py 가 자동으로 적재한다.
"""

from crawler.faq_common import auto_tag, categorize, clean

# (company, question, answer) — category/tags는 자동 부여
_RAW = [
    # 벤츠
    (
        "벤츠",
        "벤츠 C-Class와 E-Class 차이는?",
        "C-Class는 준중형(6,200만원~), E-Class는 중형(7,500만원~)으로 크기·가격·포지션이 다릅니다.",
    ),
    (
        "벤츠",
        "벤츠 정기점검 주기는?",
        "ASSYST Plus 시스템으로 주행거리·시간 기반 점검 알림을 제공합니다. 보통 1.5~2만km 간격입니다.",
    ),
    (
        "벤츠",
        "벤츠 공식 인증 중고차 구매 시 혜택은?",
        "Mercedes-Benz Certified 중고는 158항목 점검·최대 24개월 보증·로드사이드 서비스가 포함됩니다.",
    ),
    (
        "벤츠",
        "벤츠 EQB와 GLC 중 어떤 차가 나을까요?",
        "EQB는 전기 SUV로 도심·출퇴근에, GLC는 내연기관 중형 SUV로 장거리·패밀리에 강점이 있습니다.",
    ),
    # 테슬라
    (
        "테슬라",
        "테슬라 Supercharger 이용 방법은?",
        "테슬라 앱에서 충전소를 검색하고, 차량에 등록된 결제 수단으로 자동 결제됩니다.",
    ),
    (
        "테슬라",
        "테슬라 Model 3 배터리 수명은?",
        "일반적으로 8~10년/20만km 이상 사용 가능하며, 보증은 8년/16만km(표준 배터리)입니다.",
    ),
    (
        "테슬라",
        "테슬라 Model Y 실내 공간은 가족용으로 충분한가요?",
        "5인승 SUV로 넓은 트렁크와 접이식 시트를 지원해 패밀리카·레저용으로 인기가 많습니다.",
    ),
    # 볼보
    (
        "볼보",
        "볼보 XC60 안전 사양은?",
        "City Safety(자동긴급제동), Lane Keeping Aid, Blind Spot 등 기본 안전 사양이 풍부합니다.",
    ),
    (
        "볼보",
        "볼보 정비는 어디서 받나요?",
        "전국 볼보 공식 서비스센터 및 인증 협력 정비소에서 받을 수 있습니다. Care by Volvo 구독 시 정비 포함.",
    ),
    (
        "볼보",
        "볼보 XC40 Recharge 충전은 어떻게 하나요?",
        "완속(가정용)·급속(공공 충전소) 모두 지원하며, 볼보 앱 또는 충전 앱으로 충전소를 검색할 수 있습니다.",
    ),
    # 아우디
    (
        "아우디",
        "아우디 A3와 Q3 중 어떤 차를 선택할까요?",
        "A3는 세단/해치백 도심형, Q3는 SUV 실용성에 강점이 있습니다.",
    ),
    (
        "아우디",
        "아우디 공식 인증 중고차(Audi Approved)란?",
        "아우디 공식 110항목 점검·최소 12개월 보증·사고 이력 투명 공개가 특징입니다.",
    ),
    (
        "아우디",
        "아우디 Q4 e-tron 배터리 보증은?",
        "신차 기준 배터리 8년/16만km 보증이 적용됩니다. 중고 구매 시 잔여 보증 기간을 확인하세요.",
    ),
    # 쉐보레
    (
        "쉐보레",
        "쉐보레 볼트 EUV 충전 방법은?",
        "완속(가정용)·급속(공공 충전소) 모두 지원하며, 충전소 앱으로 위치 검색이 가능합니다.",
    ),
    (
        "쉐보레",
        "쉐보레 볼트 EUV 배터리 보증 기간은?",
        "신차 기준 8년/16만km 배터리 보증이 적용됩니다. 공식 서비스센터에서 잔여 보증을 확인할 수 있습니다.",
    ),
]

FALLBACK_BRANDS = frozenset({"벤츠", "테슬라", "볼보", "아우디", "쉐보레"})


def get_fallback_rows(company: str) -> list[tuple]:
    """브랜드별 대표 FAQ → (company, category, question, answer, persona_tags)"""
    rows = []
    for comp, question, answer in _RAW:
        if comp != company:
            continue
        q, a = clean(question), clean(answer)
        rows.append((comp, categorize(q, a), q, a, auto_tag(q, a, comp)))
    return rows
