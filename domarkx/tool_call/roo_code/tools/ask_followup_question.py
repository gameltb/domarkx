import logging

from ..tool import register_tool


@register_tool("ask_followup_question")
def ask_followup_question_tool(question: str, follow_up: list) -> str:
    """
    向用户提问以收集额外信息。

    参数:
        question (str): 要问用户的问题。
        follow_up (list): 2-4 个建议答案的列表。

    返回:
        str: 格式化后的问题和建议答案字符串。

    抛出:
        ValueError: 如果 'follow_up' 参数格式不正确。
    """
    logging.info(f"正在准备向用户提问: '{question}'。")

    if not isinstance(follow_up, list):
        error_msg = "参数 'follow_up' 必须是一个列表。"
        logging.error(error_msg)
        raise ValueError(error_msg)

    if not (2 <= len(follow_up) <= 4):
        error_msg = f"参数 'follow_up' 必须包含 2 到 4 个建议答案，但接收到 {len(follow_up)} 个。"
        logging.error(error_msg)
        raise ValueError(error_msg)

    for item in follow_up:
        if not isinstance(item, str):
            error_msg = "参数 'follow_up' 中的所有建议答案必须是字符串。"
            logging.error(error_msg)
            raise ValueError(error_msg)

    suggest_tags = "\n".join([f"<suggest>{s}</suggest>" for s in follow_up])

    formatted_response = (
        f"<ask_followup_question>\n"
        f"<question>{question}</question>\n"
        f"<follow_up>\n{suggest_tags}\n</follow_up>\n"
        f"</ask_followup_question>"
    )
    logging.info("成功格式化问题和建议答案。")
    return formatted_response
