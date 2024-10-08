from dotenv import load_dotenv
import os
from openai import OpenAI
import streamlit as st
import json
import requests
from datetime import datetime
import pytz
# 한국 표준시 (KST) 타임존 가져오기
kst = pytz.timezone('Asia/Seoul')
names = st.secrets["names"]
short_numbers = st.secrets["short_numbers"]

def get_teachers_number(**kwargs):
    try:
        name = kwargs['name']
        index = names.index(name)
        return short_numbers[index]
    except (KeyError, ValueError, IndexError):
        return "교사 이름을 찾을 수 없음"

# 단축번호로 교사 이름을 찾는 함수
def get_teachers_name(**kwargs):
    try:
        number = kwargs['number']
        index = short_numbers.index(number)
        return names[index]
    except (KeyError, ValueError, IndexError):
        return "해당 단축번호에 해당하는 교사를 찾을 수 없습니다."
    
def get_meal(**kwargs):
    try:
        date = kwargs['YYYYMMDD']
        url = f"https://open.neis.go.kr/hub/mealServiceDietInfo?Type=json&ATPT_OFCDC_SC_CODE=K10&SD_SCHUL_CODE=7801148&MMEAL_SC_CODE=2&MLSV_YMD={date}"
        # API를 호출하여 데이터 가져오기
        response = requests.get(url)
        # 응답을 JSON 형태로 변환
        data = response.json()
        # 급식 메뉴 가져오기
        menu = data["mealServiceDietInfo"][1]["row"][0]["DDISH_NM"]
        menu = menu.replace('<br/>','\n')
        return menu
    except (KeyError, IndexError):
        return "급식정보가 없습니다"

load_dotenv()
# API_KEY = os.environ['OPENAI_API_KEY']
API_KEY = st.secrets["OpenAI_key"]



client = OpenAI(api_key=API_KEY)

#thread id 를 하나로 관리하기 위함
if 'key' not in st.session_state:
    thread = client.beta.threads.create()
    st.session_state.key = thread.id

print(st.session_state.key)
thread_id = st.session_state.key
assistant_id = st.secrets["ASSISTANT_ID"]

my_assistant = client.beta.assistants.retrieve(assistant_id)
thread_messages = client.beta.threads.messages.list(thread_id,order="asc")
with st.sidebar:
  st.caption("예시 질문")
  st.caption("오늘 급식 뭐야?")
  st.caption("남궁연 선생님 내선번호 뭐니?")
  st.caption("349는 누구번호야?")
  st.caption("경조사 출결기준 알려줘")

st.header('설악GPT')
st.caption("🚀 설악고등학교 선생님들을 돕기 위해 만들어졌어요. 아직은 모르는 것이 많습니다.")
st.caption("설악고등학교 급식메뉴, 학교내선번호, 출결, 성적 기준등에 대해 공부했습니다")

if "text_boxes" not in st.session_state:
    st.session_state.text_boxes = []

for msg in thread_messages.data:
    if msg.role == 'assistant':
        with st.chat_message(msg.role, avatar=".\seoli.png"):
            st.markdown(msg.content[0].text.value)
    else:
        with st.chat_message(msg.role):
            st.markdown(msg.content[0].text.value)


prompt = st.chat_input("물어보고 싶은 것을 입력하세요!")

if prompt:
  st.chat_message("user").write(prompt)
  with st.spinner("..생각중.."):
    message = client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=prompt
    )
    current_time = datetime.now(kst).strftime('%Y-%m-%d %H:%M:%S')
    run = client.beta.threads.runs.create_and_poll(
        thread_id=thread_id,
        assistant_id=assistant_id,
        instructions= my_assistant.instructions + "\n 현재 시각은" + current_time 
    )

    print(run.instructions)
    if run.status == 'completed': 
        messages = client.beta.threads.messages.list(
            thread_id=thread_id
        )
        st.chat_message("assistant",avatar=".\seoli.png").write(messages.data[0].content[0].text.value)
    else:
        print(run.status)

    tool_outputs = []
    if run.status =='requires_action':
      for tool in run.required_action.submit_tool_outputs.tool_calls:
        print(tool.function.name)
        if tool.function.name == "get_meal":
          arguments = json.loads(tool.function.arguments)
          print(arguments)
          tool_outputs.append({
            "tool_call_id": tool.id,
            "output": get_meal(**arguments)
          })

        elif tool.function.name == "get_teachers_number":
          arguments = json.loads(tool.function.arguments)
          tool_outputs.append({
            "tool_call_id": tool.id,
            "output": get_teachers_number(**arguments)
          })

        elif tool.function.name == "get_teachers_name":
          arguments = json.loads(tool.function.arguments)
          tool_outputs.append({
            "tool_call_id": tool.id,
            "output": get_teachers_name(**arguments)
          })

      if tool_outputs:
        print(tool_outputs)
        try:
          run = client.beta.threads.runs.submit_tool_outputs_and_poll(
            thread_id=thread_id,
            run_id=run.id,
            tool_outputs=tool_outputs
          )
          print("Tool outputs submitted successfully.")
        except Exception as e:
          print("Failed to submit tool outputs:", e)
      else:
        print("No tool outputs to submit.")
      
      if run.status == 'completed':
        messages = client.beta.threads.messages.list(
          thread_id=thread_id
        )
        st.chat_message("assistant",avatar=".\seoli.png").write(messages.data[0].content[0].text.value)
      else:
        print(run.status)
