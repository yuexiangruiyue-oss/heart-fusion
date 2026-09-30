# -*- coding: utf-8 -*-
"""
heart_protocol.middleware —— 无缝嵌入主流推理引擎的中间件

一行接入任意开源大模型的 Token 生成流:

    from heart_protocol.middleware import Pipeline, HeartGuard, intercept_stream

    pipe = Pipeline().use(HeartGuard(model_fn=my_llm))
    result = pipe.run("用户输入")

    for tok in intercept_stream(token_iter):   # 逐token流式拦截
        print(tok, end="")
"""

from .pipeline import HeartGuard, GuardResult, Pipeline, use
from .stream import StreamReport, intercept_stream

__all__ = [
    "HeartGuard", "GuardResult", "Pipeline", "use",
    "StreamReport", "intercept_stream",
]
