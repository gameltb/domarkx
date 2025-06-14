import io
import logging
import re  # 新增导入

from rich.console import Console

from ...utils.no_border_rich_tracebacks import NoBorderTraceback
from ...utils.agent_fs_map import get_virtual_path

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


def _replace_paths_in_string(text: str) -> str:
    """
    在给定文本中查找并替换所有已映射的实际路径为虚拟路径。
    这会尝试匹配常见的Unix和Windows路径模式。
    """
    # 匹配可能的路径模式：
    # (?:[a-zA-Z]:[\\/]|[/])? - 可选的Windows盘符或Unix根目录
    # (?:[\\.]{1,2}[\\/])? - 可选的相对路径前缀 (./ or ../)
    # (?:[a-zA-Z0-9_\-. ]+[\\/]) - 一个或多个目录段，以斜杠结尾
    # [a-zA-Z0-9_\-. ]+ - 最终的文件名或目录名
    # 这个正则表达式旨在匹配常见的绝对路径、相对路径和裸路径片段
    path_regex = re.compile(
        r"(?:"  # Non-capturing group for path start
        r"(?:[a-zA-Z]:[\\/])|"  # Windows absolute path (e.g., C:\)
        r"(?:[\\.]{1,2}[\\/])|"  # Relative path (e.g., ./ or ../)
        r"[\\/]"  # Unix absolute path (e.g., /)
        r")?"  # Optional path start for bare paths (e.g., "my_file.txt" if mapped as a root)
        r"(?:[a-zA-Z0-9_\-. ]+[\\/])*"  # Zero or more directory segments (e.g., "dir1/dir2/")
        r"[a-zA-Z0-9_\-. ]+"  # Final file/directory name (e.g., "file.txt")
    )

    def _replacer(match):
        real_path = match.group(0)
        virtual_path = get_virtual_path(real_path)
        if virtual_path:
            # logging.debug(f"将实际路径 '{real_path}' 转换为虚拟路径 '{virtual_path}'")
            return virtual_path
        return real_path

    return path_regex.sub(_replacer, text)


def format_assistant_response(tool_name: str, tool_result: str) -> str:
    """
    将工具执行结果格式化为助手的完整回复。
    在返回结果之前，将 tool_result 中存在于 fs_map 中的实际路径转换为虚拟路径。
    """
    processed_tool_result = _replace_paths_in_string(tool_result)

    return f'<tool_output tool_name="{tool_name}">\n{processed_tool_result}\n</tool_output>'
