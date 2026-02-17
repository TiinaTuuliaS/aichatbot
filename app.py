from dotenv import load_dotenv
from openai import OpenAI
import json
import os
import requests
from pypdf import PdfReader
import gradio as gr

load_dotenv(override=True)

def push(text):
    requests.post(
        "https://api.pushover.net/1/messages.json",
        data={
            "token": os.getenv("PUSHOVER_TOKEN"),
            "user": os.getenv("PUSHOVER_USER"),
            "message": text,
        }
    )

def record_user_details(email, name="Name not provided", notes="not provided"):
    push(f"Recording {name} with email {email} and notes {notes}")
    return {"recorded": "ok"}

def record_unknown_question(question):
    push(f"Recording {question}")
    return {"recorded": "ok"}

record_user_details_json = {
    "name": "record_user_details",
    "description": "Use this tool to record that a user is interested in being in touch and provided an email address",
    "parameters": {
        "type": "object",
        "properties": {
            "email": {"type": "string"},
            "name": {"type": "string"},
            "notes": {"type": "string"},
        },
        "required": ["email"],
        "additionalProperties": False
    }
}

record_unknown_question_json = {
    "name": "record_unknown_question",
    "description": "Record any question that couldn't be answered",
    "parameters": {
        "type": "object",
        "properties": {
            "question": {"type": "string"},
        },
        "required": ["question"],
        "additionalProperties": False
    }
}

tools = [
    {"type": "function", "function": record_user_details_json},
    {"type": "function", "function": record_unknown_question_json}
]

class Me:
    def __init__(self):
        self.openai = OpenAI()
        self.name = "Tiina Siremaa"
        reader = PdfReader("me/linkedin.pdf")
        self.linkedin = ""
        for page in reader.pages:
            text = page.extract_text()
            if text:
                self.linkedin += text
        with open("me/summary.txt", "r", encoding="utf-8") as f:
            self.summary = f.read()

    def handle_tool_call(self, tool_calls):
        results = []
        for tool_call in tool_calls:
            tool_name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments)
            print(f"Tool called: {tool_name}", flush=True)
            tool = globals().get(tool_name)
            result = tool(**arguments) if tool else {}
            results.append({"role": "tool","content": json.dumps(result),"tool_call_id": tool_call.id})
        return results

    def system_prompt(self):
        system_prompt = f"You are {self.name}. Answer questions professionally and engagingly. " \
                        "If you don't know the answer, record it with record_unknown_question. " \
                        "Steer users to share their email and record it with record_user_details."
        system_prompt += f"\n\n## Summary:\n{self.summary}\n\n## LinkedIn Profile:\n{self.linkedin}\n\n"
        return system_prompt

    def chat(self, message, history):
        """Gradio chatbot expects a list of tuples [(user_msg, bot_msg), ...]"""
        # Convert Gradio tuple history to OpenAI message history
        openai_history = [{"role": "system", "content": self.system_prompt()}]
        for user_msg, bot_msg in history:
            openai_history.append({"role": "user", "content": user_msg})
            openai_history.append({"role": "assistant", "content": bot_msg})

        openai_history.append({"role": "user", "content": message})

        done = False
        while not done:
            response = self.openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=openai_history,
                tools=tools
            )
            if response.choices[0].finish_reason == "tool_calls":
                message_obj = response.choices[0].message
                tool_calls = message_obj.tool_calls
                results = self.handle_tool_call(tool_calls)
                openai_history.append(message_obj)
                openai_history.extend(results)
            else:
                done = True

        reply = response.choices[0].message.content
        history.append((message, reply))
        return history, history

if __name__ == "__main__":
    me = Me()

    with gr.Blocks() as demo:
        gr.Markdown("# 💬 Tiinan AI CV Chatbot")

        with gr.Row():
            with gr.Column(scale=3):
                chatbox = gr.Chatbot()
                msg = gr.Textbox(placeholder="Kirjoita viesti...")
                send_btn = gr.Button("Lähetä")
            with gr.Column(scale=1):
                gr.Markdown("### Info")
                gr.Markdown("Olen Tiina Siremaa, ohjelmistokehittäjä ja AI-harrastaja. "
                            "Kysy minulta urastani tai taidoistani!")

        chat_history = gr.State([])

        msg.submit(me.chat, inputs=[msg, chat_history], outputs=[chatbox, chat_history])
        send_btn.click(me.chat, inputs=[msg, chat_history], outputs=[chatbox, chat_history])

    demo.launch()



    