import logging
import os

from domarkx.utils.agent_fs_map import resolve_virtual_path

from ..tool import register_tool


@register_tool("write_to_file")
def write_to_file_tool(path: str, content: str, line_count: int) -> str:
    """
    将完整内容写入文件。如果文件不存在，则创建。如果存在，则覆盖。

    参数:
        path (str): 要写入的文件的路径。
        content (str): 要写入的完整内容。
        line_count (int): 文件中的总行数（用于验证）。

    返回:
        str: 写入操作的结果信息。

    抛出:
        TypeError: 如果参数类型不正确。
        ValueError: 如果提供的 line_count 与实际内容不符。
        OSError: 如果目录创建或文件写入失败。
        PermissionError: 如果没有权限写入文件。
        IOError: 如果文件写入发生错误。
        Exception: 捕获其他未预料的错误。
    """
    logging.info(f"尝试将内容写入文件: '{path}'。期望行数: {line_count}。")
    virtual_path = path

    # 参数类型检查
    if not isinstance(path, str):
        raise TypeError(f"参数 'path' 必须是字符串类型，但接收到 {type(path).__name__}。")
    if not isinstance(content, str):
        raise TypeError(f"参数 'content' 必须是字符串类型，但接收到 {type(content).__name__}。")
    if not isinstance(line_count, int):
        raise TypeError(f"参数 'line_count' 必须是整数类型，但接收到 {type(line_count).__name__}。")

    actual_line_count = content.count("\n") + (
        1 if content.strip() else 0
    )  # Adjust for empty content or content without trailing newline
    if content and not content.endswith("\n"):  # If content ends without a newline, but has content, it's one line
        actual_line_count = content.count("\n") + 1
    elif not content:  # Empty content is 0 lines
        actual_line_count = 0

    if actual_line_count != line_count:
        error_msg = (
            f"提供的 'line_count' ({line_count}) 与实际内容行数 ({actual_line_count}) 不符。"
            f"请确保 'line_count' 精确反映 'content' 中的行数，包括尾随的换行符。"
        )
        logging.error(error_msg)
        raise ValueError(error_msg)

    rpath = resolve_virtual_path(path)
    logging.info(f"解析后的文件路径: '{rpath}'。")

    try:
        # 确保目录存在
        directory = os.path.dirname(rpath)
        if directory and not os.path.exists(directory):
            logging.info(f"创建目录: '{directory}'。")
            os.makedirs(directory)

        # 写入文件
        with open(rpath, "w", encoding="utf-8") as f:
            f.write(content)

        logging.info(f"文件 '{virtual_path}' 已成功写入，共 {actual_line_count} 行。")
        return f"文件 '{virtual_path}' 已成功写入，共 {actual_line_count} 行。"
    except PermissionError as e:
        error_msg = f"没有权限写入文件 '{virtual_path}': {e}"
        logging.error(error_msg)
        raise PermissionError(error_msg)
    except IOError as e:
        error_msg = f"写入文件 '{virtual_path}' 时发生 IO 错误: {e}"
        logging.error(error_msg)
        raise IOError(error_msg)
    except Exception as e:
        error_msg = f"写入文件 '{virtual_path}' 时发生意外错误: {e}"
        logging.error(error_msg)
        raise Exception(error_msg)
