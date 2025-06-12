import ast
import logging
import os
from typing import Any, Optional

from domarkx.utils.agent_fs_map import resolve_virtual_path

from ..tool import register_tool


class ASTModifier(ast.NodeTransformer):
    """
    一个AST转换器，用于根据指定的动作修改Python代码的AST。
    支持重命名、添加、删除、更新函数/类定义的内容和签名，以及管理导入语句。
    """

    def __init__(self, action: str, **kwargs: Any):
        logging.info(f"初始化 ASTModifier，动作: '{action}', 参数: {kwargs}")
        self.action = action
        self.kwargs = kwargs
        self.modified_count = 0
        self.processed_nodes = (
            set()
        )  # To prevent double counting if a node is visited multiple times due to generic_visit

    def visit_FunctionDef(self, node: ast.FunctionDef):
        logging.debug(f"访问函数定义: {node.name}")
        # Process the node itself first, then visit its children
        if (
            node.name == self.kwargs.get("target_name", self.kwargs.get("old_name"))
            and self.kwargs.get("definition_type") == "function"
        ):
            if id(node) in self.processed_nodes:
                return self.generic_visit(node)  # Already processed this specific node instance

            logging.info(f"在行 {node.lineno} 找到目标函数 '{node.name}'，准备执行 '{self.action}' 操作。")
            if self.action == "rename_definition":
                new_name = self.kwargs["new_name"]
                logging.info(f"重命名函数 '{node.name}' 为 '{new_name}'。")
                node.name = new_name
                self.modified_count += 1
            elif self.action == "remove_definition":
                logging.info(f"移除函数 '{node.name}'。")
                self.modified_count += 1
                return None  # Remove the node
            elif self.action == "update_definition_body":
                new_body_code = self.kwargs["new_content"]
                logging.info(f"更新函数 '{node.name}' 的主体。")
                try:
                    dummy_func_code = f"def _dummy_func():\n{new_body_code}"
                    dummy_tree = ast.parse(dummy_func_code)
                    if not (
                        isinstance(dummy_tree.body[0], ast.FunctionDef) and dummy_tree.body[0].name == "_dummy_func"
                    ):
                        raise ValueError("Provided 'new_content' for body update is not a valid function body.")
                    node.body = dummy_tree.body[0].body
                    self.modified_count += 1
                except SyntaxError as e:
                    logging.error(f"解析函数 '{node.name}' 的新主体时发生语法错误: {e}")
                    raise SyntaxError(f"解析函数 '{node.name}' 的新主体时发生语法错误: {e}")
                except IndexError:
                    logging.error(f"提供的 'new_content' 无法解析为有效的函数主体。")
                    raise ValueError(f"提供的 'new_content' 无法解析为有效的函数主体。")
            elif self.action == "update_signature":
                new_signature_code = self.kwargs["new_content"]
                logging.info(f"更新函数 '{node.name}' 的签名。")
                try:
                    dummy_tree = ast.parse(new_signature_code)
                    if not (
                        isinstance(dummy_tree.body[0], ast.FunctionDef) and dummy_tree.body[0].name == "dummy_name"
                    ):  # Check name too for safety
                        raise ValueError(
                            "Provided 'new_content' for signature update is not a valid function definition."
                        )
                    dummy_func = dummy_tree.body[0]
                    node.args = dummy_func.args
                    node.returns = dummy_func.returns
                    node.type_comment = dummy_func.type_comment
                    # Decorators are tricky: assuming new_content includes full signature, decorators are implicitly replaced if present.
                    # For a simple signature update, we don't touch decorators.
                    # If the user wants to change decorators, they'd use `update_definition_body` or `add_definition`.
                    node.decorator_list = dummy_func.decorator_list  # Update decorators as well
                    self.modified_count += 1
                except SyntaxError as e:
                    logging.error(f"解析函数 '{node.name}' 的新签名时发生语法错误: {e}")
                    raise SyntaxError(f"解析函数 '{node.name}' 的新签名时发生语法错误: {e}")
                except IndexError:
                    logging.error(f"提供的 'new_content' 无法解析为有效的函数签名。")
                    raise ValueError(f"提供的 'new_content' 无法解析为有效的函数签名。")
            self.processed_nodes.add(id(node))
        return self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        logging.debug(f"访问类定义: {node.name}")
        # Process the node itself first, then visit its children
        if (
            node.name == self.kwargs.get("target_name", self.kwargs.get("old_name"))
            and self.kwargs.get("definition_type") == "class"
        ):
            if id(node) in self.processed_nodes:
                return self.generic_visit(node)

            logging.info(f"在行 {node.lineno} 找到目标类 '{node.name}'，准备执行 '{self.action}' 操作。")
            if self.action == "rename_definition":
                new_name = self.kwargs["new_name"]
                logging.info(f"重命名类 '{node.name}' 为 '{new_name}'。")
                node.name = new_name
                self.modified_count += 1
            elif self.action == "remove_definition":
                logging.info(f"移除类 '{node.name}'。")
                self.modified_count += 1
                return None  # Remove the node
            elif self.action == "update_definition_body":
                new_body_code = self.kwargs["new_content"]
                logging.info(f"更新类 '{node.name}' 的主体。")
                try:
                    dummy_class_code = f"class _DummyClass:\n{new_body_code}"
                    dummy_tree = ast.parse(dummy_class_code)
                    if not (isinstance(dummy_tree.body[0], ast.ClassDef) and dummy_tree.body[0].name == "_DummyClass"):
                        raise ValueError("Provided 'new_content' for body update is not a valid class body.")
                    node.body = dummy_tree.body[0].body
                    self.modified_count += 1
                except SyntaxError as e:
                    logging.error(f"解析类 '{node.name}' 的新主体时发生语法错误: {e}")
                    raise SyntaxError(f"解析类 '{node.name}' 的新主体时发生语法错误: {e}")
                except IndexError:
                    logging.error(f"提供的 'new_content' 无法解析为有效的类主体。")
                    raise ValueError(f"提供的 'new_content' 无法解析为有效的类主体。")
            elif self.action == "update_signature":
                new_signature_code = self.kwargs["new_content"]
                logging.info(f"更新类 '{node.name}' 的签名。")
                try:
                    dummy_tree = ast.parse(new_signature_code)
                    if not (
                        isinstance(dummy_tree.body[0], ast.ClassDef) and dummy_tree.body[0].name == "DummyClass"
                    ):  # Check name too for safety
                        raise ValueError("Provided 'new_content' for signature update is not a valid class definition.")
                    dummy_class = dummy_tree.body[0]
                    node.bases = dummy_class.bases
                    node.keywords = dummy_class.keywords
                    node.decorator_list = dummy_class.decorator_list  # Update decorators as well
                    self.modified_count += 1
                except SyntaxError as e:
                    logging.error(f"解析类 '{node.name}' 的新签名时发生语法错误: {e}")
                    raise SyntaxError(f"解析类 '{node.name}' 的新签名时发生语法错误: {e}")
                except IndexError:
                    logging.error(f"提供的 'new_content' 无法解析为有效的类签名。")
                    raise ValueError(f"提供的 'new_content' 无法解析为有效的类签名。")
            self.processed_nodes.add(id(node))
        return self.generic_visit(node)

    def visit_Module(self, node: ast.Module):
        logging.debug("访问模块节点。")
        # Handle add_definition
        if self.action == "add_definition" and self.kwargs.get("new_content"):
            new_def_code = self.kwargs["new_content"]
            definition_type = self.kwargs.get("definition_type")
            logging.info(f"尝试在模块中添加新的 '{definition_type}' 定义。")
            try:
                new_ast_node = ast.parse(new_def_code).body[0]

                if (isinstance(new_ast_node, ast.FunctionDef) and definition_type == "function") or (
                    isinstance(new_ast_node, ast.ClassDef) and definition_type == "class"
                ):
                    current_names = {n.name for n in node.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
                    if new_ast_node.name in current_names:
                        logging.error(f"定义 '{new_ast_node.name}' 已存在于模块中。")
                        raise ValueError(f"定义 '{new_ast_node.name}' 已存在。")

                    node.body.append(new_ast_node)  # Append at the end of the module
                    self.modified_count += 1
                    logging.info(f"成功添加新的 {definition_type} 定义 '{new_ast_node.name}'。")
                else:
                    logging.error(f"提供的 'new_content' 不是有效的 {definition_type} 定义。")
                    raise ValueError(f"提供的 'new_content' 不是有效的 {definition_type} 定义。")
            except SyntaxError as e:
                logging.error(f"解析 'new_content' 时发生语法错误: {e}")
                raise SyntaxError(f"解析 'new_content' 时发生语法错误: {e}")
            except IndexError:
                logging.error("提供的 'new_content' 无法解析为有效的 AST 节点。")
                raise ValueError("提供的 'new_content' 无法解析为有效的 AST 节点。")

        # Handle add_import
        if self.action == "add_import" and self.kwargs.get("import_statement"):
            import_code = self.kwargs["import_statement"]
            logging.info(f"尝试在模块中添加导入语句: '{import_code}'。")
            try:
                new_import_node = ast.parse(import_code).body[0]
                if isinstance(new_import_node, (ast.Import, ast.ImportFrom)):
                    import_exists = False
                    for existing_node in node.body:
                        # Simple check for exact match of import statement
                        if ast.dump(existing_node) == ast.dump(new_import_node):
                            import_exists = True
                            break

                    if import_exists:
                        logging.warning(f"导入语句 '{import_code}' 已存在。")
                        raise ValueError(f"导入语句 '{import_code}' 已存在。")
                    else:
                        insert_idx = 0
                        for i, stmt in enumerate(node.body):
                            if not isinstance(stmt, (ast.Import, ast.ImportFrom)):
                                insert_idx = i
                                break
                        node.body.insert(insert_idx, new_import_node)
                        self.modified_count += 1
                        logging.info(f"成功添加导入语句 '{import_code}'。")
                else:
                    logging.error("提供的 'import_statement' 不是有效的导入语句。")
                    raise ValueError("提供的 'import_statement' 不是有效的导入语句。")
            except SyntaxError as e:
                logging.error(f"解析导入语句时发生语法错误: {e}")
                raise SyntaxError(f"解析导入语句时发生语法错误: {e}")
            except IndexError:
                logging.error("提供的 'import_statement' 无法解析为有效的 AST 节点。")
                raise ValueError("提供的 'import_statement' 无法解析为有效的 AST 节点。")

        # Handle remove import
        if self.action == "remove_import" and self.kwargs.get("target_name"):
            target_name = self.kwargs["target_name"]
            target_type = self.kwargs.get("definition_type")
            logging.info(f"尝试从模块中移除导入: '{target_name}' (类型: {target_type})。")

            new_body = []
            removed_count_before_visit = self.modified_count
            found_import_to_remove = False

            for stmt in node.body:
                if isinstance(stmt, ast.Import):
                    if target_type == "module" and any(alias.name == target_name for alias in stmt.names):
                        logging.info(f"移除导入语句: {ast.dump(stmt)}")
                        self.modified_count += 1
                        found_import_to_remove = True
                        continue
                    else:
                        new_body.append(stmt)
                elif isinstance(stmt, ast.ImportFrom):
                    if target_type == "module" and stmt.module == target_name:  # Matches 'from target_name import ...'
                        logging.info(f"移除 from-import 语句 (模块): {ast.dump(stmt)}")
                        self.modified_count += 1
                        found_import_to_remove = True
                        continue
                    elif (
                        target_type == "symbol"
                        and stmt.module
                        and any(alias.name == target_name for alias in stmt.names)
                    ):
                        new_names = [alias for alias in stmt.names if alias.name != target_name]
                        if new_names:
                            stmt.names = new_names
                            new_body.append(stmt)
                            self.modified_count += 1
                            logging.info(f"从 '{stmt.module}' 导入中移除符号 '{target_name}'。")
                        else:  # All symbols removed, remove the entire import statement
                            self.modified_count += 1
                            logging.info(f"移除 from-import 语句 (所有符号): {ast.dump(stmt)}")
                        found_import_to_remove = True
                        continue
                    else:
                        new_body.append(stmt)
                else:
                    new_body.append(stmt)
            node.body = new_body

            if not found_import_to_remove:  # Check if any import was actually removed
                logging.warning(f"未找到要删除的导入 '{target_name}' (类型: {target_type})。")
                raise ValueError(f"未找到要删除的导入 '{target_name}' (类型: {target_type})。")
            logging.info(f"成功移除导入或符号 '{target_name}'。")

        return self.generic_visit(node)


@register_tool("modify_python_ast")
def modify_python_ast_tool(
    path: str,
    action: str,
    definition_type: Optional[str] = None,  # "function", "class", "module", "symbol"
    old_name: Optional[str] = None,  # For rename
    new_name: Optional[str] = None,  # For rename
    target_name: Optional[str] = None,  # For remove, update_definition_body, update_signature, remove_import
    new_content: Optional[str] = None,  # For add_definition, update_definition_body, update_signature
    import_statement: Optional[str] = None,  # For add_import
) -> str:
    """
    使用 Python 的抽象语法树（AST）功能，对 Python 代码进行结构性修改。
    此工具能够精确地重命名、添加、删除、更新文件中的顶级函数或类定义的内容和签名，以及管理导入语句。

    参数:
        path (str): 要修改的 Python 文件的路径。
        action (str): 要执行的 AST 修改类型。
                      支持的值: "rename_definition", "add_definition", "remove_definition",
                                "update_definition_body", "update_signature",
                                "add_import", "remove_import"
        definition_type (str, 可选): 要操作的定义类型。
                                   当 action 为 "rename_definition", "add_definition", "remove_definition",
                                   "update_definition_body", "update_signature" 时，支持 "function", "class"。
                                   当 action 为 "remove_import" 时，支持 "module", "symbol"。
        old_name (str, 可选): 目标函数或类的当前名称。
                            当 action 为 "rename_definition" 时必填。
        new_name (str, 可选): 目标函数或类的新名称。
                            当 action 为 "rename_definition" 时必填。
        target_name (str, 可选): 要操作（删除、修改内容、修改签名）的函数、类或导入的名称。
                                 当 action 为 "remove_definition", "update_definition_body",
                                 "update_signature", "remove_import" 时必填。
        new_content (str, 可选):
            - 当 action 为 "add_definition" 时，是完整的新函数或类代码字符串。
            - 当 action 为 "update_definition_body" 时，是新的函数或类的 **主体内容** 字符串，需正确缩进。
              例如，对于 `def f(): pass`，其主体内容为 `    pass`。
            - 当 action 为 "update_signature" 时，是新的函数或类的 **签名部分** 字符串，需包含完整的 def/class 行。
              例如，对于 `def f(a: int, b: str) -> None:` 或 `class MyClass(Parent):`。
            这些内容都应为有效且独立的 Python 代码片段。
        import_statement (str, 可选): 要添加的完整导入语句，例如 "import os" 或 "from collections import deque"。
                                     当 action 为 "add_import" 时必填。
                                     注意：应为有效且独立的 Python 导入语句。

    返回:
        str: 操作的结果信息，例如成功消息、错误详情，或者修改的摘要。

    抛出:
        TypeError: 如果参数类型不正确。
        ValueError: 如果参数缺失、无效或操作失败。
        FileNotFoundError: 如果文件不存在。
        IsADirectoryError: 如果路径是一个目录。
        IOError: 如果文件读写发生错误。
        SyntaxError: 如果Python文件存在语法错误。
        RuntimeError: 如果 Python 版本不支持 ast.unparse。
        Exception: 捕获其他未预料的错误。
    """
    logging.info(f"调用 modify_python_ast 工具，path='{path}', action='{action}'。")
    virtual_path = path

    # 参数类型检查
    if not isinstance(path, str):
        raise TypeError(f"参数 'path' 必须是字符串类型，但接收到 {type(path).__name__}。")
    if not isinstance(action, str):
        raise TypeError(f"参数 'action' 必须是字符串类型，但接收到 {type(action).__name__}。")
    if definition_type is not None and not isinstance(definition_type, str):
        raise TypeError(f"参数 'definition_type' 必须是字符串类型或 None，但接收到 {type(definition_type).__name__}。")
    if old_name is not None and not isinstance(old_name, str):
        raise TypeError(f"参数 'old_name' 必须是字符串类型或 None，但接收到 {type(old_name).__name__}。")
    if new_name is not None and not isinstance(new_name, str):
        raise TypeError(f"参数 'new_name' 必须是字符串类型或 None，但接收到 {type(new_name).__name__}。")
    if target_name is not None and not isinstance(target_name, str):
        raise TypeError(f"参数 'target_name' 必须是字符串类型或 None，但接收到 {type(target_name).__name__}。")
    if new_content is not None and not isinstance(new_content, str):
        raise TypeError(f"参数 'new_content' 必须是字符串类型或 None，但接收到 {type(new_content).__name__}。")
    if import_statement is not None and not isinstance(import_statement, str):
        raise TypeError(
            f"参数 'import_statement' 必须是字符串类型或 None，但接收到 {type(import_statement).__name__}。"
        )

    path = resolve_virtual_path(path)
    logging.info(f"解析后的文件路径: '{path}'。")

    if not os.path.exists(path):
        logging.error(f"文件 '{virtual_path}' (resolved to '{path}') 不存在。")
        raise FileNotFoundError(f"文件 '{virtual_path}' 不存在。")
    if not os.path.isfile(path):
        logging.error(f"路径 '{virtual_path}' (resolved to '{path}') 是一个目录，不是文件。")
        raise IsADirectoryError(f"路径 '{virtual_path}' 是一个目录，不是文件。")
    if not path.lower().endswith(".py"):
        logging.error(f"文件 '{virtual_path}' 不是一个 Python 文件 (.py)。")
        raise ValueError(f"文件 '{virtual_path}' 不是一个 Python 文件 (.py)。")

    try:
        with open(path, "r", encoding="utf-8") as f:
            original_code = f.read()
        logging.info(f"成功读取文件 '{virtual_path}' 内容。")
    except IOError as e:
        logging.error(f"读取文件 '{virtual_path}' 时发生 IO 错误: {e}")
        raise IOError(f"无法读取文件 '{virtual_path}': {e}")
    except Exception as e:
        logging.error(f"读取文件 '{virtual_path}' 时发生未知错误: {e}")
        raise Exception(f"读取文件 '{virtual_path}' 时发生错误: {e}")

    try:
        tree = ast.parse(original_code)
        # Add parent node references for easier traversal in ASTModifier
        for node_ast in ast.walk(tree):
            for child in ast.iter_child_nodes(node_ast):
                child.parent_node = node_ast
        logging.info("成功解析 Python 文件为 AST。")
    except SyntaxError as e:
        logging.error(f"解析 Python 文件 '{virtual_path}' 时发生语法错误: {e}")
        raise SyntaxError(f"解析 Python 文件 '{virtual_path}' 时发生语法错误: {e}")
    except Exception as e:
        logging.error(f"解析 Python 文件 '{virtual_path}' 为 AST 时发生未知错误: {e}")
        raise Exception(f"解析 Python 文件 '{virtual_path}' 为 AST 时发生错误: {e}")

    modifier_kwargs = {}
    result_message = ""

    # Validate parameters based on action
    if action == "rename_definition":
        if not all([definition_type, old_name, new_name]):
            raise ValueError(
                "对于 'rename_definition' 动作，'definition_type', 'old_name', 和 'new_name' 都是必填参数。"
            )
        if definition_type not in ["function", "class"]:
            raise ValueError(f"不支持的 definition_type '{definition_type}'。支持 'function' 或 'class'。")
        modifier_kwargs.update(
            definition_type=definition_type, target_name=old_name, new_name=new_name
        )  # target_name used for lookup in ASTModifier
        result_message = f"成功: 已在文件 '{virtual_path}' 中将 {definition_type} '{old_name}' 重命名为 '{new_name}'。"

    elif action == "add_definition":
        if not all([definition_type, new_content]):
            raise ValueError("对于 'add_definition' 动作，'definition_type' 和 'new_content' 都是必填参数。")
        if definition_type not in ["function", "class"]:
            raise ValueError(f"不支持的 definition_type '{definition_type}'。支持 'function' 或 'class'。")
        modifier_kwargs.update(definition_type=definition_type, new_content=new_content)
        result_message = f"成功: 已在文件 '{virtual_path}' 中添加新的 {definition_type} 定义。"

    elif action == "remove_definition":
        if not all([definition_type, target_name]):
            raise ValueError("对于 'remove_definition' 动作，'definition_type' 和 'target_name' 都是必填参数。")
        if definition_type not in ["function", "class"]:
            raise ValueError(f"不支持的 definition_type '{definition_type}'。支持 'function' 或 'class'。")
        modifier_kwargs.update(definition_type=definition_type, target_name=target_name)
        result_message = f"成功: 已在文件 '{virtual_path}' 中删除 {definition_type} '{target_name}'。"

    elif action == "update_definition_body":
        if not all([definition_type, target_name, new_content]):
            raise ValueError(
                "对于 'update_definition_body' 动作，'definition_type', 'target_name', 和 'new_content' 都是必填参数。"
            )
        if definition_type not in ["function", "class"]:
            raise ValueError(f"不支持的 definition_type '{definition_type}'。支持 'function' 或 'class'。")
        # Ensure new_content is indented for body parsing by ASTModifier
        indented_new_content = "\n".join(["    " + line for line in new_content.splitlines()])
        modifier_kwargs.update(
            definition_type=definition_type, target_name=target_name, new_content=indented_new_content
        )
        result_message = f"成功: 已在文件 '{virtual_path}' 中更新 {definition_type} '{target_name}' 的主体内容。"

    elif action == "update_signature":
        if not all([definition_type, target_name, new_content]):
            raise ValueError(
                "对于 'update_signature' 动作，'definition_type', 'target_name', 和 'new_content' 都是必填参数。"
            )
        if definition_type not in ["function", "class"]:
            raise ValueError(f"不支持的 definition_type '{definition_type}'。支持 'function' 或 'class'。")
        modifier_kwargs.update(definition_type=definition_type, target_name=target_name, new_content=new_content)
        result_message = f"成功: 已在文件 '{virtual_path}' 中更新 {definition_type} '{target_name}' 的签名。"

    elif action == "add_import":
        if not import_statement:
            raise ValueError("对于 'add_import' 动作，'import_statement' 是必填参数。")
        modifier_kwargs.update(import_statement=import_statement)
        result_message = f"成功: 已在文件 '{virtual_path}' 中添加导入语句 '{import_statement}'。"

    elif action == "remove_import":
        if not all([definition_type, target_name]):
            raise ValueError("对于 'remove_import' 动作，'definition_type' 和 'target_name' 都是必填参数。")
        if definition_type not in ["module", "symbol"]:
            raise ValueError(
                f"对于 'remove_import' 动作，不支持的 definition_type '{definition_type}'。支持 'module' 或 'symbol'。"
            )
        modifier_kwargs.update(definition_type=definition_type, target_name=target_name)
        result_message = f"成功: 已在文件 '{virtual_path}' 中删除导入 '{target_name}' (类型: {definition_type})。"

    else:
        raise ValueError(f"不支持的 AST 动作 '{action}'。")

    logging.info(f"开始应用 AST 转换。动作: {action}, 目标: {target_name or old_name or 'N/A'}")
    modifier = ASTModifier(action, **modifier_kwargs)
    new_tree = modifier.visit(tree)

    # Check if any modifications were made by the transformer
    if modifier.modified_count == 0:
        # For add actions, if modified_count is 0, it means a ValueError was raised earlier
        # (e.g., definition already exists), so no warning is needed here.
        if action not in ["add_definition", "add_import"]:
            logging.warning(f"警告: 未在文件 '{virtual_path}' 中找到匹配项进行操作 '{action}'。")
            raise ValueError(f"未在文件 '{virtual_path}' 中找到匹配项进行操作 '{action}'。")

    try:
        # Use ast.unparse for Python 3.9+
        new_code = ast.unparse(new_tree)
    except AttributeError:
        error_msg = "您的Python版本不支持 ast.unparse。请使用 Python 3.9 或更高版本。"
        logging.error(error_msg)
        raise RuntimeError(error_msg)
    except Exception as e:
        error_msg = f"将 AST 转换回代码时发生意外错误: {e}"
        logging.error(error_msg)
        raise Exception(error_msg)

    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_code)
        logging.info(f"成功将修改后的代码写入文件 '{virtual_path}'。")
        return result_message
    except PermissionError as e:
        error_msg = f"没有权限写入文件 '{virtual_path}': {e}"
        logging.error(error_msg)
        raise PermissionError(error_msg)
    except IOError as e:
        error_msg = f"写入文件 '{virtual_path}' 时发生 IO 错误: {e}"
        logging.error(error_msg)
        raise IOError(error_msg)
    except Exception as e:
        error_msg = f"写入文件 '{virtual_path}' 时发生未知错误: {e}"
        logging.error(error_msg)
        raise Exception(error_msg)
