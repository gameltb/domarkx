import logging
import os
import subprocess

from domarkx.utils.agent_fs_map import resolve_virtual_path

from ..tool import register_tool


@register_tool("execute_command")
def execute_command_tool(command: str, cwd: str = None) -> str:
    """
    在系统上执行 CLI 命令。

    参数:
        command (str): 要执行的 CLI 命令。
        cwd (str): 命令的工作目录（默认为当前工作目录）。

    返回:
        str: 命令的 stdout 和 stderr 输出。

    抛出:
        TypeError: 如果 'command' 或 'cwd' 参数类型不正确。
        FileNotFoundError: 如果指定的工作目录不存在。
        NotADirectoryError: 如果指定的工作目录不是一个目录。
        RuntimeError: 如果命令执行失败（非零退出码）。
        Exception: 捕获其他未预料的错误。
    """
    logging.info(f"尝试执行命令: '{command}' 在目录 '{cwd if cwd else '.'}'。")

    if not isinstance(command, str):
        error_msg = f"参数 'command' 必须是字符串类型，但接收到 {type(command).__name__}。"
        logging.error(error_msg)
        raise TypeError(error_msg)

    if cwd is not None and not isinstance(cwd, str):
        error_msg = f"参数 'cwd' 必须是字符串类型或 None，但接收到 {type(cwd).__name__}。"
        logging.error(error_msg)
        raise TypeError(error_msg)

    if not cwd:
        cwd = "."
    resolved_cwd = resolve_virtual_path(cwd)
    if not os.path.exists(resolved_cwd):
        logging.error(f"指定的工作目录 '{cwd}' (resolved to '{resolved_cwd}') 不存在。")
        raise FileNotFoundError(f"指定的工作目录 '{cwd}' 不存在。")
    if not os.path.isdir(resolved_cwd):
        logging.error(f"指定的工作目录 '{cwd}' (resolved to '{resolved_cwd}') 不是一个目录。")
        raise NotADirectoryError(f"指定的工作目录 '{cwd}' 不是一个目录。")
    logging.info(f"命令的实际工作目录将是: '{resolved_cwd}'。")

    try:
        process = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=resolved_cwd,
            check=False,  # 我们将手动检查 returncode
        )

        output = f"--- 命令输出 (stdout) ---\n{process.stdout.strip()}\n" if process.stdout.strip() else ""
        if process.stderr:
            output += f"--- 命令错误 (stderr) ---\n{process.stderr.strip()}\n"

        if process.returncode != 0:
            error_msg = f"命令 '{command}' 执行失败，退出码: {process.returncode}.\n{output}"
            logging.error(error_msg)
            raise RuntimeError(error_msg)
        else:
            success_msg = f"命令 '{command}' 执行成功。\n{output}"
            logging.info(success_msg)
            return success_msg

    except FileNotFoundError as e:
        # 捕获的是 command 本身未找到的情况，而不是 cwd
        error_msg = f"命令 '{command.split()[0]}' 未找到。请确保它已安装并可执行: {e}"
        logging.error(error_msg)
        raise FileNotFoundError(error_msg)
    except PermissionError as e:
        error_msg = f"没有权限执行命令 '{command}' 或访问指定目录: {e}"
        logging.error(error_msg)
        raise PermissionError(error_msg)
    except Exception as e:
        error_msg = f"执行命令 '{command}' 时发生意外错误: {e}"
        logging.error(error_msg)
        raise Exception(error_msg)
