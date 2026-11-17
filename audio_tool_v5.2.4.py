import os
import urllib.parse
import urllib.request
import httpx

# ==========================================
# 🛡️ 终极武力补丁：强制覆盖 Gradio 传来的代理指令
# 绝对禁止 httpx 读取 socks4，同时保留 requests (Gemini API) 的 VPN 穿透
# ==========================================
_orig_sync_init = httpx.Client.__init__
def _new_sync_init(self, *args, **kwargs):
    kwargs['trust_env'] = False
    _orig_sync_init(self, *args, **kwargs)
httpx.Client.__init__ = _new_sync_init

_orig_async_init = httpx.AsyncClient.__init__
def _new_async_init(self, *args, **kwargs):
    kwargs['trust_env'] = False
    _orig_async_init(self, *args, **kwargs)
httpx.AsyncClient.__init__ = _new_async_init

import gradio as gr
import edge_tts
import asyncio
import tempfile
import base64
import requests
import re
import concurrent.futures
import uuid
import time
import glob
import json

# --- 路径与全局配置 ---
TEMP_DIR = os.path.abspath(tempfile.gettempdir())
BASE_DIR = os.path.dirname(os.path.abspath(__file__)) if "__file__" in locals() else os.getcwd()
PROFILE_PATH = os.path.join(BASE_DIR, "user_english_profile.json")

# 🌟 根据 API 后台实测可用额度强行置顶！
DEFAULT_TEXT_MODELS = [
    "gemini-3.5-flash-lite",  # 500 RPD 首选日常主力
    "gemini-3.1-flash-lite",  # 500 RPD 备用主力
    "gemini-3.6-flash",       # 20 RPD 满血精析
    "gemini-3.8-flash",       # 20 RPD 备用精析
    "gemini-3-flash",         # 20 RPD 标配备选
    "gemini-2.5-flash",       # 20 RPD 保底
    "gemini-2.5-flash-lite"   # 20 RPD 保底
]

LANG_VOICES = {
    "英语": {
        "美式 - 女声 (Aria)": "en-US-AriaNeural",
        "美式 - 男声 (Christopher)": "en-US-ChristopherNeural",
        "英式 - 女声 (Sonia)": "en-GB-SoniaNeural",
        "英式 - 男声 (Ryan)": "en-GB-RyanNeural"
    },
    "日语": {
        "标准 - 女声 (Nanami)": "ja-JP-NanamiNeural",
        "标准 - 男声 (Keita)": "ja-JP-KeitaNeural"
    },
    "意大利语": {
        "标准 - 女声 (Elsa)": "it-IT-ElsaNeural",
        "标准 - 男声 (Diego)": "it-IT-DiegoNeural"
    }
}

SPEED_RATES = {
    "x0.6 (更慢)": "-40%",
    "x0.8 (较慢)": "-20%",
    "x0.9 (略慢)": "-10%",
    "x1.0 (正常)": "+0%",
    "x1.2 (较快)": "+20%"
}

STOPWORDS = {
    "i", "me", "my", "we", "our", "you", "your", "he", "him", "his", "she", "her", "it", "its", "they", "them", "their",
    "what", "which", "who", "whom", "this", "that", "these", "those", "am", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "having", "do", "does", "did", "doing", "a", "an", "the", "and", "but", "if", "or", "because", "as",
    "until", "while", "of", "at", "by", "for", "with", "about", "against", "between", "into", "through", "during", "before",
    "after", "above", "below", "to", "from", "up", "down", "in", "out", "on", "off", "over", "under", "again", "further",
    "then", "once", "here", "there", "when", "where", "why", "how", "all", "any", "both", "each", "few", "more", "most",
    "other", "some", "such", "no", "nor", "not", "only", "own", "same", "so", "than", "too", "very", "can", "will", "just"
}

def load_profile():
    default_data = {
        "api_key": "",
        "elo_score": 320,
        "calibrated": False,
        "preferred_model": "gemini-3.5-flash-lite",
        "pro_model": "gemini-3.6-flash",
        "streak": 0,
        "history_count": 0
    }
    if os.path.exists(PROFILE_PATH):
        try:
            with open(PROFILE_PATH, "r", encoding="utf-8") as f:
                saved = json.load(f)
                default_data.update(saved)
        except Exception:
            pass
    return default_data

def save_profile(profile_data):
    try:
        with open(PROFILE_PATH, "w", encoding="utf-8") as f:
            json.dump(profile_data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def get_elo_stage_info(elo):
    if elo < 250:
        return "🌱 初阶：具象画面锚定 (CEFR A2-B1)", "#27ae60", "使用核心1500基础词 + 强生活画面感描绘，建立零障碍直觉印象"
    elif elo < 450:
        return "🌊 中阶：母语语境延展 (CEFR B2)", "#2980b9", "标准英英功能释义 + 母语者脑海意象 + 高频语块搭配"
    else:
        return "🔬 高阶：精准手术刀辨析 (CEFR C1-C2)", "#8e44ad", "直击学术/商务语域色彩 + 近义词边界解剖 + 严密概念定义"

def render_status_banner():
    prof = load_profile()
    elo = prof.get("elo_score", 320)
    has_key = bool(prof.get("api_key", "").strip())
    cur_model = prof.get("preferred_model", "gemini-3.5-flash-lite")
    pro_model = prof.get("pro_model", "gemini-3.6-flash")
    stage_name, color, desc = get_elo_stage_info(elo)
    key_badge = (
        f"<span style='background:#dcfce7; color:#166534; padding:3px 8px; border-radius:12px; font-size:12px; font-weight:bold;'>🔑 日常: {cur_model} | 精析: {pro_model}</span>"
        if has_key else
        "<span style='background:#fee2e2; color:#991b1b; padding:3px 8px; border-radius:12px; font-size:12px; font-weight:bold;'>⚠️ 未配置 API Key</span>"
    )
    calib_badge = "已标定" if prof.get("calibrated") else "默认初始值"
    
    return f"""
    <div style="background: linear-gradient(90deg, #f8fafc 0%, #f1f5f9 100%); border-left: 5px solid {color}; padding: 10px 15px; border-radius: 6px; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.04);">
        <div>
            <span style="font-size: 15px; font-weight: bold; color: {color};">{stage_name}</span>
            <span style="background: {color}; color: white; padding: 2px 8px; border-radius: 10px; font-size: 12px; margin-left: 8px; font-weight: bold;">Elo: {elo} / 600</span>
            <span style="color: #64748b; font-size: 12px; margin-left: 6px;">({calib_badge})</span>
            <div style="font-size: 12px; color: #475569; margin-top: 3px;">🎯 当前策略：{desc}</div>
        </div>
        <div>{key_badge}</div>
    </div>
    """

# ==========================================
# 🌟 音频生成与 A-B 复读引擎
# ==========================================
async def generate_audio_async(text, lang_choice, voice_choice, speed_choice):
    if not text.strip(): 
        return "<div style='color: #e74c3c; padding: 10px;'>⚠️ 请先在左侧输入文本。</div>"
        
    now = time.time()
    for f in glob.glob(os.path.join(TEMP_DIR, "audio_*.mp3")):
        if os.path.getmtime(f) < now - 3600:
            try: os.remove(f)
            except: pass

    voice_id = LANG_VOICES[lang_choice][voice_choice]
    safe_filename = f"audio_{uuid.uuid4().hex[:8]}.mp3"
    output_path = os.path.join(TEMP_DIR, safe_filename)
    
    try:
        communicate = edge_tts.Communicate(text, voice_id, rate=SPEED_RATES[speed_choice])
        await communicate.save(output_path)
        with open(output_path, "rb") as f:
            audio_b64 = base64.b64encode(f.read()).decode('utf-8')
    except Exception as e:
        return f"<div style='color: #e74c3c; padding: 10px;'>⚠️ 播放器生成出错: {str(e)}</div>"
    finally:
        if os.path.exists(output_path):
            try: os.remove(output_path)
            except: pass

    uid = uuid.uuid4().hex[:8]
    html_controls = f"""
    <div style="background: #fdfdfd; border: 1px solid #e5e7eb; border-radius: 8px; padding: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.02);">
        <div style="margin-bottom: 10px; font-size: 13px; color: #8e44ad; font-weight: bold;">
            🎧 原生进度条播放器：请拖动进度条定位，随后在下方抓取精确时间。
        </div>
        <audio id="audio_core_{uid}" src="data:audio/mp3;base64,{audio_b64}" controls style="width: 100%; border-radius: 5px; outline: none; margin-bottom: 15px; height: 40px;"></audio>
        <div style="display: flex; gap: 15px; align-items: center; flex-wrap: wrap;">
            <div style="display: flex; gap: 5px; align-items: center; font-size: 14px; background: #f3f4f6; padding: 5px 10px; border-radius: 6px;">
                <span style="font-weight: 600; color: #4b5563; margin-right: 5px;">A-B区间</span>
                <input type="number" id="inStart_{uid}" placeholder="0.00" step="0.01" style="width: 65px; text-align: center; border: 1px solid #d1d5db; border-radius: 4px; padding: 4px; outline: none;">
                <button onclick="document.getElementById('inStart_{uid}').value = document.getElementById('audio_core_{uid}').currentTime.toFixed(2)" style="cursor:pointer; background:#fff; border:1px solid #d1d5db; border-radius:4px; padding:4px 8px; font-size: 12px; color: #374151;">取起点</button>
                <span style="color: #9ca3af; margin: 0 2px;">—</span>
                <input type="number" id="inEnd_{uid}" placeholder="结束" step="0.01" style="width: 65px; text-align: center; border: 1px solid #d1d5db; border-radius: 4px; padding: 4px; outline: none;">
                <button onclick="document.getElementById('inEnd_{uid}').value = document.getElementById('audio_core_{uid}').currentTime.toFixed(2)" style="cursor:pointer; background:#fff; border:1px solid #d1d5db; border-radius:4px; padding:4px 8px; font-size: 12px; color: #374151;">取终点</button>
            </div>
            <div style="display: flex; gap: 5px; align-items: center; font-size: 14px; background: #f3f4f6; padding: 5px 10px; border-radius: 6px;">
                <span style="font-weight: 600; color: #4b5563;">次数</span>
                <select id="selCount_{uid}" style="border:1px solid #d1d5db; border-radius: 4px; padding: 4px; outline: none; cursor: pointer; background: #fff;">
                    <option value="999999" selected>∞ 无限</option>
                    <option value="1">1 次</option>
                    <option value="2">2 次</option>
                    <option value="3">3 次</option>
                    <option value="5">5 次</option>
                    <option value="10">10 次</option>
                </select>
            </div>
            <button id="btnLoop_{uid}" onclick="window.toggleLoop_{uid}()" style="margin-left: auto; background: #f97316; color: white; border: none; padding: 8px 18px; border-radius: 6px; cursor: pointer; font-weight: bold; font-size: 14px; transition: all 0.2s;">
                ▶️ 开始洗脑复读
            </button>
        </div>
        <div style="margin-top: 15px; text-align: right; border-top: 1px dashed #ddd; padding-top: 10px;">
            <a href="data:audio/mp3;base64,{audio_b64}" download="精读练习音频.mp3" style="color: #8e44ad; text-decoration: none; font-weight: bold; font-size: 14px; background: #f3e9f7; padding: 6px 12px; border-radius: 5px;">📥 下载完整 MP3</a>
        </div>
    </div>
    <img src="dummy.jpg" style="display:none;" onerror="
        window.loopState_{uid} = {{ active: false, count: 0, timer: null }};
        if (window.audioKeydownHandler_{uid}) {{
            window.removeEventListener('keydown', window.audioKeydownHandler_{uid});
        }}
        window.audioKeydownHandler_{uid} = function(e) {{
            if (!window.loopState_{uid}.active) return;
            var aud = document.getElementById('audio_core_{uid}');
            if (!aud) return;
            if (e.code === 'Space') {{
                e.preventDefault(); 
                if (aud.paused) aud.play().catch(err => console.log(err));
                else aud.pause();
            }} else if (e.code === 'ArrowLeft') {{
                e.preventDefault();
                aud.currentTime = Math.max(0, aud.currentTime - 1.0);
            }} else if (e.code === 'ArrowRight') {{
                e.preventDefault();
                aud.currentTime = Math.min(aud.duration, aud.currentTime + 1.0);
            }}
        }};
        window.addEventListener('keydown', window.audioKeydownHandler_{uid});

        window.toggleLoop_{uid} = function() {{
            var aud = document.getElementById('audio_core_{uid}');
            var btn = document.getElementById('btnLoop_{uid}');
            var start = parseFloat(document.getElementById('inStart_{uid}').value) || 0;
            var end = parseFloat(document.getElementById('inEnd_{uid}').value) || aud.duration;
            var maxCount = parseInt(document.getElementById('selCount_{uid}').value) || 999999;
            
            if (!window.loopState_{uid}.active) {{
                if (start >= end) {{ alert('❌ 起点时间必须小于终点时间！'); return; }}
                window.loopState_{uid}.active = true;
                window.loopState_{uid}.count = 0;
                aud.currentTime = start;
                aud.play().catch(e => console.log(e));
                btn.innerHTML = '⏹ 停止复读';
                btn.style.background = '#ef4444';
                
                if (window.loopState_{uid}.timer) clearInterval(window.loopState_{uid}.timer);
                window.loopState_{uid}.timer = setInterval(function() {{
                    if (!window.loopState_{uid}.active) {{
                        clearInterval(window.loopState_{uid}.timer);
                        return;
                    }}
                    var currEnd = parseFloat(document.getElementById('inEnd_{uid}').value) || aud.duration;
                    if (aud.currentTime >= currEnd) {{
                        window.loopState_{uid}.count++;
                        if (window.loopState_{uid}.count >= maxCount) {{
                            window.loopState_{uid}.active = false;
                            aud.pause();
                            btn.innerHTML = '▶️ 开始洗脑复读';
                            btn.style.background = '#f97316';
                            clearInterval(window.loopState_{uid}.timer);
                        }} else {{
                            aud.currentTime = parseFloat(document.getElementById('inStart_{uid}').value) || 0;
                            aud.play().catch(e => console.log(e));
                        }}
                    }}
                }}, 50);
            }} else {{
                window.loopState_{uid}.active = false;
                aud.pause();
                btn.innerHTML = '▶️ 开始洗脑复读';
                btn.style.background = '#f97316';
                if (window.loopState_{uid}.timer) clearInterval(window.loopState_{uid}.timer);
            }}
        }};
        this.parentNode.removeChild(this);
    ">
    """
    return html_controls

def generate_audio(text, lang_choice, voice_choice, speed_choice):
    return asyncio.run(generate_audio_async(text, lang_choice, voice_choice, speed_choice))

async def get_audio_b64(text, lang_choice, voice_choice):
    if not text: return ""
    try:
        async def _generate():
            voice_id = LANG_VOICES[lang_choice][voice_choice]
            communicate = edge_tts.Communicate(text, voice_id)
            audio_data = b""
            async for chunk in communicate.stream():
                if chunk["type"] == "audio": 
                    audio_data += chunk["data"]
            return base64.b64encode(audio_data).decode('utf-8')
        
        return await asyncio.wait_for(_generate(), timeout=8.0)
    except Exception: 
        return ""

# ==========================================
# 🌊 Gemini i+1 智能模型分层引擎
# ==========================================
def extract_context_sentence(full_text, selected_text, sel_index=None):
    if not full_text:
        return selected_text
    try:
        if sel_index and isinstance(sel_index, (list, tuple)) and len(sel_index) == 2:
            start, end = sel_index[0], sel_index[1]
        else:
            start = full_text.find(selected_text)
            end = start + len(selected_text) if start != -1 else 0
            
        if start == -1:
            return selected_text
            
        left_bound = max(
            full_text.rfind('.', 0, start),
            full_text.rfind('!', 0, start),
            full_text.rfind('?', 0, start),
            full_text.rfind('\n', 0, start)
        )
        right_candidates = [
            pos for pos in (
                full_text.find('.', end),
                full_text.find('!', end),
                full_text.find('?', end),
                full_text.find('\n', end)
            ) if pos != -1
        ]
        right_bound = min(right_candidates) + 1 if right_candidates else len(full_text)
        sentence = full_text[left_bound + 1 : right_bound].strip()
        return sentence if len(sentence) > len(selected_text) else selected_text
    except Exception:
        return selected_text

def fetch_remote_models_on_demand(api_key):
    if not api_key or not api_key.strip():
        return DEFAULT_TEXT_MODELS
    clean_key = urllib.parse.quote(api_key.strip())
    found = []
    for api_ver in ["v1beta", "v1"]:
        url = f"https://generativelanguage.googleapis.com/{api_ver}/models?key={clean_key}"
        try:
            res = requests.get(url, timeout=(3, 8))
            if res.status_code == 200:
                for m in res.json().get("models", []):
                    methods = m.get("supportedGenerationMethods", [])
                    name = m.get("name", "").replace("models/", "")
                    if "generateContent" in methods and "gemini" in name.lower():
                        if not any(x in name.lower() for x in ["embedding", "imagen", "veo", "aqa", "tts"]):
                            if name not in found:
                                found.append(name)
        except Exception:
            pass
    combined = list(dict.fromkeys(DEFAULT_TEXT_MODELS + found))
    return combined

def extract_json_safely(raw_text):
    text = raw_text.strip()
    text = re.sub(r'^```(?:json)?\s*|\s*```$', '', text, flags=re.MULTILINE).strip()
    try:
        return json.loads(text)
    except Exception:
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            return json.loads(match.group(0))
        raise

def call_gemini_immersion_api(selected_text, context_sentence, elo_score, api_key, model_override=None):
    prof = load_profile()
    target_model = model_override if model_override else prof.get("preferred_model", "gemini-3.5-flash-lite")
    
    if elo_score < 250:
        level_prompt = f"""
        Learner Level: Beginner-Intermediate (Elo {elo_score}/600, CEFR A2-B1).
        STRICT RULE: Use ONLY simple, everyday English words in your explanations.
        - "mental_image": Paint a super vivid, physical, everyday life scene or action for "{selected_text}".
        - "core_definition": Explain the meaning in 1-2 very simple, friendly English sentences.
        - "precision_nuance": Give 1 super easy tip on when people say this in daily life.
        """
    elif elo_score < 450:
        level_prompt = f"""
        Learner Level: Upper-Intermediate (Elo {elo_score}/600, CEFR B2).
        RULE: Use natural, clear, idiomatic English.
        - "mental_image": Describe the core mental model or scenario a native speaker pictures for "{selected_text}".
        - "core_definition": Provide an accurate, functional English definition in context.
        - "precision_nuance": Explain the register and contrast it with 1 common simpler word.
        """
    else:
        level_prompt = f"""
        Learner Level: Advanced/Mastery (Elo {elo_score}/600, CEFR C1-C2).
        RULE: Surgical lexical precision, analytical depth, and stylistic nuance.
        - "mental_image": Articulate the underlying conceptual metaphor or cognitive framing.
        - "core_definition": Rigorous, high-precision definition capturing the exact semantic boundary.
        - "precision_nuance": Dissect nuance by contrasting "{selected_text}" with 2 close synonyms.
        """

    prompt = f"""
    You are an elite English cognitive lexicographer based on Krashen's i+1 theory.
    Target: "{selected_text}"
    Context: "{context_sentence}"
    {level_prompt}

    Return ONLY a raw, valid JSON object with the exact keys below:
    {{
        "phonetic": "IPA phonetic transcription or empty string",
        "part_of_speech": "pos tag",
        "mental_image": "English text for mental imagery",
        "core_definition": "English text for core definition",
        "precision_nuance": "English text for nuance",
        "collocations": [
            {{"phrase": "chunk 1", "meaning_en": "explanation"}},
            {{"phrase": "chunk 2", "meaning_en": "explanation"}},
            {{"phrase": "chunk 3", "meaning_en": "explanation"}}
        ],
        "context_example": "Example sentence",
        "zh_emergency": "Ultra-brief Chinese meaning under 15 chars"
    }}
    """

    clean_key = urllib.parse.quote(api_key.strip())
    headers = {"Content-Type": "application/json", "x-goog-api-key": api_key.strip()}
    
    fallback_queue = [
        "gemini-3.5-flash-lite", 
        "gemini-3.1-flash-lite", 
        "gemini-3.6-flash", 
        "gemini-3.8-flash"
    ]
    models_to_try = list(dict.fromkeys([target_model] + fallback_queue))

    err_logs = []
    for m in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={clean_key}"
        payload = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.35}}
        try:
            res = requests.post(url, headers=headers, json=payload, timeout=(4, 12))
            if res.status_code == 200:
                raw_text = res.json()["candidates"][0]["content"]["parts"][0]["text"]
                parsed = extract_json_safely(raw_text)
                parsed["_used_model"] = m
                return parsed, None
            else:
                err_logs.append(f"[{m}] HTTP {res.status_code}: {res.text[:120]}")
        except Exception as e:
            err_logs.append(f"[{m}] 错误: {str(e)}")
            
    return None, " | ".join(err_logs)

async def build_immersion_html_async(selected_text, context_sentence, lang_choice, voice_choice, model_override=None):
    prof = load_profile()
    api_key = prof.get("api_key", "").strip()
    elo_score = prof.get("elo_score", 320)
    stage_name, stage_color, _ = get_elo_stage_info(elo_score)

    if not api_key:
        return """
        <div style="padding: 18px; background: #fffbeb; border: 1px solid #fde68a; border-radius: 8px; color: #92400e;">
            <h3 style="margin-top:0;">🔑 尚未填入 Gemini API Key</h3>
            <p style="font-size: 14px;">请在上方折叠栏配置密钥后使用。</p>
        </div>
        """

    data, err = await asyncio.to_thread(call_gemini_immersion_api, selected_text, context_sentence, elo_score, api_key, model_override)
    if not data:
        return f"""
        <div style="padding: 15px; background: #fef2f2; border: 1px solid #fecaca; border-radius: 8px; color: #991b1b;">
            <h4>⚠️ 引擎响应异常或全部模型重试失败</h4>
            <p style="font-size: 13px;">追踪日志：<br>{err}</p>
        </div>
        """

    used_model = data.get("_used_model", model_override or prof.get("preferred_model", ""))
    phonetic = data.get("phonetic", "")
    pos = data.get("part_of_speech", "")
    mental_image = data.get("mental_image", "")
    core_def = data.get("core_definition", "")
    nuance = data.get("precision_nuance", "")
    collocations = data.get("collocations", [])[:3]
    example_sent = data.get("context_example", "")
    zh_emergency = data.get("zh_emergency", "")

    audio_tasks = [
        get_audio_b64(selected_text, lang_choice, voice_choice),
        get_audio_b64(mental_image, lang_choice, voice_choice),
        get_audio_b64(core_def, lang_choice, voice_choice),
        get_audio_b64(example_sent, lang_choice, voice_choice)
    ]
    for c in collocations:
        audio_tasks.append(get_audio_b64(c.get("phrase", ""), lang_choice, voice_choice))

    audios = await asyncio.gather(*audio_tasks)
    word_aud, img_aud, def_aud, ex_aud = audios[0], audios[1], audios[2], audios[3]
    coll_auds = audios[4:]

    audio_css = "height: 28px; width: 100%; max-width: 280px; margin-top: 4px; outline: none;"
    
    html = f"<div style='padding: 12px; font-family: -apple-system, BlinkMacSystemFont, \"Segoe UI\", Roboto, sans-serif;'>"
    html += f"<div style='display:flex; justify-content:space-between; align-items:center; margin-bottom:6px; flex-wrap:wrap; gap:4px;'>"
    html += f"<span style='background:{stage_color}; color:white; font-size:11px; padding:2px 8px; border-radius:10px; font-weight:bold;'>{stage_name} (Elo {elo_score})</span>"
    html += f"<span style='background:#e2e8f0; color:#334155; font-size:11px; padding:2px 8px; border-radius:10px; font-weight:600;'>🤖 本次驱动: {used_model}</span>"
    if pos:
        html += f"<span style='color:#64748b; font-size:12px; font-style:italic; font-weight:600;'>{pos}</span>"
    html += f"</div>"

    html += f"<h2 style='margin: 4px 0; color: #1e293b;'>{selected_text}</h2>"
    if phonetic:
        html += f"<div style='color: #0d9488; font-size: 14px; margin-bottom: 6px;'>{phonetic}</div>"
    if word_aud:
        html += f"<audio controls style='{audio_css}' src='data:audio/mp3;base64,{word_aud}'></audio>"

    if mental_image:
        html += f"""
        <div style="margin-top: 14px; background: #f0fdf4; border-left: 4px solid #22c55e; padding: 10px 12px; border-radius: 6px;">
            <div style="font-size: 13px; font-weight: bold; color: #15803d; margin-bottom: 4px;">🎬 Mental Picture (脑海画面直觉)</div>
            <div style="font-size: 14px; color: #166534; line-height: 1.55;">{mental_image}</div>
            {f"<audio controls style='{audio_css}' src='data:audio/mp3;base64,{img_aud}'></audio>" if img_aud else ""}
        </div>
        """

    if core_def:
        html += f"""
        <div style="margin-top: 12px; background: #eff6ff; border-left: 4px solid #3b82f6; padding: 10px 12px; border-radius: 6px;">
            <div style="font-size: 13px; font-weight: bold; color: #1d4ed8; margin-bottom: 4px;">🎯 Adaptive Definition (i+1 精准定义)</div>
            <div style="font-size: 14px; color: #1e3a8a; line-height: 1.55; font-weight: 500;">{core_def}</div>
            {f"<audio controls style='{audio_css}' src='data:audio/mp3;base64,{def_aud}'></audio>" if def_aud else ""}
        </div>
        """

    if nuance:
        html += f"""
        <div style="margin-top: 12px; background: #faf5ff; border-left: 4px solid #a855f7; padding: 10px 12px; border-radius: 6px;">
            <div style="font-size: 13px; font-weight: bold; color: #7e22ce; margin-bottom: 4px;">🔬 Nuance & Precision (语感边界与辨析)</div>
            <div style="font-size: 13.5px; color: #581c87; line-height: 1.55;">{nuance}</div>
        </div>
        """

    if collocations:
        html += f"<div style='margin-top: 14px;'><div style='font-size: 13px; font-weight: bold; color: #0f172a; margin-bottom: 6px;'>📌 Active Chunks (高频语块)</div>"
        html += "<ul style='padding-left: 18px; margin: 0;'>"
        for idx, c in enumerate(collocations):
            p_en, m_en = c.get("phrase", ""), c.get("meaning_en", "")
            c_aud = coll_auds[idx] if idx < len(coll_auds) else ""
            html += f"<li style='margin-bottom: 8px; font-size: 13.5px;'>"
            html += f"<b style='color: #0369a1;'>{p_en}</b> — <span style='color: #475569;'>{m_en}</span><br>"
            if c_aud:
                html += f"<audio controls style='{audio_css}' src='data:audio/mp3;base64,{c_aud}'></audio>"
            html += "</li>"
        html += "</ul></div>"

    if example_sent:
        html += f"""
        <div style="margin-top: 12px; border-top: 1px dashed #e2e8f0; padding-top: 10px;">
            <div style="font-size: 13px; font-weight: bold; color: #475569; margin-bottom: 4px;">📝 Immersive Example</div>
            <div style="font-size: 13.5px; color: #334155; font-style: italic;">"{example_sent}"</div>
            {f"<audio controls style='{audio_css}' src='data:audio/mp3;base64,{ex_aud}'></audio>" if ex_aud else ""}
        </div>
        """

    if zh_emergency:
        html += f"""
        <details style="margin-top: 14px; font-size: 12px; color: #94a3b8; cursor: pointer;">
            <summary style="outline: none;">🙈 实在卡壳？点此偷看一眼中文破冰提示</summary>
            <div style="margin-top: 5px; padding: 6px 10px; background: #f8fafc; border-radius: 4px; color: #64748b;">
                参考大意：{zh_emergency}
            </div>
        </details>
        """

    html += "</div>"
    return html

# ==========================================
# 📚 传统双语字典模块
# ==========================================
def get_youdao_json(query, lang):
    le_dict = {"英语": "en", "日语": "jap", "意大利语": "it"}
    le = le_dict.get(lang, "en")
    encoded_query = urllib.parse.quote(query)
    url = f"http://dict.youdao.com/jsonapi?q={encoded_query}&le={le}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        res = requests.get(url, headers=headers, timeout=(3, 8))
        if res.status_code == 200: return res.json()
    except: pass
    return {}

def youdao_fanyi_translate(text):
    try:
        url = f"http://fanyi.youdao.com/translate?&doctype=json&type=AUTO&i={urllib.parse.quote(text)}"
        res = requests.get(url, timeout=(3, 8))
        if res.status_code == 200:
            data = res.json()
            return "".join([tgt['tgt'] for tgt in data['translateResult'][0]])
    except: pass
    return ""

def google_translate(text, lang):
    sl = {"英语": "en", "日语": "ja", "意大利语": "it"}.get(lang, "en")
    url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl={sl}&tl=zh-CN&dt=t&dt=rm&q={urllib.parse.quote(text)}"
    try:
        res = requests.get(url, timeout=(3, 8))
        if res.status_code == 200:
            data = res.json()
            translated_text, romaji = "", ""
            for item in data[0]:
                if item[0] and isinstance(item[0], str):
                    translated_text += item[0]
                if len(item) > 3 and item[0] is None and item[1] is None and isinstance(item[3], str):
                    romaji += item[3] + " "
            return translated_text.strip(), romaji.strip()
    except: pass
    return "", ""

def mymemory_translate(text, lang):
    try:
        lang_code = {"英语": "en", "日语": "ja", "意大利语": "it"}.get(lang, "en")
        res = requests.get(f"https://api.mymemory.translated.net/get?q={urllib.parse.quote(text)}&langpair={lang_code}|zh-CN", timeout=(3, 8))
        return res.json()["responseData"]["translatedText"]
    except: return ""

def get_jisho_kana(word):
    try:
        url = f"https://jisho.org/api/v1/search/words?keyword={urllib.parse.quote(word)}"
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=(3, 8))
        if res.status_code == 200:
            data = res.json()
            if data.get("data"):
                for item in data["data"]:
                    for jp in item.get("japanese", []):
                        if jp.get("word") == word and jp.get("reading"):
                            return jp.get("reading")
                return data["data"][0].get("japanese", [{}])[0].get("reading", "")
    except: pass
    return ""

def safe_extract_translation(word_node):
    try:
        trs = word_node.get("trs", [])
        if not trs: return ""
        trans_list = []
        for tr in trs:
            i_node = tr.get("tr", [{}])[0].get("l", {}).get("i", "")
            if isinstance(i_node, list): trans_list.append("".join(i_node))
            elif isinstance(i_node, dict): trans_list.append(i_node.get("#text", str(i_node)))
            else: trans_list.append(str(i_node))
        return "; ".join(trans_list)
    except: pass

def extract_phonetic(data, lang):
    if not data: return ""
    try:
        if lang == "日语":
            kana, romaji = "", ""
            if "jc" in data and "word" in data["jc"] and len(data["jc"]["word"]) > 0:
                w = data["jc"]["word"][0]
                kana, romaji = w.get("kana", ""), w.get("romaji", "")
            if not kana and "jap" in data and "word" in data["jap"] and len(data["jap"]["word"]) > 0:
                w = data["jap"]["word"][0]
                kana, romaji = w.get("kana", ""), w.get("romaji", "")
            res = []
            if kana: res.append(f"[{kana}]")
            if romaji: res.append(f"romaji: {romaji}")
            if res: return " / ".join(res)
        elif lang == "意大利语":
            if "it" in data and "word" in data["it"] and len(data["it"]["word"]) > 0:
                w = data["it"]["word"][0]
                if w.get("phone"): return f"[{w['phone']}]"
        else:
            if "simple" in data and "word" in data["simple"] and len(data["simple"]["word"]) > 0:
                w = data["simple"]["word"][0]
                uk, us, phone = w.get("ukphone"), w.get("usphone"), w.get("phone")
                if uk and us: return f"英 [{uk}]  美 [{us}]"
                elif uk or us: return f"[{uk or us}]"
                elif phone: return f"[{phone}]"
            if "ec" in data and "word" in data["ec"] and len(data["ec"]["word"]) > 0:
                w = data["ec"]["word"][0]
                uk, us = w.get("ukphone"), w.get("usphone")
                if uk and us: return f"英 [{uk}]  美 [{us}]"
                elif uk or us: return f"[{uk or us}]"
    except: pass
    return ""

def extract_collocations(data, query_text):
    colls = []
    try:
        if "phrs" in data and "phrs" in data["phrs"]:
            for p in data["phrs"]["phrs"][:6]:
                en = p["phr"]["headword"]["l"]["i"]
                en = "".join(en) if isinstance(en, list) else str(en)
                try:
                    zh_raw = p["phr"]["trs"][0]["tr"]["l"]["i"]
                    zh = zh_raw.get("#text", str(zh_raw)) if isinstance(zh_raw, dict) else ("".join(zh_raw) if isinstance(zh_raw, list) else str(zh_raw))
                except: zh = "暂无释义"
                colls.append({"en": en, "zh": zh})
    except: pass
    return colls

def score_english_collocation(phrase_en):
    phrase_lower = phrase_en.lower()
    score = 0
    high_value_markers = ['be ', ' of', ' to ', ' doing', ' sth', ' sb', ' in ', ' for ', ' with ', ' on ', ' about ', 'make ', 'take ', 'get ', 'have ', 'used to', 'capable']
    for marker in high_value_markers:
        if marker in phrase_lower: score += 20
    if len(phrase_lower.split()) >= 3: score += 10
    low_value_markers = ['market', 'economy', 'industry', 'system', 'stage', 'embryo', 'adult', 'character']
    for marker in low_value_markers:
        if marker in phrase_lower: score -= 15
    return score

def fetch_dictionary_data(text, lang):
    text_clean = text.strip()
    queries = [text_clean]
    is_paragraph = len(text_clean) > 6 if lang == "日语" else len(text_clean.split()) > 3 
    
    content_words = []
    if lang == "英语":
        words = re.findall(r'\b[a-zA-Z]{5,}\b', text_clean.lower())
        unique_words = list(dict.fromkeys([w for w in words if w not in STOPWORDS]))
        unique_words.sort(key=len, reverse=True) 
        content_words = unique_words[:6]
        for cw in content_words:
            if cw not in queries: queries.append(cw)
            
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        future_to_word = {executor.submit(get_youdao_json, q, lang): q for q in queries}
        for future in concurrent.futures.as_completed(future_to_word):
            w = future_to_word[future]
            try: results[w] = future.result()
            except: results[w] = {}

    main_data = results.get(text_clean, {})
    zh_trans = ""
    try:
        if lang == "日语":
            if "jc" in main_data and "word" in main_data["jc"] and len(main_data["jc"]["word"]) > 0:
                zh_trans = safe_extract_translation(main_data["jc"]["word"][0])
            elif "jap" in main_data and "word" in main_data["jap"] and len(main_data["jap"]["word"]) > 0:
                zh_trans = safe_extract_translation(main_data["jap"]["word"][0])
        elif lang == "意大利语":
            if "it" in main_data and "word" in main_data["it"]:
                zh_trans = safe_extract_translation(main_data["it"]["word"][0])
        elif lang == "英语":
            if "ec" in main_data and "word" in main_data["ec"]:
                zh_trans = safe_extract_translation(main_data["ec"]["word"][0])
    except: pass

    gt_trans, gt_romaji = "", ""
    if not zh_trans or is_paragraph or lang == "日语":
        gt_trans, gt_romaji = google_translate(text_clean, lang)
        if not zh_trans or is_paragraph:
            if gt_trans and gt_trans.lower() != text_clean.lower():
                zh_trans = gt_trans
            else:
                yd_trans = youdao_fanyi_translate(text_clean)
                zh_trans = yd_trans if yd_trans else mymemory_translate(text_clean, lang)

    if not zh_trans: zh_trans = "暂无释义，请更换文本。"
    main_phonetic = extract_phonetic(main_data, lang)

    if lang == "日语":
        jisho_kana = get_jisho_kana(text_clean) if not is_paragraph else ""
        yd_kana = ""
        if "jc" in main_data and "word" in main_data["jc"] and len(main_data["jc"]["word"]) > 0:
            yd_kana = main_data["jc"]["word"][0].get("kana", "")
        final_kana = jisho_kana if jisho_kana else yd_kana
        ph_parts = []
        if final_kana: ph_parts.append(f"[{final_kana}]")
        if gt_romaji: ph_parts.append(f"romaji: {gt_romaji}")
        if ph_parts: main_phonetic = " / ".join(ph_parts)

    raw_collocations = []
    seen_en = set()
    for q in queries:
        if q in results:
            for coll in extract_collocations(results[q], q):
                if coll["en"].lower() not in seen_en:
                    coll["phonetic"] = extract_phonetic(results.get(coll["en"], {}), lang)
                    raw_collocations.append(coll)
                    seen_en.add(coll["en"].lower())
            if is_paragraph and q != text_clean and q not in seen_en:
                word_zh = ""
                if lang == "英语":
                    try: word_zh = safe_extract_translation(results[q].get("ec", {}).get("word", [{}])[0])
                    except: pass
                if word_zh:
                    raw_collocations.append({"en": q, "zh": f"[核心词汇] {word_zh}", "phonetic": extract_phonetic(results[q], lang)})
                    seen_en.add(q.lower())

    if lang == "英语":
        scored = [(score_english_collocation(c["en"]) if "[核心词汇]" not in c["zh"] else 999, c) for c in raw_collocations]
        scored.sort(key=lambda x: x[0], reverse=True)
        collocations = [item[1] for item in scored][:6]
    else:
        collocations = raw_collocations[:6]

    examples, examples_zh = [], []
    try:
        if "blng_sents_part" in main_data and "sentence-pair" in main_data["blng_sents_part"]:
            for sp in main_data["blng_sents_part"]["sentence-pair"][:3]:
                examples.append(str(sp["sentence-eng"]))
                examples_zh.append(str(sp["sentence-translation"]))
    except: pass

    en_en = []
    if lang == "英语":
        targets = [text_clean] if not is_paragraph else content_words[:2]
        for target in targets:
            try:
                res_en = requests.get(f"https://api.dictionaryapi.dev/api/v2/entries/en/{target}", timeout=(3, 8))
                if res_en.status_code == 200:
                    json_data = res_en.json()[0]
                    for meaning in json_data.get('meanings', []):
                        pos = meaning.get('partOfSpeech', '')
                        for defn in meaning.get('definitions', []):
                            if len(en_en) < 4:
                                prefix = "" if not is_paragraph else f"<b>{target}</b>: "
                                en_en.append({'pos': pos, 'def': f"{prefix}{defn.get('definition', '')}"})
            except: pass

    return zh_trans, collocations, en_en, examples, examples_zh, main_phonetic

async def build_bilingual_html_async(selected_text, lang_choice, voice_choice):
    zh_trans, collocations, en_en, examples, examples_zh, main_phonetic = await asyncio.to_thread(fetch_dictionary_data, selected_text, lang_choice)
    audio_tasks = [get_audio_b64(selected_text, lang_choice, voice_choice)]
    for coll in collocations: audio_tasks.append(get_audio_b64(coll["en"], lang_choice, voice_choice))
    for item in en_en: audio_tasks.append(get_audio_b64(item['def'], lang_choice, voice_choice))
    for ex in examples: audio_tasks.append(get_audio_b64(re.sub(r'<[^>]+>', '', ex), lang_choice, voice_choice))

    audios = await asyncio.gather(*audio_tasks)
    idx = 0
    word_audio = audios[idx]; idx += 1
    coll_audios = audios[idx : idx + len(collocations)]; idx += len(collocations)
    en_en_audios = audios[idx : idx + len(en_en)]; idx += len(en_en)
    ex_audios = audios[idx : idx + len(examples)]

    audio_css = "height: 30px; width: 100%; max-width: 300px; margin-top: 5px; outline: none;"
    html = f"<div style='padding: 10px; font-family: sans-serif;'>"
    html += f"<h2 style='margin-bottom: 5px; color: #2c3e50;'>{selected_text}</h2>"
    if main_phonetic: html += f"<div style='color: #16a085; font-size: 15px; margin-bottom: 10px;'>{main_phonetic}</div>"
    if word_audio: html += f"<audio controls style='{audio_css}' src='data:audio/mp3;base64,{word_audio}'></audio>"
    html += f"<hr style='margin: 15px 0; border: 0; border-top: 1px solid #eee;'>"
    html += f"<h4 style='color: #34495e; margin-bottom: 5px;'>【原文翻译】</h4>"
    html += f"<p style='font-size: 16px; font-weight: 500; color: #e74c3c;'>{zh_trans}</p>"

    if collocations:
        html += f"<hr style='margin: 15px 0; border: 0; border-top: 1px solid #eee;'>"
        html += f"<h4 style='color: #2980b9; margin-bottom: 5px;'>📌 【TEM/BEC 核心词与高频搭配】</h4><ul style='padding-left: 20px;'>"
        for i, coll in enumerate(collocations):
            zh_display = coll['zh'].replace("[核心词汇]", "<span style='background:#f39c12; color:white; padding:2px 6px; border-radius:4px; font-size:0.85em; margin-right:5px;'>核心词汇</span>")
            html += f"<li style='margin-bottom: 10px;'><b style='color: #2c3e50;'>{coll['en']}</b> "
            if coll.get("phonetic"): html += f"<span style='color: #16a085; font-size: 0.9em; margin-left: 5px;'>{coll['phonetic']}</span> "
            html += f"<br><span style='color: #7f8c8d; line-height: 1.8;'>{zh_display}</span><br>"
            if coll_audios[i]: html += f"<audio controls style='{audio_css}' src='data:audio/mp3;base64,{coll_audios[i]}'></audio>"
            html += f"</li>"
        html += "</ul>"

    if en_en:
        html += f"<hr style='margin: 15px 0; border: 0; border-top: 1px solid #eee;'>"
        html += f"<h4 style='color: #27ae60; margin-bottom: 5px;'>📖 【英英释义穿透】</h4><ul style='padding-left: 20px;'>"
        for i, item in enumerate(en_en):
            html += f"<li style='margin-bottom: 10px;'><span style='color: #7f8c8d; font-style: italic;'>[{item['pos']}]</span> {item['def']}<br>"
            if en_en_audios[i]: html += f"<audio controls style='{audio_css}' src='data:audio/mp3;base64,{en_en_audios[i]}'></audio>"
            html += f"</li>"
        html += "</ul>"

    if examples:
        html += f"<hr style='margin: 15px 0; border: 0; border-top: 1px solid #eee;'>"
        html += f"<h4 style='color: #8e44ad; margin-bottom: 5px;'>📝 【精选双语例句】</h4><ul style='padding-left: 20px;'>"
        for i, ex in enumerate(examples):
            display_ex = ex.replace('<b>', '<strong style="color:#d35400;">').replace('</b>', '</strong>')
            html += f"<li style='margin-bottom: 10px; line-height: 1.5;'><span>{display_ex}</span><br><span style='color: #7f8c8d;'>{examples_zh[i]}</span><br>"
            if ex_audios[i]: html += f"<audio controls style='{audio_css}' src='data:audio/mp3;base64,{ex_audios[i]}'></audio>"
            html += f"</li>"
        html += "</ul>"

    html += "</div>"
    return html

# ==========================================
# 🎯 划词路由与交互
# ==========================================
async def on_text_select(evt: gr.SelectData, full_text, lang_choice, voice_choice, study_mode, last_signature):
    selected_text = evt.value.strip()
    
    # 🌟 核心防误触机制：生成本次操作的指纹（文本+光标位置+语言配置）
    current_signature = f"{selected_text}_{evt.index}_{lang_choice}_{voice_choice}_{study_mode}"
    
    # 如果指纹完全一样，说明是焦点丢失导致的重复触发（比如正在点击右侧播放器），直接果断丢弃！
    if current_signature == last_signature:
        return gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update()
        
    if not selected_text:
        return "<p>请选择有效的文本。</p>", "", "", gr.update(visible=False), render_status_banner(), current_signature
        
    context_sentence = extract_context_sentence(full_text, selected_text, evt.index)
    
    if lang_choice == "英语" and "全英母语印象" in study_mode:
        html = await build_immersion_html_async(selected_text, context_sentence, lang_choice, voice_choice)
        return html, selected_text, context_sentence, gr.update(visible=True), render_status_banner(), current_signature
    else:
        html = await build_bilingual_html_async(selected_text, lang_choice, voice_choice)
        return html, selected_text, context_sentence, gr.update(visible=False), render_status_banner(), current_signature

async def handle_elo_feedback(delta, feedback_type, last_word, last_context, lang_choice, voice_choice):
    prof = load_profile()
    new_elo = max(100, min(600, prof.get("elo_score", 320) + delta))
    prof["elo_score"] = new_elo
    save_profile(prof)
    
    if feedback_type == "good" or not last_word:
        return gr.update(), render_status_banner(), new_elo
        
    new_card_html = await build_immersion_html_async(last_word, last_context, lang_choice, voice_choice)
    return new_card_html, render_status_banner(), new_elo

async def handle_manual_upgrade(last_word, last_context, lang_choice, voice_choice):
    if not last_word:
        return "<p>请先在左侧划取一个词或句子。</p>", render_status_banner()
    prof = load_profile()
    pro_model = prof.get("pro_model", "gemini-3.6-flash")
    html = await build_immersion_html_async(last_word, last_context, lang_choice, voice_choice, model_override=pro_model)
    return html, render_status_banner()

def save_settings_and_key(api_key_input, manual_elo, preferred_model, pro_model):
    prof = load_profile()
    if api_key_input.strip():
        prof["api_key"] = api_key_input.strip()
    prof["elo_score"] = int(manual_elo)
    prof["preferred_model"] = preferred_model
    prof["pro_model"] = pro_model
    save_profile(prof)
    return render_status_banner(), f"✅ 已保存！日常默认模型：**{preferred_model}** (500 RPD) ｜ 深度精析模型：**{pro_model}**"

def refresh_model_dropdowns(api_key_input):
    prof = load_profile()
    key = api_key_input.strip() or prof.get("api_key", "")
    models = fetch_remote_models_on_demand(key)
    cur_pref = prof.get("preferred_model", "gemini-3.5-flash-lite")
    cur_pro = prof.get("pro_model", "gemini-3.6-flash")
    return (
        gr.update(choices=models, value=cur_pref if cur_pref in models else models[0]),
        gr.update(choices=models, value=cur_pro if cur_pro in models else models[0]),
        f"🔄 扫描完成！当前共加载 {len(models)} 个可用文本生成模型。"
    )

def run_placement_calibration(pref_style, vocab_checked):
    base_map = {"A": 180, "B": 340, "C": 480}
    score = base_map.get(pref_style[0] if pref_style else "B", 320)
    final_elo = max(120, min(580, score + len(vocab_checked) * 18 - 35))
    
    prof = load_profile()
    prof["elo_score"] = final_elo
    prof["calibrated"] = True
    save_profile(prof)
    return render_status_banner(), final_elo, f"🎉 期初标定完成！初始分设定为 **{final_elo} Elo**。"

def cancel_generation_msg():
    return "<div style='padding: 30px 20px; color: #e74c3c; text-align: center; border: 1px dashed #fca5a5; border-radius: 8px;'>⏹️ <b>已成功打断解析！</b><br><br>您可以重新在左侧准确划选需要的词汇或句子。</div>"

head_js = """
<script>
    document.addEventListener('keydown', function(e) {
        if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'q') {
            e.preventDefault();
            var clearBtn = document.getElementById('clear_text_btn');
            if (clearBtn) { clearBtn.click(); }
        }
    });
</script>
"""

init_prof = load_profile()

with gr.Blocks(title="丹尼尔专属英日意语言学习系统 v5.2.4") as app:
    gr.Markdown("## 🎧 丹尼尔专属英日意语言学习系统 v5.2.4")
    
    status_banner = gr.HTML(value=render_status_banner())
    
    with gr.Accordion("⚙️ 全英大脑设置 & 双轨模型选择 & 🎯 水平标定", open=not bool(init_prof.get("api_key"))):
        with gr.Tabs():
            with gr.TabItem("🔑 1. API Key、双轨模型与段位"):
                with gr.Row():
                    api_key_box = gr.Textbox(
                        label="Gemini API Key",
                        value=init_prof.get("api_key", ""),
                        type="password",
                        placeholder="在此粘贴密钥...",
                        scale=2
                    )
                    model_dropdown = gr.Dropdown(
                        label="1️⃣ 日常划词默认模型 (已强行置顶 500 RPD 顶配)",
                        choices=DEFAULT_TEXT_MODELS,
                        value=init_prof.get("preferred_model", "gemini-3.5-flash-lite"),
                        allow_custom_value=True,
                        scale=2
                    )
                    pro_model_dropdown = gr.Dropdown(
                        label="2️⃣ 点击『🚀深度精析』时调用的高阶模型",
                        choices=DEFAULT_TEXT_MODELS,
                        value=init_prof.get("pro_model", "gemini-3.6-flash"),
                        allow_custom_value=True,
                        scale=2
                    )
                with gr.Row():
                    elo_slider = gr.Slider(
                        minimum=100, maximum=600, step=10,
                        value=init_prof.get("elo_score", 320),
                        label="当前全英解释深度 (Elo)",
                        scale=3
                    )
                    refresh_models_btn = gr.Button("🔄 联网扫描账号全部文本模型", variant="secondary", scale=1)
                    save_cfg_btn = gr.Button("💾 保存设置", variant="primary", scale=1)
                cfg_msg = gr.Markdown("")
                
            with gr.TabItem("🎯 2. 期初英语能力盲测"):
                calib_style = gr.Radio(
                    label="你偏好的全英解释风格",
                    choices=[
                        "A. [具象画面] Super vivid, everyday life scene or action.",
                        "B. [功能语境] Accurate, functional English definition.",
                        "C. [精准辨析] Surgical lexical precision and synonym dissection."
                    ],
                    value="B. [功能语境] Accurate, functional English definition."
                )
                calib_vocab = gr.CheckboxGroup(
                    label="你熟悉的进阶词汇",
                    choices=["1. Inevitable", "2. Ambiguous", "3. Deteriorate", "4. Meticulous", "5. Ubiquitous", "6. Ephemeral"]
                )
                calib_btn = gr.Button("🚀 锁定段位", variant="primary")
                calib_result_md = gr.Markdown("")

    last_selected_state = gr.State("")
    last_context_state = gr.State("")
    # 🌟 新增：专门用于记录前一次划词操作指纹的状态变量
    last_signature_state = gr.State("")

    with gr.Row():
        with gr.Column(scale=11):
            with gr.Row(elem_id="textbox_header"):
                gr.Markdown("📝 **学习文稿区** (Ctrl+Q 零延迟清空)")
                clear_btn = gr.Button("🗑️ 一键清空", size="sm", variant="secondary", elem_id="clear_text_btn")

            text_input = gr.Textbox(show_label=False, lines=11, placeholder="在此粘贴文稿并划词...")
            clear_btn.click(fn=None, js="() => ''", outputs=[text_input])
            
            with gr.Row():
                study_mode_radio = gr.Radio(
                    label="🧠 查词认知模式",
                    choices=["🌊 全英母语印象进化模式 (i+1)", "📚 传统双语词典模式"],
                    value="🌊 全英母语印象进化模式 (i+1)",
                    scale=2
                )
                lang_dropdown = gr.Dropdown(label="📚 学习语言", choices=list(LANG_VOICES.keys()), value="英语", scale=1)
            
            with gr.Row():
                voice_dropdown = gr.Dropdown(label="🗣️ 发音人", choices=list(LANG_VOICES["英语"].keys()), value="美式 - 女声 (Aria)")
                speed_dropdown = gr.Dropdown(label="⏱️ 语速", choices=list(SPEED_RATES.keys()), value="x1.0 (正常)")
            
            generate_btn = gr.Button("🎧 生成全文播放器与 A-B 复读面板", variant="primary")
            repeat_panel = gr.HTML(label="复读控制台")

        with gr.Column(scale=9):
            with gr.Row():
                with gr.Column(scale=3, min_width=0):
                    gr.Markdown("### 📚 划词解析区")
                with gr.Column(scale=1, min_width=0):
                    cancel_btn = gr.Button("⏹️ 紧急打断 (停止解析)", size="sm", variant="stop")

            dict_output = gr.HTML(
                value="<div style='padding: 30px 20px; color: #64748b; text-align: center; border: 1px dashed #cbd5e1; border-radius: 8px;'>👈 在左侧划取任意英文单词或句子查看全英母语印象解析。</div>"
            )
            
            with gr.Group(visible=False) as feedback_group:
                gr.Markdown("<div style='font-size:12px; color:#475569; text-align:center; margin-bottom:4px;'>⚡ <b>难度反馈与模型按需升级：</b></div>")
                with gr.Row():
                    btn_too_hard = gr.Button("🌫️ 太难/太抽象 (-25)", size="sm", variant="secondary")
                    btn_just_right = gr.Button("💡 瞬间秒懂 (+5)", size="sm", variant="primary")
                    btn_more_precise = gr.Button("🔍 求更精确 (+25)", size="sm", variant="secondary")
                btn_upgrade_pro = gr.Button("🚀 感觉不够透彻？动用高阶模型重新深度精析 (不影响默认模型)", size="sm", variant="primary")

    lang_dropdown.change(fn=lambda l: gr.update(choices=list(LANG_VOICES[l].keys()), value=list(LANG_VOICES[l].keys())[0]), inputs=lang_dropdown, outputs=voice_dropdown)
    
    save_cfg_btn.click(
        fn=save_settings_and_key,
        inputs=[api_key_box, elo_slider, model_dropdown, pro_model_dropdown],
        outputs=[status_banner, cfg_msg]
    )
    
    refresh_models_btn.click(
        fn=refresh_model_dropdowns,
        inputs=[api_key_box],
        outputs=[model_dropdown, pro_model_dropdown, cfg_msg]
    )
    
    calib_btn.click(
        fn=run_placement_calibration,
        inputs=[calib_style, calib_vocab],
        outputs=[status_banner, elo_slider, calib_result_md]
    )
    
    generate_btn.click(fn=generate_audio, inputs=[text_input, lang_dropdown, voice_dropdown, speed_dropdown], outputs=[repeat_panel])
    
    # 🌟 加入了指纹状态传递
    evt_select = text_input.select(
        fn=on_text_select, 
        inputs=[text_input, lang_dropdown, voice_dropdown, study_mode_radio, last_signature_state], 
        outputs=[dict_output, last_selected_state, last_context_state, feedback_group, status_banner, last_signature_state]
    )

    evt_hard = btn_too_hard.click(
        fn=handle_elo_feedback,
        inputs=[gr.State(-25), gr.State("hard"), last_selected_state, last_context_state, lang_dropdown, voice_dropdown],
        outputs=[dict_output, status_banner, elo_slider]
    )
    evt_good = btn_just_right.click(
        fn=handle_elo_feedback,
        inputs=[gr.State(5), gr.State("good"), last_selected_state, last_context_state, lang_dropdown, voice_dropdown],
        outputs=[dict_output, status_banner, elo_slider]
    )
    evt_precise = btn_more_precise.click(
        fn=handle_elo_feedback,
        inputs=[gr.State(25), gr.State("precise"), last_selected_state, last_context_state, lang_dropdown, voice_dropdown],
        outputs=[dict_output, status_banner, elo_slider]
    )
    
    evt_upgrade = btn_upgrade_pro.click(
        fn=handle_manual_upgrade,
        inputs=[last_selected_state, last_context_state, lang_dropdown, voice_dropdown],
        outputs=[dict_output, status_banner]
    )

    cancel_btn.click(
        fn=cancel_generation_msg,
        inputs=None,
        outputs=[dict_output],
        cancels=[evt_select, evt_hard, evt_good, evt_precise, evt_upgrade]
    )

if __name__ == "__main__":
    app.launch(inbrowser=True, head=head_js, share=False, allowed_paths=[TEMP_DIR])