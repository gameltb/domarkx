import os
import pathlib
import re
from typing import Annotated

import rich
import rich.markdown
import typer
from prompt_toolkit import PromptSession
from rich.console import Console

from domarkx.utils.chat_doc_parser import MarkdownLLMParser

# Regex patterns to extract a filename/path from the first line of a code block's content.
# Order matters: more specific or common patterns first.
FILENAME_PATTERNS = [
    # Matches: #!/usr/bin/env python3 path/to/script.py -> path/to/script.py
    # Matches: #!/bin/bash path/to/script.sh -> path/to/script.sh
    re.compile(r"^\s*#!\s*(?:[\w\/\.-]+/env\s+\w+\s+)?([\w\/\.-]+\.[a-zA-Z0-9]+)\s*"),
    # Matches: # path/to/file.ext or # file.ext
    re.compile(r"^\s*#\s*([\w\/\.-]+\.[a-zA-Z0-9]+)\s*"),
    # Matches: /* path/to/file.css */ or /* file.tcss */
    re.compile(r"^\s*\/\*\s*([\w\/\.-]+\.[a-zA-Z0-9]+)\s*\*\/"),
    # Matches: ; alembic.ini or ; path/to/alembic.ini
    re.compile(r"^\s*;+\s*([\w\/\.-]+\.ini)\s*"),
    # For general markdown files if specified like: re.compile(r"^\s*\s*")
]


def do_extract_code_to_file(output_base_dir: str, block_inner_content: str):
    block_lines = block_inner_content.strip().split("\n")
    if not block_lines:
        print("⚠️ Block  is empty, skipping.")
        return

    first_line = block_lines[0].strip()
    filepath_extracted = None
    # By default, the first line (comment) is NOT part of the final code,
    # unless it's a shebang or a comment type that is typically kept (like CSS block comments).
    first_line_is_code = False

    for pattern_idx, pattern in enumerate(FILENAME_PATTERNS):
        match = pattern.match(first_line)
        if match:
            filepath_extracted = match.group(1).strip()
            # Shebangs must be the first line of the script.
            if first_line.startswith("#!"):
                first_line_is_code = True
            # CSS comments that define filename are usually not kept if they are just markers,
            # but sometimes block comments start a file. For simplicity, we'll treat it as not code for now
            # unless the user wants to adjust. Let's assume if it matched, it was a marker.
            # If the comment IS the path, we usually want to strip it for Python/other similar files.
            break

    filepath_extracted = PromptSession().prompt("filepath > ", default=filepath_extracted if filepath_extracted else "")

    if filepath_extracted:
        # Construct full path relative to the output_base_dir
        full_path = os.path.join(output_base_dir, filepath_extracted)

        # Ensure directory structure exists
        dir_name = os.path.dirname(full_path)
        if dir_name:  # If there's a directory part (e.g., "dam/tui")
            os.makedirs(dir_name, exist_ok=True)

        # Determine the actual code to write
        if first_line_is_code:  # e.g., shebang
            code_to_write = "\n".join(block_lines)
        else:  # The first line was a filename comment, so skip it for the output file
            code_to_write = "\n".join(block_lines[1:])

        # Ensure there's content to write, especially after stripping the first line
        if not code_to_write.strip() and not first_line_is_code and len(block_lines) == 1:
            print(f"⚠️ File '{filepath_extracted}' would be empty after stripping comment. Skipping.")
            return
        if not code_to_write.strip() and first_line_is_code:  # e.g. only a shebang
            print(f"📝 Writing file '{filepath_extracted}' which might only contain the shebang/comment.")

        try:
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(code_to_write)
            print(f"✅ Extracted and wrote: {full_path}")
        except IOError as e:
            print(f"❌ Error writing file {full_path}: {e}")
        except Exception as e:
            print(f"❌ An unexpected error occurred while writing {full_path}: {e}")
    else:
        print(f'❔ : No filename pattern matched for first line: "{first_line[:70]}..."')


def extract_code_to_file(
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

    do_extract_code_to_file(".", code_block.code)


def register(main_app: typer.Typer):
    main_app.command()(extract_code_to_file)
