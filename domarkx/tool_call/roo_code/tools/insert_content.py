import logging
import os

from domarkx.utils.agent_fs_map import resolve_virtual_path

from ..tool import register_tool


@register_tool("insert_content")
def insert_content_tool(path: str, line: int, content: str) -> str:
    """
    在文件的指定行插入内容。

    参数:
        path (str): 文件的路径。
        line (int): 要插入内容的行号（1-based）。0 表示追加到文件末尾。
        content (str): 要插入的内容。

    返回:
        str: 插入操作的结果信息。

    抛出:
        TypeError: 如果 'path', 'line', 'content' 参数类型不正确。
        ValueError: 如果 'line' 参数超出有效范围。
        FileNotFoundError: 如果文件不存在。
        IsADirectoryError: 如果路径是一个目录。
        IOError: 如果文件读写操作失败。
    """
    logging.info(f"尝试在文件 '{path}' 的第 {line} 行插入内容。")
    virtual_path = path
    path = resolve_virtual_path(path)

    # 参数类型检查
    if not isinstance(path, str):
        error_msg = f"参数 'path' 必须是字符串类型，但接收到 {type(path).__name__}。"
        logging.error(error_msg)
        raise TypeError(error_msg)
    if not isinstance(line, int):
        error_msg = f"参数 'line' 必须是整数类型，但接收到 {type(line).__name__}。"
        logging.error(error_msg)
        raise TypeError(error_msg)
    if not isinstance(content, str):
        error_msg = f"参数 'content' 必须是字符串类型，但接收到 {type(content).__name__}。"
        logging.error(error_msg)
        raise TypeError(error_msg)

    # 文件存在性检查
    if not os.path.exists(path):
        logging.error(f"文件 '{virtual_path}' 不存在。")
        raise FileNotFoundError(f"文件 '{virtual_path}' 不存在。")
    if not os.path.isfile(path):
        logging.error(f"路径 '{virtual_path}' 是一个目录，不是文件。")
        raise IsADirectoryError(f"路径 '{virtual_path}' 是一个目录，不是文件。")

    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        logging.info(f"成功读取文件 '{virtual_path}'。")
    except IOError as e:
        logging.error(f"读取文件 '{virtual_path}' 时发生 IO 错误: {e}")
        raise IOError(f"无法读取文件 '{virtual_path}': {e}")

    # 确保要插入的内容以换行符结束，除非它是空内容
    insert_content_normalized = content
    if content and not content.endswith("\n"):
        insert_content_normalized += "\n"

    content_lines = insert_content_normalized.splitlines(keepends=True)

    message = ""
    if line == 0:  # 追加到文件末尾
        lines.extend(content_lines)
        message = f"内容已追加到文件 '{virtual_path}' 的末尾。"
        logging.info(message)
    else:
        # 调整行号为0-based索引
        insert_idx = line - 1

        if not (0 <= insert_idx <= len(lines)):
            error_msg = (
                f"指定的行号 {line} 超出文件 '{virtual_path}' 的有效范围 (1 到 {len(lines) + 1}，或 0 表示末尾)。"
            )
            logging.error(error_msg)
            raise ValueError(error_msg)

        lines[insert_idx:insert_idx] = content_lines
        message = f"内容已插入到文件 '{virtual_path}' 的第 {line} 行。"
        logging.info(message)

    try:
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(lines)
        logging.info(f"成功将修改后的内容写入文件 '{virtual_path}'。")
        return message
    except PermissionError as e:
        error_msg = f"没有权限写入文件 '{virtual_path}': {e}"
        logging.error(error_msg)
        raise PermissionError(error_msg)
    except IOError as e:
        error_msg = f"写入文件 '{virtual_path}' 时发生 IO 错误: {e}"
        logging.error(error_msg)
        raise IOError(error_msg)
