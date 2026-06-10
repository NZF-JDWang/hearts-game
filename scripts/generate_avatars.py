"""Generate 10 themed character avatars for the Hearts roster via Grok Imagine.

Output: assets/avatars/avatar_<01..10>.png  (128x128 RGBA)
        assets/avatars/_manifest.json  (id, prompt, file, sha256)

Idempotent: skips generation if a matching file already exists (by sha of prompt).
Re-running the script picks up any new characters.

Usage:
    PYTHONPATH=src python3 scripts/generate_avatars.py
    PYTHONPATH=src python3 scripts/generate_avatars.py --force  # regenerate all
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, List

from PIL import Image

# xAI config (reads from svens's profile .env, like the rest of the lab)
ENV_PATH = Path("/home/jd/.hermes/profiles/sven/.env")
if ENV_PATH.is_file():
    for line in ENV_PATH.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

XAI_API_KEY = os.environ.get("XAI_API_KEY", "")
if not XAI_API_KEY:
    print("ERROR: XAI_API_KEY not set", file=sys.stderr)
    sys.exit(1)

API_URL = "https://api.x.ai/v1/images/generations"
MODEL = "grok-imagine-image-quality"
AVATAR_SIZE = 128  # final size in px (square)

# 10 characters. id, name, personality, theme, prompt.
CHARACTERS: List[Dict[str, str]] = [
    {
        "id": "vamp_countess",
        "name": "Countess Mara",
        "personality": "aggressive",
        "prompt": (
            "portrait of a vampire countess, head and shoulders, "
            "dark red and black formal high-collared cape, pale skin, "
            "sharp elegant features, dark hair in a vintage updo with a red rose, "
            "deep crimson lips, hint of fangs, "
            "solid deep purple background with subtle vignette, no text no logos, "
            "painterly digital art style, dramatic cinematic lighting"
        ),
    },
    {
        "id": "mad_hatter",
        "name": "Thaddeus Brass",
        "personality": "balanced",
        "prompt": (
            "portrait of a steampunk inventor, head and shoulders, "
            "brass goggles pushed up on forehead, top hat with small gears, "
            "leather apron over waistcoat, copper pocket watch chain, "
            "muted sepia and brass color palette, "
            "solid warm brown background, no text no logos, "
            "painterly digital art style"
        ),
    },
    {
        "id": "jazz_singer",
        "name": "Lina Holloway",
        "personality": "conservative",
        "prompt": (
            "portrait of a 1920s jazz singer, head and shoulders, "
            "feather headband, pearl necklace, satin dress strap visible, "
            "soft golden sepia lighting, contemplative expression, "
            "solid smoky gold background, no text no logos, "
            "painterly digital art style, art deco poster feel"
        ),
    },
    {
        "id": "hacker",
        "name": "Zero",
        "personality": "aggressive",
        "prompt": (
            "portrait of a cyberpunk hacker, head and shoulders, "
            "hooded jacket, LED strip reflecting cyan light on face, "
            "terminal-green eyeshadow smudge, undercut hair, "
            "subtle data-mesh reflection in pupils, "
            "solid near-black background with a single cyan rim light, "
            "no text no logos, painterly digital art style"
        ),
    },
    {
        "id": "samurai",
        "name": "Reza Hayashi",
        "personality": "balanced",
        "prompt": (
            "portrait of a female samurai, head and shoulders, "
            "white and crimson kimono, hair tied high with a kanzashi pin, "
            "calm focused expression, single cherry blossom petal falling, "
            "solid soft white background with a faint red accent, no text no logos, "
            "painterly digital art style, sumi-e inspired"
        ),
    },
    {
        "id": "disco_queen",
        "name": "Vee Stardust",
        "personality": "aggressive",
        "prompt": (
            "portrait of a 1970s disco queen, head and shoulders, "
            "big halo hair, sequined headband, shimmery eyeshadow, "
            "huge sparkling smile, mirror-ball light reflections on skin, "
            "solid deep purple background with a few sparkle bokeh dots, "
            "no text no logos, painterly digital art style, glamorous"
        ),
    },
    {
        "id": "mystic",
        "name": "Wren of the Hollow",
        "personality": "conservative",
        "prompt": (
            "portrait of a forest mystic, head and shoulders, "
            "moss-green hooded cloak, white face paint with subtle rune marks, "
            "soft glowing candle in foreground out of focus, "
            "deep emerald and gold color palette, "
            "solid dark forest-green background, no text no logos, "
            "painterly digital art style, ethereal"
        ),
    },
    {
        "id": "pirate",
        "name": "Captain Saul",
        "personality": "aggressive",
        "prompt": (
            "portrait of a weathered pirate captain, head and shoulders, "
            "tricorn hat with a tarnished brass buckle, salt-and-pepper beard, "
            "leather coat collar turned up, gold hoop earring, "
            "scar across one cheek, squinty confident eye, "
            "solid muted ocean-blue background, no text no logos, "
            "painterly digital art style, oceanic lighting"
        ),
    },
    {
        "id": "mad_scientist",
        "name": "Dr. Indy Vex",
        "personality": "balanced",
        "prompt": (
            "portrait of a mad scientist, head and shoulders, "
            "white lab coat with a scorch mark, wild Einstein hair, "
            "oversized brass goggles, a faint green glow from a vial near collar, "
            "mischievous grin, "
            "solid dark teal background with a green rim light, no text no logos, "
            "painterly digital art style"
        ),
    },
    {
        "id": "grandmaster",
        "name": "Aurelia Voss",
        "personality": "conservative",
        "prompt": (
            "portrait of a chess grandmaster, head and shoulders, "
            "sharp charcoal turtleneck, hair pulled back tight, "
            "calculating grey eyes, faint chess-piece shadow on cheek, "
            "high-contrast monochrome with one red accent pin on collar, "
            "solid mid-grey background, no text no logos, "
            "painterly digital art style, minimal"
        ),
    },
]


def call_grok(prompt: str, retries: int = 3) -> bytes:
    """Hit xAI /v1/images/generations and return raw PNG bytes."""
    body = json.dumps({
        "model": MODEL,
        "prompt": prompt,
        "n": 1,
        "response_format": "b64_json",
        "aspect_ratio": "1:1",
        "resolution": "2k",
    }).encode()
    req = urllib.request.Request(
        API_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {XAI_API_KEY}",
            "Content-Type": "application/json",
        },
    )
    last_err = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                resp = json.loads(r.read())
            entry = resp["data"][0]
            b64 = entry.get("b64_json") or entry.get("b64")
            if not b64:
                raise RuntimeError(f"no b64 in response: {list(entry.keys())}")
            return base64.b64decode(b64)
        except (urllib.error.HTTPError, urllib.error.URLError, KeyError) as e:
            last_err = e
            wait = 2 ** attempt
            print(f"  retry {attempt + 1}/{retries} after {wait}s: {e}", file=sys.stderr)
            time.sleep(wait)
    raise RuntimeError(f"grok api failed after {retries} tries: {last_err}")


def post_process(raw_png: bytes, out_path: Path) -> str:
    """Resize to AVATAR_SIZE x AVATAR_SIZE, ensure RGBA, write to disk.

    Returns sha256 hex of the final file.
    """
    import io
    im = Image.open(io.BytesIO(raw_png)).convert("RGBA")
    im = im.resize((AVATAR_SIZE, AVATAR_SIZE), Image.LANCZOS)
    im.save(out_path, "PNG", optimize=True)
    digest = hashlib.sha256(out_path.read_bytes()).hexdigest()
    return digest


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--force", action="store_true",
                   help="regenerate even if file with matching sha exists")
    p.add_argument("--out", type=Path, default=Path("assets/avatars"),
                   help="output directory (default: assets/avatars)")
    p.add_argument("--dry-run", action="store_true",
                   help="print what would happen without calling the API")
    args = p.parse_args()

    out_dir: Path = args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    if len(CHARACTERS) != 10:
        print(f"ERROR: expected 10 characters, got {len(CHARACTERS)}", file=sys.stderr)
        return 1

    # Personality sanity: 4 aggressive, 3 balanced, 3 conservative
    counts: Dict[str, int] = {"aggressive": 0, "balanced": 0, "conservative": 0}
    for c in CHARACTERS:
        counts[c["personality"]] += 1
    if counts != {"aggressive": 4, "balanced": 3, "conservative": 3}:
        print(f"ERROR: personality distribution must be 4-3-3, got {counts}",
              file=sys.stderr)
        return 1

    manifest_path = out_dir / "_manifest.json"
    manifest: List[Dict[str, str]] = []

    for idx, c in enumerate(CHARACTERS, start=1):
        avatar_name = f"avatar_{idx:02d}.png"
        out_path = out_dir / avatar_name
        prompt_hash = hashlib.sha256(c["prompt"].encode()).hexdigest()[:16]
        print(f"[{idx:02d}/10] {c['id']:<14} ({c['personality']:<12}) → {avatar_name}",
              file=sys.stderr)

        # Skip if matching file already on disk
        if out_path.exists() and not args.force:
            try:
                im = Image.open(out_path)
                if im.size == (AVATAR_SIZE, AVATAR_SIZE):
                    existing_sha = hashlib.sha256(out_path.read_bytes()).hexdigest()[:16]
                    print(f"  exists, sha={existing_sha} — skip", file=sys.stderr)
                    manifest.append({
                        "id": c["id"],
                        "name": c["name"],
                        "personality": c["personality"],
                        "file": avatar_name,
                        "prompt": c["prompt"],
                        "prompt_hash": prompt_hash,
                        "sha256": existing_sha,
                    })
                    continue
            except Exception:
                pass  # corrupt or wrong size — regenerate

        if args.dry_run:
            print(f"  [dry-run] would call grok and write {out_path}", file=sys.stderr)
            continue

        raw = call_grok(c["prompt"])
        sha = post_process(raw, out_path)
        print(f"  wrote {out_path} ({out_path.stat().st_size} bytes, sha={sha[:16]})",
              file=sys.stderr)
        manifest.append({
            "id": c["id"],
            "name": c["name"],
            "personality": c["personality"],
            "file": avatar_name,
            "prompt": c["prompt"],
            "prompt_hash": prompt_hash,
            "sha256": sha,
        })
        time.sleep(0.5)  # gentle rate limit

    if not args.dry_run:
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        print(f"\nwrote {manifest_path}", file=sys.stderr)

    # Summary
    print("\n=== Roster summary ===", file=sys.stderr)
    for m in manifest:
        print(f"  {m['file']:<18} {m['name']:<22} {m['personality']:<12} {m['id']}",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
