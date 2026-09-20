"""
自动发图模块
═══════════════════════════════════════════════════════════════
流程:
  1. LLM 同时生成: (a) 推文文案 (b) 配图描述 (image prompt)
  2. 用 image model (OpenAI dall-e-3 / 兼容 SD) 生图
  3. 下载图片到本地
  4. twikit.upload_media() 上传 + create_tweet(media_ids=...) 发推

支持 3 种生图 backend:
  - OpenAI DALL-E 3 (贵, $0.04/张)
  - 任何 OpenAI 兼容的图 API (硅基流动 / Together / 阿里 / etc)
  - 跳过 (只发文案)

依赖: pip install httpx
"""

import asyncio
import os
import re
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()

MEDIA_DIR = Path("media")
MEDIA_DIR.mkdir(exist_ok=True)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  配置
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# 生图 API (可选): 用 OpenAI 还是别的
IMAGE_PROVIDER = os.getenv("IMAGE_PROVIDER", "openai")  # openai / none
IMAGE_API_KEY  = os.getenv("IMAGE_API_KEY", os.getenv("LLM_API_KEY", ""))
IMAGE_BASE_URL = os.getenv("IMAGE_BASE_URL", "https://api.openai.com/v1")
IMAGE_MODEL    = os.getenv("IMAGE_MODEL", "dall-e-3")    # dall-e-3 / dall-e-2 / cogview-3 / etc
IMAGE_SIZE     = os.getenv("IMAGE_SIZE", "1024x1024")    # 1024x1024 / 1792x1024 / 1024x1792


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  LLM 同时生成文案 + 配图描述
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TEXT_AND_IMAGE_PROMPT = """你是 {persona}

写一条推文, 关于主题: {topic}

要求:
1. [TWEET] 后面写推文本身 (中文, 100-200 字, 适合 Twitter)
2. [IMAGE_PROMPT] 后面写配图描述 (英文, 详细, 适合 AI 生图模型)
   - 描述构图、色调、主体、背景、光线
   - 50-150 词
   - 不要含文字

格式:
[TWEET]
<推文内容>

[IMAGE_PROMPT]
<英文配图描述>
"""


async def generate_text_and_image_prompt(llm, topic: str, persona: str = "一个分享 AI 工具的产品经理") -> tuple[str, str]:
    """LLM 同时产出推文 + 配图描述"""
    prompt = TEXT_AND_IMAGE_PROMPT.format(persona=persona, topic=topic)
    resp = await llm.chat.completions.create(
        model=os.getenv("LLM_MODEL", "deepseek-chat"),
        messages=[{"role": "user", "content": prompt}],
        temperature=0.85,
        max_tokens=500,
    )
    text = resp.choices[0].message.content

    # 解析
    tweet_match = re.search(r"\[TWEET\]\s*\n?(.+?)(?=\[IMAGE_PROMPT\]|$)", text, re.DOTALL)
    img_match = re.search(r"\[IMAGE_PROMPT\]\s*\n?(.+?)$", text, re.DOTALL)

    tweet = tweet_match.group(1).strip() if tweet_match else text[:200].strip()
    img_prompt = img_match.group(1).strip() if img_match else ""

    return tweet, img_prompt


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  生图 (OpenAI / 兼容 API)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def generate_image(prompt: str) -> Path | None:
    """生图, 保存到 media/, 返回本地路径"""
    if IMAGE_PROVIDER == "none":
        return None
    if not IMAGE_API_KEY:
        print("   ⚠️ IMAGE_API_KEY 没设置, 跳过生图")
        return None

    client = AsyncOpenAI(api_key=IMAGE_API_KEY, base_url=IMAGE_BASE_URL)

    try:
        print(f"   🎨 生图中: {prompt[:60]}...")
        resp = await client.images.generate(
            model=IMAGE_MODEL,
            prompt=prompt,
            size=IMAGE_SIZE,
            n=1,
        )
        image_url = resp.data[0].url

        # 下载
        import httpx
        async with httpx.AsyncClient() as h:
            r = await h.get(image_url, timeout=60)
            r.raise_for_status()

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = MEDIA_DIR / f"gen_{ts}.png"
        filename.write_bytes(r.content)
        print(f"   ✅ 图片已保存: {filename}")
        return filename

    except Exception as e:
        print(f"   ❌ 生图失败: {e}")
        return None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  组合使用 (供 bot.py 调用)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def generate_post_with_image(llm, topic: str, persona: str, dry_run: bool = True) -> dict:
    """生成完整的一条 post (文案 + 配图)
    返回:
      {
        "text": "推文内容",
        "image_path": Path 或 None,
        "image_prompt": "生图 prompt",
      }
    """
    tweet, img_prompt = await generate_text_and_image_prompt(llm, topic, persona)
    image_path = None
    if img_prompt:
        image_path = await generate_image(img_prompt)

    return {
        "text": tweet,
        "image_path": image_path,
        "image_prompt": img_prompt,
    }