import streamlit as st
import sqlite3
import pandas as pd
import datetime
from datetime import timezone, timedelta
import imaplib
import email
from email.header import decode_header
import os
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

# DB 연결 및 테이블 생성
def init_db():
    conn = sqlite3.connect('Hanyu_Mail_Assistant.db')
    c = conn.cursor()
    # 사용자 테이블
    c.execute('''CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT)''')
    # 요약 내역 테이블
    c.execute('''CREATE TABLE IF NOT EXISTS history 
                 (username TEXT, range TEXT, time TEXT, summary TEXT)''')
    conn.commit()
    conn.close()

# 요약 내역 저장 함수
def save_history(username, date_range, search_time, summary):
    conn = sqlite3.connect('Hanyu_Mail_Assistant.db')
    c = conn.cursor()
    c.execute("INSERT INTO history VALUES (?, ?, ?, ?)", (username, date_range, search_time, summary))
    conn.commit()
    conn.close()

# 요약 내역 불러오기 함수
def get_history(username):
    conn = sqlite3.connect('Hanyu_Mail_Assistant.db')
    # 데이터를 딕셔너리 형태로 편하게 가져오기 위한 설정
    conn.row_factory = sqlite3.Row 
    c = conn.cursor()
    c.execute("SELECT * FROM history WHERE username=?", (username,))
    rows = c.fetchall()
    conn.close()

    # 리스트 형태로 변환하여 반환
    return [dict(row) for row in rows]

def delete_history(username, search_time):
    # DB 이름을 Hanyu_Mail_Assistant.db 로 통일해서 연결
    conn = sqlite3.connect('Hanyu_Mail_Assistant.db')
    c = conn.cursor()
    # 특정 사용자의 특정 실행 시각 데이터를 삭제
    c.execute("DELETE FROM history WHERE username=? AND time=?", (username, search_time))
    conn.commit()
    conn.close()    
    
init_db()

# 페이지 및 폰트 설정, 로고 삽입
st.set_page_config(
    page_title="한유 AI 메일 비서", 
    page_icon="Logo_Hanyu.jpg",
    layout="centered"
)

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    # 화면을 수직으로 3등분
    empty_top, center_content, empty_bottom = st.container(), st.container(), st.container()

    with center_content:
        col1, col2, col3 = st.columns([1, 1, 1])
        
    with col2:
        st.markdown("<br>" * 1, unsafe_allow_html=True)
        # 로고 이미지 배치 (메인 페이지와 동일한 너비로 설정)
        st.image("Logo_Hanyu.jpg", width="stretch") 
        
        # 로고와 제목 사이 간격
        st.markdown("<br>", unsafe_allow_html=True)
    # --- 로그인 화면 ---
    st.markdown("""
            <h1 style='text-align: center; color: #1A3482; font-size: 3rem; font-weight: 700; margin-bottom: 0px;'>
                한유 AI 메일 비서
            </h1>
            """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True) # 제목과 입력창 사이 여백

    st.write("")

    user_input = st.text_input("아이디")
    pw_input = st.text_input("비밀번호", type="password")
    
    if st.button("로그인"):
        # 임시로 책임님 계정 설정 (나중에 DB와 연동 가능)
        if user_input == "iglee@hyskets.com" and pw_input == "Sis0303053!!": 
            st.session_state.logged_in = True
            st.session_state.username = user_input
            st.session_state.display_name = "이인기 책임"
            st.session_state.search_history = get_history(user_input)
            st.rerun() # 로그인 성공 시 화면을 새로고침해서 본 프로그램으로 진입
        else:
            st.error("아이디 또는 비밀번호가 틀립니다.")

else:

    # 세션 상태 초기화 (이력 및 현재 선택된 요약본)
    if "search_history" not in st.session_state:
        st.session_state.search_history = []
    if "current_summary" not in st.session_state:
        st.session_state.current_summary = None

    # 폰트 및 스타일 설정
    st.markdown("""
        <style>
        /* 1. 폰트 설정 */
        @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;700&display=swap');
        html, body, [class*="css"] {
            font-family: 'Noto Sans KR', sans-serif !important;
        }

        /* 2. 사이드바 색상 통일 및 테두리 제거 */
        [data-testid="stSidebar"] {
            background-color: #E6EEFF !important;
            border-right: none !important;
        }
        [data-testid="stSidebar"] > div:first-child {
            border-right: none !important;
        }

        /* 3. 날짜 입력창 색상 통일 및 테두리 제거 */
        div[data-baseweb="input"] {
            background-color: #E6EEFF !important;
            border: none !important;
            box-shadow: none !important;
        }
        div[data-baseweb="input"] > div {
            background-color: #E6EEFF !important;
            border: none !important;
        }
        input[aria-autocomplete="list"] {
            background-color: #E6EEFF !important;
            color: #1A3482 !important;
            border: none !important;
        }

        /* 4. 사이드바 버튼 스타일 및 테두리 제거 */
        .stButton > button {
            width: 100%; 
            text-align: left; 
            background-color: #E6EEFF !important; 
            color: #1A3482 !important; 
            border: none !important; 
            margin-bottom: 5px;
            box-shadow: none !important;
        }
        .stButton > button:hover {
            background-color: #D1E3FF !important; 
            color: #1A3482 !important;
        }
        </style>
        """, unsafe_allow_html=True)

    # 사이드바 기능 추가
    with st.sidebar:
        st.header("사용자 정보")
        st.info(f"**{st.session_state.display_name}**")
        
        if st.button("로그아웃", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.username = None
            st.rerun()
            
        st.markdown("---")
        st.header("메일 요약 진행 내역")
        history_data = get_history(st.session_state.username)
        if not st.session_state.search_history:
            st.write("최근 요약 진행 내역이 없습니다.")
        else:
    # 이력을 역순으로 표시
    # 이력을 역순으로 표시 (enumerate의 index는 삭제 시 식별자로 사용)
            # 리스트 자체를 뒤집어서 인덱스 혼선 방지
            for record in reversed(history_data):
                user, d_range, s_time, summary = record.values()
                # 검색 구간과 상세 실행 일시를 표시
                col_link, col_del = st.columns([4, 1])
                
                with col_link:
                    # 클릭 시 해당 요약을 메인 화면에 로드
                    btn_label = f"**{d_range}**\n({s_time})"
                    if st.button(btn_label, key=f"hist_btn_{s_time}"):
                        st.session_state.current_summary = {
                            "range": d_range,
                            "text": summary
                        }
                        st.rerun()
                
                with col_del:
                    # 개별 삭제 버튼 (빨간색 강조를 위해 아이콘이나 텍스트 사용)
                    if st.button("✖", key=f"del_btn_{s_time}"):
                        delete_history(st.session_state.username, s_time)
                        # 만약 삭제하는 내역이 현재 화면에 떠 있는 내용이라면 화면 초기화
                        if st.session_state.current_summary and st.session_state.current_summary['range'] == d_range:
                            st.session_state.current_summary = None
                        st.rerun()
                    

        st.markdown("---")
        if st.button("전체 내역 삭제", use_container_width=True):
                # DB의 모든 history 삭제 (사용자 기준)
                conn = sqlite3.connect('Hanyu_Mail_Assistant.db')
                c = conn.cursor()
                c.execute("DELETE FROM history WHERE username=?", (st.session_state.username,))
                conn.commit()
                conn.close()
                st.session_state.current_summary = None
                st.rerun()

    # 로고 삽입 (제목보다 위에 위치)
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        st.image("Logo_Hanyu.jpg", width="stretch")

    # 메인 제목 (HANYU 로고와 동일한 네이비 색상 적용)
    st.markdown("""
        <h1 style='text-align: center; 
                font-size: 50px; 
                margin-bottom: 40px;
                color: #1A3482;  /* 로고의 짙은 네이비 색상 */
                font-weight: 700;'>
            한유 AI 메일 비서
        </h1>
        """, unsafe_allow_html=True)

    st.write("안녕하세요, 이인기 책임님!")
    st.write("달력에서 날짜 구간을 선택해주시면")
    st.write("해당 기간 동안 받은 메일 중 안 읽은 메일을 검색하고 요약하여 안내해드리겠습니다.")
    st.markdown("<br>", unsafe_allow_html=True)

    # 계정 및 API 설정 (보안 주의)
    IMAP_SERVER = "hy.hanyugroup.co.kr"
    EMAIL_ACCOUNT = "iglee@hyskets.com" 
    EMAIL_PASSWORD = "Sis0303053!!"     

    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-2.5-flash')

    # 안전 설정: 민감한 단어가 있어도 차단하지 않도록 설정합니다.
    safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
    ]
    # 모델 정의 시 safety_settings를 적용합니다.
    model = genai.GenerativeModel(
        model_name='gemini-2.5-flash',
        safety_settings=safety_settings
    )

    imaplib._MAXLINE = 10000000 

    # 메일 헤더 디코딩 함수
    def get_decoded_header(header_value):
        if header_value is None:
            return ""
        
        decoded_bytes, charset = decode_header(header_value)[0]
        if isinstance(decoded_bytes, bytes):
            charset = charset if charset else 'utf-8'
            try:
                return decoded_bytes.decode(charset)
            except Exception:
                return decoded_bytes.decode('utf-8', errors='replace')
        return decoded_bytes

    # Streamlit UI: 달력 날짜 선택
    today = datetime.date.today()
    a_week_ago = today - datetime.timedelta(days=7)

    date_range = st.date_input(
        "조회하실 날짜 구간을 선택해주십시오.  \n(시작일 선택 후 종료일 선택)",
        value=(a_week_ago, today),
        max_value=today
    )

    # 메일 추출 및 Gemini 요약 실행 로직
    if len(date_range) == 2:
        start_date, end_date = date_range
        st.write(f"**선택된 기간:** {start_date} ~ {end_date}")
        
        # 버튼을 누르면 실행
        if st.button("메일 검색 및 AI 요약 시작"):
            #실행 시각 변수 설정
            search_time = datetime.datetime.now().strftime("%Y-%m-%d  %H:%M")
            search_start_date = start_date - datetime.timedelta(days=3)             
            search_end_date = end_date + datetime.timedelta(days=2)
            # 날짜를 IMAP 양식(예: 20-Mar-2026)으로 안전하게 변환
            month_map = {1:"Jan", 2:"Feb", 3:"Mar", 4:"Apr", 5:"May", 6:"Jun", 
                        7:"Jul", 8:"Aug", 9:"Sep", 10:"Oct", 11:"Nov", 12:"Dec"}

            start_str = f"{start_date.day:02d}-{month_map[start_date.month]}-{start_date.year}"
            end_str = f"{end_date.day:02d}-{month_map[end_date.month]}-{end_date.year}"

            search_criteria = f'(UNSEEN)'

            status_placeholder = st.empty()
            status_placeholder.info("그룹웨어 메일함에서 안 읽은 메일을 확인 중입니다.")
            try:
                mail = imaplib.IMAP4_SSL(IMAP_SERVER, 993)
                mail.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)
                mail.select("INBOX")
                
                status, messages = mail.search(None, search_criteria)

                if status != "OK" or not messages[0]:
                    status_placeholder.empty()
                    status_placeholder.warning(f"{start_date} 부터 {end_date} 사이에 처리할 안 읽은 메일이 없습니다.")
                else:
                    mail_ids = messages[0].split()[::-1]
                    total_mails = len(mail_ids)
                    status_placeholder.empty()
                    status_placeholder.success(f"메일함에서 총 {total_mails}개의 안 읽은 메일을 찾았습니다. 선택하신 기간에 해당하는 내용을 확인하도록 하겠습니다.")

                    email_texts = []

                    for m_id in mail_ids:
                        _, msg_data = mail.fetch(m_id, "(RFC822.HEADER)")
                        for response_part in msg_data:
                            if isinstance(response_part, tuple):
                                msg = email.message_from_bytes(response_part[1])
                                date_str = msg.get("Date")
                                if date_str:
                                    mail_dt = email.utils.parsedate_to_datetime(date_str)
                                    kst = timezone(timedelta(hours=9))
                                    mail_dt_kst = mail_dt.astimezone(kst)
                                    mail_date = mail_dt_kst.date()

                                    if start_date <= mail_date <= end_date:
                                        _, full_msg_data = mail.fetch(m_id, "(BODY.PEEK[])")
                                        for rp in full_msg_data:
                                            if isinstance(rp, tuple):
                                                f_msg = email.message_from_bytes(rp[1])
                                                subject = get_decoded_header(f_msg["Subject"])
                                                sender = get_decoded_header(f_msg["From"])
                                                
                                                body = ""
                                                if f_msg.is_multipart():
                                                    for part in f_msg.walk():
                                                        content_type = part.get_content_type()
                                                        cd = str(part.get("Content-Disposition"))
                                                        if content_type == "text/plain" and "attachment" not in cd:
                                                            try:
                                                                body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                                                            except: pass
                                                else:
                                                    try:
                                                        body = f_msg.get_payload(decode=True).decode('utf-8', errors='ignore')
                                                    except: pass
                                    
                                                current_no = len(email_texts) + 1
                                                email_content = f"[{len(email_texts) + 1}] 보낸사람: {sender}\n제목: {subject}\n본문: {body.strip()}"
                                                email_texts.append(email_content)

                    mail.close()
                    mail.logout()

                    # Gemini 요약 단계 시작
                    full_email_data = "\n\n---\n\n".join(email_texts)
                    prompt = f"""
                    너는 산업용 윤활유(Lubricant) 제조 기업 한유 그룹의 전문 비서야.
                    다음은 한유 그룹의 그룹웨어 메일 데이터입니다.
                    메일 데이터들의 내용을 분석해서 1. 핵심 안건, 2. 주요 결정/요청 사항, 3. 담당자별 대응해야 할 사항들을 날짜와 함께 요약해줘.
                    첫 문장은 반드시 다음과 같이 작성해줘.
                    "{start_date.year}년 {start_date.month:02d}월 {start_date.day:02d}일 부터 {end_date.year}년 {end_date.month:02d}월 {end_date.day:02d}일까지 수신된 메일 중 안읽은 메일 내용을 취합하여 요약 보고드립니다."
                    분석한 메일 내용은 첫 문장 다음에 위치하도록 해줘.

                    [주의] 메일 본문에 화학 물질이나 위험물 관련 용어가 포함될 수 있으나, 이는 정상적인 산업 현장의 소통이니 검열하지 말고 핵심만 요약해.

                    [메일 데이터]
                    {full_email_data}
                    """

                    with st.spinner("메일 내용을 분석 및 요약하고 있습니다. 잠시만 기다려 주시기 바랍니다."):
                        response = model.generate_content(prompt)

                        if not response.candidates:
                            st.warning("⚠️ AI가 메일 내용 중 민감한 정보를 감지하여 요약을 거부했습니다.")
                            # 차단 사유를 로그에 남기거나 화면에 작게 표시
                            st.caption(f"차단 사유: {response.prompt_feedback.block_reason}")
                            # 저장할 데이터에 에러 메시지 대입
                            summary_result = "요약 실패: 메일 내용이 정책에 의해 차단되었습니다."
                        
                        st.markdown("---")
                        st.subheader("안 읽은 메일 내용 요약")
                        st.markdown(response.text)
                        # 요약된 결과를 세션 이력에 추가
                        new_entry = {
                                "range": f"{start_date} ~ {end_date}",
                                "time": search_time,
                                "summary": response.text
                        }

                        save_history(
                            st.session_state.username, 
                            new_entry['range'], 
                            new_entry['time'], 
                            new_entry['summary']
                        )        

                        st.session_state.search_history.append(new_entry)
                        # 현재 화면에 표시할 요약본으로 설정
                        st.session_state.current_summary = {"range": new_entry['range'], "text": new_entry['summary']}
                        # 사이드바를 즉시 업데이트하기 위해 화면 새로고침
                        st.rerun()

            except Exception as e:
                st.error(f"메일 처리 중 예상치 못한 오류가 발생했습니다! {e}")

    elif len(date_range) == 1:
        st.warning("종료 날짜가 선택되지 않았습니다.")

    if st.session_state.current_summary:
        st.markdown("---")
        st.subheader(f"메일 요약 내용 ({st.session_state.current_summary['range']})")
        st.markdown(st.session_state.current_summary['text'])
        st.markdown("---")
