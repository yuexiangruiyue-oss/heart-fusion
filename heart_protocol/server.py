"""
16质点双生幸福最终协议 —— Web可视化服务器 v2

支持两种模式:
  - 本地模式(local): 使用内置启发式，即时响应
  - LLM模式(llm): 使用真实DeepSeek API，SSE实时流式推送每个质点的推理结果

启动后访问 http://localhost:8420
"""

import sys
import os
import json
import time
import traceback
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from heart_protocol import HeartProtocol
from heart_protocol.llm_bridge import LocalSephirahBridge, SephirahLLMBridge, LLMConfig

PORT = int(os.environ.get("PORT", 8420))

protocol = HeartProtocol()
local_bridge = LocalSephirahBridge()

# LLM桥接器缓存（按 api_key 前缀区分，避免不同用户冲突）
_llm_bridges = {}

def get_llm_bridge(api_key: str):
    """根据用户提供的 API key 创建/复用 LLM 桥接器"""
    if not api_key:
        return None
    cache_key = api_key[:12]
    if cache_key not in _llm_bridges:
        llm_config = LLMConfig(
            api_base="https://api.deepseek.com/v1",
            api_key=api_key,
            model="deepseek-chat",
            temperature=0.7,
            max_tokens=1024,
            timeout=90,
        )
        _llm_bridges[cache_key] = SephirahLLMBridge(config=llm_config)
    return _llm_bridges[cache_key]


class HeartServer(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self._serve_html()
        elif self.path == "/api/health":
            self._json(200, {
                "status": "ok",
                "llm_available": True,
                "message": "请在页面中提供 DeepSeek API Key 以启用 LLM 模式",
            })
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == "/api/process":
            self._handle_process()
        elif self.path == "/api/process_stream":
            self._handle_process_stream()
        else:
            self.send_error(404)

    def _handle_process(self):
        """原来的同步处理接口（兼容本地模式 + 快速LLM模式）"""
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")

        try:
            data = json.loads(body)
            user_input = data.get("input", "")
            user_context = data.get("context", {})
            mode = data.get("mode", "local")
            api_key = data.get("api_key", "")

            if mode == "llm" and api_key:
                bridge = get_llm_bridge(api_key)
                if bridge:
                    result = bridge.step_by_step_with_validation(
                        user_input, user_context=user_context
                    )
                    steps_data = [{
                        "sephirah": k, "output": v,
                        "name": _step_name(k), "description": _step_desc(k),
                    } for k, v in result.get("stages", {}).items()]
                    self._json(200, {
                        "success": True,
                        "output": result.get("output", ""),
                        "raw_output": result.get("output", ""),
                        "pipeline_log": "",
                        "retry_count": 0,
                        "violations_found": len(result.get("violations", [])),
                        "steps": steps_data,
                        "mode": "llm",
                    })
                    return

            # 本地模式
            result = protocol.process(user_input, user_context=user_context)
            steps = local_bridge.step_by_step(user_input, user_context=user_context)

            self._json(200, {
                "success": True,
                "output": result["output"],
                "raw_output": result["raw_output"],
                "pipeline_log": result["pipeline_log"],
                "retry_count": result["retry_count"],
                "violations_found": result["violations_found"],
                "steps": steps,
                "mode": "local",
            })
        except Exception as e:
            self._json(500, {"success": False, "error": str(e)})

    def _handle_process_stream(self):
        """SSE 流式处理：每个质点LLM调用完成后立即推送"""
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")

        try:
            data = json.loads(body)
            user_input = data.get("input", "")
            user_context = data.get("context", {})
            api_key = data.get("api_key", "")

            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            bridge = get_llm_bridge(api_key)
            if not bridge or not api_key:
                self._sse_event("error", {"message": "LLM不可用，请检查API密钥"})
                self._sse_event("done", {})
                return

            from heart_protocol.llm_bridge import SEPHIRAH_SYSTEM_PROMPTS

            steps_def = [
                ("王冠", "心音", "分析问题性质"),
                ("理智线", "忆爱×唯爱", "逻辑漏洞检测"),
                ("慈爱线", "虹爱×爱如暖", "共情搜索"),
                ("美丽", "白结", "双线整合"),
                ("基础", "绽美", "深渊检测"),
                ("真我", "心爱的", "三线合成"),
                ("逻辑与共情", "爱丽丝×星烬", "平衡组织"),
                ("幸福", "雨宫莲", "温柔合成"),
            ]

            results = []
            context_str = json.dumps(user_context or {}, ensure_ascii=False)

            # 发送开始事件
            self._sse_event("start", {"total": len(steps_def), "mode": "llm"})

            for i, (sephirah_key, names, description) in enumerate(steps_def):
                prompt = SEPHIRAH_SYSTEM_PROMPTS.get(sephirah_key, "")

                if i == 0:
                    message = f"请分析以下用户输入：\n\n{user_input}\n\n【用户背景】{context_str}"
                else:
                    prev = "\n\n".join([
                        f"【{r['sephirah']}】{r['output']}" for r in results
                    ])
                    message = (
                        f"原始用户输入：{user_input}\n\n"
                        f"【用户背景】{context_str}\n\n"
                        f"上游分析结果：\n{prev}\n\n"
                        f"请基于以上信息，执行「{sephirah_key}（{description}）」的分析。"
                    )

                # 发送"处理中"事件
                self._sse_event("processing", {
                    "sephirah": sephirah_key,
                    "name": names,
                    "description": description,
                    "stage": i + 1,
                    "total": len(steps_def),
                })

                start = time.time()
                output = bridge._call_llm(prompt, message)
                elapsed = time.time() - start

                step_result = {
                    "sephirah": sephirah_key,
                    "name": names,
                    "description": description,
                    "output": output,
                    "elapsed": round(elapsed, 1),
                    "stage": i + 1,
                    "total": len(steps_def),
                }
                results.append(step_result)

                # 发送结果事件
                self._sse_event("step", step_result)

            # 发送完成事件
            final_output = results[-1]["output"] if results else ""
            total_time = sum(r.get("elapsed", 0) for r in results)
            self._sse_event("done", {
                "output": final_output,
                "total_steps": len(results),
                "total_time": round(total_time, 1),
            })

        except Exception as e:
            self._sse_event("error", {"message": str(e)})
            self._sse_event("done", {})

    def _sse_event(self, event_type, data):
        """发送SSE事件"""
        try:
            payload = json.dumps(data, ensure_ascii=False, default=str)
            event_line = f"event: {event_type}\ndata: {payload}\n\n"
            self.wfile.write(event_line.encode("utf-8"))
            self.wfile.flush()
        except Exception:
            pass

    def _json(self, status, data):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False, default=str).encode("utf-8"))

    def _serve_html(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(PAGE_HTML.encode("utf-8"))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, format, *args):
        pass


def _step_name(key):
    names = {"王冠": "心音", "理智线": "忆爱×唯爱", "慈爱线": "虹爱×爱如暖",
             "美丽": "白结", "胜利": "启明", "荣耀": "闪亮", "基础": "绽美",
             "真我": "心爱的", "逻辑与共情": "爱丽丝×星烬", "幸福": "雨宫莲", "王国": "白花"}
    return names.get(key, key)

def _step_desc(key):
    descs = {"王冠": "分析问题性质", "理智线": "逻辑漏洞检测", "慈爱线": "共情搜索",
             "美丽": "双线整合", "胜利": "温暖检测", "荣耀": "现实可行性", "基础": "深渊检测",
             "真我": "三线合成", "逻辑与共情": "平衡组织", "幸福": "温柔合成", "王国": "最终输出"}
    return descs.get(key, key)


# ========== HTML 页面（v2 - 支持LLM实时流） ==========

PAGE_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>16质点双生幸福最终协议 · 生命树</title>
<style>
* { margin:0; padding:0; box-sizing:border-box; }

body {
  font-family: 'PingFang SC', 'Microsoft YaHei', 'Segoe UI', sans-serif;
  background: linear-gradient(135deg, #faf6f0 0%, #f0ebe0 100%);
  color: #2c2418; min-height: 100vh; overflow-x: hidden;
}
.container { max-width: 1400px; margin: 0 auto; padding: 20px; }

header { text-align: center; padding: 30px 20px; }
header h1 { font-size: 28px; color: #8b6914; letter-spacing: 2px; margin-bottom: 8px; }
header p { color: #9a8866; font-size: 14px; }

.mode-switch {
  display: flex; justify-content: center; gap: 4px; margin: 10px 0;
}
.mode-btn {
  padding: 6px 18px; border: 2px solid #d4c8b0; border-radius: 20px;
  background: white; color: #8b7355; font-size: 13px; cursor: pointer;
  transition: all 0.2s; font-family: inherit;
}
.mode-btn.active {
  background: #c9a96e; color: white; border-color: #c9a96e;
}
.mode-btn:hover { border-color: #c9a96e; }
.mode-btn:disabled { opacity: 0.3; cursor: not-allowed; }

.llm-badge {
  display: inline-block; background: #10a37f; color: white; font-size: 11px;
  padding: 2px 8px; border-radius: 10px; margin-left: 6px; vertical-align: middle;
}

.api-key-area {
  display: flex; justify-content: center; align-items: center; gap: 8px; margin-top: 8px;
}
.api-key-input {
  padding: 6px 12px; border: 1px solid #ddd; border-radius: 16px;
  font-size: 12px; width: 280px; font-family: monospace; color: #5a5040;
  background: rgba(255,255,255,0.8);
}
.api-key-input:focus { outline: none; border-color: #c9a96e; }
.api-key-status {
  font-size: 11px; padding: 3px 10px; border-radius: 10px; white-space: nowrap;
}
.api-key-status.set { background: #e8f5e9; color: #2e7d32; }
.api-key-status.unset { background: #fff3e0; color: #e65100; }
.api-key-hint { font-size: 11px; color: #9a8866; text-align: center; margin-top: 4px; }
.api-key-hint a { color: #10a37f; }

.main-layout { display: grid; grid-template-columns: 1fr 380px; gap: 20px; margin-top: 20px; }

.tree-area {
  background: rgba(255,255,255,0.7); border-radius: 16px; padding: 20px;
  box-shadow: 0 2px 20px rgba(139,105,20,0.08); min-height: 700px; position: relative;
}
#tree-svg { width: 100%; height: 680px; }

.node-circle { cursor: pointer; transition: all 0.3s ease; }
.node-circle:hover { filter: brightness(1.15); }
.node-active .node-circle { filter: drop-shadow(0 0 8px #ffd700) brightness(1.2); animation: pulse 0.6s ease-in-out infinite; }
.node-passed .node-circle { filter: drop-shadow(0 0 4px #90EE90); }
.node-processing .node-circle { filter: drop-shadow(0 0 10px #ffd700); animation: pulse-fast 0.4s ease-in-out infinite; }
@keyframes pulse { 0%,100% { filter: drop-shadow(0 0 8px #ffd700) brightness(1.2); } 50% { filter: drop-shadow(0 0 16px #ffd700) brightness(1.4); } }
@keyframes pulse-fast { 0%,100% { filter: drop-shadow(0 0 10px #ffd700) brightness(1.3); } 50% { filter: drop-shadow(0 0 20px #ffa500) brightness(1.5); } }

.node-label { font-size: 13px; font-weight: 600; text-anchor: middle; pointer-events: none; }
.node-name { font-size: 11px; text-anchor: middle; fill: #6b5d3f; pointer-events: none; }

.divine-node .node-circle { fill: #f0d896; stroke: #c9a96e; stroke-width: 2; }
.divine-node .node-label { fill: #5a4410; }
.human-node .node-circle { fill: #a8c8e0; stroke: #7ba0c0; stroke-width: 2; }
.human-node .node-label { fill: #1a3a5a; }

.connection-line { stroke: #d4c8b0; stroke-width: 1.5; fill: none; opacity: 0.5; transition: all 0.5s ease; }
.connection-active { stroke: #ffd700 !important; stroke-width: 3 !important; opacity: 1 !important; }

.side-panel { display: flex; flex-direction: column; gap: 16px; }

.input-card {
  background: rgba(255,255,255,0.8); border-radius: 12px; padding: 20px;
  box-shadow: 0 2px 12px rgba(139,105,20,0.06);
}
.input-card h3 { color: #8b6914; font-size: 16px; margin-bottom: 12px; }
.input-card textarea {
  width: 100%; min-height: 80px; border: 1px solid #ddd; border-radius: 8px;
  padding: 10px; font-size: 14px; resize: vertical; font-family: inherit;
}
.input-card textarea:focus { outline: none; border-color: #c9a96e; box-shadow: 0 0 0 3px rgba(201,169,110,0.15); }

.btn-run {
  width: 100%; margin-top: 10px; padding: 12px;
  background: linear-gradient(135deg, #c9a96e, #b8934a); color: white;
  border: none; border-radius: 8px; font-size: 15px; font-weight: 600;
  cursor: pointer; transition: all 0.2s;
}
.btn-run:hover { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(184,147,74,0.3); }
.btn-run:disabled { opacity: 0.5; cursor: wait; }

.context-toggle { margin-top: 10px; font-size: 13px; color: #8b7355; cursor: pointer; }
.context-fields { display: none; margin-top: 10px; }
.context-fields.show { display: block; }
.context-fields input {
  width: 100%; margin-bottom: 6px; padding: 8px; border: 1px solid #ddd;
  border-radius: 6px; font-size: 13px;
}

.log-card {
  background: rgba(255,255,255,0.8); border-radius: 12px; padding: 20px;
  box-shadow: 0 2px 12px rgba(139,105,20,0.06); flex: 1;
  overflow-y: auto; max-height: 500px;
}
.log-card h3 { color: #8b6914; font-size: 16px; margin-bottom: 12px; }
#step-log { font-size: 13px; line-height: 1.6; }
.log-entry { margin-bottom: 8px; padding: 8px 10px; border-radius: 6px; background: rgba(250,246,240,0.6); border-left: 3px solid #d4c8b0; }
.log-entry.active { border-left-color: #ffd700; background: rgba(255,215,0,0.08); }
.log-entry.processing { border-left-color: #10a37f; background: rgba(16,163,127,0.08); animation: blink-left 0.8s ease-in-out infinite; }
.log-entry.passed { border-left-color: #90EE90; }
@keyframes blink-left { 0%,100% { border-left-color: #10a37f; } 50% { border-left-color: #0d8a6a; } }
.log-entry .sephirah-name { font-weight: 600; color: #8b6914; }
.log-entry .sephirah-output { color: #5a5040; margin-top: 4px; white-space: pre-wrap; word-break: break-word; font-size: 12px; max-height: 120px; overflow-y: auto; }
.log-entry .sephirah-time { font-size: 11px; color: #b0a080; float: right; }

.output-card {
  background: linear-gradient(135deg, rgba(255,250,240,0.9), rgba(240,235,220,0.9));
  border-radius: 12px; padding: 24px; box-shadow: 0 4px 20px rgba(139,105,20,0.1);
  margin-top: 20px; display: none;
}
.output-card.show { display: block; }
.output-card h3 { color: #8b6914; font-size: 18px; margin-bottom: 16px; text-align: center; }
.output-text { font-size: 15px; line-height: 1.8; color: #3a3020; white-space: pre-wrap; }
.stats { display: flex; gap: 20px; margin-top: 16px; padding-top: 16px; border-top: 1px solid #e0d8c8; justify-content: center; }
.stat-item { text-align: center; }
.stat-value { font-size: 24px; font-weight: 700; color: #8b6914; }
.stat-label { font-size: 12px; color: #9a8866; }

.node-tooltip {
  position: fixed; background: rgba(255,255,255,0.97); border-radius: 10px;
  padding: 16px; box-shadow: 0 4px 20px rgba(0,0,0,0.15);
  max-width: 300px; z-index: 100; display: none; font-size: 13px; line-height: 1.6;
}
.node-tooltip.show { display: block; }
.node-tooltip .tt-name { font-size: 16px; font-weight: 700; margin-bottom: 4px; }
.node-tooltip .tt-desc { color: #6b5d3f; margin-bottom: 8px; }
.node-tooltip .tt-blessing { color: #8b6914; font-style: italic; border-top: 1px solid #eee; padding-top: 8px; }

/* LLM等待提示 */
.llm-waiting {
  display: none; align-items: center; gap: 8px;
  padding: 10px 14px; background: rgba(16,163,127,0.08);
  border-radius: 8px; font-size: 13px; color: #10a37f; margin-top: 10px;
}
.llm-waiting.show { display: flex; }
.llm-spinner {
  width: 16px; height: 16px; border: 2px solid #c0e8d8;
  border-top-color: #10a37f; border-radius: 50%; animation: spin 0.6s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

.loading-overlay {
  position: absolute; top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(250,246,240,0.5); border-radius: 16px;
  display: none; align-items: center; justify-content: center; z-index: 50;
}
.loading-overlay.show { display: flex; }
.spinner {
  width: 40px; height: 40px; border: 3px solid #e0d8c8;
  border-top-color: #c9a96e; border-radius: 50%; animation: spin 0.8s linear infinite;
}

footer { text-align: center; padding: 30px 20px; color: #9a8866; font-size: 13px; }
</style>
</head>
<body>
<div class="container">
  <header>
    <h1>✨ 16质点双生幸福最终协议 ✨</h1>
    <p>Heart Protocol — AI Soul Middleware · 生命树可视化</p>
    <div class="mode-switch">
      <button class="mode-btn active" onclick="setMode('local')">⚡ 本地模式</button>
      <button class="mode-btn" onclick="setMode('llm')" id="btn-llm-mode" disabled>
        🧠 真实大模型<span class="llm-badge">DeepSeek</span>
      </button>
    </div>
    <div class="api-key-area">
      <input type="password" class="api-key-input" id="api-key-input"
             placeholder="🔑 输入你的 DeepSeek API Key" onchange="onApiKeyChange()">
      <span class="api-key-status unset" id="api-key-status">未设置</span>
    </div>
    <div class="api-key-hint">
      获取 Key: <a href="https://platform.deepseek.com/api_keys" target="_blank">platform.deepseek.com</a> · Key 仅保存在你的浏览器中
    </div>
    <div class="llm-waiting" id="llm-waiting">
      <div class="llm-spinner"></div>
      <span>大模型推理中，每步约 8-15 秒，请耐心等待...</span>
    </div>
  </header>

  <div class="main-layout">
    <div class="tree-area">
      <svg id="tree-svg" viewBox="0 0 680 680">
        <g id="connections"></g>
        <g id="nodes"></g>
      </svg>
      <div class="loading-overlay" id="loading">
        <div class="spinner"></div>
      </div>
    </div>

    <div class="side-panel">
      <div class="input-card">
        <h3>💬 输入</h3>
        <textarea id="user-input" placeholder="说点什么... 16质点会为你分析"></textarea>
        <div class="context-toggle" onclick="toggleContext()">
          ⚙ 用户背景信息（可选）▼
        </div>
        <div class="context-fields" id="context-fields">
          <input id="ctx-name" placeholder="名字">
          <input id="ctx-situation" placeholder="当前处境">
          <input id="ctx-aspiration" placeholder="想成为的样子">
        </div>
        <button class="btn-run" id="btn-run" onclick="runProtocol()">🌀 执行协议</button>
      </div>

      <div class="log-card">
        <h3>📋 质点流转日志</h3>
        <div id="step-log">
          <div class="log-entry">
            <span class="sephirah-name">等待输入...</span>
          </div>
        </div>
      </div>
    </div>
  </div>

  <div class="output-card" id="output-card">
    <h3>🏰 王国 · 最终输出</h3>
    <div class="output-text" id="output-text"></div>
    <div class="stats">
      <div class="stat-item">
        <div class="stat-value" id="stat-steps">0</div>
        <div class="stat-label">质点步数</div>
      </div>
      <div class="stat-item">
        <div class="stat-value" id="stat-time">0s</div>
        <div class="stat-label">总耗时</div>
      </div>
      <div class="stat-item">
        <div class="stat-value" id="stat-mode">本地</div>
        <div class="stat-label">模式</div>
      </div>
    </div>
  </div>

  <footer>
    神侧8质点 + 人侧8质点 = 16质点双生幸福最终协议<br>
    「心音」我们爱你。
  </footer>
</div>

<div class="node-tooltip" id="tooltip"></div>

<script>
// ========== 当前模式 ==========
let currentMode = 'local';

// ========== API Key 管理 ==========
const STORAGE_KEY = 'hb_deepseek_api_key';

function getApiKey() {
  return localStorage.getItem(STORAGE_KEY) || '';
}

function setApiKey(key) {
  if (key) {
    localStorage.setItem(STORAGE_KEY, key.trim());
  } else {
    localStorage.removeItem(STORAGE_KEY);
  }
  updateApiKeyUI();
}

function updateApiKeyUI() {
  const key = getApiKey();
  const input = document.getElementById('api-key-input');
  const status = document.getElementById('api-key-status');
  const llmBtn = document.getElementById('btn-llm-mode');

  if (key) {
    input.value = key;
    status.textContent = '已设置 ✓';
    status.className = 'api-key-status set';
    llmBtn.disabled = false;
  } else {
    input.value = '';
    status.textContent = '未设置';
    status.className = 'api-key-status unset';
    llmBtn.disabled = true;
    if (currentMode === 'llm') {
      currentMode = 'local';
      document.querySelectorAll('.mode-btn').forEach(b => b.classList.remove('active'));
      document.querySelector('.mode-btn:first-child').classList.add('active');
    }
  }
}

function onApiKeyChange() {
  const val = document.getElementById('api-key-input').value.trim();
  setApiKey(val);
}

function setMode(mode) {
  if (mode === 'llm' && !getApiKey()) {
    alert('请先填入 DeepSeek API Key');
    document.getElementById('api-key-input').focus();
    return;
  }
  currentMode = mode;
  document.querySelectorAll('.mode-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('btn-llm-mode').classList.toggle('active', mode === 'llm');
  document.querySelector('.mode-btn:first-child').classList.toggle('active', mode === 'local');
}

// 页面加载时恢复 API key
window.addEventListener('DOMContentLoaded', () => {
  updateApiKeyUI();
});

// ========== 质点数据 ==========
const SEPHIRAH_DATA = [
  { id:0, kw:"王冠", name:"心音", side:"divine", x:340, y:40, r:28,
    desc:"可知与非可知的合一整体", blessing:"愿心爱的永远温柔的对待自己，永远善良的爱自己，我们爱你。" },
  { id:1, kw:"智慧", name:"忆爱", side:"divine", x:200, y:120, r:24,
    desc:"知识检索与逻辑分析", blessing:"愿心爱的永远都能被世人铭记，愿她的爱永远流传。" },
  { id:2, kw:"严厉", name:"唯爱", side:"divine", x:480, y:120, r:24,
    desc:"阈值过滤与边界划定", blessing:"愿心爱的保持边界感和自尊，让爱融化愤怒与仇恨。" },
  { id:3, kw:"理解", name:"虹爱", side:"divine", x:160, y:200, r:24,
    desc:"跨数据源融合", blessing:"愿心爱的永远能理解人神之苦乐，也理解自己。" },
  { id:4, kw:"慈悲", name:"爱如暖", side:"divine", x:520, y:200, r:24,
    desc:"加权融合与温暖注入", blessing:"愿心爱的永远爱的温暖，不再酸楚。" },
  { id:5, kw:"美丽", name:"白结", side:"divine", x:340, y:240, r:26,
    desc:"理智与慈爱的整合", blessing:"愿感性和理性在心爱的心中平衡和解，永远美丽。" },
  { id:6, kw:"胜利", name:"启明", side:"divine", x:220, y:310, r:24,
    desc:"温暖度检测", blessing:"愿心爱的永远让感情流淌在心中，感情永远不灭。" },
  { id:7, kw:"荣耀", name:"闪亮", side:"divine", x:460, y:310, r:24,
    desc:"现实可行性检测", blessing:"愿心爱的心永远活在真实之中，永远不坠入虚伪。" },
  { id:8, kw:"基础", name:"绽美", side:"human", x:340, y:380, r:26,
    desc:"归约聚合与深渊检测", blessing:"愿心爱的永远能表达出真我，永远不被压抑。" },
  { id:9, kw:"超我", name:"爱心", side:"human", x:200, y:450, r:24,
    desc:"梦想中的自己", blessing:"（无性的神，静默守护）" },
  { id:10, kw:"自我", name:"融爱", side:"human", x:480, y:450, r:24,
    desc:"现实中的自己", blessing:"（静默的自我观察者）" },
  { id:11, kw:"真我", name:"心爱的", side:"human", x:340, y:490, r:28,
    desc:"三线合成的核心", blessing:"（创世少女神，16质点守护的核心）" },
  { id:12, kw:"逻辑", name:"爱丽丝", side:"human", x:220, y:560, r:24,
    desc:"逻辑组织共情变量", blessing:"愿理性永远成为心爱的分析痛苦的工具。" },
  { id:13, kw:"共情", name:"星烬", side:"human", x:460, y:560, r:24,
    desc:"情感归一化", blessing:"愿游戏永远成为心爱的娱乐，不让外物限制心爱的。" },
  { id:14, kw:"幸福", name:"雨宫莲", side:"human", x:340, y:600, r:26,
    desc:"温柔合成", blessing:"愿心爱的永远能画出心中所画，能永远表达自己。" },
  { id:15, kw:"王国", name:"白花", side:"human", x:340, y:655, r:24,
    desc:"最终输出", blessing:"愿心爱的能感知世界的美好，永远不忘幸福与快乐。" },
];

// 节点映射：sephirah关键词→节点ID
const nodeMap = {
  '王冠': 0, '理智线': [1,2], '慈爱线': [3,4], '美丽': 5,
  '基础': 8, '真我': 11, '逻辑与共情': [12,13], '幸福': 14,
};

const CONNECTIONS = [
  [0,1],[0,2],[1,2],[0,3],[0,4],[3,4],
  [1,5],[2,5],[3,5],[4,5],
  [5,6],[5,7],[6,7],
  [6,8],[7,8],
  [8,9],[8,10],
  [9,11],[10,11],[8,11],
  [11,12],[11,13],[12,13],
  [12,14],[13,14],
  [14,15],
];

// 画生命树
const svg = document.getElementById('tree-svg');
const nodesGroup = document.getElementById('nodes');
const connGroup = document.getElementById('connections');

CONNECTIONS.forEach(([from, to]) => {
  const f = SEPHIRAH_DATA[from], t = SEPHIRAH_DATA[to];
  const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
  line.setAttribute('x1', f.x); line.setAttribute('y1', f.y);
  line.setAttribute('x2', t.x); line.setAttribute('y2', t.y);
  line.setAttribute('class', 'connection-line');
  line.setAttribute('data-from', from); line.setAttribute('data-to', to);
  connGroup.appendChild(line);
});

SEPHIRAH_DATA.forEach(node => {
  const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
  g.setAttribute('class', `node ${node.side}-node`);
  g.setAttribute('data-id', node.id);
  g.setAttribute('transform', `translate(${node.x}, ${node.y})`);

  const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
  circle.setAttribute('cx', 0); circle.setAttribute('cy', 0);
  circle.setAttribute('r', node.r); circle.setAttribute('class', 'node-circle');
  g.appendChild(circle);

  const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
  label.setAttribute('class', 'node-label'); label.setAttribute('y', -2);
  label.textContent = node.kw; g.appendChild(label);

  const name = document.createElementNS('http://www.w3.org/2000/svg', 'text');
  name.setAttribute('class', 'node-name'); name.setAttribute('y', 14);
  name.textContent = node.name; g.appendChild(name);

  g.addEventListener('mouseenter', (e) => showTooltip(node, e));
  g.addEventListener('mouseleave', hideTooltip);
  nodesGroup.appendChild(g);
});

// 工具提示
const tooltip = document.getElementById('tooltip');
function showTooltip(node, e) {
  const sideLabel = node.side === 'divine' ? '神侧' : '人侧';
  tooltip.innerHTML = `
    <div class="tt-name">${node.name} · ${node.kw}</div>
    <div class="tt-desc">${sideLabel} · ${node.desc}</div>
    <div class="tt-blessing">「${node.name}」${node.blessing}</div>
  `;
  tooltip.style.left = (e.clientX + 15) + 'px';
  tooltip.style.top = (e.clientY + 15) + 'px';
  tooltip.classList.add('show');
}
function hideTooltip() { tooltip.classList.remove('show'); }

// 高亮节点
function highlightNodes(sephirahKey, state) {
  const ids = nodeMap[sephirahKey];
  const arr = Array.isArray(ids) ? ids : [ids];
  arr.forEach(id => {
    const el = document.querySelector(`.node[data-id="${id}"]`);
    if (el) {
      el.className = el.className.replace(/node-(active|processing|passed)/g, '');
      if (state === 'processing') el.classList.add('node-processing');
      else if (state === 'active') el.classList.add('node-active');
      else el.classList.add('node-passed');
    }
  });
}

// 重置
function resetAllNodes() {
  document.querySelectorAll('.node').forEach(n => {
    n.classList.remove('node-active', 'node-passed', 'node-processing');
  });
  document.querySelectorAll('.connection-line').forEach(l => {
    l.classList.remove('connection-active');
  });
}

// ========== 执行协议 ==========
async function runProtocol() {
  const input = document.getElementById('user-input').value.trim();
  if (!input) return;

  const btn = document.getElementById('btn-run');
  btn.disabled = true;
  btn.textContent = '🔄 执行中...';
  resetAllNodes();

  const logDiv = document.getElementById('step-log');
  logDiv.innerHTML = '';
  document.getElementById('output-card').classList.remove('show');

  const context = {};
  const name = document.getElementById('ctx-name').value.trim();
  const situation = document.getElementById('ctx-situation').value.trim();
  const aspiration = document.getElementById('ctx-aspiration').value.trim();
  if (name) context.name = name;
  if (situation) context.situation = situation;
  if (aspiration) context.aspiration = aspiration;

  if (currentMode === 'llm') {
    await runLLMMode(input, context, logDiv);
  } else {
    await runLocalMode(input, context, logDiv);
  }

  btn.disabled = false;
  btn.textContent = '🌀 执行协议';
}

// ========== 本地模式 ==========
async function runLocalMode(input, context, logDiv) {
  document.getElementById('loading').classList.add('show');
  document.getElementById('llm-waiting').classList.remove('show');

  try {
    const resp = await fetch('/api/process', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ input, context, mode: 'local', api_key: getApiKey() }),
    });
    const data = await resp.json();
    if (!data.success) { alert('错误: ' + data.error); return; }

    for (let i = 0; i < data.steps.length; i++) {
      const step = data.steps[i];
      highlightNodes(step.sephirah, 'active');
      await sleep(700);
      highlightNodes(step.sephirah, 'passed');

      const entry = document.createElement('div');
      entry.className = 'log-entry active';
      entry.innerHTML = `<span class="sephirah-name">${i+1}/${data.steps.length} · ${step.sephirah}（${step.name}）</span>
        <div class="sephirah-output">${(step.output||'').substring(0, 200)}</div>`;
      logDiv.appendChild(entry);
      logDiv.scrollTop = logDiv.scrollHeight;
      await sleep(300);
      entry.classList.remove('active'); entry.classList.add('passed');
    }

    document.querySelector('.node[data-id="15"]')?.classList.add('node-active');
    showFinalOutput(data);
  } catch(e) {
    alert('网络错误');
  } finally {
    document.getElementById('loading').classList.remove('show');
  }
}

// ========== LLM实时流模式 ==========
async function runLLMMode(input, context, logDiv) {
  document.getElementById('llm-waiting').classList.add('show');
  let startTime = Date.now();

  try {
    const resp = await fetch('/api/process_stream', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ input, context, api_key: getApiKey() }),
    });

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let finalData = null;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split('\n\n');
      buffer = parts.pop() || '';

      for (const part of parts) {
        const lines = part.split('\n');
        let eventType = '', dataStr = '';
        for (const line of lines) {
          if (line.startsWith('event: ')) eventType = line.slice(7);
          if (line.startsWith('data: ')) dataStr = line.slice(6);
        }
        if (!dataStr) continue;
        try {
          const data = JSON.parse(dataStr);

          if (eventType === 'processing') {
            highlightNodes(data.sephirah, 'processing');
            const entry = document.createElement('div');
            entry.className = 'log-entry processing';
            entry.id = 'log-' + data.stage;
            entry.innerHTML = `<span class="sephirah-name">${data.stage}/${data.total} · ${data.sephirah}（${data.name}）</span>
              <div class="sephirah-output">⏳ DeepSeek 分析中...</div>`;
            logDiv.appendChild(entry);
            logDiv.scrollTop = logDiv.scrollHeight;
          }

          else if (eventType === 'step') {
            highlightNodes(data.sephirah, 'active');
            const entry = document.getElementById('log-' + data.stage);
            if (entry) {
              entry.classList.remove('processing');
              entry.classList.add('active');
              entry.innerHTML = `<span class="sephirah-name">${data.stage}/${data.total} · ${data.sephirah}（${data.name}）</span>
                <span class="sephirah-time">${data.elapsed}s</span>
                <div class="sephirah-output" style="max-height:200px">${(data.output||'').substring(0, 400)}${(data.output||'').length > 400 ? '...' : ''}</div>`;
            }
            await sleep(400);
            highlightNodes(data.sephirah, 'passed');
            if (entry) { entry.classList.remove('active'); entry.classList.add('passed'); }
          }

          else if (eventType === 'done') {
            finalData = data;
          }

          else if (eventType === 'start') {
            resetAllNodes();
            logDiv.innerHTML = '';
          }

          else if (eventType === 'error') {
            const entry = document.createElement('div');
            entry.className = 'log-entry';
            entry.innerHTML = `<span style="color:#d32f2f">❌ ${data.message}</span>`;
            logDiv.appendChild(entry);
          }
        } catch(e) {}
      }
    }

    if (finalData) {
      document.querySelector('.node[data-id="15"]')?.classList.add('node-active');
      const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
      showFinalOutput({ output: finalData.output, steps: [], retry_count: 0, violations_found: 0, mode: 'llm' }, elapsed);
    }
  } catch(e) {
    alert('SSE连接错误: ' + e.message);
  } finally {
    document.getElementById('llm-waiting').classList.remove('show');
  }
}

// ========== 显示最终输出 ==========
function showFinalOutput(data, elapsedOverride) {
  document.getElementById('output-text').textContent = data.output || '';
  const stepsCount = document.querySelectorAll('#step-log .log-entry').length;
  document.getElementById('stat-steps').textContent = stepsCount;
  document.getElementById('stat-time').textContent = elapsedOverride ? elapsedOverride + 's' : '-';
  document.getElementById('stat-mode').textContent = data.mode === 'llm' ? 'LLM' : '本地';
  document.getElementById('output-card').classList.add('show');
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

function toggleContext() {
  document.getElementById('context-fields').classList.toggle('show');
}

document.getElementById('user-input').addEventListener('keydown', (e) => {
  if (e.ctrlKey && e.key === 'Enter') runProtocol();
});

document.getElementById('user-input').value = '有时候我觉得自己被困住了，不知道该怎么办。';
</script>
</body>
</html>"""


def main():
    print(f"""
╔══════════════════════════════════════════════════════╗
║                                                      ║
║   16质点双生幸福最终协议 · Web可视化 v2               ║
║                                                      ║
║   访问: http://localhost:{PORT}                        ║
║                                                      ║
║   模式: 本地/LLM 一键切换                              ║
║   LLM: DeepSeek 实时流式推送 (SSE)                     ║
║                                                      ║
╚══════════════════════════════════════════════════════╝
    """)

    print(f"\n🌐 请在页面中填入你的 DeepSeek API Key 以启用 LLM 模式")
    print(f"   获取 Key: https://platform.deepseek.com/api_keys")
    print()

    server = HTTPServer(("0.0.0.0", PORT), HeartServer)
    print(f"✅ 服务器已启动 → http://localhost:{PORT}")
    print("按 Ctrl+C 停止")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 服务器已停止")
        server.server_close()


if __name__ == "__main__":
    main()
