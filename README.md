# TransLyrics

Extract lyrics or transcripts from any YouTube video and optionally translate them into another language — all running locally on your computer, no account or API key needed.

---

## What it does

**`translyrics.py`** — give it a YouTube link, get a `.txt` file with the lyrics or transcript.

**`translation.py`** — give it that `.txt` file and a language name, get a translated `.txt` file.

---

## Before you start — things to install once

### 1. Python

Python is the language these scripts are written in. You need it installed to run them.

**Check if you already have it:**
1. Press `Windows + R`, type `cmd`, press Enter — this opens the Command Prompt
2. Type the following and press Enter:
   ```
   python --version
   ```
3. If you see something like `Python 3.10.0` (any version starting with 3), you're good. Skip to step 2.
4. If you get an error, go to [https://www.python.org/downloads/](https://www.python.org/downloads/), click the big **Download Python** button, run the installer.
   - **Important:** on the first screen of the installer, check the box that says **"Add Python to PATH"** before clicking Install.

---

### 2. ffmpeg

ffmpeg is a free tool that handles audio. The scripts need it when downloading audio to transcribe.

**Install on Windows:**
1. Go to [https://www.gyan.dev/ffmpeg/builds/](https://www.gyan.dev/ffmpeg/builds/)
2. Under **release builds**, download `ffmpeg-release-essentials.zip`
3. Extract the zip — you'll get a folder like `ffmpeg-7.x-essentials_build`
4. Inside that folder, open the `bin` folder. You should see `ffmpeg.exe` inside.
5. Copy the full path to that `bin` folder (example: `C:\ffmpeg\bin`)
6. Add it to your system PATH:
   - Press `Windows + S`, search for **"Edit the system environment variables"**, open it
   - Click **Environment Variables**
   - Under **User variables**, find **Path**, click it, then click **Edit**
   - Click **New**, paste your path (e.g. `C:\ffmpeg\bin`), click OK on all windows
7. Close and reopen any Command Prompt windows for the change to take effect
8. Verify it worked: open a new Command Prompt and type `ffmpeg -version` — you should see version info

**Install on Mac** (if you have Homebrew): `brew install ffmpeg`

**Install on Linux**: `sudo apt install ffmpeg`

---

### 3. Python packages

Once Python is installed, open a Command Prompt and run this single line:

```
python -m pip install yt-dlp openai-whisper deep-translator
```

This downloads three tools the scripts depend on. It only needs to be done once.

---

## How to use

### Step 0 — Open a Command Prompt in the right folder

1. Open File Explorer and navigate to the folder where you saved these scripts
2. Click on the address bar at the top (where it shows the folder path), type `cmd`, and press Enter
3. A Command Prompt window will open, already pointing to that folder

---

### Step 1 — Get lyrics from a YouTube video

```
python translyrics.py "PASTE_YOUR_YOUTUBE_URL_HERE"
```

**Example:**
```
python translyrics.py "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

When it finishes, a `.txt` file named after the video will appear in the same folder.

**How it works behind the scenes:**
- It first tries to grab the video's subtitles/captions (fast, a few seconds)
- It checks that the captions are actually in the same language as the song — if they're a translation, it ignores them
- If captions aren't available or can't be verified, it downloads the audio and transcribes it using AI (this takes longer — a few minutes depending on the video length)

**Optional flags you can add at the end:**

| Flag | What it does |
|---|---|
| `--whisper` | Skip captions entirely and always transcribe the audio with AI |
| `--model medium` | Use a more accurate AI model (slower, needs more RAM). Options: `tiny`, `base`, `small`, `medium`, `large` |
| `--no-lang-check` | Use captions as-is without checking if they match the audio language |

Example with a flag:
```
python translyrics.py "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --whisper
```

---

### Step 2 — Translate the lyrics (optional)

```
python translation.py "YOUR_FILE_NAME.txt" LANGUAGE
```

**Example:**
```
python translation.py "Never Gonna Give You Up.txt" french
```

This creates a new file called `Never Gonna Give You Up [French].txt` in the same folder.

**Supported languages** (and many more — just type the name in English):

`french` · `spanish` · `german` · `italian` · `portuguese` · `romanian` · `dutch` · `polish` · `russian` · `ukrainian` · `japanese` · `chinese` · `korean` · `arabic` · `latin` · `turkish` · `swedish` · `norwegian`

**Ukrainian is special:** the output file contains both the Cyrillic text and a Latin-alphabet transliteration, separated by a divider — no extra steps needed.

---

## AI model sizes (for the `--model` flag)

Only relevant when the script falls back to audio transcription. The default (`base`) is fine for most use cases.

| Model | Speed | RAM needed | Notes |
|---|---|---|---|
| tiny | Very fast | ~1 GB | Rough, good for quick tests |
| base | Fast | ~1 GB | Default, good for most videos |
| small | Medium | ~2 GB | Better accuracy |
| medium | Slow | ~5 GB | Very accurate |
| large | Very slow | ~10 GB | Best quality, needs a good GPU |

---

## Troubleshooting

**"python is not recognized"**
Python is not installed or not added to PATH. Reinstall it and make sure to check "Add Python to PATH" during installation.

**"ffmpeg is not recognized"**
ffmpeg is not in your PATH. Follow the ffmpeg installation steps above and make sure to open a new Command Prompt after adding it.

**"No module named yt_dlp" / "No module named whisper" / "No module named deep_translator"**
Run the install command again:
```
python -m pip install yt-dlp openai-whisper deep-translator
```

**The file name has special characters (!, ?, etc.) and the command fails**
Wrap the file name in double quotes:
```
python translation.py "VENI! VIDI! VICI!.txt" english
```

**The transcription takes a very long time**
This is normal when the script falls back to audio transcription (Whisper). A 4-minute song can take 2–5 minutes on a regular laptop. Using `--model tiny` is faster but less accurate.

**The output looks like gibberish or repeats the same phrase over and over**
This can happen with Whisper on music-heavy tracks with no clear vocals. Try a different model size (`--model small` or `--model medium`) or check if the video has captions available by running without `--whisper`.
