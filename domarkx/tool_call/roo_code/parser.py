import re


class ToolCallParsingError(Exception):
    """自定义异常，用于工具调用解析错误。"""

    pass


def parse_tool_calls(message: str) -> list:
    """
    解析消息字符串中的工具调用，能够稳健处理残缺的块并尝试修复。
    如果块不可修复，则抛出 ToolCallParsingError 错误。

    参数:
        message (str): 包含工具调用的消息字符串。

    返回:
        list: 包含解析出的工具调用字典的列表。每个字典包含 'tool_name' 和 'parameters'。
              'parameters' 是一个字典，其中键为参数名，值为参数内容（字符串）。

    示例:
        >>> parse_tool_calls("<tool1><param1>value1</param1></tool1>")
        [{'tool_name': 'tool1', 'parameters': {'param1': 'value1'}}]

        >>> parse_tool_calls("<tool2><paramA>incomplete<paramB>complete</paramB></tool2>")
        [{'tool_name': 'tool2', 'parameters': {'paramA': 'incomplete', 'paramB': 'complete'}}]

        >>> parse_tool_calls("<tool3><paramC>valueC") # 缺少工具结束标签
        [{'tool_name': 'tool3', 'parameters': {'paramC': 'valueC'}}]
    """
    tool_calls = []

    idx = 0
    while idx < len(message):
        # 查找顶级（工具调用）的开始标签
        # 匹配格式为 <tag_name> 的标签
        open_tag_match = re.match(r"<\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*>", message[idx:], re.DOTALL)
        if not open_tag_match:
            # 如果当前位置没有找到开始标签，则跳过一个字符继续查找
            idx += 1
            continue

        tool_name = open_tag_match.group(1)
        # 获取开始标签结束后的位置
        tool_start_tag_end = idx + open_tag_match.end()

        # 尝试查找当前工具的匹配结束标签
        # 使用 re.escape() 确保工具名中的特殊字符被正确处理
        tool_close_tag_pattern = re.compile(r"<\/\s*" + re.escape(tool_name) + r"\s*>", re.DOTALL)
        tool_close_tag_match = tool_close_tag_pattern.search(message, tool_start_tag_end)

        tool_block_content = ""
        # 默认情况下，如果工具块不完整，其内容延伸到消息的末尾
        tool_block_end_pos = len(message)

        if tool_close_tag_match:
            # 如果找到匹配的结束标签，则内容介于开始标签和结束标签之间
            tool_block_content = message[tool_start_tag_end : tool_close_tag_match.start()]
            # 下一个搜索的起始位置在结束标签之后
            tool_block_end_pos = tool_close_tag_match.end()
        else:
            # 工具块不完整: 内容延伸到下一个可能的顶级工具标签的开始，或消息的末尾。
            # 这是“尝试修复”的一部分。
            next_tool_open_tag = re.search(r"<\s*[a-zA-Z_][a-zA-Z0-9_]*\s*>", message[tool_start_tag_end:], re.DOTALL)
            if next_tool_open_tag:
                # 内容延伸到下一个顶级标签的开始
                tool_block_content = message[tool_start_tag_end : tool_start_tag_end + next_tool_open_tag.start()]
                tool_block_end_pos = tool_start_tag_end + next_tool_open_tag.start()
            else:
                # 内容延伸到消息的末尾
                tool_block_content = message[tool_start_tag_end:]
                tool_block_end_pos = len(message)

        # 解析工具块内容中的参数
        current_params = {}
        temp_idx = 0
        while temp_idx < len(tool_block_content):
            # 查找下一个参数的开始标签
            param_open_tag_match = re.search(
                r"<\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*>", tool_block_content[temp_idx:], re.DOTALL
            )

            if not param_open_tag_match:
                break  # 没有更多标签，或只剩下空白字符，退出循环

            # 在当前参数标签之前，检查是否有非空白字符的内容。
            # 这处理了类似 `<tool> 格式错误的文本 <param>...</param> </tool>` 的情况
            text_before_tag = tool_block_content[temp_idx : temp_idx + param_open_tag_match.start()].strip()
            if text_before_tag:
                raise ToolCallParsingError(
                    f"工具 '{tool_name}' 块中在标签前存在格式错误的非标签内容: '{text_before_tag}'"
                )

            param_name = param_open_tag_match.group(1)
            # 获取参数开始标签结束后的位置
            param_start_tag_end = temp_idx + param_open_tag_match.end()

            # 参数内容的开始位置就是参数开始标签的结束位置
            param_content_start = param_start_tag_end

            # 尝试查找当前参数的匹配结束标签
            param_close_tag_pattern = re.compile(r"<\/\s*" + re.escape(param_name) + r"\s*>", re.DOTALL)
            param_close_tag_match = param_close_tag_pattern.search(tool_block_content, param_content_start)

            param_value_raw = ""
            # 默认情况下，如果参数块不完整，其内容延伸到工具块的末尾
            param_block_end_pos = len(tool_block_content)

            if param_close_tag_match:
                # 如果找到匹配的结束标签，则内容介于开始标签和结束标签之间
                param_value_raw = tool_block_content[param_content_start : param_close_tag_match.start()]
                # 下一个参数搜索的起始位置在结束标签之后
                param_block_end_pos = param_close_tag_match.end()
            else:
                # 参数块不完整: 内容延伸到下一个同级参数标签的开始，或当前工具块的末尾。
                # 这是“尝试修复”的又一部分。
                next_param_open_tag = re.search(
                    r"<\s*[a-zA-Z_][a-zA-Z0-9_]*\s*>", tool_block_content[param_content_start:], re.DOTALL
                )

                if next_param_open_tag:
                    # 内容延伸到下一个参数标签的开始
                    param_value_raw = tool_block_content[
                        param_content_start : param_content_start + next_param_open_tag.start()
                    ]
                    param_block_end_pos = param_content_start + next_param_open_tag.start()
                else:
                    # 内容延伸到当前工具块的末尾
                    param_value_raw = tool_block_content[param_content_start:]
                    param_block_end_pos = len(tool_block_content)

            # 去除值的空白字符并存储
            current_params[param_name] = param_value_raw.strip()
            temp_idx = param_block_end_pos

        # 将解析出的工具调用添加到结果列表
        tool_calls.append({"tool_name": tool_name, "parameters": current_params})
        # 更新主循环的索引，继续搜索下一个工具调用
        idx = tool_block_end_pos

    return tool_calls
