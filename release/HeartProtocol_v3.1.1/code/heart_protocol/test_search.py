# -*- coding: utf-8 -*-
"""双线真联网单元测试
- 理智线:「智慧」质点实时检索实时新闻/常识/知识,与内部知识库对比(协议第1次计算)
- 慈爱线:「理解」质点实时检索人类共同经历(协议第2次计算)
运行: python -m pytest test_search.py -v
全部 mock 网络层，不发真实请求、不消耗 API 额度。
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from heart_protocol import thinkers  # noqa: E402


class FakeResp:
    """假 HTTP 响应：支持 read() 与 with 上下文。"""

    def __init__(self, data: bytes):
        self._d = data

    def read(self) -> bytes:
        return self._d

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _ok_body(content="ok"):
    return json.dumps({"choices": [
        {"message": {"role": "assistant", "content": content}}]}).encode("utf-8")


# ---------- 1. chat() 的 enable_search 透传 ----------

def test_chat_payload_with_search(monkeypatch):
    """enable_search=True 时请求体必须携带该字段。"""
    monkeypatch.setattr(thinkers, "KEY", "test-key")
    monkeypatch.setattr(thinkers, "EP", "https://fake.ep/v1")
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["data"] = json.loads(req.data.decode("utf-8"))
        return FakeResp(_ok_body("联网回答"))

    monkeypatch.setattr(thinkers.urllib.request, "urlopen", fake_urlopen)
    out = thinkers.chat("sys", "user", enable_search=True)
    assert out == "联网回答"
    assert captured["data"]["enable_search"] is True


def test_chat_payload_without_search(monkeypatch):
    """默认不带 enable_search，不影响其余 14 个不走联网的质点。"""
    monkeypatch.setattr(thinkers, "KEY", "test-key")
    monkeypatch.setattr(thinkers, "EP", "https://fake.ep/v1")
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["data"] = json.loads(req.data.decode("utf-8"))
        return FakeResp(_ok_body("普通回答"))

    monkeypatch.setattr(thinkers.urllib.request, "urlopen", fake_urlopen)
    out = thinkers.chat("sys", "user", enable_search=False)
    assert out == "普通回答"
    assert "enable_search" not in captured["data"]


# ---------- 2. 全链编排: 智慧(理智线) + 理解(慈爱线) 双质点联网 ----------

def _run_mock_chain(monkeypatch, on_search=None):
    """mock chat 跑完整 16 思想体链路，返回 (result, calls)。
    on_search: 检索调用（enable_search=True）时的行为，None 则正常返回。
    """
    calls = []

    def fake_chat(system, user, max_tokens=300, temperature=0.6,
                  retries=4, enable_search=False):
        calls.append({"enable_search": enable_search, "system": system})
        if enable_search and on_search is not None:
            return on_search()
        return "发言"

    monkeypatch.setattr(thinkers, "chat", fake_chat)
    ens = thinkers.SephirahEnsemble()
    res = ens.run("测试输入")
    return res, calls


def test_search_points_use_search(monkeypatch):
    """全链 16 次调用中，「智慧」(理智线)与「理解」(慈爱线)走联网，其余 14 个不走。

    协议第1次计算: 理智线先外部搜索实时新闻/常识/知识，与内部知识库对比；
    协议第2次计算: 慈爱线检索全人类相同痛苦与感受（必须实时联网）。
    """
    res, calls = _run_mock_chain(monkeypatch)
    assert len(calls) == 16
    search_calls = [c for c in calls if c["enable_search"]]
    assert len(search_calls) == 2, "智慧+理解两个质点走联网检索"
    search_sys = [c["system"] for c in search_calls]
    assert any("实时联网检索" in s and "实时新闻" in s for s in search_sys), \
        "智慧指令须声明联网检索实时新闻/常识/知识"
    assert any("实时联网检索" in s and "相同痛苦与感受" in s for s in search_sys), \
        "理解指令须声明检索全人类相同痛苦与感受"
    for who in ("智慧", "理解"):
        t = [t for t in res.thoughts if t.who == who][0]
        assert t.meta.get("search") == "enable_search", f"{who} meta 须可追溯联网"


def test_search_fallback(monkeypatch):
    """联网通道失败 → 自动退回内置知识，链路完整不断。"""

    def boom():
        raise RuntimeError("LLM 调用失败 HTTP 400: enable_search 不支持")

    res, calls = _run_mock_chain(monkeypatch, on_search=boom)
    # 16 次正常调用 + 2 次失败的联网尝试（智慧/理解各一）= 18
    assert len(calls) == 18
    for who in ("智慧", "理解"):
        t = [t for t in res.thoughts if t.who == who][0]
        assert t.text == "发言", f"{who} 退回后仍正常产出"
        assert t.meta.get("search") is None, f"{who} 不再标记联网"
    assert len(res.thoughts) == 16, "链路完整"


# ---------- 3. search_web 解析与容错 ----------

_DDG_SAMPLE = """
<div class="result results_links">
  <a class="result__a" href="x">考研失败，我的人生完了 - 搜狐</a>
  <a class="result__snippet">很多人都有过类似经历…</a>
</div>
<div class="result results_links">
  <a class="result__a" href="y">考试失败后如何调整心态 - 知乎</a>
  <a class="result__snippet">过来人分享真实故事</a>
</div>
"""


def test_search_web_parse(monkeypatch):
    """DDG HTML 样本解析出标题与摘要。"""

    def fake_urlopen(req, timeout=None):
        return FakeResp(_DDG_SAMPLE.encode("utf-8"))

    monkeypatch.setattr(thinkers.urllib.request, "urlopen", fake_urlopen)
    out = thinkers.search_web("考试失败")
    assert len(out) == 2
    assert "考研失败" in out[0][0]
    assert "很多人" in out[0][1]
    assert "知乎" in out[1][0]


def test_search_web_failure_returns_empty(monkeypatch):
    """检索网络异常 → 返回空列表，不抛异常不阻断链路。"""

    def fake_urlopen(req, timeout=None):
        raise ConnectionError("网络断")

    monkeypatch.setattr(thinkers.urllib.request, "urlopen", fake_urlopen)
    assert thinkers.search_web("任意") == []


# ---------- 4. trail 轨迹记录 meta ----------

def test_trail_records_meta(monkeypatch, tmp_path):
    """断点轨迹 JSONL 每行含 meta，可追溯「智慧」「理解」走了联网。"""

    def fake_chat(system, user, max_tokens=300, temperature=0.6,
                  retries=4, enable_search=False):
        return "发言"

    monkeypatch.setattr(thinkers, "chat", fake_chat)
    trail = tmp_path / "trail.jsonl"
    ens = thinkers.SephirahEnsemble(trail_path=str(trail))
    ens.run("测试输入")
    lines = [json.loads(ln) for ln in
             trail.read_text(encoding="utf-8").splitlines()]
    assert len(lines) == 16
    for who in ("智慧", "理解"):
        t = [ln for ln in lines if ln["who"] == who][0]
        assert t["meta"]["search"] == "enable_search"