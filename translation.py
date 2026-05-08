"""
translation.py — Translate lyrics/transcript from a translyrics output .txt file.

Usage:
  python translation.py <txt_file> <language>

Examples:
  python translation.py "Blinding Lights.txt" french
  python translation.py "Blinding Lights.txt" spanish
  python translation.py "Blinding Lights.txt" romanian
  python translation.py "Blinding Lights.txt" ukrainian
  python translation.py "Blinding Lights.txt" japanese

Note: Ukrainian output includes both Cyrillic and transliteration in the same file.
"""

import argparse
import os
import sys


# ---------------------------------------------------------------------------
# Ukrainian transliteration table (Cabinet of Ministers of Ukraine standard)
# ---------------------------------------------------------------------------

UA_TRANSLIT = {
    'а': 'a',  'б': 'b',  'в': 'v',  'г': 'h',  'ґ': 'g',
    'д': 'd',  'е': 'e',  'є': 'ye', 'ж': 'zh', 'з': 'z',
    'и': 'y',  'і': 'i',  'ї': 'yi', 'й': 'y',  'к': 'k',
    'л': 'l',  'м': 'm',  'н': 'n',  'о': 'o',  'п': 'p',
    'р': 'r',  'с': 's',  'т': 't',  'у': 'u',  'ф': 'f',
    'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'shch',
    'ь': '',   'ю': 'yu', 'я': 'ya',
    # Uppercase
    'А': 'A',  'Б': 'B',  'В': 'V',  'Г': 'H',  'Ґ': 'G',
    'Д': 'D',  'Е': 'E',  'Є': 'Ye', 'Ж': 'Zh', 'З': 'Z',
    'И': 'Y',  'І': 'I',  'Ї': 'Yi', 'Й': 'Y',  'К': 'K',
    'Л': 'L',  'М': 'M',  'Н': 'N',  'О': 'O',  'П': 'P',
    'Р': 'R',  'С': 'S',  'Т': 'T',  'У': 'U',  'Ф': 'F',
    'Х': 'Kh', 'Ц': 'Ts', 'Ч': 'Ch', 'Ш': 'Sh', 'Щ': 'Shch',
    'Ь': '',   'Ю': 'Yu', 'Я': 'Ya',
}


def transliterate_ukrainian(text: str) -> str:
    result = []
    for char in text:
        result.append(UA_TRANSLIT.get(char, char))
    return "".join(result)


# ---------------------------------------------------------------------------
# File I/O
# ---------------------------------------------------------------------------

def read_lyrics_file(path: str) -> tuple[str, str, str]:
    """
    Parse a translyrics .txt file.
    Returns (title, source, lyrics_text).
    """
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()

    title = ""
    source = ""
    lyrics_lines = []
    past_header = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("Title:"):
            title = stripped[len("Title:"):].strip()
        elif stripped.startswith("Source:"):
            source = stripped[len("Source:"):].strip()
        elif stripped.startswith("=" * 10):
            past_header = True
        elif past_header:
            lyrics_lines.append(line.rstrip())

    lyrics = "\n".join(lyrics_lines).strip()
    return title, source, lyrics


def save_translation(title: str, source: str, translated: str, language: str,
                     original_path: str, transliterated: str = None) -> str:
    """Save translated lyrics to a .txt file. Returns the saved path."""
    base = os.path.splitext(os.path.basename(original_path))[0]
    filename = f"{base} [{language.capitalize()}].txt"

    with open(filename, "w", encoding="utf-8") as f:
        f.write(f"Title: {title}\n")
        f.write(f"Source: {source}\n")
        f.write(f"Translation: {language.capitalize()} (via Google Translate)\n")
        f.write("=" * 60 + "\n\n")
        f.write(translated)
        f.write("\n")

        if transliterated:
            f.write("\n" + "=" * 60 + "\n")
            f.write("TRANSLITERATION (Latin alphabet)\n")
            f.write("=" * 60 + "\n\n")
            f.write(transliterated)
            f.write("\n")

    return filename


# ---------------------------------------------------------------------------
# Translation
# ---------------------------------------------------------------------------

def translate_text(text: str, target_language: str) -> str:
    """
    Translate text using deep-translator (Google Translate backend).
    Splits into chunks to stay within API limits.
    """
    try:
        from deep_translator import GoogleTranslator
    except ImportError:
        print("[ERROR] deep-translator is not installed.")
        print("        Run: python -m pip install deep-translator")
        sys.exit(1)

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

    translator = GoogleTranslator(source="auto", target=target_language)
    translated_chunks = []

    for i, chunk in enumerate(chunks):
        if len(chunks) > 1:
            print(f"[INFO] Translating chunk {i + 1}/{len(chunks)}...")
        translated_chunks.append(translator.translate(chunk))

    return "\n".join(translated_chunks)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Translate a translyrics .txt file to another language."
    )
    parser.add_argument("file", help="Path to the .txt file from translyrics.py")
    parser.add_argument("language", help="Target language (e.g. french, spanish, romanian, ukrainian)")
    args = parser.parse_args()

    if not os.path.isfile(args.file):
        print(f"[ERROR] File not found: {args.file}")
        sys.exit(1)

    print(f"[INFO] Reading: {args.file}")
    title, source, lyrics = read_lyrics_file(args.file)

    if not lyrics:
        print("[ERROR] No lyrics found in the file.")
        sys.exit(1)

    print(f"[INFO] Translating to {args.language.capitalize()}...")
    translated = translate_text(lyrics, args.language)

    transliterated = None
    if args.language.lower() == "ukrainian":
        print("[INFO] Generating transliteration...")
        transliterated = transliterate_ukrainian(translated)

    out_path = save_translation(title, source, translated, args.language,
                                args.file, transliterated)
    print(f"[DONE] Saved to: {out_path}")
    print("\n" + "=" * 60)
    print(translated[:2000])
    if len(translated) > 2000:
        print(f"\n... [truncated — full text in {out_path}]")


if __name__ == "__main__":
    main()
