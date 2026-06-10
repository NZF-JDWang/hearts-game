"""Generate 10 realistic human portrait avatars for the Hearts roster via Grok Imagine.

Output: assets/avatars/avatar_<01..10>.png  (128x128 RGBA)
        assets/avatars/_manifest.json  (id, prompt, file, sha256)

Usage:
    python scripts/generate_avatars.py           # generate missing
    python scripts/generate_avatars.py --force   # regenerate all
    python scripts/generate_avatars.py --dry-run  # validate prompts only
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import sys
import time
from pathlib import Path

import requests
from PIL import Image

# ---------------------------------------------------------------------------
# Project roots
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[1]
AVATAR_DIR = ROOT / "assets" / "avatars"
MANIFEST_PATH = AVATAR_DIR / "_manifest.json"

# ---------------------------------------------------------------------------
# Character definitions (must match src/hearts/roster.py)
# ---------------------------------------------------------------------------

CHARACTERS = [
    {
        "id": "marco",
        "name": "Marco",
        "personality": "aggressive",
        "avatar_file": "avatar_01.png",
        "prompt": (
            "Photorealistic portrait photo of an Italian man in his early 30s, "
            "short dark hair, clean-shaven, intense confident expression, "
            "wearing a navy collared shirt, plain light grey background, "
            "head and shoulders framing, soft studio lighting, no text"
        ),
    },
    {
        "id": "priya",
        "name": "Priya",
        "personality": "balanced",
        "avatar_file": "avatar_02.png",
        "prompt": (
            "Photorealistic portrait photo of a South Asian woman in her late 20s, "
            "long dark hair, calm thoughtful expression, "
            "wearing a white blouse, plain light grey background, "
            "head and shoulders framing, soft studio lighting, no text"
        ),
    },
    {
        "id": "tomoko",
        "name": "Tomoko",
        "personality": "conservative",
        "avatar_file": "avatar_03.png",
        "prompt": (
            "Photorealistic portrait photo of a Japanese woman in her early 60s, "
            "short neat grey hair, gentle reserved expression, "
            "wearing a cream cardigan over a light top, plain light grey background, "
            "head and shoulders framing, soft studio lighting, no text"
        ),
    },
    {
        "id": "jesus",
        "name": "Jesús",
        "personality": "aggressive",
        "avatar_file": "avatar_04.png",
        "prompt": (
            "Photorealistic portrait photo of a Spanish man in his mid 20s, "
            "short dark curly hair, sharp competitive grin, "
            "wearing a dark henley shirt, plain light grey background, "
            "head and shoulders framing, soft studio lighting, no text"
        ),
    },
    {
        "id": "anna",
        "name": "Anna",
        "personality": "balanced",
        "avatar_file": "avatar_05.png",
        "prompt": (
            "Photorealistic portrait photo of a Scandinavian woman in her early 30s, "
            "blonde hair in a practical bun, composed steady expression, "
            "wearing a light blue scrubs top, plain light grey background, "
            "head and shoulders framing, soft studio lighting, no text"
        ),
    },
    {
        "id": "kwame",
        "name": "Kwame",
        "personality": "aggressive",
        "avatar_file": "avatar_06.png",
        "prompt": (
            "Photorealistic portrait photo of a Ghanaian man in his mid 40s, "
            "close-cropped hair, warm but determined expression, "
            "wearing a checkered button-down shirt, plain light grey background, "
            "head and shoulders framing, soft studio lighting, no text"
        ),
    },
    {
        "id": "sarah",
        "name": "Sarah",
        "personality": "conservative",
        "avatar_file": "avatar_07.png",
        "prompt": (
            "Photorealistic portrait photo of an Irish woman in her early 50s, "
            "shoulder-length brown hair with reading glasses, quiet observant expression, "
            "wearing a green cardigan, plain light grey background, "
            "head and shoulders framing, soft studio lighting, no text"
        ),
    },
    {
        "id": "dmitri",
        "name": "Dmitri",
        "personality": "aggressive",
        "avatar_file": "avatar_08.png",
        "prompt": (
            "Photorealistic portrait photo of a Russian man in his late 30s, "
            "short fair hair, icy focused expression, "
            "wearing a black turtleneck, plain light grey background, "
            "head and shoulders framing, soft studio lighting, no text"
        ),
    },
    {
        "id": "lin",
        "name": "Lin",
        "personality": "balanced",
        "avatar_file": "avatar_09.png",
        "prompt": (
            "Photorealistic portrait photo of a Chinese woman in her early 20s, "
            "straight black hair, analytical alert expression, "
            "wearing a casual dark hoodie, plain light grey background, "
            "head and shoulders framing, soft studio lighting, no text"
        ),
    },
    {
        "id": "ben",
        "name": "Ben",
        "personality": "conservative",
        "avatar_file": "avatar_10.png",
        "prompt": (
            "Photorealistic portrait photo of a New Zealand man in his late 60s, "
            "white receding hair, mild patient expression, "
            "wearing a worn brown cardigan over a light shirt, plain light grey background, "
            "head and shoulders framing, soft studio lighting, no text"
        ),
    },
]

# ---------------------------------------------------------------------------
# Personality distribution check
# ---------------------------------------------------------------------------

def _validate_distribution(chars: list[dict]) -> None:
    from collections import Counter
    counts = Counter(c["personality"] for c in chars)
    assert counts["aggressive"] >= 3, f"need >= 3 aggressive, got {counts['aggressive']}"
    assert counts["balanced"] >= 3, f"need >= 3 balanced, got {counts['balanced']}"
    assert counts["conservative"] >= 3, f"need >= 3 conservative, got {counts['conservative']}"
    print(f"  OK: {counts['aggressive']} aggressive, {counts['balanced']} balanced, {counts['conservative']} conservative")

# ---------------------------------------------------------------------------
# Grok Imagine API
# ---------------------------------------------------------------------------

def _api_key() -> str:
    # Try sven profile env, then real home, then env.
    for env_path in [
        Path.home() / ".env",
        Path("/home/jd/.hermes/profiles/sven/.env"),
        Path("/home/jd/.hermes/.env"),
    ]:
        if env_path.is_file():
            for line in env_path.read_text().splitlines():
                if line.startswith("XAI_API_KEY="):
                    return line.split("=", 1)[1].strip()
    key = os.environ.get("XAI_API_KEY", "")
    if key:
        return key
    raise RuntimeError("XAI_API_KEY not found in .env or environment")


def _generate_image(prompt: str, out_path: Path) -> None:
    """Call xAI Grok Imagine and save the 128x128 RGBA result."""
    import base64
    import io
    api_key = _api_key()
    url = "https://api.x.ai/v1/images/generations"
    payload = {
        "model": "grok-imagine-image-quality",
        "prompt": prompt,
        "n": 1,
        "response_format": "b64_json",
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    resp = requests.post(url, json=payload, headers=headers, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    b64 = data["data"][0]["b64_json"]

    raw = Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGBA")

    # Resize to 128x128 for game use.
    out = raw.resize((128, 128), Image.LANCZOS)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.save(str(out_path), format="PNG")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Generate avatar portraits via Grok Imagine")
    parser.add_argument("--force", action="store_true", help="Regenerate all avatars")
    parser.add_argument("--dry-run", action="store_true", help="Validate prompts only, no API calls")
    args = parser.parse_args()

    print("Avatar generation — realistic human portraits")
    print(f"  Characters: {len(CHARACTERS)}")
    _validate_distribution(CHARACTERS)

    AVATAR_DIR.mkdir(parents=True, exist_ok=True)
    manifest: list[dict] = []

    for i, char in enumerate(CHARACTERS, 1):
        out_path = AVATAR_DIR / char["avatar_file"]
        prompt = char["prompt"]
        print(f"  [{i:02d}/10] {char['name']:<10} personality={char['personality']:<12} file={char['avatar_file']}")

        if args.dry_run:
            print(f"           prompt: {prompt[:80]}...")
            manifest.append({"id": char["id"], "name": char["name"], "prompt": prompt,
                             "file": char["avatar_file"], "sha256": "<dry-run>"})
            continue

        if out_path.exists() and not args.force:
            # Verify it's a real image (not a placeholder).
            try:
                im = Image.open(str(out_path))
                if im.size == (128, 128) and out_path.stat().st_size > 5000:
                    print(f"           ✓ exists and valid ({out_path.stat().st_size:,} bytes), skipping")
                    sha = hashlib.sha256(out_path.read_bytes()).hexdigest()[:16]
                    manifest.append({"id": char["id"], "name": char["name"], "prompt": prompt,
                                     "file": char["avatar_file"], "sha256": sha})
                    continue
            except Exception:
                pass  # Fall through to regenerate.

        print(f"           generating...")
        _generate_image(prompt, out_path)
        sha = hashlib.sha256(out_path.read_bytes()).hexdigest()[:16]
        size = out_path.stat().st_size
        print(f"           ✓ saved {size:,} bytes  sha256={sha}")
        manifest.append({"id": char["id"], "name": char["name"], "prompt": prompt,
                         "file": char["avatar_file"], "sha256": sha})
        time.sleep(1)  # Gentle rate-limit.

    if not args.dry_run:
        MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n")
        print(f"\n  Manifest written to {MANIFEST_PATH}")
    else:
        print(f"\n  Dry run — {len(manifest)} prompts validated.")


if __name__ == "__main__":
    main()