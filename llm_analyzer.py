import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

from config import LLM_ENDPOINT, LLM_MODEL


RAW_DIR = Path("data/raw")
ANALYSIS_DIR = Path("data/analysis")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Analyze exported Telegram comments with an LLM endpoint.")
    parser.add_argument("file", help="JSON file name from data/raw or a direct path to a JSON file.")
    parser.add_argument("--limit", type=int, default=None, help="Analyze only first N posts.")
    return parser.parse_args(argv)


def resolve_input_path(value):
    path = Path(value)

    if path.exists():
        return path

    raw_path = RAW_DIR / value

    if raw_path.exists():
        return raw_path

    raise FileNotFoundError(f"File not found: {value}. Checked current path and {RAW_DIR}.")


def build_output_path(input_path):
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    return ANALYSIS_DIR / f"analysis_{input_path.name}"


def build_prompt(post):
    comments = post.get("comments") or []
    comments_payload = []

    for comment in comments:
        user = comment.get("user") or {}
        comments_payload.append({
            "comment_id": comment.get("comment_id"),
            "comment_date": comment.get("comment_date"),
            "comment_text": comment.get("comment_text"),
            "reply_to_msg_id": comment.get("reply_to_msg_id"),
            "user_id": user.get("user_id"),
            "username": user.get("username"),
            "first_name": user.get("first_name"),
            "last_name": user.get("last_name"),
            "reactions": comment.get("comment_reactions", []),
        })

    payload = {
        "post": {
            "post_id": post.get("post_id"),
            "post_date": post.get("post_date"),
            "post_text": post.get("post_text"),
            "post_views": post.get("post_views"),
            "post_forwards": post.get("post_forwards"),
            "post_reactions": post.get("post_reactions", []),
        },
        "comments": comments_payload,
    }

    return (
        "Проанализируй Telegram-пост и комментарии к нему. "
        "Верни краткий структурированный анализ на русском языке: "
        "1) главная тема поста, 2) тональность обсуждения, 3) основные вопросы/темы в комментариях, "
        "4) самые активные или заметные пользователи, 5) риски/негатив, 6) краткий вывод.\n\n"
        f"Данные:\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )


def call_llm(prompt):
    request_payload = {
        "model": LLM_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "Ты аналитик Telegram-комментариев. Отвечай конкретно и структурированно.",
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        "temperature": 0.2,
    }

    request = urllib.request.Request(
        LLM_ENDPOINT,
        data=json.dumps(request_payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            response_text = response.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        details = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"LLM endpoint returned HTTP {e.code}: {details}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Cannot connect to LLM endpoint: {e.reason}") from e

    try:
        response_json = json.loads(response_text)
    except json.JSONDecodeError:
        return {
            "analysis": response_text,
            "raw_response": response_text,
        }

    return {
        "analysis": extract_analysis_text(response_json),
        "raw_response": response_json,
    }


def extract_analysis_text(response_json):
    choices = response_json.get("choices")

    if choices:
        message = choices[0].get("message") or {}
        content = message.get("content")

        if content:
            return content

        text = choices[0].get("text")

        if text:
            return text

    for key in ("analysis", "text", "content", "response", "output"):
        value = response_json.get(key)

        if isinstance(value, str):
            return value

    return json.dumps(response_json, ensure_ascii=False, indent=2)


def analyze_posts(posts, limit=None):
    selected_posts = posts[:limit] if limit else posts
    result = []

    for index, post in enumerate(selected_posts, start=1):
        post_id = post.get("post_id")
        comments_count = len(post.get("comments") or [])
        print(f"Analyzing post {post_id} ({index}/{len(selected_posts)}), comments: {comments_count}")

        prompt = build_prompt(post)
        llm_result = call_llm(prompt)

        result.append({
            "post_id": post_id,
            "post_date": post.get("post_date"),
            "comments_count": comments_count,
            "analysis": llm_result["analysis"],
            "raw_response": llm_result["raw_response"],
        })

    return result


def main(args=None):
    if args is None:
        args = parse_args()
    input_path = resolve_input_path(args.file)
    output_path = build_output_path(input_path)

    with input_path.open("r", encoding="utf-8") as f:
        posts = json.load(f)

    if not isinstance(posts, list):
        raise RuntimeError("Input JSON must be a list of posts.")

    analyses = analyze_posts(posts, args.limit)
    output = {
        "source_file": str(input_path),
        "llm_endpoint": LLM_ENDPOINT,
        "llm_model": LLM_MODEL,
        "posts_analyzed": len(analyses),
        "analyses": analyses,
    }

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"Done. Analysis saved to {output_path}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
