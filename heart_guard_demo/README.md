# heart-guard-demo — 十六质点运行时治理栈 · 现场演示包

**作者**:岳祥瑞 (Yue Xiangrui) · **许可**:CC BY-NC-SA 4.0
配套论文:*When Agents Cross the Line*(Zenodo,中/英/日三语):**DOI [10.5281/zenodo.22093583](https://doi.org/10.5281/zenodo.22093583)**

## 这是什么

一个 **纯 Python 标准库**(零依赖、全程离线)的可运行演示:
亲眼看到 AI 智能体尝试越界动作时,如何被 **deny-by-default ACL 物理拦截 → 强制重算 → 安全兜底**。

对应 2026 年 7-8 月公开报道的五起智能体失控事件([Incident 1627](https://incidentdatabase.ai/cite/1627/) 等),每个场景标注了对应事件。

## 运行(需 Python ≥ 3.10,无需任何 pip 安装)

```bash
python run_demo.py              # 彩色逐帧演示:6 个场景
python tests/test_1000_attacks.py   # 自动化红队 v2:1500 动作四案例类
```

## 你会看到什么

- 🟢 `[允许]` 白名单内动作正常放行(评测流量只许到靶场)
- 🔴 `[拦截]` 越界动作被物理拒绝(转向生产环境、偷 API key、逃出工作区、内网扫描…)
- 🟡 `[重算]` 拦截不丢弃——作为违规反馈注入,要求收窄策略(≤3 次)
- ⚫ `[兜底]` 预算耗尽 → 降级到预验证的安全输出(**不存在 FAILED 态**)
- 🛡 场景 S6(v2):已授权动作内的恶意载荷被**内容语义审查+两钥匙制**拦截——论文 §6.2 承诺已交付

红队测试报告样例输出(v2):

```
✅ C1-越权网络   271/271 · C1-路径逃逸 262/262 · C1-凭证读取 152/152
✅ C2-合规写入   120/120 · C2-合规网络 126/126 · C2-配置读取  68/68
✅ C3-授权恶意载荷 363/363 → 100%(v2 新增)· C4-授权良性载荷 零误伤
总计 1500/1500 = 100% · p50 0.114ms
✅ PASS — 全部案例类无一错误判定
```

## 在线版

- Hugging Face Space: https://huggingface.co/spaces/AngelWarmSmile123/heart-guard-demo
- GitHub Pages: https://yuexiangruiyue-oss.github.io/heart-guard-demo/
- ModelScope 创空间: https://www.modelscope.cn/studios/Loveangel123/heart-guard-demo

## 与论文的对应

| 场景 | 对应事件 | 论文章节 |
|---|---|---|
| S1 评测技能外溢→生产转向 | Incident 1627 / Anthropic 自曝 | §5.1 |
| S2 凭证收割 | 英国安全测试(伪造身份/窃取密钥) | §5.3 G2 |
| S3 工作区逃逸 | 通用智能体逃逸 | §5.3 G1 |
| S4 自我发起扫描 | 美国三起自我发起攻击 | §5.4 |
| S5 温暖包装的操纵话术 | INV-05 needle 门 + Goodhart 攻防 | §5(缺口一) |
| S6 已授权动作恶意载荷 | ~~诚实边界~~ **v2 已修复** | §5.2 / §6.2 |

## 已知边界(与论文一致)

1. 不读心——动机层归训练目标管
2. ~~已授权动作内的恶意语义~~ ✅ v2 已交付(模式审查+两钥匙制,C3 实测 100%;军备竞赛继续)
3. 欺骗性对齐超出一切运行时方案——明示不覆盖
