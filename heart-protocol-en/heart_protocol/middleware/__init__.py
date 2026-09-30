# -*- coding: utf-8 -*-
"""
heart_protocol.middleware — middleware that embeds seamlessly into mainstream inference engines

Plug the token generation stream of any open-source LLM into the protocol in one line:

    from heart_protocol.middleware import Pipeline, HeartGuard, intercept_stream

    pipe = Pipeline().use(HeartGuard(model_fn=my_llm))
    result = pipe.run("user input")

    for tok in intercept_stream(token_iter):   # per-token streaming interception
        print(tok, end="")
"""

from .pipeline import HeartGuard, GuardResult, Pipeline, use
from .stream import StreamReport, intercept_stream

__all__ = [
    "HeartGuard", "GuardResult", "Pipeline", "use",
    "StreamReport", "intercept_stream",
]
