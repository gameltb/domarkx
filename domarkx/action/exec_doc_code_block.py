import pathlib
from typing import Annotated

import rich
import rich.markdown
import typer
from rich.console import Console

from domarkx.utils.chat_doc_parser import MarkdownLLMParser


def exec_doc_code_block(
    doc: Annotated[
        pathlib.Path,
        typer.Argument(exists=True, file_okay=True, dir_okay=False, writable=True, readable=True, resolve_path=True),
    ],
    message_index: int,
    code_block_in_message_index: int,
):
    with doc.open() as f:
        md_content = f.read()

    parser = MarkdownLLMParser()
    parser.parse(md_content, resolve_inclusions=False)

    message_obj, code_block = parser.get_message_and_code_block(message_index, code_block_in_message_index)

    console = Console()
    md = rich.markdown.Markdown(message_obj.content)
    console.rule("message")
    console.print(md)
    console.rule("code")
    console.print(rich.markdown.Markdown(f"```{code_block.language}\n{code_block.code}\n```"))
    console.input("Press Enter to exec, Ctrl+C to cancel.")
    console.rule("exec")

    if code_block.language.startswith("python"):
        exec(code_block.code)


def register(main_app: typer.Typer):
    main_app.command()(exec_doc_code_block)
