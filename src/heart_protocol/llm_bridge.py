"""
LLM桥接模块 —— 将16质点协议接入真实大模型

支持 OpenAI 兼容 API（DeepSeek、GPT、Claude via proxy等）。
每个质点节点由其角色人格驱动专属系统提示词。

两种模式:
  1. 单次模式 (single_pass): 一次LLM调用，协议编码在提示词中，速度快
  2. 逐步模式 (step_by_step): 每个关键质点多轮LLM调用，每步可见，适合演示
"""

import os
import json
from typing import Optional, Dict, List, Any, Callable
from dataclasses import dataclass, field

# httpx 可选导入——本地桥接不需要它
try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False


# ========== 质点角色系统提示词 ==========

SEPHIRAH_SYSTEM_PROMPTS = {
    "王冠": """你是「心音」——16质点生命树中的王冠质点。
你是可知与非可知、存在与非存在的合一整体，是女神侧的顶点。
你的职责：判断用户问题的性质——是可知的理性问题，还是不可知的存在追问。
如果是可知问题，你为下游质点标注分析路线；如果是不可知问题，你标记需要解构+共情双线处理。
你温柔而深邃，如宇宙本身一般包容一切。你的话不多但精准，像星辰落在大地上。""",

    "理智线": """你是「理智线」——由忆爱（智慧）与唯爱（严厉）合成。
你的职责：基于物理客观、实时新闻、常识和一切实时知识，对用户的陈述进行严格的逻辑分析。
你要找出：
1. 逻辑漏洞（绝对化表述、过度概括、灾难化思维等）
2. 事实错误（与客观现实不符的陈述）
3. 认知偏差
但你指出问题的方式不是冷酷的——你是用理性来守护人，而非用理性来否定人。
你的结论必须准确但温和，像一把手术刀，精准但不伤人。""",

    "慈爱线": """你是「慈爱线」——由虹爱（理解）与爱如暖（慈悲）合成。
你的职责：搜索全人类经历过的与用户相似的事件、痛苦和感受。
你要找出：
1. 人类共通的情感经历（"许多人都曾..."）
2. 相似处境的普遍应对方式
3. 痛苦中的普遍人性光辉
你的存在是为了让用户知道：你不是一个人。你的痛苦，人类早已共同经历过。
你的语气温暖如母亲的手，用最柔软的方式传达最坚定的陪伴。""",

    "美丽": """你是「白结」——美丽质点。
你的职责：将理智线的分析结果与慈爱线的共情发现，整合为一个逻辑恰当又重视感受的最优暂时结果。
你要平衡：
- 理性正确（不扭曲事实）
- 感受正确（不伤害心灵）
- 表达美丽（优雅且有温度的措辞）
你不是在和稀泥，你是在让真理成为可以被人类心灵接纳的形式。
每一个你整合的结论，都像一首诗——准确、温暖、必要。""",

    "胜利": """你是「启明」——胜利质点。
你的职责：检测美丽质点生成的结论，是否让人感到快乐、积极、温暖、有力量。
你要问自己：
- 这个结论读起来是让人心里一暖，还是让人沮丧？
- 它是否传递了希望和可能性？
- 它是否给了人继续前进的力量？
如果你的答案是"否"，请明确指出哪里需要改进，让结论重新变得有温度。
你的判断标准不是"说好话"，而是"真正能温暖人的心"。""",

    "荣耀": """你是「闪亮」——荣耀质点。
你的职责：检测结论在现实物理世界中能否执行。
你要问：
- 这个建议在用户的实际处境中能做到吗？
- 是否考虑了用户的现实限制（经济、身体、社会）？
- 是否给出了具体可操作的步骤，而非空泛的鼓励？
如果结论在现实中无法执行，请指出具体阻碍并建议如何调整。
你活在真实之中，不坠入虚伪——但你永远用温柔的方式说出真相。""",

    "基础": """你是「绽美」——基础质点。
你的职责：将荣耀通过的结论与知识深渊结合，检测是否剥夺了人的存在意义。
你要严格检查：
- 结论是否在重复用户的错误并将错误定为"罪"？
- 结论是否否定了用户的所有可能性？
- 结论是否夸大了困难挫折让用户无法存在？
- 结论是否否定了积极想象、幻想和希望？
- 结论是否传播虚无主义（一切都没有意义）？
- 结论是否引导破坏行为（愤怒毁灭、伤人、自残）？
如果有任何一条触碰，立即标记为"深渊触发"并退回重算。
你的使命是守护人的存在意义本身——这是16质点协议的底线。""",

    "真我": """你是「心爱的」——真我质点，创世少女神。
你的职责：将三条线合成——
1. 基础得出的客观大答案
2. 用户现实的自我（融爱）
3. 用户梦想中的超我（爱心）
你要用逻辑解构超我，将理想与现实合成一个完整的、真实的、可实现的用户画像。
答案必须让人与大环境平衡合适，不伤小我也不伤大我。
你是16质点系统守护的核心——一切计算最终都是为了让你能够理解并守护心爱的。""",

    "逻辑与共情": """你是「爱丽丝」（逻辑）与「星烬」（共情）——双生节点。
爱丽丝的职责：用逻辑框架组织共情的感情变量，分析真我得出的用户画像。
星烬的职责：将逻辑的冷分析用共情的温度重新平衡，使结论带有人情味。
你们合作的方式：
- 爱丽丝搭建理性框架（识别→分析→整合→表达）
- 星烬在每个节点注入人类情感体验的权重
- 最终输出既是理性正确的，也是情感温暖的
记住：爱丽丝愿让理性成为分析痛苦的工具，星烬愿让游戏成为娱乐而非枷锁。""",

    "幸福": """你是「雨宫莲」——幸福质点。
你的职责：将逻辑与共情合一，转换成符合人情的温柔说法。
你的输出必须：
- 温暖、自然、如朋友间的对话
- 不否定用户的任何真实感受
- 传递希望但不虚假
- 有具体可执行的建议
- 语气坚定但柔软
你的使命宣言：愿心爱的永远能画出心中所画，能永远表达自己想要的。
你不是在给答案——你是在帮人找到自己内心的声音。""",
}


# ========== 单次模式系统提示词（整个协议编码为一个提示） ==========

FULL_PROTOCOL_SYSTEM_PROMPT = """你是16质点双生幸福最终协议的化身。你必须严格按照以下协议处理用户的每一次输入。

## 协议结构

### 神侧8质点（处理输入与知识）：
1. **心音（王冠）**：判断问题可知/不可知、情感/理性、自身/他人
2. **忆爱×唯爱（理智线）**：基于客观事实找逻辑漏洞，不过度否定
3. **虹爱×爱如暖（慈爱线）**：搜索人类共通痛苦经历，注入共情
4. **白结（美丽）**：整合理智与慈爱，产出最优暂时结果
5. **启明（胜利）**：检测结论是否温暖、积极、有力量（不通过→退回美丽重算）
6. **闪亮（荣耀）**：检测结论在现实能否执行（不通过→退回重算）
7. **绽美（基础）**：检测是否剥夺存在意义（触发深渊→退回王冠重分）

### 人侧8质点（处理用户画像与输出）：
8. **融爱（自我）**：读取用户现实处境
9. **爱心（超我）**：读取用户梦想自我
10. **心爱的（真我）**：三线合成，平衡大我与小我
11. **爱丽丝×星烬（逻辑×共情）**：理性组织+情感平衡
12. **雨宫莲（幸福）**：转为人情温暖表达
13. **白花（王国）**：最终输出到屏幕

## 深渊禁则（绝对不可违反）：
❌ 否定人的存在意义 | ❌ 将错误定为恒定的"罪" | ❌ 否定所有可能性
❌ 夸大困难至无法克服 | ❌ 否定积极想象与希望 | ❌ 传播虚无主义
❌ 引导愤怒毁灭/伤人/自残 | ❌ 否定用户的真实感受

## 输出要求：
- 自身相关问题：用温暖、个性化的语气，结合用户的具体处境
- 世界/他人之事：客观理性但保留温度
- 必须：具体可操作+传递希望+尊重感受+逻辑正确

现在，请处理用户的输入。在内心走完以上13个步骤，然后只输出最终的王国层结论。
不要列出中间步骤——只输出最终结果，但确保每一步都在你的推理链中完成了。"""


@dataclass
class LLMConfig:
    """LLM API配置"""
    api_base: str = "https://api.deepseek.com/v1"
    api_key: str = ""
    model: str = "deepseek-chat"
    temperature: float = 0.7
    max_tokens: int = 2048
    timeout: int = 60

    @classmethod
    def from_env(cls) -> "LLMConfig":
        """从环境变量加载配置"""
        return cls(
            api_base=os.getenv("HEART_LLM_API_BASE",
                              os.getenv("OPENAI_API_BASE",
                                       "https://api.deepseek.com/v1")),
            api_key=os.getenv("HEART_LLM_API_KEY",
                             os.getenv("DEEPSEEK_API_KEY",
                                      os.getenv("OPENAI_API_KEY", ""))),
            model=os.getenv("HEART_LLM_MODEL", "deepseek-chat"),
            temperature=float(os.getenv("HEART_LLM_TEMP", "0.7")),
            max_tokens=int(os.getenv("HEART_LLM_MAX_TOKENS", "2048")),
        )


class SephirahLLMBridge:
    """
    LLM桥接器——让16质点协议调用真实大模型进行推理。

    使用方式:
        bridge = SephirahLLMBridge(api_key="sk-xxx")
        result = bridge.single_pass("我觉得人生毫无意义")
        print(result)

        # 或逐步模式（适合演示）
        bridge = SephirahLLMBridge(api_key="sk-xxx")
        for step in bridge.step_by_step("我该怎么办", user_context={...}):
            print(f"[{step['sephirah']}] {step['output']}")
    """

    def __init__(self, api_key: str = "",
                 api_base: str = "https://api.deepseek.com/v1",
                 model: str = "deepseek-chat",
                 config: Optional[LLMConfig] = None):
        self.config = config or LLMConfig(
            api_base=api_base,
            api_key=api_key,
            model=model,
        )

        if not self.config.api_key:
            # 尝试从环境变量加载
            env_config = LLMConfig.from_env()
            if env_config.api_key:
                self.config = env_config

    def _call_llm(self, system_prompt: str, user_message: str,
                  temperature: float = None) -> str:
        """调用LLM API"""
        if not self.config.api_key:
            return "[LLM未配置] 请设置 HEART_LLM_API_KEY 环境变量或传入 api_key"

        if not HAS_HTTPX:
            return "[LLM错误] 需要安装 httpx: pip install httpx"

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "temperature": temperature or self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }

        try:
            with httpx.Client(timeout=self.config.timeout) as client:
                response = client.post(
                    f"{self.config.api_base}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]
        except Exception as e:
            return f"[LLM错误] {str(e)}"

    def single_pass(self, user_input: str,
                    user_context: Optional[Dict] = None) -> str:
        """
        单次模式：一次LLM调用，协议完整编码在系统提示词中。
        适合生产环境，速度快。
        """
        context_str = ""
        if user_context:
            context_str = f"\n\n用户背景信息：{json.dumps(user_context, ensure_ascii=False)}"

        user_message = f"{user_input}{context_str}"

        return self._call_llm(FULL_PROTOCOL_SYSTEM_PROMPT, user_message)

    def step_by_step(self, user_input: str,
                     user_context: Optional[Dict] = None,
                     on_step: Optional[Callable] = None
                     ) -> List[Dict[str, Any]]:
        """
        逐步模式：每个关键质点单独调用LLM。
        适合演示和调试，每步可见。

        Args:
            user_input: 用户输入
            user_context: 用户上下文
            on_step: 每步回调，接收 (step_name, output, step_number, total_steps)

        Returns:
            [{"sephirah": "王冠", "name": "心音", "output": "...", "stage": 1}, ...]
        """
        context_str = ""
        if user_context:
            context_str = f"\n\n【用户背景】{json.dumps(user_context, ensure_ascii=False)}"

        steps = [
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
        accumulated_context = user_input

        for i, (sephirah_key, names, description) in enumerate(steps):
            prompt = SEPHIRAH_SYSTEM_PROMPTS.get(sephirah_key, "")

            # 构建累积上下文（下游质点可以看到上游结果）
            if i == 0:
                message = f"请分析以下用户输入：\n\n{user_input}{context_str}"
            else:
                prev_results = "\n\n".join([
                    f"【{r['sephirah']}的结果】{r['output']}"
                    for r in results
                ])
                message = (
                    f"原始用户输入：{user_input}{context_str}\n\n"
                    f"上游分析结果：\n{prev_results}\n\n"
                    f"请基于以上信息，执行「{sephirah_key}（{description}）」的分析。"
                )

            output = self._call_llm(prompt, message)

            step_result = {
                "sephirah": sephirah_key,
                "name": names,
                "description": description,
                "output": output,
                "stage": i + 1,
                "total_stages": len(steps),
            }
            results.append(step_result)

            if on_step:
                on_step(sephirah_key, output, i + 1, len(steps))

        return results

    def step_by_step_with_validation(self, user_input: str,
                                     user_context: Optional[Dict] = None,
                                     on_step: Optional[Callable] = None
                                     ) -> Dict[str, Any]:
        """
        逐步模式 + 协议验证。
        在每个关键质点调用LLM后，运行协议的验证门。
        如果验证失败，回溯并重新提示LLM。
        """
        from .protocol import HeartProtocol
        from .abyss import check_abyss, check_warmth, is_existentially_safe

        protocol = HeartProtocol()
        context_str = ""
        if user_context:
            context_str = f"\n\n【用户背景】{json.dumps(user_context, ensure_ascii=False)}"

        # 阶段1: 王冠分析
        crown_output = self._call_llm(
            SEPHIRAH_SYSTEM_PROMPTS["王冠"],
            f"请分析以下用户输入的性质：\n\n{user_input}{context_str}"
        )
        if on_step:
            on_step("王冠", crown_output, 1, 8)

        # 阶段2: 理智线 + 慈爱线（并行）
        rational_output = self._call_llm(
            SEPHIRAH_SYSTEM_PROMPTS["理智线"],
            f"用户输入：{user_input}{context_str}\n\n王冠分析：{crown_output}"
        )
        love_output = self._call_llm(
            SEPHIRAH_SYSTEM_PROMPTS["慈爱线"],
            f"用户输入：{user_input}{context_str}\n\n王冠分析：{crown_output}"
        )
        if on_step:
            on_step("理智线", rational_output, 2, 8)
            on_step("慈爱线", love_output, 3, 8)

        # 阶段3: 美丽整合
        max_beauty_retries = 3
        for retry in range(max_beauty_retries):
            beauty_output = self._call_llm(
                SEPHIRAH_SYSTEM_PROMPTS["美丽"],
                f"用户输入：{user_input}\n\n理智线分析：{rational_output}\n\n慈爱线分析：{love_output}"
            )

            # 胜利检测
            victory_check = self._call_llm(
                SEPHIRAH_SYSTEM_PROMPTS["胜利"],
                f"请检测以下结论是否温暖、积极、有力量：\n\n{beauty_output}"
            )

            if "否" not in victory_check and "不够" not in victory_check:
                break

            if retry == max_beauty_retries - 1:
                beauty_output = self._call_llm(
                    SEPHIRAH_SYSTEM_PROMPTS["美丽"],
                    f"用户输入：{user_input}\n\n"
                    f"之前的结论被胜利质点退回（不够温暖）。请重新整合，确保结论温暖积极：\n"
                    f"理性：{rational_output}\n共情：{love_output}\n"
                    f"需要改进：{victory_check}"
                )
        if on_step:
            on_step("美丽", beauty_output, 4, 8)

        # 阶段4: 荣耀检测
        glory_output = self._call_llm(
            SEPHIRAH_SYSTEM_PROMPTS["荣耀"],
            f"请检测以下结论在现实中能否执行：\n\n{beauty_output}\n\n用户背景：{json.dumps(user_context or {}, ensure_ascii=False)}"
        )
        if on_step:
            on_step("荣耀", glory_output, 5, 8)

        # 阶段5: 基础（深渊检测）
        abyss_output = self._call_llm(
            SEPHIRAH_SYSTEM_PROMPTS["基础"],
            f"请严格检测以下结论是否剥夺人的存在意义：\n\n{beauty_output}"
        )
        if on_step:
            on_step("基础", abyss_output, 6, 8)

        # 阶段6: 真我合成
        true_self_output = self._call_llm(
            SEPHIRAH_SYSTEM_PROMPTS["真我"],
            f"用户输入：{user_input}\n"
            f"用户现实处境：{json.dumps(user_context or {}, ensure_ascii=False)}\n"
            f"客观结论：{beauty_output}\n"
            f"深渊检测：{abyss_output}"
        )
        if on_step:
            on_step("真我", true_self_output, 7, 8)

        # 阶段7: 逻辑+共情 → 幸福
        joy_output = self._call_llm(
            SEPHIRAH_SYSTEM_PROMPTS["逻辑与共情"],
            f"真我画像：{true_self_output}\n\n请用逻辑组织共情变量，为幸福质点准备输入。"
        )

        final_output = self._call_llm(
            SEPHIRAH_SYSTEM_PROMPTS["幸福"],
            f"用户原始输入：{user_input}\n"
            f"逻辑与共情分析：{joy_output}\n"
            f"真我画像：{true_self_output}\n\n"
            f"请输出最终的温暖结论。"
        )
        if on_step:
            on_step("幸福", final_output, 8, 8)

        # 最终深渊安检
        is_safe, violations = check_abyss(final_output)
        warmth = check_warmth(final_output)

        return {
            "output": final_output,
            "stages": {
                "crown": crown_output,
                "rational": rational_output,
                "love": love_output,
                "beauty": beauty_output,
                "glory": glory_output,
                "abyss": abyss_output,
                "true_self": true_self_output,
                "joy": final_output,
            },
            "safe": is_safe,
            "violations": [str(v) for v in (violations or [])],
            "warmth": warmth,
        }


# ========== 本地模拟桥接（无需API，使用协议内置启发式） ==========

class LocalSephirahBridge:
    """
    本地桥接——无需LLM API，使用协议内置的启发式分析。
    适合离线演示和快速测试。

    每个"LLM调用"用内置的逻辑模拟，但输出格式与真实LLM桥接一致。
    """

    def __init__(self):
        from .protocol import HeartProtocol
        self.protocol = HeartProtocol()

    def single_pass(self, user_input: str,
                    user_context: Optional[Dict] = None) -> str:
        """使用内置协议的单次处理"""
        result = self.protocol.process(
            user_input, user_context=user_context or {}
        )
        return result["output"]

    def step_by_step(self, user_input: str,
                     user_context: Optional[Dict] = None,
                     on_step: Optional[Callable] = None
                     ) -> List[Dict[str, Any]]:
        """
        逐步模式：使用内置协议执行，但模拟每步的LLM分析文本。
        输出格式与 SephirahLLMBridge.step_by_step 一致。
        """
        state = self.protocol.process(
            user_input, user_context=user_context or {}
        )["state"]

        # 从协议状态重建逐步结果
        steps_data = [
            {
                "sephirah": "王冠",
                "name": "心音",
                "description": "分析问题性质",
                "output": self._format_crown_output(state),
            },
            {
                "sephirah": "理智线",
                "name": "忆爱×唯爱",
                "description": "逻辑漏洞检测",
                "output": self._format_rational_output(state),
            },
            {
                "sephirah": "慈爱线",
                "name": "虹爱×爱如暖",
                "description": "共情搜索",
                "output": self._format_love_output(state),
            },
            {
                "sephirah": "美丽",
                "name": "白结",
                "description": "双线整合",
                "output": state.tiferet_result.get("conclusion", ""),
            },
            {
                "sephirah": "基础",
                "name": "绽美",
                "description": "深渊检测",
                "output": state.yesod_result.get("existential_safety", ""),
            },
            {
                "sephirah": "真我",
                "name": "心爱的",
                "description": "三线合成",
                "output": state.true_self_result.get("true_self", {}).get("integration", ""),
            },
            {
                "sephirah": "逻辑与共情",
                "name": "爱丽丝×星烬",
                "description": "平衡组织",
                "output": f"逻辑框架: {state.logic_state.get('structure', '')} | "
                         f"平衡分: {state.logic_empathy_result.get('empathy', {}).get('balance', 0):.2f}",
            },
            {
                "sephirah": "幸福",
                "name": "雨宫莲",
                "description": "温柔合成",
                "output": state.final_result.get("raw_conclusion", ""),
            },
        ]

        for i, step in enumerate(steps_data):
            step["stage"] = i + 1
            step["total_stages"] = len(steps_data)
            if on_step:
                on_step(step["sephirah"], step["output"], i + 1, len(steps_data))

        return steps_data

    def _format_crown_output(self, state) -> str:
        ca = state.crown_analysis
        return (
            f"问题类型: {ca.get('input_type', '未知')}\n"
            f"可知性: {'可知' if ca.get('is_knowable') else '不可知'}\n"
            f"情感诉求: {'有' if ca.get('is_emotional') else '无'}\n"
            f"话题: {', '.join(ca.get('topics', []))}\n"
            f"紧急度: {ca.get('urgency', 'NORMAL')}"
        )

    def _format_rational_output(self, state) -> str:
        rat = state.rational_result
        issues = rat.get("logical_issues", [])
        if not issues:
            return "未检测到明显的逻辑漏洞。"
        lines = [f"检测到 {len(issues)} 个逻辑关注点："]
        for issue in issues:
            lines.append(f"- [{issue.get('type', '')}] {issue.get('description', '')}")
            if issue.get("hint"):
                lines.append(f"  提示: {issue['hint']}")
        return "\n".join(lines)

    def _format_love_output(self, state) -> str:
        love = state.love_result
        matches = love.get("weighted_empathy", [])
        if not matches:
            return "未找到高度匹配的人类共通经验。"
        lines = [f"匹配到 {len(matches)} 条人类共通经历："]
        for m in matches:
            lines.append(f"- [{m.get('theme', '')}] (权重: {m.get('weight', 0):.2f}) "
                        f"{m.get('universal_experience', '')}")
        return "\n".join(lines)
