import autogen

config_list = [
    {
        "model": "doesnotmatter",
        "api_key": "doesnotmatter",
        "base_url": "http://127.0.0.1:1234/v1",
    }
]

assistant = autogen.AssistantAgent(
    name="assistant",
    llm_config={"config_list": config_list}
)

user_proxy = autogen.UserProxyAgent(
    name="user_proxy",
    code_execution_config={"work_dir": "coding", "use_docker": False},
)

task = """
generate a random number
"""

user_proxy.initiate_chat(
    assistant,
    message=task,
    
)

