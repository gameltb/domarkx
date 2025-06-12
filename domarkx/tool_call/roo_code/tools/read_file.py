import glob
import logging
import os
from typing import Optional

from domarkx.utils.agent_fs_map import resolve_virtual_path

from ..tool import register_tool


@register_tool("read_file")
def read_file_tool(path: str, start_line: int = None, end_line: int = None) -> str:
    """
    读取指定路径的文件内容。适用于检查已知或未知内容的文件。
    可指定 `start_line` 和 `end_line` 高效读取部分内容。
    支持通配符 `*` 来一次性读取多个文件（例如 `*.py`, `dir/*.md`）。
    当使用通配符时，`start_line` 和 `end_line` 参数将被忽略，将返回所有匹配文件的完整内容。

    参数:
        path (str): 要读取的文件路径，可包含通配符。
        start_line (int): (可选) 开始行号（1-based）。
        end_line (int): (可选) 结束行号（1-based，包含）。

    返回:
        str: 文件的内容，每行前缀行号。如果匹配到多个文件，则会显示每个文件的内容，并以文件名分隔。

    抛出:
        TypeError: 如果参数类型不正确。
        FileNotFoundError: 如果文件不存在。
        IsADirectoryError: 如果路径是一个目录。
        PermissionError: 如果没有权限读取文件。
        ValueError: 如果行号范围无效。
        IOError: 如果文件读写发生错误。
        Exception: 捕获其他未预料的错误。
    """
    logging.info(f"尝试读取文件: '{path}'。开始行: {start_line}, 结束行: {end_line}。")
    virtual_path = path

    # 参数类型检查
    if not isinstance(path, str):
        error_msg = f"参数 'path' 必须是字符串类型，但接收到 {type(path).__name__}。"
        logging.error(error_msg)
        raise TypeError(error_msg)
    if start_line is not None and not isinstance(start_line, int):
        error_msg = f"参数 'start_line' 必须是整数类型或 None，但接收到 {type(start_line).__name__}。"
        logging.error(error_msg)
        raise TypeError(error_msg)
    if end_line is not None and not isinstance(end_line, int):
        error_msg = f"参数 'end_line' 必须是整数类型或 None，但接收到 {type(end_line).__name__}。"
        logging.error(error_msg)
        raise TypeError(error_msg)

    # 定义一个内部函数来处理单个文件的读取逻辑
    def _read_single_file(file_path: str, s_line: Optional[int], e_line: Optional[int]) -> str:
        resolved_file_path = resolve_virtual_path(file_path)
        logging.info(f"正在读取单个文件: '{file_path}' (resolved to '{resolved_file_path}')。")

        if not os.path.exists(resolved_file_path):
            logging.error(f"文件 '{file_path}' 不存在。")
            raise FileNotFoundError(f"文件 '{file_path}' 不存在。")
        if not os.path.isfile(resolved_file_path):
            logging.error(f"路径 '{file_path}' 是一个目录，不是文件。")
            raise IsADirectoryError(f"路径 '{file_path}' 是一个目录，不是文件。")

        # 模拟PDF和DOCX处理
        if file_path.lower().endswith((".pdf", ".docx")):
            logging.warning(f"注意: '{file_path}' 是二进制文件 (PDF/DOCX)。此工具模拟提取原始文本。")
            return f"注意: '{file_path}' 是二进制文件 (PDF/DOCX)。此工具模拟提取原始文本，实际实现会使用相应库。\n模拟内容: 这是从 {file_path} 提取的文本内容。"

        try:
            with open(resolved_file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            logging.info(f"成功读取文件 '{file_path}' 的 {len(lines)} 行。")

            output_lines = []
            # 调整为0-based索引
            start_idx = (s_line - 1) if s_line is not None and s_line > 0 else 0
            end_idx = e_line if e_line is not None and e_line > 0 else len(lines)

            # 确保索引在有效范围内
            start_idx = max(0, min(start_idx, len(lines)))
            end_idx = max(0, min(end_idx, len(lines)))

            if start_idx >= end_idx and s_line is not None and e_line is not None:
                error_msg = (
                    f"指定的行范围 (从 {s_line} 到 {e_line}) 无效或为空，因为文件只有 {len(lines)} 行。没有内容被读取。"
                )
                logging.warning(error_msg)
                raise ValueError(error_msg)  # 抛出 ValueError 而不是返回字符串

            for i in range(start_idx, end_idx):
                output_lines.append(f"{i + 1} | {lines[i].rstrip('\n')}")

            logging.info(f"成功从文件 '{file_path}' 提取指定行内容。")
            return "\n".join(output_lines)
        except PermissionError as e:
            error_msg = f"没有权限读取文件 '{file_path}': {e}"
            logging.error(error_msg)
            raise PermissionError(error_msg)
        except IOError as e:
            error_msg = f"读取文件 '{file_path}' 时发生 IO 错误: {e}"
            logging.error(error_msg)
            raise IOError(error_msg)
        except Exception as e:
            error_msg = f"读取文件 '{file_path}' 时发生意外错误: {e}"
            logging.error(error_msg)
            raise Exception(error_msg)

    # 检查路径是否包含通配符
    if glob.has_magic(virtual_path):
        logging.info(f"路径 '{virtual_path}' 包含通配符，将处理多个文件。")
        dirname, basename = os.path.split(virtual_path)

        resolved_dirname = resolve_virtual_path(dirname) if dirname else resolve_virtual_path(".")
        if resolved_dirname is None:
            error_msg = f"无法解析通配符路径 '{virtual_path}' 的目录部分 '{dirname}'。"
            logging.error(error_msg)
            raise ValueError(error_msg)

        full_glob_pattern = os.path.join(resolved_dirname, basename)
        matching_files = glob.glob(full_glob_pattern)
        logging.info(f"找到 {len(matching_files)} 个匹配 '{virtual_path}' 的文件。")

        if not matching_files:
            warning_msg = f"警告: 未找到与通配符模式 '{virtual_path}' 匹配的文件。"
            logging.warning(warning_msg)
            return warning_msg  # 仍然返回警告，而不是抛出错误，因为这不一定是失败

        results = []
        for file_match in sorted(matching_files):
            try:
                # 忽略 start_line 和 end_line for wildcard matches
                file_content = _read_single_file(file_match, None, None)
                display_path = os.path.relpath(file_match, resolve_virtual_path("."))
                results.append(f"--- 文件: {display_path} ---\n{file_content}\n")
            except (FileNotFoundError, IsADirectoryError, PermissionError, IOError, ValueError, Exception) as e:
                logging.error(f"处理匹配文件 '{file_match}' 时发生错误: {e}")
                results.append(f"--- 文件: {file_match} ---\n错误: {e}\n")  # 记录错误但继续处理其他文件

        if not results:
            error_msg = f"所有匹配文件 '{virtual_path}' 都无法读取。"
            logging.error(error_msg)
            raise RuntimeError(error_msg)  # 如果所有文件都失败了，则抛出运行时错误

        logging.info(f"成功读取所有匹配 '{virtual_path}' 的文件。")
        return "\n".join(results)
    else:
        # 如果没有通配符，则回退到原来的单个文件读取逻辑
        return _read_single_file(virtual_path, start_line, end_line)
