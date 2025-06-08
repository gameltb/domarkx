import json
import logging
from datetime import datetime

from autogen_core import EVENT_LOGGER_NAME
from autogen_core.logging import LLMCallEvent


class LLMJsonlTracker(logging.Handler):
    def __init__(self, log_file) -> None:
        """Logging handler that tracks the number of tokens used in the prompt and completion."""
        super().__init__()
        self.log_file = log_file

    def emit(self, record: logging.LogRecord) -> None:
        """Emit the log record. To be used by the logging module."""
        try:
            # Use the StructuredMessage if the message is an instance of it
            if isinstance(record.msg, LLMCallEvent):
                entry = {
                    "timestamp": datetime.now().isoformat(),
                    "data": record.msg.kwargs,
                }
                with open(self.log_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            self.handleError(record)


# Set up the logging configuration to use the custom handler
def setup_jsonl_logger(log_file="autogen_llm_generations.log.jsonl"):
    logger = logging.getLogger(EVENT_LOGGER_NAME)
    logger.setLevel(logging.INFO)
    llm_usage = LLMJsonlTracker(log_file)
    logger.handlers = [llm_usage]


setup_jsonl_logger()
