#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sinh kịch bản JSON từng phần (summaries/p01.json..pNN.json) qua CLI tiết kiệm token: ưu tiên `agy`, hết quota tự chuyển sang `claude`."""

import argparse
import json
import math
import re
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

QUOTA_PATTERNS = re.compile(
    r"429|resource_exhausted|exhausted your capacity|quota will reset|rate[_ ]?limit|too many requests|credit balance|overloaded|usage limit",
    re.I,
)

LOCK = threading.Lock()
EXHAUSTED: set[str] = set()


def extract_json_array(raw: str) -> list[dict]:
    """Tách mảng JSON từ stdout (kể cả khi được bọc trong ```json ... ```)."""
    cleaned = raw.strip()
    fence = re.search(r"```(?:json)?\s*(\[[\s\S]*\])\s*```", cleaned)
    if fence:
        cleaned = fence.group(1)
    else:
        start = cleaned.find("[")
        end = cleaned.rfind("]")
        if start != -1 and end > start:
            cleaned = cleaned[start : end + 1]
    data = json.loads(cleaned)
    if not isinstance(data, list):
        raise ValueError("Expected JSON array")
    return data


def build_prompt(work_dir: Path, part_nums: list[int], novel_title: str, protagonist_brief: str, chapters_per_part: int, total_chapters: int) -> str:
    digests = [str((work_dir / "production" / "digests" / f"p{n:02d}.txt").resolve()) for n in part_nums]
    digest_list = "\n".join(f"- {d}" for d in digests)
    return f"""Read these {len(part_nums)} digest files for "{novel_title}":
{digest_list}

Return ONLY a valid JSON array of {len(part_nums)} objects (parts {part_nums[0]}..{part_nums[-1]}; total chapters={total_chapters}, {chapters_per_part}/part). Do NOT write files or add prose outside the JSON array.

Each object MUST have exact keys:
- "part": integer
- "chapter_start": integer
- "chapter_end": integer
- "arc_stage": short Vietnamese role/stage label
- "summary": 3-5 cohesive Vietnamese sentences faithfully summarizing those chapters
- "scene_title": concise Vietnamese scene title (5-10 words)
- "visual_scene": detailed Vietnamese description of the single most iconic scene
- "camera_motion": cycle through "pushIn", "zoomOut", "panLeft", "panRight", "driftUp", "driftDown"
- "duration_seconds": 3.5
- "thumbnail_lines": 2 or 3 short punchy UPPERCASE Vietnamese lines (<=20 chars/line); NO character names, NO chapter numbers, NO story title
- "image_prompt": detailed English prompt for a 16:9 realistic 3D donghua semi-realistic 2.5D illustration. Protagonist consistency: {protagonist_brief}. Main subject(s) in RIGHT 60-65%, LEFT 35-40% naturally darker & uncluttered, warm amber rim light + cool teal shadows, rich textures. End with exact clause: STRICTLY NO text, NO letters, NO words, NO Chinese characters, NO Vietnamese characters, NO numbers, NO readable signage, NO logos, NO watermarks, NO UI badges, NO collage."""


def run_provider(provider: str, work_dir: Path, prompt: str, agy_model: str, claude_model: str, effort: str) -> tuple[bool, str, bool]:
    """Chạy 1 lượt CLI. Trả về (ok, output_or_error, hit_quota)."""
    if provider == "agy":
        cmd = [
            "agy",
            "--model", agy_model,
            "--dangerously-skip-permissions",
            "--disable-slash-commands",
            "--add-dir", str(work_dir),
        ]
        if not re.search(r"-(low|medium|high|xhigh|max)$", agy_model):
            cmd.extend(["--effort", effort])
        cmd.extend(["-p", prompt])
    elif provider == "claude":
        cmd = [
            "claude",
            "-p", prompt,
            "--model", claude_model,
            "--effort", effort,
            "--no-session-persistence",
            "--dangerously-skip-permissions",
            "--add-dir", str(work_dir),
        ]
    else:
        raise ValueError(f"Unsupported provider: {provider}")

    res = subprocess.run(
        cmd,
        stdin=subprocess.DEVNULL,
        cwd=str(work_dir),
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=300,
    )
    combined = (res.stdout or "") + "\n" + (res.stderr or "")
    if QUOTA_PATTERNS.search(combined):
        return False, combined[-500:].strip(), True
    if res.returncode != 0:
        return False, f"Exit={res.returncode}: {combined[-500:].strip()}", False
    return True, res.stdout or "", False


def process_chunk(
    chunk: list[int],
    work_dir: Path,
    summaries_dir: Path,
    novel_title: str,
    protagonist_brief: str,
    chapters_per_part: int,
    total_chapters: int,
    providers: list[str],
    agy_model: str,
    claude_model: str,
    effort: str,
) -> tuple[list[int], str]:
    prompt = build_prompt(work_dir, chunk, novel_title, protagonist_brief, chapters_per_part, total_chapters)
    last_err = "No providers available"

    for prov in providers:
        with LOCK:
            if prov in EXHAUSTED:
                continue
        for attempt in range(1, 3):
            try:
                ok, payload, hit_quota = run_provider(prov, work_dir, prompt, agy_model, claude_model, effort)
                if hit_quota:
                    with LOCK:
                        EXHAUSTED.add(prov)
                    print(f"[QUOTA] {prov} exhausted -> switching provider (chunk {chunk[0]:02d}-{chunk[-1]:02d})", flush=True)
                    last_err = f"{prov} quota exhausted"
                    break
                if not ok:
                    last_err = payload
                    continue

                items = extract_json_array(payload)
                by_p = {int(it["part"]): it for it in items}
                missing = [n for n in chunk if n not in by_p]
                if missing:
                    last_err = f"{prov} missing parts {missing} in JSON output"
                    continue

                for n in chunk:
                    obj = by_p[n]
                    (summaries_dir / f"p{n:02d}.json").write_text(
                        json.dumps(obj, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )
                return chunk, prov
            except Exception as exc:
                last_err = f"{prov} attempt {attempt}: {exc}"

    raise RuntimeError(f"Chunk {chunk} failed: {last_err}")


def main():
    parser = argparse.ArgumentParser(description="Sinh JSON kịch bản theo batch qua agy (ưu tiên) -> claude (dự phòng)")
    parser.add_argument("--work-dir", required=True, help="Thư mục dự án video")
    parser.add_argument("--novel-title", required=True, help="Tên bộ truyện")
    parser.add_argument("--source-chapters", type=int, required=True, help="Tổng số chương nguồn")
    parser.add_argument("--chapters-per-part", type=int, required=True, help="Số chương mỗi phần")
    parser.add_argument("--protagonist-brief", required=True, help="Mô tả ngắn tạo hình nhân vật chính để đồng nhất prompt")
    parser.add_argument("--batch-size", type=int, default=5, help="Số phần mỗi lượt gọi CLI (mặc định: 5)")
    parser.add_argument("--workers", type=int, default=3, help="Số luồng song song (mặc định: 3)")
    parser.add_argument("--providers", default="agy,claude", help="Thứ tự CLI (mặc định: agy,claude)")
    parser.add_argument("--agy-model", default="gemini-3.8-flash-medium", help="Model cho agy (mặc định: gemini-3.8-flash-medium)")
    parser.add_argument("--claude-model", default="sonnet", help="Model cho claude (mặc định: sonnet)")
    parser.add_argument("--effort", default="low", help="Mức effort (mặc định: low để tiết kiệm token)")
    parser.add_argument("--force", action="store_true", help="Ghi đè các summaries/pXX.json đã có")
    args = parser.parse_args()

    work_dir = Path(args.work_dir).resolve()
    summaries_dir = work_dir / "production" / "summaries"
    summaries_dir.mkdir(parents=True, exist_ok=True)

    total_parts = math.ceil(args.source_chapters / args.chapters_per_part)
    todo = [n for n in range(1, total_parts + 1) if args.force or not (summaries_dir / f"p{n:02d}.json").exists()]
    print(f"Queued {len(todo)}/{total_parts} summary parts (providers={args.providers}, agy={args.agy_model}, claude={args.claude_model}, effort={args.effort})")
    if not todo:
        return

    chunks = [todo[i : i + args.batch_size] for i in range(0, len(todo), args.batch_size)]
    providers = [p.strip().lower() for p in args.providers.split(",") if p.strip()]

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {
            ex.submit(
                process_chunk,
                ch,
                work_dir,
                summaries_dir,
                args.novel_title,
                args.protagonist_brief,
                args.chapters_per_part,
                args.source_chapters,
                providers,
                args.agy_model,
                args.claude_model,
                args.effort,
            ): ch
            for ch in chunks
        }
        for fut in as_completed(futs):
            done_chunk, used_prov = fut.result()
            print(f"[OK] Parts {done_chunk[0]:02d}-{done_chunk[-1]:02d} via {used_prov}", flush=True)


if __name__ == "__main__":
    main()
