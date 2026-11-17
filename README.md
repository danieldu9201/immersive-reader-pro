# immersive-reader-pro
An immersive, AI-powered multilingual reading tool featuring Gemini API, Elo-based cognitive leveling, and native A-B looping audio.
### 💡 开发者寄语 | Developer's Note

**致各位浏览本项目的学习者：**

在代码编写层面，我仅是一名初学者。开发这个工具的初衷，是想分享我在语言学习中遇到的痛点，并借助 AI 的力量将解决方案落地。我希望通过这个项目，传递一种“为学习者定制”的产品理念。这个工具主要聚焦于解决以下两个核心需求：

1. **为“回声法（Echo Method）”定制的语音库**：过去我发现，市面上的翻译软件普遍缺乏灵活的语音回放与下载功能。因此，我在工具中加入了音频变速、A-B 区间复读和独立下载功能。现在，我们可以根据跟读的需求，自由控制输入句子的长度，定制属于自己的循环“回声”。
    
2. **打破单一标准的“分层英英释义”**：传统词典的英英释义往往采用一刀切的单一标准，却忽略了学习者认知能力的差异。为了更好地辅助大脑理解，我在工具中引入了分层翻译机制。它能根据学习者的不同水平，动态提供相匹配的英文解释，循序渐进地培养母语直觉。
    

**To everyone reading this introduction:**

As a programmer, I am still very much a beginner. The motivation behind this project is to share the pain points I've personally encountered in my language learning journey, and to use the power of AI to turn those solutions into a tangible tool. More than just writing code, I want to share a product philosophy tailored specifically for language learners. This tool focuses on solving two core challenges:

1. **Custom Audio Toolkit for the "Echo Method"**: In the past, I noticed that most translation software lacked flexible audio playback and download features. After discovering the "Echo Method" for language acquisition, I integrated speed control, A-B looping, and audio extraction into this tool. Now, learners have full control over the length and pace of the sentences they want to shadow, creating their own personalized audio loops.
    
2. **Adaptive English-to-English Definitions**: Traditional dictionaries typically offer a one-size-fits-all English explanation, completely ignoring the varying proficiency levels among learners. To bridge this gap, I introduced a multi-tiered definition mechanism. It provides dynamically customized English explanations matched to the user's specific level, significantly easing comprehension and helping to build native-like intuition step by step.
# 🎧 专属多语种精读系统 | Immersive Multilingual Reading System

基于 Gemini API 和 Edge-TTS 打造的沉浸式多语种（英/日/意）精读与查词辅助工具。系统首创了「全英母语印象进化模式 (i+1)」，通过具象画面、精准语境和难度自适应，帮助学习者建立真正的母语直觉；同时配备强大的 A-B 区间洗脑复读机，完美兼容本地代理网络。

An immersive multilingual (EN/JA/IT) intensive reading and dictionary tool powered by Gemini API and Microsoft Edge-TTS. Pioneering the "Native Impression Evolution Mode (i+1)", it helps learners build genuine native intuition through mental imagery, precise context, and adaptive difficulty. It also features a powerful A-B looping audio player with ultimate robustness against local proxy network issues.

---

## ✨ 核心功能 | Core Features

*   **🌊 双轨大模型智能解析 | Dual-Track AI Engine**
    *   **日常极速划词 (Daily Quick Search)**：强制置顶 `gemini-3.5-flash-lite` / `3.1` 等高配额模型（每日 500 次），保证日常高频查词无忧。 / Hardcoded priority for high-quota models (500 requests/day) for high-frequency daily use.
    *   **满血深度精析 (Deep Analysis)**：遇长难句一键调用 `gemini-3.6-flash` 等高阶模型（每日 20 次），实施“降维打击”。 / One-click access to advanced models (20 requests/day) for complex sentences and nuanced breakdowns.

*   **🧠 i+1 自适应难度评级 | Elo-Based Cognitive Leveling**
    *   内置 100-600 分的 Elo 动态水平系统。根据用户的英语水平，动态生成“具象画面 (Mental Picture)”、“自适应释义 (Adaptive Definition)”和“语感辨析 (Nuance)”，彻底摆脱死记硬背。
    *   Features a dynamic Elo rating system (100-600). It tailors outputs into "Mental Pictures", "Adaptive Definitions", and "Nuance" based on the user's proficiency, eliminating the need for rote memorization.

*   **🎧 原生 A-B 区间复读机 | Native A-B Looping Audio Player**
    *   无缝接入 Edge-TTS，划取任意文本即刻生成标准母语发音。内置可视化进度条，支持精确到 0.01 秒的 A-B 区间截取与无缝洗脑循环，支持快捷键操控。
    *   Seamlessly integrated with Edge-TTS for instant native pronunciation. Includes a visual progress bar, 0.01s-precision A-B looping, and keyboard shortcuts (Space to toggle, arrows to seek).

*   **📚 传统双语模式与多语种支持 | Multilingual Bilingual Dictionary Mode**
    *   支持英语、日语（集成 Jisho 假名提取）、意大利语。自动提取 TEM/BEC 核心词、高频搭配、英英释义及双语例句。
    *   Supports English, Japanese (with Jisho Kana extraction), and Italian. Automatically extracts core vocabulary, high-frequency collocations, EN-EN definitions, and bilingual examples.

*   **⚡ 极致网络穿透与防卡死 | Ultimate Network Robustness & Anti-Freeze**
    *   **代理免疫启动 (Proxy-Immune Startup)**：底层强行修补 `httpx`（同步与异步），完美解决 Gradio 在 Windows 代理环境下（如 `socks4`）的启动闪退问题。 / Forces `httpx` to ignore system proxies during startup, completely resolving Gradio crashes under Windows VPN environments.
    *   **API 智能回退与音频熔断 (API Fallback & Audio Circuit Breaker)**：API 握手超时限制 4 秒并自动顺延备胎模型；TTS 音频生成引入 8 秒强制熔断机制，网络阻塞时瞬间降级返回纯文本，告别无限期卡死。 / 4-second API connection timeout with auto-fallback to backup models; 8-second circuit breaker for TTS generation to prevent UI freezing during network congestion.

---

## 🛠️ 运行环境 | Requirements

*   **Python Version**: Python 3.8+
*   **Dependencies**:
    ```bash
    pip install gradio edge-tts requests httpx
    ```

---

## 🚀 运行与使用指南 | Usage Guide

1.  **克隆或下载本项目 / Clone or download this repository.**
2.  **在终端中运行启动脚本 / Run the script in your terminal:**
    ```bash
    python audio_tool_v5.2.4.py
    ```
3.  **打开浏览器 / Open your browser:**
    程序启动后，访问终端中提示的本地地址（通常为 `http://127.0.0.1:7860`）。 / Navigate to the local URL provided in the terminal (usually `http://127.0.0.1:7860`).
4.  **首次使用配置 / Initial Setup:**
    *   展开顶部的 **「⚙️ 全英大脑设置 & 双轨模型选择」** 面板。 / Expand the settings panel at the top.
    *   填入你的 **Google Gemini API Key**。 / Enter your Gemini API Key.
    *   点击 **「💾 保存设置」**。API Key 和个人配置会自动保存在本地 `user_english_profile.json` 文件中。 / Click Save. Your key and preferences will be securely saved locally in `user_english_profile.json`.

---

## ⚠️ 注意事项与隐私说明 | Notes & Privacy

*   **API Key 隐私保护 (Privacy & Security)**：本程序不会收集任何隐私。你的 API Key 完全保存在本地运行目录的 `user_english_profile.json` 中。**请确保将此 JSON 文件加入 `.gitignore`**，切勿上传到公开代码库。 / This application respects your privacy. Your API Key is stored entirely locally. **Ensure `user_english_profile.json` is added to your `.gitignore`** to prevent accidental leaks.
*   **模型可用性 (Model Availability)**：程序代码硬编码置顶了部分拥有高额度配额的模型（如 `gemini-3.5-flash-lite`）。由于 Google API 政策动态变化，若某模型不可用，程序会自动触发 Fallback 机制顺延至下一梯队。 / Hardcoded primary models may change availability based on Google's API policies. The system will automatically fallback to alternative models if the primary one fails.
*   **关于代理环境 (Proxy Routing)**：程序底层启动 UI（Gradio）时会自动忽略系统代理以防止报错，而后台发送到 Google 的 API 请求会**正常走你的全局/系统代理**。确保你的 VPN 节点可以稳定连接 API 即可。 / The Gradio UI ignores system proxies to prevent startup crashes, while the backend API requests will naturally route through your active system VPN. Ensure your proxy node can stably connect to Google APIs.
