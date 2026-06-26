"""
app.py
======
전국 Car-BTI 대시보드 (v2)

기능 요약
---------
[Tab 1] 🗺️ 지역 분석
  ① 지도 시각화 4축 토글 (전기차/SUV/평균가/수입차)
  ② 16색 페르소나 모드
  ③ 레이더 차트로 선택 지역의 4축 점수 한눈에
  ⑤ 페르소나 매칭도 기반 FAQ 정렬
  ⑤ 페르소나 4자리에 맞춘 추천 차량 4종 카드

[Tab 2] 🧪 나의 Car-BTI 테스트
  ④ 4문항 설문 → 본인 페르소나 산출
     → 가장 비슷한 지역 Top 3 / 추천 차량 / 매칭 FAQ Top 3
"""

import os
import sqlite3

import folium
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
from streamlit_folium import st_folium

# ════════════════════════════════════════
# 페이지 설정 & 상수
# ════════════════════════════════════════
st.set_page_config(page_title="전국 Car-BTI 대시보드", page_icon="🗺️", layout="wide")
DB_PATH = "db/car_bti.db"

AXIS_LABELS = {
    "E": ("⚡", "친환경 (Eco)"),
    "G": ("⛽", "내연기관 (Gasoline)"),
    "L": ("🏕️", "대형/SUV (Large)"),
    "S": ("🏙️", "소형/세단 (Small)"),
    "P": ("💎", "프리미엄 (Premium)"),
    "B": ("💰", "가성비 (Budget)"),
    "I": ("🌍", "수입 (Import)"),
    "D": ("🇰🇷", "국산 (Domestic)"),
}

AXIS_DESC = {
    "E": "전기차 등 친환경 차량 보급률이 높고 인프라가 잘 갖춰진 지역",
    "G": "내연기관 차량의 비중이 높고 익숙함을 선호하는 지역",
    "L": "험지/캠핑/다목적 공간을 위한 SUV·대형차 선호도가 높은 지역",
    "S": "주차와 도심 주행에 유리한 세단·중소형차를 선호하는 지역",
    "P": "평균 구매가가 상대적으로 높아 최신 트렌드·고급 브랜드를 선호하는 지역",
    "B": "차량 구매 시 경제성·가성비를 가장 먼저 고려하는 합리적 소비 지역",
    "I": "해외 브랜드 차량 등록 비중이 높은 지역",
    "D": "현대·기아 등 국산 브랜드 비중이 높은 실용적 지역",
}

# ② 16색 페르소나 색상 (E계열=녹색, G계열=주황/빨강)
PERSONA_COLORS = {
    "ESBD": "#a7f3d0", "ESBI": "#6ee7b7", "ESPD": "#34d399", "ESPI": "#10b981",
    "ELBD": "#bbf7d0", "ELBI": "#86efac", "ELPD": "#22c55e", "ELPI": "#15803d",
    "GSBD": "#fed7aa", "GSBI": "#fdba74", "GSPD": "#fb923c", "GSPI": "#f97316",
    "GLBD": "#fecaca", "GLBI": "#fca5a5", "GLPD": "#f87171", "GLPI": "#dc2626",
}

# 지도 시각화 모드
VIZ_MODES = {
    "⚡ 친환경 (전기차 보급률)": ("ev_ratio", "YlGn", "전기차 보급률 (%)"),
    "🚙 대형/SUV (SUV 비율)": ("suv_ratio", "Oranges", "SUV 비율 (%)"),
    "💎 프리미엄 (평균 구매가)": ("avg_price", "Purples", "평균 구매가 (만원)"),
    "🌍 수입차 비중": ("import_ratio", "Blues", "수입차 비율 (%)"),
    "🌈 16색 페르소나": (None, None, None),
}


# ════════════════════════════════════════
# 데이터 로딩
# ════════════════════════════════════════
@st.cache_data
def load_map_data():
    geojson_url = (
        "https://raw.githubusercontent.com/southkorea/southkorea-maps/"
        "master/kostat/2013/json/skorea_provinces_geo_simple.json"
    )
    geojson_data = requests.get(geojson_url).json()

    data = {
        "region": ["서울특별시", "부산광역시", "대구광역시", "인천광역시", "광주광역시",
                   "대전광역시", "울산광역시", "세종특별자치시", "경기도", "강원도",
                   "충청북도", "충청남도", "전라북도", "전라남도", "경상북도",
                   "경상남도", "제주특별자치도"],
        "ev_ratio":      [2.1, 6.7, 2.5, 2.0, 1.9, 8.2, 1.7, 3.5, 2.3, 4.7, 1.6, 3.8, 7.2, 1.9, 1.6, 1.5, 2.5],
        "suv_ratio":     [38, 45, 42, 48, 46, 44, 47, 50, 49, 55, 53, 52, 51, 54, 56, 52, 45],
        "import_ratio":  [25.5, 21.0, 22.5, 20.5, 15.2, 17.8, 16.4, 18.5, 23.0, 12.5, 14.2, 13.8, 12.9, 11.5, 13.0, 14.5, 19.5],
        "avg_price":     [6500, 4200, 4500, 4700, 4600, 4600, 5000, 5200, 5100, 4200, 4300, 4400, 4100, 4000, 4300, 4500, 4800],
    }
    df = pd.DataFrame(data)

    def calc_bti(row):
        e = "E" if row["ev_ratio"]     >= 3.0   else "G"
        l = "L" if row["suv_ratio"]    >= 50.0  else "S"
        p = "P" if row["avg_price"]    >= 5000  else "B"
        i = "I" if row["import_ratio"] >= 20.0  else "D"
        return f"{e}{l}{p}{i}"

    df["persona_type"] = df.apply(calc_bti, axis=1)
    return geojson_data, df


@st.cache_data
def load_db():
    """DB에서 FAQ + 추천 차량 로드. 없으면 빈 DF."""
    if not os.path.exists(DB_PATH):
        return pd.DataFrame(), pd.DataFrame()
    conn = sqlite3.connect(DB_PATH)
    try:
        faq = pd.read_sql("SELECT * FROM company_faq", conn)
    except Exception:
        faq = pd.DataFrame()
    try:
        cars = pd.read_sql("SELECT * FROM persona_cars", conn)
    except Exception:
        cars = pd.DataFrame()
    conn.close()
    return faq, cars


geojson_data, df_stats = load_map_data()
faq_df, cars_df = load_db()


# ════════════════════════════════════════
# 유틸리티
# ════════════════════════════════════════
def match_score(persona: str, tags: str) -> float:
    """
    v2.1: 페르소나 ↔ FAQ 태그 매칭도 (베이스라인 + 직접 매칭).

    공식: base(15%) + 매칭 자리수 × 25%, 최대 100%
      0자리 매칭 → 15%  (모든 FAQ는 자동차 관련이라 최소 베이스 보장)
      1자리 매칭 → 40%
      2자리 매칭 → 65%
      3자리 매칭 → 90%
      4자리 매칭 → 100%
    """
    BASE = 0.15
    if not tags or pd.isna(tags):
        return BASE
    p_set = set(persona)
    t_set = {t.strip() for t in tags.split(",")}
    overlap = len(p_set & t_set)
    return min(BASE + overlap * 0.25, 1.0)


def overlap_chars(persona: str, tags: str) -> str:
    if not tags or pd.isna(tags):
        return ""
    return ",".join(sorted(set(persona) & {t.strip() for t in tags.split(",")}))


def make_radar(region: str, row) -> go.Figure:
    """③ 4축 점수 레이더 차트."""
    eco  = min(row["ev_ratio"] / 8.0 * 100, 100)
    suv  = row["suv_ratio"]
    prem = max(0, min((row["avg_price"] - 3500) / 30, 100))   # 3500~6500 → 0~100
    imp  = min(row["import_ratio"] / 30 * 100, 100)

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=[eco, suv, prem, imp, eco],
        theta=["⚡친환경", "🚙SUV/대형", "💎프리미엄", "🌍수입차", "⚡친환경"],
        fill="toself",
        name=region,
        line_color="#3b82f6",
        fillcolor="rgba(59, 130, 246, 0.25)",
    ))
    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 100], showticklabels=False),
            angularaxis=dict(tickfont=dict(size=13)),
        ),
        showlegend=False,
        height=320,
        margin=dict(t=20, b=20, l=40, r=40),
    )
    return fig


def persona_desc_html(persona: str) -> str:
    parts = []
    for c in persona:
        emoji, label = AXIS_LABELS[c]
        parts.append(f"{emoji} <b>{label}</b> — {AXIS_DESC[c]}<br>")
    return "".join(parts)


def render_recommended_cars(persona: str, cars: pd.DataFrame):
    """페르소나의 4자리에 매칭되는 차량 4종 카드 표시."""
    if cars.empty:
        st.warning("⚠️ persona_cars 가 비어있습니다. `python setup_db.py` 를 먼저 실행해주세요.")
        return
    cols = st.columns(4)
    for i, axis in enumerate(persona):
        emoji, label = AXIS_LABELS[axis]
        sub = cars[cars["persona_axis"] == axis]
        if sub.empty:
            continue
        # 자리수마다 다른 차량이 나오도록 인덱스 분산
        car = sub.iloc[i % len(sub)]
        with cols[i]:
            st.markdown(f"##### {emoji} {label} ({axis})")
            # 차량 이미지 (향후 추가 예정)
            st.markdown(
                "<div style='height:100px;background:#f0f4f8;border-radius:6px;"
                "display:flex;align-items:center;justify-content:center;color:#64748b;"
                "font-size:12px;margin-bottom:6px;text-align:center;padding:8px'>"
                "🚗<br/><span style=\"font-size:11px\">사진은 발표 시<br/>추가될 예정입니다</span>"
                "</div>",
                unsafe_allow_html=True,
            )
            st.markdown(f"### {car['brand']} {car['car_model']}")
            st.caption(f"💸 {car['price']}")
            st.write(car["reason"])


def render_faq_list(persona: str, faq: pd.DataFrame, top_n: int = None):
    """매칭도 기반 정렬 + 시각화로 FAQ 표시."""
    if faq.empty:
        st.warning("⚠️ FAQ 가 비어있습니다. `python crawler/crawl_faq.py` 를 실행해주세요.")
        return
    if "persona_tags" not in faq.columns:
        st.warning("⚠️ persona_tags 컬럼이 없습니다. setup_db.py / crawl_faq.py 를 v2로 다시 실행해주세요.")
        for _, row in faq.iterrows():
            with st.expander(f"Q. {row['question']}"):
                st.write(row["answer"])
        return

    scored = faq.copy()
    scored["_score"]   = scored["persona_tags"].apply(lambda t: match_score(persona, t))
    scored["_overlap"] = scored["persona_tags"].apply(lambda t: overlap_chars(persona, t))
    scored = scored.sort_values("_score", ascending=False)
    if top_n:
        scored = scored.head(top_n)

    for _, row in scored.iterrows():
        pct = int(row["_score"] * 100)
        ov  = row["_overlap"]
        badge = f"🎯 매칭 {pct}%"
        if ov:
            badge += f" · 일치 자리: {ov}"
        with st.expander(f"{badge}  |  Q. {row['question']}"):
            st.progress(row["_score"], text=f"페르소나 [{persona}] 와 매칭도 {pct}%")
            st.write(row["answer"])
            st.caption(f"카테고리: {row['car_category']} · 페르소나 태그: {row['persona_tags']}")


# ════════════════════════════════════════
# 세션 상태
# ════════════════════════════════════════
if "selected_region" not in st.session_state:
    st.session_state.selected_region = "서울특별시"


def on_region_input():
    user_input = st.session_state.get("region_input", "").strip()
    if not user_input:
        return
    for r in df_stats["region"].values:
        if user_input[:2] in r:
            st.session_state.selected_region = r
            return


# ════════════════════════════════════════
# 헤더 & 탭
# ════════════════════════════════════════
st.title("🗺️ 전국 지역별 자동차 소비 성향 (Car-BTI) 분석")
st.caption(
    "지도를 클릭하거나 지역명을 입력해 4자리 Car-BTI를 확인해보세요. "
    "두 번째 탭에서는 나만의 Car-BTI를 직접 진단할 수 있습니다."
)

# ── Car-BTI 4축 설명 (MBTI 처럼 4개 축의 조합) ──
with st.expander("🧬 Car-BTI 가 처음이신가요? — 4가지 축 설명 보기", expanded=False):
    st.markdown(
        "Car-BTI는 **MBTI 처럼 4가지 축의 조합 (총 16가지 유형)** 으로 자동차 소비 성향을 표현합니다. "
        "각 자리수는 서로 반대되는 성향 중 하나를 나타냅니다."
    )
    axis_cols = st.columns(4)
    axis_pairs = [
        ("⚡", "E", "친환경",     "⛽", "G", "내연기관"),
        ("🏕️", "L", "대형/SUV",  "🏙️", "S", "소형/세단"),
        ("💎", "P", "프리미엄",   "💰", "B", "가성비"),
        ("🌍", "I", "수입",       "🇰🇷", "D", "국산"),
    ]
    for i, (e1, c1, l1, e2, c2, l2) in enumerate(axis_pairs):
        with axis_cols[i]:
            st.markdown(
                f"<div style='border:1px solid #e2e8f0;border-radius:8px;padding:14px;text-align:center;background:#f8fafc'>"
                f"<div style='font-size:22px'>{e1}</div>"
                f"<div style='font-weight:bold;font-size:18px;font-family:monospace'>{c1}</div>"
                f"<div style='color:#475569;font-size:13px;margin-bottom:8px'>{l1}</div>"
                f"<div style='color:#94a3b8;font-size:18px;margin:4px 0'>↕</div>"
                f"<div style='color:#475569;font-size:13px;margin-top:8px'>{l2}</div>"
                f"<div style='font-weight:bold;font-size:18px;font-family:monospace'>{c2}</div>"
                f"<div style='font-size:22px'>{e2}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
    st.markdown(
        "<div style='margin-top:14px;padding:10px;background:#eff6ff;border-radius:6px;font-size:14px'>"
        "📌 <b>예시</b> &nbsp;&nbsp; <code>GSPI</code> = 내연기관(G) + 소형/세단(S) + 프리미엄(P) + 수입차(I) → "
        "<b>서울특별시 스타일</b> · 도심 출퇴근에 고급 수입 세단을 타는 성향"
        "</div>",
        unsafe_allow_html=True,
    )

st.divider()

tab1, tab2 = st.tabs(["🗺️ 지역 분석", "🧪 나의 Car-BTI 테스트"])


# ════════════════════════════════════════
# Tab 1: 지역 분석
# ════════════════════════════════════════
with tab1:
    # ── ① 지도 시각화 토글 ──
    viz_mode = st.radio(
        "🎨 지도 시각화 기준",
        list(VIZ_MODES.keys()),
        horizontal=True,
        key="viz_mode",
    )

    col_map, col_info = st.columns([5, 5])

    # ── 지도 ──
    with col_map:
        st.subheader("📍 전국 Car-BTI 지도")

        m = folium.Map(location=[36.5, 127.5], zoom_start=7, tiles="CartoDB positron")
        col, palette, label = VIZ_MODES[viz_mode]

        if col is None:  # 🌈 16색 페르소나 모드
            persona_map = dict(zip(df_stats["region"], df_stats["persona_type"]))

            def style_fn(feature):
                name = feature["properties"]["name"]
                # geojson 의 region 이름 변형에 대비 (앞 2글자로 매칭)
                p = None
                for r, pp in persona_map.items():
                    if r.startswith(name[:2]) or name.startswith(r[:2]):
                        p = pp
                        break
                color = PERSONA_COLORS.get(p, "#cccccc")
                return {"fillColor": color, "fillOpacity": 0.75, "color": "#666", "weight": 1}

            folium.features.GeoJson(
                geojson_data,
                style_function=style_fn,
                tooltip=folium.features.GeoJsonTooltip(fields=["name"], aliases=["지역:"]),
            ).add_to(m)
        else:
            folium.Choropleth(
                geo_data=geojson_data,
                data=df_stats,
                columns=["region", col],
                key_on="feature.properties.name",
                fill_color=palette,
                fill_opacity=0.7,
                line_opacity=0.3,
                legend_name=label,
            ).add_to(m)
            folium.features.GeoJson(
                geojson_data,
                style_function=lambda x: {"fillColor": "transparent", "color": "transparent"},
                tooltip=folium.features.GeoJsonTooltip(fields=["name"], aliases=["지역:"]),
            ).add_to(m)

        map_data = st_folium(m, width=600, height=500, key=f"map_{viz_mode}")
        if map_data and map_data.get("last_active_drawing"):
            clicked = map_data["last_active_drawing"]["properties"]["name"]
            for r in df_stats["region"].values:
                if r.startswith(clicked[:2]) or clicked.startswith(r[:2]):
                    st.session_state.selected_region = r
                    break

        # 16색 모드 범례
        if col is None:
            with st.expander("🎨 16색 페르소나 범례"):
                legend_cols = st.columns(4)
                for i, (p, c) in enumerate(PERSONA_COLORS.items()):
                    with legend_cols[i % 4]:
                        st.markdown(
                            f"<div style='display:flex;align-items:center;gap:6px;padding:2px 0'>"
                            f"<div style='width:16px;height:16px;background:{c};"
                            f"border:1px solid #555;border-radius:3px'></div>"
                            f"<span style='font-family:monospace;font-size:13px'>{p}</span>"
                            f"</div>",
                            unsafe_allow_html=True,
                        )

    # ── 분석 패널 ──
    with col_info:
        st.subheader("🔍 지역 분석")
        st.text_input(
            "거주하시거나 궁금한 지역을 입력하세요 (예: 서울, 부산, 강원도)",
            key="region_input",
            on_change=on_region_input,
        )

        selected = st.session_state.selected_region
        region_data = df_stats[df_stats["region"] == selected].iloc[0]
        persona = region_data["persona_type"]
        p_color = PERSONA_COLORS.get(persona, "#888")

        # 페르소나 배지
        st.markdown(
            f"<div style='padding:14px;background:{p_color}33;"
            f"border-left:6px solid {p_color};border-radius:6px;margin-bottom:10px'>"
            f"<div style='font-size:14px;color:#666'>🎯 {selected}의 Car-BTI</div>"
            f"<div style='font-size:28px;font-weight:bold;letter-spacing:4px'>[ {persona} ]</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

        # ③ 레이더 차트
        st.plotly_chart(make_radar(selected, region_data), use_container_width=True)

        # 페르소나 설명
        with st.expander("📖 페르소나 4축 상세 설명", expanded=True):
            st.markdown(persona_desc_html(persona), unsafe_allow_html=True)

        # 통계 요약 (기존)
        with st.expander("📊 차량 통계 요약"):
            st.progress(min(int(region_data["ev_ratio"] * 10), 100),
                        text=f"⚡ 전기차 비율: {region_data['ev_ratio']}%")
            st.progress(int(region_data["suv_ratio"]),
                        text=f"🚙 SUV/레저용 비율: {region_data['suv_ratio']}%")
            st.progress(int(region_data["import_ratio"]),
                        text=f"🌍 수입차 비율: {region_data['import_ratio']}%")
            st.write(f"💸 **평균 차량 구매 가격:** {int(region_data['avg_price']):,}만 원")

    st.divider()

    # ── ⑤ 추천 차량 ──
    st.subheader(f"🚗 [{persona}] 페르소나 추천 차량")
    st.caption("Car-BTI 4축 각각에 가장 잘 맞는 차량을 한 대씩 추천합니다.")
    render_recommended_cars(persona, cars_df)

    st.divider()

    # ── ⑤ 매칭 FAQ ──
    st.subheader(f"💡 [{persona}] 페르소나 매칭 FAQ")
    st.caption("모든 FAQ를 이 지역 페르소나와의 매칭도 순으로 정렬했습니다.")
    render_faq_list(persona, faq_df)


# ════════════════════════════════════════
# Tab 2: 나의 Car-BTI 테스트
# ════════════════════════════════════════
with tab2:
    st.subheader("🧪 나의 Car-BTI 테스트")
    st.caption("4가지 질문에 답하시면 본인의 Car-BTI와 가장 비슷한 지역, 어울리는 차량, 추천 FAQ를 보여드립니다.")

    q1 = st.radio(
        "**Q1.** 다음 차량 중 더 끌리시는 쪽은?",
        ["⚡ 전기차/하이브리드 등 친환경", "⛽ 내연기관(가솔린/디젤/LPG)"],
        key="t_q1",
    )
    q2 = st.radio(
        "**Q2.** 주말에 차량을 주로 어떻게 활용하시나요?",
        ["🏕️ 캠핑·패밀리·레저 — SUV/대형이 필요", "🏙️ 도심 주행·주차 편의 — 소형/세단을 선호"],
        key="t_q2",
    )
    q3 = st.radio(
        "**Q3.** 차량 구매 예산은 어느 정도이신가요?",
        ["💎 5,000만원 이상 — 프리미엄도 고려", "💰 5,000만원 미만 — 가성비 우선"],
        key="t_q3",
    )
    q4 = st.radio(
        "**Q4.** 브랜드 선호도는?",
        ["🌍 수입 브랜드 (벤츠/BMW/볼보 등)", "🇰🇷 국산 브랜드 (현대/기아/제네시스 등)"],
        key="t_q4",
    )

    if st.button("🚀 내 Car-BTI 확인하기", type="primary", use_container_width=True):
        my_persona = (
            ("E" if q1.startswith("⚡") else "G")
            + ("L" if q2.startswith("🏕") else "S")
            + ("P" if q3.startswith("💎") else "B")
            + ("I" if q4.startswith("🌍") else "D")
        )
        my_color = PERSONA_COLORS.get(my_persona, "#888")

        st.divider()

        # 결과 배지
        st.markdown(
            f"<div style='padding:24px;background:{my_color}33;"
            f"border-left:8px solid {my_color};border-radius:8px;margin-bottom:14px'>"
            f"<div style='font-size:16px;color:#666'>🎯 당신의 Car-BTI는</div>"
            f"<div style='font-size:40px;font-weight:bold;letter-spacing:6px'>[ {my_persona} ]</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

        # 4축 설명
        st.markdown("##### 📖 당신의 4축 분석")
        st.markdown(persona_desc_html(my_persona), unsafe_allow_html=True)

        st.divider()

        # ── 가장 비슷한 지역 Top 3 ──
        st.markdown("##### 🗺️ 당신과 가장 비슷한 Car-BTI 성향 지역 Top 3")
        stats = df_stats.copy()
        stats["_score"] = stats["persona_type"].apply(
            lambda p: sum(1 for a, b in zip(p, my_persona) if a == b)
        )
        top3 = stats.sort_values("_score", ascending=False).head(3)

        cols = st.columns(3)
        rank_emojis = ["🥇", "🥈", "🥉"]
        for i, (_, row) in enumerate(top3.iterrows()):
            with cols[i]:
                rcolor = PERSONA_COLORS.get(row["persona_type"], "#888")
                st.markdown(
                    f"<div style='padding:14px;background:{rcolor}22;"
                    f"border-left:4px solid {rcolor};border-radius:6px;text-align:center'>"
                    f"<div style='font-size:32px'>{rank_emojis[i]}</div>"
                    f"<div style='font-size:18px;font-weight:bold;margin:6px 0'>{row['region']}</div>"
                    f"<div style='font-family:monospace;font-size:20px;letter-spacing:3px'>{row['persona_type']}</div>"
                    f"<div style='font-size:13px;color:#666;margin-top:6px'>4자리 중 {row['_score']}자리 일치</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

        st.divider()

        # 추천 차량
        st.markdown(f"##### 🚗 당신([{my_persona}])에게 어울리는 차량")
        render_recommended_cars(my_persona, cars_df)

        st.divider()

        # 매칭 FAQ Top 3
        st.markdown(f"##### 💡 당신께 도움될 FAQ Top 3")
        render_faq_list(my_persona, faq_df, top_n=3)