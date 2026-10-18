# -*- coding: utf-8 -*-
"""
16质点真实对话聊天服务 —— 日常可用版（任务 #22）

在 thinkers.py 的 SephirahEnsemble（16质点全链 + _redline_guard 红线兜底）之上，
提供日常聊天所需的一切：

  - ThreadingHTTPServer 多线程：100-150 秒的全链长任务不再阻塞其他请求
  - SSE 流式进度：每个质点上场/完成即时推送，网页实时显示「当前进行到哪个质点」
  - 会话历史持久化：heart_protocol/chat_history/{session_id}.json，按会话组织可回看
  - 环境变量自动注入：启动时从 Windows 用户级注册表(HKCU\\Environment)
    补齐 BAILIAN_MAAS_KEY / BAILIAN_MAAS_ENDPOINT / BAILIAN_MAAS_MODEL
  - 百炼不可用时自动降级本地启发式模式（页头明示，不伪装成真实链路）

设计原则：thinkers.py / abyss.py / protocol.py 等现有文件零改动。
进度注入通过子类 ProgressEnsemble 覆写 think() / _redline_guard() 实现。

启动:
    python -X utf8 heart_protocol/chat_server.py      （或项目根目录 start_chat.cmd）
访问:
    http://127.0.0.1:8430
"""

import json
import os
import random
import re
import string
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

HISTORY_DIR = os.path.join(_HERE, "chat_history")
PAGE_PATH = os.path.join(_HERE, "chat_page.html")

PORT = int(os.environ.get("HEART_CHAT_PORT", "8430"))
HOST = os.environ.get("HEART_CHAT_HOST", "127.0.0.1")
MAX_CONCURRENCY = max(1, int(os.environ.get("HEART_CHAT_MAX_CONCURRENCY", "2")))
MAX_MSG_LEN = 4000          # 单条消息长度上限（防误粘巨文打爆 token）
MAX_HISTORY_TURNS = 3       # 多轮上下文携带的最近轮数
HEARTBEAT_SEC = 20          # SSE 心跳间隔
QUEUE_TIMEOUT = 900         # 排队等待上限（秒）
LOCAL_STEP_DELAY = 0.15     # 本地模式每步展示延迟（秒）


# ────────────────────────────────────────────────────────────
# 1. 百炼环境变量注入（必须发生在 import heart_protocol.thinkers 之前！
#    thinkers.py 在模块顶层就固化了 EP/KEY/MODEL）
# ────────────────────────────────────────────────────────────
def _ensure_bailian_env() -> None:
    """确保进程拿到最新百炼配置（registry 优先）。

    背景：注册表里的用户级变量只有新开的 shell 才会继承，双击启动 / 从
    IDE 启动时经常拿不到；而且本机实测出现过父进程残留旧版失效 key 的
    情况（新旧 key 前缀与长度恰好相同，仅内容不同）。因此默认以 Windows
    用户级注册表 HKCU\\Environment 为配置真源，有值即覆盖进程残留。

    优先级:
      1. 注册表用户级变量（默认真源，有值即覆盖）
      2. 进程环境变量（注册表缺该项时兜底使用）
      3. 设置 HEART_CHAT_ENV_SOURCE=process 可显式要求进程优先（调试用）
    非 Windows 平台（无 winreg）直接跳过。
    """
    names = ("BAILIAN_MAAS_KEY", "BAILIAN_MAAS_ENDPOINT", "BAILIAN_MAAS_MODEL")
    proc_first = os.environ.get("HEART_CHAT_ENV_SOURCE", "").lower() == "process"
    if proc_first and all(os.environ.get(n) for n in names):
        return
    try:
        import winreg
    except ImportError:
        return
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            for name in names:
                try:
                    val, _ = winreg.QueryValueEx(k, name)
                except FileNotFoundError:
                    continue
                if isinstance(val, str) and val.strip():
                    os.environ[name] = val.strip()
    except OSError:
        # 读不到注册表就保持现状，后续由 /api/health 报告 llm_ready=False
        pass


_ensure_bailian_env()

# 2. 现在才能 import thinkers（模块级读取 BAILIAN_MAAS_* 已完成注入）
from heart_protocol.thinkers import (  # noqa: E402
    EP, KEY, MODEL, SephirahEnsemble,
)
from heart_protocol.llm_bridge import LocalSephirahBridge  # noqa: E402
from heart_protocol.protocol import HeartProtocol  # noqa: E402

LLM_READY = bool(EP and KEY)


# ────────────────────────────────────────────────────────────
# 3. SSE 发射器：线程安全写 + 心跳 + 客户端断开检测
# ────────────────────────────────────────────────────────────
class ClientDisconnected(BaseException):
    """浏览器断开 SSE 连接。

    故意继承 BaseException 而非 Exception：thinkers.py 的 TS() 只捕
    RuntimeError，run() 外层也只捕常规异常；继承 BaseException 可以
    穿透这些 except，让链路立刻中止，不再白白烧 API。
    """


class SseEmitter:
    """SSE 事件发射器（写锁保护，支持心跳线程并发写）。"""

    def __init__(self, wfile):
        self.wfile = wfile
        self.lock = threading.Lock()
        self.client_gone = False
        self._stop_hb = threading.Event()
        self._hb_thread = None

    def send(self, event: str, data: dict) -> None:
        """发送一个 SSE 事件；客户端已断开时抛 ClientDisconnected。"""
        if self.client_gone:
            raise ClientDisconnected()
        try:
            payload = json.dumps(data, ensure_ascii=False, default=str)
            chunk = f"event: {event}\ndata: {payload}\n\n".encode("utf-8")
            with self.lock:
                self.wfile.write(chunk)
                self.wfile.flush()
        except ClientDisconnected:
            raise
        except Exception:
            self.client_gone = True
            raise ClientDisconnected() from None

    def start_heartbeat(self, interval: float = HEARTBEAT_SEC) -> None:
        """启动心跳线程：周期性写 SSE 注释行 ': ping'，防中间层断连。"""
        if self._hb_thread is not None:
            return

        def _loop():
            while not self._stop_hb.wait(interval):
                if self.client_gone:
                    return
                try:
                    with self.lock:
                        self.wfile.write(b": ping\n\n")
                        self.wfile.flush()
                except Exception:
                    self.client_gone = True
                    return

        self._hb_thread = threading.Thread(target=_loop, daemon=True,
                                           name="sse-heartbeat")
        self._hb_thread.start()

    def stop_heartbeat(self) -> None:
        self._stop_hb.set()


# ────────────────────────────────────────────────────────────
# 4. 带进度回调的 16 质点编排器（thinkers.py 零改动的关键）
# ────────────────────────────────────────────────────────────
class ProgressEnsemble(SephirahEnsemble):
    """覆写 think()/_redline_guard()，把链路进度实时喂给 SSE。

    覆写点与 thinkers.py 的对应关系：
      - run() 里所有质点都经 self.think() 上场 → 覆写 think() 拿到每步进度
      - 王国产出后 run() 调 self._redline_guard() → 覆写它拿到红线兜底状态
      - TS()（智慧/理解联网）失败会退回非联网重跑 → think() 收到同一质点
        二次上场时，通过 retry 标记识别并推送「退回内置知识」事件
    """

    # thinkers.py 降级安全模板的固定前缀，用于区分「改写成功」与「降级模板」
    FALLBACK_PREFIX = "亲爱的，你此刻的感受是真实而重要的"

    def __init__(self, on_event, model: str = MODEL, trail_path: str = ""):
        super().__init__(model=model, trail_path=trail_path)
        self.on_event = on_event        # callable(event_name, data_dict)
        self._stage = 0
        self._last_who = None
        self.redline_status = "pending"
        self.redline_violations = []

    # -- 覆写：每个质点上场前后各发一个事件 --
    def think(self, key, user_input, upstream="", max_tokens=300, search=False):
        t0 = time.time()
        self._stage += 1
        retry = (self._last_who == key)
        self._last_who = key
        tk = self.thinkers[key]
        total = len(self.thinkers)

        if retry:
            # 同一质点连续上场 = TS() 联网失败后退回内置知识重跑
            self.on_event("fallback", {
                "stage": self._stage, "total": total,
                "who": key, "name": tk.name,
                "reason": "联网检索通道失败，已退回内置知识（链路不断）",
            })
        self.on_event("processing", {
            "stage": self._stage, "total": total,
            "who": key, "name": tk.name,
            "role": (tk.role or "")[:60],
            "search": bool(search),
        })

        th = super().think(key, user_input, upstream,
                           max_tokens=max_tokens, search=search)

        self.on_event("step", {
            "stage": self._stage, "total": total,
            "who": th.who, "name": th.name, "text": th.text,
            "elapsed": round(time.time() - t0, 1),
            "search": bool(th.meta.get("search")),
        })
        return th

    # -- 覆写：红线兜底状态推送 --
    def _redline_guard(self, user_input, text):
        self.on_event("redline", {"status": "checking"})
        final_text, vios = super()._redline_guard(user_input, text)
        if not vios:
            self.redline_status = "passed"
        elif final_text.startswith(self.FALLBACK_PREFIX):
            self.redline_status = "fallback_template"
        else:
            self.redline_status = "rewritten"
        self.redline_violations = [
            {"severity": getattr(v, "severity", "?"),
             "category": getattr(v, "category", "?"),
             "description": getattr(v, "description", "")}
            for v in vios
        ]
        self.on_event("redline", {
            "status": self.redline_status,
            "violations": self.redline_violations,
        })
        return final_text, vios


# ────────────────────────────────────────────────────────────
# 5. 会话历史持久化
# ────────────────────────────────────────────────────────────
class HistoryStore:
    """会话历史：一会话一 JSON 文件，写入加锁，原子落盘。

    文件结构:
    {
      "session_id": "s20261018_153000_ab12",
      "title": "首条用户消息前20字",
      "created_at": "...", "updated_at": "...",
      "messages": [
        {"role":"user","content":"...","ts":"..."},
        {"role":"assistant","content":"最终输出","ts":"...","elapsed":128.5,
         "mode":"live","thoughts":[{who,name,text,elapsed,search},...],
         "fusion_chain":[...],"violations":[...],"redline":"passed"}
      ]
    }
    """

    _ID_RE = re.compile(r"^[A-Za-z0-9_]{4,64}$")

    def __init__(self, dirpath: str):
        self.dir = dirpath
        os.makedirs(self.dir, exist_ok=True)
        self.lock = threading.Lock()

    # -- 内部工具 --
    def _path(self, sid: str) -> str:
        return os.path.join(self.dir, sid + ".json")

    def _valid(self, sid: str) -> bool:
        return bool(sid) and bool(self._ID_RE.match(sid))

    def _load(self, sid: str):
        if not self._valid(sid):
            return None
        path = self._path(sid)
        if not os.path.isfile(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return None

    def _save(self, session: dict) -> None:
        # 先写临时文件再替换，避免写一半崩溃留下残缺 JSON
        path = self._path(session["session_id"])
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(session, f, ensure_ascii=False, indent=1)
        os.replace(tmp, path)

    # -- 对外接口 --
    def new_session(self, title: str = "") -> dict:
        sid = "s" + time.strftime("%Y%m%d_%H%M%S") + "_" + \
              "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
        now = time.strftime("%Y-%m-%dT%H:%M:%S")
        session = {
            "session_id": sid,
            "title": title or "新对话",
            "created_at": now,
            "updated_at": now,
            "messages": [],
        }
        with self.lock:
            self._save(session)
        return session

    def list_sessions(self, limit: int = 200) -> list:
        """会话列表（按 updated_at 倒序），供侧栏展示。"""
        items = []
        try:
            names = [n for n in os.listdir(self.dir) if n.endswith(".json")]
        except OSError:
            names = []
        for name in names:
            sid = name[:-5]
            sess = self._load(sid)
            if not sess:
                continue
            msgs = sess.get("messages", [])
            preview = ""
            for m in reversed(msgs):
                if m.get("role") == "user" and m.get("content"):
                    preview = m["content"].replace("\n", " ")[:40]
                    break
            items.append({
                "session_id": sid,
                "title": sess.get("title", "未命名"),
                "created_at": sess.get("created_at", ""),
                "updated_at": sess.get("updated_at", ""),
                "message_count": len(msgs),
                "preview": preview,
            })
        items.sort(key=lambda x: x["updated_at"], reverse=True)
        return items[:limit]

    def get(self, sid: str):
        return self._load(sid)

    def delete(self, sid: str) -> bool:
        if not self._valid(sid):
            return False
        path = self._path(sid)
        if not os.path.isfile(path):
            return False
        with self.lock:
            os.remove(path)
        return True

    def append_user(self, sid: str, content: str) -> bool:
        """用户消息先落盘（链路中途崩溃也不丢用户输入）。"""
        with self.lock:
            sess = self._load(sid)
            if not sess:
                return False
            sess["messages"].append({
                "role": "user", "content": content,
                "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            })
            if len(sess["messages"]) == 1:
                sess["title"] = content.replace("\n", " ").strip()[:20] or "新对话"
            sess["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            self._save(sess)
        return True

    def append_assistant(self, sid: str, content: str, meta: dict) -> bool:
        with self.lock:
            sess = self._load(sid)
            if not sess:
                return False
            entry = {
                "role": "assistant", "content": content,
                "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            }
            entry.update(meta)
            sess["messages"].append(entry)
            sess["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            self._save(sess)
        return True


def build_multi_turn_input(history_msgs: list, current_msg: str) -> str:
    """把最近几轮对话拼进本轮输入，让 16 个质点都能看到上下文。

    thinkers.py 的 run() 只接受 user_input + user_context 两个入口，
    在「不改 thinkers.py」的约束下，多轮上下文只能拼进 user_input。
    用清晰的分隔标记区分「历史」与「本轮原话」，质点可自行区分。
    """
    recent = [m for m in history_msgs if not m.get("error", False)]
    recent = recent[-(MAX_HISTORY_TURNS * 2):]   # 最近 N 轮（用户+协议各一条）
    if not recent:
        return current_msg
    lines = ["【历史对话（最近几轮，仅供理解上下文）】"]
    for m in recent:
        who = "用户" if m.get("role") == "user" else "协议"
        text = (m.get("content") or "").replace("\n", " ")[:600]
        lines.append(f"{who}：{text}")
    lines.append("")
    lines.append("【本轮用户原话】")
    lines.append(current_msg)
    return "\n".join(lines)


# ────────────────────────────────────────────────────────────
# 6. HTTP 服务
# ────────────────────────────────────────────────────────────
store = HistoryStore(HISTORY_DIR)
_chain_sem = threading.BoundedSemaphore(MAX_CONCURRENCY)   # 同时跑几条 100s+ 链路
_local_protocol = None
_local_bridge = None
_local_lock = threading.Lock()


def _get_local():
    """延迟初始化本地降级引擎（HeartProtocol + LocalSephirahBridge）。"""
    global _local_protocol, _local_bridge
    with _local_lock:
        if _local_protocol is None:
            _local_protocol = HeartProtocol()
        if _local_bridge is None:
            _local_bridge = LocalSephirahBridge()
    return _local_protocol, _local_bridge


class ChatHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"   # keep-alive，SSE 需要
    server_version = "HeartChat/1.0"

    # ---- 路由 ----
    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/index.html", "/chat"):
            self._serve_page()
        elif path == "/api/health":
            self._json(200, {
                "status": "ok",
                "llm_ready": LLM_READY,
                "model": MODEL if LLM_READY else "",
                "mode": "live" if LLM_READY else "local",
                "history_dir": HISTORY_DIR,
                "max_concurrency": MAX_CONCURRENCY,
            })
        elif path == "/api/sessions":
            self._json(200, {"success": True,
                             "sessions": store.list_sessions()})
        else:
            m = re.match(r"^/api/sessions/([A-Za-z0-9_]+)$", path)
            if m:
                sess = store.get(m.group(1))
                if sess:
                    self._json(200, {"success": True, "session": sess})
                else:
                    self._json(404, {"success": False, "error": "会话不存在"})
            else:
                self.send_error(404)

    def do_POST(self):
        if urlparse(self.path).path == "/api/chat":
            self._handle_chat()
        else:
            self.send_error(404)

    def do_DELETE(self):
        m = re.match(r"^/api/sessions/([A-Za-z0-9_]+)$", urlparse(self.path).path)
        if m:
            ok = store.delete(m.group(1))
            self._json(200 if ok else 404,
                       {"success": ok, "error": None if ok else "会话不存在"})
        else:
            self.send_error(404)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", "0")
        self.end_headers()

    # ---- 页面与通用响应 ----
    def _serve_page(self):
        try:
            with open(PAGE_PATH, "r", encoding="utf-8") as f:
                html = f.read()
        except OSError as e:
            self._json(500, {"success": False,
                             "error": f"前端页面缺失: {PAGE_PATH} ({e})"})
            return
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status, data):
        body = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body_json(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length <= 0 or length > 1024 * 1024:
            return None
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None

    # ---- 核心：聊天 SSE ----
    def _handle_chat(self):
        data = self._read_body_json() or {}
        message = (data.get("message") or "").strip()
        session_id = (data.get("session_id") or "").strip()
        ctx = data.get("context") or {}
        force_local = bool(data.get("local"))

        if not message:
            self._json(400, {"success": False, "error": "消息不能为空"})
            return
        truncated = False
        if len(message) > MAX_MSG_LEN:
            message = message[:MAX_MSG_LEN]
            truncated = True

        # 会话：传入的 id 无效则新建
        sess = store.get(session_id) if session_id else None
        if sess is None:
            sess = store.new_session()
        sid = sess["session_id"]

        # 用户消息先落盘
        store.append_user(sid, message)
        history = [m for m in store.get(sid)["messages"]][:-1]  # 不含刚插入的本条

        # SSE 响应头（done 后即关闭连接，客户端无需等 EOF）
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.send_header("X-Accel-Buffering", "no")
        self.close_connection = True
        self.end_headers()

        emitter = SseEmitter(self.wfile)
        use_live = LLM_READY and not force_local

        try:
            emitter.send("session", {
                "session_id": sid, "title": store.get(sid)["title"],
                "truncated": truncated,
            })
            emitter.send("start", {
                "mode": "live" if use_live else "local",
                "model": MODEL if use_live else "内置启发式",
                "total": 16 if use_live else 8,
                "hint": "16质点全链约需 100-150 秒，每个质点完成后会在此逐一点亮"
                        if use_live else "本地降级模式（未配置百炼环境变量），"
                                        "非真实16质点链路",
            })

            # 并流控：非阻塞先试，占满则推送排队提示后阻塞等待
            if not _chain_sem.acquire(blocking=False):
                emitter.send("queue", {
                    "message": "已有链路在运行，排队等待中（最多 %d 秒）…"
                               % QUEUE_TIMEOUT,
                })
                if not _chain_sem.acquire(timeout=QUEUE_TIMEOUT):
                    emitter.send("error", {"message": "排队超时，请稍后再试"})
                    emitter.send("done", {"aborted": True})
                    return

            try:
                if use_live:
                    self._run_live_chain(emitter, sid, message, ctx, history)
                else:
                    self._run_local_chain(emitter, sid, message, ctx)
            finally:
                _chain_sem.release()

        except ClientDisconnected:
            # 用户关页面/刷新：链路已中止，不写残缺的助手消息
            print(f"  ✗ [{sid}] 客户端断开，链路中止", flush=True)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            print(f"  ✗ [{sid}] 连接中断", flush=True)
        except Exception as e:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            try:
                emitter.send("error", {"message": f"链路异常：{e}"})
                emitter.send("done", {"aborted": True})
            except ClientDisconnected:
                pass
            store.append_assistant(sid, f"⚠ 链路中断：{e}", {"error": True})
        finally:
            emitter.stop_heartbeat()

    # ---- 真实 16 质点全链 ----
    def _run_live_chain(self, emitter: SseEmitter, sid: str,
                        message: str, ctx: dict, history: list):
        emitter.start_heartbeat()
        t0 = time.time()

        ensemble = ProgressEnsemble(on_event=emitter.send)
        user_input = build_multi_turn_input(history, message)

        result = ensemble.run(user_input, user_context=ctx)
        elapsed = round(time.time() - t0, 1)

        thoughts_meta = [
            {"who": th.who, "name": th.name, "text": th.text,
             "search": bool(th.meta.get("search"))}
            for th in result.thoughts
        ]
        meta = {
            "mode": "live",
            "model": MODEL,
            "elapsed": elapsed,
            "thoughts": thoughts_meta,
            "fusion_chain": result.fusion_chain,
            "violations": ensemble.redline_violations,
            "redline": ensemble.redline_status,
        }
        # 无论浏览器是否还连着，跑完的结果都要落盘
        store.append_assistant(sid, result.output, meta)

        emitter.send("done", {
            "output": result.output,
            "elapsed": elapsed,
            "mode": "live",
            "redline": ensemble.redline_status,
            "violations": ensemble.redline_violations,
            "fusion_chain": result.fusion_chain,
            "thoughts_count": len(result.thoughts),
        })

    # ---- 本地降级链（无百炼 env 时；页头会明示非真实链路）----
    def _run_local_chain(self, emitter: SseEmitter, sid: str,
                         message: str, ctx: dict):
        t0 = time.time()
        protocol, bridge = _get_local()
        result = protocol.process(message, user_context=ctx)
        steps = bridge.step_by_step(message, user_context=ctx)
        elapsed = round(time.time() - t0, 1)

        for i, step in enumerate(steps):
            emitter.send("processing", {
                "stage": i + 1, "total": len(steps),
                "who": step["sephirah"], "name": step["name"],
                "role": step.get("description", ""), "search": False,
            })
            time.sleep(LOCAL_STEP_DELAY)
            emitter.send("step", {
                "stage": i + 1, "total": len(steps),
                "who": step["sephirah"], "name": step["name"],
                "text": step.get("output", ""),
                "elapsed": LOCAL_STEP_DELAY, "search": False,
            })

        meta = {
            "mode": "local", "elapsed": elapsed,
            "thoughts": [
                {"who": s["sephirah"], "name": s["name"],
                 "text": s.get("output", ""), "search": False}
                for s in steps
            ],
            "fusion_chain": [], "violations": [], "redline": "local",
        }
        store.append_assistant(sid, result["output"], meta)
        emitter.send("done", {
            "output": result["output"], "elapsed": elapsed, "mode": "local",
            "redline": "local", "violations": [],
            "fusion_chain": [], "thoughts_count": len(steps),
        })

    # ---- 日志精简 ----
    def log_message(self, fmt, *args):
        sys.stderr.write("[%s] %s\n" %
                         (time.strftime("%H:%M:%S"), fmt % args))


# ────────────────────────────────────────────────────────────
# 7. 入口
# ────────────────────────────────────────────────────────────
def main():
    mode_desc = (
        f"真实16质点全链（百炼 · {MODEL}）" if LLM_READY
        else "⚠ 未检测到 BAILIAN_MAAS_KEY/ENDPOINT，将降级本地模式"
    )
    print("=" * 58)
    print("  16质点双生幸福最终协议 · 日常聊天服务")
    print("=" * 58)
    print(f"  访问地址 : http://{HOST}:{PORT}")
    print(f"  运行模式 : {mode_desc}")
    print(f"  历史目录 : {HISTORY_DIR}")
    print(f"  并发链路 : {MAX_CONCURRENCY}（多出的请求自动排队）")
    print(f"  单次回复 : 真实链路约 100-150 秒，页面实时显示质点进度")
    print("-" * 58)
    print("  按 Ctrl+C 停止服务")
    print()

    server = ThreadingHTTPServer((HOST, PORT), ChatHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 服务已停止")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()