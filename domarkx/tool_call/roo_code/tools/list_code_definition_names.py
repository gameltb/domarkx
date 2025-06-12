import ast
import importlib
import inspect
import logging
import os
import sys

from domarkx.utils.agent_fs_map import resolve_virtual_path

from ..tool import register_tool


@register_tool("list_code_definition_names")
def list_code_definition_names_tool(path: str = None, symbol: str = None) -> str:
    """
    扫描文件、目录或指定符号，列出其中定义的函数、类、方法、变量等的名称。
    目前主要支持Python文件 (.py) 和Python符号。

    参数:
        path (str): 要扫描的文件或目录路径。如果提供了 'symbol'，则此参数将被忽略。
        symbol (str): 要检查的Python模块、包或对象的完全限定符号名称（例如 'os', 'os.path.join'）。
                      如果提供了此参数，工具将尝试加载并内省该符号。

    返回:
        str: 代码定义名称的格式化列表。

    抛出:
        ValueError: 如果 'path' 和 'symbol' 参数使用不正确。
        TypeError: 如果参数类型不正确。
        FileNotFoundError: 如果指定路径不存在。
        NotADirectoryError: 如果指定路径是目录但预期是文件。
        ImportError: 如果无法导入指定的符号。
        AttributeError: 如果符号中的对象不存在。
        IOError: 如果文件读写发生错误。
        SyntaxError: 如果Python文件存在语法错误。
        Exception: 捕获其他未预料的错误。
    """
    logging.info(f"尝试列出代码定义名称。Path: '{path}', Symbol: '{symbol}'。")
    results = []

    if (path is None and symbol is None) or (path is not None and symbol is not None):
        error_msg = "必须且只能提供 'path' 或 'symbol' 参数之一。"
        logging.error(error_msg)
        raise ValueError(error_msg)

    # 确保参数类型正确
    if path is not None and not isinstance(path, str):
        error_msg = f"参数 'path' 必须是字符串类型或 None，但接收到 {type(path).__name__}。"
        logging.error(error_msg)
        raise TypeError(error_msg)
    if symbol is not None and not isinstance(symbol, str):
        error_msg = f"参数 'symbol' 必须是字符串类型或 None，但接收到 {type(symbol).__name__}。"
        logging.error(error_msg)
        raise TypeError(error_msg)

    if symbol:
        logging.info(f"正在内省 Python 符号: {symbol}")
        results.append(f"正在内省符号: {symbol}")
        try:
            # 尝试导入符号
            obj = None
            if "." in symbol:
                module_name, obj_name = symbol.rsplit(".", 1)
                # 尝试导入模块，并确保其目录在 sys.path 中
                try:
                    module = importlib.import_module(module_name)
                except ImportError:
                    # 如果直接导入失败，尝试将其父目录添加到 sys.path
                    if os.path.exists(module_name.replace(".", os.sep) + ".py"):  # Check if it's a file path
                        module_dir = os.path.dirname(module_name.replace(".", os.sep))
                    else:  # Assume it's a package and try parent dir
                        module_parts = module_name.split(".")
                        module_dir = os.path.join(*module_parts[:-1]) if len(module_parts) > 1 else ""

                    # Resolve to actual path to add to sys.path
                    resolved_module_dir = resolve_virtual_path(module_dir if module_dir else "./")
                    if resolved_module_dir not in sys.path:
                        sys.path.insert(0, resolved_module_dir)
                        logging.info(f"添加 '{resolved_module_dir}' 到 sys.path。")
                    module = importlib.import_module(module_name)  # Retry import

                obj = getattr(module, obj_name)
            else:
                # 尝试导入模块，并确保其目录在 sys.path 中
                try:
                    obj = importlib.import_module(symbol)
                except ImportError:
                    # 如果直接导入失败，尝试将其父目录添加到 sys.path
                    resolved_symbol_path = resolve_virtual_path(symbol.replace(".", os.sep) + ".py")
                    symbol_dir = os.path.dirname(resolved_symbol_path)
                    if symbol_dir and symbol_dir not in sys.path:
                        sys.path.insert(0, symbol_dir)
                        logging.info(f"添加 '{symbol_dir}' 到 sys.path。")
                    obj = importlib.import_module(symbol)  # Retry import

            # 遍历对象成员
            for name, member in inspect.getmembers(obj):
                if name.startswith("__") and name.endswith("__"):
                    continue

                if inspect.isfunction(member):
                    # 检查函数是否属于当前符号的定义范围
                    if (
                        hasattr(member, "__module__")
                        and member.__module__
                        and (member.__module__ == symbol or member.__module__.startswith(f"{symbol}."))
                    ) or (
                        inspect.isclass(obj)
                        and hasattr(member, "__qualname__")
                        and member.__qualname__.startswith(f"{obj.__name__}.")
                    ):
                        results.append(f"  函数: {member.__qualname__}")
                elif inspect.isclass(member):
                    # 检查类是否属于当前符号的定义范围
                    if (
                        hasattr(member, "__module__")
                        and member.__module__
                        and (member.__module__ == symbol or member.__module__.startswith(f"{symbol}."))
                    ):
                        results.append(f"  类: {member.__qualname__}")
                elif not inspect.ismodule(member) and not inspect.isfunction(member) and not inspect.isclass(member):
                    # 启发式判断为成员（变量、常量等）
                    # 简单的 inspect.getmembers 会包含大量非代码定义项，此处仅列出少量
                    # 更精确的变量检测需要AST，但inspect无法直接提供。
                    # 暂时不对普通成员做过多过滤，除非agent明确要求
                    if not callable(member):  # 过滤掉所有可调用的对象
                        results.append(f"  成员: {name}")

        except ImportError as e:
            logging.error(f"无法导入符号 '{symbol}': {e}")
            raise ImportError(f"无法导入符号 '{symbol}'。请确保该模块已安装且可访问: {e}")
        except AttributeError as e:
            logging.error(f"符号 '{symbol}' 中的对象不存在: {e}")
            raise AttributeError(f"符号 '{symbol}' 中的对象不存在或无法访问: {e}")
        except Exception as e:
            logging.error(f"内省符号 '{symbol}' 时发生未知错误: {e}")
            raise Exception(f"内省符号 '{symbol}' 时发生错误: {e}")

        if len(results) <= 1:  # Only the initial "正在内省符号" message
            return f"符号 '{symbol}' 中没有找到明显的代码定义。"
        return "\n".join(results)

    elif path:
        virtual_path = path
        path = resolve_virtual_path(path)
        logging.info(f"正在扫描路径: {virtual_path} (resolved to {path})")

        if not os.path.exists(path):
            logging.error(f"路径 '{virtual_path}' 不存在。")
            raise FileNotFoundError(f"路径 '{virtual_path}' 不存在。")

        def process_file(file_path):
            file_definitions = []
            if not file_path.endswith(".py"):
                file_definitions.append(f"文件: {file_path} - (非Python文件，跳过详细定义解析)")
                logging.info(f"跳过非 Python 文件: {file_path}")
                return file_definitions

            logging.info(f"正在解析 Python 文件: {file_path}")
            file_definitions.append(f"文件: {file_path}")
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    file_content = f.read()
                tree = ast.parse(file_content, filename=file_path)

                # 添加父节点引用，方便 AST 遍历
                for node in ast.walk(tree):
                    for child in ast.iter_child_nodes(node):
                        child.parent_node = node

                # 定义 AST 访问器
                class DefinitionVisitor(ast.NodeVisitor):
                    def __init__(self):
                        self.definitions = []

                    def visit_FunctionDef(self, node):
                        self.definitions.append(f"  函数: {node.name} (行 {node.lineno})")
                        self.generic_visit(node)

                    def visit_AsyncFunctionDef(self, node):
                        self.definitions.append(f"  异步函数: {node.name} (行 {node.lineno})")
                        self.generic_visit(node)

                    def visit_ClassDef(self, node):
                        self.definitions.append(f"  类: {node.name} (行 {node.lineno})")
                        self.generic_visit(node)

                    def visit_Assign(self, node):
                        # 仅考虑模块级别的变量赋值
                        is_module_level = False
                        current = node
                        while hasattr(current, "parent_node"):
                            if isinstance(current.parent_node, ast.Module):
                                is_module_level = True
                                break
                            # 如果父节点是函数或类，则不是模块级别的
                            if isinstance(current.parent_node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                                break
                            current = current.parent_node

                        if is_module_level:
                            for target in node.targets:
                                if isinstance(target, ast.Name):
                                    self.definitions.append(f"  变量: {target.id} (行 {node.lineno})")
                        self.generic_visit(node)

                    # 我们可以选择是否添加对方法（函数内部的函数/类）的特殊处理
                    # 目前 AST 访问器会把它们作为嵌套函数/类处理，如果我们想明确区分，可以在 visit_ClassDef 内部进一步处理
                    # 但当前的 FunctionDef/AsyncFunctionDef 访问器会抓取所有函数，包括方法。
                    # 为了避免重复，我们只关注顶级定义。

                visitor = DefinitionVisitor()
                visitor.visit(tree)

                if not visitor.definitions:
                    file_definitions.append("  没有找到任何代码定义。")
                else:
                    file_definitions.extend(visitor.definitions)
            except SyntaxError as e:
                error_msg = f"解析文件 '{file_path}' 时发生语法错误: {e}"
                logging.error(error_msg)
                raise SyntaxError(error_msg)
            except IOError as e:
                error_msg = f"读取文件 '{file_path}' 时发生 IO 错误: {e}"
                logging.error(error_msg)
                raise IOError(error_msg)
            except Exception as e:
                error_msg = f"解析文件 '{file_path}' 时发生意外错误: {e}"
                logging.error(error_msg)
                raise Exception(error_msg)

            file_definitions.append("")  # 为每个文件添加空行分隔
            return file_definitions

        if os.path.isfile(path):
            results.extend(process_file(path))
        elif os.path.isdir(path):
            for root, _, files in os.walk(path):
                for file_name in files:
                    full_path = os.path.join(root, file_name)
                    # 捕获并记录 process_file 内部的异常，但继续处理其他文件
                    try:
                        results.extend(process_file(full_path))
                    except (SyntaxError, IOError, Exception) as e:
                        results.append(f"文件: {full_path} - 错误: {e}")
                        logging.warning(f"处理文件 '{full_path}' 时发生错误: {e}")
        else:
            error_msg = f"路径 '{virtual_path}' 既不是文件也不是目录。"
            logging.error(error_msg)
            raise ValueError(error_msg)

        if not results:
            return f"在 '{virtual_path}' 中没有找到任何文件或可解析的定义。"

        # 移除可能由于 process_file 内部错误导致重复的 "文件: xxx - 错误"
        # 实际的错误会通过异常抛出，这里只格式化成功的结果
        final_results = [line for line in results if not line.startswith("文件: ") or "错误: " not in line]
        if not final_results:
            return f"在 '{virtual_path}' 中没有找到任何可用的代码定义。"

        return "\n".join(final_results)
    else:
        # 理论上不会走到这里，因为前面已经检查了互斥性
        pass
