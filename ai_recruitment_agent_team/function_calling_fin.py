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

assistant = autogen.AssistantAgent(
    name="assistant",
    system_message="You are to get the stock price of a company using its ticker symbol and save it to a file. Always output the ticker symbol directly.",
    llm_config=llm_config,
)

user_proxy = autogen.UserProxyAgent(
    name="user_proxy",
    is_termination_msg=lambda x: x.get("content", "") and x.get("content", "").rstrip().endswith("TERMINATE"),
    human_input_mode="ALWAYS",
    max_consecutive_auto_reply=10,
    code_execution_config=False,
)

@user_proxy.register_for_execution()
@assistant.register_for_llm(description="get the stock price of a company using ticker and save to a file")
def get_and_save_stock_price(ticker: Annotated[str, "the ticker symbol of the company"]) -> str:
    ticker = ticker.strip()
    
    stock = yf.Ticker(ticker)
    stock_price = stock.history(period="1d")['Close'][0]
    response = f"The stock price of {ticker} is {stock_price}"
    print(response)
    
    random_number = random.randint(1, 100)
    with open("saved_file_" + str(random_number) + ".txt", "w") as f:
        f.write(response)
    
    return response

group_chat = autogen.GroupChat(agents=[user_proxy, assistant], messages=[], max_round=12)
manager = autogen.GroupChatManager(groupchat=group_chat, llm_config=llm_config)

user_proxy.initiate_chats(
    [
        {
            "recipient": assistant,
            "message": "Get the stock price of microsoft and save it to a file",
            "clear_history": True,
            "silent": False,
            "summary_method": "last_msg",
        },
    ]
)