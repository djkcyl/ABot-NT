"""移植自 Ariadne"""

import logging
import sys
import traceback
from types import TracebackType
from typing import TYPE_CHECKING

from graia.broadcast.exceptions import (
    ExecutionStop,
    PropagationCancelled,
    RequirementCrashed,
)
from loguru import logger

if TYPE_CHECKING:
    from asyncio import AbstractEventLoop


class LoguruHandler(logging.Handler):
    def emit(self, record):
        # Get corresponding Loguru level if it exists.
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message.
        frame, depth = sys._getframe(6), 6
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


loguru_handler = LoguruHandler()


def loguru_exc_callback(cls: type[BaseException], val: BaseException, tb: TracebackType | None, *_, **__):
    """loguru 异常回调

    Args:
        cls (Type[Exception]): 异常类
        val (Exception): 异常的实际值
        tb (TracebackType): 回溯消息
    """
    if not issubclass(cls, ExecutionStop | PropagationCancelled):
        logger.opt(exception=(cls, val, tb)).error("Exception:")


def loguru_exc_callback_async(loop, context: dict):
    """loguru 异步异常回调

    Args:
        loop (AbstractEventLoop): 异常发生的事件循环
        context (dict): 异常上下文
    """
    message = context.get("message") or "Unhandled exception in event loop"
    if (
        handle := context.get("handle")
    ) and handle._callback.__qualname__ == "ClientConnectionRider.connection_manage.<locals>.<lambda>":
        logger.warning("Uncompleted aiohttp transport", style="yellow bold")
        return
    exception = context.get("exception")
    if exception is None:
        exc_info = False
    elif isinstance(exception, ExecutionStop | PropagationCancelled | RequirementCrashed):
        return
    else:
        exc_info = (type(exception), exception, exception.__traceback__)
    if (
        "source_traceback" not in context
        and loop._current_handle is not None
        and loop._current_handle._source_traceback
    ):
        context["handle_traceback"] = loop._current_handle._source_traceback

    log_lines = [message]
    for key in sorted(context):
        if key in {"message", "exception"}:
            continue
        value = context[key]
        if key == "handle_traceback":
            tb = "".join(traceback.format_list(value))
            value = "Handle created at (most recent call last):\n" + tb.rstrip()
        elif key == "source_traceback":
            tb = "".join(traceback.format_list(value))
            value = "Object created at (most recent call last):\n" + tb.rstrip()
        else:
            value = repr(value)
        log_lines.append(f"{key}: {value}")

    logger.opt(exception=exc_info).error("\n".join(log_lines))


def patch(loop: "AbstractEventLoop", level: str = "INFO"):
    """用这种方法重定向 logging 的 Logger 到 loguru 会丢失部分日志（未解决）"""
    logging.basicConfig(handlers=[loguru_handler], level=0, force=True)

    for name in logging.root.manager.loggerDict:
        _logger = logging.getLogger(name)
        for handler in _logger.handlers:
            if isinstance(handler, logging.StreamHandler):
                _logger.removeHandler(handler)

    logger.remove()
    logger.add(sys.stderr, level=level, enqueue=True)

    # 下面两行有 bug，可能会在输出错误时报错，可能会丢掉部分错误
    # sys.excepthook = loguru_exc_callback
    # traceback.print_exception = loguru_exc_callback
    loop.set_exception_handler(loguru_exc_callback_async)
