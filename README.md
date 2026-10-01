# TranscriptLab

**A local-first desktop workbench that turns audio, video, YouTube, podcasts and documents into clean Markdown, ready to be used as a corpus for a RAG system.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE) ![Python](https://img.shields.io/badge/Python-3.9%2B-blue) ![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey)

## Why it exists

Companies that hold valuable know-how (lectures, interviews, calls, manuals) cannot always send it to a public AI service. TranscriptLab runs the heavy work on your own machine: speech-to-text with OpenAI Whisper, document conversion with MarkItDown, and cleaning rules that make the output consistent. The result is a folder of tidy Markdown files with metadata headers, which is the raw material for a retrieval-augmented generation (RAG) pipeline or later fine-tuning.

## What it does

The app is a Tkinter desktop GUI with one tab per job:

| Tab | Purpose |
|---|---|
| **Transcription** | Batch queue for audio/video files, Whisper model choice per language, model download on demand, live log and progress |
| **Live** | Capture audio playing on the PC (Windows loopback) and transcribe it in chunks |
| **MD** | Convert PDF, DOCX and subtitle files to Markdown |
| **MD Polish** | Re-flow wrapped lines, remove caption noise and hyphenation, apply custom correction dictionaries, optional Claude-assisted clean-up levels |
| **YouTube** | Fetch captions for videos or channels and save them as Markdown |
| **Download** | Download media with yt-dlp, with pacing and optional automatic transcription |
| **Podcast** | Read RSS feeds, download episodes and transcribe them |
| **Link Grabber** | Collect video links from a channel with filters (duration, sections) |
| **Dictionaries** | Vocabulary profiles that prime Whisper and fix recurring mistakes |
| **Comparison** | Run two Whisper models on the same excerpt and compare the output |

Other features: metadata header per Markdown file, ETA estimates learned from past runs, saved queues, a LAN status page to watch long batches from a phone, and a built-in tools manager that installs and checks Whisper, ffmpeg, pandoc and Docling.

## Quick start (Windows)

1. Install Python 3.9+ and [ffmpeg](https://ffmpeg.org/).
2. Run `TranscriptLab.bat` (or `python TranscriptLab.py`).
3. Open the tools manager inside the app to install Whisper and MarkItDown.
4. Add files in the **Transcription** tab, choose language and model, press start.

Whisper models run locally. Nothing is uploaded unless you turn on the optional Claude-assisted polish, which needs your own API key.

## Responsible use

Only transcribe or download material you have the right to use. The repository contains code only; it ships no transcripts, recordings or corpus data.

## Project facts

- About 27,000 lines of Python in one file, organised in clear sections
- More than 70 numbered versions, from a 35 KB prototype to the current build (see `archive/versions/`)
- `prompts/` holds the written briefs used to direct each major version (some are in Portuguese)
- `docs/legacy/` has the first READMEs

## Roadmap

- Read API keys from environment variables or the OS keychain instead of the local settings file
- Split the single file into modules and add automated tests
- Export chunked Markdown with embeddings metadata for common vector stores

---

## How this was built

Built with **Claude (Anthropic)** as the coding partner. I wrote the requirements and the revision prompts, tested every build on real data, and decided what to fix next. The `archive/versions/` folder keeps every earlier release so the iteration history is visible, and `prompts/` shows the briefs I gave Claude. See [ai-assisted-development](https://github.com/junqueirach/ai-assisted-development) for the method.

**Security note:** the app stores any API keys you enter in a local settings file outside this repository. `.gitignore` excludes config and settings files so keys are never committed.

## Licence

MIT. See [LICENSE](LICENSE).

## Author

Luiz Junqueira - [junqueira.ch](https://www.junqueira.ch) - [LinkedIn](https://www.linkedin.com/in/luizjunqueira/)
