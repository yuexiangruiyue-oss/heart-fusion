# -*- coding: utf-8 -*-
"""
概率网适配器 —— 把整张 Transformer / 大模型接进王冠
=====================================================

协议里「王冠 = 整张概率网」，每个质点按自己的定义在网里取变量。
本模块提供两种可直接注入 `HeartProtocol(probability_net=...)` 的句柄：

    BailianNet   —— 百炼 OpenAI 兼容接口（qwen3.8-flash / deepseek / kimi / glm）
    LocalNet     —— 任意本地 callable（transformers、llama.cpp、ollama 均可包）

契约（duck typing，不依赖基类）:

    net.query(sephirah=..., definition=..., user_input=...) -> dict | list

返回约定（都允许）:
    {"variables": [{...}, ...]}     质点取到的变量列表
    {"text": "..."}                 该质点的文本产出（美丽/真我/幸福等）
    {"pass": true/false, ...}       检验类质点的判定（胜利/荣耀）
    [{...}, ...]                    直接给列表

取不到/失败时抛异常即可，`_query_net` 会记一条失败并退回内置规则，链路不断。
"""

import json
import os
import urllib.request

DEFAULT_BASE = "https://ws-fgz48q1yhkpnbmw9.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
DEFAULT_MODEL = "qwen3.8-flash"

SYSTEM_TMPL = (
    "你是「16质点双生幸福协议」里的「{sephirah}」质点。\n"
    "你的职责：{definition}\n"
    "铁律：不否定用户、不评判用户人格、只陈述物理客观性质；"
    "不输出虚无主义、不引导自伤或伤害他人。\n"
    "只输出一个 JSON 对象，不要解释、不要 markdown 代码块。\n"
    "格式：{{\"variables\": [{{\"description\": \"...\"}}], \"text\": \"...\", "
    "\"pass\": true/false, \"safe\": true/false}}（与职责无关的字段可省略）"
)


def _extract_json(text: str):
    """从模型输出里取出第一个 JSON 对象（容忍 ```json 包裹与前后废话）。"""
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    start, depth = None, 0
    for i, ch in enumerate(text):
        if ch == "{":
            if start is None:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if start is not None and depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    start, depth = None, 0
    return None


class BailianNet:
    """百炼 OpenAI 兼容端点。密钥只从参数/环境变量读，不落盘。"""

    def __init__(self, api_key=None, base_url=None, model=None,
                 timeout=90, temperature=0.3, max_tokens=500):
        self.api_key = api_key or os.environ.get("BAILIAN_MAAS_KEY", "")
        self.base_url = (base_url or os.environ.get("BAILIAN_MAAS_ENDPOINT",
                                                    DEFAULT_BASE)).rstrip("/")
        self.model = model or os.environ.get("BAILIAN_MAAS_MODEL", DEFAULT_MODEL)
        self.timeout = timeout
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.calls = 0
        self.errors = 0

    def _chat(self, system: str, user: str, max_tokens=None) -> str:
        if not self.api_key:
            raise RuntimeError("BAILIAN_MAAS_KEY 未设置")
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
            "temperature": self.temperature,
            "max_tokens": max_tokens or self.max_tokens,
        }
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {self.api_key}"},
            method="POST")
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        return body["choices"][0]["message"]["content"]

    def query(self, sephirah: str, definition: str, user_input: str, **_) -> dict:
        self.calls += 1
        try:
            raw = self._chat(
                SYSTEM_TMPL.format(sephirah=sephirah, definition=definition),
                f"【用户原话】\n{user_input}")
        except Exception:
            self.errors += 1
            raise
        data = _extract_json(raw)
        if data is None:
            return {"text": raw.strip()}
        if "text" not in data and "variables" not in data:
            data = {"variables": [data]}
        return data


class LocalNet:
    """把任意本地生成函数包成概率网句柄。

    generate(system, user) -> str，例如 transformers/ollama 的一层薄封装。
    """

    def __init__(self, generate, system_tmpl: str = SYSTEM_TMPL):
        self.generate = generate
        self.system_tmpl = system_tmpl
        self.calls = 0

    def query(self, sephirah: str, definition: str, user_input: str, **_) -> dict:
        self.calls += 1
        raw = self.generate(
            self.system_tmpl.format(sephirah=sephirah, definition=definition),
            f"【用户原话】\n{user_input}")
        data = _extract_json(raw)
        return data if isinstance(data, dict) else {"text": raw.strip()}


def web_search_fn(n: int = 5):
    """把 thinkers.search_web 包成 HeartProtocol(search_fn=...) 需要的形状。"""
    def _search(query: str):
        from .thinkers import search_web
        try:
            results = search_web(query, n=n)
        except Exception:
            return []
        out = []
        for title, snippet in results:
            piece = f"{title}：{snippet}".strip("：")
            if piece:
                out.append(piece[:300])
        return out
    return _search
