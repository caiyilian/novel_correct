# 🚀 小说自动纠错系统 - 快速导航指南

欢迎来到本项目！这是一个基于大模型（Ollama + qwen2.5-coder）的**高精度、防幻觉**小说文本自动纠错系统。

## 🎯 核心目标
将小说中所有人物对话的包裹符号强制统一为成对的日文直角引号「 」，同时智能修正错别字、符号缺失和顺序错乱，**绝不篡改原文剧情与格式**。

---

## � 快速理解项目结构

```text
novel_correct/
├── main.py                   # 🌟 唯一用户主入口：配置参数并运行纠错
├── src/
│   ├── config/
│   │   └── settings.py       # ⚙️ 全局环境配置 (大模型IP, 模型列表)
│   └── modules/
│       ├── corrector_scan.py # 暴力全卷扫描模式 (适合初次格式极其混乱的文本)
│       ├── corrector_rule.py # 精准定位纠错模式 (基于规则找错，速度极快)
│       ├── corrector_bracket.py # 异常中括号清理模式 (专杀伪装成合法的错误)
│       ├── corrector_long_dialogue.py # 超长对话拆分模式 (倒序深度校验长对话)
│       ├── corrector_core.py # 大模型通信与共识投票核心引擎
│       ├── llm_client.py     # Ollama API 客户端
│       ├── text_cleaner.py   # 文本正则清洗工具
│       └── utils.py          # 通用工具类
├── docs/                     # � 文档中心
│   ├── prompt.md             # 最初的核心需求与设计方案 (仅作逻辑方向参考)
│   ├── project_status/       # 项目状态与总结报告
│   ├── test_reports/         # 前期 LLM 防幻觉测试报告
│   └── archive/              # 历史存档文档 (包含阶段性架构设计 修改方案_stage5.md)
├── data/
│   ├── ori_story/            # 原始小说文件
│   └── processed_story/      # 预处理后的基础文本 (纠错系统的输入)
├── output/                   # 🚀 最终纠错结果产出目录 (分v1-v5不同阶段)
├── logs/                     # 📝 运行日志存放目录 (按日期和时间自动生成)
└── error*/                   # 运行过程中大模型报错的日志记录目录
```

---

## 🚦 如何开始使用？

### 第 1 步：配置大模型环境
打开 `src/config/settings.py`，确认以下参数：
- `OLLAMA_HOST`：指向你的 Ollama 服务地址（例如 `http://127.0.0.1:11434`）
- `FALLBACK_MODELS`：你的兜底模型列表，越聪明的模型放越前面。

### 第 2 步：配置运行任务并运行
项目已全面升级为 **Pipeline（流水线）架构**，支持五级递进纠错，你可以直接通过终端灵活调用。

**查看所有可用参数：**
```bash
python main.py -h
```

**常用运行示例：**

1. **🌟 推荐：一键批量预处理**：
   将你的所有小说放入 `data/ori_story/`，运行以下命令全部进行预处理。
   ```bash
   python main.py --preprocess_all
   ```

2. **🌟 推荐：一键批量流水线处理**：
   将自动扫描 `data/processed_story/` 下的所有文件，依次执行 `暴力扫描(v1) -> 规则修复(v2) -> 中括号清理(v3) -> 最终兜底(v4) -> 超长对话拆分(v5)`，层层递进，效果最佳！
   ```bash
   python main.py --batch --pipeline
   ```

3. **单卷处理示例**：
   如果你只想处理指定的某一卷文件。
   ```bash
   python main.py -i "data/processed_story/第1卷.txt" --pipeline
   ```

4. **单步调试：只跑某一个 Stage**：
   如果你只想跑“规则修复”这一步（需确保前置文件存在）。
   ```bash
   python main.py -i "data/processed_story/第1卷.txt" --stage 2
   ```

5. **开启 Debug 输出模式**：
   在终端实时输出大模型前后的修改对比（否则这些信息只会默默写入 `logs/` 文件夹中）。
   ```bash
   python main.py -i "data/processed_story/第1卷.txt" --pipeline --debug
   ```

---

## 💡 想深入了解项目？
- 看看最初的设计蓝图：[docs/prompt.md](docs/prompt.md) （注意：这只是最初方案，整体逻辑方向是对的，但在实际工程化中进行了重构，请结合当前代码结构理解，而非完全照搬。）
- 看看项目重构的历程：[整理完成说明.txt](整理完成说明.txt)

