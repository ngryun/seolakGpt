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

time_schedule = {
    "1교시": {"시작 시간": "8:40", "종료 시간": "9:30"},
    "2교시": {"시작 시간": "9:40", "종료 시간": "10:30"},
    "3교시": {"시작 시간": "10:40", "종료 시간": "11:30"},
    "4교시": {"시작 시간": "11:40", "종료 시간": "12:30"},
    "점심 식사 시간": {"시작 시간": "12:30", "종료 시간": "13:30"},
    "5교시": {"시작 시간": "13:30", "종료 시간": "14:20"},
    "청소 시간": {"시작 시간": "14:20", "종료 시간": "14:40"},
    "6교시": {"시작 시간": "14:40", "종료 시간": "15:30"},
    "7교시": {"시작 시간": "15:40", "종료 시간": "16:30"}
}

def get_time_schedule(**kwargs):
    교시 = kwargs['교시']
    # 입력된 교시에 해당하는 시간 반환
    if 교시 in time_schedule:
        return str(time_schedule[교시]["시작 시간"]) + ' ~ ' + str(time_schedule[교시]["종료 시간"])
    else:
        return "해당 교시가 존재하지 않습니다."
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
st.caption("🚀지능 개선에 도움을 준 선생님 : 이애림, 박현주")

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

my_assistant = client.beta.assistants.retrieve(assistant_id)
thread_messages = client.beta.threads.messages.list(thread_id,order="asc")

#   st.caption("오늘 급식 뭐야?")
#   st.caption("남궁연 선생님 내선번호 뭐니?")
#   st.caption("349는 누구번호야?")
#   st.caption("경조사 출결기준 알려줘")

for msg in thread_messages.data:
    if msg.role == 'assistant':
        with st.chat_message(msg.role, avatar="seoli.png"):
            st.markdown(msg.content[0].text.value)
    else:
        with st.chat_message(msg.role):
            st.markdown(msg.content[0].text.value)

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
            elif function_name == "get_time_schedule":
                output = get_time_schedule(**arguments)
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
                    print(event.data.object)
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
    st.chat_message("user").write(prompt)
    
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


                # run = client.beta.threads.runs.retrieve(
                # thread_id=thread_id,
                # run_id=event.data.id
                # )

                # if run.status == 'completed':
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
                        deleted_message = client.beta.threads.messages.delete(
                            message_id = message.id,
                            thread_id=thread_id,
                        )
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


button_cliked = False

with st.sidebar:
   st.markdown("질문예시")
   if st.button("남궁연 내선번호는?"):
       prompt_b = "남궁연 내선번호는?"
       button_cliked = True
   if st.button("1학년 2회고사는 언제부터야?"):
       prompt_b = "1학년 2회고사는 언제부터야?"
       button_cliked = True
   if st.button("오늘 급식메뉴는?"):
       prompt_b = "오늘 급식메뉴는?"
       button_cliked = True
   if st.button("1교시는 언제 시작해?"):
       prompt_b = "1교시는 언제 시작해?"
       button_cliked = True       
   if st.button("경조사 출결기준 알려줄래?"):
       prompt_b = "경조사 출결기준 알려줄래?"
       button_cliked = True
   if st.button("2학년 인문계 1등급은 몇명까지야?"):
       prompt_b = "2학년 인문계 1등급은 몇명까지야?"
       button_cliked = True    
   if st.button("10월 주요일정알려줘"):
       prompt_b = "10월 주요일정알려줘"
       button_cliked = True    
   if st.button("교장선생님 성함으로 삼행시지어줘"):
       prompt_b = "교장선생님 성함 알려주고 삼행시지어줄래?"
       button_cliked = True    

if button_cliked:
  process_prompt(prompt_b, client, thread_id, assistant_id, my_assistant)

prompt = st.chat_input("물어보고 싶은 것을 입력하세요!")
if prompt:
    process_prompt(prompt, client, thread_id, assistant_id, my_assistant)

