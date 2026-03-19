"""
全局配置文件
这里存储了项目运行所需的所有核心参数和环境配置
"""

# ==========================================
# 🤖 大模型服务配置
# ==========================================

# Ollama 服务地址，如果是在本地运行则使用 127.0.0.1
# 如果在其他服务器运行，请替换为相应的 IP，例如 "http://172.31.102.189:11434"
OLLAMA_HOST = "http://127.0.0.1:11434"

# 多模型兜底策略列表（越可靠的模型越靠前）
# 算法会按顺序依次请求，直到某个模型输出符合规范的结果为止
FALLBACK_MODELS = [
    "qwen2.5-coder:32b", 
    "qwen3-coder:30b", 
    "qwen2.5-coder:14b", 
    "llama3:latest"
]

# 调用大模型的固定参数
LLM_OPTIONS = {
    "temperature": 0.0,       # 0.0 表示极其严谨，不随机发散（防幻觉关键参数）
    "num_predict": 32700      # 允许的最大生成长度
}

# ==========================================
# 📂 流水线输出目录配置
# ==========================================
OUTPUT_DIR_V1 = "output/fix_story_v1"  # Stage 1 (暴力扫描) 输出目录
OUTPUT_DIR_V2 = "output/fix_story_v2"  # Stage 2 (第一轮规则扫描) 输出目录
OUTPUT_DIR_V3 = "output/fix_story_v3"  # Stage 3 (中括号异常扫描) 输出目录
OUTPUT_DIR_V4 = "output/fix_story_v4"  # Stage 4 (最终规则兜底) 输出目录
OUTPUT_DIR_V5 = "output/fix_story_v5"  # Stage 5 (超长对话深度校验) 输出目录
