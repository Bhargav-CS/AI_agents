from typing import Annotated
import yfinance as yf
import autogen
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

assistant1 = autogen.AssistantAgent(
    name="assistant1",
    system_message="you are to save to a file",
    llm_config=llm_config,
)

assistant2 = autogen.AssistantAgent(
    name="assistant2",
    system_message="you are to save to a file",
    llm_config=llm_config,
)

user_proxy = autogen.UserProxyAgent(
    name="user_proxy",
    is_termination_msg=lambda x: x.get("content", "") and x.get("content", "").rstrip().endswith("TERMINATE"),
    human_input_mode="NEVER",
    max_consecutive_auto_reply=10,
    code_execution_config=False,
)

@user_proxy.register_for_execution()
@assistant1.register_for_llm(description="save to a file")
@assistant2.register_for_llm(description="save to a file")
def save_to_file(data: Annotated[str, "the response from the model"]) -> str:
    print(data)
    
    random_number = random.randint(1, 100)
    with open("saved_file_" + str(random_number) + ".txt", "w") as f:
        f.write(data)
    
    return data

group_chat = autogen.GroupChat(agents=[user_proxy, assistant1, assistant2], messages=[], max_round=12)
manager = autogen.GroupChatManager(groupchat=group_chat, llm_config=llm_config)


user_proxy.initiate_chats(
    [
        {
            "recipient": assistant1,
            "message": "Give a quote from a famous author",
            "clear_history": True,
            "silent": False,
            "summary_method": "last_msg",
        },
        {
            "recipient": assistant2,
            "message": "Give a quote from a different famous author, make sure it is not as same as the last function",
            "summary_method": "reflection_with_llm",
        },
    ]
)