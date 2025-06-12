import logging
import os

from domarkx.utils.agent_fs_map import resolve_virtual_path

from ..tool import register_tool


@register_tool("list_files")
def list_files_tool(path: str, recursive: bool = False) -> str:
    """
    列出指定目录下的文件和目录。

    参数:
        path (str): 要列出内容的目录路径。
        recursive (bool): 是否递归列出。

    返回:
        str: 目录内容的格式化字符串。

    抛出:
        TypeError: 如果 'path' 或 'recursive' 参数类型不正确。
        FileNotFoundError: 如果路径不存在。
        NotADirectoryError: 如果路径不是一个目录。
        PermissionError: 如果没有权限访问目录。
        Exception: 捕获其他未预料的错误。
    """
    logging.info(f"尝试列出 '{path}' 的文件和目录。递归模式: {recursive}。")
    virtual_path = path

    # 参数类型检查
    if not isinstance(path, str):
        error_msg = f"参数 'path' 必须是字符串类型，但接收到 {type(path).__name__}。"
        logging.error(error_msg)
        raise TypeError(error_msg)
    if not isinstance(recursive, bool):
        error_msg = f"参数 'recursive' 必须是布尔类型，但接收到 {type(recursive).__name__}。"
        logging.error(error_msg)
        raise TypeError(error_msg)

    path = resolve_virtual_path(path)

    if not os.path.exists(path):
        logging.error(f"路径 '{virtual_path}' (resolved to '{path}') 不存在。")
        raise FileNotFoundError(f"路径 '{virtual_path}' 不存在。")
    if not os.path.isdir(path):
        logging.error(f"路径 '{virtual_path}' (resolved to '{path}') 不是一个目录。")
        raise NotADirectoryError(f"路径 '{virtual_path}' 不是一个目录。")

    output_lines = [f"列出 '{virtual_path}' 的内容:"]

    try:
        if recursive:
            logging.info(f"递归列出目录 '{virtual_path}'。")
            for root, dirs, files in os.walk(path):
                relative_path = os.path.relpath(root, start=path)
                level = relative_path.count(os.sep) if relative_path != "." else 0
                indent = "    " * level

                # 排除特定的目录，如 __pycache__
                dirs[:] = [d for d in dirs if d not in ["__pycache__"]]  # 就地修改 dirs 列表以跳过这些目录

                dir_name = os.path.basename(root) if root != path else "."
                if dir_name not in ["__pycache__"]:  # 再次检查以防万一
                    output_lines.append(f"{indent}├── {dir_name}/")

                sub_indent = "    " * (level + 1)

                for d in sorted(dirs):
                    output_lines.append(f"{sub_indent}├── {d}/")

                # 过滤并打印文件
                sorted_files = sorted(files)
                for i, f in enumerate(sorted_files):
                    prefix = "└──" if i == len(sorted_files) - 1 else "├──"
                    output_lines.append(f"{sub_indent}{prefix} {f}")
        else:
            logging.info(f"非递归列出目录 '{virtual_path}'。")
            entries = os.listdir(path)
            # 过滤掉 __pycache__ 目录（非递归模式下）
            entries = [e for e in entries if e != "__pycache__"]

            sorted_entries = sorted(entries)
            for i, entry in enumerate(sorted_entries):
                full_path = os.path.join(path, entry)
                prefix = "└──" if i == len(sorted_entries) - 1 else "├──"
                if os.path.isdir(full_path):
                    output_lines.append(f"{prefix} {entry}/")
                else:
                    output_lines.append(f"{prefix} {entry}")
    except PermissionError as e:
        error_msg = f"没有权限访问目录 '{virtual_path}': {e}"
        logging.error(error_msg)
        raise PermissionError(error_msg)
    except Exception as e:
        error_msg = f"列出目录 '{virtual_path}' 时发生意外错误: {e}"
        logging.error(error_msg)
        raise Exception(error_msg)

    logging.info(f"成功列出 '{virtual_path}' 的内容。")
    return "\n".join(output_lines)
