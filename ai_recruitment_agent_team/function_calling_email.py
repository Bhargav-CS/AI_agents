from typing import Annotated, Optional
import autogen
import smtplib
from email.message import EmailMessage
import random

config_list = [
    {
        "model": "llama3.1",
        "api_key": "doesnotmatter",
        "base_url": "http://127.0.0.1:11434/v1",
    }
]

llm_config = {
    "config_list": config_list,
    "timeout": 120,
}

assistant = autogen.AssistantAgent(
    name="assistant",
    system_message="You are to draft and send personalized emails.",
    llm_config=llm_config,
)

user_proxy = autogen.UserProxyAgent(
    name="user_proxy",
    is_termination_msg=lambda x: x.get("content", "") and x.get("content", "").rstrip().endswith("TERMINATE"),
    human_input_mode="ALWAYS",
    max_consecutive_auto_reply=10,
    code_execution_config=False,
)

# Provide your sender details here
SENDER_NAME = "Bhargav Patki"
SENDER_EMAIL = "patkibhargav79@gmail.com"
SENDER_PASSKEY = "qwgb psqw gukm uumo"

def send_email(receiver_email: str, subject: str, body: str) -> str:
    if not receiver_email:
        return "error: No receiver email provided"

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"{SENDER_NAME} <{SENDER_EMAIL}>"
    msg["To"] = receiver_email
    msg.set_content(body)

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(SENDER_EMAIL, SENDER_PASSKEY)
            smtp.send_message(msg)
    except Exception as e:
        return f"error: {e}"
    return "email sent successfully"

@user_proxy.register_for_execution()
@assistant.register_for_llm(description="draft and send a personalized email")
def draft_and_send_email(data: Annotated[dict, "the email details including receiver_email, subject, and body"]) -> str:
    receiver_email = data.get("receiver_email")
    subject = data.get("subject")
    body = data.get("body")
    
    return send_email(receiver_email, subject, body)

group_chat = autogen.GroupChat(agents=[user_proxy, assistant], messages=[], max_round=12)
manager = autogen.GroupChatManager(groupchat=group_chat, llm_config=llm_config)

user_proxy.initiate_chats(
    [
        {
            "recipient": assistant,
            "message": "Draft and send an email patkibhargav@gmail.com to subject 'Welcome' and for the body of the email use warm message some quotes and some instructions for the next steps.",
            "clear_history": True,
            "silent": False,
            "summary_method": "last_msg",
        },
    ]
)