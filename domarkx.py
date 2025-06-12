import importlib
import logging
import os

import typer
from dotenv import load_dotenv

from domarkx.utils.no_border_rich_tracebacks import NoBorderRichHandler

# Configure logging
logger = logging.getLogger("domarkx")
logging.basicConfig(
    level=logging.INFO,
    handlers=[
        NoBorderRichHandler(
            rich_tracebacks=True,
            tracebacks_max_frames=1,
            tracebacks_show_locals=True,
            markup=True,
            show_time=False,
            show_level=True,
            show_path=True,
        )
    ],
    format="[dim][%(name)s][/dim] %(message)s",
)


cli_app = typer.Typer()


def load_actions():
    actions_dir = "domarkx/action"
    for filename in os.listdir(actions_dir):
        if filename.endswith(".py") and not filename.startswith("__"):
            module_name = filename[:-3]
            module = importlib.import_module(f"{actions_dir.replace('/', '.')}.{module_name}")
            if hasattr(module, "register"):
                module.register(cli_app)


if __name__ == "__main__":
    load_dotenv()
    load_actions()
    try:
        cli_app()
    except Exception as e:
        logger.error(e, exc_info=True)
