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
PROMPTS_DIR = Path("prompts")
DEFAULT_PROMPT_LANGUAGE = "ru"
PROMPT_FILES = {
    "ru": "llm_ru.json",
    "en": "llm_en.json",
    "zh": "llm_zh.json",
}


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Analyze exported Telegram comments with an LLM endpoint.")
    parser.add_argument("file", help="JSON file name from data/raw or a direct path to a JSON file.")
    parser.add_argument("--limit", type=int, default=None, help="Analyze only first N posts.")
    parser.add_argument(
        "--language",
        choices=tuple(PROMPT_FILES),
        default=None,
        help="Prompt language shortcut: ru, en, or zh. Default: ru.",
    )
    parser.add_argument(
        "--prompt-file",
        default=None,
        help="Path to a prompt JSON file. Overrides --language.",
    )
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


def resolve_prompt_path(prompt_file=None, language=None):
    if prompt_file:
        path = Path(prompt_file)

        if path.exists():
            return path

        prompts_path = PROMPTS_DIR / prompt_file

        if prompts_path.exists():
            return prompts_path

        raise FileNotFoundError(f"Prompt file not found: {prompt_file}. Checked current path and {PROMPTS_DIR}.")

    prompt_language = language or DEFAULT_PROMPT_LANGUAGE
    return PROMPTS_DIR / PROMPT_FILES[prompt_language]


def load_prompt_config(path):
    with path.open("r", encoding="utf-8") as f:
        config = json.load(f)

    if not isinstance(config, dict):
        raise RuntimeError(f"Prompt file must contain a JSON object: {path}")

    for key in ("system", "user_template"):
        if not isinstance(config.get(key), str) or not config[key].strip():
            raise RuntimeError(f"Prompt file must contain non-empty string field '{key}': {path}")

    if "{data}" not in config["user_template"]:
        raise RuntimeError(f"Prompt user_template must contain '{{data}}' placeholder: {path}")

    return config


def write_json_atomic(data, path):
    tmp_path = path.with_name(f"{path.name}.tmp")

    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    os.replace(tmp_path, path)


def build_analysis_output(input_path, analyses, prompt_path=None, prompt_config=None):
    return {
        "source_file": str(input_path),
        "prompt_file": str(prompt_path) if prompt_path else None,
        "prompt_language": (prompt_config or {}).get("language"),
        "llm_endpoint": LLM_ENDPOINT,
        "llm_model": LLM_MODEL,
        "posts_analyzed": len(analyses),
        "analyses": analyses,
    }


def build_prompt(post, prompt_config):
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

    data = json.dumps(payload, ensure_ascii=False, indent=2)
    return prompt_config["user_template"].format(data=data)


def call_llm(prompt, system_prompt):
    request_payload = {
        "model": LLM_MODEL,
        "messages": [
            {
                "role": "system",
                "content": system_prompt,
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


def analyze_posts(posts, limit=None, input_path=None, output_path=None, prompt_path=None, prompt_config=None):
    selected_posts = posts[:limit] if limit else posts
    result = []
    active_prompt_config = prompt_config or load_prompt_config(prompt_path or resolve_prompt_path())

    for index, post in enumerate(selected_posts, start=1):
        if not isinstance(post, dict):
            item = {
                "post_id": None,
                "post_date": None,
                "comments_count": 0,
                "analysis": None,
                "raw_response": None,
                "analysis_error": f"Post item at index {index} must be an object.",
            }
            result.append(item)

            if input_path and output_path:
                write_json_atomic(
                    build_analysis_output(input_path, result, prompt_path, active_prompt_config),
                    output_path,
                )

            continue

        post_id = post.get("post_id")
        comments_count = len(post.get("comments") or [])
        print(f"Analyzing post {post_id} ({index}/{len(selected_posts)}), comments: {comments_count}")

        try:
            prompt = build_prompt(post, active_prompt_config)
            llm_result = call_llm(prompt, active_prompt_config["system"])
            analysis = llm_result["analysis"]
            raw_response = llm_result["raw_response"]
            error = None
        except Exception as e:
            analysis = None
            raw_response = None
            error = str(e)
            print(f"Error analyzing post {post_id}: {e}", file=sys.stderr)

        item = {
            "post_id": post_id,
            "post_date": post.get("post_date"),
            "comments_count": comments_count,
            "analysis": analysis,
            "raw_response": raw_response,
        }

        if error:
            item["analysis_error"] = error

        result.append(item)

        if input_path and output_path:
            write_json_atomic(
                build_analysis_output(input_path, result, prompt_path, active_prompt_config),
                output_path,
            )

    return result


def main(args=None):
    if args is None:
        args = parse_args()
    input_path = resolve_input_path(args.file)
    output_path = build_output_path(input_path)
    prompt_path = resolve_prompt_path(args.prompt_file, args.language)
    prompt_config = load_prompt_config(prompt_path)

    with input_path.open("r", encoding="utf-8") as f:
        posts = json.load(f)

    if not isinstance(posts, list):
        raise RuntimeError("Input JSON must be a list of posts.")

    analyses = analyze_posts(posts, args.limit, input_path, output_path, prompt_path, prompt_config)
    output = build_analysis_output(input_path, analyses, prompt_path, prompt_config)
    write_json_atomic(output, output_path)

    print(f"Done. Analysis saved to {output_path}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
