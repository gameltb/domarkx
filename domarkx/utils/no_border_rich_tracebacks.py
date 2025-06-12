import linecache
import os
from logging import LogRecord
from typing import (
    Iterable,
    List,
    Optional,
)

import rich.box
from pygments.token import Comment, Keyword, Name, Number, Operator, String, Token
from pygments.token import Text as TextToken
from rich._loop import loop_last
from rich._null_file import NullFile
from rich.columns import Columns
from rich.console import (
    Console,
    ConsoleOptions,
    ConsoleRenderable,
    Group,
    RenderResult,
    group,
)
from rich.constrain import Constrain
from rich.highlighter import ReprHighlighter
from rich.logging import RichHandler
from rich.panel import Panel
from rich.scope import render_scope
from rich.style import Style
from rich.syntax import Syntax
from rich.text import Text
from rich.theme import Theme
from rich.traceback import Frame, PathHighlighter, Stack, Traceback, _iter_syntax_lines

BOX_STYLE = rich.box.SIMPLE


class NoBorderTraceback(Traceback):
    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        theme = self.theme
        background_style = theme.get_background_style()
        token_style = theme.get_style_for_token

        traceback_theme = Theme(
            {
                "pretty": token_style(TextToken),
                "pygments.text": token_style(Token),
                "pygments.string": token_style(String),
                "pygments.function": token_style(Name.Function),
                "pygments.number": token_style(Number),
                "repr.indent": token_style(Comment) + Style(dim=True),
                "repr.str": token_style(String),
                "repr.brace": token_style(TextToken) + Style(bold=True),
                "repr.number": token_style(Number),
                "repr.bool_true": token_style(Keyword.Constant),
                "repr.bool_false": token_style(Keyword.Constant),
                "repr.none": token_style(Keyword.Constant),
                "scope.border": token_style(String.Delimiter),
                "scope.equals": token_style(Operator),
                "scope.key": token_style(Name),
                "scope.key.special": token_style(Name.Constant) + Style(dim=True),
            },
            inherit=False,
        )

        highlighter = ReprHighlighter()

        @group()
        def render_stack(stack, last: bool) -> RenderResult:
            if stack.frames:
                stack_renderable: ConsoleRenderable = Panel(
                    self._render_stack(stack),
                    title="[traceback.title]Traceback [dim](most recent call last)",
                    style=background_style,
                    border_style="traceback.border",
                    expand=True,
                    padding=(0, 1),
                    box=BOX_STYLE,
                )
                stack_renderable = Constrain(stack_renderable, self.width)
                with console.use_theme(traceback_theme):
                    yield stack_renderable

            if stack.syntax_error is not None:
                with console.use_theme(traceback_theme):
                    yield Constrain(
                        Panel(
                            self._render_syntax_error(stack.syntax_error),
                            style=background_style,
                            border_style="traceback.border.syntax_error",
                            expand=True,
                            padding=(0, 1),
                            width=self.width,
                            box=BOX_STYLE,
                        ),
                        self.width,
                    )
                yield Text.assemble(
                    (f"{stack.exc_type}: ", "traceback.exc_type"),
                    highlighter(stack.syntax_error.msg),
                )
            elif stack.exc_value:
                yield Text.assemble(
                    (f"{stack.exc_type}: ", "traceback.exc_type"),
                    highlighter(stack.exc_value),
                )
            else:
                yield Text.assemble((f"{stack.exc_type}", "traceback.exc_type"))

            for note in stack.notes:
                yield Text.assemble(("[NOTE] ", "traceback.note"), highlighter(note))

            if stack.is_group:
                for group_no, group_exception in enumerate(stack.exceptions, 1):
                    grouped_exceptions: List[Group] = []
                    for group_last, group_stack in loop_last(group_exception.stacks):
                        grouped_exceptions.append(render_stack(group_stack, group_last))
                    yield ""
                    yield Constrain(
                        Panel(
                            Group(*grouped_exceptions),
                            title=f"Sub-exception #{group_no}",
                            border_style="traceback.group.border",
                            box=BOX_STYLE,
                        ),
                        self.width,
                    )

            if not last:
                if stack.is_cause:
                    yield Text.from_markup(
                        "\n[i]The above exception was the direct cause of the following exception:\n",
                    )
                else:
                    yield Text.from_markup(
                        "\n[i]During handling of the above exception, another exception occurred:\n",
                    )

        for last, stack in loop_last(reversed(self.trace.stacks)):
            yield render_stack(stack, last)

    @group()
    def _render_stack(self, stack: Stack) -> RenderResult:
        path_highlighter = PathHighlighter()
        theme = self.theme

        def render_locals(frame: Frame) -> Iterable[ConsoleRenderable]:
            if frame.locals:
                locals_p = render_scope(
                    frame.locals,
                    title="locals",
                    indent_guides=self.indent_guides,
                    max_length=self.locals_max_length,
                    max_string=self.locals_max_string,
                )
                locals_p.box = BOX_STYLE
                yield locals_p

        exclude_frames: Optional[range] = None
        if self.max_frames != 0:
            exclude_frames = range(
                self.max_frames // 2,
                len(stack.frames) - self.max_frames // 2,
            )

        excluded = False
        for frame_index, frame in enumerate(stack.frames):
            if exclude_frames and frame_index in exclude_frames:
                excluded = True
                continue

            if excluded:
                assert exclude_frames is not None
                yield Text(
                    f"\n... {len(exclude_frames)} frames hidden ...",
                    justify="center",
                    style="traceback.error",
                )
                excluded = False

            first = frame_index == 0
            frame_filename = frame.filename
            suppressed = any(frame_filename.startswith(path) for path in self.suppress)

            if os.path.exists(frame.filename):
                text = Text.assemble(
                    path_highlighter(Text(frame.filename, style="pygments.string")),
                    (":", "pygments.text"),
                    (str(frame.lineno), "pygments.number"),
                    " in ",
                    (frame.name, "pygments.function"),
                    style="pygments.text",
                )
            else:
                text = Text.assemble(
                    "in ",
                    (frame.name, "pygments.function"),
                    (":", "pygments.text"),
                    (str(frame.lineno), "pygments.number"),
                    style="pygments.text",
                )
            if not frame.filename.startswith("<") and not first:
                yield ""
            yield text
            if frame.filename.startswith("<"):
                yield from render_locals(frame)
                continue
            if not suppressed:
                try:
                    code_lines = linecache.getlines(frame.filename)
                    code = "".join(code_lines)
                    if not code:
                        # code may be an empty string if the file doesn't exist, OR
                        # if the traceback filename is generated dynamically
                        continue
                    lexer_name = self._guess_lexer(frame.filename, code)
                    syntax = Syntax(
                        code,
                        lexer_name,
                        theme=theme,
                        line_numbers=True,
                        line_range=(
                            frame.lineno - self.extra_lines,
                            frame.lineno + self.extra_lines,
                        ),
                        highlight_lines={frame.lineno},
                        word_wrap=self.word_wrap,
                        code_width=self.code_width,
                        indent_guides=self.indent_guides,
                        dedent=False,
                    )
                    yield ""
                except Exception as error:
                    yield Text.assemble(
                        (f"\n{error}", "traceback.error"),
                    )
                else:
                    if frame.last_instruction is not None:
                        start, end = frame.last_instruction

                        # Stylize a line at a time
                        # So that indentation isn't underlined (which looks bad)
                        for line1, column1, column2 in _iter_syntax_lines(start, end):
                            try:
                                if column1 == 0:
                                    line = code_lines[line1 - 1]
                                    column1 = len(line) - len(line.lstrip())
                                if column2 == -1:
                                    column2 = len(code_lines[line1 - 1])
                            except IndexError:
                                # Being defensive here
                                # If last_instruction reports a line out-of-bounds, we don't want to crash
                                continue

                            syntax.stylize_range(
                                style="traceback.error_range",
                                start=(line1, column1),
                                end=(line1, column2),
                            )
                    yield (
                        Columns(
                            [
                                syntax,
                                *render_locals(frame),
                            ],
                            padding=1,
                        )
                        if frame.locals
                        else syntax
                    )


class NoBorderRichHandler(RichHandler):
    def emit(self, record: LogRecord) -> None:
        """Invoked by logging."""
        message = self.format(record)
        traceback = None
        if self.rich_tracebacks and record.exc_info and record.exc_info != (None, None, None):
            exc_type, exc_value, exc_traceback = record.exc_info
            assert exc_type is not None
            assert exc_value is not None
            traceback = NoBorderTraceback.from_exception(
                exc_type,
                exc_value,
                exc_traceback,
                width=self.tracebacks_width,
                code_width=self.tracebacks_code_width,
                extra_lines=self.tracebacks_extra_lines,
                theme=self.tracebacks_theme,
                word_wrap=self.tracebacks_word_wrap,
                show_locals=self.tracebacks_show_locals,
                locals_max_length=self.locals_max_length,
                locals_max_string=self.locals_max_string,
                suppress=self.tracebacks_suppress,
                max_frames=self.tracebacks_max_frames,
            )
            message = record.getMessage()
            if self.formatter:
                record.message = record.getMessage()
                formatter = self.formatter
                if hasattr(formatter, "usesTime") and formatter.usesTime():
                    record.asctime = formatter.formatTime(record, formatter.datefmt)
                message = formatter.formatMessage(record)

        message_renderable = self.render_message(record, message)
        log_renderable = self.render(record=record, traceback=traceback, message_renderable=message_renderable)
        if isinstance(self.console.file, NullFile):
            # Handles pythonw, where stdout/stderr are null, and we return NullFile
            # instance from Console.file. In this case, we still want to make a log record
            # even though we won't be writing anything to a file.
            self.handleError(record)
        else:
            try:
                self.console.print(log_renderable)
            except Exception:
                self.handleError(record)
