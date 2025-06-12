import pathlib
from typing import Annotated

import typer
from rich.console import Console

from domarkx.tool_call.roo_code.parser import parse_tool_calls
from domarkx.tool_call.roo_code.tool import execute_tool_call, format_assistant_response
from domarkx.utils.chat_doc_parser import MarkdownLLMParser, Message, append_message


def do_roo_code_action(
    doc: Annotated[
        pathlib.Path,
        typer.Argument(exists=True, file_okay=True, dir_okay=False, writable=True, readable=True, resolve_path=True),
    ],
    message_index: int,
):
    with doc.open() as f:
        md_content = f.read()

    parser = MarkdownLLMParser()
    parser.parse(md_content, resolve_inclusions=False)

    message_obj, code_block = parser.get_message_and_code_block(message_index)

    console = Console()
    console.rule("message")
    console.print(message_obj.content)
    console.rule("tool_calls")
    tool_calls = parse_tool_calls(message_obj.content)
    assistant_responses = ""
    for tool_call in tool_calls:
        console.print(tool_call)
        console.rule("tool_calls_exec")
        tool_name, result = execute_tool_call(tool_call)
        assistant_response = format_assistant_response(tool_name, result)
        console.print(assistant_response)
        assistant_responses += assistant_response

    with doc.open("a") as f:
        append_message(f, Message("user", assistant_responses, {"source": "user", "type": "UserMessage"}))


def register(main_app: typer.Typer):
    main_app.command()(do_roo_code_action)
