"""
translyrics.py — Extract lyrics/transcript from a YouTube URL.

Strategy:
  1. Fetch video metadata (title, declared audio language, subtitle tracks) via yt-dlp.
  2. Try to fetch existing subtitles via yt-dlp — preferring non-English tracks,
     since those are more likely the original lyrics rather than a translation.
  3. If the caption language doesn't match the declared audio language, warn and
     fall back to Whisper so you get the actual sung lyrics, not a translation.
  4. If no captions exist at all, fall back to Whisper.
  5. If the lyrics are not in English, automatically translate them to English
     and save both files inside an output folder named after the song.

Usage:
  python translyrics.py <youtube_url>
  python translyrics.py <youtube_url> --whisper          # always use Whisper
  python translyrics.py <youtube_url> --model medium     # Whisper model size
  python translyrics.py <youtube_url> --no-lang-check    # skip mismatch detection
"""

__author__ = "Millie"

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def sanitize_filename(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "_", name)


def get_video_metadata(url: str) -> dict:
    """
    Fetch full video metadata via yt-dlp --dump-json.
    Returns a dict with at minimum: title, language, subtitles, automatic_captions.
    Returns {} on failure.
    """
    result = subprocess.run(
        [sys.executable, "-m", "yt_dlp", "--dump-json", "--no-playlist", url],
        capture_output=True, text=True
    )
    try:
        return json.loads(result.stdout)
    except (json.JSONDecodeError, ValueError):
        return {}


def choose_subtitle_lang(metadata: dict) -> str:
    """
    Pick the best subtitle language to request.
    Priority: non-English manual subs > non-English auto subs > English.
    Non-English tracks are more likely to be the original lyrics, not a translation.
    """
    manual = list(metadata.get("subtitles", {}).keys())
    auto = list(metadata.get("automatic_captions", {}).keys())

    non_en_manual = [lang for lang in manual if not lang.startswith("en")]
    if non_en_manual:
        return non_en_manual[0]

    non_en_auto = [lang for lang in auto if not lang.startswith("en")]
    if non_en_auto:
        return non_en_auto[0]

    return "en"


def parse_vtt(path: str) -> tuple[str, str | None]:
    """
    Parse a WebVTT subtitle file into clean deduplicated text.
    Returns (transcript_text, caption_language_code).
    YouTube auto-captions repeat lines across adjacent cues — dedup them.
    """
    with open(path, encoding="utf-8") as f:
        raw = f.read()

    cap_lang = None
    lines = []
    seen_last = None
    for line in raw.splitlines():
        if not line.strip():
            continue
        if line.startswith("WEBVTT") or line.startswith("Kind:"):
            continue
        if line.startswith("Language:"):
            cap_lang = line.split(":", 1)[1].strip()
            continue
        if re.match(r"^\d{2}:\d{2}", line):  # timestamp line
            continue
        # Strip VTT inline tags like <00:00:00.000><c>word</c>
        clean = re.sub(r"<[^>]+>", "", line).strip()
        if not clean:
            continue
        if clean != seen_last:
            lines.append(clean)
            seen_last = clean

    return "\n\n".join(lines), cap_lang


def extract_captions(url: str, lang: str = "en") -> tuple[str | None, str | None]:
    """
    Try to download subtitles with yt-dlp for the given language.
    Returns (transcript_text, caption_lang) or (None, None) if unavailable.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        out_template = os.path.join(tmpdir, "%(title)s.%(ext)s")

        cmd = [
            sys.executable, "-m", "yt_dlp",
            "--skip-download",
            "--write-auto-sub",
            "--write-sub",
            "--sub-lang", lang,
            "--sub-format", "vtt",
            "--no-playlist",
            "-o", out_template,
            url,
        ]
        subprocess.run(cmd, capture_output=True, text=True)

        vtt_files = [f for f in os.listdir(tmpdir) if f.endswith(".vtt")]
        if not vtt_files:
            return None, None

        vtt_path = os.path.join(tmpdir, vtt_files[0])
        transcript, cap_lang = parse_vtt(vtt_path)
        return transcript, cap_lang


def transcribe_with_whisper(url: str, title: str, model_size: str = "base") -> tuple[str, str]:
    """
    Download audio via yt-dlp and transcribe with OpenAI Whisper.
    Returns (transcript_text, detected_language_code).
    """
    try:
        import whisper
    except ImportError:
        print("[ERROR] openai-whisper is not installed.")
        print("        Run: python -m pip install openai-whisper")
        sys.exit(1)

    with tempfile.TemporaryDirectory() as tmpdir:
        audio_path = os.path.join(tmpdir, "audio.mp3")

        print(f"[INFO] Downloading audio for: {title}")
        cmd = [
            sys.executable, "-m", "yt_dlp",
            "--no-playlist",
            "-x", "--audio-format", "mp3",
            "-o", audio_path,
            url,
        ]
        subprocess.run(cmd, check=True)

        print(f"[INFO] Transcribing with Whisper model '{model_size}' (this may take a moment)...")
        model = whisper.load_model(model_size)
        result = model.transcribe(audio_path, fp16=False)

        detected_lang = result.get("language", "unknown")
        segments = result.get("segments", [])
        if segments:
            transcript = "\n\n".join(seg["text"].strip() for seg in segments if seg["text"].strip())
        else:
            transcript = result["text"].strip()

        return transcript, detected_lang


def translate_to_english(text: str) -> str | None:
    """
    Translate text to English using Google Translate via deep-translator.
    Splits into chunks to stay within API limits.
    Returns None if deep-translator is not installed.
    """
    try:
        from deep_translator import GoogleTranslator
    except ImportError:
        print("[WARN] deep-translator is not installed — skipping auto-translation.")
        print("       Run: python -m pip install deep-translator")
        return None

    MAX_CHUNK = 4500
    paragraphs = text.split("\n")
    chunks = []
    current_chunk = []
    current_len = 0

    for para in paragraphs:
        if current_len + len(para) + 1 > MAX_CHUNK:
            chunks.append("\n".join(current_chunk))
            current_chunk = [para]
            current_len = len(para)
        else:
            current_chunk.append(para)
            current_len += len(para) + 1

    if current_chunk:
        chunks.append("\n".join(current_chunk))

    translator = GoogleTranslator(source="auto", target="english")
    translated_chunks = []
    for i, chunk in enumerate(chunks):
        if len(chunks) > 1:
            print(f"[INFO] Translating chunk {i + 1}/{len(chunks)}...")
        translated_chunks.append(translator.translate(chunk))

    return "\n".join(translated_chunks)


def save_output(title: str, transcript: str, source: str, output_dir: str) -> str:
    """Save transcript to a .txt file inside output_dir. Returns the saved path."""
    safe_title = sanitize_filename(title)[:80]
    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, f"{safe_title}.txt")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"Title: {title}\n")
        f.write(f"Source: {source}\n")
        f.write("=" * 60 + "\n\n")
        f.write(transcript)
        f.write("\n")

    return filepath


def save_translation(title: str, source: str, translated: str, output_dir: str) -> str:
    """Save English translation to a .txt file inside output_dir. Returns the saved path."""
    safe_title = sanitize_filename(title)[:80]
    filepath = os.path.join(output_dir, f"{safe_title} [English].txt")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"Title: {title}\n")
        f.write(f"Source: {source}\n")
        f.write("Translation: English (via Google Translate)\n")
        f.write("=" * 60 + "\n\n")
        f.write(translated)
        f.write("\n")

    return filepath


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Extract lyrics/transcript from a YouTube URL."
    )
    parser.add_argument("url", help="YouTube video URL")
    parser.add_argument(
        "--whisper", action="store_true",
        help="Skip caption extraction and always use Whisper"
    )
    parser.add_argument(
        "--model", default="base",
        choices=["tiny", "base", "small", "medium", "large"],
        help="Whisper model size (default: base). Larger = more accurate but slower."
    )
    parser.add_argument(
        "--no-lang-check", action="store_true",
        help="Skip caption language mismatch detection (use captions as-is)"
    )
    args = parser.parse_args()

    print(f"[INFO] Processing: {args.url}\n")

    # --- Fetch video metadata (title, declared audio language, subtitle tracks) ---
    print("[INFO] Fetching video metadata...")
    metadata = get_video_metadata(args.url)
    title = metadata.get("title") or "unknown"
    audio_lang = metadata.get("language")  # declared audio language, e.g. "la", "de", or None

    output_dir = sanitize_filename(title)[:80]

    if args.whisper:
        transcript, transcript_lang = transcribe_with_whisper(args.url, title, args.model)
        source = f"Whisper transcription (model: {args.model})"
    else:
        sub_lang = choose_subtitle_lang(metadata)
        if sub_lang != "en":
            print(f"[INFO] Non-English subtitle track found: '{sub_lang}'. Trying it first.")
        print(f"[INFO] Trying to fetch captions (lang: {sub_lang})...")

        transcript, cap_lang = extract_captions(args.url, sub_lang)

        if transcript:
            print(f"[OK]   Captions found for: {title}")
            if cap_lang:
                print(f"[INFO] Caption language: {cap_lang}")

            # Language mismatch check: captions are only trusted when the declared
            # audio language is known AND matches the caption language.
            # If the audio language is undeclared, we can't verify — fall back to Whisper.
            if not args.no_lang_check:
                if audio_lang and cap_lang:
                    audio_base = audio_lang.split("-")[0].lower()
                    cap_base = cap_lang.split("-")[0].lower()
                    if audio_base != cap_base:
                        print(f"[WARN] Caption language '{cap_lang}' doesn't match "
                              f"declared audio language '{audio_lang}'.")
                        print("[WARN] Captions appear to be a translation, not the original lyrics.")
                        print("[INFO] Falling back to Whisper to transcribe the actual lyrics...")
                        transcript, transcript_lang = transcribe_with_whisper(args.url, title, args.model)
                        source = f"Whisper transcription (model: {args.model})"
                    else:
                        transcript_lang = cap_lang
                        source = "YouTube captions (yt-dlp)"
                else:
                    print("[WARN] Video has no declared audio language — cannot verify captions.")
                    print("[INFO] Falling back to Whisper to ensure original lyrics are captured...")
                    transcript, transcript_lang = transcribe_with_whisper(args.url, title, args.model)
                    source = f"Whisper transcription (model: {args.model})"
            else:
                transcript_lang = cap_lang or audio_lang
                source = "YouTube captions (yt-dlp)"
        else:
            print("[INFO] No captions available. Falling back to Whisper transcription.")
            transcript, transcript_lang = transcribe_with_whisper(args.url, title, args.model)
            source = f"Whisper transcription (model: {args.model})"

    # --- Save original lyrics ---
    orig_path = save_output(title, transcript, source, output_dir)
    print(f"\n[DONE] Saved to: {orig_path}")

    # --- Auto-translate to English if lyrics are not in English ---
    lang_base = (transcript_lang or "").split("-")[0].lower()
    if lang_base and lang_base != "en":
        print(f"\n[INFO] Lyrics are in '{transcript_lang}' — translating to English...")
        translated = translate_to_english(transcript)
        if translated:
            trans_path = save_translation(title, source, translated, output_dir)
            print(f"[DONE] Translation saved to: {trans_path}")

    print("\n" + "=" * 60)
    print(transcript[:2000])
    if len(transcript) > 2000:
        print(f"\n... [truncated — full text in {orig_path}]")


if __name__ == "__main__":
    main()
