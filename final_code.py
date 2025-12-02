%%writefile module/project1.py
import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# -----------------------------------------------------------------------------
# 0. 페이지 설정
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="👻 GoStock - 나만의 작은 주식 비서",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 탭 스타일 CSS
st.markdown("""
<style>
    .stTabs [data-baseweb="tab-list"] { gap: 2px; }
    .stTabs [data-baseweb="tab"] {
        height: 50px; white-space: pre-wrap; background-color: #f0f2f6;
        border-radius: 4px 4px 0px 0px; gap: 1px;
        padding-top: 10px; padding-bottom: 10px;
        flex-grow: 1; text-align: center; font-size: 1.2rem; font-weight: 600;
    }
    .stTabs [aria-selected="true"] {
        background-color: #ffffff; border-bottom: 2px solid #4e8cff; color: #4e8cff;
    }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 1. 데이터 로드 및 전처리
# -----------------------------------------------------------------------------
@st.cache_data
def load_data():
    fin_path = 'fin_info_final.csv'
    price_path = 'stock_re.csv'

    try:
        df_fin = pd.read_csv(fin_path)
        df_price = pd.read_csv(price_path, encoding='euc-kr')
    except FileNotFoundError:
        return None, None

    # [주가 데이터 전처리]
    df_price.columns = df_price.columns.str.strip()
    
    # 숫자형 변환 (쉼표 제거)
    numeric_cols = ['종가', '시가', '고가', '저가', '거래량']
    for col in numeric_cols:
        if df_price[col].dtype == 'object':
            df_price[col] = df_price[col].astype(str).str.replace(',', '').astype(float)
    
    df_price['날짜'] = pd.to_datetime(df_price['날짜'])
    df_price['회사코드'] = df_price['회사코드'].astype(str).str.zfill(6)
    df_price = df_price.sort_values(by=['회사코드', '날짜']).reset_index(drop=True)
    
    # 이동평균선 계산
    df_price['MA5'] = df_price.groupby('회사코드')['종가'].transform(lambda x: x.rolling(window=5).mean())
    df_price['MA20'] = df_price.groupby('회사코드')['종가'].transform(lambda x: x.rolling(window=20).mean())
    df_price['MA60'] = df_price.groupby('회사코드')['종가'].transform(lambda x: x.rolling(window=60).mean())

    return df_fin, df_price

df_info_origin, df_money = load_data()

if df_info_origin is None or df_money is None:
    st.error("데이터 파일을 찾을 수 없습니다.")
    st.stop()

# -----------------------------------------------------------------------------
# 2. 시장 평균(마지막 행) 분리 + 종목 기본 정보 준비
# -----------------------------------------------------------------------------
# 마지막 행이 '종목 평균'
market_mean_series = df_info_origin.iloc[-1]

# 실제 종목 리스트 (마지막 행 제외)
df_info = df_info_origin.iloc[:-1].copy()

# 회사코드 매핑
code_map = df_money[['사명', '회사코드']].drop_duplicates().set_index('사명')['회사코드'].to_dict()
if '회사코드' not in df_info.columns:
    # 회사코드 매핑 보완
    df_info['회사코드'] = df_info['사명'].map(code_map)
    df_info['회사코드'] = df_info['회사코드'].fillna("000000")  # 기본값 넣기


# -----------------------------------------------------------------------------
# 3. 메인 헤더
# -----------------------------------------------------------------------------
st.title("👻 GoStock")
st.caption("나만의 작고 소중한 주식 비서")

# -----------------------------------------------------------------------------
# 4. 종목 필터 설정 & 리스트
# -----------------------------------------------------------------------------
st.markdown("### 🔎 종목 필터")  # 문구 수정

good_filter = st.checkbox("🟢 저평가 종목", value=False)  # 네이밍 수정 >> (우량주만 보기 > 저평가 종목)

if good_filter:
    filtered_df = df_info[
        (df_info["PER(배)"] >= 0) &
        (df_info["PBR(배)"] >= 0) &
        (df_info["PER(배)"] <= 10) &
        (df_info["PBR(배)"] <= 1)
    ].copy()
else:
    filtered_df = df_info.copy()

st.markdown("#### 📋 대상 종목 리스트")  # 문구 수정
show_cols = ["사명", "PER(배)", "PBR(배)", "ROE(%)", "매출액증가율", "부채비율", "배당수익률"]   # 컬럼 순서 조정
# show_cols = ["사명", "PER(배)", "PBR(배)", "ROE(%)", "배당수익률"]

# (추가)인덱스를 1부터 시작하도록 변경
filtered_df = filtered_df.reset_index(drop=True)
filtered_df.index = filtered_df.index + 1
filtered_df = filtered_df.rename_axis("순번")  

st.dataframe(filtered_df[show_cols], use_container_width=True)

# -----------------------------------------------------------------------------
# 5. 분석할 종목 선택
# -----------------------------------------------------------------------------
st.markdown("### 📌 분석할 종목 선택")

if filtered_df.empty:
    st.error("⚠️ 현재 필터 조건을 만족하는 종목이 없습니다. 필터를 조정해 주세요.")
    st.stop()

filtered_df = filtered_df.dropna(subset=["회사코드"])
filtered_labels = filtered_df.apply(
    lambda x: f"{x['사명']} ({str(x['회사코드']).zfill(6)})",
    axis=1
).tolist()

selected_label = st.selectbox("🔍 종목 선택", filtered_labels, index=0)
selected_company = selected_label.split(" (")[0]

# 선택된 종목 정보 & 주가 데이터
company_info = filtered_df[filtered_df['사명'] == selected_company].iloc[0]
company_money = df_money[df_money['사명'] == selected_company].sort_values('날짜')

if company_money.empty:
    st.error("해당 종목의 주가 데이터가 없습니다.")
    st.stop()

# -----------------------------------------------------------------------------
# 6. 상단 핵심 요약 (현재 주가 / PER / PBR / ROE)
# -----------------------------------------------------------------------------
last_row = company_money.iloc[-1]
last_price = last_row['종가']
prev_price = company_money.iloc[-2]['종가'] if len(company_money) > 1 else last_price
change = last_price - prev_price
change_pct = (change / prev_price) * 100 if prev_price != 0 else 0

st.markdown("---")
st.markdown(f"### 💡 {selected_company} 주요 지표 한눈에 보기")

m1, m2, m3, m4, m5, m6 = st.columns(6)  # 컬럼 추가 및 설명 내용 수정
m1.metric("현재 주가", f"{last_price:,.0f}원", f"{change:,.0f}원 ({change_pct:.2f}%)")
m2.metric("PER", f"{company_info.get('PER(배)', 0):.2f}배", help="주가수익비율(주가 대비 기업의 순이익을 비교하여 기업의 가치를 평가, 낮을수록 저평가")
m3.metric("PBR", f"{company_info.get('PBR(배)', 0):.2f}배", help="주가순자산비율 (주가가 기업의 순자산 가치 대비 얼마나 높고 낮은지를 나타내는 지표, 낮을수록 저평가)")
m4.metric("ROE", f"{company_info.get('ROE(%)', 0):.2f}%", help="자기자본이익률 (자기자본을 활용해 1년간 얼마나 벌여 들였는가를 나타내는 지표, 높을수록 우")
m5.metric("매출액 증가율", f"{company_info.get('매출액증가율', 0):.2f}%", help="기업의 일정 기간 매출액이 전년 대비 얼마나 늘었는지를 백분율로 나타내는 지표, 기업의 성장성을 판단")
m6.metric("부채비율", f"{company_info.get('부채비율', 0):.2f}%", help="기업이 타인 자본(부채)에 얼마나 의존하고 있는지를 백분율로 나타내는 지표, 일반적으로 100% 이하가 표준")
st.markdown("---")

# -----------------------------------------------------------------------------
# 7. 탭 구성
# -----------------------------------------------------------------------------
tab1, tab2 = st.tabs(["💎 기본적 분석 (Fundamental)", "📊 기술적 분석 (Technical)"])  # 문구 수정

# =============================================================================
# [TAB 1] 가치투자 - 가치 기반 펀더멘털 분석
# =============================================================================
with tab1:
    st.subheader("💎 내재 가치 기반의 종목 평가 분석")

    # (점수 컬럼 & 원본 값 매핑)
     # 평가항목 문구 수정
    score_map = {                                 
        '수익성': ('ROE(%)_점수', 'ROE(%)'),
        '성장성': ('매출액증가율_점수', '매출액증가율'),
        '배당 정도': ('배당수익률_점수', '배당수익률'),
        '저평가 정도': ('PER(배)_점수', 'PER(배)'),
        '안정성': ('부채비율_점수', '부채비율')
    }

    labels = list(score_map.keys())
    my_scores = [company_info.get(score_map[l][0], 0) for l in labels]
    avg_scores = [market_mean_series.get(score_map[l][0], 0) for l in labels]

    # 레이더 차트용 데이터 닫기
    r_me = my_scores + [my_scores[0]]
    r_avg = avg_scores + [avg_scores[0]]
    theta = labels + [labels[0]]

    fig = go.Figure()

    # 시장 평균
    fig.add_trace(go.Scatterpolar(
        r=r_avg,
        theta=theta,
        fill='toself',
        name='시장 평균 점수',
        line_color='gray',
        fillcolor='rgba(128, 128, 128, 0.3)',
        mode='lines'
    ))

    # 내 종목
    fig.add_trace(go.Scatterpolar(
        r=r_me,
        theta=theta,
        fill='toself',
        name=f'{selected_company} 점수',
        line_color='#2980b9',
        fillcolor='rgba(41, 128, 185, 0.4)',
        mode='lines+markers'
    ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 10],
                tickfont=dict(size=11)
            ),
            angularaxis=dict(
                tickfont=dict(size=14),  # 방사형 차트 내 평가항목 글꼴 크기 조정
                rotation=90   # 방사형 차트 꼭지점 위치 조정
            )
        ),
        showlegend=True,
        height=500,
        title=dict(
            text=f"📊 {selected_company} 투자 매력도 (10점 만점)",
            x=0.45,           # 타이틀 위치 조정 추가
            xanchor="center"  # 타이틀 가운데 정렬
        )
    )


    
    st.plotly_chart(fig, use_container_width=True)

    # 상세 분석
    st.divider()
    st.markdown("#### 📝 지표별 상세 진단")  # 문구 수정
    st.info("💡 점수는 0점에서 10점까지 미리 산정되었으며, 회색 영역은 대상 종목의 전체 평균을 의미합니다.")  # 문구 수정

    positive_count = 0

    for label in labels:
        score_col, raw_col = score_map[label]
        
        my_s = company_info.get(score_col, 0)
        avg_s = market_mean_series.get(score_col, 0)
        my_raw = company_info.get(raw_col, 0)

        if my_s >= avg_s:
            status = "**우수 (평균 이상)**"
            icon = "✅"
            positive_count += 1
        else:
            status = "미흡 (평균 미만)"
            icon = "🔻"

        st.markdown(
            f"- {icon} **{label}** : **{my_s:.1f}점** (평균 {avg_s:.1f}점 대비)\n"
            f"    - (실제값: {my_raw:,.2f}) → **{status}**"
        )

    st.markdown("<br>", unsafe_allow_html=True)

    if positive_count >= 3:
        st.success(f"🌟 **추천 여부** : **{positive_count}개** 지표가 평균 이상 → **추천**")
    else:
        st.warning(f"⚠️ **추천 여부** : **{positive_count}개** 지표만 평균 이상 → **비추천**")

# =============================================================================
# [TAB 2] 기술투자 (크로스 & 추세)
# =============================================================================
with tab2:
    st.subheader("📈 차트 & 추세 분석")
    
    # 1. 분석용 데이터 준비
    view_data = company_money.copy()
    
    # 2. 크로스 이벤트 계산을 위한 이전 값(Shift) 생성
    view_data['Prev_MA5'] = view_data['MA5'].shift(1)
    view_data['Prev_MA20'] = view_data['MA20'].shift(1)
    view_data['Prev_MA60'] = view_data['MA60'].shift(1)
    
    cross_events = []

    # 3. 차트 그리기
    fig = go.Figure()
    
    # 캔들(연하게)
    fig.add_trace(go.Candlestick(
        x=view_data['날짜'], 
        open=view_data['시가'], high=view_data['고가'],
        low=view_data['저가'], close=view_data['종가'], 
        name='주가',
        increasing_line_color='rgba(255, 0, 0, 0.4)',
        increasing_fillcolor='rgba(255, 0, 0, 0.4)',
        decreasing_line_color='rgba(0, 0, 255, 0.4)',
        decreasing_fillcolor='rgba(0, 0, 255, 0.4)'
    ))
    
    # 이평선
    fig.add_trace(go.Scatter(
        x=view_data['날짜'], y=view_data['MA5'], 
        line=dict(color='mediumblue', width=1.5), 
        name='5일선'
    ))
    fig.add_trace(go.Scatter(
        x=view_data['날짜'], y=view_data['MA20'], 
        line=dict(color='magenta', width=1.5), 
        name='20일선'
    ))
    fig.add_trace(go.Scatter(
        x=view_data['날짜'], y=view_data['MA60'], 
        line=dict(color='green', width=2), 
        name='60일선 (기준)'
    ))
    
    # 4. 골든/데드 크로스 탐지
    for idx, row in view_data.iterrows():
        if pd.isna(row['MA60']) or pd.isna(row['Prev_MA60']):
            continue

        is_g5 = (row['MA5'] > row['MA60']) and (row['Prev_MA5'] <= row['Prev_MA60'])
        is_g20 = (row['MA20'] > row['MA60']) and (row['Prev_MA20'] <= row['Prev_MA60'])
        
        is_d5 = (row['MA5'] < row['MA60']) and (row['Prev_MA5'] >= row['Prev_MA60'])
        is_d20 = (row['MA20'] < row['MA60']) and (row['Prev_MA20'] >= row['Prev_MA60'])

        date_str = row['날짜'].strftime('%Y-%m-%d')
        cross_point = row['MA60'] 

        if is_g5 or is_g20:
            fig.add_annotation(
                x=row['날짜'], y=cross_point,
                text="<b>💰</b>",
                font=dict(size=15, color="red"),
                showarrow=True, 
                arrowhead=2, 
                arrowcolor="rgba(0,0,0,0.4)",
                arrowwidth=1.5,
                ax=0, ay=-60
            )
            cross_events.append(f"🔴 **골든크로스 (매수)**: {date_str}")

        if is_d5 or is_d20:
            fig.add_annotation(
                x=row['날짜'], y=cross_point,
                text="<b>💸</b>",
                font=dict(size=15, color="blue"),
                showarrow=True, 
                arrowhead=2, 
                arrowcolor="rgba(0,0,0,0.4)",
                arrowwidth=1.5,
                ax=0, ay=60
            )
            cross_events.append(f"🔵 **데드크로스 (매도)**: {date_str}")
    
    fig.update_layout(
        title=f"{selected_company} 일봉 차트", 
        xaxis_rangeslider_visible=False,
        height=600,
        plot_bgcolor='rgba(0,0,0,0)',
        hovermode="x unified"
    )
    st.plotly_chart(fig, use_container_width=True)
    
    # 5. 하단 정보 패널
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### 🔔 최근 매매 신호")
        if cross_events:
            for e in reversed(cross_events[-5:]):
                st.markdown(e)
        else:
            st.info("최근 조회 기간 내 특이 신호가 없습니다.")
        
    with c2:
        st.markdown("#### 🔍 추세 스캔 결과")
        last = view_data.iloc[-1]
        
        if pd.isna(last['MA5']) or pd.isna(last['MA60']):
            st.write("데이터 부족으로 판단 불가")
        elif last['MA5'] > last['MA60']:
            st.success("📈 현재 **'상승 추세'** 구간입니다.")
        else:
            st.error("📉 현재 **'하락 추세'** 구간입니다.")
