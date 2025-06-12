import logging

from ..tool import register_tool


@register_tool("attempt_completion")
def attempt_completion_tool(result: str, command: str = None) -> str:
    """
    表示任务已完成，并提供结果和可选的展示命令。

    参数:
        result (str): 任务的最终结果描述。
        command (str): 用于展示结果的 CLI 命令。

    返回:
        str: 格式化后的完成信息字符串。

    抛出:
        TypeError: 如果 'result' 或 'command' 参数类型不正确。
    """
    logging.info("尝试构建任务完成信息。")

    if not isinstance(result, str):
        error_msg = f"参数 'result' 必须是字符串类型，但接收到 {type(result).__name__}。"
        logging.error(error_msg)
        raise TypeError(error_msg)

    if command is not None and not isinstance(command, str):
        error_msg = f"参数 'command' 必须是字符串类型或 None，但接收到 {type(command).__name__}。"
        logging.error(error_msg)
        raise TypeError(error_msg)

    command_tag = f"<command>{command}</command>\n" if command else ""

    formatted_completion = f"<attempt_completion>\n<result>\n{result}\n</result>\n{command_tag}</attempt_completion>"
    logging.info("成功格式化任务完成信息。")
    return formatted_completion
