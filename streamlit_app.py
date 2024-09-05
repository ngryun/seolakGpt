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
        print(date)
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

API_KEY = st.secrets["OpenAI_key"]
client = OpenAI(api_key=API_KEY)
st.header('설악고등학교 챗봇')
st.caption("🚀지능 개선에 도움을 준 분 : 이애림선생님,박현주선생님, 변미영교장선생님")
thread_id=''
#thread id 를 하나로 관리하기 위함
if 'key' not in st.session_state:
    # if st.button("오늘 급식메뉴는?"):
    #     prompt_b = "오늘 메뉴는?"
    #     button_cliked = True
    msg = "나는 설이야! 설악고 선생님들의 친한 친구로, 여러 가지 일을 도와주고 있지. 궁금한 거 있으면 언제든지 물어봐! 😊✨"
    with st.chat_message("assistant", avatar="seoli.png"):
        st.markdown(msg)
    thread = client.beta.threads.create()
    st.session_state.key = thread.id
    
thread_id = st.session_state.key
assistant_id = st.secrets["ASSISTANT_ID"]
print(thread_id)
my_assistant = client.beta.assistants.retrieve(assistant_id)
thread_messages = client.beta.threads.messages.list(thread_id,order="asc")

def handle_tool_outputs(run, client, thread_id):
    tool_outputs = []
    if run.status == 'requires_action':
        for tool in run.required_action.submit_tool_outputs.tool_calls:
            function_name = tool.function.name
            arguments = json.loads(tool.function.arguments)
            output = None
            print(function_name)

            if function_name == "get_meal":
                output = get_meal(**arguments)
            elif function_name == "get_teachers_number":
                output = get_teachers_number(**arguments)
            elif function_name == "get_teachers_name":
                output = get_teachers_name(**arguments)

            if output:
                print(output)
                tool_outputs.append({
                    "tool_call_id": tool.id,
                    "output": output
                })

        if tool_outputs:
            try:
                #원래는 sumit_tool_outputs_and_poll 인가 그랬음.
                stream = client.beta.threads.runs.submit_tool_outputs(
                    thread_id=thread_id,
                    run_id=run.id,
                    tool_outputs=tool_outputs,
                    stream = True
                )
                print("Tool outputs submitted successfully.")
                res_box = st.empty()
                report=[]

                for event in stream:
                    # print(event.data.object)
                    if event.data.object == 'thread.message.delta':
                        for content in event.data.delta.content:
                            if content.type == 'text':
                                report.append(content.text.value)
                                result = "".join(report).strip()
                                res_box.markdown(f'*{result}*')
                                event = True
            except Exception as e:
                print("Failed to submit tool outputs:", e)
        else:
            print("No tool outputs to submit.")
            event = False

    return event
def process_prompt(prompt, client, thread_id, assistant_id, my_assistant, max_retries=3):
    print('함수시작')
    st.chat_message("user").write(prompt)
    print(thread_id)
    retries = 0
    success = False
    with st.chat_message("assistant", avatar="seoli.png"):
        res_box = st.empty()
        report=[]
        
        while retries < max_retries and not success:
            message = client.beta.threads.messages.create(
                thread_id=thread_id,
                role="user",
                content=prompt
            )
            current_time = datetime.now(kst).strftime('%Y-%m-%d %H:%M:%S')
            stream = client.beta.threads.runs.create(
                thread_id=thread_id,
                assistant_id=assistant_id,
                instructions=my_assistant.instructions + "\n 현재 시각은 " + current_time,
                stream = True
            )
            with st.spinner():
                for event in stream:
                    print(event.data.object)
                    if event.data.object == 'thread.message.delta':
                        for content in event.data.delta.content:
                            if content.type == 'text':
                                report.append(content.text.value)
                                result = "".join(report).strip()
                                res_box.markdown(f'*{result}*')
                                success = True
                print("야호" + event.data.id)
                run = client.beta.threads.runs.retrieve(
                thread_id=thread_id,
                run_id=event.data.id
                )
                print(run.status)
        
            if run.status == 'requires_action':

                event = handle_tool_outputs(run, client, thread_id)
                if event:
                    success = True
                else:
                    retries += 1
                    print(f"Retrying... ({retries}/{max_retries})")
                    if retries >= max_retries:
                        res_box.markdown("미안.. 오류발생")
                        run = client.beta.threads.runs.cancel(
                        thread_id=thread_id,
                        run_id=run.id
                        )
                        # deleted_message = client.beta.threads.messages.delete(
                        #     message_id = message.id,
                        #     thread_id=thread_id,
                        # )
                        thread = client.beta.threads.create()
                        thread_id = thread.id
                        st.session_state.key = thread.id
                    else:
                        print(run.status + "\n")
                        print(run)
                        run = client.beta.threads.runs.cancel(
                        thread_id=thread_id,
                        run_id=run.id
                        )
                        deleted_message = client.beta.threads.messages.delete(
                            message_id = message.id,
                            thread_id=thread_id,
                        )
    print('함수끝')

button_cliked = False
print("메시지출력전")
for msg in thread_messages.data:
    if msg.role == 'assistant':
        with st.chat_message(msg.role, avatar="seoli.png"):
            st.markdown(msg.content[0].text.value)
    else:
        with st.chat_message(msg.role):
            st.markdown(msg.content[0].text.value)
print('메시지출력후')
with st.sidebar:
   st.markdown("질문예시")
   if st.button("설악고에 대해 소개해줘"):
       prompt_b = "설악고에 대해 소개해줘"
       button_cliked = True
   if st.button("오늘 급식메뉴는?"):
       prompt_b = "오늘 급식메뉴는?"
       button_cliked = True
   if st.button("지금은 몇교시야?"):
       prompt_b = "지금은 몇교시야?"
       button_cliked = True       
   if st.button("경조사 출결기준 알려줘?"):
       prompt_b = "경조사 출결기준 알려줘?"
       button_cliked = True
   if st.button("3학년 4등급은 몇명까지야?"):
       prompt_b = "3학년 4등급은 몇명까지야? 정확히 계산해줘!"
       button_cliked = True    
   if st.button("10월 주요일정은?"):
       prompt_b = "10월 주요일정알려줘"
       button_cliked = True
   if st.button("남궁연 내선번호는?"):
       prompt_b = "남궁연 내선번호는?"
       button_cliked = True 
   if st.button("교장선생님 성함으로 삼행시!"):
       prompt_b = "교장선생님 성함 알려주고 삼행시지어줄래?"
       button_cliked = True
   if st.button("교감선생님 성함으로 이행시!"):
       prompt_b = "교감선생님 성함 알려주고 이행시지어줄래?"
       button_cliked = True       

if button_cliked:
    process_prompt(prompt_b, client, thread_id, assistant_id, my_assistant)

print("prompt 입력전")
prompt = st.chat_input("물어보고 싶은 것을 입력하세요!")
if prompt:
    print("prompt 입력후")
    process_prompt(prompt, client, thread_id, assistant_id, my_assistant)

