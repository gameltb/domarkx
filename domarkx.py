import asyncio
import logging
import pathlib
from typing import Annotated

import rich
import rich.markdown
import typer
from autogen_agentchat import ui
from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models._utils.parse_r1_content import parse_r1_content
from dotenv import load_dotenv
from prompt_toolkit import PromptSession
from rich.console import Console
from rich.logging import RichHandler

from domarkx.utils.chat_doc_parser import MarkdownLLMParser, Message, append_message

# Configure logging
logger = logging.getLogger("autogen")
logging.basicConfig(
    level=logging.INFO,
    handlers=[RichHandler(rich_tracebacks=True, markup=True, show_time=False, show_level=True, show_path=True)],
    format="[dim][%(name)s][/dim] %(message)s",
)


cli_app = typer.Typer()


async def aexec_doc(doc: pathlib.Path):
    with doc.open() as f:
        md_content = f.read()

    console = Console()
    parser = MarkdownLLMParser()
    parsed_doc = parser.parse(md_content, source_path=str(doc.absolute()))

    if parsed_doc.config.session_setup_code:
        session_setup_code = parsed_doc.config.session_setup_code
        console.print(rich.markdown.Markdown(f"```{session_setup_code.language}\n{session_setup_code.code}\n```"))
        local_vars = {}
        exec(session_setup_code.code, globals(), local_vars)

        client = local_vars["client"]

    console.print("".join(parsed_doc.raw_lines))


    chat_agent_state = parsed_doc.config.session_config

    system_message = parsed_doc.conversation[0].content

    messages = []
    for md_message in parsed_doc.conversation[1:]:
        message_dict = md_message.metadata

        thought, content = parse_r1_content(md_message.content)
        message_dict["content"] = content
        if thought:
            message_dict["thought"] = "\n".join(line.removeprefix("> ") for line in thought.splitlines())
        messages.append(message_dict)

    chat_agent_state["llm_context"]["messages"] = messages

    if system_message is None or len(system_message) == 0:
        system_message = "You are a helpful AI assistant. "

    chat_agent = AssistantAgent(
        "assistant", model_client=client, system_message=system_message, model_client_stream=True
    )

    await chat_agent.load_state(chat_agent_state)

    task = None
    if len(messages) == 0 or messages[-1].get("type", "") != "UserMessage":
        task = await PromptSession().prompt_async(
            "task > ",
            multiline=True,
            bottom_toolbar="press Alt+Enter in order to accept the input. (Or Escape followed by Enter.)",
        )

    console.input("Click Enter to run stream, Ctrl+C to cancel.")

    response = await ui.Console(chat_agent.run_stream(task=task))

    new_state = await chat_agent.save_state()

    for message in new_state["llm_context"]["messages"][len(messages) :]:
        content = message.pop("content", "")
        thought = message.pop("thought", "")
        if thought:
            thought = "\n".join("> " + line for line in f"""<think>{thought}</think>""".splitlines())
            content = f"""
{thought}

{content}"""
        with doc.open("a") as f:
            append_message(f, Message("assistant", content, message))

    console.print(response)


@cli_app.command()
def exec_doc(
    doc: Annotated[
        pathlib.Path,
        typer.Argument(exists=True, file_okay=True, dir_okay=False, writable=True, readable=True, resolve_path=True),
    ],
):
    load_dotenv()

    asyncio.run(aexec_doc(doc))


@cli_app.command()
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

    from domarkx.utils.chat_doc_parser import MarkdownLLMParser

    parser = MarkdownLLMParser()
    parsed_doc = parser.parse(md_content, resolve_inclusions=False)

    message_obj, code_block = parser.get_message_and_code_block(message_index, code_block_in_message_index)

    console = Console()
    md = rich.markdown.Markdown(message_obj.content)
    console.rule("message")
    console.print(md)
    console.rule("code")
    console.print(rich.markdown.Markdown(f"```{code_block.language}\n{code_block.code}\n```"))
    console.input("Click Enter to exec, Ctrl+C to cancel.")
    console.rule("exec")

    if code_block.language.startswith("python"):
        exec(code_block.code)


if __name__ == "__main__":
    cli_app()
