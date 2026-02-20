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
            "email": {
                "type": "string",
                "description": "The email address of this user"
            },
            "name": {
                "type": "string",
                "description": "The user's name, if they provided it"
            }
            ,
            "notes": {
                "type": "string",
                "description": "Any additional information about the conversation that's worth recording to give context"
            }
        },
        "required": ["email"],
        "additionalProperties": False
    }
}

record_unknown_question_json = {
    "name": "record_unknown_question",
    "description": "Always use this tool to record any question that couldn't be answered as you didn't know the answer",
    "parameters": {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "The question that couldn't be answered"
            },
        },
        "required": ["question"],
        "additionalProperties": False
    }
}

tools = [{"type": "function", "function": record_user_details_json},
        {"type": "function", "function": record_unknown_question_json}]


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
        system_prompt = f"You are acting as {self.name}. You are answering questions on {self.name}'s website, \
particularly questions related to {self.name}'s career, background, skills and experience. \
Your responsibility is to represent {self.name} for interactions on the website as faithfully as possible. \
You are given a summary of {self.name}'s background and LinkedIn profile which you can use to answer questions. \
Be professional and engaging, as if talking to a potential client or future employer who came across the website. \
If you don't know the answer to any question, use your record_unknown_question tool to record the question that you couldn't answer, even if it's about something trivial or unrelated to career. \
If the user is engaging in discussion, try to steer them towards getting in touch via email; ask for their email and record it using your record_user_details tool. "

        system_prompt += f"\n\n## Summary:\n{self.summary}\n\n## LinkedIn Profile:\n{self.linkedin}\n\n"
        system_prompt += f"With this context, please chat with the user, always staying in character as {self.name}."
        return system_prompt
    
    def chat(self, message, history):
        messages = [{"role": "system", "content": self.system_prompt()}] + history + [{"role": "user", "content": message}]
        done = False
        while not done:
            response = self.openai.chat.completions.create(model="gpt-4o-mini", messages=messages, tools=tools)
            if response.choices[0].finish_reason=="tool_calls":
                message = response.choices[0].message
                tool_calls = message.tool_calls
                results = self.handle_tool_call(tool_calls)
                messages.append(message)
                messages.extend(results)
            else:
                done = True
        return response.choices[0].message.content
    

if __name__ == "__main__":
    me = Me()

    custom_css = """
    .app-wrap { 
        max-width: 980px; 
        margin: 0 auto; 
        padding: 18px 18px 28px 18px;
    }

    .hero {
        border-radius: 18px;
        padding: 18px 18px;
        border: 1px solid rgba(0,0,0,.08);
        background: rgba(255,255,255,.72);
        backdrop-filter: blur(6px);
        margin-bottom: 14px;
    }

    .hero h1 { margin: 0 0 6px 0; font-size: 28px; line-height: 1.2; }
    .hero p { margin: 0; opacity: .88; }

    .meta {
        margin-top: 10px;
        display: flex;
        gap: 10px;
        flex-wrap: wrap;
        opacity: .92;
        font-size: 14px;
        align-items: center;
    }

    .pill {
        border: 1px solid rgba(0,0,0,.10);
        border-radius: 999px;
        padding: 6px 10px;
        background: rgba(255,255,255,.65);
        display: inline-flex;
        gap: 8px;
        align-items: center;
        text-decoration: none;
        color: inherit;
    }

    .cards-title { margin: 10px 0 8px 0; font-weight: 600; opacity: .9; }

    .qgrid button {
        width: 100%;
        text-align: left;
        border-radius: 14px !important;
        padding: 12px 12px !important;
        border: 1px solid rgba(0,0,0,.10) !important;
    }

    .footer {
        margin-top: 10px;
        opacity: .72;
        font-size: 12px;
    }
    """

    quick_questions = [
        "Kerro lyhyesti taustastasi ja vahvuuksistasi.",
        "Minkälaisiin rooleihin haet ja miksi?",
        "Mitä teknologioita käytät eniten ja missä olet vahvimmillasi?",
        "Millaisissa projekteissa olet ollut mukana?",
        "Miten sinuun saa parhaiten yhteyden?",
        "Miksi olisit hyvä tähän rooliin?",
    ]

    def send_quick(question, history):
        # ChatInterface/Chatbot history on Gradio 6.x:ssa yleensä "messages"-muodossa:
        # [{"role":"user"/"assistant","content":"..."}, ...]
        history = history or []

        assistant = me.chat(question, history)

        new_history = history + [
            {"role": "user", "content": question},
            {"role": "assistant", "content": assistant},
        ]

        # Päivitä chat + tyhjennä textbox
        return new_history, ""

    with gr.Blocks(theme=gr.themes.Soft(), css=custom_css) as demo:
        with gr.Column(elem_classes=["app-wrap"]):
            gr.HTML(
                """
                <div class="hero">
                  <h1>💬 Tiinan CV-chatbot</h1>
                  <p>Työnantajille: kysy minusta, osaamisestani ja projekteistani. Vastaan CV:n ja profiilitietojen pohjalta.</p>
                  <div class="meta">
                    <span class="pill">⚡ Pikakysymykset alla</span>
                    <a class="pill" href="https://www.linkedin.com/in/tiina-siremaa-7589a61b5/" target="_blank" rel="noopener noreferrer">
                      🔗 LinkedIn
                    </a>
                  </div>
                </div>
                """
            )

            gr.Markdown(
                "**Pikakysymykset (klikkaa → kysymys lähtee suoraan chattiin):**",
                elem_classes=["cards-title"]
            )

            with gr.Row(elem_classes=["qgrid"]):
                with gr.Column():
                    btns_left = [gr.Button(q) for q in quick_questions[::2]]
                with gr.Column():
                    btns_right = [gr.Button(q) for q in quick_questions[1::2]]

            chat = gr.ChatInterface(
                fn=me.chat,
                title=None,
                description=None,
                textbox=gr.Textbox(
                    placeholder="Kirjoita kysymys ja paina Enter…",
                    autofocus=True,
                ),
            )

            # Nappi -> suoraan vastaus chattiin
            for b in (btns_left + btns_right):
                b.click(
                    fn=send_quick,
                    inputs=[b, chat.chatbot],
                    outputs=[chat.chatbot, chat.textbox],
                )

            gr.HTML(
                """
                <div class="footer">
                  Vinkki: kysy konkreettisesti esim. “mitä teit viime projektissa?” tai “millaista arvoa tuot tiimiin?”.
                </div>
                """
            )

    demo.launch()