import logging
import os
import re
from typing import Optional

from domarkx.utils.agent_fs_map import resolve_virtual_path

from ..tool import register_tool


@register_tool("search_and_replace")
def search_and_replace_tool(
    path: str,
    search: str,
    replace: str,
    start_line: Optional[int] = None,
    end_line: Optional[int] = None,
    use_regex: bool = False,
    ignore_case: bool = False,
) -> str:
    """
    在文件中查找并替换文本字符串或模式。

    参数:
        path (str): 文件的路径。
        search (str): 要搜索的文本或模式。
        replace (str): 替换内容。
        start_line (int): 起始行号（1-based）。
        end_line (int): 结束行号（1-based，包含）。
        use_regex (bool): 是否将 search 作为正则表达式处理。
        ignore_case (bool): 是否忽略大小写。

    返回:
        str: 替换操作的结果信息和预览。

    抛出:
        TypeError: 如果参数类型不正确。
        FileNotFoundError: 如果文件不存在。
        IsADirectoryError: 如果路径是一个目录。
        PermissionError: 如果没有权限修改文件。
        ValueError: 如果行号范围无效或正则表达式无效。
        IOError: 如果文件读写发生错误。
        Exception: 捕获其他未预料的错误。
    """
    logging.info(f"尝试在文件 '{path}' 中查找和替换。搜索: '{search}', 替换: '{replace}'。")
    virtual_path = path

    # 参数类型检查
    if not isinstance(path, str):
        raise TypeError(f"参数 'path' 必须是字符串类型，但接收到 {type(path).__name__}。")
    if not isinstance(search, str):
        raise TypeError(f"参数 'search' 必须是字符串类型，但接收到 {type(search).__name__}。")
    if not isinstance(replace, str):
        raise TypeError(f"参数 'replace' 必须是字符串类型，但接收到 {type(replace).__name__}。")
    if start_line is not None and not isinstance(start_line, int):
        raise TypeError(f"参数 'start_line' 必须是整数类型或 None，但接收到 {type(start_line).__name__}。")
    if end_line is not None and not isinstance(end_line, int):
        raise TypeError(f"参数 'end_line' 必须是整数类型或 None，但接收到 {type(end_line).__name__}。")
    if not isinstance(use_regex, bool):
        raise TypeError(f"参数 'use_regex' 必须是布尔类型，但接收到 {type(use_regex).__name__}。")
    if not isinstance(ignore_case, bool):
        raise TypeError(f"参数 'ignore_case' 必须是布尔类型，但接收到 {type(ignore_case).__name__}。")

    path = resolve_virtual_path(path)
    logging.info(f"解析后的文件路径: '{path}'。")

    if not os.path.exists(path):
        logging.error(f"文件 '{virtual_path}' (resolved to '{path}') 不存在。")
        raise FileNotFoundError(f"文件 '{virtual_path}' 不存在。")
    if not os.path.isfile(path):
        logging.error(f"路径 '{virtual_path}' (resolved to '{path}') 是一个目录，不是文件。")
        raise IsADirectoryError(f"路径 '{virtual_path}' 是一个目录，不是文件。")

    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        logging.info(f"成功读取文件 '{virtual_path}' 的 {len(lines)} 行。")

        flags = 0
        if ignore_case:
            flags |= re.IGNORECASE

        try:
            search_pattern = re.compile(search, flags) if use_regex else re.compile(re.escape(search), flags)
            logging.info(
                f"成功编译搜索模式: '{search_pattern.pattern}' (use_regex={use_regex}, ignore_case={ignore_case})。"
            )
        except re.error as e:
            error_msg = f"无效的正则表达式 '{search}': {e}"
            logging.error(error_msg)
            raise ValueError(error_msg)  # 抛出 ValueError for invalid regex

        changes_made = 0
        diff_preview = []
        new_lines = []

        # 调整为0-based索引
        start_idx = (start_line - 1) if start_line is not None and start_line > 0 else 0
        end_idx = end_line if end_line is not None and end_line > 0 else len(lines)

        # 确保索引在有效范围内
        start_idx = max(0, min(start_idx, len(lines)))
        end_idx = max(0, min(end_idx, len(lines)))

        if start_idx >= end_idx and (
            start_line is not None or end_line is not None
        ):  # Check if any range was specified
            if len(lines) == 0:
                warning_msg = f"文件 '{virtual_path}' 为空，没有内容可查找和替换。"
                logging.warning(warning_msg)
                return warning_msg  # 返回警告而不是抛出错误，因为文件为空不是操作失败
            else:
                error_msg = f"指定的行范围 (从 {start_line} 到 {end_line}) 无效或为空，因为文件只有 {len(lines)} 行。没有内容被修改。"
                logging.error(error_msg)
                raise ValueError(error_msg)  # 抛出 ValueError for invalid range

        logging.info(f"将在文件 '{virtual_path}' 的行 {start_idx + 1} 到 {end_idx} 范围内进行查找和替换。")
        for i, line in enumerate(lines):
            if start_idx <= i < end_idx:
                new_line, num_subs = search_pattern.subn(replace, line)
                if num_subs > 0:
                    changes_made += num_subs
                    # 添加 diff 预览
                    diff_preview.append(f"-{i + 1} | {line.rstrip()}")
                    diff_preview.append(f"+{i + 1} | {new_line.rstrip()}")
                    new_lines.append(new_line)
                else:
                    new_lines.append(line)
            else:
                new_lines.append(line)

        if changes_made == 0:
            info_msg = f"在 '{virtual_path}' 中没有找到匹配 '{search}' 的内容，未进行替换。"
            logging.info(info_msg)
            return info_msg  # 返回信息而不是抛出错误，因为没有找到匹配项不是失败

        try:
            with open(path, "w", encoding="utf-8") as f:
                f.writelines(new_lines)
            logging.info(f"文件 '{virtual_path}' 中已完成 {changes_made} 处替换并保存。")

            return (
                f"文件 '{virtual_path}' 中已完成 {changes_made} 处替换。\n"
                f"修改预览:\n"
                f"{'=' * 20}\n"
                f"{chr(10).join(diff_preview)}\n"
                f"{'=' * 20}"
            )
        except PermissionError as e:
            error_msg = f"没有权限修改文件 '{virtual_path}': {e}"
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

    except FileNotFoundError as e:
        # Re-raise FileNotFoundError which is handled by the caller
        raise e
    except IsADirectoryError as e:
        # Re-raise IsADirectoryError which is handled by the caller
        raise e
    except Exception as e:
        error_msg = f"查找和替换文件 '{virtual_path}' 时发生意外错误: {e}"
        logging.error(error_msg)
        raise Exception(error_msg)
