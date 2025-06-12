import ast
import importlib
import inspect
import logging
import os
import sys

from domarkx.utils.agent_fs_map import resolve_virtual_path

from ..tool import register_tool
from .read_file import read_file_tool  # Import read_file_tool to reuse its functionality


@register_tool("view_code_definition")
def view_code_definition_tool(path: str = None, name: str = None, symbol: str = None) -> str:
    """
    精确提取指定文件中某个具体代码定义（函数、类、方法）或给定符号的完整代码块和/或文档字符串。
    目前主要支持Python文件 (.py) 和Python符号。

    参数:
        path (str): 文件的路径。如果提供了 'symbol'，则此参数将被忽略。
        name (str): 在指定 'path' 的文件内要查找的代码定义的名称（例如函数名、类名或方法名）。
                    如果提供了 'symbol'，则此参数将被忽略。
        symbol (str): 要查看的Python模块、函数或类的完全限定符号名称（例如 'os.path.join', 'collections.deque'）。
                      如果提供了此参数，工具将尝试加载并获取该符号的源代码和/或文档字符串。

    返回:
        str: 指定代码定义的完整代码块和/或文档字符串，每行前缀行号（如果适用）。

    抛出:
        TypeError: 如果参数类型不正确。
        ValueError: 如果参数缺失、冲突或定义类型不支持。
        FileNotFoundError: 如果文件不存在。
        IsADirectoryError: 如果路径是一个目录。
        ImportError: 如果无法导入指定的符号。
        AttributeError: 如果符号中的对象不存在。
        SyntaxError: 如果Python文件存在语法错误。
        IOError: 如果文件读写发生错误。
        RuntimeError: 如果源代码不可用。
        Exception: 捕获其他未预料的错误。
    """
    logging.info(f"尝试查看代码定义。Path: '{path}', Name: '{name}', Symbol: '{symbol}'。")

    # 参数类型检查
    if path is not None and not isinstance(path, str):
        raise TypeError(f"参数 'path' 必须是字符串类型或 None，但接收到 {type(path).__name__}。")
    if name is not None and not isinstance(name, str):
        raise TypeError(f"参数 'name' 必须是字符串类型或 None，但接收到 {type(name).__name__}。")
    if symbol is not None and not isinstance(symbol, str):
        raise TypeError(f"参数 'symbol' 必须是字符串类型或 None，但接收到 {type(symbol).__name__}。")

    if symbol:
        if path is not None or name is not None:
            raise ValueError("当提供 'symbol' 参数时，'path' 和 'name' 必须为 None。")
        logging.info(f"通过符号名 '{symbol}' 查看定义。")
        try:
            obj = None
            if "." in symbol:
                module_name, obj_name = symbol.rsplit(".", 1)
                try:
                    module = importlib.import_module(module_name)
                except ImportError:
                    resolved_module_path = resolve_virtual_path(module_name.replace(".", os.sep) + ".py")
                    module_dir = os.path.dirname(resolved_module_path)
                    if module_dir and module_dir not in sys.path:
                        sys.path.insert(0, module_dir)
                        logging.info(f"添加 '{module_dir}' 到 sys.path。")
                    module = importlib.import_module(module_name)  # Retry import
                obj = getattr(module, obj_name)
            else:
                try:
                    obj = importlib.import_module(symbol)
                except ImportError:
                    resolved_symbol_path = resolve_virtual_path(symbol.replace(".", os.sep) + ".py")
                    symbol_dir = os.path.dirname(resolved_symbol_path)
                    if symbol_dir and symbol_dir not in sys.path:
                        sys.path.insert(0, symbol_dir)
                        logging.info(f"添加 '{symbol_dir}' 到 sys.path。")
                    obj = importlib.import_module(symbol)  # Retry import

            output = [f"--- 符号: {symbol} ---"]

            doc = inspect.getdoc(obj)
            if doc:
                output.append("--- 文档字符串 ---")
                output.append(doc)
                output.append("---")
                logging.info(f"获取到符号 '{symbol}' 的文档字符串。")
            else:
                logging.info(f"符号 '{symbol}' 没有文档字符串。")

            try:
                source_lines, start_lineno = inspect.getsourcelines(obj)
                output.append("--- 源代码 ---")
                for i, line in enumerate(source_lines):
                    output.append(f"{start_lineno + i} | {line.rstrip()}")
                logging.info(f"获取到符号 '{symbol}' 的源代码，共 {len(source_lines)} 行。")
            except TypeError:
                warning_msg = f"注意: 符号 '{symbol}' 的源代码不可用 (可能是内置模块或动态生成)。"
                logging.warning(warning_msg)
                output.append(warning_msg)
            except OSError as e:
                error_msg = f"错误: 无法获取符号 '{symbol}' 的源代码文件: {e}"
                logging.error(error_msg)
                output.append(error_msg)  # Append error to output, but still raise exception if it's critical
                raise OSError(error_msg)  # Re-raise for centralized error handling

            return "\n".join(output)

        except ImportError as e:
            logging.error(f"无法导入符号 '{symbol}': {e}")
            raise ImportError(f"无法导入符号 '{symbol}'。请确保该模块已安装并可访问: {e}")
        except AttributeError as e:
            logging.error(f"符号 '{symbol}' 中的对象不存在: {e}")
            raise AttributeError(f"符号 '{symbol}' 中的对象不存在: {e}")
        except Exception as e:
            logging.error(f"查看符号 '{symbol}' 时发生意外错误: {e}")
            raise Exception(f"查看符号 '{symbol}' 时发生错误: {e}")

    elif path and name:
        logging.info(f"通过文件路径 '{path}' 和名称 '{name}' 查看定义。")
        virtual_path = path
        path = resolve_virtual_path(path)

        if not os.path.exists(path):
            logging.error(f"文件 '{virtual_path}' 不存在。")
            raise FileNotFoundError(f"文件 '{virtual_path}' 不存在。")
        if not os.path.isfile(path):
            logging.error(f"路径 '{virtual_path}' 是一个目录，不是文件。")
            raise IsADirectoryError(f"路径 '{virtual_path}' 是一个目录，不是文件。")

        if not path.lower().endswith(".py"):
            warning_msg = f"文件 '{virtual_path}' 不是 Python 文件。目前只支持 Python 文件的详细定义查看。"
            logging.warning(warning_msg)
            # For non-Python files, just return a message, don't raise an error.
            return warning_msg

        try:
            with open(path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                file_content = "".join(lines)
            logging.info(f"成功读取文件 '{virtual_path}'。")
        except IOError as e:
            logging.error(f"读取文件 '{virtual_path}' 时发生 IO 错误: {e}")
            raise IOError(f"无法读取文件 '{virtual_path}': {e}")

        try:
            tree = ast.parse(file_content, filename=path)
            logging.info(f"成功解析文件 '{virtual_path}' 为 AST。")
        except SyntaxError as e:
            logging.error(f"文件 '{virtual_path}' 存在语法错误，无法解析: {e}")
            raise SyntaxError(f"文件 '{virtual_path}' 存在语法错误，无法解析: {e}")
        except Exception as e:
            logging.error(f"解析文件 '{virtual_path}' 为 AST 时发生意外错误: {e}")
            raise Exception(f"解析文件 '{virtual_path}' 为 AST 时发生错误: {e}")

        target_node = None
        # 添加父节点引用，方便 AST 遍历，如果未在其他地方添加的话
        for node_ast in ast.walk(tree):
            for child in ast.iter_child_nodes(node_ast):
                child.parent_node = node_ast

        # 找到目标节点（函数、类、方法）
        # 优化：优先匹配顶层定义，然后考虑方法
        for node_ast in ast.iter_child_nodes(tree):  # Only iterate top-level for initial search
            if isinstance(node_ast, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node_ast.name == name:
                target_node = node_ast
                break

        # If not found at top level, search within classes for methods
        if not target_node:
            for node_ast in ast.walk(tree):
                if isinstance(node_ast, ast.ClassDef):
                    for item in node_ast.body:
                        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == name:
                            # Verify if the method name is fully qualified like "ClassName.method_name"
                            # If so, we need to match both class and method name
                            if "." in name:
                                class_part, method_part = name.rsplit(".", 1)
                                if node_ast.name == class_part and item.name == method_part:
                                    target_node = item
                                    break
                            else:  # Assume it's a direct method name if not fully qualified
                                target_node = item
                                break
                    if target_node:
                        break

        if not target_node:
            error_msg = f"在文件 '{virtual_path}' 中未找到名为 '{name}' 的函数、类或方法定义。"
            logging.warning(error_msg)  # Use warning, as not finding is a valid outcome sometimes
            raise ValueError(error_msg)

        start_line_num = target_node.lineno
        logging.info(f"找到定义 '{name}'，从行 {start_line_num} 开始。")

        # 启发式地找到代码块的结束行
        # 找出目标节点代码块的最小缩进
        target_indent = 0
        if start_line_num <= len(lines):
            line_content = lines[start_line_num - 1]
            target_indent = len(line_content) - len(line_content.lstrip())

        end_line_candidate = start_line_num  # Start from the definition's first line
        # Iterate through the lines from the start_line_num onwards
        for i in range(start_line_num - 1, len(lines)):
            line_content = lines[i].rstrip("\n")
            current_indent = len(line_content) - len(line_content.lstrip())

            # If it's a completely empty line or a comment line, or if the indent matches or is deeper
            # than the target indent, it's part of the block or a valid continuation.
            if not line_content.strip() or line_content.lstrip().startswith("#") or current_indent >= target_indent:
                end_line_candidate = i + 1  # Update candidate to current line + 1 (1-based)
            else:
                # Found a line with shallower indent that is not empty/comment, so the block ended before this line
                break

        # If the block includes only decorators or empty lines, ensure at least one non-empty line
        # is included if the definition itself is a multi-line statement.
        # This heuristic tries to capture the entire logical block.
        # A more robust solution might require traversing the AST to find the last node's line number,
        # but that can be complex for comments/trailing empty lines.

        # Use read_file_tool to get the formatted content, it handles line numbering
        logging.info(f"估计定义 '{name}' 的代码块结束于行 {end_line_candidate}。调用 read_file_tool。")
        return read_file_tool(path=virtual_path, start_line=start_line_num, end_line=end_line_candidate)

    else:
        raise ValueError("必须提供 'path' 和 'name' 参数，或只提供 'symbol' 参数。")
