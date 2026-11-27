#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sinh ảnh scene sạch (không chữ): ưu tiên `agy` (`gemini-3.8-flash-low`, `effort=low`), hết quota tự chuyển sang `codex exec` (`reasoning=low`)."""

import argparse
import json
import re
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps

QUOTA_PATTERNS = re.compile(
    r"429|resource_exhausted|exhausted your capacity|quota will reset|rate[_ ]?limit|too many requests|credit balance|overloaded|usage limit",
    re.I,
)

LOCK = threading.Lock()
EXHAUSTED: set[str] = set()


def load_log(log_path: Path) -> dict:
    if log_path.exists():
        try:
            items = json.loads(log_path.read_text(encoding="utf-8"))
            if isinstance(items, list):
                return {x["part"]: x for x in items}
        except Exception:
            pass
    return {}


def save_log(log_path: Path, log_map: dict):
    ordered = [log_map[k] for k in sorted(log_map)]
    log_path.write_text(json.dumps(ordered, ensure_ascii=False, indent=2), encoding="utf-8")


def build_qa_sheets(art_dir: Path, prod_dir: Path, total_parts: int):
    files = [art_dir / f"p{n:02d}.png" for n in range(1, total_parts + 1)]
    missing = [f.name for f in files if not f.exists()]
    assert not missing, f"Missing art files: {missing}"

    sizes = set()
    for fp in files:
        with Image.open(fp) as im:
            im.verify()
        with Image.open(fp) as im:
            w, h = im.size
            assert w > h, f"Not landscape: {fp} {w}x{h}"
            sizes.add((w, h))

    font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 18)
    sheets = []
    for b_idx, start in enumerate(range(0, len(files), 16), 1):
        group = files[start : start + 16]
        rows = (len(group) + 3) // 4
        sheet = Image.new("RGB", (1280, rows * 204), "#141922")
        d = ImageDraw.Draw(sheet)
        for i, fp in enumerate(group):
            x, y = (i % 4) * 320, (i // 4) * 204
            with Image.open(fp) as im:
                sheet.paste(ImageOps.fit(im.convert("RGB"), (320, 180)), (x, y))
            d.text((x + 8, y + 182), fp.stem.upper(), font=font, fill="white")
        out_jpg = prod_dir / f"qa_art_{b_idx:02d}.jpg"
        sheet.save(out_jpg, quality=92)
        sheets.append(str(out_jpg))
    print(f"Verified {total_parts}/{total_parts} PNGs! Dimensions: {sorted(sizes)}")
    print("QA sheets:", sheets)


def copy_fallback_from_output(combined: str, dst: Path) -> bool:
    patterns = [
        r"([A-Za-z]:\\\\[^\s'\"<>]+(?:generated_images|brain)[^\s'\"<>]+\.(?:png|jpg|jpeg))",
        r"([A-Za-z]:[\\/][^\s'\"<>]+(?:generated_images|brain)[^\s'\"<>]+\.(?:png|jpg|jpeg))",
    ]
    for pat in patterns:
        matches = re.findall(pat, combined, re.I)
        if matches:
            src_img = Path(matches[-1].replace("\\\\", "\\"))
            if src_img.exists():
                with Image.open(src_img) as im:
                    im.convert("RGB").save(dst, format="PNG")
                return True
    return False


def validate_png(dst: Path) -> tuple[int, int]:
    if not dst.exists() or dst.stat().st_size < 50000:
        raise FileNotFoundError(f"Missing or too small image: {dst}")
    with Image.open(dst) as im:
        im.verify()
    with Image.open(dst) as im:
        w, h = im.size
        if w <= h:
            raise ValueError(f"Not landscape 16:9: {w}x{h}")
        if im.format != "PNG":
            im.convert("RGB").save(dst, format="PNG")
    return w, h


def run_agy_image(work_dir: Path, dst: Path, part_obj: dict, ref_image: Path | None, style_only: bool, agy_model: str, effort: str) -> tuple[bool, str, bool]:
    n = part_obj["part"]
    ref_clause = ""
    if ref_image and ref_image.exists():
        if style_only:
            ref_clause = f"Reference image `{ref_image}` is for 2.5D realistic donghua STYLE and lighting ONLY (do NOT copy its character face, clothes, or setting).\n"
        else:
            ref_clause = f"Reference image `{ref_image}` is for recurring protagonist FACE and 2.5D realistic donghua STYLE consistency ONLY (adapt age/clothes/setting strictly to the prompt).\n"

    prompt = (
        f"Invoke the `image-generator` subagent ONCE to generate ONE 16:9 widescreen illustration for Part {n:02d}. "
        f"{ref_clause}"
        f"Exact image prompt: {part_obj['image_prompt']} "
        f"After `image-generator` replies with the generated file path, convert/save it as PNG to `{dst}` (if you cannot write `{dst}`, print the exact full source file path). "
        f"If `image-generator` fails with 429 or quota/capacity error, DO NOT retry — immediately reply with the exact error."
    )
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
    res = subprocess.run(
        cmd,
        stdin=subprocess.DEVNULL,
        cwd=str(work_dir),
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=240,
    )
    combined = (res.stdout or "") + "\n" + (res.stderr or "")
    if QUOTA_PATTERNS.search(combined):
        return False, combined[-400:].strip(), True
    if not dst.exists() or dst.stat().st_size < 50000:
        copy_fallback_from_output(combined, dst)
    try:
        w, h = validate_png(dst)
        return True, f"{w}x{h}", False
    except Exception as exc:
        return False, f"Exit={res.returncode}; {exc}; tail={combined[-300:].strip()}", False


def run_codex_image(work_dir: Path, dst: Path, msg_file: Path, part_obj: dict, ref_image: Path | None, style_only: bool) -> tuple[bool, str, bool]:
    n = part_obj["part"]
    ref_clause = ""
    if ref_image and ref_image.exists():
        ref_rel = ref_image.relative_to(work_dir).as_posix() if ref_image.is_relative_to(work_dir) else str(ref_image)
        if style_only:
            ref_clause = f"Use the attached image `{ref_rel}` ONLY as 2.5D semi-realistic donghua rendering style and lighting reference (do NOT copy its character face, clothes, or setting).\n"
        else:
            ref_clause = f"Use the attached image `{ref_rel}` ONLY as face and 2.5D semi-realistic donghua rendering style consistency reference for the recurring protagonist (adapt age/clothes/setting strictly to the prompt below).\n"

    prompt = f"""Use your built-in `image_gen` tool ONCE to generate a 16:9 widescreen cinematic scene illustration for Part {n:02d}.
{ref_clause}Prompt for `image_gen`:
{part_obj['image_prompt']}

CRITICAL:
1. Ensure there is ZERO text, letters, Chinese characters, numbers, signage, or watermarks anywhere in the image.
2. Keep the left 35-40% of the frame naturally darker and uncluttered, and the main subject(s) in the right 60-65%.
3. Copy the generated PNG directly to `{dst}` and reply with the generated source path and `{dst}`."""

    cmd = [
        "codex", "exec",
        "--skip-git-repo-check",
        "--ephemeral",
        "-s", "workspace-write",
        "-C", str(work_dir),
        "-c", 'model_reasoning_effort="low"',
    ]
    if ref_image and ref_image.exists():
        cmd.extend(["-i", str(ref_image)])
    cmd.extend(["-o", str(msg_file), "-"])

    res = subprocess.run(
        cmd,
        input=prompt,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=240,
    )
    combined = (res.stdout or "") + "\n" + (res.stderr or "")
    if msg_file.exists():
        combined += "\n" + msg_file.read_text(encoding="utf-8", errors="replace")
    if QUOTA_PATTERNS.search(combined):
        return False, combined[-400:].strip(), True
    if not dst.exists() or dst.stat().st_size < 50000:
        copy_fallback_from_output(combined, dst)
    try:
        w, h = validate_png(dst)
        return True, f"{w}x{h}", False
    except Exception as exc:
        return False, f"Exit={res.returncode}; {exc}; tail={combined[-300:].strip()}", False


def generate_one(
    work_dir: Path,
    art_dir: Path,
    msg_dir: Path,
    part_obj: dict,
    ref_image: Path | None,
    style_only: bool,
    providers: list[str],
    agy_model: str,
    effort: str,
) -> tuple[int, bool, str, str]:
    n = part_obj["part"]
    dst = art_dir / f"p{n:02d}.png"
    msg_file = msg_dir / f"p{n:02d}.txt"
    last_err = "No provider available"

    for prov in providers:
        with LOCK:
            if prov in EXHAUSTED:
                continue
        for attempt in range(1, 3):
            try:
                if prov == "agy":
                    ok, info, hit_quota = run_agy_image(work_dir, dst, part_obj, ref_image, style_only, agy_model, effort)
                elif prov == "codex":
                    ok, info, hit_quota = run_codex_image(work_dir, dst, msg_file, part_obj, ref_image, style_only)
                else:
                    raise ValueError(f"Unsupported image provider: {prov}")

                if hit_quota:
                    with LOCK:
                        EXHAUSTED.add(prov)
                    print(f"[QUOTA] {prov} image quota exhausted -> falling back (part p{n:02d})", flush=True)
                    last_err = f"{prov} quota exhausted"
                    break
                if ok:
                    return n, True, prov, f"{info} (attempt {attempt})"
                last_err = f"{prov} attempt {attempt}: {info}"
            except Exception as exc:
                last_err = f"{prov} attempt {attempt}: {exc}"

    return n, False, "none", last_err


def main():
    parser = argparse.ArgumentParser(description="Sinh ảnh scene sạch (không chữ): ưu tiên agy, hết quota chuyển codex")
    parser.add_argument("--work-dir", required=True, help="Thư mục dự án video")
    parser.add_argument("--parts", nargs="*", type=int, help="Danh sách số phần cần sinh")
    parser.add_argument("--force", action="store_true", help="Ghi đè ảnh PNG đã có")
    parser.add_argument("--workers", type=int, default=4, help="Số luồng song song (mặc định: 4)")
    parser.add_argument("--ref", type=str, default=None, help="Ảnh tham chiếu (mặc định art/p01.png)")
    parser.add_argument("--style-only", action="store_true", help="Chỉ tham chiếu phong cách vẽ")
    parser.add_argument("--qa-only", action="store_true", help="Chỉ kiểm tra ảnh hiện có và xuất bảng QA")
    parser.add_argument("--providers", default="agy,codex", help="Thứ tự CLI sinh ảnh (mặc định: agy,codex)")
    parser.add_argument("--agy-model", default="gemini-3.8-flash-low", help="Model cho agy (mặc định: gemini-3.8-flash-low)")
    parser.add_argument("--effort", default="low", help="Mức effort cho agy (mặc định: low)")
    args = parser.parse_args()

    work_dir = Path(args.work_dir).resolve()
    art_dir = work_dir / "art"
    prod_dir = work_dir / "production"
    msg_dir = prod_dir / "cli_logs"
    log_path = prod_dir / "generation_log.json"
    art_dir.mkdir(parents=True, exist_ok=True)
    msg_dir.mkdir(parents=True, exist_ok=True)

    manifest = json.loads((prod_dir / "parts_manifest.json").read_text(encoding="utf-8"))
    by_part = {p["part"]: p for p in manifest}
    total_parts = len(manifest)

    if args.qa_only:
        build_qa_sheets(art_dir, prod_dir, total_parts)
        return

    default_ref = art_dir / "p01.png"
    ref_image = Path(args.ref).resolve() if args.ref else (default_ref if default_ref.exists() else None)
    providers = [p.strip().lower() for p in args.providers.split(",") if p.strip()]

    if args.parts:
        targets = [n for n in args.parts if args.force or not (art_dir / f"p{n:02d}.png").exists()]
    else:
        targets = [n for n in range(1, total_parts + 1) if args.force or not (art_dir / f"p{n:02d}.png").exists()]

    print(f"Queued {len(targets)} parts | providers={providers} | agy={args.agy_model} ({args.effort}) | ref={ref_image.name if ref_image else 'none'}")
    if targets:
        log_map = load_log(log_path)
        ok_list, fail_list = [], []
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            futs = {
                ex.submit(generate_one, work_dir, art_dir, msg_dir, by_part[n], ref_image, args.style_only, providers, args.agy_model, args.effort): n
                for n in targets
            }
            for fut in as_completed(futs):
                n, ok, used_prov, info = fut.result()
                if ok:
                    ok_list.append(n)
                    with LOCK:
                        log_map[n] = {"part": n, "provider": used_prov, "saved": f"art/p{n:02d}.png", "info": info}
                        save_log(log_path, log_map)
                    print(f"[OK] p{n:02d} via {used_prov}: {info}", flush=True)
                else:
                    fail_list.append((n, info))
                    print(f"[FAIL] p{n:02d}: {info}", flush=True)
        print(f"Finished batch: {len(ok_list)} OK, {len(fail_list)} FAILED.")
        if fail_list:
            raise RuntimeError(f"Failed parts: {[x[0] for x in fail_list]}")

    if all((art_dir / f"p{n:02d}.png").exists() for n in range(1, total_parts + 1)):
        build_qa_sheets(art_dir, prod_dir, total_parts)


if __name__ == "__main__":
    main()
