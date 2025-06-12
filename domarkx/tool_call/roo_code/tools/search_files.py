import logging
import os
import re
from typing import Optional

from domarkx.utils.agent_fs_map import resolve_virtual_path

from ..tool import register_tool


@register_tool("search_files")
def search_files_tool(path: str, regex: str, file_pattern: Optional[str] = None) -> str:
    """
    在指定目录下进行正则表达式搜索，提供上下文结果。

    参数:
        path (str): 要搜索的目录路径。
        regex (str): 正则表达式模式。
        file_pattern (str): 文件名 glob 模式（例如 '*.ts'）。

    返回:
        str: 搜索结果的格式化字符串。

    抛出:
        TypeError: 如果参数类型不正确。
        FileNotFoundError: 如果路径不存在。
        NotADirectoryError: 如果路径不是一个目录。
        ValueError: 如果正则表达式无效。
        Exception: 捕获其他未预料的错误。
    """
    logging.info(f"尝试在路径 '{path}' 中搜索文件。正则表达式: '{regex}', 文件模式: '{file_pattern}'。")
    virtual_path = path

    # 参数类型检查
    if not isinstance(path, str):
        raise TypeError(f"参数 'path' 必须是字符串类型，但接收到 {type(path).__name__}。")
    if not isinstance(regex, str):
        raise TypeError(f"参数 'regex' 必须是字符串类型，但接收到 {type(regex).__name__}。")
    if file_pattern is not None and not isinstance(file_pattern, str):
        raise TypeError(f"参数 'file_pattern' 必须是字符串类型或 None，但接收到 {type(file_pattern).__name__}。")

    path = resolve_virtual_path(path)
    logging.info(f"解析后的搜索目录路径: '{path}'。")

    if not os.path.exists(path):
        logging.error(f"路径 '{virtual_path}' (resolved to '{path}') 不存在。")
        raise FileNotFoundError(f"路径 '{virtual_path}' 不存在。")
    if not os.path.isdir(path):
        logging.error(f"路径 '{virtual_path}' (resolved to '{path}') 不是一个目录。")
        raise NotADirectoryError(f"路径 '{virtual_path}' 不是一个目录。")

    results = []
    try:
        compiled_regex = re.compile(regex)
        logging.info(f"成功编译正则表达式: '{regex}'。")
    except re.error as e:
        error_msg = f"无效的正则表达式 '{regex}': {e}"
        logging.error(error_msg)
        raise ValueError(error_msg)

    # 遍历目录并搜索文件
    for root, _, files in os.walk(path):
        for file_name in files:
            # 过滤文件模式
            if file_pattern:
                # 兼容 '*' 或 '*.ext' 模式
                if file_pattern.startswith("*."):
                    if not file_name.lower().endswith(file_pattern[1:].lower()):
                        continue
                elif file_pattern == "*":  # Match all files
                    pass
                elif file_name.lower() != file_pattern.lower():  # Exact match for filename
                    continue

            full_path = os.path.join(root, file_name)
            virtual_full_path = os.path.relpath(full_path, start=resolve_virtual_path("."))  # Display virtual path

            try:
                with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()

                file_has_match = False
                for i, line in enumerate(lines):
                    if compiled_regex.search(line):
                        if not file_has_match:  # Add file header only once per file
                            results.append(f"文件: {virtual_full_path}")
                            file_has_match = True

                        # 提供上下文
                        for j in range(max(0, i - 2), min(len(lines), i + 3)):
                            prefix = "--> " if j == i else "    "
                            results.append(f"{prefix}{j + 1} | {lines[j].rstrip()}")
                        results.append("")  # 空行分隔不同的匹配
                if file_has_match:
                    logging.info(f"在文件 '{virtual_full_path}' 中找到匹配项。")

            except PermissionError as e:
                warning_msg = f"警告: 没有权限读取文件 '{virtual_full_path}'。跳过。错误: {e}"
                logging.warning(warning_msg)
                results.append(warning_msg)
            except IOError as e:
                error_msg = f"读取文件 '{virtual_full_path}' 时发生 IO 错误。跳过。错误: {e}"
                logging.error(error_msg)
                results.append(error_msg)
            except Exception as e:
                error_msg = f"处理文件 '{virtual_full_path}' 时发生意外错误。跳过。错误: {e}"
                logging.error(error_msg)
                results.append(error_msg)

    if not results or all("警告:" in r or "错误:" in r for r in results):
        info_msg = f"在 '{virtual_path}' 中没有找到匹配 '{regex}' {'在文件模式 ' + file_pattern if file_pattern else ''} 的内容。"
        logging.info(info_msg)
        return info_msg

    logging.info(f"成功完成在 '{virtual_path}' 中的搜索。")
    return "\n".join(results)
