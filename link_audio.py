import os
import sys
import re
from pathlib import Path
from database import get_db, ensure_audio_path_column

SUPPORTED_EXTS = {'.mp3', '.m4a', '.aac', '.wav', '.flac', '.ogg'}

SEP_VARIANTS = [" – ", " - ", " — "]


def normalize(text: str) -> str:
    if not text:
        return ''
    text = text.lower()
    # Replace separators with spaces
    for sep in SEP_VARIANTS:
        text = text.replace(sep, ' ')
    # Remove anything in parentheses/brackets
    text = re.sub(r"[\(\[][^\)\]]*[\)\]]", " ", text)
    # Replace non-alnum with spaces
    text = re.sub(r"[^a-z0-9]+", " ", text)
    # Collapse spaces
    text = re.sub(r"\s+", " ", text).strip()
    return text


def scan_files(root: Path):
    files = []
    for path in root.rglob('*'):
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTS:
            files.append(path)
    return files


def main():
    if len(sys.argv) < 2:
        print("Usage: python link_audio.py <base_audio_folder>")
        sys.exit(1)

    base = Path(sys.argv[1]).expanduser()
    if not base.exists() or not base.is_dir():
        print(f"Base folder not found: {base}")
        sys.exit(2)

    ensure_audio_path_column()

    print(f"Scanning for audio under: {base}")
    audio_files = scan_files(base)
    print(f"Found {len(audio_files)} audio files")

    # Build index by normalized filename (without extension)
    file_index = {}
    for f in audio_files:
        key = normalize(f.stem)
        if key:
            file_index.setdefault(key, []).append(f)

    linked = 0
    ambiguous = 0
    missing = 0

    with get_db() as conn:
        cur = conn.cursor()
        songs = cur.execute('SELECT id, title, artist FROM songs').fetchall()
        for song in songs:
            title_key = normalize(song['title'])
            artist_key = normalize(song['artist'])

            candidates = []
            # direct title match
            if title_key in file_index:
                candidates.extend(file_index[title_key])

            # title + artist combined
            combined_key = normalize(f"{song['title']} {song['artist']}")
            if combined_key in file_index:
                candidates.extend(x for x in file_index[combined_key] if x not in candidates)

            # fuzzy: filename contains title tokens and artist tokens
            if not candidates:
                for k, flist in file_index.items():
                    if title_key and title_key in k:
                        if artist_key and (artist_key in k or any(tok in k for tok in artist_key.split())):
                            candidates.extend(x for x in flist if x not in candidates)

            # Decide
            if len(candidates) == 1:
                path = str(candidates[0])
                cur.execute('UPDATE songs SET audio_path = ? WHERE id = ?', (path, song['id']))
                linked += 1
            elif len(candidates) > 1:
                # ambiguous, leave unset
                ambiguous += 1
            else:
                missing += 1

    print(f"Linking done. Linked: {linked}, Ambiguous: {ambiguous}, Missing: {missing}")


if __name__ == '__main__':
    main()
