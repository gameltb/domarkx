import io
import logging

from rich.console import Console

from ...utils.no_border_rich_tracebacks import NoBorderTraceback

REGISTERED_TOOLS = {}


# 初始化一个Console实例，输出到StringIO以捕获内容
console_output = io.StringIO()
console = Console(file=console_output, soft_wrap=True)


def register_tool(name: str):
    """
    一个装饰器，用于注册一个函数作为可执行工具。

    参数:
        name (str): 工具的名称（对应于XML标签名）。
    """

    def decorator(func):
        REGISTERED_TOOLS[name] = func
        return func

    return decorator


def execute_tool_call(tool_call: dict, return_traceback=False):
    """
    执行一个解析出的工具调用。

    参数:
        tool_call (dict): 由 parse_tool_calls 返回的单个工具调用字典。

    返回:
        tuple: (tool_name: str, result: str) 工具执行的结果。

    抛出:
        ValueError: 如果找不到对应的工具。
        TypeError: 如果参数类型不正确。
        RuntimeError: 如果工具执行时发生其他错误。
    """
    tool_name = tool_call.get("tool_name")
    parameters = tool_call.get("parameters", {})

    logging.info(f"正在尝试执行工具 '{tool_name}'，参数: {parameters}")

    if tool_name not in REGISTERED_TOOLS:
        error_msg = f"未找到工具 '{tool_name}'。"
        logging.error(error_msg)
        raise ValueError(error_msg)

    tool_func = REGISTERED_TOOLS[tool_name]

    # 将字符串参数转换为Python类型（例如，'true'/'false'转换为布尔值）
    processed_params = {}
    for param_name, param_value_str in parameters.items():
        if isinstance(param_value_str, str):
            if param_value_str.lower() == "true":
                processed_params[param_name] = True
            elif param_value_str.lower() == "false":
                processed_params[param_name] = False
            else:
                processed_params[param_name] = param_value_str
        else:
            processed_params[param_name] = param_value_str  # 如果不是字符串，则保留原样

    try:
        result = tool_func(**processed_params)
        logging.info(f"工具 '{tool_name}' 执行成功。")
        return tool_name, str(result)  # 确保返回工具名和字符串结果
    except TypeError as e:
        error_msg = f"工具 '{tool_name}' 的参数类型不正确或缺失: {e}"
        logging.error(error_msg, exc_info=True)  # exc_info=True 会在日志中包含异常信息
        console_output.truncate(0)
        console_output.seek(0)
        console.print(NoBorderTraceback(show_locals=True, extra_lines=1, max_frames=1))
        traceback_str = console_output.getvalue()
        return (
            tool_name,
            f"错误: {error_msg}\nTraceback:\n{'\n'.join([line.rstrip() for line in traceback_str.splitlines()])}",
        )
    except Exception as e:
        error_msg = f"执行工具 '{tool_name}' 时发生错误: {e}"
        logging.error(error_msg, exc_info=True)  # exc_info=True 会在日志中包含异常信息
        console_output.truncate(0)
        console_output.seek(0)
        console.print(NoBorderTraceback(show_locals=True, extra_lines=1, max_frames=1))
        traceback_str = console_output.getvalue()
        return (
            tool_name,
            f"错误: {error_msg}\n"
            + (
                "Traceback:\n{'\n'.join([line.rstrip() for line in traceback_str.splitlines()])}"
                if return_traceback
                else ""
            ),
        )


def format_assistant_response(tool_name: str, tool_result: str) -> str:
    """
    将工具执行结果格式化为助手的完整回复。

    参数:
        tool_name (str): 执行的工具的名称。
        tool_result (str): 工具执行返回的原始结果字符串。

    返回:
        str: 格式化后的助手回复字符串（XML 格式）。
    """
    # 确保XML内容中的特殊字符被转义，以避免解析问题
    # 这里为了简洁，仅对一些常见字符进行简单替换，实际生产级可能需要更全面的XML转义库
    # 但由于通常工具结果是纯文本，这种简单处理通常足够
    # tool_result_escaped = (
    #     tool_result.replace("&", "&amp;")
    #     .replace("<", "&lt;")
    #     .replace(">", "&gt;")
    #     .replace('"', "&quot;")
    #     .replace("'", "&apos;")
    # )

    # 鉴于工具返回的通常是多行文本，直接插入即可，外部系统会处理
    return f'<tool_output tool_name="{tool_name}">\n{tool_result}\n</tool_output>'
