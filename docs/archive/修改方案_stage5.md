我已经基于你选择的**“方案一：倒序处理”**，完善了最终的 Stage 5 修改方案。

请你最后确认一下这个架构设计，确认无误后，我就会开始进行代码编写。

---

### 🚀 Stage 5: 超长对话深度校验 (最终修改方案)

#### 1. ⚙️ 新增参数与配置
*   **`src/config/settings.py`**：新增 `OUTPUT_DIR_V5 = "output/fix_story_v5"`。
*   **`main.py` (命令行参数)**：
    *   新增 `--long_dialogue_top_k` 参数（默认 `10`）：每卷抽查最长的几个对话。
    *   新增 `--long_dialogue_min_agree` 参数（默认 `2`）：拆分长对话需要更严格的共识。
    *   `--stage` 范围扩大到 5，并在 `--pipeline` 中将 Stage 5 串联在最后。

#### 2. 🛠️ 工具库扩展 (`src/modules/utils.py`)
新增两个提取和排序对话的工具函数：
*   **`extract_all_dialogues(content: str) -> List[Dict]`**：
    遍历文本，提取所有被成对「 和 」包裹的内容，记录它们的 `start_index`、`end_index` 和 `length`。
*   **`get_top_k_longest_dialogues(dialogues: List[Dict], k: int) -> List[Dict]`**：
    按长度降序获取 Top K。

#### 3. 🧩 核心业务模块 (`src/modules/corrector_long_dialogue.py`)
新建此模块，包含以下核心逻辑：

*   **专属大模型 Prompt (`build_long_dialogue_prompt`)**：
    明确告知模型：*“这段文字虽然被包裹在「」中，但它非常长，我们怀疑其中缺失了中间的开闭符号，导致原本属于旁白或者其他人的对话被错误地合并进来了。请你判断是否应该拆分，并在合适的位置补全缺失的符号。”*

*   **🛡️ 倒序处理循环 (`correct_single_volume_long_dialogue`)**：
    1.  提取全卷所有对话。
    2.  获取最长的 Top K 个对话。
    3.  **【关键】** 将这 Top K 个对话按照它们在文中的绝对位置（`start_index`）**从大到小（从后往前）排序**。
    4.  从后往前依次遍历这 K 个对话，调用 `get_centered_story_clip` 提取上下文。
    5.  调用大模型决策是否修改。
    6.  使用 `apply_chunk_correction` 写入修改。**因为是从后往前修改的，所以即使后面的文本长度发生了变化，也绝对不会影响排在前面的对话的绝对索引。**

#### 4. 🔀 工作流串联 (`main.py`)
在 `--pipeline` 流程中：
*   接收 `Stage 4` 的输出文件（`output/fix_story_v4/第X卷.txt`）。
*   调用 `correct_single_volume_long_dialogue`。
*   将最终的究极完成版输出到 `output/fix_story_v5/第X卷.txt`。

---

这个基于倒序处理的方案既优雅又安全，能完美解决绝对索引偏移的问题。

如果这个方案符合你的心意，请告诉我“**同意执行**”，我马上开始修改代码！