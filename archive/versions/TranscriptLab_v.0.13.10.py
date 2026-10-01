#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TranscriptLab - GUI
===================
Batch-transcribe video/audio with OpenAI Whisper (CLI) and turn the result
into clean, AI-ready Markdown via MarkItDown.

Every Markdown file this app writes goes through the MD polish stage (see
"MD polish" below): PDF/DOCX output is re-flowed (MarkItDown keeps the visual
line wrapping, the justification spaces, one form feed per page and hyphens
broken across lines), and subtitle/transcript prose is cleaned of caption
noise. The metadata header is preserved verbatim, so "Qualidade" keeps the
value the user configured.

VERSIONING NOTE (read me):
    APP_VERSION below follows Semantic Versioning (MAJOR.MINOR.PATCH).
    ALWAYS bump it when the code changes:
      - PATCH: bug fixes / tiny tweaks (0.6.0 -> 0.6.1)
      - MINOR: new backward-compatible features (0.6.0 -> 0.7.0)
      - MAJOR: breaking changes (0.6.0 -> 1.0.0)
    The About dialog shows this value.

Requirements:
    - Python 3.9+ (Tkinter included by default on Windows)
    - Whisper (https://github.com/openai/whisper)
    - MarkItDown (https://github.com/microsoft/markitdown) for the MD features
    - ffmpeg recommended (Whisper needs it for most formats; also enables % bar)

Author: Luiz Junqueira & Claude AI
"""

APP_VERSION = "0.13.10"
# v0.13.0 — "Check for All Tools Update" bug fixes:
#   - the "Update" button there used to just open the tool's own Settings
#     dialog instead of updating anything; it now runs the real upgrade
#     inline, with its own log.
#   - a tool that wasn't installed used to be reported as "Up to date"
#     (and still triggered a pointless network call); it now shows "Not
#     installed" immediately, with no network call.
#   - a per-tool Settings dialog's own Update row used to keep showing a
#     stale "Update available" after a successful update until manually
#     re-checked; it now refreshes itself right after.
#   - "latest version" checks (MarkItDown/yt-dlp/Whisper) now walk PyPI's
#     full release list and explicitly skip pre-releases/yanked releases
#     instead of trusting the bare "latest" field.
# v0.13.1 — fixes found testing v0.13.0 against a real custom Whisper
#   install and a real dependency conflict:
#   - a Whisper install at a custom/manual path (not this app's own
#     managed venv) was reported "Not installed" in Check for All Tools
#     Update — it only checked the default managed location. New shared
#     resolve_whisper_env_dir() (also now used by Settings -> Whisper)
#     derives the real venv from whatever whisper_path is configured.
#   - _update_whisper() referenced a Settings-dialog-local closure by
#     name from outside it — a NameError waiting to happen the moment it
#     ran from Check for All Tools Update instead of that dialog.
#   - pip can exit 0 having changed nothing (a dependency conflict with
#     another already-installed package leaves the old version in
#     place) — this used to be logged identically to a real upgrade,
#     which is what made that case so confusing to diagnose. Now logged
#     as an explicit "installed version didn't change" warning instead.
# v0.13.2 — fixed the actual cause of the case above, not just its
#   reporting: an unversioned "pip install --upgrade markitdown[all]"
#   gives pip an easy out — if the latest version's own dependency needs
#   conflict with anything already installed (e.g. mammoth~=1.11.0
#   vs. an already-installed 1.12.0), pip can just leave the old
#   version in place, since it still technically "satisfies" the bare
#   unversioned request, and exit 0 having changed nothing. Update flows
#   (which already know the exact target version from "Check for
#   updates") now pin to that exact version instead, removing the easy
#   out: pip either resolves it for real or fails with a genuine,
#   readable conflict error. Applies to MarkItDown/yt-dlp/Whisper;
#   "Install (global)" is unaffected (no known target version yet).
# v0.13.3 — the exact-pin fix above can still legitimately fail: the
#   shared tools venv (markitdown/yt-dlp/youtube-transcript-api) had
#   accumulated an already-installed youtube-transcript-api that a newer
#   markitdown[all] release's own pin couldn't be reconciled with, no
#   matter how precisely the markitdown command itself was constructed
#   — the conflict lives in the venv's accumulated state, not in the
#   command. New "Rebuild environment" (Settings -> MarkItDown, and
#   offered as a log hint whenever a pinned update fails) wipes tools/
#   venv and reinstalls markitdown[all] + yt-dlp together into a fresh
#   one, so there's nothing left over to conflict with.
# v0.13.4 — the rebuild itself could silently no-op: shutil.rmtree(...,
#   ignore_errors=True) can fail to remove anything on Windows if a file
#   from the old venv is still momentarily locked, and `python -m venv`
#   against a pre-existing folder does NOT clear installed packages —
#   so "rebuild" could quietly change nothing at all. Now verified
#   explicitly (with one short retry for a transient lock) instead of
#   trusted blindly. The rebuild's reinstall is now pinned to the exact
#   latest stable version too, and success/failure both now show a
#   messagebox, not just a log line that's easy to miss.
# v0.13.5 — the REAL root cause, finally confirmed on a genuinely fresh
#   venv: markitdown[all]==0.1.7 hard-pins youtube-transcript-api~=1.0.0,
#   and every 1.0.x-1.2.2 release of youtube-transcript-api requires
#   Python <3.14 — so markitdown[all] is simply uninstallable on Python
#   3.14+, on any machine, regardless of environment state. Neither
#   pinning (v0.13.2) nor rebuilding (v0.13.3/4) could ever have fixed
#   this — both were real fixes for real bugs found along the way, just
#   not this one. New MARKITDOWN_INSTALL_SPEC requests every markitdown
#   extra except "all"/"youtube-transcription" (the only two that touch
#   youtube-transcript-api), and youtube-transcript-api is installed as
#   its own separate, unpinned package in the same pip command instead —
#   TranscriptLab never used markitdown's own YouTube-transcript feature
#   anyway (the YouTube tab calls youtube_transcript_api directly).
# v0.13.6 — Check for All Tools Update / Settings dialogs now show the
#   current installed version even when there's nothing to update to
#   (previously just "Up to date." with no way to tell which version).
#   New About section lists every managed tool with its installed
#   version, or "Not installed" — all local, no network call.
# v0.13.7 — Docling + Pandoc + pysrt/webvtt-py backend (no UI wiring
#   yet — that's v0.13.8). Verified against real installs/binaries, not
#   docs, before writing any of this:
#   - Docling gets its own dedicated venv (its base install always pulls
#     torch/torchvision/rapidocr/accelerate — confirmed no lighter path
#     exists). It has no __main__.py (confirmed against its actual wheel
#     — console_scripts only), so it's invoked via its venv's own
#     docling(.exe), not `-m docling` the way MarkItDown is. Its CLI
#     writes to a directory, not a target filename, so
#     finalize_docling_output() moves the result afterward.
#   - Pandoc installs as a binary via GitHub Releases (mirrors FFmpeg),
#     confirmed against the real 3.10.2 release and its actual Windows
#     asset names. No pypandoc dependency — called directly via
#     subprocess like every other external tool here. Real conversions
#     tested against the actual binary: -t gfm --wrap=none (not plain
#     -t markdown) is what gives clean pipe tables instead of ASCII-art
#     ones. PANDOC_EXTENSIONS corrects an earlier wrong assumption in
#     this thread — pandoc DOES read pptx/xlsx, verified by actually
#     converting real files, not just checking the docs.
#   - pysrt/webvtt-py are the new low-level SRT/VTT parser under the
#     existing subtitle_to_prose prose engine (same (text, seconds) cue
#     shape either way), with the original hand-rolled parser kept as
#     the automatic fallback if either library isn't installed.
#   - New "document-clean" polish profile: Docling/Pandoc output doesn't
#     need MarkItDown's reflow/hyphen-repair treatment (there's no fixed
#     -width wrapping to undo), so it gets paragraph-preserving cleanup
#     only — without "prose" profile's spoken-transcript noise
#     stripping, since this is real document content, not ASR output.
# v0.13.8 — wires v0.13.7's backend into the UI, plus a real bug found
#   testing v0.13.7 (a passing-audio-transcription report, "peace of
#   mind" check):
#   - TranscriptionWorker's live-transcription whisper command was the
#     ONE whisper invocation in the app missing --model_dir — it
#     silently ignored the app's own portable model cache, meaning a
#     model already downloaded via Settings would be invisibly
#     re-downloaded, and that download's tqdm progress (carriage-return
#     based) produces zero log lines for the whole transfer, identical
#     in appearance to a genuine hang. Fixed, plus a log heads-up when a
#     model genuinely isn't cached yet.
#   - Settings -> "MD Conversion Tool" (renamed from "MarkItDown..."):
#     hub dialog listing all 4 models + install status + a Select
#     button, with dedicated new Docling/Pandoc settings dialogs and a
#     minimal pysrt/webvtt-py info dialog (no install of its own).
#   - Check for All Tools Update gained Docling/Pandoc rows.
#   - MD File Generation: top "Model: Name" line (click to switch among
#     installed models), filenames get a "[modelid]" suffix, a real
#     pre-flight dialog lists any queued file the selected model can't
#     handle plus which installed models would work. Sub-window renamed
#     "MD Converter Activity". Subtitle/transcript files still always
#     use the built-in bypass regardless of model (unchanged decision).
#   - AV Transcription / YouTube Transcription: indicator renamed
#     "MD Converter (Name)", switched to double-click, and — per the
#     explicit "override the bypass for these 2 tabs" decision — now
#     routes through the selected model when it's MarkItDown (falls
#     back to the tuned built-in engine for Docling/Pandoc, whose format
#     lists don't include .srt/.vtt at all, and for pysrt_webvtt, which
#     IS that built-in engine). YouTube's path was fully in-memory, so
#     this needed a new temp-file bridge; AV's already wrote real files.
#     Filename tagging for these two tabs' outputs is deferred past this
#     version — the functional routing is the part that was explicitly
#     approved and is what's tested here.
# v0.13.9 — a full audit of every v0.13.8 Settings dialog after real-world
#   testing turned up copy-paste bugs in every single one of them:
#   - Docling's Install button read "Install MarkItDown (global)";
#     Pandoc's status line read "FFmpeg found: ..."; pysrt/webvtt-py's
#     button read "Install MarkItDown (global)" too and jumped to the
#     MarkItDown dialog with no explanation why. All three were reused
#     string keys from the templates these dialogs were built from,
#     never swapped for tool-specific ones. Fixed with dedicated strings
#     for each; pysrt/webvtt-py's redirect to MarkItDown Settings is
#     real (they install together) but now says so.
#   - A real Docling install failure (PermissionError inside pip's own
#     cache folder — Windows-specific, same category as the venv-lock
#     issue from a few versions back) led to adding --no-cache-dir to
#     every pip install this app runs.
#   - The "MD Conversion Tool" hub never refreshed after installing
#     something from one of the per-model dialogs it opens (a separate
#     Toplevel with no link back) — Pandoc could install successfully
#     and the hub would still show it as missing. Rebuilt as one card
#     per model (was a single cramped 5-column grid row, likely also
#     the cause of a "garbage characters" report) and now refreshes on
#     <FocusIn>.
#   - Comparison tab: "Done" used to appear as soon as a file's sampling
#     finished, before Phase 2 (matching it against the base folder and
#     every other queued file) had even started — misleading, since the
#     file was still actively in use. New ST_COMPARING state ("Comparing
#     ...") fills that gap; "Done" is relabeled "Finished" here and only
#     shown once Phase 2 genuinely completes for the whole batch.
# v0.13.10 — real hands-on testing of v0.13.7-9's tool installs/
#   conversions turned up several more issues, verified against real
#   binaries/logs/files before fixing, not guessed:
#   - Pandoc EPUB conversions came back full of raw <span id="...">/
#     <div class="section">-style anchor markup pandoc preserves from
#     EPUB's internal navigation IDs. Downloaded the real pandoc binary
#     and tested directly: -t gfm-raw_html (disabling the raw_html
#     extension) drops the empty anchor spans entirely, keeps every
#     span/div's real text content, and converts <img> to proper
#     markdown image syntax. Applied to every Pandoc conversion.
#   - pysrt/webvtt-py-converted subtitle files never got a [modelid]
#     filename suffix (by original design — no "external model" runs
#     for the always-on bypass). Now tagged [pysrt_webvtt] specifically
#     — that engine genuinely does the parsing (since v0.13.7), so it's
#     an accurate tag regardless of which "big document" model happens
#     to be globally selected.
#   - A Docling install that went fully silent for minutes after pip's
#     "Installing collected packages:" line (pip prints nothing during
#     the actual unpack/compile of ~100 packages including torch) looked
#     identical to a hang. _attach_stream (shared by every install flow
#     in the app) now prints a heartbeat after 15s of genuine silence.
#   - The "nothing changed" warning only ever checked the PRIMARY
#     package's version — when pysrt/webvtt-py genuinely installed
#     alongside MarkItDown while MarkItDown itself stayed the same
#     version, the app still claimed nothing happened. Now tracks the
#     extra packages too.
#   - Every per-model Settings dialog (not just the hub) now refreshes
#     on <FocusIn>, not just once at open.
#   - Docling/Pandoc dialogs had two more leftover wrong-tool strings:
#     Pandoc's "Download and install automatically" (fine wording, just
#     never Pandoc-specific) and Docling's silent gap above.
#   - A real Docling PDF conversion failed with a PermissionError INSIDE
#     Docling's own temp-file cleanup (not this app's code), on a
#     filename containing accented Portuguese characters — plausibly,
#     not confirmedly, a Docling/Windows Unicode-path issue. Defensive
#     fix either way: Docling now always receives a plain-ASCII temp
#     filename, never the real one.
#   - Comparison tab status flow refined further after hands-on testing:
#     "Transcribing..." (was "Checking..."), a new "Transcribed" state
#     for a file that's done sampling but still waiting on the rest of
#     the batch (Phase 2 is a genuinely batch-wide operation, doesn't
#     start per-file), "Comparing..." once Phase 2 actually starts for
#     the whole batch, "Done" (not "Finished") once it fully completes.
APP_NAME = "TranscriptLab"
APP_AUTHOR = "Luiz Junqueira & Claude AI"
APP_CONTACT = "USEReira.ch@gmail.com"

import os
import tempfile
import re
import sys
import json
import time
import queue
import shutil
import glob
import zipfile
import tarfile
import threading
import subprocess
import webbrowser
import urllib.request
import urllib.parse
import urllib.error
import ssl
import socket
import collections
import secrets
import difflib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from datetime import datetime

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import tkinter.font as tkfont

# ==========================================================================
# Paths / persistence
# ==========================================================================
#
# v0.11.0 PORTABILITY MODEL (item 1.2 / Q1): everything the app owns — its
# config, its dictionaries, and its managed tool installs — lives in a
# folder next to the .py (or next to the frozen .exe). Moving that whole
# folder to another drive or PC keeps the app fully working, because every
# path stored in config.json is written relative to APP_DIR and re-resolved
# against APP_DIR on load (see to_app_relative / from_app_relative below).


def app_base_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    try:
        return os.path.dirname(os.path.abspath(__file__))
    except NameError:
        return os.getcwd()


APP_DIR = Path(app_base_dir())
CONFIG_DIR = APP_DIR / "TranscriptLab_Data"
CONFIG_FILE = CONFIG_DIR / "config.json"
DICTIONARIES_FILE = CONFIG_DIR / "dictionaries.json"
ETA_HISTORY_FILE = CONFIG_DIR / "eta_history.json"
QUEUES_STATE_FILE = CONFIG_DIR / "queues_state.json"
# v0.12.0 — Comparison tab scratch space; wiped at the start/end of every
# Check run (never persisted, portable like everything else under CONFIG_DIR).
COMPARISON_TEMP_DIR = CONFIG_DIR / "temp" / "comparison"
# v0.12.1 — crash-safe partial report, written/updated as a Check run
# progresses so a real crash (not just Cancel) never loses everything.
COMPARISON_REPORTS_DIR = CONFIG_DIR / "comparison_reports"
COMPARISON_SAFETY_NET_FILE = COMPARISON_REPORTS_DIR / "safety_net_report.md"

# Legacy (pre-0.11.0) location; only used for one-time migration.
LEGACY_CONFIG_DIR = Path.home() / ".whisper_transcriber"

# All app-managed external tools live under one portable "tools" folder.
TOOLS_DIR = APP_DIR / "tools"
TOOLS_VENV_DIR = TOOLS_DIR / "venv"                # markitdown, yt-dlp, youtube-transcript-api, pysrt, webvtt-py
WHISPER_ENV_DIR = TOOLS_DIR / "whisper_env"
WHISPER_MODELS_DIR = TOOLS_DIR / "whisper_models"
FFMPEG_INSTALL_DIR = TOOLS_DIR / "ffmpeg"
# v0.13.7 — new conversion-model backends. Docling gets its own dedicated
# venv (mirrors WHISPER_ENV_DIR): its base install always pulls torch/
# torchvision/rapidocr/accelerate, too heavy and too likely to conflict
# with the lightweight shared tools venv (verified: pip install docling
# resolves cleanly on its own, but there's no lighter install path).
# Pandoc is a compiled binary, not a Python package (mirrors
# FFMPEG_INSTALL_DIR) -- no venv involved at all.
DOCLING_ENV_DIR = TOOLS_DIR / "docling_env"
PANDOC_INSTALL_DIR = TOOLS_DIR / "pandoc"

DEFAULT_WHISPER_PATHS = [
    r"C:\WhisperWorkspace\venv\Scripts\whisper.exe",
]


def to_app_relative(path):
    """Store a path relative to APP_DIR when possible, so the whole app
    folder can move to another drive/PC and keep working (item 1.2)."""
    if not path:
        return path
    try:
        p = os.path.abspath(path)
        rel = os.path.relpath(p, str(APP_DIR))
        if not rel.startswith(".."):
            return rel.replace(os.sep, "/")
    except (ValueError, OSError):
        pass
    return path


def from_app_relative(path):
    """Reverse of to_app_relative: resolve a stored path against APP_DIR
    first (portable case), falling back to the raw value (absolute paths
    from before 0.11.0, or paths outside the app folder by user choice)."""
    if not path:
        return path
    if os.path.isabs(path):
        return path
    candidate = os.path.normpath(os.path.join(str(APP_DIR), path))
    return candidate


def migrate_legacy_config_dir():
    """One-time move of the pre-0.11.0 home-folder config into the new
    app-relative TranscriptLab_Data folder (item 1.2 / Q1: config now lives
    next to the .py). Never overwrites an existing new-location file, never
    touches old global tool installs (that migration is offered separately
    in the tools Settings dialogs, item 1.5)."""
    try:
        if not LEGACY_CONFIG_DIR.exists() or CONFIG_DIR.exists():
            return
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        for name in ("config.json", "dictionaries.json", "eta_history.json"):
            src = LEGACY_CONFIG_DIR / name
            dst = CONFIG_DIR / name
            if src.exists() and not dst.exists():
                shutil.copy2(str(src), str(dst))
    except OSError:
        pass

# App icons (transparent RGBA PNG + multi-size ICO, base64). Regenerated
# from the 1024px master: cropped, white corners flood-filled to alpha.
APP_ICON_SMALL_BASE64 = (
    "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"
)

APP_ICON_LARGE_BASE64 = (
    "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"
    "YII="
)

APP_ICON_ICO_BASE64 = (
    "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"
    "4/8HuAF+TEYleBkAAAAASUVORK5CYII="
)

# --- Interface languages ---------------------------------------------------
UI_LANGUAGES = [("pt", "Português"), ("en", "English")]

# --- Audio language built-ins (code -> whisper --language param) -----------
AUDIO_LANG_OPTIONS = {
    "auto": {"param": None},
    "pt": {"param": "Portuguese"},
    "en": {"param": "English"},
    "es": {"param": "Spanish"},
}
DEFAULT_AUDIO_LANGS = ["auto", "pt", "en", "es"]

# Full Whisper language set (code -> English name). Used by the "Add languages"
# manager. Whisper's --language accepts the English name.
WHISPER_LANGUAGES = {
    "en": "English", "zh": "Chinese", "de": "German", "es": "Spanish",
    "ru": "Russian", "ko": "Korean", "fr": "French", "ja": "Japanese",
    "pt": "Portuguese", "tr": "Turkish", "pl": "Polish", "ca": "Catalan",
    "nl": "Dutch", "ar": "Arabic", "sv": "Swedish", "it": "Italian",
    "id": "Indonesian", "hi": "Hindi", "fi": "Finnish", "vi": "Vietnamese",
    "he": "Hebrew", "uk": "Ukrainian", "el": "Greek", "ms": "Malay",
    "cs": "Czech", "ro": "Romanian", "da": "Danish", "hu": "Hungarian",
    "ta": "Tamil", "no": "Norwegian", "th": "Thai", "ur": "Urdu",
    "hr": "Croatian", "bg": "Bulgarian", "lt": "Lithuanian", "la": "Latin",
    "mi": "Maori", "ml": "Malayalam", "cy": "Welsh", "sk": "Slovak",
    "te": "Telugu", "fa": "Persian", "lv": "Latvian", "bn": "Bengali",
    "sr": "Serbian", "az": "Azerbaijani", "sl": "Slovenian", "kn": "Kannada",
    "et": "Estonian", "mk": "Macedonian", "br": "Breton", "eu": "Basque",
    "is": "Icelandic", "hy": "Armenian", "ne": "Nepali", "mn": "Mongolian",
    "bs": "Bosnian", "kk": "Kazakh", "sq": "Albanian", "sw": "Swahili",
    "gl": "Galician", "mr": "Marathi", "pa": "Punjabi", "si": "Sinhala",
    "km": "Khmer", "sn": "Shona", "yo": "Yoruba", "so": "Somali",
    "af": "Afrikaans", "oc": "Occitan", "ka": "Georgian", "be": "Belarusian",
    "tg": "Tajik", "sd": "Sindhi", "gu": "Gujarati", "am": "Amharic",
    "yi": "Yiddish", "lo": "Lao", "uz": "Uzbek", "fo": "Faroese",
    "ht": "Haitian creole", "ps": "Pashto", "tk": "Turkmen", "nn": "Nynorsk",
    "mt": "Maltese", "sa": "Sanskrit", "lb": "Luxembourgish", "my": "Myanmar",
    "bo": "Tibetan", "tl": "Tagalog", "mg": "Malagasy", "as": "Assamese",
    "tt": "Tatar", "haw": "Hawaiian", "ln": "Lingala", "ha": "Hausa",
    "ba": "Bashkir", "jw": "Javanese", "su": "Sundanese",
}

TASK_KEYS = ["transcribe", "translate"]

# Output formats. 'md' is produced by TranscriptLab (not by whisper directly).
OUTPUT_FORMATS = ["txt", "srt", "vtt", "json", "tsv", "md"]
WHISPER_FORMATS = ["txt", "srt", "vtt", "json", "tsv"]   # produced by whisper
TEXT_REPLACE_FORMATS = ["txt", "srt", "vtt", "tsv", "md"]  # dict find/replace

# Catalog: (cli_name, english_only, size_mb, vram_gb, desc_key)
MODEL_CATALOG = [
    ("tiny",      False, 75,   1, "model_tiny"),
    ("tiny.en",   True,  75,   1, "model_tiny_en"),
    ("base",      False, 145,  1, "model_base"),
    ("base.en",   True,  145,  1, "model_base_en"),
    ("small",     False, 480,  2, "model_small"),
    ("small.en",  True,  480,  2, "model_small_en"),
    ("medium",    False, 1500, 5, "model_medium"),
    ("medium.en", True,  1500, 5, "model_medium_en"),
    ("turbo",     False, 1600, 6, "model_turbo"),
    ("large",     False, 2900, 10, "model_large"),
]
MODEL_INFO = {row[0]: {"english_only": row[1], "size_mb": row[2],
                       "vram_gb": row[3], "desc_key": row[4]}
              for row in MODEL_CATALOG}
ALL_MODEL_CLIS = [row[0] for row in MODEL_CATALOG]

MEDIA_EXTENSIONS = (".mkv", ".mp4", ".mp3", ".wav", ".m4a", ".webm",
                    ".avi", ".mov", ".flac", ".ogg",
                    ".opus", ".aac", ".wma", ".aiff", ".aif")

# Inputs accepted in the MD File Generation tab (what MarkItDown / our cleaner
# can handle).
MARKITDOWN_EXTENSIONS = (".pdf", ".docx", ".pptx", ".xlsx", ".xls", ".csv",
                         ".json", ".xml", ".html", ".htm", ".txt", ".md",
                         ".rtf", ".epub", ".srt", ".vtt")
SUBTITLE_EXTENSIONS = (".srt", ".vtt")

# v0.13.8 — the four selectable MD conversion models. pysrt/webvtt-py is
# listed here (not just an internal implementation detail of the
# always-on subtitle bypass from v0.13.7) because it's the model AV
# Transcription/YouTube Transcription route through when the user wants
# to keep today's tuned prose quality instead of accepting MarkItDown/
# Docling/Pandoc's raw passthrough for that content.
CONVERSION_MODEL_IDS = ("markitdown", "docling", "pandoc", "pysrt_webvtt")


def conversion_model_display_name(model_id):
    return {
        "markitdown": "MarkItDown",
        "docling": "Docling",
        "pandoc": "Pandoc",
        "pysrt_webvtt": "pysrt/webvtt-py",
    }.get(model_id, model_id)


def conversion_model_extensions(model_id):
    """Extensions this model actually converts through its own engine —
    NOT counting the always-on subtitle/transcript bypass (.srt/.vtt/
    .txt/.md convert the same tuned way regardless of which model is
    selected, per the explicit decision to keep that bypass; see
    model_supports_extension() below for how the two combine)."""
    if model_id == "markitdown":
        return set(MARKITDOWN_EXTENSIONS) - set(SUBTITLE_EXTENSIONS) - {".txt", ".md"}
    if model_id == "docling":
        return set(DOCLING_EXTENSIONS)
    if model_id == "pandoc":
        return set(PANDOC_EXTENSIONS)
    if model_id == "pysrt_webvtt":
        return set(SUBTITLE_EXTENSIONS)
    return set()


def model_supports_extension(model_id, ext, bypass_exempt=True):
    """bypass_exempt=True (the default, used by MD File Generation's
    unsupported-format check): .srt/.vtt/.txt/.md always report as
    supported, regardless of model, since they never actually reach the
    model's own engine. Pass False for contexts that care about the
    model's own real coverage (e.g. AV/YouTube tabs' routing, where
    those same extensions DO go through the selected model — see the
    "override the bypass for these 2 tabs" decision)."""
    ext = (ext or "").lower()
    if bypass_exempt and ext in (".srt", ".vtt", ".txt", ".md"):
        return True
    return ext in conversion_model_extensions(model_id)


def find_unsupported_queue_items(filepaths, model_id, installed_models):
    """v0.13.8: pre-flight scan for MD File Generation's "Start Batch
    Conversion" (per the explicit "pre-flight, not per-file" decision) —
    returns [(filepath, [other_installed_models_that_support_it]), ...]
    for every file the selected model can't handle. Subtitle/transcript
    bypass extensions never appear here (always supported)."""
    unsupported = []
    for fp in filepaths:
        ext = os.path.splitext(fp)[1].lower()
        if model_supports_extension(model_id, ext):
            continue
        alternatives = [m for m in installed_models
                       if m != model_id and model_supports_extension(m, ext)]
        unsupported.append((fp, alternatives))
    return unsupported


# Download (yt-dlp) options
DOWNLOAD_RESOLUTIONS = ["best", "2160", "1440", "1080", "720", "480", "360"]
DOWNLOAD_AUDIO_FORMATS = ["mp3", "m4a", "opus", "best"]
DOWNLOAD_CONTAINERS = ["mp4", "mkv"]

# Rate-limit caps (Feature G)
TRANSCRIBE_SOFT_CAP = 20
TRANSCRIBE_HARD_CAP = 150
DOWNLOAD_SOFT_CAP = 20
DOWNLOAD_HARD_CAP = 50

# Human-like delays between items (seconds)
YT_TRANSCRIBE_DELAY = (1.5, 3.0)
YT_DOWNLOAD_DELAY = (3.0, 8.0)
BLOCK_BACKOFF_SECONDS = 12.0

# Causes that stop the whole batch after one retry
BLOCK_CAUSES = ("rate_limited", "bot_check")

# Speed-factor (wall/audio) defaults; self-calibrate per Whisper model via a
# capped rolling average persisted across sessions (eta_history.json).
# 1.0 (realtime) was found to badly under-estimate CPU-based Whisper runs
# (e.g. a 2h video taking 8h => factor ~4.0), so the fallback before any real
# sample exists is set conservatively higher and flagged low-confidence.
DEFAULT_SPEED_FACTOR = 3.0
SPEED_FACTOR_SAMPLE_CAP = 20   # rolling-average window; keeps estimate adaptive
YT_PER_VIDEO_DEFAULT = 3.0   # near-constant transcript fetch seconds
MD_PER_FILE_DEFAULT = 0.6    # per-file conversion seconds

ST_PENDING = "pending"
ST_RUNNING = "running"
ST_DONE = "done"
ST_ERROR = "error"
ST_SKIPPED = "skipped"
ST_MEMBERS_ONLY = "members_only"   # item 12 (v0.11.0)
# v0.13.9/v0.13.10 — Comparison tab only. Phase 2 (matching a file
# against the base folder and every other queued file) is a genuinely
# batch operation — it only starts once EVERY file has finished
# sampling, not as each one individually finishes — so a file that
# finishes sampling early has to sit somewhere between "done
# transcribing" and "actively being compared" while the rest of the
# batch catches up:
#   ST_RUNNING     -> "Transcribing..." (renamed from "Checking...")
#   ST_TRANSCRIBED -> "Transcribed" — this file's own sampling is done;
#                      waiting for the whole batch to finish before
#                      Phase 2 (a genuinely batch operation) can start.
#   ST_COMPARING   -> "Comparing..." — Phase 2 is now actually running
#                      for the whole batch.
#   ST_DONE        -> "Done" — Phase 2 fully finished for the whole
#                      batch (this tab's own meaning of ST_DONE, later
#                      than every other tab's, which is why it's worth
#                      spelling out here specifically).
# Both non-terminal on purpose (excluded from ST_TERMINAL below) — real
# in-progress states, not stopping points for "how many are left" logic.
ST_TRANSCRIBED = "transcribed"
ST_COMPARING = "comparing"
ST_TERMINAL = (ST_DONE, ST_ERROR, ST_SKIPPED, ST_MEMBERS_ONLY)

FFMPEG_DOWNLOAD_URL = "https://ffmpeg.org/download.html"
# Static ffmpeg build (Windows) used by the auto-download installer.
FFMPEG_WIN_BUILD_URL = (
    "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/"
    "ffmpeg-master-latest-win64-gpl.zip"
)


# ==========================================================================
# Translations
# ==========================================================================

TRANSLATIONS = {
    "pt": {
        "window_title": APP_NAME,
        "tab_transcription": "Transcrição A/V",
        "tab_dictionary": "Dicionário de Vocabulário",
        "tab_md": "Geração de MD",
        # Menubar
        "menu_settings": "Configurações",
        "menu_about": "Sobre",
        "menu_whisper": "Whisper...",
        "menu_markitdown": "Ferramenta de conversão MD...",
        "menu_ffmpeg": "FFmpeg...",
        "menu_output_formats": "Formatos de saída...",
        "menu_general": "Geral...",
        "general_settings_title": "Configurações — Geral",
        "general_batch_section": "Proteções de lote",
        "general_warn_batch": "Avisar quando muitos vídeos forem enfileirados",
        "general_cap_batch": "Limitar lotes a 150 itens",
        "general_header_lang_section": "Idioma do cabeçalho do MD",
        "general_header_lang_pt": "Português",
        "general_header_lang_en": "Inglês",
        "menu_lan_status": "Status na Rede Local (LAN)...",
        "lan_settings_title": "Configurações — Status na Rede Local",
        "lan_intro": ("Página de status somente leitura para acompanhar este computador "
                     "a partir de outro na mesma rede local."),
        "lan_enable": "Ativar página de status na rede local",
        "lan_port_label": "Porta:",
        "lan_bind_label": "Endereço de bind:",
        "lan_token_enable": "Exigir token de acesso (?k=...)",
        "lan_regen_token": "Gerar novo token",
        "lan_running_at": "Ativo em: {url}",
        "lan_stopped": "Desativado.",
        "lan_start_failed": "Não foi possível iniciar: {err}",
        "lan_firewall_note": ("O Firewall do Windows pode bloquear conexões de entrada. "
                              "Se necessário, execute este comando como administrador:"),
        "menu_interface_language": "Idioma da interface",
        # Status indicators (linha 1)
        "dep_whisper": "Whisper",
        "dep_markitdown": "MarkItDown",
        "dep_ffmpeg": "FFmpeg",
        "dep_found": "✓",
        "dep_missing": "✗",
        "dep_hint": "(clique para configurar)",
        # Main controls remaining
        "audio_language": "Idioma do áudio:",
        "ai_model": "Modelo de IA:",
        "add_languages": "Adicionar idiomas...",
        "add_model": "Adicionar modelo...",
        "task": "Tarefa:",
        "vocab_dict": "Dicionário de vocabulário:",
        "none": "(Nenhum)",
        "model_status": "Status do modelo:",
        "no_models_installed": "Nenhum modelo instalado — use 'Adicionar modelo...' para baixar um.",
        "output_folder": "Pasta de saída:",
        "same_folder": "Mesma pasta de cada arquivo",
        "fixed_folder": "Pasta fixa:",
        "browse": "Procurar...",
        # Tasks
        "task_transcribe": "Transcrever (mesmo idioma)",
        "task_translate": "Traduzir para Inglês",
        # Audio langs (built-ins)
        "audlang_auto": "Detectar automaticamente",
        "audlang_portuguese": "Português (PT-BR)",
        "audlang_english": "Inglês (EN)",
        "audlang_spanish": "Espanhol (ES)",
        # Model descriptions
        "model_tiny": "mais rápido, menor precisão",
        "model_tiny_en": "só Inglês, mais rápido",
        "model_base": "rápido, precisão básica",
        "model_base_en": "só Inglês",
        "model_small": "bom equilíbrio velocidade/precisão",
        "model_small_en": "só Inglês",
        "model_medium": "excelente precisão, mais lento",
        "model_medium_en": "só Inglês",
        "model_turbo": "rápido, ótima precisão multilíngue",
        "model_large": "máxima precisão, mais lento e pesado",
        "model_downloaded": "✓ Já baixado no cache  ({size}, ~{vram} GB VRAM recomendado)",
        "model_not_downloaded": "✗ NÃO baixado ainda  ({size} para baixar, ~{vram} GB VRAM recomendado)",
        # Output formats (dialog)
        "output_formats": "Formatos de saída (marque o que deseja manter):",
        "output_formats_title": "Formatos de saída",
        "fmt_txt": "TXT — texto puro, sem marcação de tempo. Ideal para ler/estudar.",
        "fmt_srt": "SRT — legenda com tempos. Use em players de vídeo (YouTube, VLC).",
        "fmt_vtt": "VTT — legenda para web (HTML5). Semelhante ao SRT.",
        "fmt_json": "JSON — dados completos (tempos por palavra/segmento) para uso técnico.",
        "fmt_tsv": "TSV — tabela (início, fim, texto) para abrir em Excel/planilhas.",
        "fmt_md": "MD — transcrição limpa (prosa, sem tempos), ideal para uso com IA.",
        # Queue
        "queue_frame": "Fila de Transcrição",
        "add_files": "+ Adicionar arquivos...",
        "remove_selected": "Remover selecionado",
        "clear_queue": "Limpar fila",
        "move_up": "Mover para cima",
        "move_down": "Mover para baixo",
        "col_order": "#",
        "col_file": "Arquivo",
        "col_folder": "Pasta",
        "col_status": "Status",
        "status_pending": "Pendente",
        "status_running": "Transcrevendo...",
        "status_running_md": "Convertendo...",
        "status_done": "Concluído",
        "status_error": "Erro",
        "status_skipped": "Cancelado",
        "status_members_only": "Somente membros",
        "yt_log_members_only": "  ✗ {name}: vídeo exclusivo para membros — pulado.\n",
        # Execution
        "start_batch": "Iniciar Transcrição em Lote",
        "start_batch_md": "Iniciar Conversão em Lote",
        "cancel": "Cancelar",
        "waiting_start": "Aguardando início...",
        "open_output_folder": "Abrir pasta de saída",
        "batch_progress": "Processando {done}/{total}",
        "preparing": "preparando...",
        "elapsed": "decorrido {elapsed}",
        "eta": "ETA {eta}",
        "position": "posição {pos}",
        "batch_finished_label": "Finalizado: {done} concluído(s), {errors} erro(s)",
        # Log
        "log_frame": "Atividade do Whisper (saída em tempo real)",
        "log_frame_md": "Atividade do Conversor de MD (saída em tempo real)",
        "log_batch_start": "Lote iniciado em {time}\n",
        "log_batch_end": "\nLote finalizado em {time}\n",
        "log_canceling": "\n[CANCELANDO] Interrompendo após o arquivo atual...\n",
        "log_file_start": "\n{sep}\n[{i}/{n}] Iniciando: {name}\n{sep}\n",
        "log_probing": "Analisando duração do áudio com ffmpeg...\n",
        "log_duration_ok": "Duração detectada: {dur}\n",
        "log_duration_fail": "Não foi possível detectar a duração (ffmpeg ausente ou formato não lido); a barra mostrará apenas atividade.\n",
        "log_cmd": "Comando: {cmd}\n\n",
        "log_model_not_cached": "Modelo '{model}' ainda não está no cache local — o download pode levar vários minutos SEM nenhuma linha de log aparecer aqui (a barra de progresso do whisper não usa quebras de linha). Isso é normal, não travou.\n",
        "log_still_working": "... ainda trabalhando, nenhuma novidade é uma boa notícia (isso pode demorar vários minutos sem mostrar nada aqui) ...\n",
        "log_file_done": "\n[OK] Concluído: {name}\n",
        "log_file_error": "\n[ERRO] Falha em {name}: {e}\n",
        "log_env_broken_abort": ("Interrompendo o lote: o ambiente do Whisper existe mas não está "
                                "funcionando — o Python do qual ele depende pode ter sido movido "
                                "ou reinstalado em outro local. Abra Configurações → Whisper e "
                                "use \"Reparar ambiente\".\n"),
        "log_dict_warn": "[AVISO] Não foi possível aplicar dicionário em {path}: {e}\n",
        "log_md_make": "Gerando MD limpo a partir da legenda...\n",
        "log_md_markitdown": "Convertendo com MarkItDown: {name}\n",
        "log_download_start": "Iniciando download do modelo '{model}' ({size})...\n",
        "log_download_dest": "Destino: {dest}\n\n",
        "log_model_ok": "\n[OK] Modelo confirmado no cache local.\n",
        # Dialogs / messages
        "warn": "Aviso",
        "error": "Erro",
        "info": "Informação",
        "confirm": "Confirmar",
        "saved": "Salvo",
        "close": "Fechar",
        "err_no_files": "Adicione pelo menos um arquivo à fila.",
        "err_no_whisper": "Whisper não foi encontrado. Abra Configurações → Whisper para localizar ou instalar.",
        "err_whisper_broken": ("O ambiente do Whisper existe mas não está funcionando — o Python do "
                               "qual ele depende pode ter sido movido ou reinstalado em outro local. "
                               "Abra Configurações → Whisper e use \"Reparar ambiente\"."),
        "err_no_markitdown": "MarkItDown não foi encontrado. Abra Configurações → MarkItDown para instalá-lo.",
        "err_model_not_ready": "{model} é necessário para converter este tipo de arquivo, mas não está pronto. Configure em Configurações → Ferramenta de conversão MD.",
        "md_unsupported_title": "Alguns arquivos não são suportados",
        "md_unsupported_intro": "Os arquivos abaixo não podem ser convertidos com o modelo selecionado ({model}):",
        "md_unsupported_row": "• {name} — modelos instalados que suportam: {models}",
        "md_unsupported_none": "nenhum modelo instalado suporta este arquivo",
        "md_model_line": "Modelo: {model} {status}",
        "md_model_choose_title": "Escolher modelo de conversão",
        "md_model_choose_intro": "Escolha qual modelo instalado usar para esta conversão. Para instalar outro modelo, use Configurações → Ferramenta de conversão MD.",
        "err_markitdown_broken": ("O ambiente compartilhado (MarkItDown/yt-dlp) existe mas não está "
                                 "funcionando — o Python do qual ele depende pode ter sido movido ou "
                                 "reinstalado em outro local. Clique em \"Instalar\" em Configurações → "
                                 "MarkItDown para reconstruí-lo automaticamente."),
        "err_ytdlp_broken": ("O ambiente compartilhado (MarkItDown/yt-dlp) existe mas não está "
                            "funcionando — o Python do qual ele depende pode ter sido movido ou "
                            "reinstalado em outro local. Clique em \"Instalar\" em Configurações → "
                            "yt-dlp para reconstruí-lo automaticamente."),
        "err_no_model_selected": "Nenhum modelo de IA instalado/selecionado. Use 'Adicionar modelo...' para baixar um.",
        "err_no_format": "Selecione pelo menos um formato de saída (Configurações → Formatos de saída).",
        "err_no_fixed_dir": "Selecione a pasta de saída fixa ou troque para 'mesma pasta de cada arquivo'.",
        "warn_path_not_found": "O caminho '{path}' não foi encontrado no disco.\nDeseja tentar executar mesmo assim (ex: caso esteja no PATH do sistema)?",
        "warn_queue_locked": "Não é possível editar a fila durante o processamento.",
        "warn_item_locked": "Itens já processados ou em andamento não podem ser removidos/movidos.",
        "info_all_in_queue": "Todos os arquivos selecionados já estão na fila.",
        "dup_dialog_title": "Transcrição já existe",
        "dup_dialog_intro": "{n} arquivo(s) já têm uma transcrição (.md/.srt/.txt/.json) na mesma pasta:",
        "dup_skip_btn": "Não adicionar estes",
        "dup_proceed_btn": "Transcrever mesmo assim",
        "select_media_title": "Selecione um ou mais arquivos de mídia (pode repetir em pastas diferentes)",
        "select_doc_title": "Selecione arquivos para converter em MD",
        "media_files": "Arquivos de mídia",
        "doc_files": "Documentos suportados",
        "all_files": "Todos os arquivos",
        "select_whisper_title": "Selecione o executável do whisper",
        "select_ffmpeg_title": "Selecione o executável do ffmpeg",
        "executable": "Executável",
        "select_output_title": "Selecione a pasta de saída",
        "cancel_title": "Cancelar",
        "cancel_question": "Cancelar o lote? O arquivo atual será interrompido.",
        "exit_title": "Sair",
        "exit_question": "Um processamento está em andamento. Sair mesmo assim?",
        "finished_with_errors_title": "Concluído com erros",
        "finished_with_errors_msg": "{done} arquivo(s) concluídos, {errors} com erro. Veja o log para detalhes.",
        "finished_title": "Concluído",
        "finished_msg": "Todos os {done} arquivo(s) foram processados com sucesso.",
        "ffmpeg_missing_warn": "ffmpeg não foi encontrado. O Whisper precisa dele para ler a maioria dos formatos de áudio/vídeo, então a transcrição pode falhar. Você pode continuar mesmo assim (arquivos .wav às vezes funcionam sem ffmpeg).\n\nDeseja continuar?",
        # Settings: Whisper
        "set_whisper_title": "Configurações — Whisper",
        "set_whisper_exe": "Executável do Whisper:",
        "set_whisper_install": "Instalar Whisper (global)",
        "set_whisper_install_q": "Instalar o Whisper globalmente usando pip?\n\nComando:\n{cmd}\n\nIsto pode baixar vários GB (inclui o PyTorch) e demorar bastante. Continuar?",
        "set_whisper_found": "✓ Whisper encontrado: {path}",
        "set_whisper_missing": "✗ Whisper não encontrado neste computador.",
        "set_models_title": "Modelos de IA (instalados ficam disponíveis no menu principal):",
        "set_models_download": "Baixar modelo selecionado",
        "set_langs_title": "Idiomas do áudio disponíveis no menu principal:",
        "set_lang_add": "Adicionar →",
        "set_lang_remove": "← Remover",
        "set_lang_pick": "Idioma para adicionar:",
        "installed_tag": "  [instalado]",
        "not_installed_tag": "",
        # Settings: MarkItDown
        "set_markitdown_title": "Configurações — MarkItDown",
        "set_markitdown_about": "O MarkItDown converte documentos (PDF, DOCX, etc.) em Markdown. É usado na aba 'Geração de MD'.",
        "set_convtool_title": "Ferramenta de conversão MD",
        "set_convtool_intro": "Escolha qual modelo converter arquivos para Markdown. Formatos de legenda/transcrição (.srt/.vtt/.txt) sempre usam o motor interno do app, independente do modelo escolhido.",
        "set_convtool_active": "Modelo ativo",
        "set_convtool_select": "Selecionar",
        "set_convtool_selected": "✓ Ativo",
        "set_convtool_configure": "Configurações / Instalar",
        "set_convtool_desc_markitdown": "Documentos gerais: PDF, DOCX, PPTX, XLSX, HTML e mais.",
        "set_convtool_desc_docling": "PDF, DOCX, PPTX, XLSX, HTML — extração com melhor preservação de layout, ambiente próprio (download maior).",
        "set_convtool_desc_pandoc": "DOCX, HTML, EPUB, RTF, ODT, PPTX, XLSX, CSV — não lê PDF.",
        "set_convtool_desc_pysrt_webvtt": "Apenas legendas (.srt/.vtt) — mesmo motor já usado no bypass automático.",
        "set_docling_title": "Configurações — Docling",
        "set_docling_about": "O Docling converte documentos com boa preservação de layout (tabelas, estrutura). Ambiente próprio e pesado (inclui torch) — instalação separada do venv compartilhado.",
        "set_pandoc_title": "Configurações — Pandoc",
        "set_pandoc_about": "O Pandoc converte DOCX, HTML, EPUB, RTF, ODT, PPTX, XLSX e CSV em Markdown. Não lê PDF.",
        "set_pysrt_webvtt_title": "Configurações — pysrt/webvtt-py",
        "set_pysrt_webvtt_about": "Analisador de legendas (.srt/.vtt) instalado junto com o MarkItDown, no mesmo ambiente compartilhado — não tem instalação própria.",
        "set_pysrt_webvtt_status_ok": "✓ Instalado (junto com o MarkItDown).",
        "set_pysrt_webvtt_status_missing": "✗ Não instalado — instale o MarkItDown para obter também pysrt/webvtt-py.",
        "set_generic_install_q": "Instalar {name} usando pip?\n\nComando:\n{cmd}\n\nContinuar?",
        "set_docling_install": "Instalar Docling",
        "set_docling_found": "✓ Docling encontrado.",
        "set_docling_missing": "✗ Docling não encontrado.",
        "set_pandoc_found": "✓ Pandoc encontrado: {path}",
        "set_pysrt_webvtt_open_markitdown": "Abrir Configurações do MarkItDown (instala junto)",
        "set_markitdown_found": "✓ MarkItDown encontrado (interpretador: {py}).",
        "set_markitdown_missing": "✗ MarkItDown não encontrado.",
        "set_markitdown_broken": ("✗ O ambiente compartilhado existe mas não está funcionando — o "
                                 "Python do qual ele depende pode ter sido movido ou reinstalado em "
                                 "outro local. Clique em \"Instalar\" para reconstruí-lo."),
        "set_markitdown_install": "Instalar MarkItDown (global)",
        "set_markitdown_install_q": "Instalar o MarkItDown globalmente usando pip?\n\nComando:\n{cmd}\n\nContinuar?",
        "set_recheck": "Verificar novamente",
        "copy_link": "Copiar link",
        "set_check_updates_btn": "Verificar atualizações",
        "set_update_btn": "Atualizar",
        "set_checking_updates": "Verificando…",
        "set_up_to_date": "Atualizado.",
        "set_up_to_date_v": "Atualizado (v{version}).",
        "set_installed_unknown_version": "Instalado (versão desconhecida).",
        "about_tools_title": "Ferramentas",
        "set_update_available": "Atualização disponível: {cur} → {new}",
        "set_update_check_failed": "Não foi possível verificar — sem conexão.",
        "set_not_installed": "✗ Não instalado.",
        "set_pip_update_q": "Atualizar {name} usando pip?\n\nComando:\n{cmd}\n\nContinuar?",
        "install_done_ok_versions": "\n[OK] Concluído com sucesso. Instalado: {before} → {after}\n",
        "install_done_extra_versions": "  + {name}: {before} → {after}\n",
        "install_done_no_change": "\n[AVISO] O pip terminou sem erros, mas a versão instalada continua {version} — nenhuma versão mais nova era compatível com outro pacote já instalado neste ambiente (normalmente aparece nas linhas acima como 'Requirement already satisfied' ou um aviso de conflito). Considere atualizar o pacote conflitante manualmente ou reconstruir o ambiente.\n",
        "set_tools_venv_rebuild": "Reconstruir ambiente",
        "set_tools_venv_rebuild_q": "Isso vai apagar e recriar o ambiente compartilhado em {path} do zero, depois reinstalar MarkItDown e yt-dlp nele. Qualquer outro pacote instalado manualmente nesse ambiente será perdido. Continuar?",
        "set_tools_venv_rebuild_hint": "\n[DICA] Se a versão exata acima não conseguiu resolver, o ambiente provavelmente acumulou versões de outros pacotes (instaladas em algum momento anterior) que agora conflitam com a atualização. Use \"Reconstruir ambiente\" para começar do zero.\n",
        "set_tools_venv_rebuild_ok": "Ambiente reconstruído com sucesso. MarkItDown e yt-dlp foram reinstalados do zero.",
        "set_tools_venv_rebuild_fail": "A reconstrução do ambiente falhou. Veja o log acima para detalhes.",
        "set_open_folder": "Abrir pasta",
        "set_uninstall": "Desinstalar",
        "set_locate": "Localizar...",
        "confirm_uninstall_msg": "Remover a instalação gerenciada pelo app em:\n{path}\n\nContinuar?",
        "menu_check_all_updates": "Verificar atualizações de todas as ferramentas",
        "check_all_title": "Verificar atualizações — todas as ferramentas",
        "check_all_intro": "Clique em cada botão para verificar. As verificações só ocorrem quando solicitadas.",
        "migrate_title": "Migrar instalações existentes",
        "migrate_intro": "TranscriptLab 0.11.0 agora mantém suas ferramentas em uma pasta portátil "
                         "dentro da pasta do app. Foram encontrados itens de uma instalação anterior:",
        "migrate_item_whisper": "Whisper instalado globalmente",
        "migrate_item_markitdown": "MarkItDown/yt-dlp instalados globalmente",
        "migrate_item_models": "{n} modelo(s) Whisper no cache antigo",
        "migrate_whisper_hint": "Abra Configurações → Whisper e clique em Instalar para migrar o Whisper "
                                "para a pasta portátil.",
        "set_ffmpeg_title": "Configurações — FFmpeg",
        "set_ffmpeg_found": "✓ FFmpeg encontrado: {path}",
        "set_ffmpeg_missing": "✗ FFmpeg não encontrado.",
        "ffmpeg_locate": "Localizar...",
        "ffmpeg_open_folder": "Abrir pasta",
        "set_ffmpeg_install_auto": "Baixar e instalar automaticamente",
        "set_pandoc_install": "Instalar Pandoc",
        "set_ffmpeg_winget": "Instalar via winget",
        "set_ffmpeg_open_page": "Abrir página de download",
        "set_ffmpeg_auto_q": "Baixar uma versão pronta do ffmpeg e instalá-la em:\n{dest}\n\nIsto baixa ~80 MB. Continuar?",
        "set_pandoc_auto_q": "Baixar uma versão pronta do pandoc e instalá-la em:\n{dest}\n\nIsto baixa ~40 MB. Continuar?",
        "set_ffmpeg_downloading": "Baixando ffmpeg... aguarde.\n",
        "set_ffmpeg_extracting": "Extraindo...\n",
        "set_ffmpeg_done": "✓ FFmpeg instalado em: {path}\n",
        "set_ffmpeg_fail": "✗ Falha ao instalar o ffmpeg automaticamente: {e}\nUse 'Abrir página de download' para instalar manualmente.\n",
        "set_pandoc_downloading": "Baixando pandoc {tag}... aguarde.\n",
        "set_pandoc_extracting": "Extraindo...\n",
        "set_pandoc_done": "✓ Pandoc instalado em: {path}\n",
        "set_pandoc_fail": "✗ Falha ao instalar o pandoc automaticamente: {e}\n",
        "set_pandoc_no_release": "✗ Não foi possível determinar a versão mais recente do pandoc: {e}\n",
        # Settings: interface language
        "lang_english": "English",
        "lang_portuguese": "Português",
        # Install (generic)
        "install_running": "Executando, acompanhe abaixo...\n",
        "install_done_ok": "\n[OK] Concluído com sucesso.\n",
        "install_done_fail": "\n[ERRO] O processo terminou com código {code}.\n",
        "install_log_title": "Saída:",
        # About
        "about_title": "Sobre o TranscriptLab",
        "about_version": "Versão",
        "about_author": "Autor",
        "about_contact": "Contato",
        # Dictionaries
        "saved_profiles": "Perfis salvos:",
        "new": "Novo",
        "duplicate": "Duplicar",
        "delete": "Excluir",
        "edit_profile": "Editar Perfil",
        "profile_name": "Nome do perfil:",
        "priming_help": ("Texto de priming (--initial_prompt)\n"
                         "Uma frase curta e natural com os nomes próprios e termos técnicos escritos "
                         "exatamente como devem aparecer. O Whisper usa isso como uma \"dica\" para "
                         "grafar esses termos corretamente desde o começo.\n"
                         "Exemplo: A Dra. Ana Costa explica a fotossíntese, as mitocôndrias e o ciclo de Krebs."),
        "replacements_help": ("Substituições pós-transcrição (uma por linha, formato:  errado=correto)\n"
                              "Correções automáticas aplicadas DEPOIS que o Whisper termina, direto nos arquivos de "
                              "texto. Úteis para erros que se repetem sempre. Diferencia maiúsculas de minúsculas.\n"
                              "Exemplo: ciclo de crebs=ciclo de Krebs"),
        "save_profile": "Salvar Perfil",
        "dup_title": "Duplicar Perfil",
        "dup_prompt": "Nome do novo perfil:",
        "dup_suffix": " (cópia)",
        "err_dup_exists": "Já existe um perfil com esse nome.",
        "select_to_duplicate": "Selecione um perfil para duplicar.",
        "delete_question": "Excluir o perfil '{name}'?",
        "err_no_profile_name": "Dê um nome ao perfil antes de salvar.",
        "profile_saved_msg": "Perfil '{name}' salvo com sucesso.",
        # Clipping
        "clip_frame": "Transcrever apenas um trecho (opcional)",
        "clip_enable": "Transcrever somente de um ponto a outro do vídeo/áudio",
        "clip_start": "Início:",
        "clip_end": "Fim:",
        "clip_hint": "Formato H:MM:SS (ex.: 0:05:00 = 5 minutos). Deixe a caixa desmarcada para processar o arquivo inteiro.",
        "clip_needs_ffmpeg": "Este recurso precisa do ffmpeg (usado para cortar o trecho antes de transcrever). Instale o ffmpeg em Configurações → FFmpeg para habilitá-lo.",
        "err_clip_invalid": "Verifique os campos de início/fim do trecho. Use o formato H:MM:SS e garanta que o fim seja depois do início.",
        "err_clip_needs_ffmpeg": "O recorte de trecho está marcado, mas o ffmpeg não foi encontrado. Instale o ffmpeg ou desmarque essa opção.",
        "phase_preparing": "Carregando modelo e preparando o áudio... isso pode levar alguns minutos (a barra ficará completa quando a transcrição real começar).",
        "phase_transcribing_note": "Transcrevendo...",
        "partial_output_note": "Um arquivo '*.partial.txt' está sendo salvo continuamente nesta pasta como rede de segurança, caso o processo seja interrompido.",
        # MD tab
        "md_intro": "Converta vários tipos de documentos em arquivos Markdown limpos, prontos para uso com IA.",
        "md_queue_frame": "Fila de Conversão",
        # Comparison tab (v0.12.0)
        "tab_comparison": "Comparação",
        "cmp_intro": ("Antes de rodar o Whisper médio (mais lento) em um lote, verifique de forma "
                     "rápida e barata se o conteúdo de cada arquivo já existe como transcrição em "
                     "Markdown em uma pasta que você mantém, e se dois ou mais arquivos do lote são, "
                     "na verdade, a mesma fonte com nomes diferentes."),
        "cmp_queue_frame": "Fila de Comparação",
        "cmp_base_folder_frame": "Pasta Base de Comparação (opcional)",
        "cmp_base_folder_hint": ("Varrida recursivamente em busca de arquivos .md. Deixe em branco "
                                 "para comparar apenas os arquivos da fila entre si (detecção de "
                                 "duplicados)."),
        "cmp_excerpt_label": "Duração do trecho por ponto de amostragem (segundos):",
        "cmp_excerpt_live_line": "≈{total}s ({minutes} min) extraídos por arquivo em {points} pontos",
        "cmp_excerpt_live_line_short_note": "Arquivos \"Short\" (< 10 min) usam 3 pontos, proporcionalmente menos.",
        "cmp_model_label": "Modelo leve para amostragem:",
        "cmp_check_button": "Verificar",
        "cmp_results_frame": "Resultados",
        "cmp_base_matches_frame": "Correspondências na Pasta Base",
        "col_cmp_candidate": "Melhor Candidato",
        "col_cmp_confidence": "Confiança",
        "col_cmp_points": "Pontos Concordantes",
        "col_cmp_tier": "Classificação",
        "cmp_tier_likely": "Provavelmente já transcrito",
        "cmp_tier_possible": "Possível correspondência, revisar",
        "cmp_tier_none": "Nenhuma correspondência",
        "cmp_remove_selected_matches": "Remover selecionados da fila",
        "cmp_duplicates_frame": "Fontes Duplicadas na Fila",
        "cmp_cluster_label": "Grupo {n}",
        "cmp_duplicates_summary": "{n} grupo(s) de possíveis duplicados encontrados — veja o relatório para detalhes.",
        "cmp_export_button": "Exportar Relatório...",
        "cmp_export_title": "Salvar relatório de comparação",
        "cmp_export_success": "Relatório salvo em:\n{path}",
        "cmp_no_results_yet": "Clique em \"Verificar\" para comparar os arquivos da fila.",
        "cmp_no_matches_found": "Nenhuma correspondência encontrada na pasta base.",
        "cmp_no_duplicates_found": "Nenhuma fonte duplicada encontrada na fila.",
        "cmp_preview_frame": "Prévia do Trecho",
        "cmp_preview_excerpt_label": "Trecho amostrado:",
        "cmp_preview_candidate_label": "Trecho correspondente:",
        "cmp_select_row_hint": "Selecione uma linha de resultado para ver os trechos lado a lado.",
        "cmp_log_frame": "Andamento",
        "cmp_status_running": "Transcrevendo...",
        "cmp_status_transcribed": "Transcrito",
        "cmp_status_comparing": "Comparando...",
        "cmp_status_finished": "Concluído",
        "cmp_model_missing_confirm": "O modelo '{model}' (~{size}) ainda não foi baixado. Baixar agora?",
        "cmp_model_dialog_title": "Baixando modelo",
        "cmp_log_sampling": "[{i}/{n}] Amostrando {name}...\n",
        "cmp_log_point": "  Ponto {i}/{n} transcrito ({name}).\n",
        "cmp_log_scanning_base": "Lendo arquivos .md da Pasta Base de Comparação...\n",
        "cmp_log_matching": "Comparando trechos...\n",
        "cmp_log_done": "Comparação concluída.\n",
        "cmp_log_env_broken_abort": ("Interrompendo a verificação: o ambiente do Whisper existe "
                                    "mas não está funcionando — o Python do qual ele depende "
                                    "pode ter sido movido ou reinstalado em outro local. Abra "
                                    "Configurações → Whisper e use \"Reparar ambiente\".\n"),
        "cmp_log_no_base_folder": ("Pasta Base de Comparação não configurada — pulando essa etapa "
                                   "(a detecção de duplicados na fila continua normalmente).\n"),
        "cmp_err_duration": "Não foi possível obter a duração de {name}.",
        "cmp_err_no_ffmpeg": "Este recurso precisa do ffmpeg para amostrar os arquivos. Instale o ffmpeg em Configurações → FFmpeg.",
        # v0.12.1 additions
        "cmp_log_base_loaded": "{n} candidatos carregados da Pasta Base.\n",
        "cmp_log_base_cached": "Usando índice já carregado da Pasta Base ({n} candidatos).\n",
        "cmp_log_matching_file": "[{i}/{n}] Comparando {name} com {count} candidatos...\n",
        "cmp_log_phase2b_start": "Verificando {n} arquivos da fila entre si ({pairs} pares)...\n",
        "cmp_log_scenario3_start": ("Nenhum arquivo na fila — comparando apenas os arquivos da "
                                   "Pasta Base entre si (sem Whisper).\n"),
        "cmp_log_md_too_few": "Menos de 2 arquivos .md na Pasta Base — nada para comparar.\n",
        "cmp_log_md_pairs_start": "Comparando {n} arquivos MD entre si (~{pairs} pares)...\n",
        "cmp_log_md_progress": "  [{i}/{n}] pares verificados...\n",
        "cmp_safety_note_matching": "comparando arquivo {i}/{n}",
        "cmp_safety_note_loaded": "{n} candidatos carregados",
        "cmp_safety_note_pairs": "{i}/{n} pares verificados",
        "cmp_safety_status_line": "Status: {status} — {note} (atualizado às {time})",
        "cmp_safety_status_in_progress": "EM ANDAMENTO",
        "cmp_safety_status_canceled": "CANCELADO (parcial)",
        "cmp_safety_status_error": "INTERROMPIDO POR ERRO (parcial)",
        "cmp_safety_status_complete": "CONCLUÍDO",
        "cmp_stale_safety_net_warn": ("O relatório de segurança de uma verificação anterior não "
                                     "parece ter terminado normalmente:\n{path}\n\nContinuar vai "
                                     "substituí-lo. Deseja continuar?"),
        "cmp_partial_note": "Resultado parcial (interrompido antes de terminar).",
    },
    "en": {
        "window_title": APP_NAME,
        "tab_transcription": "A/V Transcription",
        "tab_dictionary": "Vocabulary Dictionary",
        "tab_md": "MD File Generation",
        "menu_settings": "Settings",
        "menu_about": "About",
        "menu_whisper": "Whisper...",
        "menu_markitdown": "MD Conversion Tool...",
        "menu_ffmpeg": "FFmpeg...",
        "menu_output_formats": "Output formats...",
        "menu_general": "General...",
        "general_settings_title": "Settings — General",
        "general_batch_section": "Batch protections",
        "general_warn_batch": "Warn when many videos are queued",
        "general_cap_batch": "Limit batches to 150 items",
        "general_header_lang_section": "MD header language",
        "general_header_lang_pt": "Portuguese",
        "general_header_lang_en": "English",
        "menu_lan_status": "LAN Status Page...",
        "lan_settings_title": "Settings — LAN Status Page",
        "lan_intro": ("Read-only status page so you can check this computer from "
                     "another one on the same local network."),
        "lan_enable": "Enable LAN status page",
        "lan_port_label": "Port:",
        "lan_bind_label": "Bind address:",
        "lan_token_enable": "Require access token (?k=...)",
        "lan_regen_token": "Generate new token",
        "lan_running_at": "Running at: {url}",
        "lan_stopped": "Disabled.",
        "lan_start_failed": "Could not start: {err}",
        "lan_firewall_note": ("Windows Firewall may block inbound connections. If needed, "
                              "run this command as administrator:"),
        "menu_interface_language": "Interface language",
        "dep_whisper": "Whisper",
        "dep_markitdown": "MarkItDown",
        "dep_ffmpeg": "FFmpeg",
        "dep_found": "✓",
        "dep_missing": "✗",
        "dep_hint": "(click to configure)",
        "audio_language": "Audio language:",
        "ai_model": "AI model:",
        "add_languages": "Add languages...",
        "add_model": "Add model...",
        "task": "Task:",
        "vocab_dict": "Vocabulary dictionary:",
        "none": "(None)",
        "model_status": "Model status:",
        "no_models_installed": "No models installed — use 'Add model...' to download one.",
        "output_folder": "Output folder:",
        "same_folder": "Same folder as each file",
        "fixed_folder": "Fixed folder:",
        "browse": "Browse...",
        "task_transcribe": "Transcribe (same language)",
        "task_translate": "Translate to English",
        "audlang_auto": "Auto-detect",
        "audlang_portuguese": "Portuguese (PT-BR)",
        "audlang_english": "English (EN)",
        "audlang_spanish": "Spanish (ES)",
        "model_tiny": "fastest, lowest accuracy",
        "model_tiny_en": "English only, fastest",
        "model_base": "fast, basic accuracy",
        "model_base_en": "English only",
        "model_small": "good speed/accuracy balance",
        "model_small_en": "English only",
        "model_medium": "excellent accuracy, slower",
        "model_medium_en": "English only",
        "model_turbo": "fast, great multilingual accuracy",
        "model_large": "maximum accuracy, slowest and heaviest",
        "model_downloaded": "✓ Already in cache  ({size}, ~{vram} GB VRAM recommended)",
        "model_not_downloaded": "✗ NOT downloaded yet  ({size} to download, ~{vram} GB VRAM recommended)",
        "output_formats": "Output formats (check what you want to keep):",
        "output_formats_title": "Output formats",
        "fmt_txt": "TXT — plain text, no timestamps. Best for reading/studying.",
        "fmt_srt": "SRT — subtitles with timing. Use in video players (YouTube, VLC).",
        "fmt_vtt": "VTT — web subtitles (HTML5). Similar to SRT.",
        "fmt_json": "JSON — full data (per-word/segment timing) for technical use.",
        "fmt_tsv": "TSV — table (start, end, text) to open in Excel/spreadsheets.",
        "fmt_md": "MD — clean transcript (prose, no timestamps), best for AI use.",
        "queue_frame": "Transcription Queue",
        "add_files": "+ Add files...",
        "remove_selected": "Remove selected",
        "clear_queue": "Clear queue",
        "move_up": "Move up",
        "move_down": "Move down",
        "col_order": "#",
        "col_file": "File",
        "col_folder": "Folder",
        "col_status": "Status",
        "status_pending": "Pending",
        "status_running": "Transcribing...",
        "status_running_md": "Converting...",
        "status_done": "Done",
        "status_error": "Error",
        "status_skipped": "Canceled",
        "status_members_only": "Members only",
        "yt_log_members_only": "  ✗ {name}: members-only video — skipped.\n",
        "start_batch": "Start Batch Transcription",
        "start_batch_md": "Start Batch Conversion",
        "cancel": "Cancel",
        "waiting_start": "Waiting to start...",
        "open_output_folder": "Open output folder",
        "batch_progress": "Processing {done}/{total}",
        "preparing": "preparing...",
        "elapsed": "elapsed {elapsed}",
        "eta": "ETA {eta}",
        "position": "position {pos}",
        "batch_finished_label": "Finished: {done} done, {errors} error(s)",
        "log_frame": "Whisper Activity (real-time output)",
        "log_frame_md": "MD Converter Activity (real-time output)",
        "log_batch_start": "Batch started at {time}\n",
        "log_batch_end": "\nBatch finished at {time}\n",
        "log_canceling": "\n[CANCELING] Stopping after the current file...\n",
        "log_file_start": "\n{sep}\n[{i}/{n}] Starting: {name}\n{sep}\n",
        "log_probing": "Probing audio duration with ffmpeg...\n",
        "log_duration_ok": "Detected duration: {dur}\n",
        "log_duration_fail": "Could not detect duration (ffmpeg missing or format unreadable); the bar will show activity only.\n",
        "log_cmd": "Command: {cmd}\n\n",
        "log_model_not_cached": "Model '{model}' isn't in the local cache yet — the download can take several minutes with NO log lines appearing here (whisper's progress bar doesn't use line breaks). That's expected, not a hang.\n",
        "log_still_working": "... still working, no news is good news (this can take several minutes with nothing shown here) ...\n",
        "log_file_done": "\n[OK] Finished: {name}\n",
        "log_file_error": "\n[ERROR] Failed on {name}: {e}\n",
        "log_env_broken_abort": ("Stopping the batch: Whisper's environment exists but isn't "
                                "working — the Python it depends on may have moved or been "
                                "reinstalled elsewhere. Open Settings → Whisper and use "
                                "\"Repair environment\".\n"),
        "log_dict_warn": "[WARNING] Could not apply dictionary to {path}: {e}\n",
        "log_md_make": "Generating clean MD from the subtitle...\n",
        "log_md_markitdown": "Converting with MarkItDown: {name}\n",
        "log_download_start": "Starting download of model '{model}' ({size})...\n",
        "log_download_dest": "Destination: {dest}\n\n",
        "log_model_ok": "\n[OK] Model confirmed in local cache.\n",
        "warn": "Warning",
        "error": "Error",
        "info": "Information",
        "confirm": "Confirm",
        "saved": "Saved",
        "close": "Close",
        "err_no_files": "Add at least one file to the queue.",
        "err_no_whisper": "Whisper was not found. Open Settings → Whisper to locate or install it.",
        "err_whisper_broken": ("Whisper's environment exists but isn't working — the Python it "
                               "depends on may have moved or been reinstalled elsewhere. Open "
                               "Settings → Whisper and use \"Repair environment\"."),
        "err_no_markitdown": "MarkItDown was not found. Open Settings → MarkItDown to install it.",
        "err_model_not_ready": "{model} is required to convert this file type, but isn't ready. Configure it in Settings → MD Conversion Tool.",
        "md_unsupported_title": "Some files aren't supported",
        "md_unsupported_intro": "The files below can't be converted with the selected model ({model}):",
        "md_unsupported_row": "• {name} — installed models that support it: {models}",
        "md_unsupported_none": "no installed model supports this file",
        "md_model_line": "Model: {model} {status}",
        "md_model_choose_title": "Choose conversion model",
        "md_model_choose_intro": "Choose which installed model to use for this conversion. To install another model, use Settings → MD Conversion Tool.",
        "err_markitdown_broken": ("The shared environment (MarkItDown/yt-dlp) exists but isn't "
                                 "working — the Python it depends on may have moved or been "
                                 "reinstalled elsewhere. Click \"Install\" under Settings → "
                                 "MarkItDown to rebuild it automatically."),
        "err_ytdlp_broken": ("The shared environment (MarkItDown/yt-dlp) exists but isn't "
                            "working — the Python it depends on may have moved or been "
                            "reinstalled elsewhere. Click \"Install\" under Settings → "
                            "yt-dlp to rebuild it automatically."),
        "err_no_model_selected": "No AI model installed/selected. Use 'Add model...' to download one.",
        "err_no_format": "Select at least one output format (Settings → Output formats).",
        "err_no_fixed_dir": "Select the fixed output folder or switch to 'same folder as each file'.",
        "warn_path_not_found": "The path '{path}' was not found on disk.\nDo you want to try running it anyway (e.g. if it's on the system PATH)?",
        "warn_queue_locked": "The queue cannot be edited during processing.",
        "warn_item_locked": "Items already processed or in progress can't be removed/moved.",
        "info_all_in_queue": "All selected files are already in the queue.",
        "dup_dialog_title": "Transcript already exists",
        "dup_dialog_intro": "{n} file(s) already have a transcript (.md/.srt/.txt/.json) in the same folder:",
        "dup_skip_btn": "Don't add these",
        "dup_proceed_btn": "Transcribe anyway",
        "select_media_title": "Select one or more media files (you can repeat across folders)",
        "select_doc_title": "Select files to convert to MD",
        "media_files": "Media files",
        "doc_files": "Supported documents",
        "all_files": "All files",
        "select_whisper_title": "Select the whisper executable",
        "select_ffmpeg_title": "Select the ffmpeg executable",
        "executable": "Executable",
        "select_output_title": "Select the output folder",
        "cancel_title": "Cancel",
        "cancel_question": "Cancel the batch? The current file will be interrupted.",
        "exit_title": "Exit",
        "exit_question": "Processing is in progress. Exit anyway?",
        "finished_with_errors_title": "Finished with errors",
        "finished_with_errors_msg": "{done} file(s) finished, {errors} with error. See the log for details.",
        "finished_title": "Finished",
        "finished_msg": "All {done} file(s) were processed successfully.",
        "ffmpeg_missing_warn": "ffmpeg was not found. Whisper needs it to read most audio/video formats, so transcription may fail. You can continue anyway (.wav files sometimes work without ffmpeg).\n\nContinue?",
        "set_whisper_title": "Settings — Whisper",
        "set_whisper_exe": "Whisper executable:",
        "set_whisper_install": "Install Whisper (global)",
        "set_whisper_install_q": "Install Whisper globally using pip?\n\nCommand:\n{cmd}\n\nThis may download several GB (includes PyTorch) and take a while. Continue?",
        "set_whisper_found": "✓ Whisper found: {path}",
        "set_whisper_missing": "✗ Whisper not found on this computer.",
        "set_models_title": "AI models (installed ones appear in the main menu):",
        "set_models_download": "Download selected model",
        "set_langs_title": "Audio languages available in the main menu:",
        "set_lang_add": "Add →",
        "set_lang_remove": "← Remove",
        "set_lang_pick": "Language to add:",
        "installed_tag": "  [installed]",
        "not_installed_tag": "",
        "set_markitdown_title": "Settings — MarkItDown",
        "set_markitdown_about": "MarkItDown converts documents (PDF, DOCX, etc.) into Markdown. It is used in the 'MD File Generation' tab.",
        "set_convtool_title": "MD Conversion Tool",
        "set_convtool_intro": "Choose which model converts files to Markdown. Subtitle/transcript formats (.srt/.vtt/.txt) always use the app's own built-in engine, regardless of the selected model.",
        "set_convtool_active": "Active model",
        "set_convtool_select": "Select",
        "set_convtool_selected": "✓ Active",
        "set_convtool_configure": "Settings / Install",
        "set_convtool_desc_markitdown": "General documents: PDF, DOCX, PPTX, XLSX, HTML, and more.",
        "set_convtool_desc_docling": "PDF, DOCX, PPTX, XLSX, HTML — extraction with better layout preservation, own environment (bigger download).",
        "set_convtool_desc_pandoc": "DOCX, HTML, EPUB, RTF, ODT, PPTX, XLSX, CSV — does not read PDF.",
        "set_convtool_desc_pysrt_webvtt": "Subtitles only (.srt/.vtt) — same engine already used by the automatic bypass.",
        "set_docling_title": "Settings — Docling",
        "set_docling_about": "Docling converts documents with strong layout preservation (tables, structure). Its own, heavy environment (includes torch) — installed separately from the shared venv.",
        "set_pandoc_title": "Settings — Pandoc",
        "set_pandoc_about": "Pandoc converts DOCX, HTML, EPUB, RTF, ODT, PPTX, XLSX, and CSV into Markdown. Does not read PDF.",
        "set_pysrt_webvtt_title": "Settings — pysrt/webvtt-py",
        "set_pysrt_webvtt_about": "Subtitle (.srt/.vtt) parser installed alongside MarkItDown, in the same shared environment — no install of its own.",
        "set_pysrt_webvtt_status_ok": "✓ Installed (alongside MarkItDown).",
        "set_pysrt_webvtt_status_missing": "✗ Not installed — install MarkItDown to also get pysrt/webvtt-py.",
        "set_generic_install_q": "Install {name} using pip?\n\nCommand:\n{cmd}\n\nContinue?",
        "set_docling_install": "Install Docling",
        "set_docling_found": "✓ Docling found.",
        "set_docling_missing": "✗ Docling not found.",
        "set_pandoc_found": "✓ Pandoc found: {path}",
        "set_pysrt_webvtt_open_markitdown": "Open MarkItDown Settings (installs together)",
        "set_markitdown_found": "✓ MarkItDown found (interpreter: {py}).",
        "set_markitdown_missing": "✗ MarkItDown not found.",
        "set_markitdown_broken": ("✗ The shared environment exists but isn't working — the Python "
                                 "it depends on may have moved or been reinstalled elsewhere. "
                                 "Click \"Install\" to rebuild it."),
        "set_markitdown_install": "Install MarkItDown (global)",
        "set_markitdown_install_q": "Install MarkItDown globally using pip?\n\nCommand:\n{cmd}\n\nContinue?",
        "set_recheck": "Re-check",
        "copy_link": "Copy link",
        "set_check_updates_btn": "Check for updates",
        "set_update_btn": "Update",
        "set_checking_updates": "Checking…",
        "set_up_to_date": "Up to date.",
        "set_up_to_date_v": "Up to date (v{version}).",
        "set_installed_unknown_version": "Installed (version unknown).",
        "about_tools_title": "Tools",
        "set_update_available": "Update available: {cur} → {new}",
        "set_update_check_failed": "Could not check — no connection.",
        "set_not_installed": "✗ Not installed.",
        "set_pip_update_q": "Update {name} using pip?\n\nCommand:\n{cmd}\n\nContinue?",
        "install_done_ok_versions": "\n[OK] Completed successfully. Installed: {before} → {after}\n",
        "install_done_extra_versions": "  + {name}: {before} → {after}\n",
        "install_done_no_change": "\n[WARNING] pip finished without errors, but the installed version is still {version} — no newer version was compatible with another package already installed in this environment (usually shows above as 'Requirement already satisfied' or a conflict warning). Consider updating the conflicting package manually, or rebuilding the environment.\n",
        "set_tools_venv_rebuild": "Rebuild environment",
        "set_tools_venv_rebuild_q": "This will delete and recreate the shared environment at {path} from scratch, then reinstall MarkItDown and yt-dlp into it. Any other package manually installed in that environment will be lost. Continue?",
        "set_tools_venv_rebuild_hint": "\n[HINT] If the exact version above still couldn't resolve, the environment has likely accumulated other packages (installed at some earlier point) that now conflict with the update. Use \"Rebuild environment\" to start fresh.\n",
        "set_tools_venv_rebuild_ok": "Environment rebuilt successfully. MarkItDown and yt-dlp were reinstalled from scratch.",
        "set_tools_venv_rebuild_fail": "Rebuilding the environment failed. See the log above for details.",
        "set_open_folder": "Open folder",
        "set_uninstall": "Uninstall",
        "set_locate": "Locate...",
        "confirm_uninstall_msg": "Remove the app-managed install at:\n{path}\n\nContinue?",
        "menu_check_all_updates": "Check all tools for updates",
        "check_all_title": "Check for updates — all tools",
        "check_all_intro": "Click each button to check. Checks only happen when requested.",
        "migrate_title": "Migrate existing installs",
        "migrate_intro": "TranscriptLab 0.11.0 now keeps its tools in a portable folder inside the "
                         "app folder. Items from a previous install were found:",
        "migrate_item_whisper": "Whisper installed globally",
        "migrate_item_markitdown": "MarkItDown/yt-dlp installed globally",
        "migrate_item_models": "{n} Whisper model(s) in the old cache",
        "migrate_whisper_hint": "Open Settings → Whisper and click Install to migrate Whisper into "
                                "the portable folder.",
        "set_ffmpeg_title": "Settings — FFmpeg",
        "set_ffmpeg_found": "✓ FFmpeg found: {path}",
        "set_ffmpeg_missing": "✗ FFmpeg not found.",
        "ffmpeg_locate": "Locate...",
        "ffmpeg_open_folder": "Open folder",
        "set_ffmpeg_install_auto": "Download and install automatically",
        "set_pandoc_install": "Install Pandoc",
        "set_ffmpeg_winget": "Install via winget",
        "set_ffmpeg_open_page": "Open download page",
        "set_ffmpeg_auto_q": "Download a ready-made ffmpeg build and install it to:\n{dest}\n\nThis downloads ~80 MB. Continue?",
        "set_pandoc_auto_q": "Download a ready-made pandoc build and install it to:\n{dest}\n\nThis downloads ~40 MB. Continue?",
        "set_ffmpeg_downloading": "Downloading ffmpeg... please wait.\n",
        "set_ffmpeg_extracting": "Extracting...\n",
        "set_ffmpeg_done": "✓ FFmpeg installed at: {path}\n",
        "set_ffmpeg_fail": "✗ Could not auto-install ffmpeg: {e}\nUse 'Open download page' to install it manually.\n",
        "set_pandoc_downloading": "Downloading pandoc {tag}... please wait.\n",
        "set_pandoc_extracting": "Extracting...\n",
        "set_pandoc_done": "✓ Pandoc installed at: {path}\n",
        "set_pandoc_fail": "✗ Could not auto-install pandoc: {e}\n",
        "set_pandoc_no_release": "✗ Could not determine the latest pandoc release: {e}\n",
        "lang_english": "English",
        "lang_portuguese": "Português",
        "install_running": "Running, follow below...\n",
        "install_done_ok": "\n[OK] Completed successfully.\n",
        "install_done_fail": "\n[ERROR] Process ended with code {code}.\n",
        "install_log_title": "Output:",
        "about_title": "About TranscriptLab",
        "about_version": "Version",
        "about_author": "Author",
        "about_contact": "Contact",
        "saved_profiles": "Saved profiles:",
        "new": "New",
        "duplicate": "Duplicate",
        "delete": "Delete",
        "edit_profile": "Edit Profile",
        "profile_name": "Profile name:",
        "priming_help": ("Priming text (--initial_prompt)\n"
                         "A short, natural sentence with the proper names and technical terms written "
                         "exactly as they should appear. Whisper uses this as a \"hint\" to spell those "
                         "terms correctly from the start.\n"
                         "Example: Dr. Ana Costa explains photosynthesis, mitochondria and the Krebs cycle."),
        "replacements_help": ("Post-transcription replacements (one per line, format:  wrong=correct)\n"
                              "Automatic corrections applied AFTER Whisper finishes, directly in the text files. "
                              "Useful for errors that repeat every time. Case-sensitive.\n"
                              "Example: krebs cycle=Krebs cycle"),
        "save_profile": "Save Profile",
        "dup_title": "Duplicate Profile",
        "dup_prompt": "New profile name:",
        "dup_suffix": " (copy)",
        "err_dup_exists": "A profile with that name already exists.",
        "select_to_duplicate": "Select a profile to duplicate.",
        "delete_question": "Delete the profile '{name}'?",
        "err_no_profile_name": "Give the profile a name before saving.",
        "profile_saved_msg": "Profile '{name}' saved successfully.",
        "clip_frame": "Transcribe only part of the file (optional)",
        "clip_enable": "Transcribe only from one point to another in the video/audio",
        "clip_start": "Start:",
        "clip_end": "End:",
        "clip_hint": "Format H:MM:SS (e.g. 0:05:00 = 5 minutes). Leave unchecked to process the whole file.",
        "clip_needs_ffmpeg": "This feature needs ffmpeg (used to cut the segment before transcribing). Install ffmpeg in Settings → FFmpeg to enable it.",
        "err_clip_invalid": "Check the start/end fields. Use the H:MM:SS format and make sure the end is after the start.",
        "err_clip_needs_ffmpeg": "Time-range clipping is checked, but ffmpeg was not found. Install ffmpeg or uncheck this option.",
        "phase_preparing": "Loading the model and preparing the audio... this can take a few minutes (the bar will fill in once real transcription starts).",
        "phase_transcribing_note": "Transcribing...",
        "partial_output_note": "A '*.partial.txt' file is being saved continuously in this folder as a safety net in case the process is interrupted.",
        "md_intro": "Convert several types of documents into clean Markdown files, ready for AI use.",
        "md_queue_frame": "Conversion Queue",
        # Comparison tab (v0.12.0)
        "tab_comparison": "Comparison",
        "cmp_intro": ("Before running whisper medium (slower) on a batch, cheaply check whether "
                     "each file's content already exists as a Markdown transcript in a folder you "
                     "maintain, and whether two or more files in the batch are actually the same "
                     "source under different names."),
        "cmp_queue_frame": "Comparison Queue",
        "cmp_base_folder_frame": "Base Comparison Folder (optional)",
        "cmp_base_folder_hint": ("Scanned recursively for .md files. Leave blank to only compare "
                                 "queue files against each other (duplicate detection)."),
        "cmp_excerpt_label": "Excerpt length per sample point (seconds):",
        "cmp_excerpt_live_line": "≈{total}s ({minutes} min) extracted per file at {points} points",
        "cmp_excerpt_live_line_short_note": "\"Short\" files (< 10 min) use 3 points, proportionally less.",
        "cmp_model_label": "Light model for sampling:",
        "cmp_check_button": "Check",
        "cmp_results_frame": "Results",
        "cmp_base_matches_frame": "Base Folder Matches",
        "col_cmp_candidate": "Best Candidate",
        "col_cmp_confidence": "Confidence",
        "col_cmp_points": "Points Agreeing",
        "col_cmp_tier": "Tier",
        "cmp_tier_likely": "Likely already transcribed",
        "cmp_tier_possible": "Possible match, review",
        "cmp_tier_none": "No match found",
        "cmp_remove_selected_matches": "Remove selected from queue",
        "cmp_duplicates_frame": "Duplicate Sources in Queue",
        "cmp_cluster_label": "Cluster {n}",
        "cmp_duplicates_summary": "{n} duplicate cluster(s) found — see the report for details.",
        "cmp_export_button": "Export Report...",
        "cmp_export_title": "Save comparison report",
        "cmp_export_success": "Report saved to:\n{path}",
        "cmp_no_results_yet": "Click \"Check\" to compare the queued files.",
        "cmp_no_matches_found": "No matches found in the base folder.",
        "cmp_no_duplicates_found": "No duplicate sources found in the queue.",
        "cmp_preview_frame": "Excerpt Preview",
        "cmp_preview_excerpt_label": "Sampled excerpt:",
        "cmp_preview_candidate_label": "Matched excerpt:",
        "cmp_select_row_hint": "Select a result row to see the excerpts side by side.",
        "cmp_log_frame": "Progress",
        "cmp_status_running": "Transcribing...",
        "cmp_status_transcribed": "Transcribed",
        "cmp_status_comparing": "Comparing...",
        "cmp_status_finished": "Done",
        "cmp_model_missing_confirm": "Model '{model}' (~{size}) isn't downloaded. Download it now?",
        "cmp_model_dialog_title": "Downloading model",
        "cmp_log_sampling": "[{i}/{n}] Sampling {name}...\n",
        "cmp_log_point": "  Point {i}/{n} transcribed ({name}).\n",
        "cmp_log_scanning_base": "Reading .md files from the Base Comparison Folder...\n",
        "cmp_log_matching": "Matching excerpts...\n",
        "cmp_log_done": "Comparison finished.\n",
        "cmp_log_env_broken_abort": ("Stopping the Check: Whisper's environment exists but isn't "
                                    "working — the Python it depends on may have moved or been "
                                    "reinstalled elsewhere. Open Settings → Whisper and use "
                                    "\"Repair environment\".\n"),
        "cmp_log_no_base_folder": ("Base Comparison Folder not configured — skipping that step "
                                   "(duplicate detection within the queue still runs normally).\n"),
        "cmp_err_duration": "Couldn't get the duration of {name}.",
        "cmp_err_no_ffmpeg": "This feature needs ffmpeg to sample the files. Install ffmpeg under Settings → FFmpeg.",
        # v0.12.1 additions
        "cmp_log_base_loaded": "{n} candidates loaded from the Base Folder.\n",
        "cmp_log_base_cached": "Reusing the already-loaded Base Folder index ({n} candidates).\n",
        "cmp_log_matching_file": "[{i}/{n}] Matching {name} against {count} candidates...\n",
        "cmp_log_phase2b_start": "Checking {n} queue files against each other ({pairs} pairs)...\n",
        "cmp_log_scenario3_start": ("No files in the queue — comparing only the Base Folder's own "
                                   "files against each other (no Whisper involved).\n"),
        "cmp_log_md_too_few": "Fewer than 2 .md files in the Base Folder — nothing to compare.\n",
        "cmp_log_md_pairs_start": "Comparing {n} MD files against each other (~{pairs} pairs)...\n",
        "cmp_log_md_progress": "  [{i}/{n}] pairs checked...\n",
        "cmp_safety_note_matching": "matching file {i}/{n}",
        "cmp_safety_note_loaded": "{n} candidates loaded",
        "cmp_safety_note_pairs": "{i}/{n} pairs checked",
        "cmp_safety_status_line": "Status: {status} — {note} (updated at {time})",
        "cmp_safety_status_in_progress": "IN PROGRESS",
        "cmp_safety_status_canceled": "CANCELED (partial)",
        "cmp_safety_status_error": "STOPPED ON ERROR (partial)",
        "cmp_safety_status_complete": "COMPLETE",
        "cmp_stale_safety_net_warn": ("The safety-net report from a previous run doesn't look "
                                     "like it finished normally:\n{path}\n\nContinuing will "
                                     "overwrite it. Continue?"),
        "cmp_partial_note": "Partial result (stopped before finishing).",
    },
}

# --- YouTube tab strings (merged in to keep the main table readable) -------
TRANSLATIONS["pt"].update({
    "tab_youtube": "Transcrição do YouTube",
    "yt_intro": "Cole um ou vários links do YouTube. O app baixa a transcrição/legenda pública de cada vídeo e gera um arquivo Markdown limpo.",
    "yt_output_info": "Este processo gera arquivos .md.",
    "yt_settings_note": "Os arquivos .srt e .txt são opcionais (marque abaixo). As opções de 'Formatos de saída' das Configurações NÃO se aplicam aqui.",
    "yt_md_required_note": "O MarkItDown é necessário para esta aba. Clique no indicador acima para instalá-lo.",
    "yt_pref_lang": "Idioma preferido da transcrição:",
    "yt_lang_auto": "Automático (melhor disponível)",
    "yt_links_label": "Cole um ou mais links do YouTube (um por linha):",
    "yt_add_links": "Adicionar à fila",
    "yt_clear_input": "Limpar campo",
    "yt_col_video": "Vídeo",
    "status_running_yt": "Baixando...",
    "yt_keep_srt": "Salvar também .srt (legenda com tempos)",
    "yt_keep_txt": "Salvar também .txt (texto puro)",
    "yt_no_valid_links": "Nenhum link do YouTube válido foi encontrado.",
    "yt_some_invalid": "{n} linha(s) ignorada(s) por não serem links válidos do YouTube.",
    "yt_need_output_dir": "Escolha primeiro uma pasta de saída.",
    "yt_log_frame": "Atividade do YouTube (saída em tempo real)",
    "yt_start": "Iniciar Download das Transcrições",
    "yt_log_fetch": "Buscando transcrição de {vid}...\n",
    "yt_generated_suffix": " (gerada automaticamente)",
    "yt_log_lang_used": "Idioma da transcrição usada: {lang}{gen}\n",
    "yt_log_lang_mismatch": "O idioma pedido ('{want}') não está disponível; foi usado '{got}'. Disponíveis: {avail}\n",
    "yt_log_wrote": "Salvo: {files}\n",
    "yt_err_no_transcript": "Este vídeo não tem legenda/transcrição disponível para baixar.",
    "yt_err_unavailable": "Vídeo indisponível, privado ou removido.",
    "yt_err_restricted": "Vídeo restrito (idade/região/membros); não é possível obter a transcrição.",
    "yt_err_blocked": "O YouTube bloqueou as requisições temporariamente. Aguarde um pouco ou adicione menos links de cada vez.",
    "yt_err_no_connection": "Sem conexão com o YouTube.",
    "yt_err_engine_missing": "O MarkItDown (e seu mecanismo do YouTube) não está instalado.",
    "yt_err_generic": "Não foi possível obter a transcrição: {e}",
})
TRANSLATIONS["en"].update({
    "tab_youtube": "YouTube Transcription",
    "yt_intro": "Paste one or several YouTube links. The app downloads each video's public transcript/subtitles and produces a clean Markdown file, ready for AI use.",
    "yt_output_info": "This process always outputs the .md file. The .srt and .txt files are optional (check below).",
    "yt_settings_note": "The 'Output formats' settings do NOT apply to this tab.",
    "yt_md_required_note": "MarkItDown is required for this tab. Click the indicator above to install it.",
    "yt_pref_lang": "Preferred transcript language:",
    "yt_lang_auto": "Auto (best available)",
    "yt_links_label": "Paste one or more YouTube links (one per line):",
    "yt_add_links": "Add to queue",
    "yt_clear_input": "Clear box",
    "yt_col_video": "Video",
    "status_running_yt": "Downloading...",
    "yt_keep_srt": "Also save .srt (subtitles with timing)",
    "yt_keep_txt": "Also save .txt (plain text)",
    "yt_no_valid_links": "No valid YouTube links were found.",
    "yt_some_invalid": "{n} line(s) ignored (not valid YouTube links).",
    "yt_need_output_dir": "Choose an output folder first.",
    "yt_log_frame": "YouTube Activity (real-time output)",
    "yt_start": "Start Transcript Download",
    "yt_log_fetch": "Fetching transcript for {vid}...\n",
    "yt_generated_suffix": " (auto-generated)",
    "yt_log_lang_used": "Transcript language used: {lang}{gen}\n",
    "yt_log_lang_mismatch": "Requested language ('{want}') is not available; used '{got}'. Available: {avail}\n",
    "yt_log_wrote": "Saved: {files}\n",
    "yt_err_no_transcript": "This video has no subtitles/transcript available to download.",
    "yt_err_unavailable": "Video unavailable, private, or removed.",
    "yt_err_restricted": "Restricted video (age/region/members); transcript can't be retrieved.",
    "yt_err_blocked": "YouTube temporarily blocked requests. Wait a bit, or add fewer links at once.",
    "yt_err_no_connection": "No connection to YouTube.",
    "yt_err_engine_missing": "MarkItDown (and its YouTube engine) is not installed.",
    "yt_err_generic": "Could not get the transcript: {e}",
})

# --- v0.8.0 additions ------------------------------------------------------
TRANSLATIONS["pt"].update({
    "tab_download": "Download do YouTube",
    # dependency indicators / menu / settings
    "dep_ytdlp": "yt-dlp",
    "menu_ytdlp": "yt-dlp...",
    "set_ytdlp_title": "Configurações do yt-dlp",
    "set_ytdlp_about": "O yt-dlp expande playlists e baixa vídeos/áudio do YouTube. "
                       "Links de vídeo único para transcrição funcionam sem ele.",
    "set_ytdlp_found": "yt-dlp encontrado e disponível.",
    "set_ytdlp_missing": "yt-dlp não encontrado. Clique em Instalar.",
    "set_ytdlp_broken": ("✗ O ambiente compartilhado existe mas não está funcionando — o "
                        "Python do qual ele depende pode ter sido movido ou reinstalado em "
                        "outro local. Clique em Instalar para reconstruí-lo."),
    "set_ytdlp_install": "Instalar / Atualizar yt-dlp",
    "set_ytdlp_install_q": "Executar:\n\n{cmd}\n\nContinuar?",
    # Feature C status / summary
    "status_cur_pos": "Posição do Vídeo Atual: {pos}",
    "status_total_transcribed": "Total Transcrito: {val}",
    "status_eta_complete": "Tempo Estimado para Concluir: {eta}",
    "eta_low_confidence_suffix": "(estimativa inicial)",
    "pct_label": "{pct}%",
    "col_length": "Duração",
    "md_col_size": "Tamanho",
    "summary_videos": "Total de Vídeos: {n}",
    "summary_total_len": "Duração Total: {dur}",
    "summary_est_transcribe": "Tempo Estimado para Transcrever: {eta}",
    "summary_est_download": "Tempo Estimado para Baixar: {eta}",
    "summary_files": "Total de Arquivos: {n}",
    "summary_total_size": "Tamanho Total: {size}",
    "summary_est_convert": "Tempo Estimado para Converter: {eta}",
    "summary_unknown_hint": "(durações desconhecidas — instale o FFmpeg/yt-dlp)",
    "est_approx_note": "≈ aproximado",
    "queue_count_near": "Na fila: {n}",
    # playlist expansion
    "yt_log_fetching_playlist": "Expandindo playlist...\n",
    "yt_playlist_mix_rejected": "Playlists do tipo \"Mix\"/rádio (infinitas) não são suportadas.",
    "yt_playlist_empty": "A playlist está vazia ou indisponível.",
    "yt_playlist_added": "{n} vídeo(s) adicionado(s) da playlist.",
    "yt_expand_error": "Não foi possível expandir a playlist: {e}",
    "yt_need_ytdlp_playlist": "Links de playlist exigem o yt-dlp. Abra Configurações → yt-dlp para instalá-lo.",
    "yt_expanding": "Expandindo playlist, aguarde...",
    # caps
    "cap_soft_title": "Aviso: muitos vídeos",
    "cap_soft_q": "Você tem {n} vídeos na fila. O YouTube pode bloquear temporariamente seu IP "
                  "por excesso de requisições quando muitos vídeos são processados em sequência.\n\n"
                  "Deseja iniciar mesmo assim?",
    "cap_soft_ok": "OK, pode iniciar",
    "cap_soft_cancel": "Cancelar",
    "cap_hard_title": "Lote acima do limite",
    "cap_hard_msg": "O lote tem {n} vídeos; o máximo é {max}. Divida em lotes menores.",
    # rate-limit
    "yt_log_backoff": "Sinal de bloqueio detectado. Aguardando antes de tentar novamente...\n",
    "yt_log_batch_stopped": "Lote interrompido para evitar bloqueio do IP. Itens restantes não processados.\n",
    "yt_block_title": "YouTube bloqueou temporariamente",
    "yt_block_dialog": "O YouTube bloqueou temporariamente seu IP (muitas requisições). "
                       "Aguarde ~24–48h, reduza o lote, aumente o atraso ou tente mais tarde.",
    # MD metadata header
    "yt_md_name": "Nome do Vídeo",
    "yt_md_duration": "Duração do Vídeo",
    "yt_md_date": "Data",
    "yt_md_link": "Link",
    "yt_md_unknown": "Desconhecido",
    # cause messages + actions
    "yt_cause_no_transcript": "Sem legenda/transcrição disponível.",
    "yt_cause_no_transcript_action": "Se isso ocorrer em muitos vídeos de uma vez, seu IP pode estar limitado.",
    "yt_cause_members": "Vídeo exclusivo para membros — exige assinatura do canal.",
    "yt_cause_private": "Vídeo privado.",
    "yt_cause_unavailable": "Vídeo indisponível, privado ou removido.",
    "yt_cause_age": "Restrito por idade; não é possível obter sem login.",
    "yt_cause_geo": "Não disponível na sua região.",
    "yt_cause_rate": "O YouTube bloqueou temporariamente seu IP (muitas requisições).",
    "yt_cause_rate_action": "Aguarde ~24–48h, reduza o lote ou aumente o atraso.",
    "yt_cause_bot": "A verificação anti-robô do YouTube está bloqueando.",
    "yt_cause_bot_action": "Atualize o yt-dlp ou tente mais tarde.",
    "yt_cause_format": "A resolução escolhida não está disponível para este vídeo.",
    "yt_cause_format_action": "Tente \"Melhor\" ou uma resolução menor.",
    "yt_cause_live": "Vídeo ao vivo/futuro, sem conteúdo para baixar ainda.",
    "yt_cause_no_conn": "Sem conexão com o YouTube.",
    "yt_cause_engine": "O mecanismo do YouTube não está instalado.",
    "yt_cause_generic": "Não foi possível concluir: {e}",
    # Download tab
    "dl_intro": "Cole links de vídeos ou de playlists do YouTube e baixe o vídeo ou apenas o áudio. "
                "Você é responsável por respeitar os termos do site e os direitos autorais.",
    "dl_resolution": "Resolução:",
    "dl_res_best": "Melhor",
    "dl_audio_only": "Apenas áudio",
    "dl_audio_format": "Formato de áudio:",
    "dl_container": "Contêiner de vídeo:",
    "dl_start": "Iniciar Download",
    "dl_log_frame": "Atividade do Download (saída em tempo real)",
    "dl_need_output_dir": "Escolha primeiro uma pasta de saída.",
    "dl_need_ytdlp": "O yt-dlp é necessário para baixar. Clique no indicador acima para instalá-lo.",
    "dl_ffmpeg_note": "O FFmpeg é necessário para mesclar vídeo+áudio e extrair áudio.",
    "dl_ffmpeg_nudge_q": "O FFmpeg não foi encontrado. Sem ele, só é possível baixar formatos progressivos "
                         "(resolução menor, sem extração de áudio). Deseja continuar mesmo assim?",
    "dl_links_label": "Cole links de vídeos ou playlists (um por linha):",
    "status_running_dl": "Baixando...",
    "dl_queue_frame": "Fila de Download",
    "dl_options": "Opções de download",
    "btn_add": "+Adicionar",
    "add_dialog_title": "Adicionar links do YouTube",
    "add_dialog_info": "Cole um ou mais links do YouTube, um por linha.\n"
                       "Você também pode colar o link de uma playlist — o aplicativo "
                       "carregará automaticamente os links dos vídeos individuais.",
})
TRANSLATIONS["pt"].update({
    # v0.9.0
    "yt_queue_frame": "Fila de Transcrição do YouTube",
    "save": "Salvar",
    "status_transcribing": "Transcrevendo...",
    "status_extracting": "Extraindo áudio...",
    "pause_every": "Pausar a cada",
    "pause_videos_for": "vídeos por",
    "pause_minutes": "minutos",
    "pause_log_start": "Pausa de {m} min após {n} vídeos (proteção contra bloqueio)...\n",
    "pause_log_tick": "  ...retomando em ~{m} min\n",
    "pause_log_resume": "Retomando.\n",
    "dl_transcribe_after": "Transcrever o vídeo após o download",
    "dl_define_whisper": "Definir Configurações do Whisper",
    "dl_whisper_intro": "Escolha o modelo, o idioma do áudio e o dicionário de vocabulário "
                        "que serão usados para transcrever os vídeos baixados. Os formatos de "
                        "saída (MD/SRT/TXT/JSON...) seguem as Configurações → Formatos de saída.",
    "dl_need_whisper": "O Whisper não foi encontrado. Abra Configurações → Whisper para localizá-lo ou instalá-lo.",
    "dl_transcribe_needs_ffmpeg": "O FFmpeg é necessário para a transcrição. Instale o FFmpeg e tente novamente.",
    "dl_whisper_must_review": "Antes de iniciar, abra \"Definir Configurações do Whisper\", confirme o modelo/idioma e clique em Salvar.",
    "dl_whisper_not_defined": "Antes de iniciar, clique em \"Definir Configurações do Whisper\" e "
                              "escolha um modelo (instalado), o idioma do áudio e o dicionário.",
    "dl_transcribe_start": "Transcrevendo {name}...\n",
    "dl_transcribe_done": "Transcrição concluída.\n",
    "dl_transcribe_error": "[AVISO] Falha na transcrição: {e}\n",
    "dl_transcribe_no_file": "[AVISO] Não foi possível localizar o arquivo baixado para transcrever.\n",
    # grabber tab
    "tab_grabber": "Coletor de Links do YouTube",
    "grab_intro": "Cole um ou mais links de playlists OU de canais/@handles do YouTube "
                  "(um por linha). O aplicativo retorna os links dos vídeos individuais.",
    "grab_input_label": "Playlists / canais (um por linha)",
    "grab_btn": "Coletar links",
    "grab_clear": "Limpar",
    "grab_mode_title_link": "Título + link",
    "grab_mode_link_only": "Somente link",
    "grab_output_label": "Vídeos encontrados",
    "grab_copy": "Copiar tudo",
    "grab_save": "Salvar em .txt",
    "grab_need_ytdlp": "O yt-dlp é necessário para esta aba. Abra Configurações → yt-dlp para instalá-lo.",
    "grab_no_input": "Cole pelo menos um link de playlist ou canal.",
    "grab_working": "Coletando links...",
    "grab_done_msg": "{n} vídeo(s) encontrado(s).",
    "grab_empty": "Nenhum vídeo encontrado.",
    "grab_error": "Falha ao coletar os links.",
    "grab_copied": "Copiado para a área de transferência.",
    "grab_saved": "Salvo em {path}",
    "grab_fetching": "Lendo: {url}",
    "grab_channel_sub": "  sublista: {name}",
    "dl_summary_transcribe_note": "+ transcrição após cada download",
})
TRANSLATIONS["en"].update({
    "tab_download": "YouTube Download",
    "dep_ytdlp": "yt-dlp",
    "menu_ytdlp": "yt-dlp...",
    "set_ytdlp_title": "yt-dlp Settings",
    "set_ytdlp_about": "yt-dlp expands playlists and downloads YouTube video/audio. "
                       "Single-video transcript links work without it.",
    "set_ytdlp_found": "yt-dlp found and available.",
    "set_ytdlp_missing": "yt-dlp not found. Click Install.",
    "set_ytdlp_broken": ("✗ The shared environment exists but isn't working — the Python "
                        "it depends on may have moved or been reinstalled elsewhere. "
                        "Click Install to rebuild it."),
    "set_ytdlp_install": "Install / Update yt-dlp",
    "set_ytdlp_install_q": "Run:\n\n{cmd}\n\nContinue?",
    "status_cur_pos": "Current Video Position: {pos}",
    "status_total_transcribed": "Total Transcribed: {val}",
    "status_eta_complete": "Estimated Time to Complete: {eta}",
    "eta_low_confidence_suffix": "(initial estimate)",
    "pct_label": "{pct}%",
    "col_length": "Length",
    "md_col_size": "Size",
    "summary_videos": "Total Videos: {n}",
    "summary_total_len": "Total Length: {dur}",
    "summary_est_transcribe": "Estimated Time to Transcribe: {eta}",
    "summary_est_download": "Estimated Time to Download: {eta}",
    "summary_files": "Total Files: {n}",
    "summary_total_size": "Total Size: {size}",
    "summary_est_convert": "Estimated Time to Convert: {eta}",
    "summary_unknown_hint": "(durations unknown — install FFmpeg/yt-dlp)",
    "est_approx_note": "≈ approximate",
    "queue_count_near": "In queue: {n}",
    "yt_log_fetching_playlist": "Expanding playlist...\n",
    "yt_playlist_mix_rejected": "Endless \"Mix\"/radio playlists are not supported.",
    "yt_playlist_empty": "The playlist is empty or unavailable.",
    "yt_playlist_added": "{n} video(s) added from the playlist.",
    "yt_expand_error": "Could not expand the playlist: {e}",
    "yt_need_ytdlp_playlist": "Playlist links require yt-dlp. Open Settings → yt-dlp to install it.",
    "yt_expanding": "Expanding playlist, please wait...",
    "cap_soft_title": "Warning: many videos",
    "cap_soft_q": "You have {n} videos in the queue. YouTube may temporarily block your IP "
                  "for too many requests when many videos are processed in a row.\n\n"
                  "Do you want to start anyway?",
    "cap_soft_ok": "OK, Do it",
    "cap_soft_cancel": "Cancel",
    "cap_hard_title": "Batch over the limit",
    "cap_hard_msg": "The batch has {n} videos; the maximum is {max}. Please split into smaller batches.",
    "yt_log_backoff": "Block signal detected. Waiting before one retry...\n",
    "yt_log_batch_stopped": "Batch stopped to avoid an IP block. Remaining items left unprocessed.\n",
    "yt_block_title": "YouTube temporarily blocked",
    "yt_block_dialog": "YouTube temporarily blocked your IP (too many requests). "
                       "Wait ~24–48h, reduce the batch, increase the delay, or try later.",
    "yt_md_name": "Video Name",
    "yt_md_duration": "Video Duration",
    "yt_md_date": "Date",
    "yt_md_link": "Link",
    "yt_md_unknown": "Unknown",
    "yt_cause_no_transcript": "No subtitles/transcript available.",
    "yt_cause_no_transcript_action": "If this fires for many videos at once, your IP may be rate-limited.",
    "yt_cause_members": "Members-only video — requires channel membership.",
    "yt_cause_private": "Private video.",
    "yt_cause_unavailable": "Video unavailable, private, or removed.",
    "yt_cause_age": "Age-restricted; can't be retrieved without sign-in.",
    "yt_cause_geo": "Not available in your region.",
    "yt_cause_rate": "YouTube temporarily blocked your IP (too many requests).",
    "yt_cause_rate_action": "Wait ~24–48h, reduce the batch, or increase the delay.",
    "yt_cause_bot": "YouTube's bot-check is blocking this.",
    "yt_cause_bot_action": "Update yt-dlp or try again later.",
    "yt_cause_format": "The chosen resolution isn't available for this video.",
    "yt_cause_format_action": "Try \"Best\" or a lower resolution.",
    "yt_cause_live": "Live/upcoming video with no downloadable content yet.",
    "yt_cause_no_conn": "No connection to YouTube.",
    "yt_cause_engine": "The YouTube engine isn't installed.",
    "yt_cause_generic": "Could not complete: {e}",
    "dl_intro": "Paste YouTube video or playlist links and download the video (with a resolution "
                "choice) or audio only. You are responsible for respecting site terms and copyright.",
    "dl_resolution": "Resolution:",
    "dl_res_best": "Best",
    "dl_audio_only": "Audio only",
    "dl_audio_format": "Audio format:",
    "dl_container": "Video container:",
    "dl_start": "Start Download",
    "dl_log_frame": "Download Activity (real-time output)",
    "dl_need_output_dir": "Choose an output folder first.",
    "dl_need_ytdlp": "yt-dlp is required to download. Click the indicator above to install it.",
    "dl_ffmpeg_note": "FFmpeg is required to merge video+audio and to extract audio.",
    "dl_ffmpeg_nudge_q": "FFmpeg was not found. Without it, only progressive formats can be downloaded "
                         "(lower resolution, no audio extraction). Continue anyway?",
    "dl_links_label": "Paste video or playlist links (one per line):",
    "status_running_dl": "Downloading...",
    "dl_queue_frame": "Download Queue",
    "dl_options": "Download options",
    "btn_add": "+Add",
    "add_dialog_title": "Add YouTube links",
    "add_dialog_info": "Paste one or more YouTube links, one per line.\n"
                       "You can also paste a playlist link — the app will automatically "
                       "load the individual video links.",
})
TRANSLATIONS["en"].update({
    # v0.9.0
    "yt_queue_frame": "YouTube Transcription Queue",
    "save": "Save",
    "status_transcribing": "Transcribing...",
    "status_extracting": "Extracting audio...",
    "pause_every": "Pause every",
    "pause_videos_for": "videos for",
    "pause_minutes": "minutes",
    "pause_log_start": "Pausing {m} min after {n} videos (rate-limit protection)...\n",
    "pause_log_tick": "  ...resuming in ~{m} min\n",
    "pause_log_resume": "Resuming.\n",
    "dl_transcribe_after": "Transcribe video after download",
    "dl_define_whisper": "Define Whisper Settings",
    "dl_whisper_intro": "Choose the model, audio language, and vocabulary dictionary used to "
                        "transcribe the downloaded videos. Output formats (MD/SRT/TXT/JSON...) "
                        "follow Settings → Output formats.",
    "dl_need_whisper": "Whisper was not found. Open Settings → Whisper to locate or install it.",
    "dl_transcribe_needs_ffmpeg": "FFmpeg is required for transcription. Install FFmpeg and try again.",
    "dl_whisper_must_review": "Before starting, open \"Define Whisper Settings\", confirm the model/language and click Save.",
    "dl_whisper_not_defined": "Before starting, click \"Define Whisper Settings\" and choose an "
                              "(installed) model, the audio language, and the dictionary.",
    "dl_transcribe_start": "Transcribing {name}...\n",
    "dl_transcribe_done": "Transcription complete.\n",
    "dl_transcribe_error": "[WARNING] Transcription failed: {e}\n",
    "dl_transcribe_no_file": "[WARNING] Could not locate the downloaded file to transcribe.\n",
    # grabber tab
    "tab_grabber": "Youtube Link Grabber",
    "grab_intro": "Paste one or more YouTube playlist OR channel/@handle links "
                  "(one per line). The app returns the individual video links.",
    "grab_input_label": "Playlists / channels (one per line)",
    "grab_btn": "Grab links",
    "grab_clear": "Clear",
    "grab_mode_title_link": "Title + link",
    "grab_mode_link_only": "Link only",
    "grab_output_label": "Videos found",
    "grab_copy": "Copy all",
    "grab_save": "Save to .txt",
    "grab_need_ytdlp": "yt-dlp is required for this tab. Open Settings → yt-dlp to install it.",
    "grab_no_input": "Paste at least one playlist or channel link.",
    "grab_working": "Grabbing links...",
    "grab_done_msg": "{n} video(s) found.",
    "grab_empty": "No videos found.",
    "grab_error": "Failed to grab links.",
    "grab_copied": "Copied to clipboard.",
    "grab_saved": "Saved to {path}",
    "grab_fetching": "Reading: {url}",
    "grab_channel_sub": "  sub-list: {name}",
    "dl_summary_transcribe_note": "+ transcription after each download",
})

# --- v0.10.0 strings -------------------------------------------------------
TRANSLATIONS["pt"].update({
    "header_include": "Incluir cabeçalho",
    "header_edit": "Editar Cabeçalho",
    "header_auto": "automático",
    "header_editor_title": "Editar Cabeçalho do MD",
    "header_editor_intro": ("Com 'automático' marcado, o aplicativo preenche o campo "
                            "sozinho. Desmarque para digitar um valor fixo (texto em "
                            "branco também é válido)."),
    "header_manual_warn_title": "Cabeçalho manual",
    "header_manual_warn_msg": ("Um ou mais campos do cabeçalho estão em modo manual "
                               "(valor fixo), e não automático. Deseja continuar mesmo "
                               "assim?\n\nClique em Cancelar para ajustar em 'Editar Cabeçalho'."),
    "log_md_clean": "Limpando transcrição em prosa fluida...\n",
    "clear_finished_title": "Limpar fila concluída?",
    "clear_finished_msg": ("A fila atual já foi processada. Deseja limpá-la antes de "
                           "adicionar os novos itens?\n\nOK: limpa a fila e adiciona os novos.\n"
                           "Cancelar: não adiciona nada."),
    "replace_queue_title": "Fila já concluída",
    "replace_queue_msg": ("Esta fila já foi processada. O que deseja fazer antes de "
                          "adicionar os novos itens?\n\nManter: mantém os itens atuais "
                          "(com erro voltam para pendente; concluídos são pulados) e "
                          "adiciona os novos.\nExcluir tudo: apaga a fila atual e adiciona "
                          "os novos."),
    "replace_queue_keep": "Manter + adicionar",
    "replace_queue_delete": "Excluir tudo + adicionar",
    "grab_sections_label": "Seções do canal / Filtros",
    "grab_sec_videos": "Vídeos",
    "grab_sec_shorts": "Shorts",
    "grab_sec_live": "Ao vivo",
    "grab_sec_podcast": "Podcast",
    "grab_exclude_members": "Excluir vídeos exclusivos para membros",
    "grab_sections_note": ("As seções valem apenas para links de canal. Excluir vídeos "
                           "de membros torna a coleta mais lenta (leitura detalhada de "
                           "cada vídeo)."),
    "model_lang_multi": "Multilíngue",
    "model_lang_en": "Inglês",
    "col_model": "Modelo",
    "col_language": "Idioma",
    "col_status": "Status",
    "set_whisper_already": "Whisper global já instalado.",
    "set_whisper_recheck": "Reverificar",
    "set_whisper_install_q2": ("O Whisper será instalado num ambiente isolado do aplicativo.\n\n"
                               "Espaço necessário: cerca de {gb} GB (PyTorch + Whisper).\n"
                               "Espaço livre: {free} GB.\nPython compatível: {py}\n\nContinuar?"),
    "install_py_none": "nenhum (será instalado automaticamente)",
    "install_py_not_standalone_note": ("⚠ Este não parece ser uma instalação dedicada do Python "
                                      "— pode pertencer a outro aplicativo e desaparecer se esse "
                                      "aplicativo for atualizado, movido ou desinstalado. Para "
                                      "maior estabilidade, considere instalar o Python 3.12 pelo "
                                      "site python.org."),
    "install_low_space": ("Espaço em disco baixo: são necessários ~{need} GB e há apenas "
                          "{free} GB livres. Deseja continuar mesmo assim?"),
    "install_manual_py": ("Não foi possível instalar automaticamente um Python compatível. "
                          "Instale o Python 3.12 (python.org) e clique em Reverificar, ou "
                          "aponte um Whisper local em Procurar."),
    "install_provision_py": "Instalando um Python compatível (3.12) via winget...",
    "install_no_compat_py": "Nenhum Python compatível (3.9–3.12) encontrado.",
    "install_provision_failed": "Falha ao obter um Python compatível automaticamente.",
    "install_using_py": "Usando Python: {py}",
    "install_creating_venv": "Criando ambiente isolado do Whisper...",
    "install_venv_failed": "Falha ao criar o ambiente isolado.",
    "install_pip_upgrade": "Atualizando o pip...",
    "install_pip_whisper": "Instalando o openai-whisper (pode baixar vários GB)...",
    "install_verifying": "Verificando a instalação (importando o whisper)...",
    "set_whisper_remove": "Remover ambiente",
    "set_whisper_broken": ("✗ O ambiente do Whisper existe em:\n{path}\n\nmas não está "
                          "funcionando — o Python do qual ele depende pode ter sido movido "
                          "ou reinstalado em outro local. Use \"Reparar ambiente\" para "
                          "recriá-lo."),
    "set_whisper_repair": "Reparar ambiente",
    "set_whisper_repair_q": ("Isto vai apagar o ambiente atual (que não está funcionando) e "
                             "recriá-lo do zero em:\n{path}\n\nPython compatível encontrado: "
                             "{py}\n\nIsto pode baixar vários GB (PyTorch + Whisper) novamente "
                             "e demorar bastante. Continuar?"),
    "set_whisper_remove_q": "Remover o ambiente do Whisper?\n\n{path}\n\nOs arquivos serão apagados.",
    "install_pick_dir": "Escolha o disco/pasta para instalar o Whisper",
    "install_pick_dir_ffmpeg": "Escolha o disco/pasta para instalar o FFmpeg",
    "install_partial_env": ("Existe um ambiente incompleto em:\n{path}\n\nDeseja apagá-lo e "
                            "recriar? (Recomendado)"),
    "set_whisper_install_q3": ("O Whisper será instalado num ambiente isolado em:\n{path}\n\n"
                               "Espaço necessário: cerca de {gb} GB (PyTorch + Whisper).\n"
                               "Espaço livre no destino: {free} GB.\nPython compatível: {py}\n\n"
                               "Continuar?"),
    "grab_mode_title_dur_link": "Título + Duração + Link",
    "grab_title_lang": "Idioma dos títulos:",
    "grab_include_duration": "Incluir duração",
    "grab_out_title": "Título do vídeo (pode ser lento)",
    "grab_out_duration": "Duração do vídeo (pode ser muito lento)",
    "grab_out_link": "Link do vídeo",
    "grab_min_dur_label": "Duração mínima ≥ (min)",
    "grab_max_dur_label": "Duração máxima ≤ (min)",
    "grab_dur_filter_forces_probe": ("Um filtro de duração está ativo: a verificação de duração "
                                     "por vídeo será executada mesmo com 'Duração do vídeo' desmarcado."),
    "grab_save_csv": "Salvar CSV",
    "grab_lang_auto": "Automático",
    "grab_lang_en": "Inglês",
    "grab_lang_pt": "Português",
    "grab_lang_es": "Espanhol",
    "grab_lang_zh": "Chinês",
    "grab_lang_fr": "Francês",
    "grab_lang_de": "Alemão",
    "set_whisper_path_warn": ("Whisper instalado, mas a pasta de scripts não está no PATH "
                              "do sistema. O aplicativo usará o caminho completo salvo.\n"),
})
TRANSLATIONS["en"].update({
    "header_include": "Include header",
    "header_edit": "Edit Header",
    "header_auto": "automatic",
    "header_editor_title": "Edit MD Header",
    "header_editor_intro": ("With 'automatic' checked, the app fills the field for you. "
                            "Uncheck it to type a fixed value (blank text is valid too)."),
    "header_manual_warn_title": "Manual header",
    "header_manual_warn_msg": ("One or more header fields are in manual (fixed-value) mode "
                               "instead of automatic. Do you want to continue anyway?\n\n"
                               "Click Cancel to adjust it in 'Edit Header'."),
    "log_md_clean": "Cleaning transcript into fluid prose...\n",
    "clear_finished_title": "Clear finished queue?",
    "clear_finished_msg": ("The current queue was already processed. Clear it before "
                           "adding the new items?\n\nOK: clears the queue and adds the new ones.\n"
                           "Cancel: nothing is added."),
    "replace_queue_title": "Queue already finished",
    "replace_queue_msg": ("This queue was already processed. What would you like to do "
                          "before adding the new items?\n\nKeep: keeps the current items "
                          "(errored ones go back to pending; done ones are skipped) and "
                          "adds the new ones.\nDelete all: clears the current queue and "
                          "adds the new ones."),
    "replace_queue_keep": "Keep + add new",
    "replace_queue_delete": "Delete all + add new",
    "grab_sections_label": "Channel sections / Filters",
    "grab_sec_videos": "Videos",
    "grab_sec_shorts": "Shorts",
    "grab_sec_live": "Live",
    "grab_sec_podcast": "Podcast",
    "grab_exclude_members": "Exclude Members Only Videos",
    "grab_sections_note": ("Sections apply only to channel links. Excluding members-only "
                           "videos makes grabbing slower (detailed per-video read)."),
    "model_lang_multi": "Multilingual",
    "model_lang_en": "English",
    "col_model": "Model",
    "col_language": "Language",
    "col_status": "Status",
    "set_whisper_already": "Global Whisper already installed.",
    "set_whisper_recheck": "Re-check",
    "set_whisper_install_q2": ("Whisper will be installed into an isolated environment "
                               "managed by the app.\n\nSpace required: about {gb} GB "
                               "(PyTorch + Whisper).\nFree space: {free} GB.\n"
                               "Compatible Python: {py}\n\nContinue?"),
    "install_py_none": "none (will be installed automatically)",
    "install_py_not_standalone_note": ("⚠ This doesn't look like a dedicated Python install — it "
                                      "may belong to another application and could disappear if "
                                      "that application is updated, moved, or uninstalled. For "
                                      "better long-term stability, consider installing Python "
                                      "3.12 from python.org."),
    "install_low_space": ("Low disk space: ~{need} GB needed but only {free} GB free. "
                          "Continue anyway?"),
    "install_manual_py": ("Could not auto-install a compatible Python. Install Python 3.12 "
                          "(python.org) and click Re-check, or point to a local Whisper "
                          "with Browse."),
    "install_provision_py": "Installing a compatible Python (3.12) via winget...",
    "install_no_compat_py": "No compatible Python (3.9-3.12) found.",
    "install_provision_failed": "Could not obtain a compatible Python automatically.",
    "install_using_py": "Using Python: {py}",
    "install_creating_venv": "Creating the isolated Whisper environment...",
    "install_venv_failed": "Failed to create the isolated environment.",
    "install_pip_upgrade": "Upgrading pip...",
    "install_pip_whisper": "Installing openai-whisper (may download several GB)...",
    "install_verifying": "Verifying the installation (importing whisper)...",
    "set_whisper_remove": "Remove environment",
    "set_whisper_broken": ("✗ Whisper's environment exists at:\n{path}\n\nbut isn't working — "
                          "the Python it depends on may have moved or been reinstalled "
                          "elsewhere. Use \"Repair environment\" to recreate it."),
    "set_whisper_repair": "Repair environment",
    "set_whisper_repair_q": ("This will delete the current (non-working) environment and "
                             "recreate it from scratch at:\n{path}\n\nCompatible Python found: "
                             "{py}\n\nThis may download several GB (PyTorch + Whisper) again "
                             "and take a while. Continue?"),
    "set_whisper_remove_q": "Remove the Whisper environment?\n\n{path}\n\nThe files will be deleted.",
    "install_pick_dir": "Choose the drive/folder to install Whisper",
    "install_pick_dir_ffmpeg": "Choose the drive/folder to install FFmpeg",
    "install_partial_env": ("An incomplete environment exists at:\n{path}\n\nDelete it and "
                            "recreate? (Recommended)"),
    "set_whisper_install_q3": ("Whisper will be installed into an isolated environment at:\n{path}"
                               "\n\nSpace required: about {gb} GB (PyTorch + Whisper).\n"
                               "Free space at destination: {free} GB.\nCompatible Python: {py}\n\n"
                               "Continue?"),
    "grab_mode_title_dur_link": "Title + Duration + Link",
    "grab_title_lang": "Title language:",
    "grab_include_duration": "Include duration",
    "grab_out_title": "Video Title (may be slow)",
    "grab_out_duration": "Video Duration (may be very slow)",
    "grab_out_link": "Video Link",
    "grab_min_dur_label": "Minimum duration ≥ (min)",
    "grab_max_dur_label": "Maximum duration ≤ (min)",
    "grab_dur_filter_forces_probe": ("A duration filter is active: the per-video duration probe "
                                     "will run even with 'Video Duration' unchecked."),
    "grab_save_csv": "Save CSV",
    "grab_lang_auto": "Automatic",
    "grab_lang_en": "English",
    "grab_lang_pt": "Portuguese",
    "grab_lang_es": "Spanish",
    "grab_lang_zh": "Chinese",
    "grab_lang_fr": "French",
    "grab_lang_de": "German",
    "set_whisper_path_warn": ("Whisper installed, but its scripts folder is not on the system "
                              "PATH. The app will use the saved full path.\n"),
})


# ---- v0.10.5 — MD polish (LLM-ready cleanup) -----------------------------
TRANSLATIONS["pt"].update({
    "md_polish_check": "Polir o MD para IA",
    "md_polish_hint": ("Corrige o que o MarkItDown herda do layout de origem: quebras de "
                       "linha no meio da frase, espaços da justificação, quebras de página, "
                       "hífens partidos e marcações de legenda. O cabeçalho de metadados "
                       "nunca é alterado."),
    "log_md_polish": "Polindo o MD para treinamento de IA...\n",
    "log_md_polish_done": "Polimento: {stats}\n",
    "log_md_polish_none": "Polimento: nada a corrigir.\n",
    "log_md_polish_suspects": ("[ATENÇÃO] {n} trecho(s) possivelmente embaralhados pelo "
                               "conversor. Nada foi adivinhado; revise à mão: {samples}\n"),
    "log_md_polish_guard": ("[ATENÇÃO] A reorganização de parágrafos foi descartada por "
                            "segurança (risco de perda de texto). O conteúdo original "
                            "foi mantido.\n"),
    "log_md_polish_error": "[AVISO] O polimento falhou ({e}); o MD foi mantido como estava.\n",
    "polish_stat_joined": "{n} linhas reunidas",
    "polish_stat_pages_joined": "{n} parágrafos religados entre páginas",
    "polish_stat_pages": "{n} quebras de página",
    "polish_stat_page_numbers": "{n} números de página removidos",
    "polish_stat_noise": "{n} marcações de legenda removidas",
    "polish_stat_entities": "{n} entidades HTML convertidas",
    "polish_stat_headings": "{n} títulos marcados",
    "polish_stat_hyphens": "hífens restaurados: {list}",
    "polish_stat_fenced": "blocos de código preservados",
})

TRANSLATIONS["en"].update({
    "md_polish_check": "Polish MD for AI",
    "md_polish_hint": ("Fixes what MarkItDown inherits from the source layout: line breaks "
                       "in mid-sentence, justification spaces, page breaks, hyphens split "
                       "across lines and caption marks. The metadata header is never "
                       "touched."),
    "log_md_polish": "Polishing the MD for AI training...\n",
    "log_md_polish_done": "Polish: {stats}\n",
    "log_md_polish_none": "Polish: nothing to fix.\n",
    "log_md_polish_suspects": ("[ATTENTION] {n} passage(s) possibly scrambled by the "
                               "converter. Nothing was guessed; please review by hand: "
                               "{samples}\n"),
    "log_md_polish_guard": ("[ATTENTION] Paragraph re-flow was discarded as a safety "
                            "measure (risk of losing text). The original content was "
                            "kept.\n"),
    "log_md_polish_error": "[WARNING] Polish failed ({e}); the MD was left as it was.\n",
    "polish_stat_joined": "{n} lines rejoined",
    "polish_stat_pages_joined": "{n} paragraphs rejoined across pages",
    "polish_stat_pages": "{n} page breaks",
    "polish_stat_page_numbers": "{n} page numbers removed",
    "polish_stat_noise": "{n} caption marks removed",
    "polish_stat_entities": "{n} HTML entities converted",
    "polish_stat_headings": "{n} headings marked",
    "polish_stat_hyphens": "hyphens restored: {list}",
    "polish_stat_fenced": "code blocks preserved",
})


# ---- v0.11.01 items 1/2/3 — timestamp anchors, repetition collapse -------
TRANSLATIONS["pt"].update({
    "keep_timestamps_check": "Manter marcações de tempo no MD",
    "polish_stat_repeats": "{n} repetições consecutivas removidas",
})

TRANSLATIONS["en"].update({
    "keep_timestamps_check": "Keep time markers in MD",
    "polish_stat_repeats": "{n} consecutive repeats removed",
})


# ==========================================================================
# Config / pure utilities (testable without GUI)
# ==========================================================================

def ensure_config_dir():
    migrate_legacy_config_dir()
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    TOOLS_DIR.mkdir(parents=True, exist_ok=True)


def load_json(path, default):
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return default
    return default


def save_json(path, data):
    ensure_config_dir()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _is_windows_store_stub(path):
    """The Microsoft Store 'python.exe' alias in WindowsApps is a stub that
    silently redirects to the Store (or a sandboxed install pip can't see).
    It passes os.path.exists but must never be used as an install/probe
    target (item 1.1 failure (b) root cause)."""
    try:
        return "windowsapps" in os.path.abspath(path).lower()
    except Exception:
        return False


def find_python_executable():
    """A Python interpreter usable for pip / -m markitdown. Avoids a frozen
    exe and avoids the Windows Store alias stub (item 1.1/1.3)."""
    exe = sys.executable or ""
    if (exe and os.path.basename(exe).lower().startswith("python")
            and not _is_windows_store_stub(exe)):
        return exe
    for name in ("python", "python3", "py"):
        w = shutil.which(name)
        if w and not _is_windows_store_stub(w):
            return w
    return exe or "python"


def _path_in_dir(path, directory):
    try:
        a = os.path.normcase(os.path.abspath(path))
        b = os.path.normcase(os.path.abspath(directory))
        return a == b or a.startswith(b + os.sep)
    except Exception:
        return False


def _is_untrusted_whisper_location(path):
    """v0.11.0 (item 1.2/1.6): a whisper.bat/whisper next to the app is now
    TRUSTED when it lives inside the app-managed tools/ folder (that's where
    the portable install puts it). It's still untrusted if it's directly in
    the app folder itself or the CWD but NOT inside tools/ — that pattern is
    the historical false-positive this check exists to catch."""
    if _path_in_dir(path, str(TOOLS_DIR)):
        return False
    return (_path_in_dir(path, app_base_dir())
            or _path_in_dir(path, os.getcwd()))


def venv_python_launches(env_dir, timeout=10):
    """v0.12.2: cheap venv-health check — can the venv's OWN python.exe
    even start up? Catches a venv whose internal base-interpreter
    reference has gone stale (the Python used to create it was moved or
    reinstalled elsewhere — surfaces as 'No Python at ...' when whisper.exe
    tries to launch) without paying for a full whisper/torch import. Just
    interpreter startup, so this is safe to run before every batch start,
    not only at app launch."""
    py = venv_python(env_dir)
    if not os.path.exists(py):
        return False
    try:
        proc = subprocess.run([py, "-c", "pass"], stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, timeout=timeout,
                              **subprocess_hidden_window_kwargs())
        return proc.returncode == 0
    except Exception:
        return False


def is_environment_fatal_output(text):
    """v0.12.4: recognizes subprocess output meaning 'the Python
    environment itself is broken', not just this one file — e.g. a venv
    launcher's 'No Python at ...' when its base interpreter has moved or
    been reinstalled elsewhere. A second, REACTIVE line of defense next
    to the proactive venv_python_launches() check above: this doesn't
    depend on any theory about exactly how a given launcher fails being
    correct (item 1's first fix relied on one such theory and had a gap
    in practice — a differently-located/named install bypassed the
    health check's location assumption entirely) — it just recognizes
    the failure from the actual output of a real invocation, the moment
    it happens, so a worker can stop a whole batch instead of repeating
    an identical failure on every remaining item."""
    lowered = (text or "").lower()
    return "no python at" in lowered


class EnvironmentBrokenError(RuntimeError):
    """Raised instead of a plain RuntimeError when a subprocess's own
    output shows the Python environment itself is broken (v0.12.4,
    detected via is_environment_fatal_output) — signals the calling
    worker to stop the whole batch rather than continuing to retry an
    identical failure on every remaining item."""
    pass


def _venv_root_for_exe(exe_path):
    """If exe_path sits in a folder that also has its own Scripts/python.exe
    (or bin/python on POSIX) sibling — i.e. exe_path lives inside SOME
    Python venv's Scripts/bin directory — returns that venv's root folder
    (two levels up). Otherwise None.

    v0.12.4: this used to be named _managed_venv_root_for_exe and also
    required exe_path be inside THIS app's own TOOLS_DIR, on the theory
    that a health check has no basis to declare a non-app-managed install
    'broken'. That reasoning silently defeated the whole health-check fix
    in practice: TOOLS_DIR is computed from this build's app_base_dir(),
    so an install created by an older app version (or living under a
    differently-named/renamed folder — the exact reported case, a
    'TranscriptLab_Tools' folder the current build doesn't recognize as
    its own 'tools') sits outside it while still being exactly the same
    kind of venv. Whether a venv's own interpreter still launches is a
    purely structural, provenance-independent question — if it won't
    start, nothing depending on it can possibly work either way,
    regardless of who created it or what its parent folder is named — so
    the location restriction added a real failure mode for no actual
    safety benefit."""
    if not exe_path:
        return None
    scripts_dir = os.path.dirname(os.path.abspath(exe_path))
    env_dir = os.path.dirname(scripts_dir)
    if os.path.exists(venv_python(env_dir)):
        return env_dir
    return None


def whisper_env_health(env_dir):
    """v0.12.2: 'missing' (no whisper.exe at all), 'broken' (files present
    but the venv's own interpreter won't launch — the stale-base-Python
    case), or 'ok' (launches). Distinct from find_managed_whisper(), which
    only ever answers the file-existence question — used unchanged
    elsewhere (e.g. enabling the Remove-environment button for a broken
    env, which should still be removable)."""
    if not find_managed_whisper(env_dir):
        return "missing"
    if not venv_python_launches(env_dir):
        return "broken"
    return "ok"


def validate_whisper_executable(path):
    """Confirm `path` is really Whisper by running it with --help."""
    if not path or not os.path.exists(path):
        return False
    try:
        proc = subprocess.run([path, "--help"], stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, text=True,
                              encoding="utf-8", errors="replace", timeout=120,
                              **subprocess_hidden_window_kwargs())
    except Exception:
        return False
    out = (proc.stdout or "").lower()
    return proc.returncode == 0 and ("--model" in out or "transcribe" in out
                                     or "whisper" in out)


def python_scripts_dirs(python_exe=None):
    """Likely Scripts/bin dirs where `pip install` drops console scripts."""
    dirs = []
    try:
        import sysconfig
        for key in ("scripts", "purelib"):
            try:
                d = sysconfig.get_path(key)
                if d:
                    dirs.append(d if key == "scripts"
                                else os.path.join(os.path.dirname(d), "Scripts"))
            except Exception:
                pass
    except Exception:
        pass
    if python_exe:
        base = os.path.dirname(os.path.abspath(python_exe))
        dirs += [base, os.path.join(base, "Scripts")]
    seen, out = set(), []
    for d in dirs:
        if d and d not in seen and os.path.isdir(d):
            seen.add(d)
            out.append(d)
    return out


WHISPER_MIN_PY = (3, 9)
WHISPER_MAX_PY = (3, 12)
WHISPER_REQUIRED_GB = 3.5

# v0.11.0 (item 1.2): all four tools install under one portable tools/
# folder next to the app. `chosen_dir` (from "Install...") is honored as
# the PARENT the tools/ folder is created under, so a user picking a
# different drive still gets one coherent, movable install.


def resolve_tools_root(chosen_dir=None):
    if not chosen_dir:
        return TOOLS_DIR
    chosen = os.path.abspath(chosen_dir)
    if _path_in_dir(chosen, str(APP_DIR)) or os.path.normcase(chosen) == os.path.normcase(str(APP_DIR)):
        return TOOLS_DIR
    return Path(chosen) / "TranscriptLab_Tools"


def resolve_ffmpeg_dir(chosen_dir=None):
    return str(resolve_tools_root(chosen_dir) / "ffmpeg")


def resolve_whisper_env_dir(chosen_dir=None):
    return str(resolve_tools_root(chosen_dir) / "whisper_env")


def resolve_venv_dir(chosen_dir=None):
    return str(resolve_tools_root(chosen_dir) / "venv")


def resolve_whisper_models_dir(chosen_dir=None):
    return str(resolve_tools_root(chosen_dir) / "whisper_models")


def venv_python(env_dir):
    env_dir = Path(env_dir)
    return str(env_dir / ("Scripts" if os.name == "nt" else "bin")
               / ("python.exe" if os.name == "nt" else "python"))


def venv_whisper(env_dir):
    env_dir = Path(env_dir)
    return str(env_dir / ("Scripts" if os.name == "nt" else "bin")
               / ("whisper.exe" if os.name == "nt" else "whisper"))


def whisper_env_dir_from_cfg(cfg):
    """Where the whisper venv actually lives: the explicitly saved
    whisper_env_dir if present, otherwise derived from whatever
    whisper_path is configured — even a fully custom/manual install
    outside this app's own tools folder — falling back to this build's
    default managed location only if neither gives a real answer.

    v0.13.1: this used to be duplicated inline (worse) inside "Check for
    All Tools Update", which skipped the whisper_path-derived fallback
    entirely and so reported a perfectly working custom Whisper install
    as "Not installed". Now it's the one place this is computed, reused
    by both that dialog and Settings -> Whisper.

    v0.13.7: renamed from resolve_whisper_env_dir (name collision —
    resolve_whisper_env_dir(chosen_dir=None) already existed above for a
    completely different purpose, "where should a NEW venv go under a
    chosen custom install root". Same name, incompatible signatures:
    Python silently let the later definition win, so the one remaining
    real call site of the OLDER function (installing Whisper to a
    custom folder) was quietly passing a plain directory string into
    THIS function's cfg.get(...) calls — an AttributeError waiting to
    happen the first time anyone actually used that flow. Never hit in
    testing because none of the tests exercised that specific path."""
    stored = cfg.get("whisper_env_dir")
    if stored:
        return from_app_relative(stored)
    saved_wp = cfg.get("whisper_path")
    if saved_wp:
        derived = _venv_root_for_exe(from_app_relative(saved_wp))
        if derived:
            return derived
    return str(WHISPER_ENV_DIR)


def venv_can_import_whisper(env_dir):
    try:
        rc = subprocess.run([venv_python(env_dir), "-c", "import whisper"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            timeout=180, **subprocess_hidden_window_kwargs()).returncode
        return rc == 0
    except Exception:
        return False


def _py_version_tuple(python_exe):
    try:
        out = subprocess.run(
            [python_exe, "-c", "import sys;print('%d.%d' % sys.version_info[:2])"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
            timeout=15, **subprocess_hidden_window_kwargs()).stdout.strip()
        a, b = out.split(".")
        return (int(a), int(b))
    except Exception:
        return None


def _py_is_whisper_compatible(python_exe):
    v = _py_version_tuple(python_exe)
    return bool(v and WHISPER_MIN_PY <= v <= WHISPER_MAX_PY)


def _looks_like_standalone_python_install(path):
    """v0.12.4: does this Python sit directly under one of the well-known,
    STANDARD python.org installer roots — as opposed to being embedded
    inside some OTHER application's own data/runtime folder, which can
    use a similar-looking folder name (e.g. 'python312') without being an
    independently-maintained install at all. Checked by actual root-
    directory membership, matching the same 3 roots the standard-
    location scan below already searches — not by folder-name pattern,
    which a bundled runtime can trivially share."""
    if os.name != "nt":
        return False
    local = os.environ.get("LOCALAPPDATA", "")
    pf = os.environ.get("ProgramFiles", r"C:\Program Files")
    roots = [r for r in (os.path.join(local, "Programs", "Python") if local else "",
                        pf, os.path.join(local, "Python") if local else "") if r]
    return any(_path_in_dir(path, root) for root in roots)


def _candidate_pythons():
    cands = []
    if getattr(sys, "executable", None) and not getattr(sys, "frozen", False):
        cands.append(sys.executable)
    try:
        out = subprocess.run(["py", "-0p"], stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL, text=True, timeout=15,
                             **subprocess_hidden_window_kwargs()).stdout
        for line in out.splitlines():
            mt = re.search(r"([A-Za-z]:\\[^\r\n]+?python\.exe)", line)
            if mt:
                cands.append(mt.group(1).strip())
    except Exception:
        pass
    for name in ("python3.12", "python3.11", "python3.10", "python3.9",
                 "python3", "python"):
        w = shutil.which(name)
        if w:
            cands.append(w)
    if os.name == "nt":
        local = os.environ.get("LOCALAPPDATA", "")
        pf = os.environ.get("ProgramFiles", r"C:\Program Files")
        for root in (os.path.join(local, "Programs", "Python"), pf,
                     os.path.join(local, "Python")):
            try:
                for sub in glob.glob(os.path.join(root, "*", "python.exe")):
                    cands.append(sub)
            except Exception:
                pass
    seen, out = set(), []
    for c in cands:
        key = os.path.normcase(os.path.abspath(c)) if c else c
        if c and key not in seen and os.path.exists(c):
            seen.add(key)
            out.append(c)
    # v0.12.4: a dedicated, standalone install is preferred over anything
    # else, regardless of discovery order — sys.executable in particular
    # can silently be another application's own bundled/private Python
    # (this app was apparently being launched BY a Python interpreter
    # embedded inside a completely unrelated app's data folder, which
    # then became the base for a brand-new venv purely because it
    # happened to be checked first). A venv built on another app's
    # private runtime is fragile in exactly the way that broke Whisper
    # the first time — if THAT app is later updated, moved, or removed,
    # this app's own tools break again for a new but identical reason.
    # A stable sort keeps each tier's original relative discovery order.
    out.sort(key=lambda p: 0 if _looks_like_standalone_python_install(p) else 1)
    return out


def find_compatible_python():
    for c in _candidate_pythons():
        if _py_is_whisper_compatible(c):
            return c
    return None


def free_gb(path):
    try:
        p = str(path)
        while p and not os.path.isdir(p):
            p = os.path.dirname(p)
        return shutil.disk_usage(p or os.getcwd()).free / (1024 ** 3)
    except Exception:
        return None


def find_managed_whisper(env_dir=None):
    candidates = []
    if env_dir:
        candidates.append(env_dir)
    candidates.append(str(WHISPER_ENV_DIR))
    for d in candidates:
        cand = venv_whisper(d)
        if os.path.exists(cand):
            return cand
    return None


def winget_available():
    return shutil.which("winget") is not None


def find_global_whisper(python_exe=None):
    managed = find_managed_whisper()
    if managed:
        # v0.12.2: managed files existing isn't enough — this function's
        # purpose is finding something that actually works, so a broken
        # venv (stale base-Python reference) must fall through rather than
        # being handed back as if it were fine.
        env_dir = _venv_root_for_exe(managed)
        if env_dir is None or venv_python_launches(env_dir):
            return managed
    names = ("whisper.exe", "whisper") if os.name == "nt" else ("whisper",)
    dirs = list(python_scripts_dirs(python_exe))
    for c in _candidate_pythons():
        dirs += python_scripts_dirs(c)
    if os.name == "nt":
        local = os.environ.get("LOCALAPPDATA", "")
        for sub in glob.glob(os.path.join(local, "Python", "*", "Scripts")):
            dirs.append(sub)
    seen = set()
    for d in dirs:
        key = os.path.normcase(os.path.abspath(d)) if d else d
        if not d or key in seen:
            continue
        seen.add(key)
        for n in names:
            cand = os.path.join(d, n)
            if (os.path.exists(cand) and not _is_untrusted_whisper_location(cand)
                    and validate_whisper_executable(cand)):
                return cand
    for n in ("whisper", "whisper.exe"):
        w = shutil.which(n)
        if w and not _is_untrusted_whisper_location(w) and validate_whisper_executable(w):
            return w
    return None


def whisper_scripts_dir_on_path(python_exe=None):
    """True if the Scripts dir that holds a global whisper is on PATH."""
    path_dirs = [os.path.normcase(os.path.abspath(p))
                 for p in (os.environ.get("PATH", "").split(os.pathsep)) if p]
    for d in python_scripts_dirs(python_exe):
        names = ("whisper.exe", "whisper") if os.name == "nt" else ("whisper",)
        if any(os.path.exists(os.path.join(d, n)) for n in names):
            return os.path.normcase(os.path.abspath(d)) in path_dirs
    return True


def find_whisper_path(saved_path=None):
    if saved_path:
        resolved = from_app_relative(saved_path)
        if os.path.exists(resolved):
            # v0.12.2: a saved path into an app-managed venv gets a real
            # health check, not just a file-existence check — a venv whose
            # base Python moved/was reinstalled elsewhere still has its
            # files present but can't actually launch. Fall through to the
            # rest of the detection chain instead of confidently returning
            # something broken.
            env_dir = _venv_root_for_exe(resolved)
            if env_dir is None or venv_python_launches(env_dir):
                return resolved
    for p in DEFAULT_WHISPER_PATHS:
        if (os.path.exists(p) and not _is_untrusted_whisper_location(p)
                and validate_whisper_executable(p)):
            return p
    return find_global_whisper()


def whisper_is_available(saved_path=None):
    return bool(find_whisper_path(saved_path))


def find_ffmpeg(saved_path=None):
    """Detection order (item 1.6): configured path -> app tools folder ->
    system PATH. A stale configured path is silently discarded (never
    reported as installed) and detection continues down the chain."""
    if saved_path:
        resolved = from_app_relative(saved_path)
        if os.path.exists(resolved):
            return resolved
    for name in ("ffmpeg.exe", "ffmpeg"):
        cand = os.path.join(str(FFMPEG_INSTALL_DIR), "bin", name)
        if os.path.exists(cand):
            return cand
        cand = os.path.join(str(FFMPEG_INSTALL_DIR), name)
        if os.path.exists(cand):
            return cand
    return shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")


def tools_venv_python():
    return venv_python(TOOLS_VENV_DIR)


def markitdown_python(config_data):
    """Interpreter used to run markitdown (item 1.6 detection order:
    configured override -> app tools venv -> system python). Fixes item 1.1
    failure (b): the install step (ensure_tools_venv/pip install) and this
    probe now always resolve to the SAME interpreter for a fresh install.

    v0.12.3: both the override and the tools-venv candidate now get a real
    health check (venv_python_launches), not just a file-existence check —
    this shared venv (also used by yt-dlp) is exactly as vulnerable to a
    stale base-Python reference as Whisper's venv was, fixed in v0.12.2."""
    override = (config_data or {}).get("markitdown_python") or ""
    if override:
        resolved = from_app_relative(override)
        if os.path.exists(resolved):
            env_dir = _venv_root_for_exe(resolved)
            if env_dir is None or venv_python_launches(env_dir):
                return resolved
    tv = tools_venv_python()
    if os.path.exists(tv) and venv_python_launches(str(TOOLS_VENV_DIR)):
        return tv
    return find_python_executable()


def ensure_tools_venv(log_cb=None):
    """Create the shared portable venv (tools/venv) for markitdown, yt-dlp
    and youtube-transcript-api if it doesn't exist yet (item 1.2/1.3), OR
    rebuild it if it exists but its own interpreter won't launch (v0.12.3
    — a stale base-Python reference, e.g. the Python used to create it was
    moved or reinstalled elsewhere; the file being present isn't enough,
    same fix as v0.12.2's Whisper venv). Returns (python_exe, error_or_None).
    Uses the exact base interpreter found by find_python_executable()
    (never the WindowsApps stub)."""
    vpy = tools_venv_python()
    if os.path.exists(vpy) and venv_python_launches(str(TOOLS_VENV_DIR)):
        return vpy, None
    base = find_python_executable()
    if _is_windows_store_stub(base):
        return None, "No usable Python interpreter found (Windows Store stub rejected)."
    try:
        os.makedirs(str(TOOLS_DIR), exist_ok=True)
        if os.path.exists(vpy):
            if log_cb:
                log_cb("Existing tools environment isn't working (its Python may have "
                       "moved or been reinstalled) — rebuilding it...\n")
            shutil.rmtree(str(TOOLS_VENV_DIR), ignore_errors=True)
        if log_cb:
            log_cb(f"Command: {base} -m venv {TOOLS_VENV_DIR}\n")
        proc = subprocess.run([base, "-m", "venv", str(TOOLS_VENV_DIR)],
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              text=True, timeout=180,
                              **subprocess_hidden_window_kwargs())
        if log_cb:
            log_cb(proc.stdout or "")
        if proc.returncode != 0 or not os.path.exists(vpy):
            return None, "Failed to create the tools venv."
        return vpy, None
    except Exception as e:
        return None, str(e)


def rebuild_tools_venv(log_cb=None):
    """v0.13.3: unconditionally wipes and recreates the shared tools venv
    (markitdown/yt-dlp/youtube-transcript-api), unlike ensure_tools_venv()
    above which only rebuilds when the venv's own interpreter won't
    launch. This is for the OTHER failure mode: the interpreter works
    fine, but packages installed into it over time (by hand, by other
    tools, by earlier app versions) have accumulated pins that make no
    clean upgrade path exist inside THIS venv any more — e.g. an
    already-installed youtube-transcript-api that a newer markitdown[all]
    release's own pin can no longer be reconciled with, even when pinned
    to an exact version (see v0.13.2 -> v0.13.3). A fresh venv has
    nothing left to conflict with. Returns (python_exe, error_or_None);
    does not reinstall anything by itself — that's the caller's job.

    v0.13.4: shutil.rmtree(..., ignore_errors=True) can silently fail to
    remove anything on Windows if a file from the old venv is still
    locked (e.g. a DLL the just-exited python.exe briefly still holds a
    handle on) — the directory then survives, `python -m venv` runs
    against the pre-existing folder (which does NOT clear installed
    packages, only ensures the venv structure exists), and the "rebuild"
    silently changes nothing at all: same packages, same conflict. Now
    verified explicitly, with one short retry for a transient lock,
    instead of trusting ignore_errors to mean it worked."""
    base = find_python_executable()
    if _is_windows_store_stub(base):
        return None, "No usable Python interpreter found (Windows Store stub rejected)."
    try:
        os.makedirs(str(TOOLS_DIR), exist_ok=True)
        shutil.rmtree(str(TOOLS_VENV_DIR), ignore_errors=True)
        if os.path.exists(str(TOOLS_VENV_DIR)):
            if log_cb:
                log_cb("Old environment folder is still locked by something — "
                       "waiting a moment and trying again...\n")
            time.sleep(1.5)
            shutil.rmtree(str(TOOLS_VENV_DIR), ignore_errors=True)
        if os.path.exists(str(TOOLS_VENV_DIR)):
            return None, ("Could not remove the old environment folder — it's still in "
                          "use by something (close any other running copy of this app, "
                          "or any process using it, and try again).")
        if log_cb:
            log_cb(f"Command: {base} -m venv {TOOLS_VENV_DIR}\n")
        proc = subprocess.run([base, "-m", "venv", str(TOOLS_VENV_DIR)],
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              text=True, timeout=180,
                              **subprocess_hidden_window_kwargs())
        if log_cb:
            log_cb(proc.stdout or "")
        vpy = tools_venv_python()
        if proc.returncode != 0 or not os.path.exists(vpy):
            return None, "Failed to create the tools venv."
        return vpy, None
    except Exception as e:
        return None, str(e)


# --------------------------------------------------------------------------
# v0.13.7 — Docling's own dedicated venv. Mirrors ensure_tools_venv()
# above structurally, but deliberately kept separate from it: Docling's
# base install always pulls torch/torchvision/rapidocr/accelerate (no
# lighter install path exists — verified against the real PyPI
# dependency graph), and mixing that into the lightweight shared tools
# venv used by markitdown/yt-dlp/youtube-transcript-api/pysrt/webvtt-py
# risks exactly the kind of accumulated-package conflict that caused
# the markitdown/youtube-transcript-api saga a few versions back.
# --------------------------------------------------------------------------

def docling_venv_python():
    return venv_python(DOCLING_ENV_DIR)


def venv_docling(env_dir):
    env_dir = Path(env_dir)
    return str(env_dir / ("Scripts" if os.name == "nt" else "bin")
               / ("docling.exe" if os.name == "nt" else "docling"))


def docling_env_dir_from_cfg(cfg):
    """Same shape as whisper_env_dir_from_cfg() above."""
    stored = (cfg or {}).get("docling_env_dir")
    if stored:
        return from_app_relative(stored)
    return str(DOCLING_ENV_DIR)


def ensure_docling_venv(log_cb=None):
    """Same shape as ensure_tools_venv() above. Docling only requires
    Python >=3.10,<4.0 (verified against its real PyPI classifier) — a
    much looser bound than Whisper's, so this reuses the simple
    self-healing pattern rather than Whisper's dedicated
    compatible-Python search."""
    vpy = docling_venv_python()
    if os.path.exists(vpy) and venv_python_launches(str(DOCLING_ENV_DIR)):
        return vpy, None
    base = find_python_executable()
    if _is_windows_store_stub(base):
        return None, "No usable Python interpreter found (Windows Store stub rejected)."
    try:
        os.makedirs(str(TOOLS_DIR), exist_ok=True)
        if os.path.exists(vpy):
            if log_cb:
                log_cb("Existing Docling environment isn't working (its Python may "
                       "have moved or been reinstalled) — rebuilding it...\n")
            shutil.rmtree(str(DOCLING_ENV_DIR), ignore_errors=True)
        if log_cb:
            log_cb(f"Command: {base} -m venv {DOCLING_ENV_DIR}\n")
        proc = subprocess.run([base, "-m", "venv", str(DOCLING_ENV_DIR)],
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              text=True, timeout=180,
                              **subprocess_hidden_window_kwargs())
        if log_cb:
            log_cb(proc.stdout or "")
        if proc.returncode != 0 or not os.path.exists(vpy):
            return None, "Failed to create the Docling venv."
        return vpy, None
    except Exception as e:
        return None, str(e)


def docling_is_available(env_dir=None):
    """Readiness probe: the venv's own docling console-script exists and
    the interpreter launches. Docling has NO __main__.py (verified
    directly against its wheel's entry_points.txt — console_scripts only,
    docling = docling.cli.main:app), so — unlike markitdown — it can
    never be invoked as `python -m docling`; the venv's own docling(.exe)
    script must be called directly, the same way Whisper's whisper.exe
    is."""
    env_dir = env_dir or str(DOCLING_ENV_DIR)
    exe = venv_docling(env_dir)
    return os.path.exists(exe) and venv_python_launches(env_dir)


def build_docling_command(docling_exe, src_path, dst_dir):
    """Docling's CLI writes to a DIRECTORY (--output), not a target
    filename (verified live: `docling myfile.pdf --to md --output
    ./scratch` produces ./scratch/myfile.md) — unlike markitdown's `-o
    dst_file`. Callers use finalize_docling_output() below to move the
    result to the actual desired filename afterward."""
    return [docling_exe, src_path, "--to", "md", "--output", dst_dir]


def finalize_docling_output(scratch_dir, src_path, dst_path):
    """After a successful build_docling_command() run, find the .md file
    Docling produced in scratch_dir (named after src_path's stem) and
    move it to dst_path. Returns True on success."""
    stem = os.path.splitext(os.path.basename(src_path))[0]
    produced = os.path.join(scratch_dir, stem + ".md")
    if not os.path.exists(produced):
        return False
    try:
        os.makedirs(os.path.dirname(dst_path) or ".", exist_ok=True)
        shutil.move(produced, dst_path)
        return True
    except OSError:
        return False


# Scoped deliberately narrower than everything Docling's InputFormat enum
# supports (sourced from its real base_models.py) — audio/video/image
# handling stays on this app's own Whisper pipeline; .md/.txt/.tex/.vtt
# stay on this app's own bypass/prose engine. This is what's left: real
# "document" formats this app doesn't already have its own path for.
DOCLING_EXTENSIONS = {
    ".pdf", ".docx", ".dotx", ".pptx", ".potx", ".xlsx", ".xlsm",
    ".html", ".htm", ".csv", ".xml", ".xbrl",
}

# Real, tested set (not the full ~40-format list Pandoc claims — many of
# those are markup dialects irrelevant here). Verified live against the
# actual 3.10.2 binary's --list-input-formats plus real conversions of
# each: docx, csv, epub, html, odt, pptx, rtf, xlsx all genuinely read
# and produce reasonable markdown. No PDF — Pandoc explicitly refuses it
# ("Pandoc can convert to PDF, but not from PDF").
PANDOC_EXTENSIONS = {
    ".docx", ".csv", ".epub", ".html", ".htm", ".odt", ".pptx", ".rtf", ".xlsx",
}


# Network calls (PyPI JSON API, GitHub releases API) happen ONLY when the
# user clicks; every call below is a small, pure(ish), mockable function so
# tests can substitute urllib.request.urlopen / subprocess.run.
# --------------------------------------------------------------------------

TOOL_PYPI_NAMES = {
    "markitdown": "markitdown",
    "ytdlp": "yt-dlp",
    "youtube_transcript_api": "youtube-transcript-api",
    "whisper": "openai-whisper",
}


def get_pip_package_version(python_exe, package):
    """Installed version of `package` as seen by `python_exe`, or None."""
    if not python_exe or not os.path.exists(python_exe):
        return None
    try:
        proc = subprocess.run(
            [python_exe, "-c",
             f"import importlib.metadata as m;print(m.version('{package}'))"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
            timeout=20, **subprocess_hidden_window_kwargs())
        v = (proc.stdout or "").strip()
        return v or None
    except Exception:
        return None


def get_ffmpeg_version(ffmpeg_path):
    if not ffmpeg_path or not os.path.exists(ffmpeg_path):
        return None
    try:
        proc = subprocess.run([ffmpeg_path, "-version"], stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, text=True, timeout=15,
                              **subprocess_hidden_window_kwargs())
        first = (proc.stdout or "").splitlines()[0] if proc.stdout else ""
        m = re.search(r"ffmpeg version (\S+)", first)
        return m.group(1) if m else (first.strip() or None)
    except Exception:
        return None


# --------------------------------------------------------------------------
# v0.11.2 — robust HTTPS fetch with a certificate-trust fallback ladder.
#
# On some Windows machines (fresh installs, or machines behind corporate
# antivirus/network HTTPS inspection) Python's own certificate trust store
# rejects a certificate that the user's browser trusts fine, raising
# CERTIFICATE_VERIFY_FAILED even though the remote server's certificate is
# perfectly valid. Every HTTPS call the app itself makes (not the isolated
# tool venvs, which are unaffected) goes through this ladder instead of a
# bare urlopen/urlretrieve, so one misconfigured trust store doesn't block
# ffmpeg installation or update checks outright.
# --------------------------------------------------------------------------

def _is_cert_verify_error(exc):
    return "CERTIFICATE_VERIFY_FAILED" in str(exc)


def _https_context_candidates():
    """SSL contexts to try in order, cheapest/most-common first:
    1. None -> let urllib use its own platform default context.
    2. certifi's CA bundle, if the certifi package happens to be installed
       (common as a transitive dependency of pip/requests/etc.).
    3. A fresh default context with load_default_certs() called explicitly
       -- on Windows this also consults the OS "CA"/"ROOT" certificate
       stores, which is what picks up a corporate HTTPS-inspection root
       certificate that's installed system-wide but that Python's own
       bundle doesn't know about.
    Only distinct, successfully-built contexts are yielded."""
    yield None
    try:
        import certifi
        yield ssl.create_default_context(cafile=certifi.where())
    except Exception:
        pass
    try:
        ctx = ssl.create_default_context()
        ctx.load_default_certs()
        yield ctx
    except Exception:
        pass


def urlopen_with_cert_fallback(url_or_request, timeout=15):
    """Robust HTTPS GET. Retries down the certificate-trust ladder above
    only when the failure is specifically a certificate-verification
    error; any other error (network down, 404, timeout, ...) is raised
    immediately from the first attempt, unchanged."""
    last_err = None
    for ctx in _https_context_candidates():
        try:
            kwargs = {"timeout": timeout}
            if ctx is not None:
                kwargs["context"] = ctx
            return urllib.request.urlopen(url_or_request, **kwargs)
        except Exception as e:
            last_err = e
            if not _is_cert_verify_error(e):
                raise
    raise last_err


def fetch_url_bytes_with_cert_fallback(url_or_request, timeout=30):
    with urlopen_with_cert_fallback(url_or_request, timeout=timeout) as resp:
        return resp.read()


def download_file_with_cert_fallback(url, dest_path, timeout=120):
    """File-download counterpart of urlopen_with_cert_fallback (used for
    the ~80MB ffmpeg build, so a generous default timeout)."""
    data = fetch_url_bytes_with_cert_fallback(url, timeout=timeout)
    with open(dest_path, "wb") as f:
        f.write(data)


def friendly_download_error(exc):
    """A plain-language explanation for CERTIFICATE_VERIFY_FAILED, since
    the raw Python/OpenSSL error text means nothing to most users. Any
    other error is returned as-is."""
    if _is_cert_verify_error(exc):
        return ("TLS certificate could not be verified. This usually means "
                "either (1) a corporate antivirus/network security tool is "
                "inspecting HTTPS traffic and its certificate isn't trusted "
                "by Python, or (2) this machine's clock/date is wrong. Try "
                "checking the system date, or ask your IT department about "
                "an HTTPS-inspection root certificate; 'Open download page' "
                "downloads via your browser instead and isn't affected.")
    return str(exc)


_PRERELEASE_TAG_RE = re.compile(
    r'(?:^|[.\-_]|(?<=\d))(a|b|rc|dev|alpha|beta|pre|preview)\.?(\d*)$', re.IGNORECASE)


def _is_prerelease_loose(version):
    """True if `version` carries a PEP 440-style pre/dev-release tag
    (a1, b2, rc1, dev3, alpha1, beta2, ...). Loose on purpose — no
    external 'packaging' dependency for the main app process (v0.13.0)."""
    return bool(_PRERELEASE_TAG_RE.search((version or "").strip()))


def _version_sort_key(version):
    """Loose PEP 440-ish sort key: (release tuple, is_final, pre_number).
    A pre-release of a release sorts below that same release's final
    version. Unparseable strings fall back to a release-less bucket so
    they still compare instead of raising."""
    v = (version or "").strip()
    m = re.match(r'^([0-9]+(?:\.[0-9]+)*)(.*)$', v)
    if not m:
        return ((), 1, 0)
    release = tuple(int(x) for x in m.group(1).split("."))
    rest = m.group(2)
    pm = _PRERELEASE_TAG_RE.search(rest)
    if pm:
        return (release, 0, int(pm.group(2) or 0))
    return (release, 1, 0)


def check_pypi_latest_version(package, timeout=10):
    """Returns (latest_version_or_None, error_or_None). Network call — only
    invoked from a background thread on explicit user click (item 1.7).

    v0.13.0: walks the full 'releases' map instead of trusting the bare
    'info.version' field, so a pre-release/dev build that happens to be
    the newest upload can never be reported as "the" latest version —
    only real, non-yanked, non-prerelease releases are candidates. Falls
    back to 'info.version' only if the project has no stable release at
    all (e.g. still in alpha)."""
    try:
        data = json.loads(fetch_url_bytes_with_cert_fallback(
            f"https://pypi.org/pypi/{package}/json", timeout=timeout).decode("utf-8"))
        releases = data.get("releases", {}) or {}
        stable = [v for v, files in releases.items()
                 if files and not all(f.get("yanked") for f in files)
                 and not _is_prerelease_loose(v)]
        if stable:
            stable.sort(key=_version_sort_key)
            return stable[-1], None
        return data.get("info", {}).get("version"), None
    except Exception as e:
        return None, friendly_download_error(e)


FFMPEG_RELEASES_API = (
    "https://api.github.com/repos/BtbN/FFmpeg-Builds/releases/tags/latest"
)


def check_ffmpeg_latest_build(timeout=10):
    """FFmpeg has no version number in the BtbN 'latest' rolling release, so
    we compare the release's published_at timestamp instead. Returns
    (latest_label_or_None, error_or_None)."""
    try:
        req = urllib.request.Request(
            FFMPEG_RELEASES_API, headers={"Accept": "application/vnd.github+json"})
        data = json.loads(fetch_url_bytes_with_cert_fallback(req, timeout=timeout)
                          .decode("utf-8"))
        return data.get("published_at"), None
    except Exception as e:
        return None, friendly_download_error(e)


# v0.13.7 — Pandoc, unlike FFmpeg's rolling BtbN build, publishes real
# semver-tagged GitHub releases (verified live: current is 3.10.2, tag
# name is the bare version with no "v" prefix, e.g. "3.10.2"), so — per
# the "stable versions only" requirement from way back at the start of
# this whole update-check thread — this explicitly checks the release's
# own "prerelease" flag too, rather than trusting any release found.
PANDOC_RELEASES_API = "https://api.github.com/repos/jgm/pandoc/releases/latest"


def check_pandoc_latest_release(timeout=10):
    """Returns (tag_name_or_None, error_or_None). /releases/latest already
    excludes pre-releases and drafts per GitHub's own semantics, but the
    prerelease flag is still checked explicitly rather than assumed."""
    try:
        req = urllib.request.Request(
            PANDOC_RELEASES_API, headers={"Accept": "application/vnd.github+json"})
        data = json.loads(fetch_url_bytes_with_cert_fallback(req, timeout=timeout)
                          .decode("utf-8"))
        if data.get("prerelease"):
            return None, "latest release is a pre-release"
        tag = data.get("tag_name")
        return (tag or None), None
    except Exception as e:
        return None, friendly_download_error(e)


def pandoc_windows_asset_url(tag):
    """Verified live against the real jgm/pandoc release assets (e.g.
    pandoc-3.10.2-windows-x86_64.zip at this exact path pattern)."""
    return (f"https://github.com/jgm/pandoc/releases/download/{tag}/"
           f"pandoc-{tag}-windows-x86_64.zip")


def find_pandoc(saved_path=None):
    """Same shape as find_ffmpeg(): saved override first (if it still
    exists), then this app's own managed install location."""
    if saved_path and os.path.exists(saved_path):
        return saved_path
    cand = os.path.join(str(PANDOC_INSTALL_DIR), "pandoc.exe" if os.name == "nt" else "pandoc")
    if os.path.exists(cand):
        return cand
    return None


def compare_versions_simple(installed, latest):
    """Best-effort 'is an update available' check without extra deps.
    v0.13.0: uses the loose PEP 440-ish key from _version_sort_key
    instead of raw digit extraction, so an installed pre-release
    correctly compares as OLDER than the same release's final version
    (digit extraction alone got this backwards — '0.1.0a1' has one more
    digit group than '0.1.0' and used to look newer)."""
    if not installed or not latest:
        return False
    if installed == latest:
        return False
    ka, kb = _version_sort_key(installed), _version_sort_key(latest)
    if ka == kb:
        return installed != latest
    return ka < kb


def markitdown_is_available(python_exe):
    """Fast probe: is the 'markitdown' module importable by python_exe?"""
    if not python_exe:
        return False
    try:
        proc = subprocess.run(
            [python_exe, "-c",
             "import importlib.util,sys;"
             "sys.exit(0 if importlib.util.find_spec('markitdown') else 1)"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=20,
            **subprocess_hidden_window_kwargs(),
        )
        return proc.returncode == 0
    except Exception:
        return False


def subtitle_libs_available(python_exe):
    """v0.13.8: readiness check for the 'pysrt/webvtt-py' conversion
    model — both libraries importable by python_exe (installed alongside
    markitdown in the shared tools venv, see _update_markitdown's
    extra_packages)."""
    if not python_exe:
        return False
    try:
        proc = subprocess.run(
            [python_exe, "-c",
             "import importlib.util,sys;"
             "ok = importlib.util.find_spec('pysrt') and importlib.util.find_spec('webvtt');"
             "sys.exit(0 if ok else 1)"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=20,
            **subprocess_hidden_window_kwargs(),
        )
        return proc.returncode == 0
    except Exception:
        return False


def subprocess_hidden_window_kwargs():
    if os.name != "nt":
        return {"creationflags": 0, "startupinfo": None}
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE
    return {"creationflags": 0, "startupinfo": startupinfo}


def subprocess_child_env():
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def whisper_child_env(ffmpeg_path):
    env = subprocess_child_env()
    if ffmpeg_path and os.path.exists(ffmpeg_path):
        p = os.path.abspath(ffmpeg_path)
        ffdir = p if os.path.isdir(p) else os.path.dirname(p)
        if ffdir:
            env["PATH"] = ffdir + os.pathsep + env.get("PATH", "")
    return env


def whisper_cache_dir():
    """v0.11.0 (item 1.3): models live inside the portable tools/ folder,
    not ~/.cache/whisper, so they travel with the app when it's moved."""
    return str(WHISPER_MODELS_DIR)


LEGACY_WHISPER_CACHE_DIR = os.path.join(str(Path.home()), ".cache", "whisper")


def migrate_legacy_whisper_models():
    """Offered (not automatic) copy of any models found in the old global
    ~/.cache/whisper into the portable tools/whisper_models folder."""
    found = []
    try:
        if os.path.isdir(LEGACY_WHISPER_CACHE_DIR):
            for cli in ALL_MODEL_CLIS:
                src = os.path.join(LEGACY_WHISPER_CACHE_DIR, model_file_name(cli))
                if os.path.exists(src):
                    found.append(cli)
    except OSError:
        pass
    return found


def copy_legacy_whisper_model(cli_name):
    src = os.path.join(LEGACY_WHISPER_CACHE_DIR, model_file_name(cli_name))
    if not os.path.exists(src):
        return False
    os.makedirs(str(WHISPER_MODELS_DIR), exist_ok=True)
    dst = os.path.join(str(WHISPER_MODELS_DIR), model_file_name(cli_name))
    if os.path.exists(dst):
        return True
    shutil.copy2(src, dst)
    return True


def model_file_name(cli_name):
    if cli_name == "turbo":
        return "large-v3-turbo.pt"
    return f"{cli_name}.pt"


def is_model_downloaded(cli_name, cache_dir=None):
    cache_dir = cache_dir or whisper_cache_dir()
    path = os.path.join(cache_dir, model_file_name(cli_name))
    return os.path.exists(path), path


def installed_model_clis(cache_dir=None):
    """Models actually present in the cache, in catalog order."""
    cache_dir = cache_dir or whisper_cache_dir()
    out = []
    for cli in ALL_MODEL_CLIS:
        if os.path.exists(os.path.join(cache_dir, model_file_name(cli))):
            out.append(cli)
    return out


def model_language_label(cli_name):
    return "English" if str(cli_name).endswith(".en") else "Multilingual"


def models_for_audio_language(audio_lang_code, only_installed=False, cache_dir=None):
    """Valid model CLIs; .en variants only when audio is English."""
    is_english = (audio_lang_code == "en")
    pool = installed_model_clis(cache_dir) if only_installed else ALL_MODEL_CLIS
    return [cli for cli in pool
            if not (MODEL_INFO[cli]["english_only"] and not is_english)]


def audio_lang_param(code):
    if code in AUDIO_LANG_OPTIONS:
        return AUDIO_LANG_OPTIONS[code]["param"]
    name = WHISPER_LANGUAGES.get(code)
    return name if name else None


def human_size(size_mb):
    return f"{size_mb} MB" if size_mb < 1000 else f"{size_mb / 1000:.1f} GB"


def fmt_hms(seconds):
    if seconds is None or seconds < 0:
        return "--:--"
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


_WHISPER_TIME_RE = re.compile(r"\[(\d{1,2}):(\d{2})(?::(\d{2}))?[.,]\d{1,3}\s*-->")


def parse_whisper_position_seconds(line):
    m = _WHISPER_TIME_RE.search(line)
    if not m:
        return None
    a, b, c = m.group(1), m.group(2), m.group(3)
    if c is not None:
        return int(a) * 3600 + int(b) * 60 + int(c)
    return int(a) * 60 + int(b)


_FFMPEG_DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d{2}):(\d{2})\.(\d+)")


def parse_ffmpeg_duration_seconds(text):
    m = _FFMPEG_DURATION_RE.search(text or "")
    if not m:
        return None
    h, mm, ss, frac = m.group(1), m.group(2), m.group(3), m.group(4)
    total = int(h) * 3600 + int(mm) * 60 + int(ss)
    try:
        total += round(float("0." + frac))
    except ValueError:
        pass
    return total


def ffmpeg_probe_duration(ffmpeg_path, media_path, timeout=25):
    if not ffmpeg_path or not os.path.exists(media_path):
        return None
    try:
        proc = subprocess.run(
            [ffmpeg_path, "-i", media_path],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
            env=subprocess_child_env(), **subprocess_hidden_window_kwargs(),
        )
        return parse_ffmpeg_duration_seconds(proc.stdout)
    except Exception:
        return None


def ffprobe_path_from_ffmpeg(ffmpeg_path):
    """ffprobe ships next to ffmpeg in the BtbN build (item 3)."""
    if not ffmpeg_path:
        return None
    d = os.path.dirname(ffmpeg_path)
    name = "ffprobe.exe" if os.name == "nt" else "ffprobe"
    cand = os.path.join(d, name)
    return cand if os.path.exists(cand) else None


def read_embedded_tags(ffmpeg_path, media_path, timeout=20):
    """item 3: read embedded container tags (title, date, source URL,
    uploader, description) via ffprobe -show_format. Returns {} on any
    failure or when ffprobe/tags aren't available (zero regression for
    tagless files)."""
    ffprobe = ffprobe_path_from_ffmpeg(ffmpeg_path)
    if not ffprobe or not media_path or not os.path.exists(media_path):
        return {}
    try:
        proc = subprocess.run(
            [ffprobe, "-v", "quiet", "-print_format", "json", "-show_format", media_path],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
            **subprocess_hidden_window_kwargs())
        data = json.loads(proc.stdout or "{}")
        tags = {(k or "").lower(): v for k, v in
                (data.get("format", {}).get("tags", {}) or {}).items()}
        return tags
    except Exception:
        return {}


def auto_metadata_from_embedded_tags(tags):
    """Maps ffprobe-read tags (item 2's yt-dlp --embed-metadata output) to
    the 7-field header. Any field the tags don't have is left absent so the
    caller can fall back to its normal strategy per-field (item 3)."""
    tags = tags or {}
    out = {}
    title = tags.get("title")
    if title:
        out["titulo"] = title
    date_raw = tags.get("date") or tags.get("creation_time")
    if date_raw:
        m = re.match(r"(\d{4})[-.]?(\d{2})[-.]?(\d{2})", str(date_raw))
        if m:
            out["data"] = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    source = tags.get("purl") or tags.get("source") or tags.get("comment")
    if source and re.match(r"https?://", str(source)):
        out["fonte"] = source
    uploader = tags.get("artist") or tags.get("uploader")
    if uploader:
        out["_uploader"] = uploader  # informational only; not a header field
    return out



    replacements = []
    for line in (raw or "").splitlines():
        line = line.strip()
        if not line or "=" not in line:
            continue
        find, _, replace = line.partition("=")
        find = find.strip()
        replace = replace.strip()
        if not find:
            continue
        replacements.append([find, replace])
    return replacements


# --------------------------------------------------------------------------
# Subtitle -> clean prose (for AI-ready Markdown). MarkItDown passes SRT
# timestamps/indices through verbatim, which is useless for AI training, so we
# parse subtitles ourselves into timestamp-free paragraphs.
# --------------------------------------------------------------------------

# Bare timestamp line, e.g. "0:01", "12:34", "1:02:03" (YouTube copy-transcript).
TS_ONLY_RE = re.compile(r"^\d{1,2}:\d{2}(?::\d{2})?(?:[.,]\d+)?$")
URL_RE = re.compile(r"https?://\S+")

# SRT/VTT "-->" timing line: optional HH:, then MM:SS, then .mmm or ,mmm.
_CUE_TIME_RE = re.compile(r"(?:(\d{1,2}):)?(\d{2}):(\d{2})[.,](\d{1,3})\s*-->")
_BARE_TS_VALUE_RE = re.compile(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?")


def parse_cue_start_seconds(line):
    """item 1 (v0.11.01): start time from an SRT/VTT '-->' timing line.
    Accepts both HH:MM:SS[,.]mmm and the shorter VTT MM:SS[,.]mmm form."""
    m = _CUE_TIME_RE.match((line or "").strip())
    if not m:
        return None
    h, mm, ss, _frac = m.groups()
    total = int(mm) * 60 + int(ss)
    if h:
        total += int(h) * 3600
    return total


def parse_bare_timestamp_seconds(line):
    """item 1 (v0.11.01): a bare 'MM:SS' / 'H:MM:SS' line (YouTube copy-
    transcript style) parsed into whole seconds."""
    m = _BARE_TS_VALUE_RE.match((line or "").strip())
    if not m:
        return None
    a, b, c = m.groups()
    if c is not None:
        return int(a) * 3600 + int(b) * 60 + int(c)
    return int(a) * 60 + int(b)


def _format_time_marker(seconds):
    """item 1 (v0.11.01): '[t=MM:SS]' / '[t=H:MM:SS]' anchor — same time
    format as the rest of the app (fmt_hms), so it reads consistently next
    to the Duração header field. None when there's nothing to anchor."""
    if seconds is None or seconds < 0:
        return None
    return f"[t={fmt_hms(seconds)}]"


def _cues_to_paragraphs(cues, min_len=220, hard_cap=1200, keep_timestamps=False):
    """cues: list of (text, start_seconds_or_None) tuples.

    item 1 (v0.11.01): with keep_timestamps=True, each paragraph is prefixed
    with a "[t=MM:SS]" anchor taken from the first cue folded into it. This
    is purely additive — with keep_timestamps=False (the pre-0.11.01
    default) the output is byte-identical to before."""
    deduped = []
    for c in cues:
        if not deduped or deduped[-1][0] != c[0]:
            deduped.append(c)
    paragraphs, buf = [], []
    for c in deduped:
        buf.append(c)
        joined = " ".join(t for t, _ in buf)
        ends_sentence = re.search(r"[.!?…][\"'”’)\]]?$", c[0])
        # Break at a sentence boundary once long enough, or force a break when a
        # stretch of unpunctuated caption text grows past the hard cap (keeps
        # RAG-friendly paragraph sizes even without punctuation).
        if (ends_sentence and len(joined) >= min_len) or len(joined) >= hard_cap:
            paragraphs.append(buf)
            buf = []
    if buf:
        paragraphs.append(buf)

    out = []
    for para in paragraphs:
        text = re.sub(r"[ \t]+", " ", " ".join(t for t, _ in para)).strip()
        if not text:
            continue
        if keep_timestamps:
            start = next((s for _, s in para if s is not None), None)
            marker = _format_time_marker(start)
            if marker:
                text = f"{marker} {text}"
        out.append(text)
    return "\n\n".join(out)


def _regex_parse_subtitle_cues(text, is_vtt=False):
    """The original hand-rolled SRT/VTT block parser (pre-v0.13.7),
    producing (text, start_seconds) cue tuples. Kept as the fallback for
    when pysrt/webvtt-py aren't installed, or a given file doesn't parse
    cleanly with them."""
    lines = (text or "").splitlines()
    cues, cur = [], []
    cur_start = None  # item 1: start-seconds of the cue currently being built

    def flush():
        nonlocal cur_start
        if cur:
            t = re.sub(r"\s+", " ", " ".join(x.strip() for x in cur if x.strip())).strip()
            if t:
                cues.append((t, cur_start))
            cur.clear()
        cur_start = None

    for raw in lines:
        line = raw.strip()
        if not line:
            flush()
            continue
        if is_vtt and (line.upper().startswith("WEBVTT")
                       or line.startswith("NOTE") or line.startswith("STYLE")
                       or line.startswith("REGION")):
            continue
        if "-->" in line:
            if cur_start is None:
                cur_start = parse_cue_start_seconds(line)
            continue
        if re.fullmatch(r"\d+", line):  # srt cue index
            continue
        cur.append(line)
    flush()
    return cues


def _cues_from_pysrt_text(text):
    """v0.13.7: pysrt-based SRT parsing, feeding the SAME (text,
    start_seconds) cue shape _regex_parse_subtitle_cues() above produces
    — so _cues_to_paragraphs()'s prose engine (dedup, sentence merging,
    timestamp handling) runs identically either way; only the low-level
    block parsing changes. Returns None (caller falls back to the regex
    parser) if pysrt isn't installed or the text doesn't parse as SRT."""
    try:
        import pysrt
    except ImportError:
        return None
    try:
        subs = pysrt.SubRipFile.from_string(text)
    except Exception:
        return None
    cues = []
    for item in subs:
        t = re.sub(r"\s+", " ", item.text_without_tags.replace("\n", " ")).strip()
        if t:
            cues.append((t, item.start.ordinal / 1000.0))
    return cues


def _cues_from_webvtt_text(text):
    """Same as _cues_from_pysrt_text() above, for WebVTT via webvtt-py."""
    try:
        import webvtt
    except ImportError:
        return None
    try:
        vtt = webvtt.from_string(text)
    except Exception:
        return None
    cues = []
    for caption in vtt:
        t = re.sub(r"\s+", " ", caption.text.replace("\n", " ")).strip()
        if t:
            cues.append((t, caption.start_in_seconds))
    return cues


def subtitle_to_prose(text, is_vtt=False, title=None, keep_timestamps=False):
    # v0.13.7: try the library-based parser first (pysrt for SRT,
    # webvtt-py for VTT) — more robust against malformed/edge-case files
    # than the hand-rolled block parser, which stays as the fallback for
    # when the library isn't installed or a given file doesn't parse
    # cleanly with it. Same cue shape either way, so every prose-quality
    # behavior already tuned here is unaffected by which parser ran.
    cues = _cues_from_webvtt_text(text) if is_vtt else _cues_from_pysrt_text(text)
    if cues is None:
        cues = _regex_parse_subtitle_cues(text, is_vtt=is_vtt)

    body = _cues_to_paragraphs(cues, keep_timestamps=keep_timestamps)
    if not body.strip():
        return ""
    header = f"# {title}\n\n" if title else ""
    return header + body.strip() + "\n"


def looks_like_timestamped_transcript(text):
    """True for YouTube 'copy transcript' style .txt: many bare-timestamp lines
    interleaved with text (which MarkItDown would pass through verbatim)."""
    non_empty = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    if len(non_empty) < 6:
        return False
    ts = sum(1 for ln in non_empty if TS_ONLY_RE.match(ln))
    return ts >= 3 and ts >= 0.15 * len(non_empty)


def transcript_text_to_prose(text, keep_timestamps=False):
    """Turn a timestamped/line-wrapped transcript .txt into fluid AI-ready
    prose: drop bare-timestamp lines, strip URLs, re-flow into paragraphs.

    item 1 (v0.11.01): with keep_timestamps=True, the bare timestamp that
    preceded a stretch of text survives as a "[t=MM:SS]" anchor at the start
    of whichever paragraph it ends up introducing."""
    cues = []
    pending_ts = None
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        if TS_ONLY_RE.match(line):
            pending_ts = parse_bare_timestamp_seconds(line)
            continue
        had_url = bool(URL_RE.search(line))
        line = URL_RE.sub("", line).strip()
        if had_url and (not line or line.endswith(":") or len(line) < 25):
            continue  # drop "…disponível neste link:" style stubs
        if line:
            cues.append((line, pending_ts))
            pending_ts = None
    body = _cues_to_paragraphs(cues, keep_timestamps=keep_timestamps)
    return (body.strip() + "\n") if body.strip() else ""


def convert_subtitle_file_to_md(src_path, dst_path, title=None, keep_timestamps=False):
    is_vtt = src_path.lower().endswith(".vtt")
    with open(src_path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
    prose = subtitle_to_prose(content, is_vtt=is_vtt, title=title,
                              keep_timestamps=keep_timestamps)
    with open(dst_path, "w", encoding="utf-8") as f:
        f.write(prose)
    return dst_path


def build_markitdown_command(python_exe, src_path, dst_path):
    return [python_exe, "-m", "markitdown", src_path, "-o", dst_path]


def build_pandoc_command(pandoc_exe, src_path, dst_path):
    """Verified live against the real pandoc 3.10.2 binary: -t gfm
    --wrap=none (NOT plain -t markdown) is what gives clean GitHub-style
    pipe tables and unwrapped paragraphs — plain "markdown" output uses
    ugly ASCII-art table formatting and hard-wraps at ~80 columns, a bad
    fit for "AI-ready" markdown. Unlike Docling, pandoc writes directly
    to a target file path (-o dst_path), no scratch-dir/move step needed.

    v0.13.10: gfm-raw_html (disabling the raw_html extension), not plain
    gfm — a real EPUB conversion came back full of bare <span id="...">/
    <div class="section">-style anchor markup pandoc preserves from the
    source's internal navigation IDs. Verified directly against a real
    EPUB and against representative HTML: disabling raw_html drops the
    empty anchor spans entirely, keeps every span/div's actual text
    content, and converts <img> to proper markdown image syntax instead
    of passing the raw tag through. No downside found for the other
    formats here (docx/csv/odt/pptx/rtf/xlsx) — this artifact is
    specifically an EPUB/HTML-source thing, not something those
    produce."""
    return [pandoc_exe, src_path, "-t", "gfm-raw_html", "--wrap=none", "-o", dst_path]


# v0.13.5: markitdown[all] pins youtube-transcript-api~=1.0.0, and every
# 1.0.x-1.2.2 release of youtube-transcript-api requires Python <3.14 —
# meaning markitdown[all] is simply uninstallable on Python 3.14+,
# regardless of environment state (confirmed against a genuinely fresh
# venv — same failure every time, not a leftover-package issue). Only
# the "all" and "youtube-transcription" extras reference
# youtube-transcript-api at all, and TranscriptLab doesn't use
# markitdown's own YouTube-transcript feature anyway (the YouTube tab
# calls youtube_transcript_api directly, in-process) — so request every
# other extra "all" would pull in, and install youtube-transcript-api
# itself as a separate, unpinned top-level package in the same command
# instead. Pip then resolves it independently of markitdown's stale
# pin, landing on whatever's newest (currently 1.2.x, which does support
# 3.14). This is markitdown 0.1.x's current extra list minus
# "all"/"youtube-transcription" — hand-maintained against markitdown's
# actual extras, so it needs revisiting if markitdown adds a new one; if
# a future markitdown release relaxes the youtube-transcript-api pin
# itself, this can go back to plain "markitdown[all]".
MARKITDOWN_EXTRAS_NO_YOUTUBE = (
    "audio-transcription,az-content-understanding,az-doc-intel,"
    "docx,outlook,pdf,pptx,xls,xlsx"
)
MARKITDOWN_INSTALL_SPEC = f"markitdown[{MARKITDOWN_EXTRAS_NO_YOUTUBE}]"


def build_pip_install_command(python_exe, package):
    # v0.13.9: --no-cache-dir added after a real Docling install failed
    # with "PermissionError: ... appdata\\local\\pip\\cache\\wheels\\..." —
    # a Windows-specific pip-cache file lock/permission issue (often AV
    # software scanning the cache), the same category of problem as the
    # venv-lock issue rebuild_tools_venv() already had to work around.
    # pip's cache is purely a speed optimization; skipping it trades a
    # slightly slower install for one less thing that can silently break
    # an install on Windows.
    return [python_exe, "-m", "pip", "install", "--upgrade", "--no-cache-dir", package]


# --------------------------------------------------------------------------
# YouTube transcript download (uses youtube-transcript-api, MarkItDown's engine)
# --------------------------------------------------------------------------

def youtube_video_id(url):
    """Extract the 11-char video id from common YouTube URL forms, or None."""
    if not url:
        return None
    url = url.strip()
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", url):
        return url
    try:
        from urllib.parse import urlparse, parse_qs
        u = urlparse(url)
    except Exception:
        return None
    host = (u.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if host == "youtu.be":
        vid = u.path.lstrip("/").split("/")[0]
        return vid if re.fullmatch(r"[A-Za-z0-9_-]{11}", vid) else None
    if host in ("youtube.com", "m.youtube.com", "music.youtube.com"):
        if u.path == "/watch":
            vid = parse_qs(u.query).get("v", [None])[0]
            return vid if vid and re.fullmatch(r"[A-Za-z0-9_-]{11}", vid) else None
        m = re.match(r"/(?:embed|shorts|live|v)/([A-Za-z0-9_-]{11})", u.path)
        if m:
            return m.group(1)
    return None


def _secs_to_srt_ts(t):
    ms = int(round(max(0.0, t) * 1000))
    h, ms = divmod(ms, 3600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def build_srt_from_snippets(snippets):
    """snippets: list of {'text','start','duration'} -> SRT text."""
    out = []
    for i, sn in enumerate(snippets, 1):
        start = float(sn.get("start", 0.0))
        end = start + float(sn.get("duration", 0.0))
        text = (sn.get("text") or "").replace("\r", "").strip()
        out.append(f"{i}\n{_secs_to_srt_ts(start)} --> {_secs_to_srt_ts(end)}\n{text}\n")
    return "\n".join(out)


def fetch_youtube_transcript(video_id, preferred_code=None):
    """Return dict(snippets, language_code, is_generated, matched_pref, available).
    Raises youtube_transcript_api exceptions on failure (mapped by caller)."""
    from youtube_transcript_api import YouTubeTranscriptApi
    from youtube_transcript_api import NoTranscriptFound
    api = YouTubeTranscriptApi()
    tlist = api.list(video_id)
    items = list(tlist)
    if not items:
        raise NoTranscriptFound(video_id, [preferred_code or "any"], tlist)

    def base_code(c):
        return (c or "").split("-")[0].lower()

    matched = []
    if preferred_code:
        matched = [t for t in items if base_code(t.language_code) == preferred_code.lower()]
    pool = matched if matched else items
    manual = [t for t in pool if not t.is_generated]
    chosen = manual[0] if manual else pool[0]
    fetched = chosen.fetch()
    raw = fetched.to_raw_data()
    available = sorted({t.language_code for t in items})
    return {
        "snippets": raw,
        "language_code": chosen.language_code,
        "is_generated": bool(chosen.is_generated),
        "matched_pref": bool(matched) or preferred_code is None,
        "available": available,
    }


def classify_ytdlp_error(text):
    """Map a yt-dlp / generic error string to a stable cause code."""
    t = (text or "").lower()
    if not t.strip():
        return "generic"
    if "members-only" in t or "members only" in t or "join this channel" in t:
        return "members_only"
    if "private video" in t or "this video is private" in t:
        return "private"
    if "confirm your age" in t or "age-restricted" in t or "age restricted" in t \
            or "inappropriate for some users" in t or "sign in to confirm your age" in t:
        return "age_restricted"
    if "not available in your country" in t or "not available in your region" in t \
            or "available in your country" in t or "available in your region" in t \
            or "blocked it in your country" in t or ("geo" in t and "block" in t):
        return "geo_blocked"
    if "not a bot" in t or "po token" in t or "potoken" in t \
            or "sign in to confirm you're not a bot" in t:
        return "bot_check"
    if "429" in t or "too many requests" in t or "requestblocked" in t \
            or "ipblocked" in t or "rate-limit" in t or "rate limit" in t \
            or "your ip" in t and "block" in t:
        return "rate_limited"
    if "requested format is not available" in t or "requested format" in t \
            or ("format" in t and "not available" in t):
        return "format_unavailable"
    if "live event will begin" in t or "premieres in" in t or "upcoming" in t \
            or "this live event" in t or "is live" in t and "no formats" in t:
        return "live_upcoming"
    if "no subtitles" in t or "no transcript" in t or "subtitles are disabled" in t \
            or "transcripts disabled" in t or "could not retrieve a transcript" in t:
        return "no_transcript"
    if "video unavailable" in t or "has been removed" in t or "no longer available" in t \
            or "does not exist" in t or "invalid" in t and "id" in t or "unavailable" in t:
        return "unavailable"
    if "urlopen error" in t or "getaddrinfo" in t or "failed to resolve" in t \
            or "name resolution" in t or "timed out" in t or "connection" in t \
            or "network" in t or "unreachable" in t:
        return "no_connection"
    return "generic"


def classify_youtube_error(exc_or_text):
    """Return a stable cause code for either a transcript-API exception or text."""
    def _s(e):
        try:
            return str(e)
        except Exception:
            return e.__class__.__name__
    if isinstance(exc_or_text, BaseException):
        exc = exc_or_text
        try:
            from youtube_transcript_api import (
                TranscriptsDisabled, NoTranscriptFound, VideoUnavailable,
                VideoUnplayable, AgeRestricted, RequestBlocked, IpBlocked,
                InvalidVideoId, YouTubeRequestFailed)
            if isinstance(exc, (RequestBlocked, IpBlocked)):
                return "rate_limited"
            if isinstance(exc, AgeRestricted):
                return "age_restricted"
            if isinstance(exc, (TranscriptsDisabled, NoTranscriptFound)):
                return "no_transcript"
            if isinstance(exc, (VideoUnavailable, InvalidVideoId)):
                code = classify_ytdlp_error(_s(exc))
                return code if code in ("members_only", "private", "geo_blocked",
                                        "age_restricted") else "unavailable"
            if isinstance(exc, VideoUnplayable):
                code = classify_ytdlp_error(_s(exc))
                return code if code != "generic" else "unavailable"
            if isinstance(exc, YouTubeRequestFailed):
                return "no_connection"
        except Exception:
            pass
        from urllib.error import URLError
        if isinstance(exc, (URLError, ConnectionError, TimeoutError)):
            return "no_connection"
        if isinstance(exc, ImportError):
            return "engine_missing"
        return classify_ytdlp_error(_s(exc))
    return classify_ytdlp_error(str(exc_or_text or ""))


# cause code -> (short message key, suggested action key)
YT_CAUSE_KEYS = {
    "no_transcript": "yt_cause_no_transcript",
    "members_only": "yt_cause_members",
    "private": "yt_cause_private",
    "unavailable": "yt_cause_unavailable",
    "age_restricted": "yt_cause_age",
    "geo_blocked": "yt_cause_geo",
    "rate_limited": "yt_cause_rate",
    "bot_check": "yt_cause_bot",
    "format_unavailable": "yt_cause_format",
    "live_upcoming": "yt_cause_live",
    "no_connection": "yt_cause_no_conn",
    "engine_missing": "yt_cause_engine",
    "generic": "yt_cause_generic",
}


def youtube_error_message(cause, strings, raw=""):
    """Return (short_message, suggested_action) localized for a cause code."""
    key = YT_CAUSE_KEYS.get(cause, "yt_cause_generic")
    if cause == "generic":
        short = strings.get("yt_cause_generic", "{e}")
        try:
            short = short.format(e=raw)
        except (KeyError, IndexError, ValueError):
            pass
    else:
        short = strings.get(key, key)
    action = strings.get(key + "_action", "")
    return short, action


def map_youtube_error(exc, strings):
    """Backward-compatible: localized short message for a transcript exception."""
    cause = classify_youtube_error(exc)
    try:
        raw = str(exc)
    except Exception:
        raw = exc.__class__.__name__
    short, _ = youtube_error_message(cause, strings, raw=raw)
    return short


# --------------------------------------------------------------------------
# yt-dlp helpers (playlist expansion + media download)
# --------------------------------------------------------------------------

def find_ytdlp(saved_path=None):
    """Detection order (item 1.6): configured path -> app tools venv ->
    system PATH. Stale configured paths are discarded silently."""
    if saved_path:
        resolved = from_app_relative(saved_path)
        if os.path.exists(resolved):
            return resolved
    for d in python_scripts_dirs(tools_venv_python()):
        for n in ("yt-dlp.exe", "yt-dlp"):
            cand = os.path.join(d, n)
            if os.path.exists(cand):
                return cand
    return shutil.which("yt-dlp") or shutil.which("yt-dlp.exe")


def ytdlp_is_available(python_exe=None):
    """Fast probe: is the 'yt_dlp' module importable? (CLI presence also counts)."""
    if find_ytdlp():
        return True
    python_exe = python_exe or markitdown_python({})
    if not python_exe:
        return False
    try:
        proc = subprocess.run(
            [python_exe, "-c",
             "import importlib.util,sys;"
             "sys.exit(0 if importlib.util.find_spec('yt_dlp') else 1)"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=20,
            **subprocess_hidden_window_kwargs())
        return proc.returncode == 0
    except Exception:
        return False


def ytdlp_command_prefix(python_exe=None):
    """Prefer the yt-dlp executable; fall back to 'python -m yt_dlp'."""
    exe = find_ytdlp()
    if exe:
        return [exe]
    return [python_exe or find_python_executable(), "-m", "yt_dlp"]


def youtube_playlist_id(url):
    """Return the list id ONLY for a pure playlist URL (no v=), else None."""
    if not url:
        return None
    url = url.strip()
    if youtube_video_id(url):
        return None
    try:
        from urllib.parse import urlparse, parse_qs
        u = urlparse(url)
    except Exception:
        return None
    host = (u.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if host not in ("youtube.com", "m.youtube.com", "music.youtube.com"):
        return None
    if u.path != "/playlist":
        return None
    lst = parse_qs(u.query).get("list", [None])[0]
    if lst and re.fullmatch(r"[A-Za-z0-9_-]+", lst):
        return lst
    return None


def is_mix_playlist(list_id):
    """Endless auto/radio playlists (Mix) start with RD."""
    return bool(list_id) and str(list_id).upper().startswith("RD")


def build_ytdlp_flat_list_command(prefix, url):
    """Enumerate a playlist without downloading: flat JSON dump."""
    return list(prefix) + ["--flat-playlist", "-J", "--no-warnings", url]


GRAB_TITLE_LANGS = ["auto", "zh", "en", "fr", "de", "pt", "es"]


def build_ytdlp_list_command(prefix, url, flat=True, title_lang=None):
    cmd = list(prefix) + ["-J", "--no-warnings", "--ignore-errors"]
    if flat:
        cmd.append("--flat-playlist")
    if title_lang and title_lang != "auto":
        cmd += ["--extractor-args", f"youtube:lang={title_lang}"]
    cmd.append(url)
    return cmd


CHANNEL_TAB_PATHS = {"videos": "/videos", "shorts": "/shorts",
                     "live": "/streams", "podcast": "/podcasts"}
MEMBERS_ONLY_AVAILABILITY = ("subscriber_only", "premium_only", "needs_auth")


def youtube_channel_base(url):
    """Return the channel base URL (without a trailing tab) if `url` is a
    YouTube channel/@handle, else None."""
    if not url:
        return None
    url = url.strip()
    try:
        from urllib.parse import urlparse
        u = urlparse(url)
    except Exception:
        return None
    host = (u.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if host not in ("youtube.com", "m.youtube.com"):
        return None
    parts = [p for p in u.path.split("/") if p]
    if not parts:
        return None
    tabs = {"videos", "shorts", "streams", "live", "podcasts",
            "featured", "playlists", "community", "about"}
    if parts[0].startswith("@"):
        base_parts = parts[:1]
    elif parts[0] in ("channel", "c", "user") and len(parts) >= 2:
        base_parts = parts[:2]
    else:
        return None
    # drop a trailing tab segment if present
    base = "https://www.youtube.com/" + "/".join(base_parts)
    return base


def build_channel_tab_urls(base, sections):
    """sections: dict of {videos,shorts,live,podcast: bool}. Returns tab URLs
    for the enabled sections."""
    urls = []
    for key, path in CHANNEL_TAB_PATHS.items():
        if sections.get(key, True):
            urls.append(base + path)
    return urls


def entry_is_members_only(entry):
    av = (entry or {}).get("availability")
    return bool(av) and str(av) in MEMBERS_ONLY_AVAILABILITY


def parse_flat_playlist_json(text):
    """Parse `yt-dlp --flat-playlist -J` output -> [{id,title,duration}]."""
    data = json.loads(text)
    entries = data.get("entries") if isinstance(data, dict) else None
    out = []
    for e in (entries or []):
        if not e:
            continue
        vid = e.get("id")
        if not vid or not re.fullmatch(r"[A-Za-z0-9_-]{11}", str(vid)):
            continue
        out.append({"id": vid, "title": e.get("title"),
                    "duration": e.get("duration")})
    return out


def build_ytdlp_download_command(prefix, url, out_dir, *, audio_only=False,
                                 audio_format="mp3", resolution="best",
                                 container="mp4", restrict_filenames=False,
                                 ffmpeg_location=None, single_video=True,
                                 progressive=False, out_tmpl_override=None):
    """Build a yt-dlp download command (verified flags).

    progressive=True selects single-file formats that need no ffmpeg merge
    (used as a degraded fallback when ffmpeg is unavailable).

    item 2 (v0.11.0): every download embeds source metadata as tags in the
    file itself (title, upload date, duration, source URL, description,
    uploader) — no sidecar files, only containers that can hold embedded
    tags are offered (DOWNLOAD_AUDIO_FORMATS/DOWNLOAD_CONTAINERS already
    exclude WAV for this reason).

    item 16 (v0.11.0): out_tmpl_override lets the caller force an exact,
    already-uniquified output path (via unique_path()) instead of the
    %(title)s template, when a pre-flight probe found the title-based name
    would collide with an existing file."""
    cmd = list(prefix) + [
        "--newline", "--no-warnings",
        "--progress-template",
        "download:PROG|%(progress._percent_str)s|%(progress.eta)s",
        # item 2: embeds title/uploader/upload_date/description/source-URL
        # tags directly into the downloaded file (yt-dlp's default mapping
        # for --embed-metadata already covers all of those fields).
        "--embed-metadata",
    ]
    cmd.append("--no-playlist" if single_video else "--yes-playlist")
    if restrict_filenames:
        cmd.append("--restrict-filenames")
    if ffmpeg_location:
        cmd += ["--ffmpeg-location", ffmpeg_location]
    if audio_only:
        if progressive:
            cmd += ["-f", "bestaudio/best"]
        else:
            cmd += ["-f", "bestaudio/best", "-x",
                    "--audio-format", audio_format, "--audio-quality", "0"]
    else:
        if resolution in (None, "best", "Best", ""):
            h = None
        else:
            h = str(resolution)
        if progressive:
            fmt = "best" if h is None else f"best[height<={h}]/best"
            cmd += ["-f", fmt]
        else:
            if h is None:
                fmt = "bestvideo+bestaudio/best"
            else:
                fmt = (f"bestvideo[height<={h}]+bestaudio/"
                       f"best[height<={h}]/best")
            cmd += ["-f", fmt, "--merge-output-format", container]
    out_tmpl = out_tmpl_override or os.path.join(out_dir, "%(title)s.%(ext)s")
    cmd += ["-o", out_tmpl, url]
    return cmd


_YTDLP_PCT_RE = re.compile(r"(\d{1,3}(?:\.\d+)?)\s*%")


def parse_ytdlp_progress_line(line):
    """Extract a 0-100 percent from a yt-dlp progress line, or None."""
    if not line:
        return None
    m = _YTDLP_PCT_RE.search(line)
    if not m:
        return None
    try:
        return max(0.0, min(100.0, float(m.group(1))))
    except ValueError:
        return None


_RE_MERGE = re.compile(r'Merging formats into "(.+?)"')
_RE_EXTRACT = re.compile(r'\[ExtractAudio\] Destination: (.+)$')
_RE_DEST = re.compile(r'\[download\] Destination: (.+)$')
_RE_ALREADY = re.compile(r'\[download\] (.+) has already been downloaded')


def parse_ytdlp_final_path(text):
    """Best-effort path of the final downloaded/merged file from yt-dlp output."""
    if not text:
        return None
    merge = _RE_MERGE.findall(text)
    if merge:
        return merge[-1].strip()
    extract = _RE_EXTRACT.findall(text)
    if extract:
        return extract[-1].strip()
    already = _RE_ALREADY.findall(text)
    if already:
        return already[-1].strip()
    dest = _RE_DEST.findall(text)
    if dest:
        return dest[-1].strip()
    return None


# --------------------------------------------------------------------------
# Output filename helpers
# --------------------------------------------------------------------------

_INVALID_FN_CHARS = re.compile(r'[\\/:*?"<>|\x00-\x1f]')
_FN_TRAILING = re.compile(r'[ .]+$')


def sanitize_filename(title, fallback="", max_len=150):
    """Make a title safe to use as a file name (no extension).

    Strips characters illegal on Windows/macOS/Linux, collapses whitespace,
    trims trailing dots/spaces, caps length, and falls back when empty."""
    if title is None:
        title = ""
    # collapse any whitespace (incl. tabs/newlines) to single spaces FIRST,
    # so they aren't deleted as control characters below
    name = re.sub(r"\s+", " ", str(title))
    name = _INVALID_FN_CHARS.sub("", name)
    name = name.strip()
    name = _FN_TRAILING.sub("", name)
    # avoid reserved Windows device names
    if name.upper() in {"CON", "PRN", "AUX", "NUL"} or \
            re.fullmatch(r"(?:COM|LPT)[1-9]", name.upper() or ""):
        name = "_" + name
    if len(name) > max_len:
        name = _FN_TRAILING.sub("", name[:max_len].strip())
    if not name:
        name = sanitize_filename(fallback, "", max_len) if fallback else ""
    return name or "untitled"


def unique_basename(base, used):
    """Return base, or base (2)/(3)/... if already in the `used` set (mutated)."""
    candidate = base
    n = 2
    lowered = {u.lower() for u in used}
    while candidate.lower() in lowered:
        candidate = f"{base} ({n})"
        n += 1
    used.add(candidate)
    return candidate


# Extensions checked for "transcript already exists" detection (item 10).
DUPLICATE_TRANSCRIPT_EXTENSIONS = ("md", "srt", "txt", "json")


def find_existing_transcripts(filepath):
    """Return the list of transcript extensions already present next to
    `filepath` (same folder, same filename stem), among
    DUPLICATE_TRANSCRIPT_EXTENSIONS."""
    folder = os.path.dirname(filepath)
    stem = os.path.splitext(os.path.basename(filepath))[0]
    found = []
    for ext in DUPLICATE_TRANSCRIPT_EXTENSIONS:
        candidate = os.path.join(folder, stem + "." + ext)
        if os.path.exists(candidate):
            found.append(ext)
    return found


def next_available_suffixed_stem(filepath):
    """base_1, base_2, ... — first stem for which NONE of the
    DUPLICATE_TRANSCRIPT_EXTENSIONS already exist in the same folder.
    item 16: universal convention starts at _1 on first collision."""
    folder = os.path.dirname(filepath)
    stem = os.path.splitext(os.path.basename(filepath))[0]
    n = 1
    while True:
        candidate_stem = f"{stem}_{n}"
        if not any(os.path.exists(os.path.join(folder, candidate_stem + "." + ext))
                   for ext in DUPLICATE_TRANSCRIPT_EXTENSIONS):
            return candidate_stem
        n += 1


def unique_path(path):
    """item 16: universal silent filename-collision suffixing for any
    single output file (YouTube downloads, MD outputs, Link Grabber
    exports, ...). Returns `path` unchanged if free; otherwise appends
    _1, _2, ... before the extension until a free name is found. No
    prompt — every writer in the app should call this before writing."""
    if not os.path.exists(path):
        return path
    folder = os.path.dirname(path)
    base, ext = os.path.splitext(os.path.basename(path))
    n = 1
    while True:
        candidate = os.path.join(folder, f"{base}_{n}{ext}")
        if not os.path.exists(candidate):
            return candidate
        n += 1


# --------------------------------------------------------------------------
# Duration / summary / speed-factor helpers
# --------------------------------------------------------------------------

def fmt_long_duration(seconds):
    """3h 34m 12s ; drops higher units when zero (34m 12s / 12s / 0s)."""
    if seconds is None or seconds < 0:
        return "—"
    seconds = int(round(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h > 0:
        return f"{h}h {m}m {s}s"
    if m > 0:
        return f"{m}m {s}s"
    return f"{s}s"


def queue_length_summary(items):
    """(total, n_known, total_seconds) over items with a numeric .duration."""
    total = len(items)
    total_seconds = 0.0
    n_known = 0
    for it in items:
        d = getattr(it, "duration", None)
        if isinstance(d, (int, float)) and d and d > 0:
            total_seconds += float(d)
            n_known += 1
    return total, n_known, total_seconds


def estimate_time_seconds(total_seconds, speed_factor):
    if not total_seconds or total_seconds <= 0:
        return None
    return total_seconds * max(0.01, float(speed_factor or DEFAULT_SPEED_FACTOR))


def current_processing_index(done_count, total, running):
    """1-based index of the item CURRENTLY processing (not finished count)."""
    if total <= 0:
        return 0
    if not running:
        return min(done_count, total)
    return min(done_count + 1, total)


def compute_batch_percent(done_seconds, cur_pos, total_seconds,
                          done_items, total_items):
    """Audio-time percent when durations are known; else item-count percent."""
    if total_seconds and total_seconds > 0:
        val = (float(done_seconds) + max(0.0, float(cur_pos or 0))) / total_seconds * 100.0
        return max(0.0, min(100.0, val))
    if total_items and total_items > 0:
        return max(0.0, min(100.0, float(done_items) / total_items * 100.0))
    return 0.0


def update_speed_factor_rolling(entry, sample, cap=SPEED_FACTOR_SAMPLE_CAP):
    """Capped rolling average update of wall/audio realtime factor.

    `entry` is {"avg": float, "count": int} or None. The window is capped at
    `cap` samples so the average stays adaptive to model/hardware changes
    instead of being diluted forever by very old samples.
    """
    try:
        sample = float(sample)
    except (TypeError, ValueError):
        return entry
    if sample <= 0:
        return entry
    if not entry or not isinstance(entry, dict) or entry.get("avg", 0) <= 0:
        return {"avg": sample, "count": 1}
    old_avg = float(entry.get("avg", sample))
    old_count = int(entry.get("count", 1))
    n = min(old_count + 1, cap)
    new_avg = old_avg + (sample - old_avg) / n
    return {"avg": new_avg, "count": min(old_count + 1, cap)}


def load_eta_history():
    data = load_json(ETA_HISTORY_FILE, {})
    return data if isinstance(data, dict) else {}


def save_eta_history(history):
    ensure_config_dir()
    tmp_path = str(ETA_HISTORY_FILE) + ".tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, ETA_HISTORY_FILE)
    except OSError:
        pass


# --------------------------------------------------------------------------
# YouTube metadata + Markdown header (Feature E)
# --------------------------------------------------------------------------

def youtube_metadata(video_id, prefix=None, timeout=30):
    """Best-effort {video_id,title,duration,upload_date,url}. Network; mocked in tests."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    meta = {"video_id": video_id, "title": None, "duration": None,
            "upload_date": None, "url": url, "uploader": None,
            "availability": None}
    pref = prefix if prefix is not None else (
        ytdlp_command_prefix() if ytdlp_is_available() else None)
    if pref:
        try:
            proc = subprocess.run(
                list(pref) + ["-J", "--no-warnings", "--skip-download", url],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                encoding="utf-8", errors="replace", timeout=timeout,
                **subprocess_hidden_window_kwargs())
            if proc.returncode == 0 and (proc.stdout or "").strip():
                d = json.loads(proc.stdout)
                meta["title"] = d.get("title")
                meta["duration"] = d.get("duration")
                meta["upload_date"] = d.get("upload_date")
                meta["uploader"] = (d.get("uploader") or d.get("channel")
                                    or d.get("uploader_id"))
                meta["availability"] = d.get("availability")
                if meta["title"]:
                    return meta
        except Exception:
            pass
    if not meta["title"]:
        try:
            from urllib.parse import quote
            oembed = ("https://www.youtube.com/oembed?format=json&url="
                      + quote(url, safe=""))
            with urlopen_with_cert_fallback(oembed, timeout=15) as r:
                d = json.loads(r.read().decode("utf-8"))
                meta["title"] = d.get("title")
                meta["uploader"] = meta["uploader"] or d.get("author_name")
        except Exception:
            pass
    return meta


MEMBERS_ONLY_PROBE_TIMEOUT = 15  # item 12: short timeout, never hangs the queue


def probe_is_members_only(video_id, prefix=None, timeout=MEMBERS_ONLY_PROBE_TIMEOUT):
    """item 12: just-in-time members-only check, run right before a queued
    YouTube item is actually processed. Returns True/False, or None if the
    probe itself failed/timed out (treated as inconclusive — the caller
    proceeds normally rather than blocking a whole batch on a flaky probe).
    A dedicated short-timeout, flat-playlist-style single-video lookup
    (cheaper than the full metadata fetch used elsewhere)."""
    pref = prefix if prefix is not None else (
        ytdlp_command_prefix() if ytdlp_is_available() else None)
    if not pref:
        return None
    url = f"https://www.youtube.com/watch?v={video_id}"
    try:
        proc = subprocess.run(
            list(pref) + ["-J", "--no-warnings", "--skip-download",
                          "--no-playlist", url],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
            **subprocess_hidden_window_kwargs())
        if proc.returncode != 0 or not (proc.stdout or "").strip():
            return None
        d = json.loads(proc.stdout)
        return entry_is_members_only(d)
    except Exception:
        return None


def build_youtube_md_header(meta, strings):
    """Localized labels, verbatim values. Always 4 lines; placeholders if unknown."""
    meta = meta or {}
    unknown = strings.get("yt_md_unknown", "Unknown")
    title = meta.get("title")
    title = title if (title is not None and str(title) != "") else unknown
    dur = meta.get("duration")
    dur_str = fmt_hms(dur) if isinstance(dur, (int, float)) and dur and dur > 0 else "—"
    ud = meta.get("upload_date")
    if ud and re.fullmatch(r"\d{8}", str(ud)):
        ud = str(ud)
        date_str = f"{ud[0:4]}-{ud[4:6]}-{ud[6:8]}"
    else:
        date_str = unknown
    url = meta.get("url") or (
        f"https://www.youtube.com/watch?v={meta.get('video_id', '')}")
    return "\n".join([
        f"{strings.get('yt_md_name', 'Video Name')}: {title}",
        f"{strings.get('yt_md_duration', 'Video Duration')}: {dur_str}",
        f"{strings.get('yt_md_date', 'Date')}: {date_str}",
        f"{strings.get('yt_md_link', 'Link')}: {url}",
    ])


# ==========================================================================
# MD header metadata (item 3/4). Portuguese labels are written verbatim into
# the file (the study material is PT-BR), regardless of the UI language.
# ==========================================================================

HEADER_FIELDS = ("titulo", "autor", "data", "tipo", "fonte", "duracao", "qualidade")
HEADER_LABELS = {
    "titulo": "Título", "autor": "Autor", "data": "Data", "tipo": "Tipo",
    "fonte": "Fonte", "duracao": "Duração", "qualidade": "Qualidade",
}
# item 14 (v0.11.0): global header-language toggle, English labels.
HEADER_LABELS_EN = {
    "titulo": "Title", "autor": "Author", "data": "Date", "tipo": "Type",
    "fonte": "Source", "duracao": "Duration", "qualidade": "Quality",
}
HEADER_UNKNOWN = "Não identificado"
KNOWN_AUTHORS = ["Jan Val Ellam", "Jociam Anthor", "Jeanne Miranda", "Alfredo Nahas"]
CONTENT_TYPES = ["Palestra", "Curso", "Live", "Entrevista", "Livro", "Artigo"]


def _strip_accents(s):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFKD", s or "")
                   if not unicodedata.combining(c))


def _norm_text(s):
    return re.sub(r"[^a-z0-9]+", " ", _strip_accents(s or "").lower()).strip()


def detect_authors(haystack):
    """Fuzzy-match KNOWN_AUTHORS inside filename/folder/content text. Tolerates
    case, accents and small typos. Returns 'A, B' / a name / HEADER_UNKNOWN."""
    import difflib
    norm = _norm_text(haystack)
    words = norm.split()
    found = []
    for author in KNOWN_AUTHORS:
        a_norm = _norm_text(author)
        if a_norm and a_norm in norm:
            found.append(author)
            continue
        toks = a_norm.split()
        surname = toks[-1]
        # Distinctive-token match (surname) with typo tolerance.
        sur_hit = any(w == surname or
                      (len(surname) >= 4 and difflib.SequenceMatcher(
                          None, w, surname).ratio() >= 0.85)
                      for w in words)
        # Require at least the surname plus one more token present-ish.
        other_hit = sum(
            1 for t in toks[:-1]
            if any(w == t or difflib.SequenceMatcher(None, w, t).ratio() >= 0.85
                   for w in words))
        if sur_hit and (len(toks) == 1 or other_hit >= 1 or len(surname) >= 5):
            found.append(author)
    return ", ".join(dict.fromkeys(found)) if found else HEADER_UNKNOWN


def detect_content_type(haystack):
    norm = _norm_text(haystack)
    for t in CONTENT_TYPES:
        if re.search(r"\b" + re.escape(_norm_text(t)) + r"\b", norm):
            return t
    return HEADER_UNKNOWN


def detect_date(haystack):
    """Find a date in a filename/folder and return YYYY-MM-DD, else unknown."""
    text = haystack or ""
    # Separated forms first: YYYY-MM-DD / DD-MM-YYYY (sep in - . /).
    for m in re.finditer(r"(?<!\d)(\d{1,4})[./-](\d{1,2})[./-](\d{1,4})(?!\d)", text):
        a, b, c = m.group(1), m.group(2), m.group(3)
        try:
            if len(a) == 4:
                y, mo, d = int(a), int(b), int(c)
            elif len(c) == 4:
                y, mo, d = int(c), int(b), int(a)
            else:
                continue
            if 1900 <= y <= 2100 and 1 <= mo <= 12 and 1 <= d <= 31:
                return f"{y:04d}-{mo:02d}-{d:02d}"
        except ValueError:
            continue
    # Contiguous 8-digit runs: YYYYMMDD or DDMMYYYY.
    for m in re.finditer(r"(?<!\d)(\d{8})(?!\d)", text):
        s = m.group(1)
        for y, mo, d in ((s[0:4], s[4:6], s[6:8]), (s[4:8], s[2:4], s[0:2])):
            try:
                yi, mi, di = int(y), int(mo), int(d)
            except ValueError:
                continue
            if 1900 <= yi <= 2100 and 1 <= mi <= 12 and 1 <= di <= 31:
                return f"{yi:04d}-{mi:02d}-{di:02d}"
    return HEADER_UNKNOWN


def author_folder_haystack(filepath, levels=3):
    """filename stem + up to `levels` parent folder names."""
    parts = [os.path.splitext(os.path.basename(filepath))[0]]
    d = os.path.dirname(filepath)
    for _ in range(levels):
        if not d:
            break
        base = os.path.basename(d)
        if base:
            parts.append(base)
        nd = os.path.dirname(d)
        if nd == d:
            break
        d = nd
    return " / ".join(p for p in parts if p)


def extract_source_link_from_text(text):
    m = re.search(r"https?://(?:www\.|m\.)?(?:youtube\.com|youtu\.be)/\S+",
                  text or "")
    return m.group(0).rstrip(".,);]") if m else None


def last_timestamp_seconds(text):
    """Largest H:MM:SS / M:SS style timestamp in a transcript/srt/vtt text."""
    best = None
    for m in re.finditer(r"(?<!\d)(\d{1,2}):(\d{2})(?::(\d{2}))?(?![\d:])", text or ""):
        h_or_m, mid, sec = m.group(1), m.group(2), m.group(3)
        if sec is not None:
            total = int(h_or_m) * 3600 + int(mid) * 60 + int(sec)
        else:
            total = int(h_or_m) * 60 + int(mid)
        if best is None or total > best:
            best = total
    return best


def auto_metadata_for_file(filepath, *, kind, source_text=None,
                           probe_duration=None, embedded_tags=None):
    """Build the automatic metadata dict for a local file (Whisper / MD tab).
    kind: 'whisper' or 'md'. source_text: file content (MD tab).

    item 3 (v0.11.0): for kind='whisper', embedded_tags (from
    read_embedded_tags/ffprobe) take priority for titulo/data/fonte; any
    field the tags don't provide keeps the existing filename/folder-based
    strategy below (zero regression for files with no tags)."""
    base = os.path.splitext(os.path.basename(filepath))[0]
    hay = author_folder_haystack(filepath)
    meta = {
        "titulo": base,
        "autor": detect_authors(hay),
        "data": detect_date(hay),
        "tipo": detect_content_type(hay),
        "fonte": HEADER_UNKNOWN,
        "duracao": fmt_hms(probe_duration) if probe_duration and probe_duration > 0 else HEADER_UNKNOWN,
        "qualidade": "Bruta",
    }
    if kind == "whisper" and embedded_tags:
        tag_meta = auto_metadata_from_embedded_tags(embedded_tags)
        if tag_meta.get("titulo"):
            meta["titulo"] = tag_meta["titulo"]
        if tag_meta.get("data"):
            meta["data"] = tag_meta["data"]
        if tag_meta.get("fonte"):
            meta["fonte"] = tag_meta["fonte"]
    if kind == "md" and source_text is not None:
        link = extract_source_link_from_text(source_text)
        if link:
            meta["fonte"] = link
        if not (probe_duration and probe_duration > 0):
            ext = os.path.splitext(filepath)[1].lower()
            if ext in (".txt", ".srt", ".vtt"):
                secs = last_timestamp_seconds(source_text)
                if secs:
                    meta["duracao"] = fmt_hms(secs)
    return meta


def auto_metadata_for_youtube(meta):
    """Map youtube_metadata() output to the header dict."""
    m = meta or {}
    title = m.get("title") or HEADER_UNKNOWN
    dur = m.get("duration")
    ud = m.get("upload_date")
    if ud and re.fullmatch(r"\d{8}", str(ud)):
        ud = str(ud)
        date_str = f"{ud[0:4]}-{ud[4:6]}-{ud[6:8]}"
    else:
        date_str = HEADER_UNKNOWN
    url = m.get("url") or (f"https://www.youtube.com/watch?v={m.get('video_id', '')}")
    is_short = isinstance(dur, (int, float)) and dur and 0 < dur < 600
    return {
        "titulo": title,
        "autor": m.get("uploader") or HEADER_UNKNOWN,
        "data": date_str,
        # item 9: duration < 10:00 -> "Short", duration-based only.
        "tipo": "Short" if is_short else detect_content_type(title),
        "fonte": url,
        "duracao": fmt_hms(dur) if isinstance(dur, (int, float)) and dur and dur > 0 else HEADER_UNKNOWN,
        "qualidade": "Bruta",
    }


def resolve_header_metadata(auto_meta, header_config):
    cfg = header_config or {}
    fields_cfg = cfg.get("fields", {}) or {}
    out = {}
    for f in HEADER_FIELDS:
        if f == "qualidade":
            auto_val = (auto_meta or {}).get(f) or "Bruta"
        else:
            auto_val = (auto_meta or {}).get(f, HEADER_UNKNOWN)
        fc = fields_cfg.get(f, {}) or {}
        if fc.get("auto", True):
            out[f] = auto_val if (auto_val is not None and str(auto_val) != "") else (
                "Bruta" if f == "qualidade" else HEADER_UNKNOWN)
        else:
            out[f] = fc.get("value", "")
    return out


def build_md_header(fields, lang="pt"):
    """Render the 7-line header block (no trailing blank line).

    item 14 (v0.11.0): lang="en" switches every label to English and maps
    the default Portuguese quality value "Bruta" to "Brute". Any other
    quality value (a user override) is left exactly as configured."""
    f = fields or {}
    labels = HEADER_LABELS_EN if lang == "en" else HEADER_LABELS
    lines = []
    for key in HEADER_FIELDS:
        val = f.get(key, HEADER_UNKNOWN)
        if val is None:
            val = HEADER_UNKNOWN
        if key == "qualidade" and lang == "en" and val == "Bruta":
            val = "Brute"
        lines.append(f"{labels[key]}: {val}")
    return "\n".join(lines)


def prepend_header_to_file(path, header_block):
    """Insert the header block at the top of an existing UTF-8 text file."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            body = f.read()
    except OSError:
        body = ""
    with open(path, "w", encoding="utf-8") as f:
        f.write(header_block.rstrip("\n") + "\n\n" + body.lstrip("\n"))
    return path


def default_header_config():
    return {"include": True,
            "fields": {f: {"auto": True, "value": ""} for f in HEADER_FIELDS}}


def header_config_all_auto(header_config):
    fields_cfg = (header_config or {}).get("fields", {}) or {}
    return all(fields_cfg.get(f, {}).get("auto", True) for f in HEADER_FIELDS)


# ==========================================================================
# MD polish (v0.10.5) — post-conversion cleanup for LLM-ready Markdown.
#
# MarkItDown is faithful to the source layout, and that is exactly the problem
# for training data. PDF/DOCX output keeps the visual line wrapping (~100
# columns), the justification spaces, a form feed per page and hyphens broken
# across lines; subtitle-derived prose carries its own noise ([Música], ">>"
# speaker marks, HTML entities, non-breaking spaces).
#
# polish_markdown() repairs that without ever inventing text. Two profiles:
#   "document" — MarkItDown output (PDF, DOCX, PPTX, HTML): full reflow.
#   "prose"    — text this app already turned into prose (SRT/VTT/TXT,
#                Whisper, YouTube): whitespace/noise + mid-sentence line
#                breaks only, paragraph structure untouched.
#
# Rules that make it safe to run unattended in a batch:
#   - the metadata header (Título:/Autor:/.../Qualidade:) is split off and
#     written back verbatim, so "Qualidade" keeps the value the user chose;
#   - files containing fenced code are only character-normalized;
#   - table rows (|) and list/quote/heading lines are never re-wrapped;
#   - after the structural stage the letter-by-letter content is compared with
#     the input; if anything would be lost the structural stage is discarded
#     (stats["guard"]) and the conservative result is kept;
#   - blocks that look scrambled by the extractor are never repaired by
#     guessing — they are reported in stats["suspects"] for a human pass.
# ==========================================================================

POLISH_PROFILES = ("document", "document-clean", "prose")

# A PDF text line is wrapped, not ended, when it reaches the column limit;
# shorter lines are real line ends (titles, signatures, short list items).
POLISH_WRAP_MIN = 78
_PLSH_SENT_END = ".!?:…”\"')»"

_PLSH_PAGE_MARKER_RE = re.compile(
    r"^(?:p[áa]g(?:ina)?\.?\s*\d{1,4}(?:\s*(?:de|of|/)\s*\d{1,4})?"
    r"|page\s*\d{1,4}(?:\s*(?:of|/)\s*\d{1,4})?"
    r"|\d{1,4}"
    r"|[-–—]\s*\d{1,4}\s*[-–—]"
    r"|\d{1,4}\s*[|/]\s*\d{1,4})$", re.I)

# Caption / auto-transcript noise.
_PLSH_NOISE_TAG_RE = re.compile(
    r"[\[(]\s*(?:m[úu]sica|music|aplausos|applause|risos|laughter|"
    r"inaud[íi]vel|inaudible|sil[êe]ncio|silence|ru[íi]dos?|noise|sons?|"
    r"sound|efeitos? sonoros?|vinheta|aplauso)\s*[\])]", re.I)
_PLSH_NOISE_CHARS_RE = re.compile(r"[♪♫]+")
_PLSH_SPEAKER_ARROW_RE = re.compile(r"^\s*(?:>>+|&gt;&gt;+)\s*")
_PLSH_HTML_TAG_RE = re.compile(
    r"</?(?:i|b|u|em|strong|font|c|v|br)(?:\s[^>]*)?/?>", re.I)
_PLSH_ENTITY_RE = re.compile(
    r"&(?:amp|lt|gt|quot|apos|nbsp|#\d{2,5}|#x[0-9a-fA-F]{2,4});")

# Markdown block starts that must never be glued onto the previous line.
_PLSH_BLOCK_START_RE = re.compile(
    r"^(?:#{1,6}\s|>\s|\||```|~~~|!\[|[-*+]\s|\d{1,3}[.)]\s|[a-z][.)]\s)")
_PLSH_FENCE_RE = re.compile(r"(?m)^[ \t]*(?:```|~~~)")

# Standalone short lines with these words are section headings.
_PLSH_SECTION_WORDS = {
    "introdução", "introducao", "introduction", "prefácio", "prefacio",
    "prólogo", "prologo", "apresentação", "apresentacao", "sumário",
    "sumario", "índice", "indice", "resumo", "abstract", "conclusão",
    "conclusao", "conclusion", "encerramento", "considerações finais",
    "consideracoes finais", "referências", "referencias", "references",
    "bibliografia", "bibliography", "apêndice", "apendice", "appendix",
    "anexo", "anexos", "glossário", "glossario", "glossary", "epílogo",
    "epilogo", "posfácio", "posfacio", "agradecimentos", "notas",
}
_PLSH_NUM_HEADING_RE = re.compile(r"^(\d{1,2}(?:\.\d{1,2})*)\.?\s+(\S.*)$")


# ---- metadata header -----------------------------------------------------

def split_md_metadata_header(text):
    """Return (header, body): the leading block of 'Label: value' metadata
    lines exactly as found (empty string when absent) and the rest."""
    if not text:
        return "", text or ""
    labels = "|".join(re.escape(v) for v in HEADER_LABELS.values())
    line_re = re.compile(r"^(?:%s)\s*:" % labels)
    lines = text.split("\n")
    i, seen = 0, 0
    while i < len(lines):
        stripped = lines[i].strip()
        if not stripped:
            if seen == 0:
                i += 1
                continue
            break
        if line_re.match(stripped):
            seen += 1
            i += 1
            continue
        break
    if seen < 2:
        return "", text
    return "\n".join(lines[:i]).rstrip("\n"), "\n".join(lines[i:]).lstrip("\n")


# ---- helpers -------------------------------------------------------------

def _plsh_content_fingerprint(text):
    """Letters/punctuation only: whitespace, hyphens and markdown markers are
    ignored, so re-wrapping and hyphen repair compare equal."""
    return re.sub(r"[\s\-\u2010\u2011\u2013\u2014#*|>`]+", "", text or "")


def _plsh_is_table_or_code(lines):
    return any(l.lstrip()[:3] in ("```", "~~~") or l.lstrip().startswith("|")
               for l in lines)


def _plsh_normalize_chars(text, stats):
    t = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    t = t.replace("\u00ad", "")                            # soft hyphen
    for ch in ("\u200b", "\u200c", "\u200d", "\ufeff"):    # zero width
        t = t.replace(ch, "")
    for ch in ("\u00a0", "\u202f", "\u2007", "\u2009", "\u2002", "\u2003"):
        t = t.replace(ch, " ")
    t = t.replace("\t", " ")
    pages = t.count("\x0c")
    if pages:
        stats["pages"] = stats.get("pages", 0) + pages
    return t


def _plsh_unescape_entities(text, stats):
    if "&" not in text:
        return text
    import html as _html
    fixed, n = _PLSH_ENTITY_RE.subn(lambda m: _html.unescape(m.group(0)), text)
    if n:
        stats["entities"] = stats.get("entities", 0) + n
    return fixed


def _plsh_strip_noise(text, stats):
    n = 0
    text, k = _PLSH_HTML_TAG_RE.subn("", text)
    n += k
    text, k = _PLSH_NOISE_TAG_RE.subn("", text)
    n += k
    text, k = _PLSH_NOISE_CHARS_RE.subn("", text)
    n += k
    lines = []
    for ln in text.split("\n"):
        ln2 = _PLSH_SPEAKER_ARROW_RE.sub("", ln)
        if ln2 != ln:
            n += 1
        lines.append(ln2)
    if n:
        stats["noise"] = stats.get("noise", 0) + n
    return "\n".join(lines)


def _plsh_drop_page_markers(text, stats):
    kept, dropped = [], 0
    for ln in text.split("\n"):
        s = ln.replace("\x0c", "").strip()
        if s and _PLSH_PAGE_MARKER_RE.match(s):
            dropped += 1
            continue
        kept.append(ln)
    if dropped:
        stats["page_markers"] = stats.get("page_markers", 0) + dropped
    return "\n".join(kept)


def _plsh_blocks(text):
    """Paragraph blocks + a flag telling whether the block starts on a new PDF
    page (form feed), i.e. the break may be a page cut, not a paragraph."""
    blocks = []
    for chunk in re.split(r"\n[ \t]*\n", text):
        lines = [l for l in chunk.split("\n") if l.strip()]
        if not lines:
            continue
        page_break = lines[0].lstrip(" \t").startswith("\x0c")
        lines = [l.replace("\x0c", "").rstrip() for l in lines if l.strip()]
        lines = [l for l in lines if l.strip()]
        if lines:
            blocks.append((lines, page_break))
    return blocks


def _plsh_can_follow(prev, cur):
    """True when `cur` is the continuation of the wrapped line `prev`."""
    if prev is None:
        return False
    p, c = prev.strip(), cur.lstrip()
    if not p or not c:
        return False
    if p.startswith("#") or p.endswith("|") or p.startswith("|"):
        return False
    if _PLSH_BLOCK_START_RE.match(c):
        return False
    return True


def _plsh_glue(prev, cur):
    p = prev.rstrip()
    return p + cur.lstrip() if p.endswith("-") else p + " " + cur.lstrip()


def _plsh_join_block(lines, stats, wrapped_only=True):
    """Re-join lines broken mid-paragraph. wrapped_only=True (documents) joins
    only lines long enough to have been wrapped by the layout; False (prose)
    joins whenever the previous line stops mid-sentence."""
    out = []
    for ln in lines:
        prev = out[-1] if out else None
        ok = _plsh_can_follow(prev, ln)
        if ok:
            p = prev.strip()
            if wrapped_only:
                ok = len(p) >= POLISH_WRAP_MIN
            else:
                ok = p[-1] not in _PLSH_SENT_END
        if ok:
            out[-1] = _plsh_glue(prev, ln)
            stats["joined"] = stats.get("joined", 0) + 1
        else:
            out.append(ln)
    return out


def _plsh_reflow(text, stats):
    paras = []
    for lines, page_break in _plsh_blocks(text):
        if _plsh_is_table_or_code(lines):
            paras.append(lines)
            continue
        joined = _plsh_join_block(lines, stats, wrapped_only=True)
        first = joined[0].lstrip()
        looks_heading = (first.startswith("#")
                         or bool(_PLSH_NUM_HEADING_RE.match(first))
                         or first.strip().lower().rstrip(":") in _PLSH_SECTION_WORDS)
        continues = page_break or first[:1].islower()
        prev_line = paras[-1][-1].strip() if paras else ""
        if (paras and continues and not looks_heading
                and not _PLSH_BLOCK_START_RE.match(first)
                and not _plsh_is_table_or_code(paras[-1])
                and not prev_line.startswith("#")
                and len(prev_line) >= POLISH_WRAP_MIN
                and prev_line[-1] not in _PLSH_SENT_END):
            paras[-1][-1] = _plsh_glue(paras[-1][-1], first)
            stats["rejoined_pages"] = stats.get("rejoined_pages", 0) + 1
            if joined[1:]:
                paras.append(joined[1:])
        else:
            paras.append(joined)
    return paras


def _plsh_tidy_spaces(line):
    line = re.sub(r"[ ]{2,}", " ", line)
    line = re.sub(r" +([,.;:!?…])", r"\1", line)
    line = re.sub(r"\(\s+", "(", line)
    line = re.sub(r"\s+\)", ")", line)
    return line.strip()


def _plsh_fix_hyphen_consistency(text, stats):
    """PDF extraction sometimes eats the hyphen of a compound broken across
    lines ("frequência-mestre" -> "frequênciamestre"). Repaired only when the
    same document spells it with a hyphen at least 3x and the glued form is
    rare, so no valid word is rewritten on a guess. Each change is reported."""
    counts = {}
    for m in re.finditer(r"\b[A-Za-zÀ-ÿ]{3,}-[A-Za-zÀ-ÿ]{3,}\b", text):
        counts[m.group(0)] = counts.get(m.group(0), 0) + 1
    fixes = []
    for compound, n_hyph in counts.items():
        if n_hyph < 3:
            continue
        glued = compound.replace("-", "")
        n_glued = len(re.findall(r"\b" + re.escape(glued) + r"\b", text))
        if 0 < n_glued <= 2 and n_glued * 3 <= n_hyph:
            text = re.sub(r"\b" + re.escape(glued) + r"\b", compound, text)
            fixes.append("%s > %s (%dx)" % (glued, compound, n_glued))
    if fixes:
        stats.setdefault("hyphens", []).extend(fixes)
    return text


def _plsh_followed_by_prose(paras, idx):
    """True when the next block is body text. A numbered line followed by a
    paragraph is a section title; followed by another short line it is a list
    item, and must stay one."""
    nxt = paras[idx + 1] if idx + 1 < len(paras) else None
    if not nxt or _plsh_is_table_or_code(nxt):
        return False
    if _PLSH_BLOCK_START_RE.match(nxt[0].lstrip()):
        return False
    return (len(nxt[0].strip()) >= POLISH_WRAP_MIN
            or len(" ".join(nxt).strip()) >= 200)


def _plsh_promote_headings(paras, stats):
    out, seen_title = [], False
    for idx, lines in enumerate(paras):
        if len(lines) == 1 and not _plsh_is_table_or_code(lines):
            s = lines[0].strip()
            if (3 <= len(s) <= 100 and not s.startswith("#")
                    and not s.rstrip().endswith(".")):
                m = _PLSH_NUM_HEADING_RE.match(s)
                low = s.lower().rstrip(":")
                letters = [c for c in s if c.isalpha()]
                if (m and m.group(2)[:1].isupper()
                        and _plsh_followed_by_prose(paras, idx)):
                    out.append(["## %s. %s" % (m.group(1), m.group(2))])
                    stats["headings"] = stats.get("headings", 0) + 1
                    continue
                if _PLSH_BLOCK_START_RE.match(s):
                    out.append(lines)          # real list item / quote / table
                    continue
                if low in _PLSH_SECTION_WORDS:
                    out.append(["## " + s])
                    stats["headings"] = stats.get("headings", 0) + 1
                    continue
                if (letters and all(c.isupper() for c in letters)
                        and len(s.split()) >= 2):
                    out.append([("# " if not seen_title else "## ") + s])
                    seen_title = True
                    stats["headings"] = stats.get("headings", 0) + 1
                    continue
        out.append(lines)
    return out


_PLSH_TS_MARKER_RE = re.compile(r"^\[t=\d{1,2}:\d{2}(?::\d{2})?\]\s*")
_PLSH_SENT_SPLIT_RE = re.compile(r"(?<=[.!?…])\s+")


def _plsh_normalize_for_compare(s):
    """Lowercase, punctuation-free comparison key. Strips an optional
    leading "[t=MM:SS]" timestamp anchor (item 1) first, so two near-
    identical sentences with different anchors still compare equal."""
    s = _PLSH_TS_MARKER_RE.sub("", s or "")
    s = re.sub(r"[^\w\s]", "", s, flags=re.UNICODE).lower()
    return re.sub(r"\s+", " ", s).strip()


def _plsh_collapse_repeated_sentences(text, stats, min_run=3):
    """item 2 (v0.11.01): Whisper sometimes repeats the same sentence many
    times in a row on silence/noise/out-of-domain audio. Collapses runs of
    `min_run`+ consecutive near-identical sentences down to the first
    occurrence — which also keeps whichever timestamp anchor that first
    occurrence carried. Only touches single-line paragraphs (plain prose);
    multi-line blocks (lists, tables, heading groups) are left untouched
    since they can't be safely sentence-split and rejoined."""
    paragraphs = text.split("\n\n")
    out_paragraphs = []
    total_removed = 0
    for para in paragraphs:
        if "\n" in para or not para.strip():
            out_paragraphs.append(para)
            continue
        sentences = _PLSH_SENT_SPLIT_RE.split(para)
        if len(sentences) < min_run:
            out_paragraphs.append(para)
            continue
        kept = []
        i, n = 0, len(sentences)
        while i < n:
            norm_i = _plsh_normalize_for_compare(sentences[i])
            j = i + 1
            if norm_i:
                while j < n and _plsh_normalize_for_compare(sentences[j]) == norm_i:
                    j += 1
            run_len = j - i
            if run_len >= min_run:
                kept.append(sentences[i])
                total_removed += run_len - 1
            else:
                kept.extend(sentences[i:j])
            i = j
        out_paragraphs.append(" ".join(kept))
    if total_removed:
        stats["repeats_collapsed"] = stats.get("repeats_collapsed", 0) + total_removed
    return "\n\n".join(out_paragraphs)


def _plsh_near_duplicate(norm_a, norm_b, threshold=0.88):
    """item 3 (v0.11.01): similar-but-not-identical text, the classic
    signature of an extractor duplicating/scrambling a passage. Exact
    matches are excluded here (those are usually legitimate repeated
    boilerplate, e.g. a repeated header) — only near-misses are flagged.

    v0.12.0: the guard+ratio body now lives in the shared
    `text_similarity_ratio()` helper (also used by the Comparison engine)
    so the two stay in sync; behavior here is unchanged."""
    if not norm_a or not norm_b or norm_a == norm_b:
        return False
    return text_similarity_ratio(norm_a, norm_b) >= threshold


def _plsh_collect_suspects(paras):
    """Blocks that look like extractor scramble (orphan fragments, column
    bleed, near-duplicate passages). Reported only — never repaired by
    guessing."""
    suspects = []
    recent_norms = []  # item 3: sliding window for the near-duplicate scan
    for lines in paras:
        block = " ".join(lines).strip()
        if not block or block.startswith("#") or _plsh_is_table_or_code(lines):
            recent_norms.append(None)
            continue
        flagged = False
        if re.search(r"   +", block):          # column bleed inside a line
            suspects.append(block[:80])
            flagged = True
        # Orphan fragment: a handful of words starting mid-sentence. Cover
        # lines ("Maio de 2026") and sign-offs start with a capital, so they
        # are not flagged.
        if (not flagged and len(block) <= 120 and len(block.split()) <= 6
                and block[:1].islower() and block[-1] not in _PLSH_SENT_END):
            suspects.append(block[:80])
            flagged = True
        # item 3: windowed near-duplicate scan — a paragraph that nearly
        # (but not exactly) repeats one from a few paragraphs back often
        # means the extractor duplicated/scrambled a passage.
        norm = _plsh_normalize_for_compare(block)
        if not flagged:
            for prev_norm in [n for n in recent_norms[-6:] if n]:
                if _plsh_near_duplicate(prev_norm, norm):
                    suspects.append(block[:80])
                    break
        recent_norms.append(norm)
    seen, out = set(), []
    for s in suspects:
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


# ---- public API ----------------------------------------------------------

def polish_markdown(text, *, profile="document", promote_headings=None,
                    fix_hyphens=None):
    """Clean a Markdown body for LLM training. Returns (new_text, stats).

    v0.13.7: profile split from a single "document" boolean into three
    purpose-specific flags, to add "document-clean" without touching
    "document"/"prose" behavior at all (reflow/strip_noise/drop_markers
    compute to the exact same values for those two as before).
      "document"       — MarkItDown output: full reflow (undoes its
                          fixed-width visual line wrap), hyphen repair,
                          heading promotion.
      "document-clean" — Docling/Pandoc output: already reflow-free
                          (Pandoc's -t gfm --wrap=none and Docling's own
                          layout-aware extraction don't hard-wrap), so
                          running the same reflow/hyphen-repair logic
                          tuned for MarkItDown's raw passthrough risks
                          "fixing" artifacts that were never there —
                          paragraph-preserving cleanup only, same as
                          "prose", but WITHOUT the spoken-transcript
                          noise stripping (real document content, not an
                          ASR/subtitle transcript).
      "prose"           — text this app already turned into prose
                          itself (SRT/VTT/TXT, Whisper, YouTube):
                          whitespace/noise + mid-sentence line breaks
                          only, paragraph structure untouched.
    """
    stats = {}
    if not (text or "").strip():
        return (text or ""), stats
    reflow = (profile == "document")
    strip_transcript_noise = (profile == "prose")
    drop_page_markers = (profile in ("document", "document-clean"))
    if promote_headings is None:
        promote_headings = reflow
    if fix_hyphens is None:
        fix_hyphens = reflow

    # Character-level stage: always safe, always applied.
    safe = _plsh_normalize_chars(text, stats)
    safe = _plsh_unescape_entities(safe, stats)
    if strip_transcript_noise:
        safe = _plsh_strip_noise(safe, stats)
    if drop_page_markers:
        safe = _plsh_drop_page_markers(safe, stats)
    safe = "\n".join(l.rstrip() for l in safe.split("\n"))

    # Fenced code: re-wrapping could corrupt it, so stop at the safe stage.
    if _PLSH_FENCE_RE.search(safe):
        stats["fenced"] = True
        out = re.sub(r"\n{3,}", "\n\n", safe).strip() + "\n"
        stats["changed"] = (out != text)
        return out, stats

    # Structural stage: re-wrapping, hyphens, headings.
    if reflow:
        paras = _plsh_reflow(safe, stats)
    else:
        paras = []
        for chunk in re.split(r"\n[ \t]*\n", safe):
            lines = [l for l in chunk.split("\n") if l.strip()]
            if lines:
                paras.append(_plsh_join_block(lines, stats, wrapped_only=False))
    tidied = []
    for lines in paras:
        new = [l if _plsh_is_table_or_code([l]) else _plsh_tidy_spaces(l)
               for l in lines]
        new = [l for l in new if l.strip()]
        if new:
            tidied.append(new)
    paras = tidied
    if promote_headings:
        paras = _plsh_promote_headings(paras, stats)
    built = "\n\n".join("\n".join(lines) for lines in paras)
    if fix_hyphens:
        built = _plsh_fix_hyphen_consistency(built, stats)

    # Guard: the structural stage may not drop a single character of content.
    if _plsh_content_fingerprint(built) != _plsh_content_fingerprint(safe):
        for k in ("joined", "rejoined_pages", "headings", "hyphens"):
            stats.pop(k, None)
        stats["guard"] = True
        out = re.sub(r"\n{3,}", "\n\n", safe).strip() + "\n"
        stats["changed"] = (out != text)
        return out, stats

    if reflow:
        sus = _plsh_collect_suspects(paras)
        if sus:
            stats["suspects"] = sus[:8]

    # item 2 (v0.11.01): repetition collapse is a deliberate content change,
    # so it runs after the fidelity guard above (which only checks the
    # reflow stage didn't accidentally lose text) rather than being caught
    # by it.
    built = _plsh_collapse_repeated_sentences(built, stats)

    out = re.sub(r"\n{3,}", "\n\n", built).strip() + "\n"
    stats["changed"] = (out != text)
    return out, stats


def polish_md_file(path, *, profile="document", promote_headings=None,
                   fix_hyphens=None):
    """Polish an .md file in place, keeping the metadata header verbatim.
    Never raises: returns the stats dict, or {"error": ...} on failure."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            original = f.read()
    except OSError as e:
        return {"error": str(e)}
    header, body = split_md_metadata_header(original)
    try:
        polished, stats = polish_markdown(
            body, profile=profile, promote_headings=promote_headings,
            fix_hyphens=fix_hyphens)
    except Exception as e:                       # a batch must never die here
        return {"error": str(e)}
    new_text = (header.rstrip("\n") + "\n\n" + polished) if header else polished
    if new_text == original:
        stats["changed"] = False
        return stats
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_text)
    except OSError as e:
        return {"error": str(e)}
    stats["changed"] = True
    return stats


def polish_profile_for_path(path):
    """MarkItDown output of a real document needs the full treatment; anything
    this app turned into prose itself only needs the light pass."""
    ext = os.path.splitext(path or "")[1].lower()
    if ext in (".srt", ".vtt", ".txt"):
        return "prose"
    return "document"


def polish_profile_for_model(model_id, path):
    """v0.13.7: model-aware version of polish_profile_for_path() above,
    for the future UI wiring (v0.13.8) once more than one conversion
    model is actually selectable. Not called anywhere yet in this
    version — defined and tested now so that wiring doesn't also have to
    design this decision. Subtitle/transcript bypass paths (.srt/.vtt/
    .txt) still always get "prose" regardless of model, same as today —
    that bypass is independent of which document-conversion model is
    selected."""
    ext = os.path.splitext(path or "")[1].lower()
    if ext in (".srt", ".vtt", ".txt"):
        return "prose"
    if model_id in ("docling", "pandoc"):
        return "document-clean"
    return "document"


def format_polish_stats(stats, strings=None):
    """Compact, localized one-liner for the log. '' when nothing changed."""
    def t(key, default, **kw):
        tpl = (strings or {}).get(key, default)
        try:
            return tpl.format(**kw)
        except Exception:
            return default.format(**kw)
    if not stats or stats.get("error"):
        return ""
    parts = []
    if stats.get("joined"):
        parts.append(t("polish_stat_joined", "{n} lines rejoined",
                       n=stats["joined"]))
    if stats.get("rejoined_pages"):
        parts.append(t("polish_stat_pages_joined",
                       "{n} paragraphs rejoined across pages",
                       n=stats["rejoined_pages"]))
    if stats.get("pages"):
        parts.append(t("polish_stat_pages", "{n} page breaks", n=stats["pages"]))
    if stats.get("page_markers"):
        parts.append(t("polish_stat_page_numbers", "{n} page numbers removed",
                       n=stats["page_markers"]))
    if stats.get("noise"):
        parts.append(t("polish_stat_noise", "{n} caption marks removed",
                       n=stats["noise"]))
    if stats.get("entities"):
        parts.append(t("polish_stat_entities", "{n} HTML entities",
                       n=stats["entities"]))
    if stats.get("headings"):
        parts.append(t("polish_stat_headings", "{n} headings", n=stats["headings"]))
    if stats.get("hyphens"):
        parts.append(t("polish_stat_hyphens", "hyphens: {list}",
                       list="; ".join(stats["hyphens"])))
    if stats.get("repeats_collapsed"):
        parts.append(t("polish_stat_repeats", "{n} consecutive repeats removed",
                       n=stats["repeats_collapsed"]))
    if stats.get("fenced"):
        parts.append(t("polish_stat_fenced", "code blocks preserved"))
    return ", ".join(parts)


def _polish_report(stats, log_cb, strings):
    """Send one polish result to a worker log (localized, best-effort)."""
    if not log_cb:
        return stats
    s = strings or {}

    def _log(key, default, **kw):
        tpl = s.get(key, default)
        try:
            log_cb(tpl.format(**kw))
        except Exception:
            log_cb(default.format(**kw))

    if stats.get("error"):
        _log("log_md_polish_error",
             "[WARNING] Polish failed ({e}); the MD was left as it was.\n",
             e=stats["error"])
        return stats
    summary = format_polish_stats(stats, s)
    if summary:
        _log("log_md_polish_done", "Polish: {stats}\n", stats=summary)
    else:
        _log("log_md_polish_none", "Polish: nothing to fix.\n")
    if stats.get("guard"):
        _log("log_md_polish_guard",
             "[ATTENTION] Paragraph re-flow was discarded as a safety measure; "
             "the original content was kept.\n")
    if stats.get("suspects"):
        _log("log_md_polish_suspects",
             "[ATTENTION] {n} passage(s) possibly scrambled by the converter. "
             "Nothing was guessed; please review by hand: {samples}\n",
             n=len(stats["suspects"]), samples=" | ".join(stats["suspects"]))
    return stats


def polish_md_and_log(path, *, profile="document", enabled=True, log_cb=None,
                      strings=None):
    """Polish an .md file on disk and report it. Never raises."""
    if not enabled or not path:
        return {}
    try:
        if not os.path.exists(path):
            return {}
    except OSError:
        return {}
    if log_cb:
        log_cb((strings or {}).get("log_md_polish",
                                   "Polishing the MD for AI training...\n"))
    stats = polish_md_file(path, profile=profile)
    return _polish_report(stats, log_cb, strings)


def polish_md_text_and_log(text, *, profile="prose", enabled=True, log_cb=None,
                           strings=None):
    """Polish Markdown still held in memory (YouTube transcripts). Returns the
    polished text; on any failure the input is returned unchanged."""
    if not enabled or not (text or "").strip():
        return text
    if log_cb:
        log_cb((strings or {}).get("log_md_polish",
                                   "Polishing the MD for AI training...\n"))
    try:
        polished, stats = polish_markdown(text, profile=profile)
    except Exception as e:
        _polish_report({"error": str(e)}, log_cb, strings)
        return text
    _polish_report(stats, log_cb, strings)
    return polished


def sleep_with_jitter(stop_flag, lo, hi):
    """Cancellable randomized delay in [lo, hi] seconds."""
    import random
    target = random.uniform(lo, hi)
    end = time.time() + target
    while time.time() < end:
        if stop_flag is not None and stop_flag.is_set():
            return
        time.sleep(0.05)


def cancellable_sleep(stop_flag, seconds, tick_cb=None):
    """Sleep `seconds`, checking stop_flag every 0.2s. tick_cb(remaining_int)
    is called about once per second. Returns False if interrupted."""
    end = time.time() + max(0.0, float(seconds))
    last_tick = None
    while time.time() < end:
        if stop_flag is not None and stop_flag.is_set():
            return False
        if tick_cb is not None:
            rem = int(round(end - time.time()))
            if rem != last_tick:
                last_tick = rem
                try:
                    tick_cb(rem)
                except Exception:
                    pass
        time.sleep(0.2)
    return not (stop_flag is not None and stop_flag.is_set())


def build_whisper_command(whisper_exe, media_path, out_dir, model, task,
                          lang_param, initial_prompt, model_dir=None):
    """Pure: build the Whisper CLI command (output_format all). model_dir
    (item 1.3) keeps downloaded models inside the portable tools/ folder."""
    cmd = [whisper_exe, media_path, "--model", model, "--task", task,
           "--fp16", "False", "--output_dir", out_dir,
           "--output_format", "all", "--verbose", "True",
           "--model_dir", model_dir or whisper_cache_dir()]
    if lang_param:
        cmd += ["--language", lang_param]
    if initial_prompt:
        cmd += ["--initial_prompt", initial_prompt]
    return cmd


def apply_replacements_to_file(path, replacements):
    if not path or not os.path.exists(path) or not replacements:
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        for find, replace in replacements:
            if find:
                content = content.replace(find, replace)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
    except OSError:
        pass


def whisper_transcribe_file(whisper_exe, media_path, out_dir, *, model, task,
                            lang_param, initial_prompt, replacements,
                            keep_formats, stop_flag=None, log_cb=None,
                            header_fields=None, ffmpeg_path=None,
                            polish=True, strings=None, header_lang="pt",
                            keep_timestamps=False):
    os.makedirs(out_dir, exist_ok=True)
    base = os.path.splitext(os.path.basename(media_path))[0]
    cmd = build_whisper_command(whisper_exe, media_path, out_dir, model, task,
                                lang_param, initial_prompt)
    if log_cb:
        log_cb("Command: " + " ".join(cmd) + "\n")
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        encoding="utf-8", errors="replace", bufsize=1,
        env=whisper_child_env(ffmpeg_path), **subprocess_hidden_window_kwargs())
    env_broken = False
    for line in proc.stdout:
        if stop_flag is not None and stop_flag.is_set():
            try:
                proc.terminate()
            except OSError:
                pass
            break
        if log_cb:
            log_cb(line)
        if is_environment_fatal_output(line):
            env_broken = True
    proc.wait()
    if stop_flag is not None and stop_flag.is_set():
        return None
    if proc.returncode != 0:
        if env_broken:
            raise EnvironmentBrokenError(
                f"whisper exited with code {proc.returncode} (Python environment broken).")
        raise RuntimeError(f"whisper exited with code {proc.returncode}.")

    def fp(ext):
        return os.path.join(out_dir, base + "." + ext)

    if replacements:
        for ext in ("txt", "srt", "vtt", "tsv"):
            apply_replacements_to_file(fp(ext), replacements)
    if "md" in (keep_formats or []):
        made = False
        for ext in ("srt", "vtt"):
            if os.path.exists(fp(ext)):
                convert_subtitle_file_to_md(fp(ext), fp("md"), title=None,
                                           keep_timestamps=keep_timestamps)
                made = True
                break
        if not made and os.path.exists(fp("txt")):
            with open(fp("txt"), "r", encoding="utf-8", errors="replace") as f:
                txt = f.read()
            prose = "\n\n".join(s.strip() for s in re.split(r"\n\s*\n", txt) if s.strip())
            with open(fp("md"), "w", encoding="utf-8") as f:
                f.write(prose.strip() + "\n")
        if replacements:
            apply_replacements_to_file(fp("md"), replacements)
        # v0.10.5 — polish before the header goes in, so the polish never sees
        # (nor rewrites) the metadata block.
        polish_md_and_log(fp("md"), profile="prose", enabled=polish,
                          log_cb=log_cb, strings=strings)
        if header_fields and os.path.exists(fp("md")):
            prepend_header_to_file(fp("md"), build_md_header(header_fields, lang=header_lang))
    for ext in WHISPER_FORMATS:
        if ext not in (keep_formats or []) and os.path.exists(fp(ext)):
            try:
                os.remove(fp(ext))
            except OSError:
                pass
    return base


# --------------------------------------------------------------------------
# Time-range clipping + timestamp shifting on output
# --------------------------------------------------------------------------

_HMS_INPUT_RE = re.compile(r"^\s*(?:(\d+):)?(\d{1,2}):(\d{1,2})(?:[.,](\d{1,3}))?\s*$")


def parse_hms_to_seconds(text):
    if text is None:
        return None
    text = text.strip()
    if not text:
        return None
    m = _HMS_INPUT_RE.match(text)
    if not m:
        return None
    h, mm, ss, frac = m.group(1), m.group(2), m.group(3), m.group(4)
    try:
        total = int(mm) * 60 + int(ss)
        if h:
            total = int(h) * 3600 + total
        if frac:
            total += float("0." + frac)
        return float(total)
    except ValueError:
        return None


def seconds_to_hms_input(seconds):
    if seconds is None:
        return ""
    seconds = max(0, int(round(seconds)))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}"


def build_ffmpeg_clip_command(ffmpeg_path, src_path, dst_path, start_seconds, end_seconds):
    duration = max(0.0, end_seconds - start_seconds)
    return [ffmpeg_path, "-y", "-ss", f"{start_seconds:.3f}", "-i", src_path,
            "-t", f"{duration:.3f}", "-c", "copy", dst_path]


def shift_srt_vtt_timestamps(content, offset_seconds, is_vtt=False):
    sep = "." if is_vtt else ","
    pattern = re.compile(r"(\d{2}):(\d{2}):(\d{2})[.,](\d{3})")

    def _shift(m):
        h, mm, ss, ms = (int(m.group(1)), int(m.group(2)),
                         int(m.group(3)), int(m.group(4)))
        total_ms = ((h * 3600 + mm * 60 + ss) * 1000 + ms
                    + int(round(offset_seconds * 1000)))
        total_ms = max(0, total_ms)
        h2, rem = divmod(total_ms, 3600_000)
        m2, rem = divmod(rem, 60_000)
        s2, ms2 = divmod(rem, 1000)
        return f"{h2:02d}:{m2:02d}:{s2:02d}{sep}{ms2:03d}"

    return pattern.sub(_shift, content)


def shift_tsv_timestamps(content, offset_seconds):
    offset_ms = int(round(offset_seconds * 1000))
    lines = content.splitlines(keepends=False)
    if not lines:
        return content
    out = [lines[0]]
    for line in lines[1:]:
        if not line.strip():
            out.append(line)
            continue
        parts = line.split("\t")
        if len(parts) >= 2:
            try:
                parts[0] = str(int(parts[0]) + offset_ms)
                parts[1] = str(int(parts[1]) + offset_ms)
            except ValueError:
                pass
        out.append("\t".join(parts))
    return "\n".join(out) + ("\n" if content.endswith("\n") else "")


def shift_json_timestamps(content, offset_seconds):
    try:
        data = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return content

    def _bump(obj):
        if isinstance(obj, dict):
            for key in ("start", "end"):
                if key in obj and isinstance(obj[key], (int, float)):
                    obj[key] = obj[key] + offset_seconds
            for v in obj.values():
                _bump(v)
        elif isinstance(obj, list):
            for v in obj:
                _bump(v)

    _bump(data)
    return json.dumps(data, ensure_ascii=False, indent=2)


def shift_output_timestamps(path, fmt, offset_seconds):
    if offset_seconds == 0 or fmt in ("txt", "md") or not path or not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        if fmt == "srt":
            content = shift_srt_vtt_timestamps(content, offset_seconds, is_vtt=False)
        elif fmt == "vtt":
            content = shift_srt_vtt_timestamps(content, offset_seconds, is_vtt=True)
        elif fmt == "tsv":
            content = shift_tsv_timestamps(content, offset_seconds)
        elif fmt == "json":
            content = shift_json_timestamps(content, offset_seconds)
        else:
            return
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
    except OSError:
        pass


# ==========================================================================
# Comparison engine (v0.12.0) — cheap pre-check, before running whisper
# medium on a batch, for (a) content that already exists as an MD
# transcript in a folder the user maintains, and (b) files in the same
# batch that are the same source under different names. All functions
# below are pure (no I/O, no subprocess) so they're unit-testable directly;
# ComparisonWorker (further down, with the other Thread workers) is the
# only piece that actually touches ffmpeg/whisper/disk.
# ==========================================================================

# Phase 1 — sample points, as % of duration. Short files (< the existing
# "Short" cutoff, item 12 / v0.11.0) get 3 points instead of 5.
COMPARISON_SAMPLE_POINTS_LONG = (15, 30, 45, 60, 75)
COMPARISON_SAMPLE_POINTS_SHORT = (25, 50, 75)
COMPARISON_SHORT_CUTOFF_SECONDS = 600  # matches the literal 0 < dur < 600 elsewhere

COMPARISON_EXCERPT_SECONDS_DEFAULT = 30
COMPARISON_EXCERPT_SECONDS_MIN = 15
COMPARISON_EXCERPT_SECONDS_MAX = 90

COMPARISON_SILENCE_SHIFT_STEP = 15   # seconds, per retry
COMPARISON_SILENCE_MAX_SHIFTS = 2
COMPARISON_SILENCE_NOISE_DB = -30
COMPARISON_SILENCE_MIN_DURATION = 1
COMPARISON_SILENCE_RATIO = 0.5   # clip counted "mostly silence" at/above this

# Phase 2 — matching/tiering. Deliberately far below the MD-polish engine's
# 0.88 near-duplicate threshold (reuse map): a tiny-model transcript of a
# few seconds vs. a clean reference transcript will legitimately score
# lower than same-quality-source-vs-itself.
COMPARISON_POINT_AGREE_THRESHOLD = 0.55
COMPARISON_LIKELY_THRESHOLD_DEFAULT = 0.75
COMPARISON_POSSIBLE_THRESHOLD_DEFAULT = 0.55
COMPARISON_DURATION_TOLERANCE_DEFAULT = 0.15   # 15%
# v0.12.1: separate, deliberately wider tolerance for the duration
# pre-filter (an active "skip this candidate" decision) vs. the 15% above
# (a "soften the tier" decision) — see should_skip_by_duration_mismatch.
COMPARISON_DURATION_PREFILTER_TOLERANCE = 0.5
COMPARISON_TOP_CANDIDATES_PER_FILE = 3
# Cheap pre-filter before the full windowed difflib pass (2a step 3 note):
# skip a candidate outright if it shares fewer than this fraction of the
# excerpt's distinct words.
COMPARISON_PREFILTER_MIN_SHARED_RATIO = 0.15

COMPARISON_TIER_LIKELY = "likely"
COMPARISON_TIER_POSSIBLE = "possible"
COMPARISON_TIER_NONE = "none"


def comparison_sample_point_percents(duration_seconds):
    """Phase 1 step 2."""
    if duration_seconds is not None and duration_seconds < COMPARISON_SHORT_CUTOFF_SECONDS:
        return COMPARISON_SAMPLE_POINTS_SHORT
    return COMPARISON_SAMPLE_POINTS_LONG


def comparison_sample_window(duration_seconds, percent, window_seconds):
    """Phase 1 step 3: window centered on `percent` of duration, clamped to
    [0, duration_seconds]. Returns (start, end) in seconds."""
    if not duration_seconds or duration_seconds <= 0:
        return 0.0, 0.0
    center = duration_seconds * (percent / 100.0)
    half = window_seconds / 2.0
    start, end = center - half, center + half
    if start < 0:
        end -= start
        start = 0.0
    if end > duration_seconds:
        start -= (end - duration_seconds)
        end = duration_seconds
    start = max(0.0, start)
    end = min(duration_seconds, max(start, end))
    return start, end


def comparison_shift_window_forward(start, end, duration_seconds, step=COMPARISON_SILENCE_SHIFT_STEP):
    """Phase 1 step 4: shift a window forward by `step` seconds, re-clamped
    to file bounds, keeping its length constant where possible."""
    length = end - start
    new_start = start + step
    new_end = new_start + length
    if duration_seconds and new_end > duration_seconds:
        new_end = duration_seconds
        new_start = max(0.0, new_end - length)
    return new_start, new_end


def comparison_excerpt_total_seconds(excerpt_seconds, duration_seconds=None):
    """Phase 4 point 1: total *extracted audio* seconds for one file at the
    current excerpt length — used for the live-computed settings line.
    duration_seconds is optional context only (to note the Short case);
    the count of points is what actually drives the total."""
    n_points = len(comparison_sample_point_percents(duration_seconds))
    return excerpt_seconds * n_points, n_points


_SILENCE_START_RE = re.compile(r"silence_start:\s*([0-9.]+)")
_SILENCE_END_RE = re.compile(r"silence_end:\s*([0-9.]+)\s*\|\s*silence_duration:\s*([0-9.]+)")


def build_silencedetect_command(ffmpeg_path, clip_path, noise_db=COMPARISON_SILENCE_NOISE_DB,
                                min_duration=COMPARISON_SILENCE_MIN_DURATION):
    """Phase 1 step 4."""
    return [ffmpeg_path, "-i", clip_path, "-af",
           f"silencedetect=noise={noise_db}dB:d={min_duration}", "-f", "null", "-"]


def parse_silence_seconds(ffmpeg_output_text, clip_duration):
    """Total silent seconds inside a clip, from ffmpeg's silencedetect
    filter output (stderr, merged with stdout the same way every other
    ffmpeg/whisper call in this app captures it). A silence_start with no
    matching silence_end (silence running to the end of the clip) counts
    through clip_duration."""
    total = 0.0
    pending_start = None
    for line in (ffmpeg_output_text or "").splitlines():
        m_end = _SILENCE_END_RE.search(line)
        if m_end:
            total += float(m_end.group(2))
            pending_start = None
            continue
        m_start = _SILENCE_START_RE.search(line)
        if m_start:
            pending_start = float(m_start.group(1))
    if pending_start is not None and clip_duration:
        total += max(0.0, clip_duration - pending_start)
    return total


def clip_is_mostly_silence(ffmpeg_output_text, clip_duration, ratio=COMPARISON_SILENCE_RATIO):
    """Phase 1 step 4."""
    if not clip_duration:
        return False
    return parse_silence_seconds(ffmpeg_output_text, clip_duration) >= clip_duration * ratio


def text_similarity_ratio(a, b):
    """Shared by the MD-polish near-duplicate scan and the Comparison
    engine (reuse map: pulled out of `_plsh_near_duplicate` so the two stay
    in sync). Length-ratio guard before the O(n*m) SequenceMatcher call,
    then difflib.SequenceMatcher.ratio()."""
    if not a or not b:
        return 0.0
    if abs(len(a) - len(b)) > max(len(a), len(b)) * 0.5:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def normalize_md_paragraphs_for_comparison(body_text):
    """Like normalize_md_body_for_comparison, but returns the list of
    normalized paragraphs instead of joining them — used by Scenario 3's
    paragraph-level cross-match (v0.12.1)."""
    paragraphs = re.split(r"\n\s*\n", body_text or "")
    return [p for p in (_plsh_normalize_for_compare(p) for p in paragraphs) if p]


def normalize_md_body_for_comparison(body_text):
    """Phase 2a step 2: split the (header-stripped) MD body into paragraphs
    on blank lines, normalize each with `_plsh_normalize_for_compare`
    (which only strips a *leading* [t=MM:SS] anchor per call — hence the
    per-paragraph split), rejoin with spaces."""
    return " ".join(normalize_md_paragraphs_for_comparison(body_text))


def _shared_word_ratio(excerpt_words_set, candidate_words):
    if not excerpt_words_set or not candidate_words:
        return 0.0
    return len(excerpt_words_set & set(candidate_words)) / len(excerpt_words_set)


def windowed_best_match(excerpt_norm, candidate_norm, size_tolerance=0.2):
    """Phase 2a step 3: slide a window (sized to the excerpt's word count,
    +/-20%) across candidate_norm, stepping by about half the excerpt
    length, scoring each offset with text_similarity_ratio; keep the best.
    Falls back to a single whole-string comparison when the candidate
    isn't longer than the excerpt (nothing to window). Returns
    (best_score, best_window_text) — the window text is normalized (not
    the original casing/punctuation), used for the side-by-side excerpt
    preview in the UI."""
    excerpt_words = excerpt_norm.split()
    candidate_words = candidate_norm.split()
    n_ex = len(excerpt_words)
    if n_ex == 0 or not candidate_words:
        return 0.0, ""
    if len(candidate_words) <= n_ex:
        return text_similarity_ratio(excerpt_norm, candidate_norm), candidate_norm
    sizes = sorted(set(max(1, int(round(n_ex * f)))
                       for f in (1 - size_tolerance, 1.0, 1 + size_tolerance)))
    step = max(1, n_ex // 2)
    n_cand = len(candidate_words)
    best_score, best_window = 0.0, ""
    for size in sizes:
        i = 0
        while i < n_cand:
            window_words = candidate_words[i:i + size]
            if not window_words:
                break
            window_text = " ".join(window_words)
            score = text_similarity_ratio(excerpt_norm, window_text)
            if score > best_score:
                best_score, best_window = score, window_text
            if i + size >= n_cand:
                break
            i += step
    return best_score, best_window


def windowed_best_score(excerpt_norm, candidate_norm, size_tolerance=0.2):
    """Score-only convenience wrapper around windowed_best_match, used by
    the broad prefiltered scan (match_excerpt_against_candidates) where
    the window text itself isn't needed."""
    return windowed_best_match(excerpt_norm, candidate_norm, size_tolerance)[0]


def match_excerpt_against_candidates(excerpt_norm, candidates, word_index=None,
                                     prefilter_min_ratio=COMPARISON_PREFILTER_MIN_SHARED_RATIO,
                                     excerpt_duration=None,
                                     duration_tolerance=COMPARISON_DURATION_PREFILTER_TOLERANCE):
    """Phase 2a step 3 (+ the pre-filters it invites). candidates: list of
    ComparisonCandidate. word_index, if given (build_candidate_word_index),
    narrows the scan to candidates sharing at least one word with the
    excerpt before the per-candidate ratio check — the real win on a large
    Base Folder, since most candidates share nothing. excerpt_duration, if
    given, applies the same safe duration pre-filter Phase 2b already uses
    for intra-queue pairs. Returns [(rel_path, score), ...] for every
    candidate that passed both pre-filters, sorted by score descending.
    Candidates filtered out are absent, not scored 0, so callers can tell
    'skipped' from 'scored low'."""
    excerpt_words = set(excerpt_norm.split())
    pool = candidates
    if word_index is not None and excerpt_words:
        indices = set()
        for w in excerpt_words:
            indices.update(word_index.get(w, ()))
        pool = [candidates[i] for i in indices]
    out = []
    for cand in pool:
        if excerpt_duration and should_skip_by_duration_mismatch(
                excerpt_duration, cand.duration_seconds, duration_tolerance):
            continue
        cand_words = cand.norm_body.split()
        if excerpt_words and _shared_word_ratio(excerpt_words, cand_words) < prefilter_min_ratio:
            continue
        out.append((cand.rel_path, windowed_best_score(excerpt_norm, cand.norm_body)))
    out.sort(key=lambda t: t[1], reverse=True)
    return out


def aggregate_candidate_scores(per_point_best_scores, point_agree_threshold=COMPARISON_POINT_AGREE_THRESHOLD):
    """Phase 2a step 4: per_point_best_scores is one best-score float per
    sample point, all against the same candidate. Returns
    (aggregate_score, points_agreeing)."""
    if not per_point_best_scores:
        return 0.0, 0
    aggregate = sum(per_point_best_scores) / len(per_point_best_scores)
    agreeing = sum(1 for s in per_point_best_scores if s >= point_agree_threshold)
    return aggregate, agreeing


def tier_for_score(score, likely_threshold, possible_threshold):
    """Phase 2a step 6 / 2b step 4."""
    if score >= likely_threshold:
        return COMPARISON_TIER_LIKELY
    if score >= possible_threshold:
        return COMPARISON_TIER_POSSIBLE
    return COMPARISON_TIER_NONE


def top_n_candidates(scored_candidates, n=COMPARISON_TOP_CANDIDATES_PER_FILE):
    """Phase 2a step 5. scored_candidates: [(path, score), ...]."""
    return sorted(scored_candidates, key=lambda t: t[1], reverse=True)[:n]


def compare_excerpt_sets(excerpts_a, excerpts_b, point_agree_threshold=COMPARISON_POINT_AGREE_THRESHOLD):
    """Phase 2b step 1-2: all-pairs (not index-aligned) comparison between
    two files' normalized excerpts. Returns (best_score, points_agreeing)
    where points_agreeing counts excerpt-pairs >= point_agree_threshold."""
    best = 0.0
    agreeing = 0
    for ea in excerpts_a:
        for eb in excerpts_b:
            if not ea or not eb:
                continue
            score = text_similarity_ratio(ea, eb)
            if score > best:
                best = score
            if score >= point_agree_threshold:
                agreeing += 1
    return best, agreeing


def durations_within_tolerance(dur_a, dur_b, tolerance=COMPARISON_DURATION_TOLERANCE_DEFAULT):
    """Phase 2b step 3 duration guard."""
    if not dur_a or not dur_b:
        return False
    return abs(dur_a - dur_b) <= max(dur_a, dur_b) * tolerance


def tier_for_pair(score, dur_a, dur_b, likely_threshold, possible_threshold, duration_tolerance):
    """Phase 2b step 3-4: text score alone can't reach 'likely' unless
    durations are also close — two different lectures can share a recited
    phrase; that alone shouldn't flag them as duplicates."""
    tier = tier_for_score(score, likely_threshold, possible_threshold)
    if tier == COMPARISON_TIER_LIKELY and not durations_within_tolerance(dur_a, dur_b, duration_tolerance):
        tier = COMPARISON_TIER_POSSIBLE
    return tier


class _ComparisonUnionFind:
    """Plain union-find (Phase 2b step 5)."""

    def __init__(self, ids):
        self.parent = {i: i for i in ids}

    def find(self, x):
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[ra] = rb


# ---- v0.12.1: header duration parsing (A2/A4 duration pre-filter) --------

_DURACAO_LINE_RE = re.compile(r"^(?:Dura[cç][aã]o|Duration)\s*:\s*(.+)$", re.IGNORECASE)


def parse_fmt_hms_seconds(text):
    """Reverses fmt_hms(): 'H:MM:SS' or 'MM:SS' -> seconds. None for
    anything else (HEADER_UNKNOWN, '--:--', missing, malformed). Named
    distinctly from the pre-existing parse_hms_to_seconds (clip-range
    field parser, different accepted formats/purpose) to avoid shadowing
    it — same module, so an identical name would have silently replaced
    that function everywhere."""
    if not text:
        return None
    text = text.strip()
    m = re.match(r"^(\d+):(\d{2}):(\d{2})$", text)
    if m:
        h, mi, se = (int(x) for x in m.groups())
        return h * 3600 + mi * 60 + se
    m = re.match(r"^(\d{1,2}):(\d{2})$", text)
    if m:
        mi, se = (int(x) for x in m.groups())
        return mi * 60 + se
    return None


def extract_header_duration_seconds(raw_text):
    """Scans the first 10 lines of a *raw* (not yet header-stripped) MD
    file for a Duração/Duration field and returns its value in seconds, or
    None if absent/unparseable. Deliberately independent of
    split_md_metadata_header()/HEADER_LABELS (Portuguese-label-only) so it
    still works on files written with the English header-label toggle."""
    for line in (raw_text or "").split("\n")[:10]:
        m = _DURACAO_LINE_RE.match(line.strip())
        if m:
            return parse_fmt_hms_seconds(m.group(1).strip())
    return None


def should_skip_by_duration_mismatch(dur_a, dur_b,
                                     tolerance=COMPARISON_DURATION_PREFILTER_TOLERANCE):
    """Pre-filter for Phase 2a/Scenario 3 (v0.12.1): only actively skips a
    pair when BOTH durations are known and clearly mismatched (default
    tolerance is much wider than the 15% used for tiering, since a wrong
    skip here silently drops a real candidate with no way to notice —
    unlike the tiering guard, which only softens a tier, never removes a
    result). Missing duration on either side is 'no signal' -> never
    skips."""
    if not dur_a or not dur_b:
        return False
    return not durations_within_tolerance(dur_a, dur_b, tolerance)


# ---- v0.12.1: Base Comparison Folder candidate index ---------------------

class ComparisonCandidate:
    """One .md file from the Base Comparison Folder, loaded and normalized
    once per Check click and cached across repeat clicks in the same
    session (see ComparisonWorker._load_base_candidates_cached). Shared by
    Phase 2a (queue file vs. base folder) and Scenario 3 (base folder vs.
    itself, when the queue is empty) — one load serves both."""

    __slots__ = ("rel_path", "norm_body", "norm_paragraphs", "duration_seconds")

    def __init__(self, rel_path, norm_body, norm_paragraphs, duration_seconds):
        self.rel_path = rel_path
        self.norm_body = norm_body
        self.norm_paragraphs = norm_paragraphs
        self.duration_seconds = duration_seconds


def build_candidate_word_index(candidates):
    """word -> set of indices into `candidates` whose norm_body contains
    that word. Built once per Base Folder load; turns the per-excerpt
    prefilter scan (and Scenario 3's per-pair scan) from O(all candidates)
    into O(candidates that could plausibly match) — the real fix for
    'Matching excerpts' stalling on a large folder."""
    index = {}
    for i, cand in enumerate(candidates):
        for w in set(cand.norm_body.split()):
            index.setdefault(w, set()).add(i)
    return index


def compute_base_folder_signature(base_folder):
    """Cheap (stat-only, no file reads) signature of a Base Comparison
    Folder's *.md files, used to decide whether a cached candidate index
    is still safe to reuse across repeat Check clicks, or needs rebuilding
    because something changed."""
    count = 0
    max_mtime = 0.0
    try:
        for root, _dirs, files in os.walk(base_folder):
            for fn in files:
                if fn.lower().endswith(".md"):
                    count += 1
                    try:
                        mtime = os.path.getmtime(os.path.join(root, fn))
                        if mtime > max_mtime:
                            max_mtime = mtime
                    except OSError:
                        pass
    except OSError:
        pass
    return (count, max_mtime)


# ---- v0.12.1: Scenario 3 (Base Folder vs. itself, no whisper) ------------

def md_pair_passes_cheap_prefilter(norm_body_a, norm_body_b, dur_a, dur_b,
                                   shared_word_min_ratio=COMPARISON_PREFILTER_MIN_SHARED_RATIO,
                                   duration_tolerance=COMPARISON_DURATION_PREFILTER_TOLERANCE):
    """Fast gate before Scenario 3's slow paragraph-cross-match pass. A
    confident duration mismatch is a hard skip; otherwise falls through to
    a cheap word-overlap check (same idea as Phase 2a's prefilter, applied
    whole-document instead of excerpt-vs-document)."""
    if should_skip_by_duration_mismatch(dur_a, dur_b, duration_tolerance):
        return False
    words_a, words_b = set(norm_body_a.split()), set(norm_body_b.split())
    if not words_a or not words_b:
        return False
    shorter = min(len(words_a), len(words_b))
    return (len(words_a & words_b) / shorter) >= shared_word_min_ratio if shorter else False


def paragraph_cross_match_coverage(paragraphs_a, paragraphs_b, match_threshold=0.6):
    """Scenario 3's thorough pass: what fraction of A's paragraphs have a
    strong match somewhere in B, and vice versa? Catches one file's content
    being fully contained inside a longer compilation file, which a single
    whole-document ratio can under-rate. Returns (coverage_a_in_b,
    coverage_b_in_a), each in [0, 1]."""
    if not paragraphs_a or not paragraphs_b:
        return 0.0, 0.0

    def coverage(source, target):
        matched = 0
        for p in source:
            best = 0.0
            for q in target:
                score = text_similarity_ratio(p, q)
                if score > best:
                    best = score
                if best >= match_threshold:
                    break
            if best >= match_threshold:
                matched += 1
        return matched / len(source)

    return coverage(paragraphs_a, paragraphs_b), coverage(paragraphs_b, paragraphs_a)


def tier_for_md_pair(whole_doc_score, coverage_a_in_b, coverage_b_in_a,
                     likely_threshold, possible_threshold):
    """Scenario 3 tiering: either a high whole-document score, or strong
    one-way paragraph coverage (a compilation file fully containing a
    shorter file's content, which can dilute the whole-document score
    alone), is enough to reach 'likely'."""
    combined = max(whole_doc_score, coverage_a_in_b, coverage_b_in_a)
    return tier_for_score(combined, likely_threshold, possible_threshold)


# ---- v0.12.1: crash-safe partial report ----------------------------------

COMPARISON_SAFETY_STATUS_IN_PROGRESS = "in_progress"
COMPARISON_SAFETY_STATUS_CANCELED = "canceled"
COMPARISON_SAFETY_STATUS_ERROR = "error"
COMPARISON_SAFETY_STATUS_COMPLETE = "complete"
_COMPARISON_SAFETY_UNFINISHED = (COMPARISON_SAFETY_STATUS_IN_PROGRESS,
                                 COMPARISON_SAFETY_STATUS_CANCELED,
                                 COMPARISON_SAFETY_STATUS_ERROR)
COMPARISON_SAFETY_WRITE_MIN_INTERVAL = 20   # seconds, throttle for mid-file checkpoints


def atomic_write_text(path, text):
    """Write-then-rename so a crash mid-write can never leave a truncated/
    corrupted file at `path` — the rename is atomic on both Windows and
    POSIX for a same-directory source/destination."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


def comparison_safety_status_marker(status):
    return f"<!-- comparison-safety-status: {status} -->"


_SAFETY_STATUS_LINE_RE = re.compile(r"<!--\s*comparison-safety-status:\s*(\w+)\s*-->")


def read_comparison_safety_status(path):
    """Status marker from an existing safety-net report file, or None if
    the file doesn't exist or carries no recognizable marker."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            first_line = f.readline()
    except OSError:
        return None
    m = _SAFETY_STATUS_LINE_RE.match(first_line.strip())
    return m.group(1) if m else None


def build_comparison_report_text(strings, status_line, base_matches, pair_results,
                                 clusters, id_to_name):
    """Shared by the GUI's Export button and ComparisonWorker's crash-
    safety-net writer, so both always produce the identical report shape.
    id_to_name maps whatever id scheme pair_results/clusters use (queue
    item_id for Scenario 1/2, the .md's own relative path for Scenario 3)
    to a display name — built once by the worker, so no caller needs its
    own queue/candidate lookup. status_line is the human-readable progress
    line for a partial (safety-net) report, or None for a finished one."""
    s = strings
    tier_labels = {COMPARISON_TIER_LIKELY: s["cmp_tier_likely"],
                  COMPARISON_TIER_POSSIBLE: s["cmp_tier_possible"],
                  COMPARISON_TIER_NONE: s["cmp_tier_none"]}
    lines = [f"# {s['cmp_results_frame']}", ""]
    if status_line:
        lines += [status_line, ""]
    lines += [f"## {s['cmp_base_matches_frame']}", ""]
    any_matches = False
    for key, matches in base_matches.items():
        if not matches:
            continue
        any_matches = True
        lines.append(f"### {id_to_name.get(key, key)}")
        for rel_path, score, agreeing, tier, _excerpt, _window in matches:
            lines.append(f"- {rel_path} \u2014 {score * 100:.0f}% ({agreeing} "
                         f"{s['col_cmp_points']}) \u2014 {tier_labels.get(tier, tier)}")
        lines.append("")
    if not any_matches:
        lines.append(s["cmp_no_matches_found"])
        lines.append("")
    lines.append(f"## {s['cmp_duplicates_frame']}")
    lines.append("")
    if not clusters:
        lines.append(s["cmp_no_duplicates_found"])
    else:
        pair_lookup = {frozenset((a, b)): score for a, b, score, _ag, _t in pair_results}
        for idx, cluster in enumerate(clusters):
            lines.append(f"### {s['cmp_cluster_label'].format(n=idx + 1)}")
            for member in cluster:
                lines.append(f"- {id_to_name.get(member, member)}")
            for i in range(len(cluster)):
                for j in range(i + 1, len(cluster)):
                    score = pair_lookup.get(frozenset((cluster[i], cluster[j])))
                    if score is None:
                        continue
                    a_name = id_to_name.get(cluster[i], cluster[i])
                    b_name = id_to_name.get(cluster[j], cluster[j])
                    lines.append(f"  - {a_name} \u2194 {b_name}: {score * 100:.0f}%")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def cluster_duplicate_pairs(item_ids, likely_pairs):
    """Phase 2b step 5: item_ids present in the queue; likely_pairs is an
    iterable of (id_a, id_b) that reached the 'likely' tier. Connected
    components via union-find; a cluster can have more than 2 members.
    Returns a list of sorted id-lists, singletons excluded."""
    uf = _ComparisonUnionFind(item_ids)
    for a, b in likely_pairs:
        uf.union(a, b)
    groups = {}
    for i in item_ids:
        groups.setdefault(uf.find(i), []).append(i)
    return [sorted(g) for g in groups.values() if len(g) >= 2]


def transcribe_comparison_clip(whisper_exe, clip_path, out_dir, model_cli, lang_param,
                               initial_prompt, ffmpeg_path, stop_flag=None):
    """Phase 1 step 6. Reuses build_whisper_command (reuse map) rather than
    the full whisper_transcribe_file — excerpts never become delivered
    files, so the MD-conversion/header/replacements pipeline that function
    also runs doesn't apply here. Only the .txt output is read back; the
    other formats whisper writes alongside it are left for the per-item
    temp-dir wipe (Phase 1 step 8) rather than deleted individually.
    Returns the transcribed text, or '' on cancellation/failure."""
    os.makedirs(out_dir, exist_ok=True)
    base = os.path.splitext(os.path.basename(clip_path))[0]
    cmd = build_whisper_command(whisper_exe, clip_path, out_dir, model_cli,
                                "transcribe", lang_param, initial_prompt)
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        encoding="utf-8", errors="replace", bufsize=1,
        env=whisper_child_env(ffmpeg_path), **subprocess_hidden_window_kwargs())
    env_broken = False
    for line in proc.stdout:
        if stop_flag is not None and stop_flag.is_set():
            try:
                proc.terminate()
            except OSError:
                pass
            break
        if is_environment_fatal_output(line):
            env_broken = True
    proc.wait()
    if stop_flag is not None and stop_flag.is_set():
        return ""
    if proc.returncode != 0:
        if env_broken:
            # v0.12.4: distinct from an ordinary failed sample point (which
            # this function silently tolerates, by design — one bad excerpt
            # shouldn't fail the whole file) — the environment itself is
            # broken, so every remaining point/file would fail identically.
            raise EnvironmentBrokenError(
                f"whisper exited with code {proc.returncode} (Python environment broken).")
        return ""
    txt_path = os.path.join(out_dir, base + ".txt")
    if not os.path.exists(txt_path):
        return ""
    try:
        with open(txt_path, "r", encoding="utf-8", errors="replace") as f:
            return f.read().strip()
    except OSError:
        return ""


# ==========================================================================
# Queue item + partial writer + workers
# ==========================================================================

class QueueItem:
    _next_id = 1

    def __init__(self, filepath):
        self.item_id = QueueItem._next_id
        QueueItem._next_id += 1
        self.filepath = filepath
        self.filename = os.path.basename(filepath)
        self.status = ST_PENDING
        self.error_message = ""
        self.output_dir = None
        self.output_txt = None
        self.output_srt = None
        self.output_md = None
        # v0.8.0: length/metadata (media or YouTube)
        self.duration = None        # seconds or None
        self.video_id = None
        self.title = None           # YouTube title (verbatim)
        self.upload_date = None     # YYYYMMDD or None
        self.meta_fetched = False
        self.size_bytes = None      # MD tab
        self.output_stem_override = None   # item 10: forced "_2"/"_3"... stem


# ==========================================================================
# item 7 (v0.11.0) — queue persistence across app restarts
# ==========================================================================

_QUEUE_ITEM_FIELDS = (
    "item_id", "filepath", "filename", "status", "error_message",
    "output_dir", "output_txt", "output_srt", "output_md", "duration",
    "video_id", "title", "upload_date", "meta_fetched", "size_bytes",
    "output_stem_override",
)


def queue_item_to_dict(it):
    """Serializes a QueueItem for persistence. A mid-processing (RUNNING)
    item is written back as PENDING, since a run in progress at close time
    was never actually completed."""
    d = {f: getattr(it, f, None) for f in _QUEUE_ITEM_FIELDS}
    if d["status"] == ST_RUNNING:
        d["status"] = ST_PENDING
    return d


def queue_item_from_dict(d):
    it = QueueItem(d.get("filepath", ""))
    for f in _QUEUE_ITEM_FIELDS:
        if f in d and d[f] is not None:
            setattr(it, f, d[f])
    return it


def save_queues_state(path, tabs):
    """tabs: {tab_key: [QueueItem, ...]}."""
    data = {tab: [queue_item_to_dict(it) for it in items] for tab, items in tabs.items()}
    save_json(path, data)


def load_queues_state(path):
    """Never raises — a missing or corrupt state file just means empty
    queues, exactly like a fresh install."""
    data = load_json(path, {})
    if not isinstance(data, dict):
        return {}
    out = {}
    max_id = 0
    for tab, raw_items in data.items():
        if not isinstance(raw_items, list):
            continue
        items = []
        for raw in raw_items:
            if not isinstance(raw, dict):
                continue
            try:
                it = queue_item_from_dict(raw)
                items.append(it)
                if isinstance(it.item_id, int):
                    max_id = max(max_id, it.item_id)
            except Exception:
                continue
        out[tab] = items
    if max_id >= QueueItem._next_id:
        QueueItem._next_id = max_id + 1
    return out



class LiveQueue:
    """Thread-safe view over a list of QueueItem, shared between the GUI
    thread and a worker thread so the queue can be edited (add/remove/
    reorder pending items) while the worker is running (item 1).

    The worker pulls items one at a time via pop_next_pending(); it never
    iterates the underlying list directly, so GUI-side mutation is always
    safe. Items are identified by their stable `item_id`, never position.
    """

    def __init__(self, items):
        self._lock = threading.Lock()
        self._items = items   # SAME list object as the GUI's queue_items;
                               # all mutation (GUI and worker) must go through
                               # this class's locked methods to stay safe.

    def snapshot(self):
        with self._lock:
            return list(self._items)

    def pop_next_pending(self):
        """Returns the next ST_PENDING item (marking nothing), or None if
        none remain. Caller is responsible for setting status afterwards."""
        with self._lock:
            for it in self._items:
                if it.status == ST_PENDING:
                    return it
        return None

    def remaining_pending_count(self):
        with self._lock:
            return sum(1 for it in self._items if it.status == ST_PENDING)

    def add(self, item):
        with self._lock:
            self._items.append(item)

    def remove(self, item_id):
        """Removes by id only if currently ST_PENDING. Returns True if removed."""
        with self._lock:
            for i, it in enumerate(self._items):
                if it.item_id == item_id:
                    if it.status != ST_PENDING:
                        return False
                    del self._items[i]
                    return True
        return False

    def move(self, item_id, direction):
        """Swaps a pending item with its pending neighbor in `direction`
        (-1/+1). Returns True if moved."""
        with self._lock:
            idx = next((i for i, it in enumerate(self._items)
                       if it.item_id == item_id), None)
            if idx is None or self._items[idx].status != ST_PENDING:
                return False
            new = idx + direction
            if not (0 <= new < len(self._items)):
                return False
            if self._items[new].status != ST_PENDING:
                return False
            self._items[idx], self._items[new] = self._items[new], self._items[idx]
            return True

    def all_items(self):
        with self._lock:
            return list(self._items)


_WHISPER_SEGMENT_LINE_RE = re.compile(
    r"^\[(\d{1,2}):(\d{2})(?::(\d{2}))?\.\d{1,3}\s*-->\s*"
    r"(\d{1,2}):(\d{2})(?::(\d{2}))?\.\d{1,3}\]\s*(.*)$"
)


def parse_whisper_segment_line(line):
    m = _WHISPER_SEGMENT_LINE_RE.match(line.strip())
    if not m:
        return None
    sh, sm, ss, eh, em, es, text = m.groups()

    def _to_seconds(h, mm, ss):
        if ss is not None:
            return int(h) * 3600 + int(mm) * 60 + int(ss)
        return int(h) * 60 + int(mm)

    start = _to_seconds(sh, sm, ss)
    end = _to_seconds(eh, em, es)
    return start, end, text


class PartialTranscriptWriter:
    def __init__(self, path):
        self.path = path
        self._fh = None

    def open(self):
        try:
            self._fh = open(self.path, "w", encoding="utf-8")
        except OSError:
            self._fh = None

    def write_segment(self, text):
        if self._fh is None:
            return
        try:
            self._fh.write(text)
            if not text.endswith("\n"):
                self._fh.write("\n")
            self._fh.flush()
            os.fsync(self._fh.fileno())
        except (OSError, ValueError):
            pass

    def close(self):
        if self._fh is not None:
            try:
                self._fh.close()
            except OSError:
                pass
            self._fh = None

    def discard(self):
        self.close()
        try:
            if os.path.exists(self.path):
                os.remove(self.path)
        except OSError:
            pass


class ModelDownloadWorker(threading.Thread):
    """Force a Whisper model download by running it over 1s of silence."""

    def __init__(self, whisper_exe, model_name, event_queue, stop_flag):
        super().__init__(daemon=True)
        self.whisper_exe = whisper_exe
        self.model_name = model_name
        self.event_queue = event_queue
        self.stop_flag = stop_flag
        self.current_process = None

    def post(self, kind, **kwargs):
        self.event_queue.put({"kind": kind, **kwargs})

    def _make_silent_wav(self, path, duration_seconds=1, sample_rate=16000):
        import wave
        import struct
        n_frames = duration_seconds * sample_rate
        with wave.open(path, "w") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(struct.pack("<h", 0) * n_frames)

    def run(self):
        tmp_dir = None
        try:
            import tempfile
            tmp_dir = tempfile.mkdtemp(prefix="whisper_model_check_")
            wav_path = os.path.join(tmp_dir, "silence.wav")
            self._make_silent_wav(wav_path)
            cmd = [self.whisper_exe, wav_path, "--model", self.model_name,
                   "--language", "English", "--fp16", "False",
                   "--output_dir", tmp_dir, "--output_format", "txt",
                   "--verbose", "True", "--model_dir", whisper_cache_dir()]
            self.post("log", text="Command: " + " ".join(cmd) + "\n\n")
            self.current_process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                encoding="utf-8", errors="replace", bufsize=1,
                env=subprocess_child_env(), **subprocess_hidden_window_kwargs())
            for line in self.current_process.stdout:
                if self.stop_flag.is_set():
                    self.current_process.terminate()
                    break
                self.post("log", text=line)
            self.current_process.wait()
            if self.stop_flag.is_set():
                self.post("dl_finished", success=False, error="Canceled.")
                return
            if self.current_process.returncode != 0:
                self.post("dl_finished", success=False,
                          error=f"whisper exited with code {self.current_process.returncode}.")
                return
            downloaded, _ = is_model_downloaded(self.model_name)
            if downloaded:
                self.post("dl_model_ok")
                self.post("dl_finished", success=True)
            else:
                self.post("dl_finished", success=False,
                          error="Command finished but the model was not found in cache.")
        except Exception as e:
            self.post("dl_finished", success=False, error=str(e))
        finally:
            if tmp_dir and os.path.exists(tmp_dir):
                try:
                    shutil.rmtree(tmp_dir)
                except OSError:
                    pass

    def cancel(self):
        self.stop_flag.set()
        if self.current_process and self.current_process.poll() is None:
            try:
                self.current_process.terminate()
            except OSError:
                pass


class CommandStreamWorker(threading.Thread):
    """Generic: run a command, stream stdout to a queue, post a finish event."""

    def __init__(self, cmd, event_queue, stop_flag, tag="cmd", env=None):
        super().__init__(daemon=True)
        self.cmd = cmd
        self.event_queue = event_queue
        self.stop_flag = stop_flag
        self.tag = tag
        self.env = env
        self.current_process = None

    def post(self, kind, **kwargs):
        self.event_queue.put({"kind": kind, "tag": self.tag, **kwargs})

    def run(self):
        try:
            self.current_process = subprocess.Popen(
                self.cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace", bufsize=1,
                env=self.env or subprocess_child_env(),
                **subprocess_hidden_window_kwargs())
            for line in self.current_process.stdout:
                if self.stop_flag.is_set():
                    self.current_process.terminate()
                    break
                self.post("cmd_log", text=line)
            self.current_process.wait()
            self.post("cmd_finished", returncode=self.current_process.returncode)
        except Exception as e:
            self.post("cmd_log", text=f"\n[ERROR] {e}\n")
            self.post("cmd_finished", returncode=-1)

    def cancel(self):
        self.stop_flag.set()
        if self.current_process and self.current_process.poll() is None:
            try:
                self.current_process.terminate()
            except OSError:
                pass


class WhisperInstallWorker(threading.Thread):
    def __init__(self, event_queue, stop_flag, strings, env_dir):
        super().__init__(daemon=True)
        self.event_queue = event_queue
        self.stop_flag = stop_flag
        self.s = strings
        self.env_dir = env_dir
        self.current_process = None

    def post(self, kind, **kwargs):
        self.event_queue.put({"kind": kind, "tag": "whisper", **kwargs})

    def log(self, key, **kw):
        self.post("cmd_log", text=self.s.get(key, key).format(**kw) + "\n")

    def _run(self, cmd, env=None):
        self.post("cmd_log", text="> " + " ".join(cmd) + "\n")
        self.current_process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            encoding="utf-8", errors="replace", bufsize=1,
            env=env or subprocess_child_env(), **subprocess_hidden_window_kwargs())
        for line in self.current_process.stdout:
            if self.stop_flag.is_set():
                self.current_process.terminate()
                break
            self.post("cmd_log", text=line)
        self.current_process.wait()
        return self.current_process.returncode

    def _provision_python(self):
        if not winget_available():
            return None
        self.log("install_provision_py")
        self._run(["winget", "install", "-e", "--id", "Python.Python.3.12",
                   "--silent", "--accept-package-agreements",
                   "--accept-source-agreements", "--scope", "user"])
        return find_compatible_python()

    def run(self):
        try:
            py = find_compatible_python()
            if not py:
                self.log("install_no_compat_py")
                py = self._provision_python()
            if not py:
                self.log("install_provision_failed")
                self.post("cmd_finished", returncode=-1)
                return
            self.log("install_using_py", py=py)
            env_dir = self.env_dir
            os.makedirs(os.path.dirname(env_dir), exist_ok=True)
            if not os.path.exists(venv_python(env_dir)):
                self.log("install_creating_venv")
                if self._run([py, "-m", "venv", env_dir]) != 0:
                    self.log("install_venv_failed")
                    self.post("cmd_finished", returncode=-1)
                    return
            vpy = venv_python(env_dir)
            self.log("install_pip_upgrade")
            self._run([vpy, "-m", "pip", "install", "--upgrade", "pip"])
            self.log("install_pip_whisper")
            self._run([vpy, "-m", "pip", "install", "--upgrade", "openai-whisper"])
            self.log("install_verifying")
            ok = venv_can_import_whisper(env_dir) and os.path.exists(venv_whisper(env_dir))
            self.post("cmd_finished", returncode=0 if ok else -1)
        except Exception as e:
            self.post("cmd_log", text=f"\n[ERROR] {e}\n")
            self.post("cmd_finished", returncode=-1)

    def cancel(self):
        self.stop_flag.set()
        if self.current_process and self.current_process.poll() is None:
            try:
                self.current_process.terminate()
            except OSError:
                pass


class YouTubeWorker(threading.Thread):
    """Download YouTube transcripts and save clean MD (always) + optional SRT/TXT."""

    def __init__(self, items, preferred_code, keep_srt, keep_txt, output_dir,
                 strings, event_queue, stop_flag, ytdlp_prefix=None,
                 delay_range=YT_TRANSCRIBE_DELAY, lang="en",
                 pause_every=0, pause_seconds=0, header_config=None,
                 polish=True, header_lang="pt", keep_timestamps=True,
                 model_id="pysrt_webvtt", markitdown_ok=False, python_exe=None):
        super().__init__(daemon=True)
        self.items = items
        self.preferred_code = preferred_code   # None = auto
        self.keep_srt = keep_srt
        self.keep_txt = keep_txt
        self.output_dir = output_dir
        self.s = strings
        self.event_queue = event_queue
        self.stop_flag = stop_flag
        self.ytdlp_prefix = ytdlp_prefix
        self.delay_range = delay_range
        self.lang = lang
        self.pause_every = pause_every
        self.pause_seconds = pause_seconds
        self.header_config = header_config
        self.polish = polish
        self.header_lang = header_lang
        self.keep_timestamps = keep_timestamps
        self.model_id = model_id
        self.markitdown_ok = markitdown_ok
        self.python_exe = python_exe

    def post(self, kind, **kwargs):
        self.event_queue.put({"kind": kind, **kwargs})

    def _maybe_pause(self, processed, idx, total, log_kind):
        if (self.pause_every > 0 and self.pause_seconds > 0 and processed > 0
                and processed % self.pause_every == 0 and idx < total - 1
                and not self.stop_flag.is_set()):
            mins = max(1, int(round(self.pause_seconds / 60)))
            self.post(log_kind, text=self.s["pause_log_start"].format(
                n=self.pause_every, m=mins))

            def tick(rem):
                if rem > 0 and rem % 60 == 0:
                    self.post(log_kind, text=self.s["pause_log_tick"].format(
                        m=rem // 60))
            cancellable_sleep(self.stop_flag, self.pause_seconds, tick_cb=tick)
            if not self.stop_flag.is_set():
                self.post(log_kind, text=self.s["pause_log_resume"])

    def _fail(self, item, idx, vid, cause, raw=""):
        short, action = youtube_error_message(cause, self.s, raw=raw)
        item.status = ST_ERROR
        item.error_message = short
        self.post("yt_item_status", index=idx, status=ST_ERROR, error=short)
        self.post("yt_log", text=self.s["log_file_error"].format(name=vid, e=short))
        if action:
            self.post("yt_log", text="    " + action + "\n")
        return short, action

    def run(self):
        total = len(self.items)
        os.makedirs(self.output_dir, exist_ok=True)
        self._used_names = set()
        processed = 0
        for idx, item in enumerate(self.items):
            if self.stop_flag.is_set():
                item.status = ST_SKIPPED
                self.post("yt_item_status", index=idx, status=ST_SKIPPED)
                continue
            self.post("yt_item_status", index=idx, status=ST_RUNNING)
            self.post("yt_progress_index", index=idx)
            sep = "=" * 70
            self.post("yt_log", text=self.s["log_file_start"].format(
                sep=sep, i=idx + 1, n=total, name=item.filename))
            vid = getattr(item, "video_id", None) or youtube_video_id(item.filepath)
            self.post("yt_log", text=self.s["yt_log_fetch"].format(vid=vid))

            # item 12: just-in-time members-only probe, right before this
            # item is actually processed. A probe failure/timeout is
            # inconclusive and does not block processing.
            if probe_is_members_only(vid, prefix=self.ytdlp_prefix) is True:
                item.status = ST_MEMBERS_ONLY
                self.post("yt_item_status", index=idx, status=ST_MEMBERS_ONLY)
                self.post("yt_log", text=self.s["yt_log_members_only"].format(name=vid))
                if idx < total - 1 and not self.stop_flag.is_set():
                    sleep_with_jitter(self.stop_flag, *self.delay_range)
                processed += 1
                self._maybe_pause(processed, idx, total, "yt_log")
                continue

            cause = None
            res = None
            for attempt in range(2):   # one back-off retry on block
                try:
                    res = fetch_youtube_transcript(vid, self.preferred_code)
                    cause = None
                    break
                except Exception as e:
                    cause = classify_youtube_error(e)
                    try:
                        raw = str(e)
                    except Exception:
                        raw = e.__class__.__name__
                    if cause in BLOCK_CAUSES and attempt == 0:
                        self.post("yt_log", text=self.s["yt_log_backoff"])
                        sleep_with_jitter(self.stop_flag, BLOCK_BACKOFF_SECONDS,
                                          BLOCK_BACKOFF_SECONDS + 4)
                        if self.stop_flag.is_set():
                            break
                        continue
                    break

            if res is None:
                short, action = self._fail(item, idx, vid, cause or "generic", raw=raw)
                if cause in BLOCK_CAUSES:
                    self._stop_batch_block(idx, total)
                    return
            else:
                try:
                    self._write_outputs(item, vid, res)
                    item.status = ST_DONE
                    self.post("yt_item_status", index=idx, status=ST_DONE)
                    self.post("yt_log", text=self.s["log_file_done"].format(name=vid))
                except Exception as e:
                    item.status = ST_ERROR
                    item.error_message = str(e)
                    self.post("yt_item_status", index=idx, status=ST_ERROR, error=str(e))
                    self.post("yt_log", text=self.s["log_file_error"].format(name=vid, e=e))

            if idx < total - 1 and not self.stop_flag.is_set():
                sleep_with_jitter(self.stop_flag, *self.delay_range)
            processed += 1
            self._maybe_pause(processed, idx, total, "yt_log")
        self.post("yt_batch_finished")

    def _stop_batch_block(self, idx, total):
        for j in range(idx + 1, total):
            self.items[j].status = ST_PENDING
        self.post("yt_log", text=self.s["yt_log_batch_stopped"])
        self.post("yt_batch_blocked", message=self.s["yt_block_dialog"])
        self.post("yt_batch_finished")

    def _srt_text_to_prose(self, srt_text):
        """v0.13.8: per the "override the bypass for these 2 tabs"
        decision, route through the selected model instead of always
        using the built-in engine. This tab is fully in-memory (no .srt
        ever hits disk today), so routing through an external subprocess
        tool needs a temp-file bridge — write the SRT text out, run the
        model, read the result back, clean up. Falls back to the
        built-in engine for pysrt_webvtt (which IS that engine) and for
        Docling/Pandoc, whose format lists don't include .srt at all."""
        if self.model_id == "markitdown" and self.markitdown_ok and self.python_exe:
            tmp_dir = tempfile.mkdtemp(prefix="yt_md_bridge_")
            try:
                src = os.path.join(tmp_dir, "transcript.srt")
                dst = os.path.join(tmp_dir, "transcript.md")
                with open(src, "w", encoding="utf-8") as f:
                    f.write(srt_text)
                cmd = build_markitdown_command(self.python_exe, src, dst)
                try:
                    subprocess.run(cmd, stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL, timeout=120,
                                  **subprocess_hidden_window_kwargs())
                    if os.path.exists(dst):
                        with open(dst, "r", encoding="utf-8", errors="replace") as f:
                            return f.read()
                except Exception:
                    pass
            finally:
                shutil.rmtree(tmp_dir, ignore_errors=True)
        return subtitle_to_prose(srt_text, is_vtt=False, title=None,
                                 keep_timestamps=getattr(self, "keep_timestamps", True))

    def _write_outputs(self, item, vid, res):
        out_dir = self.output_dir
        item.output_dir = out_dir
        srt_text = build_srt_from_snippets(res["snippets"])
        prose = self._srt_text_to_prose(srt_text)
        # v0.10.5 — clean caption noise/entities before the header is added.
        prose = polish_md_text_and_log(
            prose, profile="prose", enabled=self.polish,
            log_cb=lambda t: self.post("yt_log", text=t), strings=self.s)
        # Feature E: metadata header (best-effort)
        meta = None
        if getattr(item, "meta_fetched", False):
            meta = {"video_id": vid, "title": item.title,
                    "duration": item.duration, "upload_date": item.upload_date,
                    "url": f"https://www.youtube.com/watch?v={vid}"}
        else:
            try:
                meta = youtube_metadata(vid, prefix=self.ytdlp_prefix)
            except Exception:
                meta = {"video_id": vid, "url": f"https://www.youtube.com/watch?v={vid}"}
        # duration fallback: last snippet end
        if not (isinstance(meta.get("duration"), (int, float)) and meta.get("duration")):
            snaps = res.get("snippets") or []
            if snaps:
                last = snaps[-1]
                meta["duration"] = float(last.get("start", 0.0)) + float(last.get("duration", 0.0))
        # Name outputs after the (original-language) video title; fall back to
        # the video id, and de-duplicate within this batch.
        if not getattr(self, "_used_names", None):
            self._used_names = set()
        base = unique_basename(
            sanitize_filename(meta.get("title"), fallback=vid), self._used_names)
        cfg = self.header_config
        if cfg and cfg.get("include", True):
            fields = resolve_header_metadata(auto_metadata_for_youtube(meta), cfg)
            header = build_md_header(fields, lang=getattr(self, "header_lang", "pt"))
            md_content = (header + "\n\n" + (prose or "")).rstrip() + "\n"
        else:
            md_content = (prose or "").rstrip() + "\n"
        md_path = unique_path(os.path.join(out_dir, base + ".md"))
        # item 16: keep every sidecar file (srt/txt) on the same
        # collision-resolved stem as the .md, so a suffixed batch stays
        # internally consistent.
        base = os.path.splitext(os.path.basename(md_path))[0]
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        item.output_md = md_path
        saved = [os.path.basename(md_path)]
        if self.keep_srt:
            with open(os.path.join(out_dir, base + ".srt"), "w", encoding="utf-8") as f:
                f.write(srt_text)
            saved.append(base + ".srt")
        if self.keep_txt:
            with open(os.path.join(out_dir, base + ".txt"), "w", encoding="utf-8") as f:
                f.write(prose if prose else "")
            saved.append(base + ".txt")
        gen = self.s["yt_generated_suffix"] if res["is_generated"] else ""
        self.post("yt_log", text=self.s["yt_log_lang_used"].format(
            lang=res["language_code"], gen=gen))
        if self.preferred_code and not res["matched_pref"]:
            self.post("yt_log", text=self.s["yt_log_lang_mismatch"].format(
                want=self.preferred_code, got=res["language_code"],
                avail=", ".join(res["available"])))
        self.post("yt_log", text=self.s["yt_log_wrote"].format(files=", ".join(saved)))


class PlaylistExpandWorker(threading.Thread):
    """Enumerate a playlist (flat extraction) and post its video entries."""

    def __init__(self, prefix, url, strings, event_queue, stop_flag):
        super().__init__(daemon=True)
        self.prefix = prefix
        self.url = url
        self.s = strings
        self.event_queue = event_queue
        self.stop_flag = stop_flag

    def post(self, kind, **kwargs):
        self.event_queue.put({"kind": kind, **kwargs})

    def run(self):
        cmd = build_ytdlp_flat_list_command(self.prefix, self.url)
        try:
            proc = subprocess.run(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                encoding="utf-8", errors="replace", timeout=120,
                **subprocess_hidden_window_kwargs())
        except Exception as e:
            self.post("expand_error", cause=classify_ytdlp_error(str(e)), raw=str(e))
            return
        if proc.returncode != 0 or not (proc.stdout or "").strip():
            raw = (proc.stderr or proc.stdout or "")
            self.post("expand_error", cause=classify_ytdlp_error(raw), raw=raw.strip())
            return
        try:
            entries = parse_flat_playlist_json(proc.stdout)
        except Exception as e:
            self.post("expand_error", cause="generic", raw=str(e))
            return
        self.post("expand_done", entries=entries)


class LinkGrabWorker(threading.Thread):
    """Resolve one or more playlist/channel/@handle URLs into individual video
    links. Channel URLs may return nested tab-playlists, so we recurse once."""

    def __init__(self, urls, prefix, strings, event_queue, stop_flag,
                 sections=None, exclude_members=False, title_lang=None,
                 want_duration=False):
        super().__init__(daemon=True)
        self.urls = urls
        self.prefix = prefix
        self.s = strings
        self.event_queue = event_queue
        self.stop_flag = stop_flag
        self.sections = sections or {k: True for k in CHANNEL_TAB_PATHS}
        self.exclude_members = exclude_members
        self.title_lang = title_lang
        self.want_duration = want_duration
        self._done = 0
        self._total = 0

    def post(self, kind, **kwargs):
        self.event_queue.put({"kind": kind, **kwargs})

    def _list(self, url, flat=True):
        cmd = build_ytdlp_list_command(self.prefix, url, flat=flat,
                                       title_lang=self.title_lang)
        proc = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            encoding="utf-8", errors="replace", timeout=1800,
            **subprocess_hidden_window_kwargs())
        if not (proc.stdout or "").strip():
            raw = (proc.stderr or proc.stdout or "")
            raise RuntimeError(raw.strip() or "yt-dlp returned no data")
        return json.loads(proc.stdout)

    def _emit_progress(self):
        self.post("grab_progress", done=self._done, total=self._total)

    def _collect(self, url, depth, out):
        if self.stop_flag.is_set():
            return
        # Members-only availability and per-video duration both require full
        # (non-flat) extraction; use it only when needed (slower).
        flat = not (self.exclude_members or self.want_duration)
        try:
            data = self._list(url, flat=flat)
        except Exception as e:
            self.post("grab_log", text=self.s["yt_expand_error"].format(e=str(e)[:200]) + "\n")
            return
        entries = data.get("entries") if isinstance(data, dict) else None
        entries = entries or []
        vids = [e for e in entries
                if e and re.fullmatch(r"[A-Za-z0-9_-]{11}", str(e.get("id") or ""))]
        if vids:
            self._total += len(vids)
            self._emit_progress()
        for e in entries:
            if not e or self.stop_flag.is_set():
                continue
            vid = e.get("id")
            if vid and re.fullmatch(r"[A-Za-z0-9_-]{11}", str(vid)):
                self._done += 1
                if self.exclude_members and entry_is_members_only(e):
                    self._emit_progress()
                    continue
                out.append({"id": vid, "title": e.get("title"),
                            "duration": e.get("duration"),
                            "url": f"https://www.youtube.com/watch?v={vid}"})
                self._emit_progress()
            elif depth < 1:
                nurl = e.get("url") or e.get("webpage_url")
                if nurl:
                    self.post("grab_log", text=self.s["grab_channel_sub"].format(
                        name=e.get("title") or nurl) + "\n")
                    self._collect(nurl, depth + 1, out)

    def run(self):
        out = []
        self.post("grab_progress", done=0, total=0)
        for url in self.urls:
            if self.stop_flag.is_set():
                break
            self.post("grab_log", text=self.s["grab_fetching"].format(url=url) + "\n")
            base = youtube_channel_base(url)
            if base:
                targets = build_channel_tab_urls(base, self.sections)
                if not targets:
                    targets = [url]
                for turl in targets:
                    if self.stop_flag.is_set():
                        break
                    self._collect(turl, 1, out)
            else:
                self._collect(url, 0, out)
        seen = set()
        uniq = []
        for e in out:
            if e["id"] in seen:
                continue
            seen.add(e["id"])
            uniq.append(e)
        self.post("grab_done", entries=uniq)


class DownloadWorker(threading.Thread):
    """Download media via yt-dlp (subprocess), with rate-limit protection."""

    def __init__(self, items, prefix, out_dir, *, audio_only, audio_format,
                 resolution, container, ffmpeg_location, strings, event_queue,
                 stop_flag, delay_range=YT_DOWNLOAD_DELAY, progressive=False,
                 pause_every=0, pause_seconds=0, transcribe=False,
                 whisper_exe=None, whisper_model="", whisper_lang_param=None,
                 whisper_task="transcribe", whisper_prompt="",
                 whisper_replacements=None, whisper_formats=None,
                 header_config=None, polish=True, header_lang="pt",
                 keep_timestamps=True):
        super().__init__(daemon=True)
        self.live_queue = items   # LiveQueue instance (item 1: live editing)
        self.prefix = prefix
        self.out_dir = out_dir
        self.audio_only = audio_only
        self.audio_format = audio_format
        self.resolution = resolution
        self.container = container
        self.ffmpeg_location = ffmpeg_location
        self.s = strings
        self.event_queue = event_queue
        self.stop_flag = stop_flag
        self.delay_range = delay_range
        self.progressive = progressive
        self.pause_every = pause_every
        self.pause_seconds = pause_seconds
        self.transcribe = transcribe
        self.whisper_exe = whisper_exe
        self.whisper_model = whisper_model
        self.whisper_lang_param = whisper_lang_param
        self.whisper_task = whisper_task
        self.whisper_prompt = whisper_prompt
        self.whisper_replacements = whisper_replacements or []
        self.whisper_formats = whisper_formats or []
        self.header_config = header_config
        self.polish = polish
        self.header_lang = header_lang
        self.keep_timestamps = keep_timestamps
        self.current_process = None

    def post(self, kind, **kwargs):
        self.event_queue.put({"kind": kind, **kwargs})

    def _maybe_pause(self, processed):
        if (self.pause_every > 0 and self.pause_seconds > 0 and processed > 0
                and processed % self.pause_every == 0
                and self.live_queue.remaining_pending_count() > 0
                and not self.stop_flag.is_set()):
            mins = max(1, int(round(self.pause_seconds / 60)))
            self.post("dl_log", text=self.s["pause_log_start"].format(
                n=self.pause_every, m=mins))

            def tick(rem):
                if rem > 0 and rem % 60 == 0:
                    self.post("dl_log", text=self.s["pause_log_tick"].format(m=rem // 60))
            cancellable_sleep(self.stop_flag, self.pause_seconds, tick_cb=tick)
            if not self.stop_flag.is_set():
                self.post("dl_log", text=self.s["pause_log_resume"])

    def _capture_downloaded_path(self, since):
        """Newest media file in out_dir modified at/after `since`."""
        best = None
        best_m = since - 1
        try:
            for fn in os.listdir(self.out_dir):
                p = os.path.join(self.out_dir, fn)
                if (os.path.isfile(p)
                        and os.path.splitext(fn)[1].lower() in MEDIA_EXTENSIONS):
                    m = os.path.getmtime(p)
                    if m >= best_m:
                        best_m = m
                        best = p
        except OSError:
            pass
        return best

    def _transcribe_after(self, item, since):
        if not (self.transcribe and self.whisper_exe):
            return
        path = self._capture_downloaded_path(since)
        if not path:
            self.post("dl_log", text=self.s["dl_transcribe_no_file"])
            return
        self.post("dl_log", text=self.s["dl_transcribe_start"].format(
            name=os.path.basename(path)))
        self.post("dl_substatus", item_id=item.item_id, text=self.s["status_transcribing"])
        try:
            header_fields = None
            cfg = getattr(self, "header_config", None)
            if cfg and cfg.get("include", True):
                probe = None
                ff = None
                if self.ffmpeg_location:
                    ff = self.ffmpeg_location
                    if os.path.isdir(ff):
                        cand = os.path.join(ff, "ffmpeg.exe")
                        ff = cand if os.path.exists(cand) else os.path.join(ff, "ffmpeg")
                    try:
                        probe = ffmpeg_probe_duration(ff, path)
                    except Exception:
                        probe = None
                auto = auto_metadata_for_file(
                    path, kind="whisper", probe_duration=probe,
                    embedded_tags=read_embedded_tags(ff, path))
                if probe and probe > 0 and probe < 600:
                    auto["tipo"] = "Short"
                header_fields = resolve_header_metadata(auto, cfg)
            whisper_transcribe_file(
                self.whisper_exe, path, self.out_dir,
                model=self.whisper_model, task=self.whisper_task,
                lang_param=self.whisper_lang_param,
                initial_prompt=self.whisper_prompt,
                replacements=self.whisper_replacements,
                keep_formats=self.whisper_formats,
                stop_flag=self.stop_flag,
                log_cb=lambda t: self.post("dl_log", text=t),
                header_fields=header_fields, ffmpeg_path=self.ffmpeg_location,
                polish=getattr(self, "polish", True), strings=self.s,
                header_lang=getattr(self, "header_lang", "pt"),
                keep_timestamps=getattr(self, "keep_timestamps", True))
            if not self.stop_flag.is_set():
                self.post("dl_log", text=self.s["dl_transcribe_done"])
        except EnvironmentBrokenError as e:
            # v0.12.4: stop attempting transcription for the rest of this
            # batch (downloads themselves continue independently) instead
            # of repeating an identical failure on every remaining item.
            self.post("dl_log", text=self.s["dl_transcribe_error"].format(e=e))
            self.post("dl_log", text=self.s["log_env_broken_abort"])
            self.transcribe = False
        except Exception as e:
            self.post("dl_log", text=self.s["dl_transcribe_error"].format(e=e))

    def _resolve_unique_out_tmpl(self, url):
        """item 16: probe yt-dlp's resolved filename before downloading; if
        it already exists on disk, force an auto-suffixed exact path
        instead of letting yt-dlp skip/overwrite it. Falls back to the
        normal %(title)s template on any probe failure (never blocks the
        download over this)."""
        default_tmpl = os.path.join(self.out_dir, "%(title)s.%(ext)s")
        try:
            probe_cmd = list(self.prefix) + [
                "--no-warnings", "--simulate", "--print", "filename",
                "--no-playlist", "-o", default_tmpl, url]
            proc = subprocess.run(
                probe_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                text=True, timeout=25, env=subprocess_child_env(),
                **subprocess_hidden_window_kwargs())
            lines = [l.strip() for l in (proc.stdout or "").splitlines() if l.strip()]
            if not lines:
                return default_tmpl
            resolved = lines[-1]
            if not os.path.isabs(resolved):
                resolved = os.path.join(self.out_dir, resolved)
            if os.path.exists(resolved):
                return unique_path(resolved)
        except Exception:
            pass
        return default_tmpl

    def _run_once(self, item, vid):
        """Run yt-dlp for one item; return (returncode, captured_text)."""
        url = f"https://www.youtube.com/watch?v={vid}"
        out_tmpl = self._resolve_unique_out_tmpl(url)
        cmd = build_ytdlp_download_command(
            self.prefix, url, self.out_dir, audio_only=self.audio_only,
            audio_format=self.audio_format, resolution=self.resolution,
            container=self.container, ffmpeg_location=self.ffmpeg_location,
            single_video=True, progressive=self.progressive,
            out_tmpl_override=out_tmpl)
        captured = []
        extracting = False
        self.current_process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            encoding="utf-8", errors="replace", bufsize=1,
            env=subprocess_child_env(), **subprocess_hidden_window_kwargs())
        for line in self.current_process.stdout:
            if self.stop_flag.is_set():
                try:
                    self.current_process.terminate()
                except OSError:
                    pass
                break
            captured.append(line)
            if ("[ExtractAudio]" in line or "[Merger]" in line
                    or "[VideoConvertor]" in line or "[FixupM3u8]" in line):
                if not extracting:
                    extracting = True
                    self.post("dl_substatus", item_id=item.item_id,
                              text=self.s["status_extracting"])
                self.post("dl_progress", percent=99.0, phase="extracting")
                self.post("dl_log", text=line)
                continue
            pct = parse_ytdlp_progress_line(line)
            if pct is not None:
                # Audio-only (and any post-processing) runs after the download
                # bar hits 100; hold below 100 so the app isn't shown as done.
                reserve = self.audio_only or extracting
                self.post("dl_progress",
                          percent=(99.0 if reserve and pct >= 100 else pct))
            else:
                self.post("dl_log", text=line)
        self.current_process.wait()
        return self.current_process.returncode, "".join(captured[-40:])

    def run(self):
        os.makedirs(self.out_dir, exist_ok=True)
        processed = 0
        while True:
            if self.stop_flag.is_set():
                break
            item = self.live_queue.pop_next_pending()
            if item is None:
                break
            vid = getattr(item, "video_id", None) or youtube_video_id(item.filepath)
            self.post("dl_item_status", item_id=item.item_id, status=ST_RUNNING)
            self.post("dl_progress_item", item_id=item.item_id)
            processed += 1
            total_hint = processed + self.live_queue.remaining_pending_count()
            sep = "=" * 70
            self.post("dl_log", text=self.s["log_file_start"].format(
                sep=sep, i=processed, n=total_hint, name=item.filename))

            # item 12: just-in-time members-only probe, right before this
            # item is actually processed. A probe failure/timeout is
            # inconclusive and does not block processing.
            if probe_is_members_only(vid, prefix=self.prefix) is True:
                item.status = ST_MEMBERS_ONLY
                self.post("dl_item_status", item_id=item.item_id, status=ST_MEMBERS_ONLY)
                self.post("dl_log", text=self.s["yt_log_members_only"].format(name=vid))
                if self.live_queue.remaining_pending_count() > 0 and not self.stop_flag.is_set():
                    sleep_with_jitter(self.stop_flag, *self.delay_range)
                self._maybe_pause(processed)
                continue

            cause = None
            rc = -1
            since = time.time() - 1
            for attempt in range(2):
                try:
                    rc, tail = self._run_once(item, vid)
                except Exception as e:
                    rc, tail = -1, str(e)
                if rc == 0:
                    cause = None
                    break
                cause = classify_ytdlp_error(tail)
                if cause in BLOCK_CAUSES and attempt == 0 and not self.stop_flag.is_set():
                    self.post("dl_log", text=self.s["yt_log_backoff"])
                    sleep_with_jitter(self.stop_flag, BLOCK_BACKOFF_SECONDS,
                                      BLOCK_BACKOFF_SECONDS + 6)
                    if self.stop_flag.is_set():
                        break
                    continue
                break

            if self.stop_flag.is_set() and rc != 0:
                item.status = ST_SKIPPED
                self.post("dl_item_status", item_id=item.item_id, status=ST_SKIPPED)
                break
            if rc == 0:
                item.output_dir = self.out_dir
                self.post("dl_progress", percent=100.0)
                self._transcribe_after(item, since)
                item.status = ST_DONE
                self.post("dl_item_status", item_id=item.item_id, status=ST_DONE)
                self.post("dl_log", text=self.s["log_file_done"].format(name=vid))
            else:
                short, action = youtube_error_message(cause or "generic", self.s, raw=tail)
                item.status = ST_ERROR
                item.error_message = short
                self.post("dl_item_status", item_id=item.item_id, status=ST_ERROR, error=short)
                self.post("dl_log", text=self.s["log_file_error"].format(name=vid, e=short))
                if action:
                    self.post("dl_log", text="    " + action + "\n")
                if cause in BLOCK_CAUSES:
                    # Remaining items are still ST_PENDING (never popped), so
                    # they're left untouched for a future run, same as before.
                    self.post("dl_log", text=self.s["yt_log_batch_stopped"])
                    self.post("dl_batch_blocked", message=self.s["yt_block_dialog"])
                    self.post("dl_batch_finished")
                    return
            if self.live_queue.remaining_pending_count() > 0 and not self.stop_flag.is_set():
                sleep_with_jitter(self.stop_flag, *self.delay_range)
            self._maybe_pause(processed)
        # Any items still ST_PENDING here means stop was requested mid-batch.
        if self.stop_flag.is_set():
            for it in self.live_queue.all_items():
                if it.status == ST_PENDING:
                    it.status = ST_SKIPPED
                    self.post("dl_item_status", item_id=it.item_id, status=ST_SKIPPED)
        self.post("dl_batch_finished")

    def cancel(self):
        self.stop_flag.set()
        if self.current_process and self.current_process.poll() is None:
            try:
                self.current_process.terminate()
            except OSError:
                pass


class TranscriptionWorker(threading.Thread):
    def __init__(self, live_queue, whisper_exe, ffmpeg_path, lang_param, task,
                 model_name, initial_prompt, replacements, keep_formats,
                 output_dir_mode, fixed_output_dir, clip_range, strings,
                 event_queue, stop_flag, header_config=None, polish=True,
                 header_lang="pt", keep_timestamps=True, model_id="pysrt_webvtt",
                 markitdown_ok=False, python_exe=None):
        super().__init__(daemon=True)
        self.live_queue = live_queue
        self.whisper_exe = whisper_exe
        self.ffmpeg_path = ffmpeg_path
        self.lang_param = lang_param
        self.task = task
        self.model_name = model_name
        self.initial_prompt = initial_prompt
        self.replacements = replacements
        self.keep_formats = keep_formats
        self.output_dir_mode = output_dir_mode
        self.fixed_output_dir = fixed_output_dir
        self.clip_range = clip_range
        self.s = strings
        self.event_queue = event_queue
        self.stop_flag = stop_flag
        self.header_config = header_config
        self.polish = polish
        self.header_lang = header_lang
        self.keep_timestamps = keep_timestamps
        self.model_id = model_id
        self.markitdown_ok = markitdown_ok
        self.python_exe = python_exe
        self._cur_full_duration = None
        self.current_process = None

    def post(self, kind, **kwargs):
        self.event_queue.put({"kind": kind, **kwargs})

    def run(self):
        processed = 0
        while True:
            if self.stop_flag.is_set():
                break
            item = self.live_queue.pop_next_pending()
            if item is None:
                break
            processed += 1
            total_hint = processed + self.live_queue.remaining_pending_count()
            self.post("item_status", item_id=item.item_id, status=ST_RUNNING)
            sep = "=" * 70
            self.post("log", text=self.s["log_file_start"].format(
                sep=sep, i=processed, n=total_hint, name=item.filename))
            self.post("log", text=self.s["log_probing"])
            full_duration = ffmpeg_probe_duration(self.ffmpeg_path, item.filepath)
            self._cur_full_duration = full_duration
            if full_duration:
                self.post("log", text=self.s["log_duration_ok"].format(dur=fmt_hms(full_duration)))
            else:
                self.post("log", text=self.s["log_duration_fail"])
            offset_seconds = 0.0
            effective_duration = full_duration
            if self.clip_range:
                start_s, end_s = self.clip_range
                if full_duration:
                    end_s = min(end_s, full_duration)
                offset_seconds = start_s
                effective_duration = max(0.0, end_s - start_s)
            self.post("duration", item_id=item.item_id, seconds=effective_duration)
            try:
                self._transcribe_one(item, item.item_id, offset_seconds)
                if self.stop_flag.is_set():
                    item.status = ST_SKIPPED
                    self.post("item_status", item_id=item.item_id, status=ST_SKIPPED)
                else:
                    item.status = ST_DONE
                    self.post("item_status", item_id=item.item_id, status=ST_DONE)
                    self.post("log", text=self.s["log_file_done"].format(name=item.filename))
            except EnvironmentBrokenError as e:
                # v0.12.4: the Python environment itself is broken, not
                # just this file — repeating the identical failure on
                # every remaining item wastes real time for no benefit.
                # Stop now instead.
                item.status = ST_ERROR
                item.error_message = str(e)
                self.post("item_status", item_id=item.item_id, status=ST_ERROR, error=str(e))
                self.post("log", text=self.s["log_file_error"].format(name=item.filename, e=e))
                self.post("log", text=self.s["log_env_broken_abort"])
                for it in self.live_queue.all_items():
                    if it.status == ST_PENDING:
                        it.status = ST_SKIPPED
                        self.post("item_status", item_id=it.item_id, status=ST_SKIPPED)
                self.post("batch_finished", env_broken=True)
                return
            except Exception as e:
                item.status = ST_ERROR
                item.error_message = str(e)
                self.post("item_status", item_id=item.item_id, status=ST_ERROR, error=str(e))
                self.post("log", text=self.s["log_file_error"].format(name=item.filename, e=e))
        # Any items still ST_PENDING here means stop was requested mid-batch.
        if self.stop_flag.is_set():
            for it in self.live_queue.all_items():
                if it.status == ST_PENDING:
                    it.status = ST_SKIPPED
                    self.post("item_status", item_id=it.item_id, status=ST_SKIPPED)
        self.post("batch_finished")

    def _resolve_output_dir(self, item):
        if self.output_dir_mode == "fixed" and self.fixed_output_dir:
            return self.fixed_output_dir
        return os.path.dirname(item.filepath)

    def _prepare_clip_if_needed(self, item, idx, tmp_dir):
        if not self.clip_range:
            return item.filepath
        if not (self.ffmpeg_path and os.path.exists(self.ffmpeg_path)):
            raise RuntimeError("Time-range clipping requested, but ffmpeg was not found.")
        start_s, end_s = self.clip_range
        ext = os.path.splitext(item.filepath)[1] or ".mkv"
        clip_path = os.path.join(tmp_dir, f"clip_{idx}{ext}")
        cmd = build_ffmpeg_clip_command(self.ffmpeg_path, item.filepath, clip_path, start_s, end_s)
        self.post("log", text=self.s["log_cmd"].format(cmd=" ".join(cmd)))
        proc = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            encoding="utf-8", errors="replace", env=subprocess_child_env(),
            **subprocess_hidden_window_kwargs())
        if proc.returncode != 0 or not os.path.exists(clip_path):
            raise RuntimeError(f"ffmpeg clip failed (code {proc.returncode}).\n{proc.stdout}")
        return clip_path

    def _transcribe_one(self, item, idx, offset_seconds):
        out_dir = self._resolve_output_dir(item)
        os.makedirs(out_dir, exist_ok=True)
        item.output_dir = out_dir
        base = item.output_stem_override or os.path.splitext(os.path.basename(item.filepath))[0]
        partial = PartialTranscriptWriter(os.path.join(out_dir, base + ".partial.txt"))
        partial.open()
        import tempfile
        tmp_dir = tempfile.mkdtemp(prefix="whisper_clip_")
        try:
            input_path = self._prepare_clip_if_needed(item, idx, tmp_dir)
            cmd = [self.whisper_exe, input_path, "--model", self.model_name,
                   "--task", self.task, "--fp16", "False",
                   "--output_dir", out_dir, "--output_format", "all",
                   "--verbose", "True", "--model_dir", whisper_cache_dir()]
            if self.lang_param:
                cmd.extend(["--language", self.lang_param])
            if self.initial_prompt:
                cmd.extend(["--initial_prompt", self.initial_prompt])
            # v0.13.8: this was the one whisper invocation in the whole
            # app missing --model_dir (the other two — model pre-download
            # and model-check — already had it), so live transcription
            # silently ignored the app's own portable model cache and
            # fell back to whisper's OS-default one instead. Best case
            # that's an unnecessary re-download; worst case, on a model
            # that was never downloaded anywhere, it's a real download
            # whose progress bar (tqdm, carriage-return based) produces
            # zero newline-terminated log lines for the whole transfer —
            # indistinguishable from a genuine hang. This log line at
            # least tells you which one you're looking at.
            already_have_it, _ = is_model_downloaded(self.model_name)
            if not already_have_it:
                self.post("log", text=self.s["log_model_not_cached"].format(
                    model=self.model_name))
            self.post("log", text=self.s["log_cmd"].format(cmd=" ".join(cmd)))
            self.post("phase", item_id=item.item_id, phase="preparing")
            self.current_process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                encoding="utf-8", errors="replace", bufsize=1,
                env=whisper_child_env(self.ffmpeg_path), **subprocess_hidden_window_kwargs())
            saw_first_segment = False
            env_broken = False
            for line in self.current_process.stdout:
                if self.stop_flag.is_set():
                    self.current_process.terminate()
                    break
                self.post("log", text=line)
                if is_environment_fatal_output(line):
                    env_broken = True
                seg = parse_whisper_segment_line(line)
                if seg is not None:
                    if not saw_first_segment:
                        saw_first_segment = True
                        self.post("phase", item_id=item.item_id, phase="transcribing")
                    seg_start, seg_end, seg_text = seg
                    partial.write_segment(seg_text.strip())
                    self.post("progress_tick", item_id=item.item_id, seconds=seg_start)
            self.current_process.wait()
            if not self.stop_flag.is_set() and self.current_process.returncode != 0:
                if env_broken:
                    raise EnvironmentBrokenError(
                        f"whisper exited with code {self.current_process.returncode} "
                        f"(Python environment broken).")
                raise RuntimeError(
                    f"whisper exited with code {self.current_process.returncode}.")
            if self.stop_flag.is_set():
                return

            def fpath(ext):
                return os.path.join(out_dir, base + "." + ext)

            # Whisper names its own outputs after input_path's stem (which is
            # the clip temp file when clipping, or the original media file
            # otherwise). Rename to `base` whenever it differs — this covers
            # both the clip-temp-file case and the item 10 duplicate-avoidance
            # override case (whisper has no knowledge of our renamed stem).
            actual_whisper_base = os.path.splitext(os.path.basename(input_path))[0]
            if actual_whisper_base != base:
                for ext in WHISPER_FORMATS:
                    src = os.path.join(out_dir, actual_whisper_base + "." + ext)
                    if os.path.exists(src):
                        dst = fpath(ext)
                        try:
                            if os.path.exists(dst):
                                os.remove(dst)
                            os.replace(src, dst)
                        except OSError:
                            pass

            # Shift timestamps back to the original timeline (clip case).
            if self.clip_range and offset_seconds:
                for ext in WHISPER_FORMATS:
                    shift_output_timestamps(fpath(ext), ext, offset_seconds)

            # Apply dictionary replacements to whisper text formats first, so
            # the MD (derived from SRT) inherits the corrections.
            if self.replacements:
                for ext in ("txt", "srt", "vtt", "tsv"):
                    self._apply_replacements(fpath(ext))

            # Build clean MD from the subtitle (prefer SRT, then VTT, then TXT).
            # v0.13.8: per the explicit "override the bypass for these 2
            # tabs" decision, route through the selected model instead of
            # always using the built-in engine — except pysrt_webvtt
            # (which IS the built-in engine, now pysrt/webvtt-py under
            # the hood per v0.13.7) and Docling/Pandoc, whose format
            # lists don't include .srt/.vtt at all, so there's no real
            # "route through them" to do — falls back to the built-in
            # engine rather than failing the whole file.
            if "md" in self.keep_formats:
                self.post("log", text=self.s["log_md_make"])
                made = False
                model_id = getattr(self, "model_id", "pysrt_webvtt")
                for ext in ("srt", "vtt"):
                    p = fpath(ext)
                    if os.path.exists(p):
                        routed = False
                        if model_id == "markitdown" and getattr(self, "markitdown_ok", False) \
                                and getattr(self, "python_exe", None):
                            cmd = build_markitdown_command(self.python_exe, p, fpath("md"))
                            try:
                                subprocess.run(cmd, stdout=subprocess.DEVNULL,
                                              stderr=subprocess.DEVNULL, timeout=120,
                                              **subprocess_hidden_window_kwargs())
                                routed = os.path.exists(fpath("md"))
                            except Exception:
                                routed = False
                        if not routed:
                            convert_subtitle_file_to_md(
                                p, fpath("md"), title=None,
                                keep_timestamps=getattr(self, "keep_timestamps", True))
                        made = True
                        break
                if not made and os.path.exists(fpath("txt")):
                    with open(fpath("txt"), "r", encoding="utf-8", errors="replace") as f:
                        txt = f.read()
                    prose = "\n\n".join(s.strip() for s in re.split(r"\n\s*\n", txt) if s.strip())
                    with open(fpath("md"), "w", encoding="utf-8") as f:
                        f.write(prose.strip() + "\n")
                if self.replacements:
                    self._apply_replacements(fpath("md"))
                polish_md_and_log(fpath("md"), profile="prose",
                                  enabled=self.polish,
                                  log_cb=lambda t: self.post("log", text=t),
                                  strings=self.s)
                cfg = self.header_config
                if cfg and cfg.get("include", True) and os.path.exists(fpath("md")):
                    auto = auto_metadata_for_file(
                        item.filepath, kind="whisper",
                        probe_duration=self._cur_full_duration,
                        embedded_tags=read_embedded_tags(self.ffmpeg_path, item.filepath))
                    if self._cur_full_duration and 0 < self._cur_full_duration < 600:
                        auto["tipo"] = "Short"
                    fields = resolve_header_metadata(auto, cfg)
                    prepend_header_to_file(fpath("md"), build_md_header(
                        fields, lang=getattr(self, "header_lang", "pt")))

            # Remove whisper formats the user did not keep.
            for ext in WHISPER_FORMATS:
                if ext not in self.keep_formats:
                    p = fpath(ext)
                    if os.path.exists(p):
                        try:
                            os.remove(p)
                        except OSError:
                            pass

            item.output_txt = fpath("txt") if os.path.exists(fpath("txt")) else None
            item.output_srt = fpath("srt") if os.path.exists(fpath("srt")) else None
            item.output_md = fpath("md") if os.path.exists(fpath("md")) else None
            partial.discard()
        finally:
            partial.close()
            try:
                shutil.rmtree(tmp_dir, ignore_errors=True)
            except OSError:
                pass

    def _apply_replacements(self, path):
        if not path or not os.path.exists(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            for find, replace in self.replacements:
                if not find:
                    continue
                content = content.replace(find, replace)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
        except OSError as e:
            self.post("log", text=self.s["log_dict_warn"].format(path=path, e=e))

    def cancel(self):
        self.stop_flag.set()
        if self.current_process and self.current_process.poll() is None:
            try:
                self.current_process.terminate()
            except OSError:
                pass


class ConversionWorker(threading.Thread):
    """MD File Generation tab: convert docs/subtitles to clean Markdown.

    v0.13.8: model_id selects which engine handles non-bypass files
    (markitdown/docling/pandoc) — subtitle/transcript files always use
    the app's own built-in engine regardless (see the explicit "keep
    the bypass" decision), so those never get the [modelid] filename
    suffix; only files that actually went through an external model do."""

    def __init__(self, items, python_exe, markitdown_ok, output_dir_mode,
                 fixed_output_dir, strings, event_queue, stop_flag,
                 header_config=None, ffmpeg_path=None, polish=True,
                 header_lang="pt", keep_timestamps=True, model_id="markitdown",
                 docling_ok=False, pandoc_path=None):
        super().__init__(daemon=True)
        self.items = items
        self.python_exe = python_exe
        self.markitdown_ok = markitdown_ok
        self.output_dir_mode = output_dir_mode
        self.fixed_output_dir = fixed_output_dir
        self.s = strings
        self.event_queue = event_queue
        self.stop_flag = stop_flag
        self.header_config = header_config
        self.ffmpeg_path = ffmpeg_path
        self.polish = polish
        self.header_lang = header_lang
        self.keep_timestamps = keep_timestamps
        self.model_id = model_id
        self.docling_ok = docling_ok
        self.pandoc_path = pandoc_path
        self.current_process = None

    def _maybe_polish(self, path, profile):
        """v0.10.5 — LLM-ready cleanup, run before the header is prepended."""
        return polish_md_and_log(path, profile=profile, enabled=self.polish,
                                 log_cb=lambda t: self.post("md_log", text=t),
                                 strings=self.s)

    def _maybe_prepend_header(self, item, src_text):
        cfg = self.header_config
        if not cfg or not cfg.get("include", True):
            return
        probe = None
        if self.ffmpeg_path:
            try:
                probe = ffmpeg_probe_duration(self.ffmpeg_path, item.filepath)
            except Exception:
                probe = None
        auto = auto_metadata_for_file(item.filepath, kind="md",
                                      source_text=src_text, probe_duration=probe)
        fields = resolve_header_metadata(auto, cfg)
        prepend_header_to_file(item.output_md, build_md_header(
            fields, lang=getattr(self, "header_lang", "pt")))

    def post(self, kind, **kwargs):
        self.event_queue.put({"kind": kind, **kwargs})

    def _resolve_output_dir(self, item):
        if self.output_dir_mode == "fixed" and self.fixed_output_dir:
            return self.fixed_output_dir
        return os.path.dirname(item.filepath)

    def run(self):
        total = len(self.items)
        for idx, item in enumerate(self.items):
            if self.stop_flag.is_set():
                item.status = ST_SKIPPED
                self.post("md_item_status", index=idx, status=ST_SKIPPED)
                continue
            self.post("md_item_status", index=idx, status=ST_RUNNING)
            sep = "=" * 70
            self.post("md_log", text=self.s["log_file_start"].format(
                sep=sep, i=idx + 1, n=total, name=item.filename))
            try:
                self._convert_one(item)
                if self.stop_flag.is_set():
                    item.status = ST_SKIPPED
                    self.post("md_item_status", index=idx, status=ST_SKIPPED)
                else:
                    item.status = ST_DONE
                    self.post("md_item_status", index=idx, status=ST_DONE)
                    self.post("md_log", text=self.s["log_file_done"].format(name=item.filename))
            except Exception as e:
                item.status = ST_ERROR
                item.error_message = str(e)
                self.post("md_item_status", index=idx, status=ST_ERROR, error=str(e))
                self.post("md_log", text=self.s["log_file_error"].format(name=item.filename, e=e))
        self.post("md_batch_finished")

    def _convert_one(self, item):
        out_dir = self._resolve_output_dir(item)
        os.makedirs(out_dir, exist_ok=True)
        item.output_dir = out_dir
        base = os.path.splitext(os.path.basename(item.filepath))[0]
        ext = os.path.splitext(item.filepath)[1].lower()
        src_text = None
        # item 16: never overwrite an existing MD output; silently suffix.
        if ext in SUBTITLE_EXTENSIONS:
            # v0.13.10: DOES get the [pysrt_webvtt] suffix now, even
            # though this bypass runs regardless of which model is
            # globally selected (explicit decision, unchanged) — pysrt/
            # webvtt-py is the real engine that parses .srt/.vtt (since
            # v0.13.7's parser swap), so tagging with its name is
            # accurate, unlike tagging with whatever the ACTIVE model
            # happens to be (which might be Docling or Pandoc, neither
            # of which touched this file at all).
            dst = unique_path(os.path.join(out_dir, f"{base} [pysrt_webvtt].md"))
            self.post("md_log", text=self.s["log_md_make"])
            with open(item.filepath, "r", encoding="utf-8", errors="replace") as f:
                src_text = f.read()
            convert_subtitle_file_to_md(item.filepath, dst, title=None,
                                       keep_timestamps=self.keep_timestamps)
            item.output_md = dst
            self._maybe_polish(dst, "prose")
            self._maybe_prepend_header(item, src_text)
            return
        # Plain text / markdown that looks like a timestamped transcript is
        # cleaned into fluid prose ourselves (an external model would pass
        # it through verbatim, keeping timestamps and mid-sentence breaks).
        if ext in (".txt", ".md"):
            with open(item.filepath, "r", encoding="utf-8", errors="replace") as f:
                src_text = f.read()
            if looks_like_timestamped_transcript(src_text):
                dst = unique_path(os.path.join(out_dir, base + ".md"))
                self.post("md_log", text=self.s["log_md_clean"])
                prose = transcript_text_to_prose(src_text, keep_timestamps=self.keep_timestamps)
                with open(dst, "w", encoding="utf-8") as f:
                    f.write(prose)
                item.output_md = dst
                self._maybe_polish(dst, "prose")
                self._maybe_prepend_header(item, src_text)
                return

        # Everything else genuinely needs the selected model's own engine
        # -- filename gets the [modelid] suffix since a real external
        # conversion tool actually ran, unlike the bypass paths above.
        dst = unique_path(os.path.join(out_dir, f"{base} [{self.model_id}].md"))
        self.post("md_log", text=self.s["log_md_markitdown"].format(name=item.filename))
        self._run_model_conversion(item.filepath, dst)
        item.output_md = dst if os.path.exists(dst) else None
        if item.output_md and src_text is None:
            try:
                with open(item.filepath, "r", encoding="utf-8", errors="replace") as f:
                    src_text = f.read()
            except OSError:
                src_text = ""
        if item.output_md:
            self._maybe_polish(item.output_md,
                               polish_profile_for_model(self.model_id, item.filepath))
            self._maybe_prepend_header(item, src_text or "")

    def _run_model_conversion(self, src_path, dst_path):
        """Builds and runs the selected model's command. Docling is the
        odd one out (writes to a directory, not dst_path directly — see
        finalize_docling_output()), everything else writes straight to
        dst_path like markitdown always has."""
        scratch_dir = None
        docling_in_dir = None
        finalize_src = src_path
        if self.model_id == "markitdown":
            if not self.markitdown_ok:
                raise RuntimeError("MarkItDown is required to convert this file type.")
            cmd = build_markitdown_command(self.python_exe, src_path, dst_path)
        elif self.model_id == "docling":
            if not self.docling_ok:
                raise RuntimeError("Docling is required to convert this file type.")
            docling_exe = venv_docling(DOCLING_ENV_DIR)
            scratch_dir = tempfile.mkdtemp(prefix="docling_out_")
            # v0.13.10: hand Docling a plain-ASCII temp filename, not the
            # real one. A real conversion failed with a PermissionError
            # INSIDE Docling's own temp-file cleanup (docling/cli/
            # main.py's own TemporaryDirectory, not anything this app
            # manages) on a file whose name included accented Portuguese
            # characters — plausibly, though not confirmed, a Docling/
            # Windows Unicode-path issue. This sidesteps it either way:
            # Docling never sees anything but a simple ASCII path.
            docling_in_dir = tempfile.mkdtemp(prefix="docling_in_")
            ext = os.path.splitext(src_path)[1]
            finalize_src = os.path.join(docling_in_dir, "input" + ext)
            shutil.copy2(src_path, finalize_src)
            cmd = build_docling_command(docling_exe, finalize_src, scratch_dir)
        elif self.model_id == "pandoc":
            if not self.pandoc_path:
                raise RuntimeError("Pandoc is required to convert this file type.")
            cmd = build_pandoc_command(self.pandoc_path, src_path, dst_path)
        else:
            raise RuntimeError(f"Unknown conversion model: {self.model_id}")

        self.post("md_log", text="Command: " + " ".join(cmd) + "\n")
        self.current_process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            encoding="utf-8", errors="replace", bufsize=1,
            env=subprocess_child_env(), **subprocess_hidden_window_kwargs())
        for line in self.current_process.stdout:
            if self.stop_flag.is_set():
                self.current_process.terminate()
                break
            self.post("md_log", text=line)
        self.current_process.wait()
        try:
            if not self.stop_flag.is_set() and self.current_process.returncode != 0:
                raise RuntimeError(
                    f"{self.model_id} exited with code {self.current_process.returncode}.")
            if scratch_dir and not self.stop_flag.is_set():
                if not finalize_docling_output(scratch_dir, finalize_src, dst_path):
                    raise RuntimeError("docling did not produce the expected output file.")
        finally:
            if scratch_dir:
                shutil.rmtree(scratch_dir, ignore_errors=True)
            if docling_in_dir:
                shutil.rmtree(docling_in_dir, ignore_errors=True)

    def cancel(self):
        self.stop_flag.set()
        if self.current_process and self.current_process.poll() is None:
            try:
                self.current_process.terminate()
            except OSError:
                pass


class ComparisonWorker(threading.Thread):
    """Comparison tab, Phase 1+2 (v0.12.0) plus Scenario 3 / caching /
    crash-safety (v0.12.1). Three entry scenarios, auto-detected in run():
      1. Queue files + Base Folder: samples each queued file, transcribes
         short excerpts with a light model, matches against the Base
         Folder (Phase 2a) and against each other (Phase 2b).
      2. Queue files only: same as 1, Phase 2a just skipped.
      3. Base Folder only (empty queue): no whisper/ffmpeg at all — every
         .md in the folder is compared against every other one directly.
    Runs entirely off the Tk thread. Posts 'comparison_results' with the
    finished (or partial, on cancel/error) data when done; the GUI thread
    only renders it. Same live_queue/event_queue/stop_flag shape as every
    other worker in this file."""

    def __init__(self, live_queue, whisper_exe, ffmpeg_path, model_cli,
                 lang_param, initial_prompt, base_folder, excerpt_seconds,
                 likely_threshold, possible_threshold, duration_tolerance,
                 strings, event_queue, stop_flag, temp_root,
                 base_index_cache=None, safety_net_path=None):
        super().__init__(daemon=True)
        self.live_queue = live_queue
        self.whisper_exe = whisper_exe
        self.ffmpeg_path = ffmpeg_path
        self.model_cli = model_cli
        self.lang_param = lang_param
        self.initial_prompt = initial_prompt
        self.base_folder = base_folder
        self.excerpt_seconds = excerpt_seconds
        self.likely_threshold = likely_threshold
        self.possible_threshold = possible_threshold
        self.duration_tolerance = duration_tolerance
        self.s = strings
        self.event_queue = event_queue
        self.stop_flag = stop_flag
        self.temp_root = temp_root
        # v0.12.1 — (signature, candidates, word_index) from a previous run
        # in this session, or None. See _load_base_candidates_cached.
        self.base_index_cache = base_index_cache
        self.safety_net_path = safety_net_path
        self.base_matches = {}
        self.pair_results = []
        self.clusters = []
        self.id_to_name = {}

    def post(self, kind, **kwargs):
        self.event_queue.put({"kind": kind, **kwargs})

    def run(self):
        try:
            items = self.live_queue.all_items()
            if not items and self.base_folder and os.path.isdir(self.base_folder):
                self._run_md_vs_md()
            else:
                self._run_media_vs_base(items)
        except Exception as e:
            self.post("log", text=f"[ERROR] {e}\n")
            try:
                self._write_safety_net(COMPARISON_SAFETY_STATUS_ERROR, note=str(e))
            except Exception:
                pass   # never let safety-net bookkeeping mask the real error
            self.post("comparison_results", base_matches=self.base_matches,
                      pair_results=self.pair_results, clusters=self.clusters,
                      id_to_name=dict(self.id_to_name), partial=True)
            self.post("batch_finished", error=str(e))

    # ---- shared: crash-safe partial report -------------------------------

    def _write_safety_net(self, status, note=""):
        if not self.safety_net_path:
            return
        status_label = {
            COMPARISON_SAFETY_STATUS_IN_PROGRESS: self.s["cmp_safety_status_in_progress"],
            COMPARISON_SAFETY_STATUS_CANCELED: self.s["cmp_safety_status_canceled"],
            COMPARISON_SAFETY_STATUS_ERROR: self.s["cmp_safety_status_error"],
            COMPARISON_SAFETY_STATUS_COMPLETE: self.s["cmp_safety_status_complete"],
        }.get(status, status)
        status_line = self.s["cmp_safety_status_line"].format(
            status=status_label, note=note, time=time.strftime("%H:%M:%S"))
        text = build_comparison_report_text(
            self.s, status_line, self.base_matches, self.pair_results,
            self.clusters, self.id_to_name)
        marked = comparison_safety_status_marker(status) + "\n" + text
        try:
            os.makedirs(os.path.dirname(self.safety_net_path), exist_ok=True)
            atomic_write_text(self.safety_net_path, marked)
        except OSError:
            pass

    def _finish(self, canceled, env_broken=False):
        if env_broken:
            status = COMPARISON_SAFETY_STATUS_ERROR
        elif canceled:
            status = COMPARISON_SAFETY_STATUS_CANCELED
        else:
            status = COMPARISON_SAFETY_STATUS_COMPLETE
        self._write_safety_net(status)
        self.post("comparison_results", base_matches=self.base_matches,
                  pair_results=self.pair_results, clusters=self.clusters,
                  id_to_name=dict(self.id_to_name), partial=(canceled or env_broken))
        if not canceled and not env_broken:
            self.post("log", text=self.s["cmp_log_done"])
        try:
            shutil.rmtree(self.temp_root, ignore_errors=True)
        except OSError:
            pass
        self.post("batch_finished", canceled=canceled, env_broken=env_broken)

    # ---- shared: Base Comparison Folder loading, cached -------------------

    def _load_base_candidates_cached(self):
        """Phase 2a steps 1-2 / Scenario 3 setup: recursively walk the Base
        Comparison Folder for *.md, strip the header, normalize the body
        (+ paragraphs, + header duration). Cached across repeat Check
        clicks in the same session (App-level storage, passed in as
        base_index_cache) via a cheap stat-only folder signature — a
        changed folder rebuilds automatically."""
        sig = compute_base_folder_signature(self.base_folder)
        if self.base_index_cache is not None and self.base_index_cache[0] == sig:
            candidates, word_index = self.base_index_cache[1], self.base_index_cache[2]
            self.post("log", text=self.s["cmp_log_base_cached"].format(n=len(candidates)))
            return candidates, word_index

        self.post("log", text=self.s["cmp_log_scanning_base"])
        out = []
        for root, _dirs, files in os.walk(self.base_folder):
            if self.stop_flag.is_set():
                break
            for fn in files:
                if not fn.lower().endswith(".md"):
                    continue
                full = os.path.join(root, fn)
                rel = os.path.relpath(full, self.base_folder)
                try:
                    with open(full, "r", encoding="utf-8", errors="replace") as f:
                        text = f.read()
                except OSError:
                    continue
                _header, body = split_md_metadata_header(text)
                norm_body = normalize_md_body_for_comparison(body)
                if not norm_body:
                    continue
                norm_paragraphs = normalize_md_paragraphs_for_comparison(body)
                duration = extract_header_duration_seconds(text)
                out.append(ComparisonCandidate(rel, norm_body, norm_paragraphs, duration))
        word_index = build_candidate_word_index(out)
        self.post("log", text=self.s["cmp_log_base_loaded"].format(n=len(out)))
        self.post("base_index_built", signature=sig, candidates=out, word_index=word_index)
        return out, word_index

    # ---- Scenarios 1/2: queue files (+ optional Base Folder) --------------

    def _run_media_vs_base(self, items):
        try:
            if os.path.exists(self.temp_root):
                shutil.rmtree(self.temp_root, ignore_errors=True)
            os.makedirs(self.temp_root, exist_ok=True)
        except OSError:
            pass

        self.id_to_name = {it.item_id: it.filename for it in items}
        excerpts_by_item = {}
        durations_by_item = {}

        total = len(items)
        for processed, item in enumerate(items, start=1):
            if self.stop_flag.is_set():
                break
            self.post("item_status", item_id=item.item_id, status=ST_RUNNING)
            self.post("log", text=self.s["cmp_log_sampling"].format(
                i=processed, n=total, name=item.filename))
            duration = ffmpeg_probe_duration(self.ffmpeg_path, item.filepath)
            durations_by_item[item.item_id] = duration
            if not duration:
                excerpts_by_item[item.item_id] = []
                self.post("item_status", item_id=item.item_id, status=ST_ERROR,
                          error=self.s["cmp_err_duration"])
                self.post("log", text=self.s["cmp_err_duration"].format(name=item.filename) + "\n")
                continue
            percents = comparison_sample_point_percents(duration)
            item_dir = os.path.join(self.temp_root, str(item.item_id))
            os.makedirs(item_dir, exist_ok=True)
            excerpts = []
            try:
                for point_idx, pct in enumerate(percents, start=1):
                    if self.stop_flag.is_set():
                        break
                    start, end = comparison_sample_window(duration, pct, self.excerpt_seconds)
                    excerpts.append(self._sample_one_point(item, point_idx, start, end,
                                                            duration, item_dir))
                    self.post("log", text=self.s["cmp_log_point"].format(
                        i=point_idx, n=len(percents), name=item.filename))
            except EnvironmentBrokenError as e:
                # v0.12.4: the Python environment itself is broken, not
                # just this excerpt — stop the whole Check instead of
                # repeating an identical failure on every remaining point.
                self.post("item_status", item_id=item.item_id, status=ST_ERROR, error=str(e))
                self.post("log", text=self.s["cmp_log_env_broken_abort"])
                try:
                    shutil.rmtree(item_dir, ignore_errors=True)
                except OSError:
                    pass
                for it in items:
                    if it.status in (ST_PENDING, ST_RUNNING):
                        self.post("item_status", item_id=it.item_id, status=ST_SKIPPED)
                self._finish(canceled=False, env_broken=True)
                return
            excerpts_by_item[item.item_id] = excerpts
            try:
                shutil.rmtree(item_dir, ignore_errors=True)
            except OSError:
                pass
            if not self.stop_flag.is_set():
                # v0.13.10: this file's OWN sampling is done, but Phase 2
                # (matching against the base folder and every other
                # queued file) is a genuinely batch operation — it can't
                # start until EVERY file finishes sampling, not as each
                # one individually finishes. ST_TRANSCRIBED marks that
                # "done sampling, waiting for the rest of the batch"
                # moment; the whole batch transitions to ST_COMPARING
                # together, right below, once this loop is done.
                self.post("item_status", item_id=item.item_id, status=ST_TRANSCRIBED)

        if self.stop_flag.is_set():
            for it in items:
                if it.status in (ST_PENDING, ST_RUNNING, ST_TRANSCRIBED):
                    self.post("item_status", item_id=it.item_id, status=ST_SKIPPED)
            self._finish(canceled=True)
            return

        # v0.13.10: the whole batch has now finished sampling — this is
        # the real "Phase 2 starts now" moment, so every file that made
        # it this far (not ST_ERROR) transitions to ST_COMPARING together,
        # rather than each showing "Comparing..." at wildly different
        # times depending on how long its own sampling took relative to
        # the others.
        for it in items:
            if it.status == ST_TRANSCRIBED:
                self.post("item_status", item_id=it.item_id, status=ST_COMPARING)

        # Phase 2a — against the Base Comparison Folder. An unconfigured/
        # missing folder doesn't block the Check, it just skips this half —
        # Phase 2b (below) is independently useful with no Base Folder at
        # all (Scenario 2).
        if self.base_folder and os.path.isdir(self.base_folder):
            candidates, word_index = self._load_base_candidates_cached()
            cand_by_path = {c.rel_path: c.norm_body for c in candidates}
            for file_idx, item in enumerate(items, start=1):
                if self.stop_flag.is_set():
                    break
                raw_excerpts = [e for e in excerpts_by_item.get(item.item_id, []) if e]
                norm_excerpts = [_plsh_normalize_for_compare(e) for e in raw_excerpts]
                # keep raw/normalized aligned; drop a point only if it
                # normalizes to nothing (e.g. pure punctuation)
                paired = [(r, n) for r, n in zip(raw_excerpts, norm_excerpts) if n]
                if not paired:
                    continue
                raw_excerpts, norm_excerpts = zip(*paired)
                self.post("log", text=self.s["cmp_log_matching_file"].format(
                    i=file_idx, n=total, name=item.filename, count=len(candidates)))
                item_duration = durations_by_item.get(item.item_id)
                # Score each excerpt against candidates the word index and
                # duration/word prefilters let through; candidates a given
                # excerpt didn't pass simply contribute 0.0 for that point
                # once reconciled below (aggregate_candidate_scores expects
                # one entry per point).
                per_point_scored = [
                    dict(match_excerpt_against_candidates(
                        ex, candidates, word_index=word_index, excerpt_duration=item_duration))
                    for ex in norm_excerpts]
                scored, agreeing_by_path = [], {}
                for path, norm_body in cand_by_path.items():
                    point_scores = [d.get(path, 0.0) for d in per_point_scored]
                    agg, agreeing = aggregate_candidate_scores(point_scores)
                    if agg > 0:
                        scored.append((path, agg))
                        agreeing_by_path[path] = agreeing
                top = top_n_candidates(scored)
                enriched = []
                for path, score in top:
                    # Which point contributed the best score against this
                    # candidate? Re-derive the matched window text just for
                    # that one pair (cheap: only done for the final top 3,
                    # not the whole corpus) so the UI can show it.
                    best_idx = max(range(len(per_point_scored)),
                                   key=lambda k: per_point_scored[k].get(path, 0.0))
                    _ws, window_text = windowed_best_match(norm_excerpts[best_idx],
                                                           cand_by_path[path])
                    enriched.append((path, score, agreeing_by_path[path],
                                     tier_for_score(score, self.likely_threshold,
                                                    self.possible_threshold),
                                     raw_excerpts[best_idx], window_text))
                if enriched:
                    self.base_matches[item.item_id] = enriched
                self._write_safety_net(
                    COMPARISON_SAFETY_STATUS_IN_PROGRESS,
                    note=self.s["cmp_safety_note_matching"].format(i=file_idx, n=total))
        else:
            self.post("log", text=self.s["cmp_log_no_base_folder"])

        if self.stop_flag.is_set():
            # v0.13.9: don't leave items stuck showing "Comparing..."
            # after a cancel mid-Phase-2a — same cleanup the end of
            # Phase 2b does on its own cancel path, below.
            for it in items:
                if it.status == ST_COMPARING:
                    self.post("item_status", item_id=it.item_id, status=ST_SKIPPED)
            self._finish(canceled=True)
            return

        # Phase 2b — duplicate-source detection within the queue itself,
        # reusing the same excerpts (no extra whisper calls).
        item_ids = [it.item_id for it in items]
        total_pairs = len(items) * (len(items) - 1) // 2
        if total_pairs:
            self.post("log", text=self.s["cmp_log_phase2b_start"].format(
                n=len(items), pairs=total_pairs))
        likely_pairs = []
        for i in range(len(items)):
            if self.stop_flag.is_set():
                break
            for j in range(i + 1, len(items)):
                a, b = items[i], items[j]
                ex_a = [_plsh_normalize_for_compare(e)
                       for e in excerpts_by_item.get(a.item_id, []) if e]
                ex_b = [_plsh_normalize_for_compare(e)
                       for e in excerpts_by_item.get(b.item_id, []) if e]
                ex_a, ex_b = [e for e in ex_a if e], [e for e in ex_b if e]
                if not ex_a or not ex_b:
                    continue
                score, agreeing = compare_excerpt_sets(ex_a, ex_b)
                tier = tier_for_pair(score, durations_by_item.get(a.item_id),
                                     durations_by_item.get(b.item_id),
                                     self.likely_threshold, self.possible_threshold,
                                     self.duration_tolerance)
                if tier != COMPARISON_TIER_NONE:
                    self.pair_results.append((a.item_id, b.item_id, score, agreeing, tier))
                if tier == COMPARISON_TIER_LIKELY:
                    likely_pairs.append((a.item_id, b.item_id))
        self.clusters = cluster_duplicate_pairs(item_ids, likely_pairs)
        canceled = self.stop_flag.is_set()
        # v0.13.9: the real "fully compared" moment for the WHOLE batch —
        # Phase 2a/2b are inherently batch operations (Phase 2b compares
        # every pair, not one item at a time), so there's no single
        # earlier point where any one item is individually "done" with
        # comparison. Items still sitting at ST_COMPARING here (not
        # ST_ERROR/ST_SKIPPED) get their real finish now; if canceled
        # mid-Phase-2, they're marked ST_SKIPPED instead of being left to
        # show "Comparing..." forever.
        for it in items:
            if it.status == ST_COMPARING:
                self.post("item_status", item_id=it.item_id,
                          status=ST_SKIPPED if canceled else ST_DONE)
        self._finish(canceled=canceled)

    def _sample_one_point(self, item, point_idx, start, end, duration, item_dir):
        """One sample point (Phase 1 steps 4-6): cut the window, silence-
        shift forward up to COMPARISON_SILENCE_MAX_SHIFTS times if it's
        mostly silence, then transcribe with the light model. A failed
        point just returns '' — it won't vote, matching this app's
        existing per-file (not per-point) error tolerance elsewhere."""
        ext = os.path.splitext(item.filepath)[1] or ".mkv"
        clip_path = os.path.join(item_dir, f"point_{point_idx}{ext}")
        tries = 0
        cur_start, cur_end = start, end
        while True:
            if self.stop_flag.is_set():
                return ""
            cmd = build_ffmpeg_clip_command(self.ffmpeg_path, item.filepath,
                                            clip_path, cur_start, cur_end)
            proc = subprocess.run(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                encoding="utf-8", errors="replace", env=subprocess_child_env(),
                **subprocess_hidden_window_kwargs())
            if proc.returncode != 0 or not os.path.exists(clip_path):
                return ""
            if tries >= COMPARISON_SILENCE_MAX_SHIFTS:
                break
            sd_cmd = build_silencedetect_command(self.ffmpeg_path, clip_path)
            sd_proc = subprocess.run(
                sd_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                encoding="utf-8", errors="replace", env=subprocess_child_env(),
                **subprocess_hidden_window_kwargs())
            if not clip_is_mostly_silence(sd_proc.stdout, cur_end - cur_start):
                break
            tries += 1
            cur_start, cur_end = comparison_shift_window_forward(cur_start, cur_end, duration)
            try:
                os.remove(clip_path)
            except OSError:
                pass
        text = transcribe_comparison_clip(
            self.whisper_exe, clip_path, item_dir, self.model_cli,
            self.lang_param, self.initial_prompt, self.ffmpeg_path,
            stop_flag=self.stop_flag)
        try:
            if os.path.exists(clip_path):
                os.remove(clip_path)
        except OSError:
            pass
        return text

    # ---- Scenario 3: Base Folder vs. itself, no whisper/ffmpeg ------------

    def _run_md_vs_md(self):
        self.post("log", text=self.s["cmp_log_scenario3_start"])
        candidates, _word_index = self._load_base_candidates_cached()
        n = len(candidates)
        self.id_to_name = {}   # each id IS its own display name (rel_path)
        if self.stop_flag.is_set():
            # Canceled while still loading the Base Folder — a short
            # candidate list here is a side effect of that, not a genuine
            # "too few files" outcome; must not be reported as finished.
            self._finish(canceled=True)
            return
        if n < 2:
            self.post("log", text=self.s["cmp_log_md_too_few"])
            self._finish(canceled=False)
            return

        total_pairs = n * (n - 1) // 2
        self.post("log", text=self.s["cmp_log_md_pairs_start"].format(n=n, pairs=total_pairs))
        self._write_safety_net(COMPARISON_SAFETY_STATUS_IN_PROGRESS,
                               note=self.s["cmp_safety_note_loaded"].format(n=n))

        likely_pairs = []
        processed_pairs = 0
        last_write = time.time()
        canceled = False
        for i in range(n):
            if self.stop_flag.is_set():
                canceled = True
                break
            for j in range(i + 1, n):
                if self.stop_flag.is_set():
                    canceled = True
                    break
                a, b = candidates[i], candidates[j]
                processed_pairs += 1
                if md_pair_passes_cheap_prefilter(a.norm_body, b.norm_body,
                                                  a.duration_seconds, b.duration_seconds):
                    whole_score = text_similarity_ratio(a.norm_body, b.norm_body)
                    cov_ab, cov_ba = paragraph_cross_match_coverage(
                        a.norm_paragraphs, b.norm_paragraphs)
                    tier = tier_for_md_pair(whole_score, cov_ab, cov_ba,
                                            self.likely_threshold, self.possible_threshold)
                    if tier != COMPARISON_TIER_NONE:
                        combined = max(whole_score, cov_ab, cov_ba)
                        self.pair_results.append((a.rel_path, b.rel_path, combined, 0, tier))
                        if tier == COMPARISON_TIER_LIKELY:
                            likely_pairs.append((a.rel_path, b.rel_path))
                now = time.time()
                if now - last_write > COMPARISON_SAFETY_WRITE_MIN_INTERVAL:
                    self.post("log", text=self.s["cmp_log_md_progress"].format(
                        i=processed_pairs, n=total_pairs))
                    self.clusters = cluster_duplicate_pairs(
                        [c.rel_path for c in candidates], likely_pairs)
                    self._write_safety_net(
                        COMPARISON_SAFETY_STATUS_IN_PROGRESS,
                        note=self.s["cmp_safety_note_pairs"].format(
                            i=processed_pairs, n=total_pairs))
                    last_write = now
            if canceled:
                break

        self.clusters = cluster_duplicate_pairs([c.rel_path for c in candidates], likely_pairs)
        self._finish(canceled=canceled)

    def cancel(self):
        self.stop_flag.set()


# ==========================================================================
# ffmpeg archive extraction (testable helper)
# ==========================================================================

def extract_ffmpeg_archive(archive_path, dest_dir):
    """Extract a downloaded ffmpeg archive and return the path to the ffmpeg
    executable copied into dest_dir, or None if not found."""
    archive_path = str(archive_path)
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    extract_root = dest_dir / "_extract"
    if extract_root.exists():
        shutil.rmtree(extract_root, ignore_errors=True)
    extract_root.mkdir(parents=True, exist_ok=True)

    if archive_path.lower().endswith(".zip"):
        with zipfile.ZipFile(archive_path) as zf:
            zf.extractall(extract_root)
    elif archive_path.lower().endswith((".tar.xz", ".tar.gz", ".tgz", ".txz")):
        with tarfile.open(archive_path) as tf:
            tf.extractall(extract_root)
    else:
        return None

    candidates = []
    for root, _dirs, files in os.walk(extract_root):
        for name in files:
            low = name.lower()
            if low == "ffmpeg.exe" or low == "ffmpeg":
                candidates.append(os.path.join(root, name))
    if not candidates:
        return None
    src = candidates[0]
    final_name = "ffmpeg.exe" if src.lower().endswith(".exe") else "ffmpeg"
    final_path = dest_dir / final_name
    shutil.copy2(src, final_path)
    if not final_name.endswith(".exe"):
        try:
            os.chmod(final_path, 0o755)
        except OSError:
            pass
    shutil.rmtree(extract_root, ignore_errors=True)
    return str(final_path)


def extract_pandoc_archive(archive_path, dest_dir):
    """Same shape as extract_ffmpeg_archive() above, for the pandoc zip
    (pandoc-{tag}-windows-x86_64.zip — verified live: pandoc.exe sits one
    level down, inside a pandoc-{tag}/ folder in the zip)."""
    archive_path = str(archive_path)
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    extract_root = dest_dir / "_extract"
    if extract_root.exists():
        shutil.rmtree(extract_root, ignore_errors=True)
    extract_root.mkdir(parents=True, exist_ok=True)

    if archive_path.lower().endswith(".zip"):
        with zipfile.ZipFile(archive_path) as zf:
            zf.extractall(extract_root)
    elif archive_path.lower().endswith((".tar.xz", ".tar.gz", ".tgz", ".txz")):
        with tarfile.open(archive_path) as tf:
            tf.extractall(extract_root)
    else:
        return None

    candidates = []
    for root, _dirs, files in os.walk(extract_root):
        for name in files:
            low = name.lower()
            if low == "pandoc.exe" or low == "pandoc":
                candidates.append(os.path.join(root, name))
    if not candidates:
        return None
    src = candidates[0]
    final_name = "pandoc.exe" if src.lower().endswith(".exe") else "pandoc"
    final_path = dest_dir / final_name
    shutil.copy2(src, final_path)
    if not final_name.endswith(".exe"):
        try:
            os.chmod(final_path, 0o755)
        except OSError:
            pass
    shutil.rmtree(extract_root, ignore_errors=True)
    return str(final_path)


# ==========================================================================
# Scrollable frame (fixes the "text hidden when window shrinks" bug)
# ==========================================================================

class ScrollableFrame(ttk.Frame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0)
        self.vscroll = ttk.Scrollbar(self, orient="vertical",
                                     command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.vscroll.set)
        self.vscroll.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.inner = ttk.Frame(self.canvas)
        self._win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", self._on_inner_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind("<Enter>", self._bind_wheel)
        self.canvas.bind("<Leave>", self._unbind_wheel)

    def _on_inner_configure(self, _event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self.canvas.itemconfig(self._win, width=event.width)

    def _bind_wheel(self, _event):
        self.canvas.bind_all("<MouseWheel>", self._on_wheel)
        self.canvas.bind_all("<Button-4>", self._on_wheel)
        self.canvas.bind_all("<Button-5>", self._on_wheel)

    def _unbind_wheel(self, _event):
        self.canvas.unbind_all("<MouseWheel>")
        self.canvas.unbind_all("<Button-4>")
        self.canvas.unbind_all("<Button-5>")

    def _on_wheel(self, event):
        if event.num == 4:
            self.canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self.canvas.yview_scroll(1, "units")
        else:
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")


class TwoToneProgress(tk.Frame):
    """Determinate progress bar: green fill on a light track with a centered
    NN% label rendered two-tone — white over the filled portion, dark over the
    unfilled portion (no opaque box). Implemented with a clipping frame so the
    text colour splits exactly at the fill edge."""
    TRACK = "#e3e6ea"
    FILL = "#1a7f37"
    DARK = "#222222"
    LIGHT = "#ffffff"

    def __init__(self, master, height=22, **kw):
        super().__init__(master, height=height, bg=self.TRACK,
                         highlightthickness=1, highlightbackground="#c2c7ce", **kw)
        self._pct = 0.0
        self._text = ""
        self.grid_propagate(False)
        self.pack_propagate(False)
        font = ("TkDefaultFont", 9, "bold")
        # bottom layer: full-width track, dark centered text
        self._base = tk.Label(self, bg=self.TRACK, fg=self.DARK, text="",
                              font=font, anchor="center")
        self._base.place(x=0, y=0, relwidth=1, relheight=1)
        # top layer: green clipping frame (width = pct) holding a full-width
        # white centered label, so only the filled part of the white text shows
        self._clip = tk.Frame(self, bg=self.FILL)
        self._clip.place(x=0, y=0, relheight=1, relwidth=0)
        self._fill_label = tk.Label(self._clip, bg=self.FILL, fg=self.LIGHT,
                                    text="", font=font, anchor="center")
        self.bind("<Configure>", lambda e: self._relayout())

    def set_percent(self, pct, text=None):
        try:
            self._pct = max(0.0, min(100.0, float(pct)))
        except (TypeError, ValueError):
            self._pct = 0.0
        if text is not None:
            self._text = text
        self._base.config(text=self._text)
        self._fill_label.config(text=self._text)
        self._relayout()

    def set_text(self, text):
        self.set_percent(self._pct, text=text or "")

    # accept ttk-style configure(value=...) as a fallback
    def configure(self, **kw):
        if "value" in kw:
            self.set_percent(kw.pop("value"))
        if kw:
            super().configure(**kw)
    config = configure

    def _relayout(self):
        self.update_idletasks()
        w = self.winfo_width() or 1
        h = self.winfo_height() or 1
        self._clip.place_configure(relwidth=self._pct / 100.0)
        # full-bar-width label inside the (narrower) clip keeps text centered
        # on the BAR, so it lines up with the dark base text underneath
        self._fill_label.place(x=0, y=0, width=w, height=h)


def render_queue_preserving_selection(tree, populate_fn):
    """item 6: every queue render does delete()+reinsert (needed because
    order/values can change), which by itself wipes Tkinter's selection,
    focus and scroll position. This wrapper captures all three before
    populate_fn() runs and restores whatever of them still exists
    afterward, so inserting new rows (playlist expansion, link reading)
    never steals the user's in-progress selection."""
    try:
        sel_before = tree.selection()
    except tk.TclError:
        sel_before = ()
    try:
        focus_before = tree.focus()
    except tk.TclError:
        focus_before = ""
    try:
        yview_before = tree.yview()
    except tk.TclError:
        yview_before = None

    populate_fn()

    existing = set(tree.get_children())
    restored_sel = [iid for iid in sel_before if iid in existing]
    if restored_sel:
        tree.selection_set(restored_sel)
    if focus_before in existing:
        tree.focus(focus_before)
    if yview_before:
        try:
            tree.yview_moveto(yview_before[0])
        except tk.TclError:
            pass


def bind_header_sort(tree, sortable_columns, *, get_items, is_running, render_fn):
    """item 17: click-header sort, Windows-Explorer-style (1st click asc,
    2nd click desc), enabled only while the queue is idle. Sorting the
    underlying list in place and re-rendering also renumbers the Order
    column, since every render enumerates the list fresh.

    sortable_columns: {col_id: (base_label, key_func)}. key_func(item)
    returns a comparable value, or None to sort last (unknown durations)."""
    state = {"col": None, "reverse": False}

    def relabel():
        for col, (base_label, _key) in sortable_columns.items():
            arrow = ""
            if state["col"] == col:
                arrow = " ▼" if state["reverse"] else " ▲"
            tree.heading(col, text=base_label + arrow)

    def on_click(col):
        if is_running():
            return
        base_label, key_func = sortable_columns[col]
        items = get_items()
        if state["col"] == col:
            state["reverse"] = not state["reverse"]
        else:
            state["col"] = col
            state["reverse"] = False
        # Unknown values always sort last regardless of direction (item 17),
        # so sort the known/unknown groups separately rather than folding
        # "is None" into a single reversible key (which would flip the
        # unknowns to the front on a descending sort).
        known = [it for it in items if key_func(it) is not None]
        unknown = [it for it in items if key_func(it) is None]
        known.sort(key=key_func, reverse=state["reverse"])
        items[:] = known + unknown
        relabel()
        render_fn()

    for col in sortable_columns:
        tree.heading(col, command=lambda c=col: on_click(c))
    relabel()
    return state


def make_scrollable_queue(parent, columns, height=12):
    """Treeview + wired vertical scrollbar; wheel routed to the tree (returns
    'break' so an enclosing ScrollableFrame doesn't also scroll). Returns
    (wrapper_frame, tree, scrollbar)."""
    wrap = ttk.Frame(parent)
    wrap.columnconfigure(0, weight=1)
    wrap.rowconfigure(0, weight=1)
    tree = ttk.Treeview(wrap, columns=columns, show="headings",
                        height=height, selectmode="extended")
    vsb = ttk.Scrollbar(wrap, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=vsb.set)
    tree.grid(row=0, column=0, sticky="nsew")
    vsb.grid(row=0, column=1, sticky="ns")

    def _wheel(event):
        if event.num == 4:
            tree.yview_scroll(-1, "units")
        elif event.num == 5:
            tree.yview_scroll(1, "units")
        else:
            tree.yview_scroll(int(-1 * (event.delta / 120)), "units")
        return "break"
    tree.bind("<MouseWheel>", _wheel)
    tree.bind("<Button-4>", _wheel)
    tree.bind("<Button-5>", _wheel)
    _enable_explorer_multiselect(tree)
    return wrap, tree, vsb


def _enable_explorer_multiselect(tree):
    """Windows-Explorer-style selection: Shift+Up/Down extend the selection
    from an anchor; Ctrl+A selects all. (Mouse shift/ctrl-click already work
    via selectmode='extended'.)"""
    tree._sel_anchor = None

    def _extend(forward):
        items = tree.get_children()
        if not items:
            return "break"
        cur = tree.focus()
        if not cur:
            sel = tree.selection()
            cur = sel[-1] if sel else items[0]
        if tree._sel_anchor not in items:
            tree._sel_anchor = cur
        try:
            ci = items.index(cur)
        except ValueError:
            ci = 0
        ni = max(0, min(len(items) - 1, ci + (1 if forward else -1)))
        new = items[ni]
        tree.focus(new)
        tree.see(new)
        ai = items.index(tree._sel_anchor)
        lo, hi = sorted((ai, ni))
        tree.selection_set(items[lo:hi + 1])
        return "break"

    def _extend_page(forward):
        """item 4: Shift+PageUp/PageDown extends the selection by one page
        (the Treeview's configured visible row count)."""
        items = tree.get_children()
        if not items:
            return "break"
        cur = tree.focus()
        if not cur:
            sel = tree.selection()
            cur = sel[-1] if sel else items[0]
        if tree._sel_anchor not in items:
            tree._sel_anchor = cur
        try:
            ci = items.index(cur)
        except ValueError:
            ci = 0
        try:
            page = max(1, int(tree.cget("height")))
        except (tk.TclError, ValueError):
            page = 10
        step = page if forward else -page
        ni = max(0, min(len(items) - 1, ci + step))
        new = items[ni]
        tree.focus(new)
        tree.see(new)
        ai = items.index(tree._sel_anchor)
        lo, hi = sorted((ai, ni))
        tree.selection_set(items[lo:hi + 1])
        return "break"

    def _select_all(_e=None):
        kids = tree.get_children()
        if kids:
            tree.selection_set(kids)
            tree._sel_anchor = kids[0]
        return "break"

    def _reset_anchor_click(e):
        row = tree.identify_row(e.y)
        if row:
            tree._sel_anchor = row

    def _reset_anchor_arrow(_e):
        tree.after(1, lambda: setattr(tree, "_sel_anchor", tree.focus()))

    tree.bind("<Shift-Down>", lambda e: _extend(True))
    tree.bind("<Shift-Up>", lambda e: _extend(False))
    tree.bind("<Shift-Next>", lambda e: _extend_page(True))   # Shift+PageDown
    tree.bind("<Shift-Prior>", lambda e: _extend_page(False))  # Shift+PageUp
    tree.bind("<Control-a>", _select_all)
    tree.bind("<Control-A>", _select_all)
    tree.bind("<Button-1>", _reset_anchor_click, add="+")
    tree.bind("<Down>", _reset_anchor_arrow, add="+")
    tree.bind("<Up>", _reset_anchor_arrow, add="+")
    # exposed for programmatic use / tests
    tree.ms_extend = _extend
    tree.ms_extend_page = _extend_page
    tree.ms_select_all = _select_all


def bind_queue_delete_key(tree, on_delete):
    """item 4: DEL deletes the selected entries, using the same rules
    (respect processing state) as the tab's existing remove-selected
    handler — every queue Treeview just reuses that handler here."""
    tree.bind("<Delete>", lambda e: (on_delete(), "break")[-1])


def bind_queue_copy_link(tree, get_link_for_item):
    """item 5: right-click a queue entry -> context menu with 'Copy link',
    puts that entry's URL on the clipboard. get_link_for_item(item_id) may
    return None/'' for rows that have no URL (menu item stays disabled)."""
    menu = tk.Menu(tree, tearoff=0)

    def do_copy(item_id):
        link = get_link_for_item(item_id) or ""
        if not link:
            return
        tree.clipboard_clear()
        tree.clipboard_append(link)

    def on_right_click(event):
        row = tree.identify_row(event.y)
        if not row:
            return
        if row not in tree.selection():
            tree.selection_set(row)
            tree.focus(row)
        link = get_link_for_item(row)
        menu.delete(0, "end")
        label = tree._copy_link_label if hasattr(tree, "_copy_link_label") else "Copy link"
        menu.add_command(label=label, command=lambda: do_copy(row),
                         state=("normal" if link else "disabled"))
        menu.tk_popup(event.x_root, event.y_root)

    tree.bind("<Button-3>", on_right_click, add="+")
    tree._copy_link_menu = menu  # keep a reference alive


# ==========================================================================
# Main application
# ==========================================================================

DEFAULT_CONFIG = {
    "ui_language": "en",
    "whisper_path": "",
    "whisper_env_dir": "",
    "ffmpeg_path": "",
    "markitdown_python": "",
    "docling_env_dir": "",
    "pandoc_path": "",
    "pandoc_installed_version": "",
    "conversion_model": "markitdown",
    "audio_lang_code": "pt",
    "audio_langs": list(DEFAULT_AUDIO_LANGS),
    "model_cli": "turbo",
    "task": "transcribe",
    "output_formats": {f: True for f in OUTPUT_FORMATS},
    "output_dir_mode": "same",
    "fixed_output_dir": "",
    "selected_dictionary": "",
    "youtube_pref_lang": "auto",
    "youtube_keep_srt": True,
    "youtube_keep_txt": True,
    "youtube_output_dir": "",
    # v0.8.0
    "download_resolution": "best",
    "download_audio_only": False,
    "download_audio_format": "mp3",
    "download_container": "mp4",
    "download_output_dir": "",
    "speed_factor_by_model": {},
    "yt_per_video_seconds": YT_PER_VIDEO_DEFAULT,
    "md_per_file_seconds": MD_PER_FILE_DEFAULT,
    # v0.9.0 — pause control
    "youtube_pause_enabled": False,
    "youtube_pause_every": 20,
    "youtube_pause_minutes": 5,
    "download_pause_enabled": False,
    "download_pause_every": 20,
    "download_pause_minutes": 5,
    # v0.9.0 — transcribe after download (uses its own Whisper settings)
    "download_transcribe": False,
    "download_whisper_defined": False,
    "download_whisper_model": "",
    "download_whisper_lang": "pt",
    "download_whisper_dictionary": "",
    # v0.10.0 — shared MD header (metadata) config across all tabs
    "md_header": default_header_config(),
    # v0.10.0 Phase 2 — grabber channel sections + members filter
    "grabber_sections": {"videos": True, "shorts": True, "live": True, "podcast": True},
    "grabber_exclude_members": False,
    "grabber_title_lang": "auto",
    # legacy keys kept only so a pre-0.11.0 config.json's values survive the
    # load-time copy loop long enough for the one-time migration below.
    "grabber_output_mode": None,
    "grabber_include_duration": None,
    # v0.11.0 item 13/18 — checkbox output selection + duration bounds
    "grabber_want_title": False,
    "grabber_want_duration_col": False,
    "grabber_want_link": True,
    "grabber_min_dur_enabled": False,
    "grabber_min_dur_minutes": "",
    "grabber_max_dur_enabled": False,
    "grabber_max_dur_minutes": "",
    # v0.10.5 — post-conversion MD cleanup for LLM training
    "md_polish": True,
    # v0.11.01 item 1 — keep "[t=MM:SS]" per-paragraph anchors in transcript-
    # derived MD (srt/vtt/whisper/youtube-transcript paths only)
    "keep_timestamps_in_md": True,
    # v0.11.0 item 1.4/1.7 — update-check bookkeeping
    "ffmpeg_build_installed_at": "",
    "_migration_offered_v011": False,
    # v0.11.0 item 8 — batch-size protections, opt-out (default ON)
    "batch_warn_enabled": True,
    "batch_cap_enabled": True,
    # v0.11.0 item 14 — global MD header language, default Portuguese
    "header_lang": "pt",
    # v0.11.0 item 20 — LAN status page, disabled by default
    "lan_status_enabled": False,
    "lan_status_port": 8080,
    "lan_status_bind": "0.0.0.0",
    "lan_status_token_enabled": False,
    "lan_status_token": "",
    # v0.12.0 — Comparison tab
    "comparison_base_folder": "",
    "comparison_excerpt_seconds": COMPARISON_EXCERPT_SECONDS_DEFAULT,
    "comparison_model_cli": "tiny",
}

_OLD_AUDIO_LANG_MAP = {"portuguese": "pt", "english": "en",
                       "spanish": "es", "auto": "auto"}


# ==========================================================================
# item 20 (v0.11.0) — LAN status page (read-only remote monitoring)
# ==========================================================================

def get_lan_ip():
    """Local LAN IP via the UDP-socket trick (20.2): connecting a UDP socket
    never actually transmits a packet, so this makes no external network
    call — it only asks the OS routing table which local interface/IP would
    be used to reach that address."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def lan_firewall_command(port):
    """The exact Windows Firewall command to allow inbound connections
    (20.2), shown verbatim in Settings and the About tab."""
    return (f'netsh advfirewall firewall add rule name="TranscriptLab LAN Status" '
           f'dir=in action=allow protocol=TCP localport={port}')


def make_lan_status_handler(get_snapshot, get_html_page, token):
    """Returns a BaseHTTPRequestHandler subclass closing over the given
    snapshot getter / page getter / token (20.1/20.2). A fresh class per
    server start keeps state changes (token, page) isolated per instance."""

    class LanStatusHandler(BaseHTTPRequestHandler):
        server_version = "TranscriptLab-LAN/1.0"

        def _authorized(self):
            if not token:
                return True
            qs = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(qs)
            return params.get("k", [None])[0] == token

        def _send_json(self, status, obj):
            body = json.dumps(obj).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_html(self, status, html):
            body = html.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = urllib.parse.urlparse(self.path).path
            if not self._authorized():
                self._send_json(403, {"error": "forbidden"})
                return
            if path == "/":
                self._send_html(200, get_html_page())
            elif path == "/api/status":
                self._send_json(200, get_snapshot())
            else:
                self._send_json(404, {"error": "not found"})

        def log_message(self, fmt, *args):
            pass  # never spam stderr from a background HTTP thread

    return LanStatusHandler


class LanStatusServer:
    """item 20.1/20.2/20.6: stdlib-only ThreadingHTTPServer on a daemon
    thread. Strictly read-only — see App._lan_build_snapshot for the only
    place that touches Tk state, always from the Tk main thread."""

    def __init__(self, get_snapshot, get_html_page):
        self.get_snapshot = get_snapshot
        self.get_html_page = get_html_page
        self.httpd = None
        self.thread = None
        self.port = None

    @property
    def running(self):
        return self.httpd is not None

    def start(self, host, port, token=None):
        if self.running:
            self.stop()
        handler_cls = make_lan_status_handler(self.get_snapshot, self.get_html_page, token)
        try:
            httpd = ThreadingHTTPServer((host, port), handler_cls)
        except OSError as e:
            return False, str(e)
        self.httpd = httpd
        self.port = httpd.server_address[1]
        self.thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        self.thread.start()
        return True, None

    def stop(self):
        if self.httpd is not None:
            try:
                self.httpd.shutdown()
                self.httpd.server_close()
            except OSError:
                pass
        self.httpd = None
        self.thread = None
        self.port = None


def build_lan_status_html(lang, hostname, app_version):
    """item 20.5: one self-contained HTML string, inline CSS/JS, no CDN.
    Polls /api/status every 3s; shows hostname, version, 'updated Xs ago',
    and a lost-connection banner. Text follows the app's UI language at the
    time the server was (re)started."""
    if lang == "pt":
        title = "TranscriptLab — Status"
        h1 = "Status do TranscriptLab"
        lost = "Conexão perdida — tentando reconectar…"
        updated_label = "atualizado há"
        seconds_word = "s"
        queues_label = "Filas"
        current_label = "Processando agora"
        tools_label = "Ferramentas"
        none_label = "nenhum"
        log_label = "Últimas linhas"
    else:
        title = "TranscriptLab — Status"
        h1 = "TranscriptLab Status"
        lost = "Connection lost — retrying…"
        updated_label = "updated"
        seconds_word = "s ago"
        queues_label = "Queues"
        current_label = "Currently processing"
        tools_label = "Tools"
        none_label = "none"
        log_label = "Recent lines"

    return f"""<!DOCTYPE html>
<html lang="{lang}"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  body {{ font-family: -apple-system, Segoe UI, Arial, sans-serif; margin: 0; padding: 24px;
         background: #0d1117; color: #c9d1d9; }}
  h1 {{ font-size: 20px; margin: 0 0 4px; }}
  .sub {{ color: #8b949e; font-size: 13px; margin-bottom: 20px; }}
  .banner {{ display: none; background: #cf222e; color: #fff; padding: 8px 12px;
            border-radius: 6px; margin-bottom: 16px; font-size: 13px; }}
  .card {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px;
          padding: 14px 16px; margin-bottom: 14px; }}
  .card h2 {{ font-size: 14px; margin: 0 0 8px; color: #8b949e; text-transform: uppercase;
             letter-spacing: .04em; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  td {{ padding: 3px 6px; }}
  .pill {{ display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 12px; }}
  .ok {{ background: #1a7f37; }}
  .bad {{ background: #6e1c1c; }}
  pre {{ white-space: pre-wrap; word-break: break-word; font-size: 12px; color: #8b949e;
        max-height: 220px; overflow-y: auto; margin: 0; }}
</style>
</head><body>
<div id="banner" class="banner">{lost}</div>
<h1>{h1}</h1>
<div class="sub" id="sub">{hostname} · v{app_version}</div>

<div class="card"><h2>{queues_label}</h2><table id="tabs"></table></div>
<div class="card"><h2>{current_label}</h2><div id="current">{none_label}</div></div>
<div class="card"><h2>{tools_label}</h2><table id="tools"></table></div>
<div class="card"><h2>{log_label}</h2><pre id="log"></pre></div>

<script>
const TAB_NAMES = {{av:"AV", md:"MD", yt:"YouTube", dl:"Download"}};
let lastOkAt = Date.now();
function fmtAgo(ms) {{
  const s = Math.max(0, Math.round(ms/1000));
  return s + "{seconds_word}";
}}
function render(data) {{
  document.getElementById("sub").textContent =
    data.hostname + " · v" + data.app_version + " · {updated_label} " + fmtAgo(0);
  const tabsEl = document.getElementById("tabs");
  tabsEl.innerHTML = "";
  for (const key in data.tabs) {{
    const t = data.tabs[key];
    const row = document.createElement("tr");
    row.innerHTML = "<td>" + (TAB_NAMES[key] || key) + "</td>" +
      "<td>pending: " + t.pending + "</td>" +
      "<td>running: " + t.running + "</td>" +
      "<td>done: " + t.done + "</td>" +
      "<td>error: " + t.error + "</td>";
    tabsEl.appendChild(row);
  }}
  const cur = data.current_item;
  document.getElementById("current").textContent = cur
    ? (cur.name + " — " + (cur.progress_pct != null ? cur.progress_pct + "%" : "…"))
    : "{none_label}";
  const toolsEl = document.getElementById("tools");
  toolsEl.innerHTML = "";
  for (const key in data.tools) {{
    const row = document.createElement("tr");
    const ok = data.tools[key];
    row.innerHTML = "<td>" + key + "</td><td><span class='pill " +
      (ok ? "ok" : "bad") + "'>" + (ok ? "OK" : "—") + "</span></td>";
    toolsEl.appendChild(row);
  }}
  document.getElementById("log").textContent = (data.log_tail || []).join("");
}}
async function poll() {{
  try {{
    const resp = await fetch("/api/status" + location.search, {{cache: "no-store"}});
    if (!resp.ok) throw new Error("bad status");
    const data = await resp.json();
    lastOkAt = Date.now();
    document.getElementById("banner").style.display = "none";
    render(data);
  }} catch (e) {{
    if (Date.now() - lastOkAt > 6000) {{
      document.getElementById("banner").style.display = "block";
    }}
  }}
}}
poll();
setInterval(poll, 3000);
</script>
</body></html>"""


class TranscriptLabApp(tk.Tk):
    def __init__(self):
        super().__init__()
        ensure_config_dir()
        self.cfg = self._load_config()
        self.lang = self.cfg.get("ui_language", "en")
        if self.lang not in TRANSLATIONS:
            self.lang = "en"
        self.s = TRANSLATIONS[self.lang]

        self.dictionaries = load_json(DICTIONARIES_FILE, {})

        # Shared MD header include flag (item 4): one var bound by all tabs so
        # they stay in sync; survives language rebuilds.
        self.header_include_var = tk.BooleanVar(
            value=bool((self.cfg.get("md_header") or {}).get("include", True)))
        # v0.10.5 — shared "polish the MD for AI" flag, honoured by every tab
        # that writes Markdown (Whisper, MD File Generation, YouTube, Download).
        self.md_polish_var = tk.BooleanVar(value=bool(self.cfg.get("md_polish", True)))
        # v0.11.01 item 1 — shared "keep [t=MM:SS] anchors" flag, same
        # cross-tab-sync pattern as md_polish_var.
        self.keep_timestamps_var = tk.BooleanVar(
            value=bool(self.cfg.get("keep_timestamps_in_md", True)))
        # Per-tab "batch finished" flags (item 9): once a queue finishes, adding
        # more prompts the user to clear the stale queue first.
        self._finished = {"av": False, "md": False, "yt": False, "dl": False}
        self.dl_whisper_reviewed = False

        # item 20 — LAN status page: start time, rolling log tail, snapshot
        # buffer + lock (the HTTP thread only ever reads the snapshot; only
        # the Tk main thread writes it), and the (initially stopped) server.
        self._start_time = time.time()
        self._lan_log_tail = collections.deque(maxlen=30)
        self._lan_snapshot = {}
        self._lan_snapshot_lock = threading.Lock()
        self._lan_server = LanStatusServer(self._lan_get_snapshot, self._lan_get_html_page)

        # runtime state
        self.queue_items = []
        self.live_queue = None
        self.md_queue_items = []
        self.worker = None
        self.stop_flag = None
        self.event_queue = queue.Queue()
        self.is_running = False
        self.md_worker = None
        self.md_stop_flag = None
        self.md_event_queue = queue.Queue()
        self.md_is_running = False
        self.youtube_queue_items = []
        self.youtube_worker = None
        self.youtube_stop_flag = None
        self.youtube_event_queue = queue.Queue()
        self.youtube_is_running = False
        # download tab
        self.download_queue_items = []
        self.dl_live_queue = None
        self.download_worker = None
        self.download_stop_flag = None
        self.download_event_queue = queue.Queue()
        self.download_is_running = False
        self._dl_done = 0
        self._dl_errors = 0
        self._dl_cur_running_id = None
        # grabber tab
        self.grabber_worker = None
        self.grabber_stop_flag = None
        self.grabber_event_queue = queue.Queue()
        self.grabber_is_running = False
        self._grab_entries = []
        # comparison tab (v0.12.0 / v0.12.1)
        self.comparison_queue_items = []
        self.comparison_live_queue = None
        self.comparison_worker = None
        self.comparison_stop_flag = None
        self.comparison_event_queue = queue.Queue()
        self.comparison_is_running = False
        self._comparison_base_matches = {}    # item_id -> [(rel_path, score, agreeing, tier, excerpt, window), ...]
        self._comparison_pair_results = []    # [(id_a, id_b, score, agreeing, tier), ...]
        self._comparison_clusters = []        # [[id, id, ...], ...]
        self._comparison_id_to_name = {}      # id (as used above) -> display name, from the worker
        self._comparison_ran_once = False
        self._comparison_partial = False      # last result was a cancel/error, not a clean finish
        self._comparison_scenario = None      # "media" or "md_only" — which results section applies
        self._comparison_base_index_cache = None   # (signature, [ComparisonCandidate,...], word_index)
        # playlist expansion workers (keyed lists, polled via the owning tab queue)
        self._expand_workers = []
        # async length probe
        self._probe_event_queue = queue.Queue()
        self._probe_threads = []
        self._yt_controls = []
        self._yt_done = 0
        self._yt_errors = 0
        self._yt_cur_index = 0
        self._wrap_labels = []
        self._batch_start_time = None
        self._batch_done = 0
        self._batch_errors = 0
        self._cur_duration = None
        self._cur_phase = None
        self._trans_total_seconds = 0.0
        self._trans_done_seconds = 0.0
        self._cur_position = 0.0
        self._cur_index = 0
        self._md_batch_start_time = None
        self._md_done = 0
        self._md_errors = 0
        self._md_cur_index = 0

        # dependency detection
        self._detect_dependencies()

        self.title(self.s["window_title"])
        self.geometry("1060x1042")
        self.minsize(760, 600)
        self._set_icon()

        self._build_menubar()
        self._build_ui()
        self._restore_queues_state()
        # item 20: now that the four main log widgets exist, route their
        # text through the LAN status log tail too.
        self._LAN_STATUS_LOG_WIDGETS = (
            self.log_text, self.md_log_text, self.yt_log_text, self.dl_log_text)

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(120, self._poll_events)
        self.after(120, self._poll_md_events)
        self.after(120, self._poll_youtube_events)
        self.after(120, self._poll_download_events)
        self.after(120, self._poll_grabber_events)
        self.after(120, self._poll_comparison_events)
        self.after(150, self._poll_probe_events)
        self.after(400, self._maybe_offer_legacy_migration)
        self.after(1000, self._lan_refresh_snapshot_loop)
        if self.cfg.get("lan_status_enabled"):
            self._lan_start_server()

    # ---- helpers ---------------------------------------------------------
    def t(self, key, **kw):
        text = self.s.get(key, key)
        if kw:
            try:
                return text.format(**kw)
            except (KeyError, IndexError, ValueError):
                return text
        return text

    def _load_config(self):
        data = load_json(CONFIG_FILE, {})
        cfg = dict(DEFAULT_CONFIG)
        cfg["output_formats"] = dict(DEFAULT_CONFIG["output_formats"])
        cfg["audio_langs"] = list(DEFAULT_AUDIO_LANGS)
        cfg["speed_factor_by_model"] = {}
        if isinstance(data, dict):
            # migrate old audio_lang_key
            if "audio_lang_code" not in data and "audio_lang_key" in data:
                data["audio_lang_code"] = _OLD_AUDIO_LANG_MAP.get(
                    data.get("audio_lang_key"), "pt")
            for k, v in data.items():
                if k == "output_formats" and isinstance(v, dict):
                    merged = dict(DEFAULT_CONFIG["output_formats"])
                    merged.update({fk: bool(fv) for fk, fv in v.items()
                                   if fk in OUTPUT_FORMATS})
                    cfg["output_formats"] = merged
                elif k in DEFAULT_CONFIG:
                    cfg[k] = v
        if not isinstance(cfg.get("speed_factor_by_model"), dict):
            cfg["speed_factor_by_model"] = {}
        # Normalize the shared MD header config (item 3/4).
        mh = cfg.get("md_header")
        norm = default_header_config()
        if isinstance(mh, dict):
            norm["include"] = bool(mh.get("include", True))
            src_fields = mh.get("fields", {}) or {}
            for f in HEADER_FIELDS:
                fc = src_fields.get(f, {}) or {}
                norm["fields"][f] = {
                    "auto": bool(fc.get("auto", True)),
                    "value": str(fc.get("value", "")),
                }
        cfg["md_header"] = norm
        gs = cfg.get("grabber_sections")
        norm_gs = {"videos": True, "shorts": True, "live": True, "podcast": True}
        if isinstance(gs, dict):
            for k in norm_gs:
                norm_gs[k] = bool(gs.get(k, True))
        cfg["grabber_sections"] = norm_gs
        cfg["grabber_exclude_members"] = bool(cfg.get("grabber_exclude_members", False))
        tl = cfg.get("grabber_title_lang", "auto")
        cfg["grabber_title_lang"] = tl if tl in GRAB_TITLE_LANGS else "auto"
        # item 13 (v0.11.0): migrate the old 3-way radio mode / "include
        # duration" checkbox into the new independent output checkboxes,
        # once, if this config predates the change.
        legacy_mode = cfg.pop("grabber_output_mode", None)
        legacy_include_dur = cfg.pop("grabber_include_duration", None)
        if (legacy_mode is not None and isinstance(data, dict)
                and "grabber_want_title" not in data):
            cfg["grabber_want_title"] = legacy_mode in ("title_link", "title_dur_link")
            cfg["grabber_want_duration_col"] = (legacy_mode == "title_dur_link"
                                                or bool(legacy_include_dur))
            cfg["grabber_want_link"] = True
        cfg["grabber_want_title"] = bool(cfg.get("grabber_want_title", False))
        cfg["grabber_want_duration_col"] = bool(cfg.get("grabber_want_duration_col", False))
        cfg["grabber_want_link"] = bool(cfg.get("grabber_want_link", True))
        cfg["grabber_min_dur_enabled"] = bool(cfg.get("grabber_min_dur_enabled", False))
        cfg["grabber_max_dur_enabled"] = bool(cfg.get("grabber_max_dur_enabled", False))
        cfg["md_polish"] = bool(cfg.get("md_polish", True))
        if cfg.get("download_resolution") not in DOWNLOAD_RESOLUTIONS:
            cfg["download_resolution"] = "best"
        if cfg.get("download_audio_format") not in DOWNLOAD_AUDIO_FORMATS:
            cfg["download_audio_format"] = "mp3"
        if cfg.get("download_container") not in DOWNLOAD_CONTAINERS:
            cfg["download_container"] = "mp4"
        # sanity
        if cfg.get("audio_lang_code") not in (
                list(AUDIO_LANG_OPTIONS) + list(WHISPER_LANGUAGES)):
            cfg["audio_lang_code"] = "pt"
        langs = cfg.get("audio_langs") or list(DEFAULT_AUDIO_LANGS)
        cfg["audio_langs"] = [c for c in langs
                              if c in AUDIO_LANG_OPTIONS or c in WHISPER_LANGUAGES]
        if not cfg["audio_langs"]:
            cfg["audio_langs"] = list(DEFAULT_AUDIO_LANGS)
        if cfg["audio_lang_code"] not in cfg["audio_langs"]:
            cfg["audio_langs"].insert(0, cfg["audio_lang_code"])
        return cfg

    # Keys that hold filesystem paths to app-managed tools; stored relative
    # to APP_DIR whenever possible so the whole folder is portable (item 1.2).
    _TOOL_PATH_KEYS = ("whisper_path", "whisper_env_dir", "ffmpeg_path",
                       "markitdown_python", "ytdlp_path")

    def _save_config(self):
        to_write = dict(self.cfg)
        for k in self._TOOL_PATH_KEYS:
            if to_write.get(k):
                to_write[k] = to_app_relative(to_write[k])
        save_json(CONFIG_FILE, to_write)

    # ---- MD header (metadata) — shared across all tabs (item 3/4) --------
    def _active_header_config(self):
        base = self.cfg.get("md_header") or default_header_config()
        return {"include": bool(self.header_include_var.get()),
                "fields": base.get("fields", default_header_config()["fields"])}

    def _on_header_include_toggle(self):
        self.cfg.setdefault("md_header", default_header_config())
        self.cfg["md_header"]["include"] = bool(self.header_include_var.get())
        self._save_config()

    def _gate_finished_queue(self, tab, has_items, clear_fn, keep_fn=None):
        """item 15: if the queue already finished a run, offer a three-way
        choice before adding new items: Keep old + add new (errored items
        reset to pending, done items stay done and are skipped on the next
        run since workers only pull ST_PENDING) / Delete all + add new /
        Cancel. Returns True to proceed with the add, False to abort."""
        if self._finished.get(tab) and has_items:
            choice = self._ask_replace_queue_choice()
            if choice == "keep" and keep_fn is not None:
                keep_fn()
                self._finished[tab] = False
                return True
            if choice == "delete":
                clear_fn()
                self._finished[tab] = False
                return True
            return False
        self._finished[tab] = False
        return True

    def _ask_replace_queue_choice(self):
        """item 15: modal Keep/Delete/Cancel dialog. Returns 'keep',
        'delete', or 'cancel'."""
        result = {"choice": "cancel"}
        dlg = tk.Toplevel(self)
        dlg.title(self.t("replace_queue_title"))
        dlg.transient(self)
        dlg.resizable(False, False)
        if getattr(self, "_icon_img_small", None) is not None:
            try:
                dlg.iconphoto(False, self._icon_img_small)
            except tk.TclError:
                pass
        frm = ttk.Frame(dlg)
        frm.pack(fill="both", expand=True, padx=16, pady=16)
        ttk.Label(frm, text=self.t("replace_queue_msg"), wraplength=380,
                  justify="left").pack(pady=(0, 12))
        btns = ttk.Frame(frm)
        btns.pack()

        def pick(choice):
            result["choice"] = choice
            dlg.destroy()
        ttk.Button(btns, text=self.t("replace_queue_keep"),
                  command=lambda: pick("keep")).pack(side="left", padx=4)
        ttk.Button(btns, text=self.t("replace_queue_delete"),
                  command=lambda: pick("delete")).pack(side="left", padx=4)
        ttk.Button(btns, text=self.t("cancel"),
                  command=lambda: pick("cancel")).pack(side="left", padx=4)
        dlg.protocol("WM_DELETE_WINDOW", lambda: pick("cancel"))
        dlg.grab_set()
        self.wait_window(dlg)
        return result["choice"]

    @staticmethod
    def _reset_errored_to_pending(items):
        """item 15 'Keep' path: errored items become re-runnable; done items
        are left untouched (workers already only pull ST_PENDING, so they
        are naturally skipped on the next run)."""
        for it in items:
            if it.status == ST_ERROR:
                it.status = ST_PENDING
                it.error_message = ""

    def _confirm_header_before_start(self):
        """When the header is on but any field is manual, warn and confirm."""
        cfg = self._active_header_config()
        if not cfg.get("include", True):
            return True
        if header_config_all_auto(cfg):
            return True
        return messagebox.askokcancel(self.t("header_manual_warn_title"),
                                      self.t("header_manual_warn_msg"))

    def _open_header_editor(self):
        cfg = self.cfg.get("md_header") or default_header_config()
        fields_cfg = cfg.get("fields", {})
        dlg = tk.Toplevel(self)
        dlg.title(self.t("header_editor_title"))
        dlg.transient(self)
        dlg.resizable(False, False)
        if getattr(self, "_icon_img_small", None) is not None:
            try:
                dlg.iconphoto(False, self._icon_img_small)
            except Exception:
                pass
        frm = ttk.Frame(dlg)
        frm.pack(fill="both", expand=True, padx=16, pady=14)
        ttk.Label(frm, text=self.t("header_editor_intro"),
                  wraplength=460, justify="left").grid(row=0, column=0, columnspan=3,
                                                       sticky="w", pady=(0, 10))
        auto_vars, val_vars, entries = {}, {}, {}

        def make_toggle(field, entry):
            def _cb():
                entry.configure(state=("disabled" if auto_vars[field].get() else "normal"))
            return _cb

        r = 1
        for field in HEADER_FIELDS:
            fc = fields_cfg.get(field, {}) or {}
            default_val = "Bruta" if field == "qualidade" else ""
            ttk.Label(frm, text=HEADER_LABELS[field] + ":").grid(
                row=r, column=0, sticky="w", padx=(0, 8), pady=3)
            av = tk.BooleanVar(value=bool(fc.get("auto", True)))
            vv = tk.StringVar(value=str(fc.get("value", default_val)))
            auto_vars[field] = av
            val_vars[field] = vv
            ent = ttk.Entry(frm, textvariable=vv, width=42)
            entries[field] = ent
            chk = ttk.Checkbutton(frm, text=self.t("header_auto"), variable=av,
                                  command=make_toggle(field, ent))
            chk.grid(row=r, column=1, sticky="w", padx=(0, 8))
            ent.grid(row=r, column=2, sticky="we", pady=3)
            ent.configure(state=("disabled" if av.get() else "normal"))
            r += 1
        frm.columnconfigure(2, weight=1)

        btns = ttk.Frame(frm)
        btns.grid(row=r, column=0, columnspan=3, sticky="e", pady=(14, 0))

        def _save():
            new_fields = {}
            for field in HEADER_FIELDS:
                new_fields[field] = {"auto": bool(auto_vars[field].get()),
                                     "value": val_vars[field].get()}
            self.cfg["md_header"] = {"include": bool(self.header_include_var.get()),
                                     "fields": new_fields}
            self._save_config()
            dlg.destroy()

        ttk.Button(btns, text=self.t("cancel"), command=dlg.destroy).pack(side="right")
        ttk.Button(btns, text=self.t("save"), command=_save).pack(side="right", padx=(0, 8))
        dlg.grab_set()

    def _build_header_controls(self, parent, with_polish_hint=False):
        """The 'Include header' checkbox + 'Edit Header' button + the v0.10.5
        'Polish MD for AI' checkbox. Shared by every tab that writes Markdown.
        with_polish_hint adds the explanatory line (only where there is room).
        Returns the frame."""
        box = ttk.Frame(parent)
        row = ttk.Frame(box)
        row.pack(anchor="w", fill="x")
        chk = ttk.Checkbutton(row, text=self.t("header_include"),
                              variable=self.header_include_var,
                              command=self._on_header_include_toggle)
        chk.pack(side="left")
        btn = ttk.Button(row, text=self.t("header_edit"),
                         command=self._open_header_editor)
        btn.pack(side="left", padx=(8, 0))
        box.edit_header_btn = btn  # item 10: exposed so callers can gate it
        pol = ttk.Checkbutton(row, text=self.t("md_polish_check"),
                              variable=self.md_polish_var,
                              command=self._on_md_polish_toggle)
        pol.pack(side="left", padx=(16, 0))
        ts = ttk.Checkbutton(row, text=self.t("keep_timestamps_check"),
                             variable=self.keep_timestamps_var,
                             command=self._on_keep_timestamps_toggle)
        ts.pack(side="left", padx=(16, 0))
        if with_polish_hint:
            hint = ttk.Label(box, text=self.t("md_polish_hint"), foreground="#666",
                             justify="left", wraplength=820)
            hint.pack(anchor="w", pady=(2, 0))
            self._md_polish_hint_label = hint
        return box

    def _on_md_polish_toggle(self):
        self.cfg["md_polish"] = bool(self.md_polish_var.get())
        self._save_config()

    def _polish_enabled(self):
        return bool(self.md_polish_var.get())

    def _on_keep_timestamps_toggle(self):
        self.cfg["keep_timestamps_in_md"] = bool(self.keep_timestamps_var.get())
        self._save_config()

    def _keep_timestamps_enabled(self):
        return bool(self.keep_timestamps_var.get())

    def _detect_dependencies(self):
        self.whisper_path = find_whisper_path(self.cfg.get("whisper_path") or None)
        self.ffmpeg_path = find_ffmpeg(self.cfg.get("ffmpeg_path") or None)
        self.python_exe = markitdown_python(self.cfg)
        self.markitdown_ok = markitdown_is_available(self.python_exe)
        self.ytdlp_ok = ytdlp_is_available(self.python_exe)
        # v0.13.7: readiness only, computed the same cheap way as the
        # others (no network) -- not wired into any tab/Settings UI yet
        # (that's v0.13.8), but available now so nothing has to change
        # here again when that wiring lands.
        self.docling_ok = docling_is_available(docling_env_dir_from_cfg(self.cfg))
        self.pandoc_path = find_pandoc(self.cfg.get("pandoc_path") or None)

    def _whisper_readiness(self):
        """v0.12.2: 'ready', 'missing', or 'broken'. A fresh, cheap
        (interpreter-startup-only) re-check of self.whisper_path right
        before any actual transcription attempt — self.whisper_path is
        normally only re-evaluated at startup or from Settings, and a
        managed venv can go stale (its base Python moved/reinstalled)
        without either of those happening in between. Clears
        self.whisper_path on finding it broken, so every caller sees the
        same falsy state afterward."""
        if not self.whisper_path:
            return "missing"
        env_dir = _venv_root_for_exe(self.whisper_path)
        if env_dir and not venv_python_launches(env_dir):
            self.whisper_path = ""
            return "broken"
        return "ready"

    def _python_choice_display(self, compat):
        """v0.12.4: the compatible-Python line shown in Install/Repair
        confirmations, with a note appended if it's not a dedicated
        standalone install — since building a venv on top of another
        application's own bundled Python is fragile in exactly the way
        that caused this class of bug in the first place (that other
        app's runtime is outside this app's control and can move,
        update, or disappear at any time)."""
        if not compat:
            return self.t("install_py_none")
        if _looks_like_standalone_python_install(compat):
            return compat
        return compat + "\n" + self.t("install_py_not_standalone_note")

    def _tools_venv_readiness(self, is_available_fn):
        """Shared by _markitdown_readiness/_ytdlp_readiness (v0.12.3):
        'ok' plus 'ready'/'missing'/'broken' for a package living in the
        shared tools venv (markitdown and yt-dlp both do, so both are
        exactly as vulnerable to a stale base-Python reference).
        markitdown_python() already falls through to a bare system
        interpreter when the tools venv is broken, so is_available_fn
        correctly ends up False either way; the extra check below only
        distinguishes the message ('broken, will be rebuilt automatically
        on next Install' vs genuinely 'missing')."""
        self.python_exe = markitdown_python(self.cfg)
        ok = is_available_fn(self.python_exe)
        if ok:
            return ok, "ready"
        if (os.path.exists(tools_venv_python())
                and not venv_python_launches(str(TOOLS_VENV_DIR))):
            return ok, "broken"
        return ok, "missing"

    def _markitdown_readiness(self):
        self.markitdown_ok, status = self._tools_venv_readiness(markitdown_is_available)
        return status

    def _ytdlp_readiness(self):
        self.ytdlp_ok, status = self._tools_venv_readiness(ytdlp_is_available)
        return status

    # ======================================================================
    # item 20 — LAN status page
    # ======================================================================
    def _lan_get_snapshot(self):
        """Called from the HTTP thread. Read-only; returns a shallow copy so
        the HTTP thread never shares mutable state with the Tk thread."""
        with self._lan_snapshot_lock:
            return dict(self._lan_snapshot)

    def _lan_get_html_page(self):
        """Called from the HTTP thread. The page string is built once per
        server start (on the Tk thread, in _lan_start_server) and cached."""
        return getattr(self, "_lan_html_page", "<html><body>starting…</body></html>")

    def _lan_queue_counts(self, items):
        counts = {"pending": 0, "running": 0, "done": 0, "error": 0}
        for it in items:
            if it.status == ST_PENDING:
                counts["pending"] += 1
            elif it.status == ST_RUNNING:
                counts["running"] += 1
            elif it.status == ST_DONE:
                counts["done"] += 1
            elif it.status in (ST_ERROR,):
                counts["error"] += 1
            # ST_SKIPPED / ST_MEMBERS_ONLY intentionally fold into neither
            # bucket here; the full per-tab summary label already covers them.
        return counts

    def _lan_current_item(self):
        """Best-effort: the first RUNNING item found across all four queues,
        with whatever progress percentage that tab's progress bar shows."""
        pairs = [
            (self.queue_items, getattr(self, "trans_progress", None)),
            (self.md_queue_items, getattr(self, "md_progress", None)),
            (self.youtube_queue_items, getattr(self, "grab_progress", None)),
            (self.download_queue_items, getattr(self, "dl_progress", None)),
        ]
        for items, bar in pairs:
            for it in items:
                if it.status == ST_RUNNING:
                    pct = None
                    try:
                        if bar is not None:
                            pct = round(float(bar.cget("value")), 1)
                    except (tk.TclError, ValueError, TypeError):
                        pct = None
                    return {"name": it.filename or it.filepath, "progress_pct": pct}
        return None

    def _lan_build_snapshot(self):
        """Tk-main-thread only. Builds the plain dict later served as JSON."""
        return {
            "app_version": APP_VERSION,
            "hostname": socket.gethostname(),
            "uptime_seconds": int(time.time() - self._start_time),
            "tabs": {
                "av": self._lan_queue_counts(self.queue_items),
                "md": self._lan_queue_counts(self.md_queue_items),
                "yt": self._lan_queue_counts(self.youtube_queue_items),
                "dl": self._lan_queue_counts(self.download_queue_items),
            },
            "current_item": self._lan_current_item(),
            "tools": {
                "whisper": bool(self.whisper_path),
                "markitdown": bool(self.markitdown_ok),
                "ytdlp": bool(self.ytdlp_ok),
                "ffmpeg": bool(self.ffmpeg_path),
            },
            "log_tail": list(self._lan_log_tail),
        }

    def _lan_refresh_snapshot_loop(self):
        try:
            snap = self._lan_build_snapshot()
            with self._lan_snapshot_lock:
                self._lan_snapshot = snap
        except Exception:
            pass
        self.after(1000, self._lan_refresh_snapshot_loop)

    def _lan_start_server(self):
        """Returns (ok, error_or_None). Never raises, never crashes the app
        (20.2) — a bind/port failure just leaves the feature disabled with a
        clear error message for the caller to display."""
        self._lan_html_page = build_lan_status_html(self.lang, socket.gethostname(), APP_VERSION)
        host = self.cfg.get("lan_status_bind") or "0.0.0.0"
        port = int(self.cfg.get("lan_status_port") or 8080)
        token = (self.cfg.get("lan_status_token") or "") \
            if self.cfg.get("lan_status_token_enabled") else None
        ok, err = self._lan_server.start(host, port, token=token)
        return ok, err

    def _lan_stop_server(self):
        self._lan_server.stop()

    def _lan_reachable_url(self):
        port = self._lan_server.port or self.cfg.get("lan_status_port") or 8080
        url = f"http://{get_lan_ip()}:{port}"
        if self.cfg.get("lan_status_token_enabled") and self.cfg.get("lan_status_token"):
            url += f"?k={self.cfg['lan_status_token']}"
        return url

    # ======================================================================
    # item 7 (v0.11.0) — queue persistence across app restarts
    # ======================================================================
    def _restore_queues_state(self):
        state = load_queues_state(QUEUES_STATE_FILE)
        if not state:
            return
        if state.get("av"):
            self.queue_items = state["av"]
            self._render_queue()
            self._update_trans_summary()
        if state.get("md"):
            self.md_queue_items = state["md"]
            self._render_md_queue()
            self._update_md_summary()
        if state.get("yt"):
            self.youtube_queue_items = state["yt"]
            self._render_youtube_queue()
            self._update_youtube_summary()
            if any(it.status in ST_TERMINAL for it in self.youtube_queue_items):
                self._finished["yt"] = True
        if state.get("dl"):
            self.download_queue_items = state["dl"]
            self._render_download_queue()
            self._update_download_summary()
            if any(it.status in ST_TERMINAL for it in self.download_queue_items):
                self._finished["dl"] = True
        if any(it.status in ST_TERMINAL for it in self.queue_items):
            self._finished["av"] = True
        if any(it.status in ST_TERMINAL for it in self.md_queue_items):
            self._finished["md"] = True

    def _save_queues_state(self):
        try:
            save_queues_state(QUEUES_STATE_FILE, {
                "av": self.queue_items,
                "md": self.md_queue_items,
                "yt": self.youtube_queue_items,
                "dl": self.download_queue_items,
            })
        except OSError:
            pass

    # ======================================================================
    # Item 1.2/1.5 — one-time offer to migrate legacy global tool installs
    # and legacy Whisper models into the portable tools/ folder. Shown once
    # per run at most, and only when something legacy is actually detected;
    # never touches anything without the user clicking Yes.
    # ======================================================================
    def _maybe_offer_legacy_migration(self):
        if self.cfg.get("_migration_offered_v011"):
            return
        self.cfg["_migration_offered_v011"] = True
        self._save_config()
        legacy_models = migrate_legacy_whisper_models()
        legacy_global_whisper = (not find_managed_whisper()
                                 and find_global_whisper(find_python_executable()))
        legacy_global_md = (not os.path.exists(tools_venv_python())
                            and markitdown_is_available(find_python_executable()))
        if not (legacy_models or legacy_global_whisper or legacy_global_md):
            return
        lines = []
        if legacy_global_whisper:
            lines.append(self.t("migrate_item_whisper"))
        if legacy_global_md:
            lines.append(self.t("migrate_item_markitdown"))
        if legacy_models:
            lines.append(self.t("migrate_item_models", n=len(legacy_models)))
        if not messagebox.askyesno(
                self.t("migrate_title"),
                self.t("migrate_intro") + "\n\n" + "\n".join(f"• {ln}" for ln in lines),
                parent=self):
            return
        if legacy_models:
            for cli in legacy_models:
                copy_legacy_whisper_model(cli)
        if legacy_global_md:
            # One-click reinstall (item 1.2): pip install MarkItDown and
            # yt-dlp into the shared portable venv right now.
            # v0.13.5: MARKITDOWN_INSTALL_SPEC (not "markitdown[all]") +
            # youtube-transcript-api installed separately — see that
            # constant's comment for why plain "[all]" breaks on 3.14+.
            vpy, err = ensure_tools_venv()
            if vpy:
                for pkg in (MARKITDOWN_INSTALL_SPEC, "yt-dlp", "youtube-transcript-api"):
                    subprocess.run(build_pip_install_command(vpy, pkg),
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                   **subprocess_hidden_window_kwargs())
                self.cfg["markitdown_python"] = vpy
                self._save_config()
        if legacy_global_whisper:
            messagebox.showinfo(self.t("migrate_title"), self.t("migrate_whisper_hint"), parent=self)
            self._open_whisper_settings()
        self._detect_dependencies()
        self._refresh_status_indicators()

    def _set_icon(self):
        import base64
        try:
            self._icon_img_small = tk.PhotoImage(data=base64.b64decode(APP_ICON_SMALL_BASE64))
            self.iconphoto(True, self._icon_img_small)
        except Exception:
            self._icon_img_small = None
        # On Windows the title bar / taskbar want a real multi-size .ico, or the
        # PhotoImage gets clipped/rescaled. Materialize the embedded .ico once.
        try:
            ico_path = os.path.join(CONFIG_DIR, "app_icon.ico")
            if not os.path.exists(ico_path):
                ensure_config_dir()
                with open(ico_path, "wb") as f:
                    f.write(base64.b64decode(APP_ICON_ICO_BASE64))
            self.iconbitmap(default=ico_path)
        except Exception:
            pass
        try:
            self._icon_img_large = tk.PhotoImage(data=base64.b64decode(APP_ICON_LARGE_BASE64))
        except Exception:
            self._icon_img_large = None

    # ---- audio language display/param -----------------------------------
    def _audio_lang_display(self, code):
        if code == "auto":
            return self.t("audlang_auto")
        if code == "pt":
            return self.t("audlang_portuguese")
        if code == "en":
            return self.t("audlang_english")
        if code == "es":
            return self.t("audlang_spanish")
        name = WHISPER_LANGUAGES.get(code, code)
        return f"{name} ({code})"

    def _model_lang_label(self, cli):
        return self.t("model_lang_en") if str(cli).endswith(".en") else self.t("model_lang_multi")

    def _model_display(self, cli):
        info = MODEL_INFO[cli]
        return f"{cli}  —  {self._model_lang_label(cli)}  —  {self.t(info['desc_key'])}"

    # ======================================================================
    # Menubar
    # ======================================================================
    def _build_menubar(self):
        menubar = tk.Menu(self)
        settings_menu = tk.Menu(menubar, tearoff=0)
        settings_menu.add_command(label=self.t("menu_whisper"),
                                  command=self._open_whisper_settings)
        settings_menu.add_command(label=self.t("menu_markitdown"),
                                  command=self._open_conversion_tool_settings)
        settings_menu.add_command(label=self.t("menu_ytdlp"),
                                  command=self._open_ytdlp_settings)
        settings_menu.add_command(label=self.t("menu_ffmpeg"),
                                  command=self._open_ffmpeg_settings)
        settings_menu.add_command(label=self.t("menu_check_all_updates"),
                                  command=self._open_check_all_updates)
        settings_menu.add_command(label=self.t("menu_output_formats"),
                                  command=self._open_output_formats)
        settings_menu.add_command(label=self.t("menu_general"),
                                  command=self._open_general_settings)
        settings_menu.add_command(label=self.t("menu_lan_status"),
                                  command=self._open_lan_status_settings)
        settings_menu.add_separator()
        lang_menu = tk.Menu(settings_menu, tearoff=0)
        self._menu_lang_var = tk.StringVar(value=self.lang)
        lang_menu.add_radiobutton(label=self.t("lang_english"), value="en",
                                  variable=self._menu_lang_var,
                                  command=lambda: self._switch_language("en"))
        lang_menu.add_radiobutton(label=self.t("lang_portuguese"), value="pt",
                                  variable=self._menu_lang_var,
                                  command=lambda: self._switch_language("pt"))
        settings_menu.add_cascade(label=self.t("menu_interface_language"),
                                  menu=lang_menu)
        menubar.add_cascade(label=self.t("menu_settings"), menu=settings_menu)
        menubar.add_command(label=self.t("menu_about"), command=self._open_about)
        self.config(menu=menubar)

    # ======================================================================
    # UI build
    # ======================================================================
    def _build_ui(self):
        if hasattr(self, "notebook") and self.notebook.winfo_exists():
            self.notebook.destroy()
        if hasattr(self, "_header_bar") and self._header_bar.winfo_exists():
            self._header_bar.destroy()
        self._style_notebook_tabs()
        self._wrap_labels = []

        self._header_bar = ttk.Frame(self)
        self._header_bar.pack(fill="x", padx=10, pady=(8, 0))
        if getattr(self, "_icon_img_small", None) is not None:
            ttk.Label(self._header_bar, image=self._icon_img_small).pack(side="left", padx=(0, 6))
        # Auto-updates with APP_VERSION (bump APP_VERSION -> header updates too).
        ttk.Label(self._header_bar, text=f"{APP_NAME} v.{APP_VERSION}",
                  font=("TkDefaultFont", 12, "bold")).pack(side="left")

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=8, pady=8)

        self.tab_main = ttk.Frame(self.notebook)
        self.tab_md = ttk.Frame(self.notebook)
        self.tab_youtube = ttk.Frame(self.notebook)
        self.tab_download = ttk.Frame(self.notebook)
        self.tab_dict = ttk.Frame(self.notebook)
        self.tab_grabber = ttk.Frame(self.notebook)
        self.tab_comparison = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_main, text=self.t("tab_transcription"))
        self.notebook.add(self.tab_md, text=self.t("tab_md"))
        self.notebook.add(self.tab_youtube, text=self.t("tab_youtube"))
        self.notebook.add(self.tab_download, text=self.t("tab_download"))
        self.notebook.add(self.tab_grabber, text=self.t("tab_grabber"))
        self.notebook.add(self.tab_dict, text=self.t("tab_dictionary"))
        self.notebook.add(self.tab_comparison, text=self.t("tab_comparison"))

        self._build_transcription_tab(self.tab_main)
        self._build_md_tab(self.tab_md)
        self._build_youtube_tab(self.tab_youtube)
        self._build_download_tab(self.tab_download)
        self._build_dictionary_tab(self.tab_dict)
        self._build_grabber_tab(self.tab_grabber)
        self._build_comparison_tab(self.tab_comparison)
        self._refresh_status_indicators()
        self._refresh_audio_lang_dropdown()
        self._refresh_model_dropdown()
        self._refresh_dictionary_dropdown()
        self._update_clip_gate()
        self._refresh_youtube_enabled()
        self._refresh_download_enabled()
        self._update_trans_summary()
        self._update_md_summary()
        self._update_youtube_summary()
        self._update_download_summary()

    def _register_wrap(self, label):
        self._wrap_labels.append(label)

    def _style_notebook_tabs(self):
        """Make the active tab clearly stand out (bold + accent + tint + padding).
        On Windows native themes the background tint may be ignored, but the bold
        accent text still distinguishes the selected tab."""
        try:
            style = ttk.Style()
            base_font = tkfont.nametofont("TkDefaultFont")
            self._tab_font_normal = (base_font.actual("family"), base_font.actual("size"))
            self._tab_font_bold = (base_font.actual("family"),
                                   base_font.actual("size"), "bold")
            style.configure("TNotebook", tabmargins=(2, 5, 2, 0))
            style.configure("TNotebook.Tab", padding=(14, 7),
                            font=self._tab_font_normal)
            style.map(
                "TNotebook.Tab",
                background=[("selected", "#ffffff"), ("active", "#eef3fb"),
                            ("!selected", "#dde1e7")],
                foreground=[("selected", "#0a58ca"), ("!selected", "#444444")],
                font=[("selected", self._tab_font_bold),
                      ("!selected", self._tab_font_normal)],
                expand=[("selected", (1, 1, 1, 0))])
        except Exception:
            pass

    # ---- transcription tab ----------------------------------------------
    def _build_transcription_tab(self, parent):
        scroll = ScrollableFrame(parent)
        scroll.pack(fill="both", expand=True)
        root = scroll.inner
        root.columnconfigure(0, weight=1)
        scroll.canvas.bind("<Configure>", self._on_main_canvas_configure, add="+")
        self._main_canvas = scroll.canvas
        r = 0

        # --- status indicators (row 1) ---
        status = ttk.LabelFrame(root, text="")
        status.grid(row=r, column=0, sticky="ew", padx=6, pady=(6, 2))
        status.columnconfigure(3, weight=1)
        self.ind_whisper = tk.Label(status, text="", cursor="hand2",
                                    font=("TkDefaultFont", 10, "bold"))
        self.ind_whisper.grid(row=0, column=0, padx=8, pady=6)
        self.ind_whisper.bind("<Button-1>", lambda e: self._open_whisper_settings())
        self.ind_markitdown = tk.Label(status, text="", cursor="hand2",
                                       font=("TkDefaultFont", 10, "bold"))
        self.ind_markitdown.grid(row=0, column=1, padx=8, pady=6)
        self.ind_markitdown.bind("<Double-Button-1>",
                                 lambda e: self._open_conversion_tool_settings())
        self.ind_ffmpeg = tk.Label(status, text="", cursor="hand2",
                                   font=("TkDefaultFont", 10, "bold"))
        self.ind_ffmpeg.grid(row=0, column=2, padx=8, pady=6)
        self.ind_ffmpeg.bind("<Button-1>", lambda e: self._open_ffmpeg_settings())
        self.ind_hint = ttk.Label(status, text=self.t("dep_hint"), foreground="#777")
        self.ind_hint.grid(row=0, column=3, sticky="e", padx=8)
        r += 1

        # --- audio language + model row ---
        cfgf = ttk.Frame(root)
        cfgf.grid(row=r, column=0, sticky="ew", padx=6, pady=2)
        cfgf.columnconfigure(1, weight=1)
        cfgf.columnconfigure(4, weight=1)
        ttk.Label(cfgf, text=self.t("audio_language")).grid(row=0, column=0, sticky="w", padx=(0, 4), pady=4)
        self.audio_lang_var = tk.StringVar()
        self.audio_lang_combo = ttk.Combobox(cfgf, textvariable=self.audio_lang_var,
                                              state="readonly", width=22)
        self.audio_lang_combo.grid(row=0, column=1, sticky="ew", pady=4)
        self.audio_lang_combo.bind("<<ComboboxSelected>>", self._on_audio_lang_change)
        ttk.Button(cfgf, text=self.t("add_languages"),
                   command=lambda: self._open_whisper_settings(focus="langs")
                   ).grid(row=0, column=2, sticky="w", padx=(6, 16), pady=4)

        ttk.Label(cfgf, text=self.t("ai_model")).grid(row=0, column=3, sticky="w", padx=(0, 4), pady=4)
        self.model_var = tk.StringVar()
        self.model_combo = ttk.Combobox(cfgf, textvariable=self.model_var,
                                        state="readonly", width=34)
        self.model_combo.grid(row=0, column=4, sticky="ew", pady=4)
        self.model_combo.bind("<<ComboboxSelected>>", self._on_model_change)
        ttk.Button(cfgf, text=self.t("add_model"),
                   command=lambda: self._open_whisper_settings(focus="models")
                   ).grid(row=0, column=5, sticky="w", padx=(6, 0), pady=4)

        # task row
        ttk.Label(cfgf, text=self.t("task")).grid(row=1, column=0, sticky="w", padx=(0, 4), pady=4)
        self.task_var = tk.StringVar()
        self.task_combo = ttk.Combobox(cfgf, textvariable=self.task_var,
                                       state="readonly", width=22)
        self.task_combo["values"] = [self.t("task_transcribe"), self.t("task_translate")]
        self.task_combo.current(0 if self.cfg.get("task", "transcribe") == "transcribe" else 1)
        self.task_combo.grid(row=1, column=1, sticky="ew", pady=4)
        self.task_combo.bind("<<ComboboxSelected>>", self._on_task_change)
        hdr = self._build_header_controls(cfgf)
        hdr.grid(row=1, column=3, columnspan=3, sticky="w", padx=(0, 0), pady=4)
        r += 1

        # model status label
        self.model_status_var = tk.StringVar(value="")
        msl = ttk.Label(root, textvariable=self.model_status_var, foreground="#555")
        msl.grid(row=r, column=0, sticky="w", padx=10, pady=(0, 4))
        self._register_wrap(msl)
        r += 1

        # vocabulary dictionary
        dictf = ttk.Frame(root)
        dictf.grid(row=r, column=0, sticky="ew", padx=6, pady=2)
        dictf.columnconfigure(1, weight=1)
        ttk.Label(dictf, text=self.t("vocab_dict")).grid(row=0, column=0, sticky="w", padx=(0, 4))
        self.dict_var = tk.StringVar()
        self.dict_combo = ttk.Combobox(dictf, textvariable=self.dict_var,
                                       state="readonly", width=34)
        self.dict_combo.grid(row=0, column=1, sticky="ew")
        r += 1

        # clip frame
        self.clip_frame = ttk.LabelFrame(root, text=self.t("clip_frame"))
        self.clip_frame.grid(row=r, column=0, sticky="ew", padx=6, pady=4)
        self.clip_frame.columnconfigure(5, weight=1)
        self.clip_enabled_var = tk.BooleanVar(value=False)
        self.clip_check = ttk.Checkbutton(self.clip_frame, text=self.t("clip_enable"),
                                          variable=self.clip_enabled_var,
                                          command=self._update_clip_gate)
        self.clip_check.grid(row=0, column=0, columnspan=6, sticky="w", padx=6, pady=(4, 0))
        ttk.Label(self.clip_frame, text=self.t("clip_start")).grid(row=1, column=0, sticky="w", padx=(6, 2), pady=4)
        self.clip_start_var = tk.StringVar(value="0:00:00")
        self.clip_start_entry = ttk.Entry(self.clip_frame, textvariable=self.clip_start_var, width=12)
        self.clip_start_entry.grid(row=1, column=1, sticky="w", pady=4)
        ttk.Label(self.clip_frame, text=self.t("clip_end")).grid(row=1, column=2, sticky="w", padx=(12, 2), pady=4)
        self.clip_end_var = tk.StringVar(value="0:05:00")
        self.clip_end_entry = ttk.Entry(self.clip_frame, textvariable=self.clip_end_var, width=12)
        self.clip_end_entry.grid(row=1, column=3, sticky="w", pady=4)
        self.clip_hint_label = ttk.Label(self.clip_frame, text=self.t("clip_hint"), foreground="#777")
        self.clip_hint_label.grid(row=2, column=0, columnspan=6, sticky="w", padx=6, pady=(0, 4))
        self._register_wrap(self.clip_hint_label)
        r += 1

        # output folder
        outf = ttk.LabelFrame(root, text=self.t("output_folder"))
        outf.grid(row=r, column=0, sticky="ew", padx=6, pady=4)
        outf.columnconfigure(1, weight=1)
        self.outdir_mode_var = tk.StringVar(value=self.cfg.get("output_dir_mode", "same"))
        ttk.Radiobutton(outf, text=self.t("same_folder"), variable=self.outdir_mode_var,
                        value="same", command=self._on_outdir_mode_change
                        ).grid(row=0, column=0, columnspan=3, sticky="w", padx=6, pady=(4, 0))
        ttk.Radiobutton(outf, text=self.t("fixed_folder"), variable=self.outdir_mode_var,
                        value="fixed", command=self._on_outdir_mode_change
                        ).grid(row=1, column=0, sticky="w", padx=6, pady=4)
        self.fixed_dir_var = tk.StringVar(value=self.cfg.get("fixed_output_dir", ""))
        self.fixed_dir_entry = ttk.Entry(outf, textvariable=self.fixed_dir_var)
        self.fixed_dir_entry.grid(row=1, column=1, sticky="ew", pady=4)
        ttk.Button(outf, text=self.t("browse"),
                   command=self._browse_fixed_dir).grid(row=1, column=2, padx=6, pady=4)
        r += 1

        # queue
        qf = ttk.LabelFrame(root, text=self.t("queue_frame"))
        qf.grid(row=r, column=0, sticky="ew", padx=6, pady=4)
        qf.columnconfigure(0, weight=1)
        btns = ttk.Frame(qf)
        btns.grid(row=0, column=0, sticky="ew", padx=4, pady=4)
        ttk.Button(btns, text=self.t("add_files"), command=self._add_files).pack(side="left", padx=2)
        ttk.Button(btns, text=self.t("remove_selected"), command=self._remove_selected).pack(side="left", padx=2)
        self.clear_queue_btn = ttk.Button(btns, text=self.t("clear_queue"), command=self._clear_queue)
        self.clear_queue_btn.pack(side="left", padx=2)
        ttk.Button(btns, text=self.t("move_up"), command=lambda: self._move_selected(-1)).pack(side="left", padx=2)
        ttk.Button(btns, text=self.t("move_down"), command=lambda: self._move_selected(1)).pack(side="left", padx=2)
        cols = ("order", "file", "folder", "length", "status")
        qwrap, self.tree, _qsb = make_scrollable_queue(qf, cols, height=8)
        qwrap.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)
        qf.rowconfigure(1, weight=1)
        bind_queue_delete_key(self.tree, self._remove_selected)
        self.tree.heading("order", text=self.t("col_order"))
        self.tree.heading("file", text=self.t("col_file"))
        self.tree.heading("folder", text=self.t("col_folder"))
        self.tree.heading("length", text=self.t("col_length"))
        self.tree.heading("status", text=self.t("col_status"))
        self.tree.column("order", width=40, anchor="center", stretch=False)
        self.tree.column("file", width=300)
        self.tree.column("folder", width=230)
        self.tree.column("length", width=90, anchor="center", stretch=False)
        self.tree.column("status", width=120, anchor="center")
        bind_header_sort(
            self.tree,
            {"file": (self.t("col_file"), lambda it: (it.filename or "").lower()),
             "length": (self.t("col_length"),
                        lambda it: it.duration if (it.duration and it.duration > 0) else None)},
            get_items=lambda: self.queue_items,
            is_running=lambda: self.is_running,
            render_fn=self._render_queue)
        self.trans_summary_var = tk.StringVar(value="")
        tsum = ttk.Label(qf, textvariable=self.trans_summary_var, foreground="#444")
        tsum.grid(row=2, column=0, sticky="w", padx=6, pady=(0, 4))
        self._register_wrap(tsum)
        r += 1

        # run controls
        runf = ttk.Frame(root)
        runf.grid(row=r, column=0, sticky="ew", padx=6, pady=4)
        runf.columnconfigure(2, weight=1)
        self.start_btn = ttk.Button(runf, text=self.t("start_batch"), command=self._start_batch)
        self.start_btn.grid(row=0, column=0, padx=2)
        self.cancel_btn = ttk.Button(runf, text=self.t("cancel"), command=self._cancel_batch, state="disabled")
        self.cancel_btn.grid(row=0, column=1, padx=2)
        self.open_out_btn = ttk.Button(runf, text=self.t("open_output_folder"),
                                       command=self._open_output_folder, state="disabled")
        self.open_out_btn.grid(row=0, column=3, padx=2, sticky="e")
        self.progress = TwoToneProgress(runf, height=22)
        self.progress.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(6, 0))
        self.progress_pct_var = tk.StringVar(value="")
        self.progress_label_var = tk.StringVar(value=self.t("waiting_start"))
        pll = ttk.Label(runf, textvariable=self.progress_label_var, foreground="#555")
        pll.grid(row=2, column=0, columnspan=4, sticky="w", pady=(2, 0))
        self._register_wrap(pll)
        r += 1

        # log
        logf = ttk.LabelFrame(root, text=self.t("log_frame"))
        logf.grid(row=r, column=0, sticky="nsew", padx=6, pady=4)
        logf.columnconfigure(0, weight=1)
        self.log_text = tk.Text(logf, height=8, wrap="word", state="disabled",
                                font=("TkFixedFont", 9))
        logsb = ttk.Scrollbar(logf, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=logsb.set)
        self.log_text.grid(row=0, column=0, sticky="nsew", padx=(4, 0), pady=4)
        logsb.grid(row=0, column=1, sticky="ns", pady=4)
        self.log_frame_label = logf
        note = ttk.Label(logf, text=self.t("partial_output_note"), foreground="#777")
        note.grid(row=1, column=0, columnspan=2, sticky="w", padx=4, pady=(0, 4))
        self._register_wrap(note)

    def _on_main_canvas_configure(self, event):
        width = max(200, event.width - 40)
        for lbl in self._wrap_labels:
            try:
                lbl.configure(wraplength=width)
            except tk.TclError:
                pass

    # ---- MD File Generation tab -----------------------------------------
    def _build_md_tab(self, parent):
        scroll = ScrollableFrame(parent)
        scroll.pack(fill="both", expand=True)
        root = scroll.inner
        root.columnconfigure(0, weight=1)
        root.rowconfigure(4, weight=1)   # queue expands; log is capped

        intro = ttk.Label(root, text=self.t("md_intro"), foreground="#555")
        intro.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 2))
        intro.configure(wraplength=900)
        self._md_intro_label = intro

        # v0.13.8: active conversion model, click to change (installed
        # models only -- installing a new one still goes through
        # Settings -> MD Conversion Tool).
        self.md_model_line_var = tk.StringVar(value="")
        self.md_model_line_lbl = ttk.Label(root, textvariable=self.md_model_line_var,
                                           cursor="hand2", font=("TkDefaultFont", 9, "underline"))
        self.md_model_line_lbl.grid(row=1, column=0, sticky="w", padx=8, pady=(0, 4))
        self.md_model_line_lbl.bind("<Button-1>", lambda e: self._open_md_model_chooser())
        self._refresh_md_model_line()

        # output folder
        outf = ttk.LabelFrame(root, text=self.t("output_folder"))
        outf.grid(row=2, column=0, sticky="ew", padx=8, pady=4)
        outf.columnconfigure(1, weight=1)
        self.md_outdir_mode_var = tk.StringVar(value="same")
        ttk.Radiobutton(outf, text=self.t("same_folder"), variable=self.md_outdir_mode_var,
                        value="same").grid(row=0, column=0, columnspan=3, sticky="w", padx=6, pady=(4, 0))
        ttk.Radiobutton(outf, text=self.t("fixed_folder"), variable=self.md_outdir_mode_var,
                        value="fixed").grid(row=1, column=0, sticky="w", padx=6, pady=4)
        self.md_fixed_dir_var = tk.StringVar(value="")
        ttk.Entry(outf, textvariable=self.md_fixed_dir_var).grid(row=1, column=1, sticky="ew", pady=4)
        ttk.Button(outf, text=self.t("browse"),
                   command=self._browse_md_fixed_dir).grid(row=1, column=2, padx=6, pady=4)

        hdr = self._build_header_controls(root, with_polish_hint=True)
        hdr.grid(row=3, column=0, sticky="ew", padx=12, pady=(2, 4))

        # queue (prominent, scrollable)
        qf = ttk.LabelFrame(root, text=self.t("md_queue_frame"))
        qf.grid(row=4, column=0, sticky="nsew", padx=8, pady=4)
        qf.columnconfigure(0, weight=1)
        qf.rowconfigure(1, weight=1)
        btns = ttk.Frame(qf)
        btns.grid(row=0, column=0, sticky="ew", padx=4, pady=4)
        ttk.Button(btns, text=self.t("add_files"), command=self._md_add_files).pack(side="left", padx=2)
        ttk.Button(btns, text=self.t("remove_selected"), command=self._md_remove_selected).pack(side="left", padx=2)
        ttk.Button(btns, text=self.t("clear_queue"), command=self._md_clear_queue).pack(side="left", padx=2)
        cols = ("order", "file", "folder", "size", "status")
        qwrap, self.md_tree, _msb = make_scrollable_queue(qf, cols, height=18)
        qwrap.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)
        bind_queue_delete_key(self.md_tree, self._md_remove_selected)
        self.md_tree.heading("order", text=self.t("col_order"))
        self.md_tree.heading("file", text=self.t("col_file"))
        self.md_tree.heading("folder", text=self.t("col_folder"))
        self.md_tree.heading("size", text=self.t("md_col_size"))
        self.md_tree.heading("status", text=self.t("col_status"))
        self.md_tree.column("order", width=40, anchor="center", stretch=False)
        self.md_tree.column("file", width=300)
        self.md_tree.column("folder", width=230)
        self.md_tree.column("size", width=90, anchor="center", stretch=False)
        self.md_tree.column("status", width=120, anchor="center")
        bind_header_sort(
            self.md_tree,
            {"file": (self.t("col_file"), lambda it: (it.filename or "").lower()),
             "size": (self.t("md_col_size"),
                      lambda it: it.size_bytes if it.size_bytes else None)},
            get_items=lambda: self.md_queue_items,
            is_running=lambda: self.md_is_running,
            render_fn=self._render_md_queue)
        self.md_summary_var = tk.StringVar(value="")
        ttk.Label(qf, textvariable=self.md_summary_var, foreground="#444"
                  ).grid(row=2, column=0, sticky="w", padx=6, pady=(0, 4))

        # run controls
        runf = ttk.Frame(root)
        runf.grid(row=5, column=0, sticky="ew", padx=8, pady=4)
        runf.columnconfigure(2, weight=1)
        self.md_start_btn = ttk.Button(runf, text=self.t("start_batch_md"), command=self._start_md_batch)
        self.md_start_btn.grid(row=0, column=0, padx=2)
        self.md_cancel_btn = ttk.Button(runf, text=self.t("cancel"), command=self._cancel_md_batch, state="disabled")
        self.md_cancel_btn.grid(row=0, column=1, padx=2)
        self.md_open_out_btn = ttk.Button(runf, text=self.t("open_output_folder"),
                                          command=self._md_open_output_folder, state="disabled")
        self.md_open_out_btn.grid(row=0, column=3, padx=2, sticky="e")
        self.md_progress = TwoToneProgress(runf, height=22)
        self.md_progress.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(6, 0))
        self.md_progress_pct_var = tk.StringVar(value="")
        self.md_progress_label_var = tk.StringVar(value=self.t("waiting_start"))
        ttk.Label(runf, textvariable=self.md_progress_label_var, foreground="#555"
                  ).grid(row=2, column=0, columnspan=4, sticky="w", pady=(2, 0))

        # log (secondary, capped)
        logf = ttk.LabelFrame(root, text=self.t("log_frame_md"))
        logf.grid(row=6, column=0, sticky="ew", padx=8, pady=4)
        logf.columnconfigure(0, weight=1)
        self.md_log_text = tk.Text(logf, height=8, wrap="word", state="disabled",
                                   font=("TkFixedFont", 9))
        logsb = ttk.Scrollbar(logf, orient="vertical", command=self.md_log_text.yview)
        self.md_log_text.configure(yscrollcommand=logsb.set)
        self.md_log_text.grid(row=0, column=0, sticky="nsew", padx=(4, 0), pady=4)
        logsb.grid(row=0, column=1, sticky="ns", pady=4)

    # ---- YouTube Transcription tab --------------------------------------
    def _build_youtube_tab(self, parent):
        scroll = ScrollableFrame(parent)
        scroll.pack(fill="both", expand=True)
        root = scroll.inner
        root.columnconfigure(0, weight=1)
        root.rowconfigure(6, weight=1)   # queue row expands; log is capped
        self._yt_controls = []

        # status indicators (MarkItDown + yt-dlp), clickable
        status = ttk.LabelFrame(root, text="")
        status.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 2))
        status.columnconfigure(2, weight=1)
        self.yt_ind_markitdown = tk.Label(status, text="", cursor="hand2",
                                          font=("TkDefaultFont", 10, "bold"))
        self.yt_ind_markitdown.grid(row=0, column=0, padx=8, pady=6)
        self.yt_ind_markitdown.bind("<Double-Button-1>",
                                    lambda e: self._open_conversion_tool_settings())
        self.yt_ind_ytdlp = tk.Label(status, text="", cursor="hand2",
                                     font=("TkDefaultFont", 10, "bold"))
        self.yt_ind_ytdlp.grid(row=0, column=1, padx=8, pady=6)
        self.yt_ind_ytdlp.bind("<Button-1>", lambda e: self._open_ytdlp_settings())
        ttk.Label(status, text=self.t("dep_hint"), foreground="#777"
                  ).grid(row=0, column=2, sticky="e", padx=8)

        intro = ttk.Label(root, text=self.t("yt_intro"), foreground="#555")
        intro.grid(row=1, column=0, sticky="ew", padx=10, pady=(2, 0))
        intro.configure(wraplength=900)
        self.yt_required_note = ttk.Label(root, text=self.t("yt_md_required_note"),
                                          foreground="#cf222e")
        self.yt_required_note.grid(row=2, column=0, sticky="w", padx=10, pady=(2, 0))
        self.yt_required_note.configure(wraplength=900)

        body = ttk.Frame(root)
        body.grid(row=3, column=0, sticky="ew", padx=8, pady=2)
        body.columnconfigure(0, weight=1)
        langrow = ttk.Frame(body)
        langrow.grid(row=0, column=0, sticky="ew", pady=2)
        ttk.Label(langrow, text=self.t("yt_pref_lang")).pack(side="left")
        self.yt_lang_var = tk.StringVar()
        self.yt_lang_combo = ttk.Combobox(langrow, textvariable=self.yt_lang_var,
                                          state="readonly", width=28)
        self.yt_lang_combo.pack(side="left", padx=6)
        self.yt_lang_combo.bind("<<ComboboxSelected>>", self._on_yt_lang_change)
        self._yt_controls.append(self.yt_lang_combo)

        # Fixed output folder (above the queue, matching the other tabs)
        of = ttk.LabelFrame(root, text=self.t("fixed_folder"))
        of.grid(row=4, column=0, sticky="ew", padx=8, pady=4)
        of.columnconfigure(0, weight=1)
        self.yt_outdir_var = tk.StringVar(value=self.cfg.get("youtube_output_dir") or str(Path.home()))
        yt_entry = ttk.Entry(of, textvariable=self.yt_outdir_var)
        yt_entry.grid(row=0, column=0, sticky="ew", padx=6, pady=6)
        yt_browse = ttk.Button(of, text=self.t("browse"), command=self._yt_browse_outdir)
        yt_browse.grid(row=0, column=1, padx=6, pady=6)
        self._yt_controls += [yt_entry, yt_browse]

        hdr = self._build_header_controls(root)
        hdr.grid(row=5, column=0, sticky="w", padx=12, pady=(2, 2))

        qf = ttk.LabelFrame(root, text=self.t("yt_queue_frame"))
        qf.grid(row=6, column=0, sticky="nsew", padx=8, pady=4)
        qf.columnconfigure(0, weight=1)
        qf.rowconfigure(1, weight=1)
        qbtns = ttk.Frame(qf)
        qbtns.grid(row=0, column=0, sticky="ew", padx=4, pady=4)
        b_add = ttk.Button(qbtns, text=self.t("btn_add"),
                           command=lambda: self._open_add_links_dialog("youtube"))
        b_add.pack(side="left", padx=2)
        b_rm = ttk.Button(qbtns, text=self.t("remove_selected"), command=self._yt_remove_selected)
        b_rm.pack(side="left", padx=2)
        b_cl = ttk.Button(qbtns, text=self.t("clear_queue"), command=self._yt_clear_queue)
        b_cl.pack(side="left", padx=2)
        b_up = ttk.Button(qbtns, text=self.t("move_up"),
                          command=lambda: self._yt_move_selected(-1))
        b_up.pack(side="left", padx=2)
        b_dn = ttk.Button(qbtns, text=self.t("move_down"),
                          command=lambda: self._yt_move_selected(1))
        b_dn.pack(side="left", padx=2)
        self._yt_controls += [b_add, b_rm, b_cl, b_up, b_dn]
        cols = ("order", "video", "length", "status")
        qwrap, self.yt_tree, _ysb2 = make_scrollable_queue(qf, cols, height=14)
        qwrap.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)
        bind_queue_delete_key(self.yt_tree, self._yt_remove_selected)
        self.yt_tree._copy_link_label = self.t("copy_link")
        bind_queue_copy_link(self.yt_tree, self._yt_link_for_iid)
        self.yt_tree.heading("order", text=self.t("col_order"))
        self.yt_tree.heading("video", text=self.t("yt_col_video"))
        self.yt_tree.heading("length", text=self.t("col_length"))
        self.yt_tree.heading("status", text=self.t("col_status"))
        self.yt_tree.column("order", width=40, anchor="center", stretch=False)
        self.yt_tree.column("video", width=460)
        self.yt_tree.column("length", width=90, anchor="center", stretch=False)
        self.yt_tree.column("status", width=160, anchor="center")
        self.yt_tree.tag_configure("members_only", foreground="#cf222e")  # item 12
        bind_header_sort(
            self.yt_tree,
            {"video": (self.t("yt_col_video"),
                      lambda it: (it.filename or it.title or "").lower()),
             "length": (self.t("col_length"),
                        lambda it: it.duration if (it.duration and it.duration > 0) else None)},
            get_items=lambda: self.youtube_queue_items,
            is_running=lambda: self.youtube_is_running,
            render_fn=self._render_youtube_queue)
        self.yt_summary_var = tk.StringVar(value="")
        ttk.Label(qf, textvariable=self.yt_summary_var, foreground="#444"
                  ).grid(row=2, column=0, sticky="w", padx=6, pady=(0, 4))

        opt = ttk.Frame(root)
        opt.grid(row=7, column=0, sticky="ew", padx=10, pady=2)
        self.yt_srt_var = tk.BooleanVar(value=self.cfg.get("youtube_keep_srt", True))
        self.yt_txt_var = tk.BooleanVar(value=self.cfg.get("youtube_keep_txt", True))
        c_srt = ttk.Checkbutton(opt, text=self.t("yt_keep_srt"), variable=self.yt_srt_var,
                                command=self._on_yt_opts_change)
        c_srt.grid(row=0, column=0, sticky="w", padx=(0, 16))
        c_txt = ttk.Checkbutton(opt, text=self.t("yt_keep_txt"), variable=self.yt_txt_var,
                                command=self._on_yt_opts_change)
        c_txt.grid(row=0, column=1, sticky="w")
        self._yt_controls += [c_srt, c_txt]

        info = ttk.Label(root, text=self.t("yt_output_info") + "  " + self.t("yt_settings_note"),
                         foreground="#555")
        info.grid(row=8, column=0, sticky="w", padx=10, pady=(2, 2))
        info.configure(wraplength=900)

        self._build_pause_box(root, "yt").grid(row=9, column=0, sticky="ew", padx=8, pady=2)

        rf = ttk.Frame(root)
        rf.grid(row=10, column=0, sticky="ew", padx=8, pady=4)
        rf.columnconfigure(2, weight=1)
        self.yt_start_btn = ttk.Button(rf, text=self.t("yt_start"), command=self._start_youtube_batch)
        self.yt_start_btn.grid(row=0, column=0, padx=2)
        self.yt_cancel_btn = ttk.Button(rf, text=self.t("cancel"), command=self._cancel_youtube_batch,
                                        state="disabled")
        self.yt_cancel_btn.grid(row=0, column=1, padx=2)
        self.yt_open_btn = ttk.Button(rf, text=self.t("open_output_folder"),
                                      command=self._yt_open_output, state="disabled")
        self.yt_open_btn.grid(row=0, column=3, padx=2, sticky="e")
        self._yt_controls.append(self.yt_start_btn)
        self.yt_progress = TwoToneProgress(rf, height=22)
        self.yt_progress.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(6, 0))
        self.yt_progress_pct_var = tk.StringVar(value="")
        self.yt_progress_label_var = tk.StringVar(value=self.t("waiting_start"))
        ttk.Label(rf, textvariable=self.yt_progress_label_var, foreground="#555"
                  ).grid(row=2, column=0, columnspan=4, sticky="w", pady=(2, 0))

        lf = ttk.LabelFrame(root, text=self.t("yt_log_frame"))
        lf.grid(row=11, column=0, sticky="ew", padx=8, pady=4)
        lf.columnconfigure(0, weight=1)
        self.yt_log_text = tk.Text(lf, height=8, wrap="word", state="disabled",
                                   font=("TkFixedFont", 9))
        ysb = ttk.Scrollbar(lf, orient="vertical", command=self.yt_log_text.yview)
        self.yt_log_text.configure(yscrollcommand=ysb.set)
        self.yt_log_text.grid(row=0, column=0, sticky="nsew", padx=(4, 0), pady=4)
        ysb.grid(row=0, column=1, sticky="ns", pady=4)

        self._refresh_youtube_lang_dropdown()
        self._render_youtube_queue()

    def _refresh_youtube_lang_dropdown(self):
        codes = ["auto"] + [c for c in self.cfg.get("audio_langs", []) if c != "auto"]
        # dedupe preserving order
        seen = set()
        codes = [c for c in codes if not (c in seen or seen.add(c))]
        displays = []
        self._yt_code_by_display = {}
        for c in codes:
            disp = self.t("yt_lang_auto") if c == "auto" else self._audio_lang_display(c)
            displays.append(disp)
            self._yt_code_by_display[disp] = c
        self.yt_lang_combo["values"] = displays
        cur = self.cfg.get("youtube_pref_lang", "auto")
        if cur not in codes:
            cur = "auto"
            self.cfg["youtube_pref_lang"] = cur
        disp = self.t("yt_lang_auto") if cur == "auto" else self._audio_lang_display(cur)
        self.yt_lang_var.set(disp)

    def _on_yt_lang_change(self, _event=None):
        code = getattr(self, "_yt_code_by_display", {}).get(self.yt_lang_var.get(), "auto")
        self.cfg["youtube_pref_lang"] = code
        self._save_config()

    def _on_yt_opts_change(self):
        self.cfg["youtube_keep_srt"] = self.yt_srt_var.get()
        self.cfg["youtube_keep_txt"] = self.yt_txt_var.get()
        self._save_config()

    def _yt_browse_outdir(self):
        d = filedialog.askdirectory(
            title=self.t("select_output_title"),
            initialdir=self._existing_dir_or_home(self.yt_outdir_var.get()))
        if d:
            self.yt_outdir_var.set(d)
            self.cfg["youtube_output_dir"] = d
            self._save_config()

    def _refresh_youtube_enabled(self):
        """Grey out the whole tab when the shared venv (youtube-transcript
        -api specifically) is missing -- this is about whether a
        transcript can be FETCHED at all, which is unrelated to which
        document-conversion model is selected (that's yt_ind_markitdown's
        text, now owned by _refresh_status_indicators so the two don't
        fight over the same label)."""
        if not hasattr(self, "yt_ind_markitdown"):
            return
        ok = bool(self.markitdown_ok)
        if hasattr(self, "yt_ind_ytdlp"):
            yok = bool(getattr(self, "ytdlp_ok", False))
            ymark = self.t("dep_found") if yok else self.t("dep_missing")
            self.yt_ind_ytdlp.configure(text=f"{self.t('dep_ytdlp')} {ymark}",
                                        fg=("#1a7f37" if yok else "#cf222e"))
        for w in self._yt_controls:
            try:
                if isinstance(w, ttk.Combobox):
                    w.configure(state="readonly" if ok else "disabled")
                else:
                    w.configure(state="normal" if ok else "disabled")
            except tk.TclError:
                pass
        # cancel/open buttons follow run state, not gating
        try:
            self.yt_required_note.grid() if not ok else self.yt_required_note.grid_remove()
        except tk.TclError:
            pass

    # --- YouTube queue ops ---
    def _open_add_links_dialog(self, target):
        # Per item 1, only the YouTube Transcription tab keeps the queue
        # locked during processing; the Download tab allows live editing.
        if target == "youtube" and self.youtube_is_running:
            messagebox.showwarning(self.t("warn"), self.t("warn_queue_locked"))
            return
        if target == "youtube":
            proceed = self._gate_finished_queue(
                "yt", bool(self.youtube_queue_items), self._yt_clear_queue,
                keep_fn=lambda: (self._reset_errored_to_pending(self.youtube_queue_items),
                                 self._render_youtube_queue()))
        else:
            proceed = self._gate_finished_queue(
                "dl", bool(self.download_queue_items), self._dl_clear_queue,
                keep_fn=lambda: (self._reset_errored_to_pending(self.download_queue_items),
                                 self._render_download_queue()))
        if not proceed:
            return
        win = tk.Toplevel(self)
        win.title(self.t("add_dialog_title"))
        win.transient(self)
        win.geometry("600x340")
        frm = ttk.Frame(win)
        frm.pack(fill="both", expand=True, padx=12, pady=12)
        frm.columnconfigure(0, weight=1)
        frm.rowconfigure(1, weight=1)
        ttk.Label(frm, text=self.t("add_dialog_info"), foreground="#555",
                  wraplength=560, justify="left").grid(row=0, column=0, sticky="w", pady=(0, 6))
        txt = tk.Text(frm, height=10, wrap="word", font=("TkFixedFont", 9))
        txt.grid(row=1, column=0, sticky="nsew")
        txt.focus_set()
        btns = ttk.Frame(frm)
        btns.grid(row=2, column=0, sticky="e", pady=(8, 0))

        def do_add():
            raw = txt.get("1.0", "end")
            if raw.strip():
                self._ingest_and_report(raw, target)
            win.destroy()
        ttk.Button(btns, text=self.t("btn_add"), command=do_add).pack(side="left", padx=2)
        ttk.Button(btns, text=self.t("cancel"), command=win.destroy).pack(side="left", padx=2)

    def _ingest_and_report(self, raw, target):
        items = self.youtube_queue_items if target == "youtube" else self.download_queue_items
        added, invalid, playlists = self._ingest_links(raw, items, target=target)
        if target == "youtube":
            self._render_youtube_queue(); self._update_youtube_summary()
        else:
            self._render_download_queue(); self._update_download_summary()
        if playlists == 0 and added == 0 and invalid == 0:
            messagebox.showinfo(self.t("info"), self.t("info_all_in_queue"))
        elif added == 0 and invalid and playlists == 0:
            messagebox.showwarning(self.t("warn"), self.t("yt_no_valid_links"))
        elif invalid:
            messagebox.showinfo(self.t("info"), self.t("yt_some_invalid", n=invalid))
        return added, invalid, playlists

    def _yt_move_selected(self, direction):
        if self.youtube_is_running:
            messagebox.showwarning(self.t("warn"), self.t("warn_queue_locked"))
            return
        sel = self.yt_tree.selection()
        if not sel:
            return
        moving_id = int(sel[0])
        by_id = {it.item_id: i for i, it in enumerate(self.youtube_queue_items)}
        idx = by_id.get(moving_id)
        if idx is None:
            return
        new = idx + direction
        if 0 <= new < len(self.youtube_queue_items):
            self.youtube_queue_items[idx], self.youtube_queue_items[new] = \
                self.youtube_queue_items[new], self.youtube_queue_items[idx]
            self._render_youtube_queue()
            self.yt_tree.selection_set(str(moving_id))
            self.yt_tree.focus(str(moving_id))

    def _yt_remove_selected(self):
        if self.youtube_is_running:
            messagebox.showwarning(self.t("warn"), self.t("warn_queue_locked"))
            return
        by_id = {it.item_id: it for it in self.youtube_queue_items}
        ids_to_remove = []
        for iid in self.yt_tree.selection():
            it = by_id.get(int(iid))
            if it is not None:
                ids_to_remove.append(it.item_id)
        if ids_to_remove:
            self.youtube_queue_items = [it for it in self.youtube_queue_items
                                        if it.item_id not in ids_to_remove]
            self._render_youtube_queue()
            self._update_youtube_summary()

    def _yt_clear_queue(self):
        if self.youtube_is_running:
            messagebox.showwarning(self.t("warn"), self.t("warn_queue_locked"))
            return
        self.youtube_queue_items = []
        self._render_youtube_queue()
        self._update_youtube_summary()

    def _yt_link_for_iid(self, iid):
        try:
            item_id = int(iid)
        except (TypeError, ValueError):
            return None
        for it in self.youtube_queue_items:
            if it.item_id == item_id:
                return it.filepath
        return None

    def _yt_status_text(self, status):
        return {ST_PENDING: self.t("status_pending"),
                ST_RUNNING: self.t("status_running_yt"),
                ST_DONE: self.t("status_done"),
                ST_ERROR: self.t("status_error"),
                ST_SKIPPED: self.t("status_skipped"),
                ST_MEMBERS_ONLY: self.t("status_members_only")}.get(status, status)

    def _render_youtube_queue(self):
        if not hasattr(self, "yt_tree"):
            return

        def populate():
            self.yt_tree.delete(*self.yt_tree.get_children())
            for i, it in enumerate(self.youtube_queue_items):
                label = it.error_message if (it.status == ST_ERROR and it.error_message) \
                    else self._yt_status_text(it.status)
                length = fmt_hms(it.duration) if it.duration else "…"
                tags = ("members_only",) if it.status == ST_MEMBERS_ONLY else ()
                self.yt_tree.insert("", "end", iid=str(it.item_id),
                                    values=(i + 1, it.filename, length, label), tags=tags)
        render_queue_preserving_selection(self.yt_tree, populate)

    def _yt_open_output(self):
        for it in self.youtube_queue_items:
            if it.output_dir:
                self._open_path(it.output_dir)
                return
        if self.yt_outdir_var.get():
            self._open_path(self.yt_outdir_var.get())

    # --- YouTube run ---
    def _start_youtube_batch(self):
        if self.youtube_is_running:
            return
        yt_md_readiness = self._markitdown_readiness()
        if yt_md_readiness != "ready":
            messagebox.showerror(
                self.t("error"),
                self.t("err_markitdown_broken") if yt_md_readiness == "broken"
                else self.t("err_no_markitdown"))
            self._open_markitdown_settings()
            return
        if not self.youtube_queue_items:
            messagebox.showerror(self.t("error"), self.t("err_no_files"))
            return
        if not self._enforce_caps(len(self.youtube_queue_items),
                                  TRANSCRIBE_SOFT_CAP, TRANSCRIBE_HARD_CAP):
            return
        out_dir = self.yt_outdir_var.get().strip()
        if not out_dir:
            messagebox.showerror(self.t("error"), self.t("yt_need_output_dir"))
            return
        self.cfg["youtube_output_dir"] = out_dir
        self._save_config()
        if not self._confirm_header_before_start():
            return
        for it in self.youtube_queue_items:
            it.status = ST_PENDING
            it.error_message = ""
            it.output_dir = None
        self._render_youtube_queue()
        code = self.cfg.get("youtube_pref_lang", "auto")
        preferred = None if code == "auto" else code
        prefix = ytdlp_command_prefix(self.python_exe) if self.ytdlp_ok else None
        every, pause_seconds = self._pause_params("yt")
        self.youtube_stop_flag = threading.Event()
        self.youtube_worker = YouTubeWorker(
            items=self.youtube_queue_items, preferred_code=preferred,
            keep_srt=self.yt_srt_var.get(), keep_txt=self.yt_txt_var.get(),
            output_dir=out_dir, strings=self.s, event_queue=self.youtube_event_queue,
            stop_flag=self.youtube_stop_flag, ytdlp_prefix=prefix,
            delay_range=YT_TRANSCRIBE_DELAY, lang=self.lang,
            pause_every=every, pause_seconds=pause_seconds,
            header_config=self._active_header_config(),
            polish=self._polish_enabled(),
            header_lang=self.cfg.get("header_lang", "pt"),
            keep_timestamps=self._keep_timestamps_enabled(),
            model_id=self._active_model(), markitdown_ok=self.markitdown_ok,
            python_exe=self.python_exe)
        self._finished["yt"] = False
        self.youtube_is_running = True
        self._yt_done = 0
        self._yt_errors = 0
        self._yt_cur_index = 0
        self._yt_total = len(self.youtube_queue_items)
        self.yt_start_btn.configure(state="disabled")
        self.yt_cancel_btn.configure(state="normal")
        self.yt_open_btn.configure(state="disabled")
        self._clear_log(self.yt_log_text)
        self._append_text(self.yt_log_text, self.t("log_batch_start",
                                                   time=datetime.now().strftime("%H:%M:%S")))
        self._set_progress(self.yt_progress, self.yt_progress_pct_var, 0.0)
        self.youtube_worker.start()

    def _cancel_youtube_batch(self):
        if self.youtube_is_running and self.youtube_worker:
            if messagebox.askyesno(self.t("cancel_title"), self.t("cancel_question")):
                self._append_text(self.yt_log_text, self.t("log_canceling"))
                self.youtube_stop_flag.set()

    def _poll_youtube_events(self):
        try:
            while True:
                ev = self.youtube_event_queue.get_nowait()
                self._handle_youtube_event(ev)
        except queue.Empty:
            pass
        self.after(120, self._poll_youtube_events)

    def _handle_youtube_event(self, ev):
        kind = ev.get("kind")
        if kind == "yt_log":
            self._append_text(self.yt_log_text, ev.get("text", ""))
        elif kind == "expand_done":
            self._apply_expanded_entries(ev.get("entries", []), "youtube")
        elif kind == "expand_error":
            short, _ = youtube_error_message(ev.get("cause", "generic"), self.s,
                                             raw=ev.get("raw", ""))
            self._append_text(self.yt_log_text,
                              self.t("yt_expand_error", e=short) + "\n")
        elif kind == "yt_progress_index":
            self._yt_cur_index = ev.get("index", 0)
            self._update_yt_progress_label()
        elif kind == "yt_item_status":
            idx = ev.get("index")
            status = ev.get("status")
            if 0 <= idx < len(self.youtube_queue_items):
                it = self.youtube_queue_items[idx]
                it.status = status
                if ev.get("error"):
                    it.error_message = ev["error"]
                try:
                    self.yt_tree.set(str(it.item_id), "status",
                                     ev.get("error") or self._yt_status_text(status))
                    self.yt_tree.item(str(it.item_id),
                                      tags=("members_only",) if status == ST_MEMBERS_ONLY else ())
                except tk.TclError:
                    pass
            if status in ST_TERMINAL:
                if status == ST_DONE:
                    self._yt_done += 1
                elif status == ST_ERROR:
                    self._yt_errors += 1
                self._update_yt_progress_label()
        elif kind == "yt_batch_blocked":
            messagebox.showwarning(self.t("yt_block_title"),
                                   ev.get("message") or self.t("yt_block_dialog"))
        elif kind == "yt_batch_finished":
            self._on_youtube_batch_finished()

    def _update_yt_progress_label(self):
        total = max(1, getattr(self, "_yt_total", 1))
        done = self._yt_done + self._yt_errors
        pct = compute_batch_percent(0, 0, 0, done, total)
        self._set_progress(self.yt_progress, self.yt_progress_pct_var, pct)
        cur = current_processing_index(done, total, self.youtube_is_running)
        self.yt_progress_label_var.set(self.t("batch_progress", done=cur, total=total))

    def _on_youtube_batch_finished(self):
        self.youtube_is_running = False
        self._finished["yt"] = True
        self.youtube_worker = None
        self._set_progress(self.yt_progress, self.yt_progress_pct_var, 100.0)
        self.yt_start_btn.configure(state="normal" if self.markitdown_ok else "disabled")
        self.yt_cancel_btn.configure(state="disabled")
        self.yt_open_btn.configure(state="normal")
        self._append_text(self.yt_log_text, self.t("log_batch_end",
                                                   time=datetime.now().strftime("%H:%M:%S")))
        self.yt_progress_label_var.set(self.t("batch_finished_label",
                                       done=self._yt_done, errors=self._yt_errors))
        if self._yt_errors:
            messagebox.showwarning(self.t("finished_with_errors_title"),
                                   self.t("finished_with_errors_msg",
                                          done=self._yt_done, errors=self._yt_errors))
        else:
            messagebox.showinfo(self.t("finished_title"),
                                self.t("finished_msg", done=self._yt_done))

    # ======================================================================
    # v0.8.0 shared helpers
    # ======================================================================
    def _set_progress(self, bar, pct_var, pct):
        txt = self.t("pct_label", pct=int(round(pct)))
        try:
            bar.set_percent(pct, text=txt)
        except Exception:
            try:
                bar.configure(value=max(0.0, min(100.0, float(pct))))
            except Exception:
                pass
        if pct_var is not None:
            pct_var.set(txt)

    @staticmethod
    def _human_bytes(n):
        if n is None:
            return "—"
        try:
            n = float(n)
        except (TypeError, ValueError):
            return "—"
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if n < 1024 or unit == "TB":
                if unit == "B":
                    return f"{int(n)} {unit}"
                return f"{n:.1f} {unit}"
            n /= 1024.0
        return f"{n:.1f} TB"

    # ---- pause-every-N control (both YouTube tabs) -----------------------
    def _build_pause_box(self, parent, kind):
        pre = "youtube" if kind == "yt" else "download"
        en = tk.BooleanVar(value=bool(self.cfg.get(f"{pre}_pause_enabled", False)))
        every = tk.StringVar(value=str(self.cfg.get(f"{pre}_pause_every", 20)))
        minutes = tk.StringVar(value=str(self.cfg.get(f"{pre}_pause_minutes", 5)))
        frame = ttk.Frame(parent)
        chk = ttk.Checkbutton(frame, text=self.t("pause_every"), variable=en,
                              command=lambda: self._on_pause_change(kind))
        chk.grid(row=0, column=0, sticky="w")
        e1 = ttk.Spinbox(frame, from_=1, to=999, width=5, textvariable=every,
                         command=lambda: self._on_pause_change(kind))
        e1.grid(row=0, column=1, padx=4)
        ttk.Label(frame, text=self.t("pause_videos_for")).grid(row=0, column=2)
        e2 = ttk.Spinbox(frame, from_=1, to=999, width=5, textvariable=minutes,
                         command=lambda: self._on_pause_change(kind))
        e2.grid(row=0, column=3, padx=4)
        ttk.Label(frame, text=self.t("pause_minutes")).grid(row=0, column=4)
        setattr(self, f"{kind}_pause_var", en)
        setattr(self, f"{kind}_pause_every_var", every)
        setattr(self, f"{kind}_pause_min_var", minutes)
        setattr(self, f"{kind}_pause_spins", (e1, e2))
        for e in (e1, e2):
            e.bind("<FocusOut>", lambda ev: self._on_pause_change(kind))
        controls = self._yt_controls if kind == "yt" else self._dl_controls
        controls += [chk, e1, e2]
        self._update_pause_enabled(kind)
        return frame

    def _on_pause_change(self, kind):
        pre = "youtube" if kind == "yt" else "download"

        def _int(var, default):
            try:
                return max(1, int(float(var.get())))
            except (TypeError, ValueError):
                return default
        self.cfg[f"{pre}_pause_enabled"] = bool(getattr(self, f"{kind}_pause_var").get())
        self.cfg[f"{pre}_pause_every"] = _int(getattr(self, f"{kind}_pause_every_var"), 20)
        self.cfg[f"{pre}_pause_minutes"] = _int(getattr(self, f"{kind}_pause_min_var"), 5)
        self._save_config()
        self._update_pause_enabled(kind)

    def _update_pause_enabled(self, kind):
        spins = getattr(self, f"{kind}_pause_spins", None)
        if not spins:
            return
        st = "normal" if getattr(self, f"{kind}_pause_var").get() else "disabled"
        for s in spins:
            try:
                s.configure(state=st)
            except tk.TclError:
                pass

    def _pause_params(self, kind):
        """Return (every_n, pause_seconds) if enabled, else (0, 0)."""
        pre = "youtube" if kind == "yt" else "download"
        if not self.cfg.get(f"{pre}_pause_enabled"):
            return 0, 0
        every = int(self.cfg.get(f"{pre}_pause_every", 20) or 0)
        minutes = int(self.cfg.get(f"{pre}_pause_minutes", 5) or 0)
        if every <= 0 or minutes <= 0:
            return 0, 0
        return every, minutes * 60

    def _enforce_caps(self, count, soft, hard):
        """item 8: both the hard cap and the soft warning are opt-out
        (default ON = current behavior). When the corresponding setting is
        off, that check is skipped entirely — no cap, no dialog."""
        if self.cfg.get("batch_cap_enabled", True) and count > hard:
            messagebox.showerror(self.t("cap_hard_title"),
                                 self.t("cap_hard_msg", n=count, max=hard))
            return False
        if self.cfg.get("batch_warn_enabled", True) and count > soft:
            return self._confirm_dialog(
                self.t("cap_soft_title"), self.t("cap_soft_q", n=count),
                self.t("cap_soft_ok"), self.t("cap_soft_cancel"))
        return True

    def _confirm_dialog(self, title, message, ok_label, cancel_label):
        """Modal yes/no with custom button labels. Returns True if OK chosen."""
        win = tk.Toplevel(self)
        win.title(title)
        win.transient(self)
        win.resizable(False, False)
        result = {"ok": False}
        frm = ttk.Frame(win)
        frm.pack(fill="both", expand=True, padx=18, pady=16)
        ttk.Label(frm, text="\u26a0", font=("TkDefaultFont", 20)).pack()
        ttk.Label(frm, text=message, wraplength=420, justify="left"
                  ).pack(pady=(6, 12))
        btns = ttk.Frame(frm)
        btns.pack()

        def choose(ok):
            result["ok"] = ok
            win.destroy()
        ttk.Button(btns, text=ok_label, command=lambda: choose(True)).pack(side="left", padx=6)
        ttk.Button(btns, text=cancel_label, command=lambda: choose(False)).pack(side="left", padx=6)
        win.bind("<Escape>", lambda e: choose(False))
        win.protocol("WM_DELETE_WINDOW", lambda: choose(False))
        win.update_idletasks()
        try:
            win.grab_set()
        except tk.TclError:
            pass
        self.wait_window(win)
        return result["ok"]

    def _get_speed_factor(self, model):
        """Returns (factor, is_confident). is_confident=False means no real
        sample exists yet for this model and the conservative default is
        being used."""
        history = getattr(self, "_eta_history", None)
        if history is None:
            history = load_eta_history()
            self._eta_history = history
        entry = history.get(model) if isinstance(history, dict) else None
        if isinstance(entry, dict) and entry.get("avg", 0) > 0:
            return float(entry["avg"]), True
        return DEFAULT_SPEED_FACTOR, False

    def _set_speed_factor(self, model, sample):
        if not model:
            return
        history = getattr(self, "_eta_history", None)
        if history is None:
            history = load_eta_history()
        entry = history.get(model) if isinstance(history, dict) else None
        history[model] = update_speed_factor_rolling(entry, sample)
        self._eta_history = history
        save_eta_history(history)

    # ---- shared link ingest (single videos + playlist expansion) ---------
    def _ingest_links(self, raw, items_list, target):
        existing = {getattr(it, "video_id", None) for it in items_list}
        added = invalid = playlists = 0
        new_singles = []
        log_widget = self.yt_log_text if target == "youtube" else self.dl_log_text
        live_q = (getattr(self, "dl_live_queue", None)
                 if (target == "download" and self.download_is_running) else None)
        ytdlp_readiness = None   # computed lazily, at most once, only if a playlist link shows up
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            vid = youtube_video_id(line)
            if vid:
                if vid in existing:
                    continue
                item = QueueItem(line)
                item.filename = line
                item.video_id = vid
                if live_q is not None:
                    live_q.add(item)
                else:
                    items_list.append(item)
                existing.add(vid)
                new_singles.append(item)
                added += 1
                continue
            plist = youtube_playlist_id(line)
            if plist:
                if is_mix_playlist(plist):
                    self._append_text(log_widget, self.t("yt_playlist_mix_rejected") + "\n")
                    invalid += 1
                    continue
                if ytdlp_readiness is None:
                    ytdlp_readiness = self._ytdlp_readiness()
                if ytdlp_readiness != "ready":
                    messagebox.showwarning(
                        self.t("warn"),
                        self.t("err_ytdlp_broken") if ytdlp_readiness == "broken"
                        else self.t("yt_need_ytdlp_playlist"))
                    invalid += 1
                    continue
                self._expand_playlist_async(line, target)
                playlists += 1
                continue
            invalid += 1
        if new_singles:
            self._probe_youtube_lengths(new_singles, target)
        return added, invalid, playlists

    def _expand_playlist_async(self, url, target):
        ev_queue = self.youtube_event_queue if target == "youtube" else self.download_event_queue
        log_widget = self.yt_log_text if target == "youtube" else self.dl_log_text
        self._append_text(log_widget, self.t("yt_log_fetching_playlist"))
        prefix = ytdlp_command_prefix(self.python_exe)
        worker = PlaylistExpandWorker(prefix, url, self.s, ev_queue, threading.Event())
        worker._target = target
        self._expand_workers.append(worker)
        worker.start()

    def _apply_expanded_entries(self, entries, target):
        items_list = self.youtube_queue_items if target == "youtube" else self.download_queue_items
        log_widget = self.yt_log_text if target == "youtube" else self.dl_log_text
        existing = {getattr(it, "video_id", None) for it in items_list}
        added = 0
        new_items = []
        live_q = (getattr(self, "dl_live_queue", None)
                 if (target == "download" and self.download_is_running) else None)
        for e in entries:
            vid = e.get("id")
            if not vid or vid in existing:
                continue
            url = f"https://www.youtube.com/watch?v={vid}"
            item = QueueItem(url)
            item.video_id = vid
            # flat-playlist titles are often locale-translated; treat as a
            # placeholder and let the per-video probe set the ORIGINAL title.
            item.title = e.get("title")
            item.filename = e.get("title") or url
            d = e.get("duration")
            item.duration = float(d) if isinstance(d, (int, float)) and d else None
            if live_q is not None:
                live_q.add(item)
            else:
                items_list.append(item)
            existing.add(vid)
            new_items.append(item)
            added += 1
        if not entries:
            self._append_text(log_widget, self.t("yt_playlist_empty") + "\n")
        else:
            self._append_text(log_widget, self.t("yt_playlist_added", n=added) + "\n")
        if target == "youtube":
            self._render_youtube_queue()
            self._update_youtube_summary()
        else:
            self._render_download_queue()
            self._update_download_summary()
        if new_items:
            # fetch original-language titles + accurate length/date in background
            self._probe_youtube_lengths(new_items, target)

    # ---- async length probing -------------------------------------------
    def _probe_media_lengths(self, items, target="trans"):
        if not self.ffmpeg_path:
            return
        ffmpeg = self.ffmpeg_path

        def work():
            for it in items:
                try:
                    dur = ffmpeg_probe_duration(ffmpeg, it.filepath)
                except Exception:
                    dur = None
                self._probe_event_queue.put(
                    {"target": target, "item": it, "duration": dur})
        th = threading.Thread(target=work, daemon=True)
        self._probe_threads.append(th)
        th.start()

    def _probe_youtube_lengths(self, items, target):
        prefix = ytdlp_command_prefix(self.python_exe) if self.ytdlp_ok else None

        def work():
            for it in items:
                vid = getattr(it, "video_id", None)
                if not vid:
                    continue
                try:
                    meta = youtube_metadata(vid, prefix=prefix)
                except Exception:
                    meta = None
                if meta:
                    self._probe_event_queue.put(
                        {"target": target, "item": it,
                         "duration": meta.get("duration"),
                         "title": meta.get("title"),
                         "upload_date": meta.get("upload_date")})
        th = threading.Thread(target=work, daemon=True)
        self._probe_threads.append(th)
        th.start()

    def _poll_probe_events(self):
        try:
            while True:
                ev = self._probe_event_queue.get_nowait()
                self._handle_probe_event(ev)
        except queue.Empty:
            pass
        self.after(150, self._poll_probe_events)

    def _handle_probe_event(self, ev):
        it = ev.get("item")
        if it is None:
            return
        d = ev.get("duration")
        if isinstance(d, (int, float)) and d and d > 0:
            it.duration = float(d)
        title = ev.get("title")
        if title:
            # full per-video extraction returns the ORIGINAL-language title;
            # overwrite the (possibly translated) flat-playlist placeholder.
            it.title = title
            it.filename = title
        if ev.get("upload_date"):
            it.upload_date = ev.get("upload_date")
            it.meta_fetched = True
        target = ev.get("target")
        if target == "trans":
            self._render_queue()
            self._update_trans_summary()
        elif target == "youtube":
            self._render_youtube_queue()
            self._update_youtube_summary()
        elif target == "download":
            self._render_download_queue()
            self._update_download_summary()
        elif target == "comparison":
            self._render_comparison_queue()

    # ---- summary lines ---------------------------------------------------
    def _update_trans_summary(self):
        if not hasattr(self, "trans_summary_var"):
            return
        total, n_known, secs = queue_length_summary(self.queue_items)
        parts = [self.t("summary_videos", n=total)]
        if secs > 0:
            parts.append(self.t("summary_total_len", dur=fmt_long_duration(secs)))
        elif total:
            parts.append(self.t("summary_unknown_hint"))
        self.trans_summary_var.set("   ·   ".join(parts))

    def _update_md_summary(self):
        if not hasattr(self, "md_summary_var"):
            return
        items = self.md_queue_items
        total = len(items)
        size = sum((it.size_bytes or 0) for it in items)
        per = float(self.cfg.get("md_per_file_seconds", MD_PER_FILE_DEFAULT))
        parts = [self.t("summary_files", n=total),
                 self.t("summary_total_size", size=self._human_bytes(size) if size else "—")]
        if total:
            parts.append(self.t("summary_est_convert",
                                eta="≈ " + fmt_long_duration(total * per)))
        self.md_summary_var.set("   ·   ".join(parts))

    def _update_youtube_summary(self):
        if not hasattr(self, "yt_summary_var"):
            return
        items = self.youtube_queue_items
        total, n_known, secs = queue_length_summary(items)
        per = float(self.cfg.get("yt_per_video_seconds", YT_PER_VIDEO_DEFAULT))
        delay = sum(YT_TRANSCRIBE_DELAY) / 2.0
        parts = [self.t("summary_videos", n=total)]
        if secs > 0:
            parts.append(self.t("summary_total_len", dur=fmt_long_duration(secs)))
        if total:
            eta = total * (per + delay)
            parts.append(self.t("summary_est_transcribe", eta="≈ " + fmt_long_duration(eta)))
        self.yt_summary_var.set("   ·   ".join(parts))

    def _update_download_summary(self):
        if not hasattr(self, "dl_summary_var"):
            return
        items = self.download_queue_items
        total, n_known, secs = queue_length_summary(items)
        parts = [self.t("summary_videos", n=total)]
        if secs > 0:
            parts.append(self.t("summary_total_len", dur=fmt_long_duration(secs)))
        elif total:
            parts.append(self.t("summary_unknown_hint"))
        if getattr(self, "dl_transcribe_var", None) and self.dl_transcribe_var.get():
            parts.append(self.t("dl_summary_transcribe_note"))
        self.dl_summary_var.set("   ·   ".join(parts))

    # ======================================================================
    # yt-dlp settings dialog
    # ======================================================================
    def _open_ytdlp_settings(self):
        win = tk.Toplevel(self)
        win.title(self.t("set_ytdlp_title"))
        win.transient(self)
        win.geometry("560x360")
        frm = ttk.Frame(win)
        frm.pack(fill="both", expand=True, padx=12, pady=12)
        frm.columnconfigure(0, weight=1)
        ttk.Label(frm, text=self.t("set_ytdlp_about"), wraplength=520,
                  foreground="#555").grid(row=0, column=0, sticky="w", pady=(0, 8))
        status_var = tk.StringVar()
        status_lbl = ttk.Label(frm, textvariable=status_var,
                               font=("TkDefaultFont", 10, "bold"))
        status_lbl.grid(row=1, column=0, sticky="w", pady=(0, 8))

        log = tk.Text(frm, height=8, wrap="word", state="disabled",
                      font=("TkFixedFont", 9))
        log.grid(row=2, column=0, sticky="nsew", pady=(0, 8))
        frm.rowconfigure(2, weight=1)

        def refresh_status():
            readiness = self._ytdlp_readiness()
            if readiness == "ready":
                status_var.set(self.t("set_ytdlp_found"))
                status_lbl.configure(foreground="#1a7f37")
            elif readiness == "broken":
                status_var.set(self.t("set_ytdlp_broken"))
                status_lbl.configure(foreground="#cf222e")
            else:
                status_var.set(self.t("set_ytdlp_missing"))
                status_lbl.configure(foreground="#cf222e")
            self._refresh_youtube_enabled()
            self._refresh_download_enabled()

        def on_change_done():
            install_btn.configure(state="normal")
            recheck_btn.configure(state="normal")
            refresh_status()
            upd_refresh()

        def do_install():
            install_btn.configure(state="disabled")
            recheck_btn.configure(state="disabled")
            self._update_ytdlp(win, log, on_done=on_change_done,
                               confirm_key="set_ytdlp_install_q")

        btns = ttk.Frame(frm)
        btns.grid(row=3, column=0, sticky="ew")
        install_btn = ttk.Button(btns, text=self.t("set_ytdlp_install"),
                                 command=do_install)
        install_btn.pack(side="left", padx=2)
        recheck_btn = ttk.Button(btns, text=self.t("set_recheck"),
                                 command=refresh_status)
        recheck_btn.pack(side="left", padx=2)
        ttk.Button(btns, text=self.t("set_open_folder"),
                  command=lambda: self._open_path(str(TOOLS_VENV_DIR))).pack(side="left", padx=2)

        def uninstall_ytdlp():
            if not messagebox.askyesno(self.t("confirm"),
                                       self.t("confirm_uninstall_msg", path=str(TOOLS_VENV_DIR)),
                                       parent=win):
                return
            vpy = tools_venv_python()
            if os.path.exists(vpy):
                subprocess.run([vpy, "-m", "pip", "uninstall", "-y", "yt-dlp"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               **subprocess_hidden_window_kwargs())
            refresh_status()
            upd_refresh()
        ttk.Button(btns, text=self.t("set_uninstall"), command=uninstall_ytdlp).pack(side="left", padx=2)
        ttk.Button(btns, text=self.t("close"),
                   command=win.destroy).pack(side="right", padx=2)

        upd_refresh = self._make_update_row(
            frm, 4,
            get_installed=lambda: get_pip_package_version(self.python_exe, "yt-dlp"),
            get_latest=lambda: check_pypi_latest_version("yt-dlp"),
            on_update_confirmed=lambda latest: self._update_ytdlp(
                win, log, on_done=on_change_done, target_version=latest))
        refresh_status()

    # ======================================================================
    # Download tab
    # ======================================================================
    def _build_download_tab(self, parent):
        scroll = ScrollableFrame(parent)
        scroll.pack(fill="both", expand=True)
        root = scroll.inner
        root.columnconfigure(0, weight=1)
        root.rowconfigure(4, weight=1)   # queue expands
        self._dl_controls = []

        status = ttk.LabelFrame(root, text="")
        status.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 2))
        status.columnconfigure(3, weight=1)
        self.dl_ind_ytdlp = tk.Label(status, text="", cursor="hand2",
                                     font=("TkDefaultFont", 10, "bold"))
        self.dl_ind_ytdlp.grid(row=0, column=0, padx=8, pady=6)
        self.dl_ind_ytdlp.bind("<Button-1>", lambda e: self._open_ytdlp_settings())
        self.dl_ind_ffmpeg = tk.Label(status, text="", cursor="hand2",
                                      font=("TkDefaultFont", 10, "bold"))
        self.dl_ind_ffmpeg.grid(row=0, column=1, padx=8, pady=6)
        self.dl_ind_ffmpeg.bind("<Button-1>", lambda e: self._open_ffmpeg_settings())
        self.dl_ind_whisper = tk.Label(status, text="", cursor="hand2",
                                       font=("TkDefaultFont", 10, "bold"))
        self.dl_ind_whisper.grid(row=0, column=2, padx=8, pady=6)
        self.dl_ind_whisper.bind("<Button-1>", lambda e: self._open_whisper_settings())
        ttk.Label(status, text=self.t("dep_hint"), foreground="#777"
                  ).grid(row=0, column=3, sticky="e", padx=8)

        intro = ttk.Label(root, text=self.t("dl_intro"), foreground="#555")
        intro.grid(row=1, column=0, sticky="ew", padx=10, pady=(2, 0))
        intro.configure(wraplength=900)

        # options
        opt = ttk.LabelFrame(root, text=self.t("dl_options"))
        opt.grid(row=2, column=0, sticky="ew", padx=8, pady=4)
        for c in range(6):
            opt.columnconfigure(c, weight=0)
        self.dl_audio_only_var = tk.BooleanVar(value=bool(self.cfg.get("download_audio_only", False)))
        ck = ttk.Checkbutton(opt, text=self.t("dl_audio_only"),
                             variable=self.dl_audio_only_var, command=self._on_dl_opts_change)
        ck.grid(row=0, column=0, sticky="w", padx=6, pady=4)
        self._dl_controls.append(ck)
        ttk.Label(opt, text=self.t("dl_resolution")).grid(row=0, column=1, sticky="e", padx=4)
        self.dl_res_var = tk.StringVar(value=self.cfg.get("download_resolution", "best"))
        self.dl_res_combo = ttk.Combobox(opt, textvariable=self.dl_res_var, state="readonly",
                                         width=8, values=[self.t("dl_res_best")] +
                                         [r for r in DOWNLOAD_RESOLUTIONS if r != "best"])
        self._sync_res_combo_display()
        self.dl_res_combo.grid(row=0, column=2, sticky="w", padx=4)
        self.dl_res_combo.bind("<<ComboboxSelected>>", lambda e: self._on_dl_opts_change())
        self._dl_controls.append(self.dl_res_combo)
        ttk.Label(opt, text=self.t("dl_audio_format")).grid(row=0, column=3, sticky="e", padx=4)
        self.dl_audiofmt_var = tk.StringVar(value=self.cfg.get("download_audio_format", "mp3"))
        self.dl_audiofmt_combo = ttk.Combobox(opt, textvariable=self.dl_audiofmt_var,
                                              state="readonly", width=7,
                                              values=DOWNLOAD_AUDIO_FORMATS)
        self.dl_audiofmt_combo.grid(row=0, column=4, sticky="w", padx=4)
        self.dl_audiofmt_combo.bind("<<ComboboxSelected>>", lambda e: self._on_dl_opts_change())
        self._dl_controls.append(self.dl_audiofmt_combo)
        ttk.Label(opt, text=self.t("dl_container")).grid(row=0, column=5, sticky="e", padx=4)
        self.dl_container_var = tk.StringVar(value=self.cfg.get("download_container", "mp4"))
        self.dl_container_combo = ttk.Combobox(opt, textvariable=self.dl_container_var,
                                              state="readonly", width=6,
                                              values=DOWNLOAD_CONTAINERS)
        self.dl_container_combo.grid(row=0, column=6, sticky="w", padx=4)
        self.dl_container_combo.bind("<<ComboboxSelected>>", lambda e: self._on_dl_opts_change())
        self._dl_controls.append(self.dl_container_combo)
        self.dl_ffmpeg_note = ttk.Label(opt, text=self.t("dl_ffmpeg_note"), foreground="#777")
        self.dl_ffmpeg_note.grid(row=1, column=0, columnspan=7, sticky="w", padx=6, pady=(0, 4))

        # output dir (single fixed folder)
        of = ttk.LabelFrame(root, text=self.t("fixed_folder"))
        of.grid(row=3, column=0, sticky="ew", padx=8, pady=2)
        of.columnconfigure(0, weight=1)
        self.dl_outdir_var = tk.StringVar(value=self.cfg.get("download_output_dir", ""))
        dl_entry = ttk.Entry(of, textvariable=self.dl_outdir_var)
        dl_entry.grid(row=0, column=0, sticky="ew", padx=6, pady=6)
        b_br = ttk.Button(of, text=self.t("browse"), command=self._dl_browse_outdir)
        b_br.grid(row=0, column=1, padx=6, pady=6)
        self._dl_controls += [dl_entry, b_br]

        # queue
        qf = ttk.LabelFrame(root, text=self.t("dl_queue_frame"))
        qf.grid(row=4, column=0, sticky="nsew", padx=8, pady=4)
        qf.columnconfigure(0, weight=1)
        qf.rowconfigure(1, weight=1)
        qbtns = ttk.Frame(qf)
        qbtns.grid(row=0, column=0, sticky="ew", padx=4, pady=4)
        b_add = ttk.Button(qbtns, text=self.t("btn_add"),
                           command=lambda: self._open_add_links_dialog("download"))
        b_add.pack(side="left", padx=2)
        b_rm = ttk.Button(qbtns, text=self.t("remove_selected"), command=self._dl_remove_selected)
        b_rm.pack(side="left", padx=2)
        b_cl = ttk.Button(qbtns, text=self.t("clear_queue"), command=self._dl_clear_queue)
        b_cl.pack(side="left", padx=2)
        self.dl_clear_queue_btn = b_cl
        b_up = ttk.Button(qbtns, text=self.t("move_up"),
                          command=lambda: self._dl_move_selected(-1))
        b_up.pack(side="left", padx=2)
        b_dn = ttk.Button(qbtns, text=self.t("move_down"),
                          command=lambda: self._dl_move_selected(1))
        b_dn.pack(side="left", padx=2)
        self._dl_controls += [b_add, b_rm, b_cl, b_up, b_dn]
        cols = ("order", "video", "length", "status")
        qwrap, self.dl_tree, _dsb = make_scrollable_queue(qf, cols, height=13)
        qwrap.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)
        bind_queue_delete_key(self.dl_tree, self._dl_remove_selected)
        self.dl_tree._copy_link_label = self.t("copy_link")
        bind_queue_copy_link(self.dl_tree, self._dl_link_for_iid)
        self.dl_tree.heading("order", text=self.t("col_order"))
        self.dl_tree.heading("video", text=self.t("yt_col_video"))
        self.dl_tree.heading("length", text=self.t("col_length"))
        self.dl_tree.heading("status", text=self.t("col_status"))
        self.dl_tree.column("order", width=40, anchor="center", stretch=False)
        self.dl_tree.column("video", width=460)
        self.dl_tree.column("length", width=90, anchor="center", stretch=False)
        self.dl_tree.column("status", width=160, anchor="center")
        self.dl_tree.tag_configure("members_only", foreground="#cf222e")  # item 12
        bind_header_sort(
            self.dl_tree,
            {"video": (self.t("yt_col_video"),
                      lambda it: (it.filename or it.title or "").lower()),
             "length": (self.t("col_length"),
                        lambda it: it.duration if (it.duration and it.duration > 0) else None)},
            get_items=lambda: self.download_queue_items,
            is_running=lambda: self.download_is_running,
            render_fn=self._render_download_queue)
        self.dl_summary_var = tk.StringVar(value="")
        ttk.Label(qf, textvariable=self.dl_summary_var, foreground="#444"
                  ).grid(row=2, column=0, sticky="w", padx=6, pady=(0, 4))

        # transcribe-after-download + Whisper settings
        trow = ttk.Frame(root)
        trow.grid(row=5, column=0, sticky="ew", padx=10, pady=2)
        self.dl_transcribe_var = tk.BooleanVar(value=bool(self.cfg.get("download_transcribe", False)))
        tchk = ttk.Checkbutton(trow, text=self.t("dl_transcribe_after"),
                               variable=self.dl_transcribe_var,
                               command=self._on_dl_transcribe_toggle)
        tchk.grid(row=0, column=0, sticky="w")
        self.dl_whisper_btn = ttk.Button(trow, text=self.t("dl_define_whisper"),
                                         command=self._open_dl_whisper_settings)
        self.dl_whisper_btn.grid(row=0, column=1, padx=10)
        self.dl_whisper_check = tk.Label(trow, text="", fg="#1a7f37",
                                         font=("TkDefaultFont", 12, "bold"))
        self.dl_whisper_check.grid(row=0, column=2, padx=(0, 2))
        self._dl_controls += [tchk, self.dl_whisper_btn]
        # column 2 reserved for the Phase-2 whisper-valid check mark
        hdr = self._build_header_controls(trow)
        hdr.grid(row=0, column=3, sticky="w", padx=(16, 0))
        # item 10: "Define Header" only makes sense when the download will
        # also be transcribed (the header attaches to the MD Whisper writes,
        # not to the raw download itself).
        self.dl_header_edit_btn = hdr.edit_header_btn
        self.dl_header_edit_btn.configure(
            state=("normal" if self.dl_transcribe_var.get() else "disabled"))

        # pause control
        self._build_pause_box(root, "dl").grid(row=6, column=0, sticky="ew", padx=8, pady=2)

        # run controls
        rf = ttk.Frame(root)
        rf.grid(row=7, column=0, sticky="ew", padx=8, pady=4)
        rf.columnconfigure(2, weight=1)
        self.dl_start_btn = ttk.Button(rf, text=self.t("dl_start"), command=self._start_download_batch)
        self.dl_start_btn.grid(row=0, column=0, padx=2)
        self.dl_cancel_btn = ttk.Button(rf, text=self.t("cancel"),
                                        command=self._cancel_download_batch, state="disabled")
        self.dl_cancel_btn.grid(row=0, column=1, padx=2)
        self.dl_open_btn = ttk.Button(rf, text=self.t("open_output_folder"),
                                      command=self._dl_open_output, state="disabled")
        self.dl_open_btn.grid(row=0, column=3, padx=2, sticky="e")
        self.dl_progress = TwoToneProgress(rf, height=22)
        self.dl_progress.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(6, 0))
        self.dl_progress_pct_var = tk.StringVar(value="")
        self.dl_progress_label_var = tk.StringVar(value=self.t("waiting_start"))
        ttk.Label(rf, textvariable=self.dl_progress_label_var, foreground="#555"
                  ).grid(row=2, column=0, columnspan=4, sticky="w", pady=(2, 0))

        # log
        logf = ttk.LabelFrame(root, text=self.t("dl_log_frame"))
        logf.grid(row=8, column=0, sticky="ew", padx=8, pady=4)
        logf.columnconfigure(0, weight=1)
        self.dl_log_text = tk.Text(logf, height=8, wrap="word", state="disabled",
                                   font=("TkFixedFont", 9))
        dsb = ttk.Scrollbar(logf, orient="vertical", command=self.dl_log_text.yview)
        self.dl_log_text.configure(yscrollcommand=dsb.set)
        self.dl_log_text.grid(row=0, column=0, sticky="nsew", padx=(4, 0), pady=4)
        dsb.grid(row=0, column=1, sticky="ns", pady=4)
        self._on_dl_transcribe_toggle()

    def _sync_res_combo_display(self):
        cur = self.cfg.get("download_resolution", "best")
        self.dl_res_var.set(self.t("dl_res_best") if cur == "best" else cur)

    def _on_dl_opts_change(self):
        disp = self.dl_res_var.get()
        res = "best" if disp == self.t("dl_res_best") else disp
        if res not in DOWNLOAD_RESOLUTIONS:
            res = "best"
        self.cfg["download_resolution"] = res
        self.cfg["download_audio_only"] = bool(self.dl_audio_only_var.get())
        af = self.dl_audiofmt_var.get()
        self.cfg["download_audio_format"] = af if af in DOWNLOAD_AUDIO_FORMATS else "mp3"
        cn = self.dl_container_var.get()
        self.cfg["download_container"] = cn if cn in DOWNLOAD_CONTAINERS else "mp4"
        self._save_config()
        # audio-only disables resolution + container; enables audio format
        if self.dl_audio_only_var.get():
            self.dl_res_combo.configure(state="disabled")
            self.dl_container_combo.configure(state="disabled")
            self.dl_audiofmt_combo.configure(state="readonly")
        else:
            self.dl_res_combo.configure(state="readonly")
            self.dl_container_combo.configure(state="readonly")
            self.dl_audiofmt_combo.configure(state="disabled")

    def _refresh_download_enabled(self):
        if not hasattr(self, "dl_ind_ytdlp"):
            return
        yok = bool(getattr(self, "ytdlp_ok", False))
        ymark = self.t("dep_found") if yok else self.t("dep_missing")
        self.dl_ind_ytdlp.configure(text=f"{self.t('dep_ytdlp')} {ymark}",
                                    fg=("#1a7f37" if yok else "#cf222e"))
        fok = bool(self.ffmpeg_path)
        fmark = self.t("dep_found") if fok else self.t("dep_missing")
        self.dl_ind_ffmpeg.configure(text=f"{self.t('dep_ffmpeg')} {fmark}",
                                     fg=("#1a7f37" if fok else "#cf222e"))
        if hasattr(self, "dl_ind_whisper"):
            wok = bool(self.whisper_path)
            wmark = self.t("dep_found") if wok else self.t("dep_missing")
            self.dl_ind_whisper.configure(text=f"{self.t('dep_whisper')} {wmark}",
                                          fg=("#1a7f37" if wok else "#cf222e"))
        state = "normal" if (yok and not self.download_is_running) else "disabled"
        if hasattr(self, "dl_start_btn"):
            self.dl_start_btn.configure(state=state)
        if hasattr(self, "dl_whisper_btn") and not self.download_is_running:
            self.dl_whisper_btn.configure(
                state=("normal" if self.dl_transcribe_var.get() else "disabled"))
        self._refresh_dl_whisper_check()
        # reflect audio-only toggle on first build
        if hasattr(self, "dl_res_combo"):
            self._on_dl_opts_change()

    def _on_dl_transcribe_toggle(self):
        on = bool(self.dl_transcribe_var.get())
        self.cfg["download_transcribe"] = on
        self._save_config()
        if hasattr(self, "dl_whisper_btn") and not self.download_is_running:
            self.dl_whisper_btn.configure(state=("normal" if on else "disabled"))
        if hasattr(self, "dl_header_edit_btn") and not self.download_is_running:
            self.dl_header_edit_btn.configure(state=("normal" if on else "disabled"))
        self._update_download_summary()

    def _dictionary_payload(self, name):
        if not name or name == self.t("none"):
            return "", []
        prof = self.dictionaries.get(name, {})
        return (prof.get("initial_prompt") or prof.get("prompt") or ""), \
            prof.get("replacements", [])

    def _dl_whisper_is_valid(self):
        return bool(self.cfg.get("download_whisper_defined")
                    and self.cfg.get("download_whisper_model")
                    and self.whisper_path)

    def _refresh_dl_whisper_check(self):
        if not hasattr(self, "dl_whisper_check"):
            return
        show = (self.dl_transcribe_var.get() and self._dl_whisper_is_valid())
        self.dl_whisper_check.configure(text=("\u2713" if show else ""))

    def _open_dl_whisper_settings(self):
        """Pick the model + audio language + vocabulary dictionary to use for
        transcribing downloaded videos. Mirrors the A/V tab's controls."""
        win = tk.Toplevel(self)
        win.title(self.t("dl_define_whisper"))
        win.transient(self)
        win.resizable(False, False)
        frm = ttk.Frame(win)
        frm.pack(fill="both", expand=True, padx=14, pady=14)
        frm.columnconfigure(1, weight=1)
        ttk.Label(frm, text=self.t("dl_whisper_intro"), foreground="#555",
                  wraplength=460, justify="left").grid(row=0, column=0, columnspan=2,
                                                       sticky="w", pady=(0, 10))
        # audio language
        codes = self.cfg.get("audio_langs", list(DEFAULT_AUDIO_LANGS))
        lang_disp = [self._audio_lang_display(c) for c in codes]
        code_by_disp = dict(zip(lang_disp, codes))
        ttk.Label(frm, text=self.t("audio_language")).grid(row=1, column=0, sticky="w", pady=4)
        lang_var = tk.StringVar()
        lang_combo = ttk.Combobox(frm, textvariable=lang_var, state="readonly",
                                  width=28, values=lang_disp)
        lang_combo.grid(row=1, column=1, sticky="ew", pady=4)
        cur_lang = self.cfg.get("download_whisper_lang") or self.cfg.get("audio_lang_code", "pt")
        if cur_lang not in codes:
            cur_lang = codes[0] if codes else "pt"
        lang_combo.set(self._audio_lang_display(cur_lang))
        # model (filtered by language, installed only)
        ttk.Label(frm, text=self.t("ai_model")).grid(row=2, column=0, sticky="w", pady=4)
        model_var = tk.StringVar()
        model_combo = ttk.Combobox(frm, textvariable=model_var, state="readonly", width=34)
        model_combo.grid(row=2, column=1, sticky="ew", pady=4)
        model_status = ttk.Label(frm, text="", foreground="#555")
        model_status.grid(row=3, column=1, sticky="w")
        model_cli_by_disp = {}

        def refill_models():
            nonlocal model_cli_by_disp
            code = code_by_disp.get(lang_var.get(), cur_lang)
            installed = models_for_audio_language(code, only_installed=True)
            disp = [self._model_display(c) for c in installed]
            model_cli_by_disp = dict(zip(disp, installed))
            model_combo["values"] = disp
            want = self.cfg.get("download_whisper_model") or self.cfg.get("model_cli", "")
            if installed:
                model_combo.set(self._model_display(want if want in installed else installed[0]))
                model_status.configure(text="")
            else:
                model_combo.set("")
                model_status.configure(text=self.t("no_models_installed"))
        refill_models()
        lang_combo.bind("<<ComboboxSelected>>", lambda e: refill_models())
        # dictionary
        ttk.Label(frm, text=self.t("vocab_dict")).grid(row=4, column=0, sticky="w", pady=4)
        dict_var = tk.StringVar()
        dict_names = [self.t("none")] + sorted(self.dictionaries.keys())
        dict_combo = ttk.Combobox(frm, textvariable=dict_var, state="readonly",
                                  width=34, values=dict_names)
        dict_combo.grid(row=4, column=1, sticky="ew", pady=4)
        cur_dict = self.cfg.get("download_whisper_dictionary", "")
        dict_combo.set(cur_dict if cur_dict in self.dictionaries else self.t("none"))
        ttk.Button(frm, text=self.t("add_model") + " / " + self.t("add_languages"),
                   command=lambda: self._open_whisper_settings()).grid(
                       row=5, column=0, columnspan=2, sticky="w", pady=(8, 0))

        btns = ttk.Frame(frm)
        btns.grid(row=6, column=0, columnspan=2, sticky="e", pady=(12, 0))

        def save_and_close():
            code = code_by_disp.get(lang_var.get(), cur_lang)
            self.cfg["download_whisper_lang"] = code
            self.cfg["download_whisper_model"] = model_cli_by_disp.get(model_var.get(), "")
            dn = dict_var.get()
            self.cfg["download_whisper_dictionary"] = "" if dn == self.t("none") else dn
            self.cfg["download_whisper_defined"] = bool(self.cfg["download_whisper_model"])
            self.dl_whisper_reviewed = True
            self._save_config()
            self._refresh_dl_whisper_check()
            win.destroy()
        ttk.Button(btns, text=self.t("save"), command=save_and_close).pack(side="left", padx=4)
        ttk.Button(btns, text=self.t("cancel"), command=win.destroy).pack(side="left", padx=4)
        win.update_idletasks()
        try:
            win.grab_set()
        except tk.TclError:
            pass

    # ---- download queue ops ----
    def _dl_move_selected(self, direction):
        sel = self.dl_tree.selection()
        if not sel:
            return
        moving_id = int(sel[0])
        if self.download_is_running and getattr(self, "dl_live_queue", None) is not None:
            moved = self.dl_live_queue.move(moving_id, direction)
            if not moved:
                target = next((it for it in self.download_queue_items
                              if it.item_id == moving_id), None)
                if target is not None and target.status != ST_PENDING:
                    messagebox.showwarning(self.t("warn"), self.t("warn_item_locked"))
                return
            self._render_download_queue()
            self.dl_tree.selection_set(str(moving_id))
            return
        by_id = {it.item_id: i for i, it in enumerate(self.download_queue_items)}
        idx = by_id.get(moving_id)
        if idx is None:
            return
        new = idx + direction
        if not (0 <= new < len(self.download_queue_items)):
            return
        self.download_queue_items[idx], self.download_queue_items[new] = \
            self.download_queue_items[new], self.download_queue_items[idx]
        self._render_download_queue()

    def _dl_remove_selected(self):
        locked_selected = False
        ids_to_remove = []
        by_id = {it.item_id: it for it in self.download_queue_items}
        for iid in self.dl_tree.selection():
            it = by_id.get(int(iid))
            if it is None:
                continue
            if self.download_is_running and it.status != ST_PENDING:
                locked_selected = True
                continue
            ids_to_remove.append(it.item_id)
        for item_id in ids_to_remove:
            if self.download_is_running and getattr(self, "dl_live_queue", None) is not None:
                self.dl_live_queue.remove(item_id)
            else:
                self.download_queue_items = [it for it in self.download_queue_items
                                             if it.item_id != item_id]
        if ids_to_remove:
            self._render_download_queue()
            self._update_download_summary()
        if locked_selected:
            messagebox.showwarning(self.t("warn"), self.t("warn_item_locked"))

    def _dl_clear_queue(self):
        if self.download_is_running:
            # Button is disabled while running; this is a defensive fallback.
            messagebox.showwarning(self.t("warn"), self.t("warn_queue_locked"))
            return
        self.download_queue_items = []
        self._render_download_queue()
        self._update_download_summary()

    def _dl_link_for_iid(self, iid):
        try:
            item_id = int(iid)
        except (TypeError, ValueError):
            return None
        for it in self.download_queue_items:
            if it.item_id == item_id:
                return it.filepath
        return None

    def _dl_status_text(self, status):
        return {ST_PENDING: self.t("status_pending"),
                ST_RUNNING: self.t("status_running_dl"),
                ST_DONE: self.t("status_done"),
                ST_ERROR: self.t("status_error"),
                ST_SKIPPED: self.t("status_skipped"),
                ST_MEMBERS_ONLY: self.t("status_members_only")}.get(status, status)

    def _render_download_queue(self):
        if not hasattr(self, "dl_tree"):
            return

        def populate():
            self.dl_tree.delete(*self.dl_tree.get_children())
            for i, it in enumerate(self.download_queue_items):
                label = it.error_message if (it.status == ST_ERROR and it.error_message) \
                    else self._dl_status_text(it.status)
                length = fmt_hms(it.duration) if it.duration else "…"
                tags = ("members_only",) if it.status == ST_MEMBERS_ONLY else ()
                self.dl_tree.insert("", "end", iid=str(it.item_id),
                                    values=(i + 1, it.filename, length, label), tags=tags)
        render_queue_preserving_selection(self.dl_tree, populate)

    def _dl_browse_outdir(self):
        d = filedialog.askdirectory(
            title=self.t("select_output_title"),
            initialdir=self._existing_dir_or_home(self.dl_outdir_var.get()))
        if d:
            self.dl_outdir_var.set(d)
            self.cfg["download_output_dir"] = d
            self._save_config()

    def _dl_open_output(self):
        for it in self.download_queue_items:
            if it.output_dir:
                self._open_path(it.output_dir)
                return
        if self.dl_outdir_var.get():
            self._open_path(self.dl_outdir_var.get())

    # ---- download run ----
    def _start_download_batch(self):
        if self.download_is_running:
            return
        ytdlp_readiness = self._ytdlp_readiness()
        if ytdlp_readiness != "ready":
            messagebox.showerror(
                self.t("error"),
                self.t("err_ytdlp_broken") if ytdlp_readiness == "broken"
                else self.t("dl_need_ytdlp"))
            self._open_ytdlp_settings()
            return
        if not self.download_queue_items:
            messagebox.showerror(self.t("error"), self.t("err_no_files"))
            return
        if not self._enforce_caps(len(self.download_queue_items),
                                  DOWNLOAD_SOFT_CAP, DOWNLOAD_HARD_CAP):
            return
        out_dir = self.dl_outdir_var.get().strip()
        if not out_dir:
            messagebox.showerror(self.t("error"), self.t("dl_need_output_dir"))
            return
        progressive = False
        if not self.ffmpeg_path:
            if not messagebox.askyesno(self.t("warn"), self.t("dl_ffmpeg_nudge_q")):
                return
            progressive = True

        # transcribe-after-download gating
        transcribe = bool(self.dl_transcribe_var.get())
        w_model = w_lang_param = w_prompt = ""
        w_reps = []
        w_formats = []
        if transcribe:
            readiness = self._whisper_readiness()
            if readiness != "ready":
                messagebox.showerror(
                    self.t("error"),
                    self.t("err_whisper_broken") if readiness == "broken"
                    else self.t("dl_need_whisper"))
                self._open_whisper_settings()
                return
            if not self.ffmpeg_path:
                messagebox.showerror(self.t("error"), self.t("dl_transcribe_needs_ffmpeg"))
                return
            if not (getattr(self, "dl_whisper_reviewed", False)
                    and self._dl_whisper_is_valid()):
                messagebox.showinfo(self.t("dl_define_whisper"),
                                    self.t("dl_whisper_must_review"))
                self._open_dl_whisper_settings()
                return
            w_model = self.cfg.get("download_whisper_model", "")
            w_lang = self.cfg.get("download_whisper_lang", "")
            installed = models_for_audio_language(w_lang or "pt", only_installed=True)
            if not w_model or not w_lang or w_model not in installed:
                messagebox.showerror(self.t("error"), self.t("dl_whisper_not_defined"))
                self._open_dl_whisper_settings()
                return
            w_formats = self._selected_keep_formats()
            if not w_formats:
                messagebox.showerror(self.t("error"), self.t("err_no_format"))
                self._open_output_formats()
                return
            w_lang_param = audio_lang_param(w_lang)
            w_prompt, w_reps = self._dictionary_payload(
                self.cfg.get("download_whisper_dictionary", ""))

        self.cfg["download_output_dir"] = out_dir
        self._save_config()
        if transcribe and not self._confirm_header_before_start():
            return
        for it in self.download_queue_items:
            it.status = ST_PENDING
            it.error_message = ""
            it.output_dir = None
        self._render_download_queue()
        audio_only = bool(self.dl_audio_only_var.get())
        res = self.cfg.get("download_resolution", "best")
        prefix = ytdlp_command_prefix(self.python_exe)
        every, pause_seconds = self._pause_params("dl")
        self.download_stop_flag = threading.Event()
        self.dl_live_queue = LiveQueue(self.download_queue_items)
        self.download_worker = DownloadWorker(
            items=self.dl_live_queue, prefix=prefix, out_dir=out_dir,
            audio_only=audio_only, audio_format=self.cfg.get("download_audio_format", "mp3"),
            resolution=res, container=self.cfg.get("download_container", "mp4"),
            ffmpeg_location=self.ffmpeg_path, strings=self.s,
            event_queue=self.download_event_queue, stop_flag=self.download_stop_flag,
            delay_range=YT_DOWNLOAD_DELAY, progressive=progressive,
            pause_every=every, pause_seconds=pause_seconds,
            transcribe=transcribe, whisper_exe=self.whisper_path,
            whisper_model=w_model, whisper_lang_param=w_lang_param,
            whisper_task="transcribe", whisper_prompt=w_prompt,
            whisper_replacements=w_reps, whisper_formats=w_formats,
            header_config=self._active_header_config(),
            polish=self._polish_enabled(),
            header_lang=self.cfg.get("header_lang", "pt"),
            keep_timestamps=self._keep_timestamps_enabled())
        self._finished["dl"] = False
        self.download_is_running = True
        self._dl_done = 0
        self._dl_errors = 0
        self._dl_cur_running_id = None
        self.dl_start_btn.configure(state="disabled")
        self.dl_cancel_btn.configure(state="normal")
        self.dl_open_btn.configure(state="disabled")
        if hasattr(self, "dl_clear_queue_btn"):
            self.dl_clear_queue_btn.configure(state="disabled")
        self._clear_log(self.dl_log_text)
        self._append_text(self.dl_log_text, self.t("log_batch_start",
                                                   time=datetime.now().strftime("%H:%M:%S")))
        self._set_progress(self.dl_progress, self.dl_progress_pct_var, 0.0)
        self.download_worker.start()

    def _cancel_download_batch(self):
        if self.download_is_running and self.download_worker:
            if messagebox.askyesno(self.t("cancel_title"), self.t("cancel_question")):
                self._append_text(self.dl_log_text, self.t("log_canceling"))
                self.download_worker.cancel()

    def _poll_download_events(self):
        try:
            while True:
                ev = self.download_event_queue.get_nowait()
                self._handle_download_event(ev)
        except queue.Empty:
            pass
        self.after(120, self._poll_download_events)

    def _handle_download_event(self, ev):
        kind = ev.get("kind")
        if kind == "dl_log":
            self._append_text(self.dl_log_text, ev.get("text", ""))
        elif kind == "expand_done":
            self._apply_expanded_entries(ev.get("entries", []), "download")
        elif kind == "expand_error":
            short, _ = youtube_error_message(ev.get("cause", "generic"), self.s,
                                             raw=ev.get("raw", ""))
            self._append_text(self.dl_log_text,
                              self.t("yt_expand_error", e=short) + "\n")
        elif kind == "dl_progress":
            pct = ev.get("percent")
            if pct is not None:
                self._set_progress(self.dl_progress, self.dl_progress_pct_var, pct)
        elif kind == "dl_progress_item":
            self._dl_cur_running_id = ev.get("item_id")
            self._update_dl_progress_label()
        elif kind == "dl_item_status":
            item_id = ev.get("item_id")
            status = ev.get("status")
            it = next((q for q in self.download_queue_items if q.item_id == item_id), None)
            if it is not None:
                it.status = status
                if ev.get("error"):
                    it.error_message = ev["error"]
                try:
                    self.dl_tree.set(str(item_id), "status",
                                     ev.get("error") or self._dl_status_text(status))
                    self.dl_tree.item(str(item_id),
                                      tags=("members_only",) if status == ST_MEMBERS_ONLY else ())
                except tk.TclError:
                    pass
            if status in ST_TERMINAL:
                if status == ST_DONE:
                    self._dl_done += 1
                elif status == ST_ERROR:
                    self._dl_errors += 1
                self._update_dl_progress_label()
        elif kind == "dl_substatus":
            item_id = ev.get("item_id")
            try:
                self.dl_tree.set(str(item_id), "status", ev.get("text", ""))
            except tk.TclError:
                pass
        elif kind == "dl_batch_blocked":
            messagebox.showwarning(self.t("yt_block_title"),
                                   ev.get("message") or self.t("yt_block_dialog"))
        elif kind == "dl_batch_finished":
            self._on_download_batch_finished()

    def _update_dl_progress_label(self):
        total = max(1, len(self.download_queue_items))
        done = self._dl_done + self._dl_errors
        cur = current_processing_index(done, total, self.download_is_running)
        self.dl_progress_label_var.set(self.t("batch_progress", done=cur, total=total))

    def _on_download_batch_finished(self):
        self.download_is_running = False
        self._finished["dl"] = True
        self.download_worker = None
        self.dl_live_queue = None
        self._set_progress(self.dl_progress, self.dl_progress_pct_var, 100.0)
        self.dl_start_btn.configure(state="normal" if self.ytdlp_ok else "disabled")
        self.dl_cancel_btn.configure(state="disabled")
        self.dl_open_btn.configure(state="normal")
        if hasattr(self, "dl_clear_queue_btn"):
            self.dl_clear_queue_btn.configure(state="normal")
        self._append_text(self.dl_log_text, self.t("log_batch_end",
                                                   time=datetime.now().strftime("%H:%M:%S")))
        self.dl_progress_label_var.set(self.t("batch_finished_label",
                                       done=self._dl_done, errors=self._dl_errors))
        if self._dl_errors:
            messagebox.showwarning(self.t("finished_with_errors_title"),
                                   self.t("finished_with_errors_msg",
                                          done=self._dl_done, errors=self._dl_errors))
        else:
            messagebox.showinfo(self.t("finished_title"),
                                self.t("finished_msg", done=self._dl_done))

    # ---- grabber tab -----------------------------------------------------
    def _build_grabber_tab(self, parent):
        scroll = ScrollableFrame(parent)
        scroll.pack(fill="both", expand=True)
        root = scroll.inner
        root.columnconfigure(0, weight=1)
        root.rowconfigure(7, weight=1)

        intro = ttk.Label(root, text=self.t("grab_intro"), foreground="#555")
        intro.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 2))
        intro.configure(wraplength=900)

        inf = ttk.LabelFrame(root, text=self.t("grab_input_label"))
        inf.grid(row=1, column=0, sticky="ew", padx=8, pady=4)
        inf.columnconfigure(0, weight=1)
        self.grab_input = tk.Text(inf, height=15, wrap="none", font=("TkFixedFont", 9))
        self.grab_input.grid(row=0, column=0, sticky="ew", padx=(6, 0), pady=6)
        gisb = ttk.Scrollbar(inf, orient="vertical", command=self.grab_input.yview)
        self.grab_input.configure(yscrollcommand=gisb.set)
        gisb.grid(row=0, column=1, sticky="ns", pady=6)
        btns = ttk.Frame(inf)
        btns.grid(row=1, column=0, columnspan=2, sticky="w", padx=6, pady=(0, 6))
        self.grab_btn = ttk.Button(btns, text=self.t("grab_btn"), command=self._grab_start)
        self.grab_btn.pack(side="left", padx=2)
        ttk.Button(btns, text=self.t("grab_clear"), command=self._grab_clear).pack(side="left", padx=2)
        self.grab_note = ttk.Label(inf, text="", foreground="#cf222e", wraplength=900)
        self.grab_note.grid(row=2, column=0, columnspan=2, sticky="w", padx=6, pady=(0, 4))

        secf = ttk.LabelFrame(root, text=self.t("grab_sections_label"))
        secf.grid(row=2, column=0, sticky="ew", padx=8, pady=(2, 2))
        gsec = self.cfg.get("grabber_sections", {})
        self.grab_sec_vars = {
            "videos": tk.BooleanVar(value=gsec.get("videos", True)),
            "shorts": tk.BooleanVar(value=gsec.get("shorts", True)),
            "live": tk.BooleanVar(value=gsec.get("live", True)),
            "podcast": tk.BooleanVar(value=gsec.get("podcast", True)),
        }
        col = 0
        for key, label in (("videos", self.t("grab_sec_videos")),
                           ("shorts", self.t("grab_sec_shorts")),
                           ("live", self.t("grab_sec_live")),
                           ("podcast", self.t("grab_sec_podcast"))):
            ttk.Checkbutton(secf, text=label, variable=self.grab_sec_vars[key],
                            command=self._on_grab_sections_change
                            ).grid(row=0, column=col, sticky="w", padx=6, pady=2)
            col += 1
        self.grab_members_var = tk.BooleanVar(
            value=self.cfg.get("grabber_exclude_members", False))
        ttk.Checkbutton(secf, text=self.t("grab_exclude_members"),
                        variable=self.grab_members_var,
                        command=self._on_grab_sections_change
                        ).grid(row=1, column=0, columnspan=4, sticky="w", padx=6, pady=(0, 2))
        ttk.Label(secf, text=self.t("grab_sections_note"), foreground="#8250df",
                  wraplength=900).grid(row=2, column=0, columnspan=4, sticky="w",
                                       padx=6, pady=(0, 4))

        ctlf = ttk.Frame(root)
        ctlf.grid(row=3, column=0, sticky="ew", padx=10, pady=2)
        # item 13: independent output checkboxes (was 3 mutually-exclusive
        # radio modes). Default: only "Video Link" checked.
        self.grab_title_var = tk.BooleanVar(
            value=self.cfg.get("grabber_want_title", False))
        self.grab_duration_var = tk.BooleanVar(
            value=self.cfg.get("grabber_want_duration_col", False))
        self.grab_link_var = tk.BooleanVar(
            value=self.cfg.get("grabber_want_link", True))
        ttk.Checkbutton(ctlf, text=self.t("grab_out_title"),
                        variable=self.grab_title_var, command=self._on_grab_mode_change
                        ).grid(row=0, column=0, sticky="w", padx=(0, 12))
        ttk.Checkbutton(ctlf, text=self.t("grab_out_duration"),
                        variable=self.grab_duration_var, command=self._on_grab_mode_change
                        ).grid(row=0, column=1, sticky="w", padx=(0, 12))
        ttk.Checkbutton(ctlf, text=self.t("grab_out_link"),
                        variable=self.grab_link_var, command=self._on_grab_mode_change
                        ).grid(row=0, column=2, sticky="w")

        # item 18: independent min/max duration bounds (minutes). Either
        # bound forces the per-video duration probe (item 12's slow path)
        # even if the "Video Duration" output box above is unchecked.
        durf = ttk.Frame(root)
        durf.grid(row=4, column=0, sticky="ew", padx=10, pady=(0, 2))
        self.grab_min_dur_var = tk.BooleanVar(
            value=self.cfg.get("grabber_min_dur_enabled", False))
        self.grab_min_dur_val = tk.StringVar(
            value=str(self.cfg.get("grabber_min_dur_minutes", "")))
        self.grab_max_dur_var = tk.BooleanVar(
            value=self.cfg.get("grabber_max_dur_enabled", False))
        self.grab_max_dur_val = tk.StringVar(
            value=str(self.cfg.get("grabber_max_dur_minutes", "")))
        ttk.Checkbutton(durf, text=self.t("grab_min_dur_label"),
                        variable=self.grab_min_dur_var,
                        command=self._on_grab_opts_change).grid(row=0, column=0, sticky="w")
        ttk.Entry(durf, textvariable=self.grab_min_dur_val, width=6
                  ).grid(row=0, column=1, sticky="w", padx=(2, 16))
        ttk.Checkbutton(durf, text=self.t("grab_max_dur_label"),
                        variable=self.grab_max_dur_var,
                        command=self._on_grab_opts_change).grid(row=0, column=2, sticky="w")
        ttk.Entry(durf, textvariable=self.grab_max_dur_val, width=6
                  ).grid(row=0, column=3, sticky="w", padx=(2, 0))
        self.grab_min_dur_val.trace_add("write", lambda *a: self._on_grab_opts_change())
        self.grab_max_dur_val.trace_add("write", lambda *a: self._on_grab_opts_change())
        self.grab_dur_filter_hint = ttk.Label(
            durf, text="", foreground="#8250df", wraplength=900)
        self.grab_dur_filter_hint.grid(row=1, column=0, columnspan=4, sticky="w", pady=(2, 0))

        opt2 = ttk.Frame(root)
        opt2.grid(row=5, column=0, sticky="ew", padx=10, pady=(0, 2))
        ttk.Label(opt2, text=self.t("grab_title_lang")).grid(row=0, column=0, sticky="w")
        self._grab_lang_by_disp = {self.t("grab_lang_" + c): c for c in GRAB_TITLE_LANGS}
        lang_disp_sorted = ([self.t("grab_lang_auto")]
                            + sorted(self.t("grab_lang_" + c) for c in GRAB_TITLE_LANGS if c != "auto"))
        self.grab_lang_var = tk.StringVar()
        cur_code = self.cfg.get("grabber_title_lang", "auto")
        self.grab_lang_var.set(self.t("grab_lang_" + cur_code))
        lang_combo = ttk.Combobox(opt2, textvariable=self.grab_lang_var, state="readonly",
                                  width=16, values=lang_disp_sorted)
        lang_combo.grid(row=0, column=1, sticky="w", padx=(4, 16))
        lang_combo.bind("<<ComboboxSelected>>", lambda e: self._on_grab_opts_change())
        self._update_grab_dur_filter_hint()

        prog = ttk.Frame(root)
        prog.grid(row=6, column=0, sticky="ew", padx=10, pady=(0, 2))
        prog.columnconfigure(0, weight=1)
        self.grab_progress = ttk.Progressbar(prog, mode="determinate", maximum=100)
        self.grab_progress.grid(row=0, column=0, sticky="ew")
        self.grab_progress_var = tk.StringVar(value="")
        ttk.Label(prog, textvariable=self.grab_progress_var, foreground="#444", width=10
                  ).grid(row=0, column=1, sticky="e", padx=(8, 0))

        outf = ttk.LabelFrame(root, text=self.t("grab_output_label"))
        outf.grid(row=7, column=0, sticky="nsew", padx=8, pady=4)
        outf.columnconfigure(0, weight=1)
        outf.rowconfigure(0, weight=1)
        self.grab_output = tk.Text(outf, height=16, wrap="none", font=("TkFixedFont", 9))
        self.grab_output.grid(row=0, column=0, sticky="nsew", padx=(6, 0), pady=6)
        gosb = ttk.Scrollbar(outf, orient="vertical", command=self.grab_output.yview)
        self.grab_output.configure(yscrollcommand=gosb.set)
        gosb.grid(row=0, column=1, sticky="ns", pady=6)
        obtns = ttk.Frame(outf)
        obtns.grid(row=1, column=0, columnspan=2, sticky="w", padx=6, pady=(0, 6))
        ttk.Button(obtns, text=self.t("grab_copy"), command=self._grab_copy).pack(side="left", padx=2)
        ttk.Button(obtns, text=self.t("grab_save"), command=self._grab_save).pack(side="left", padx=2)
        ttk.Button(obtns, text=self.t("grab_save_csv"), command=self._grab_save_csv).pack(side="left", padx=2)
        self.grab_status_var = tk.StringVar(value="")
        ttk.Label(outf, textvariable=self.grab_status_var, foreground="#444"
                  ).grid(row=2, column=0, columnspan=2, sticky="w", padx=6, pady=(0, 4))

    def _on_grab_sections_change(self):
        self.cfg["grabber_sections"] = {k: v.get() for k, v in self.grab_sec_vars.items()}
        self.cfg["grabber_exclude_members"] = self.grab_members_var.get()
        self._save_config()

    def _grab_duration_bounds_minutes(self):
        """item 18: returns (min_minutes_or_None, max_minutes_or_None),
        ignoring a bound whose checkbox is off or whose value isn't a
        valid non-negative number."""
        def _val(enabled_var, val_var):
            if not enabled_var.get():
                return None
            try:
                v = float(val_var.get())
                return v if v >= 0 else None
            except (TypeError, ValueError):
                return None
        return (_val(self.grab_min_dur_var, self.grab_min_dur_val),
                _val(self.grab_max_dur_var, self.grab_max_dur_val))

    def _grab_duration_filter_active(self):
        lo, hi = self._grab_duration_bounds_minutes()
        return lo is not None or hi is not None

    def _apply_grab_duration_filter(self, entries):
        """item 18: keep only entries satisfying the active bound(s). While
        any bound is active, entries with undeterminable duration are
        excluded (they can't be shown to satisfy a bound they might not
        meet)."""
        lo, hi = self._grab_duration_bounds_minutes()
        if lo is None and hi is None:
            return entries
        lo_s = lo * 60 if lo is not None else None
        hi_s = hi * 60 if hi is not None else None
        out = []
        for e in entries:
            dur = e.get("duration")
            if not isinstance(dur, (int, float)) or dur <= 0:
                continue
            if lo_s is not None and dur < lo_s:
                continue
            if hi_s is not None and dur > hi_s:
                continue
            out.append(e)
        return out

    def _update_grab_dur_filter_hint(self):
        if self._grab_duration_filter_active() and not self.grab_duration_var.get():
            self.grab_dur_filter_hint.configure(text=self.t("grab_dur_filter_forces_probe"))
        else:
            self.grab_dur_filter_hint.configure(text="")

    def _on_grab_opts_change(self):
        self.cfg["grabber_title_lang"] = self._grab_lang_by_disp.get(
            self.grab_lang_var.get(), "auto")
        self.cfg["grabber_want_title"] = self.grab_title_var.get()
        self.cfg["grabber_want_duration_col"] = self.grab_duration_var.get()
        self.cfg["grabber_want_link"] = self.grab_link_var.get()
        self.cfg["grabber_min_dur_enabled"] = self.grab_min_dur_var.get()
        self.cfg["grabber_min_dur_minutes"] = self.grab_min_dur_val.get()
        self.cfg["grabber_max_dur_enabled"] = self.grab_max_dur_var.get()
        self.cfg["grabber_max_dur_minutes"] = self.grab_max_dur_val.get()
        self._save_config()
        self._update_grab_dur_filter_hint()
        self._render_grab_output()

    def _grab_clear(self):
        self.grab_input.delete("1.0", "end")

    def _format_grab_entries(self, entries):
        """item 13: build each output line from whichever of the three
        output checkboxes are currently checked."""
        want_title = self.grab_title_var.get()
        want_dur = self.grab_duration_var.get()
        want_link = self.grab_link_var.get()
        lines = []
        for e in entries:
            parts = []
            if want_title:
                parts.append((e.get("title") or "").strip() or e["id"])
            if want_dur:
                parts.append(fmt_hms(e.get("duration")) if e.get("duration") else "—")
            if want_link:
                parts.append(e["url"])
            lines.append(" — ".join(parts) if parts else e["url"])
        return "\n".join(lines)

    def _render_grab_output(self):
        self.grab_output.delete("1.0", "end")
        if self._grab_entries:
            self.grab_output.insert("1.0", self._format_grab_entries(self._grab_entries) + "\n")

    def _on_grab_mode_change(self):
        self._on_grab_opts_change()

    def _grab_start(self):
        if self.grabber_is_running:
            return
        grab_ytdlp_readiness = self._ytdlp_readiness()
        if grab_ytdlp_readiness != "ready":
            self.grab_note.configure(
                text=self.t("err_ytdlp_broken") if grab_ytdlp_readiness == "broken"
                else self.t("grab_need_ytdlp"))
            return
        self.grab_note.configure(text="")
        raw = self.grab_input.get("1.0", "end").strip()
        urls = [ln.strip() for ln in raw.splitlines() if ln.strip()]
        if not urls:
            self.grab_note.configure(text=self.t("grab_no_input"))
            return
        self._grab_entries = []
        self.grab_output.delete("1.0", "end")
        self.grab_status_var.set(self.t("grab_working"))
        self.grab_progress.configure(mode="indeterminate")
        self.grab_progress.start(12)
        self.grab_progress_var.set("")
        self.grab_btn.configure(state="disabled")
        self.grabber_is_running = True
        self.grabber_stop_flag = threading.Event()
        prefix = ytdlp_command_prefix(self.python_exe)
        self.grabber_worker = LinkGrabWorker(
            urls, prefix, self.s, self.grabber_event_queue, self.grabber_stop_flag,
            sections={k: v.get() for k, v in self.grab_sec_vars.items()},
            exclude_members=self.grab_members_var.get(),
            title_lang=self._grab_lang_by_disp.get(self.grab_lang_var.get(), "auto"),
            # item 18: an active min/max duration bound forces the per-video
            # duration probe even if the "Video Duration" output box is off.
            want_duration=(self.grab_duration_var.get()
                           or self._grab_duration_filter_active()))
        self.grabber_worker.start()

    def _poll_grabber_events(self):
        try:
            while True:
                ev = self.grabber_event_queue.get_nowait()
                self._handle_grabber_event(ev)
        except queue.Empty:
            pass
        self.after(150, self._poll_grabber_events)

    def _handle_grabber_event(self, ev):
        kind = ev.get("kind")
        if kind == "grab_log":
            self.grab_status_var.set(ev.get("text", "").strip())
        elif kind == "grab_progress":
            total = ev.get("total", 0)
            done = ev.get("done", 0)
            if total and total > 0:
                if str(self.grab_progress.cget("mode")) != "determinate":
                    self.grab_progress.stop()
                    self.grab_progress.configure(mode="determinate")
                self.grab_progress.configure(maximum=total, value=done)
                self.grab_progress_var.set(f"{done}/{total}")
        elif kind == "grab_done":
            self._grab_entries = self._apply_grab_duration_filter(ev.get("entries", []))
            self.grabber_is_running = False
            self.grab_btn.configure(state="normal")
            self.grab_progress.stop()
            self.grab_progress.configure(mode="determinate")
            n = len(self._grab_entries)
            self.grab_progress.configure(maximum=max(1, n), value=n)
            self.grab_progress_var.set(f"{n}/{n}" if n else "")
            self._render_grab_output()
            if self._grab_entries:
                self.grab_status_var.set(self.t("grab_done_msg", n=n))
            else:
                self.grab_status_var.set(self.t("grab_empty"))
        elif kind == "grab_error":
            self.grabber_is_running = False
            self.grab_btn.configure(state="normal")
            self.grab_progress.stop()
            self.grab_progress.configure(mode="determinate", value=0)
            self.grab_status_var.set(self.t("grab_error"))

    def _grab_copy(self):
        text = self.grab_output.get("1.0", "end").strip()
        if not text:
            return
        self.clipboard_clear()
        self.clipboard_append(text)
        self.grab_status_var.set(self.t("grab_copied"))

    def _grab_save(self):
        text = self.grab_output.get("1.0", "end").strip()
        if not text:
            return
        path = filedialog.asksaveasfilename(
            title=self.t("grab_save"), defaultextension=".txt",
            filetypes=[("Text", "*.txt"), ("All files", "*.*")])
        if not path:
            return
        path = unique_path(path)  # item 16: silent auto-suffix, never overwrite
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text + "\n")
            self.grab_status_var.set(self.t("grab_saved", path=path))
        except OSError as e:
            self.grab_status_var.set(str(e))

    def _grab_save_csv(self):
        if not self._grab_entries:
            return
        path = filedialog.asksaveasfilename(
            title=self.t("grab_save_csv"), defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("All files", "*.*")])
        if not path:
            return
        path = unique_path(path)  # item 16: silent auto-suffix, never overwrite

        def cell(v):
            v = "" if v is None else str(v)
            if any(ch in v for ch in (";", '"', "\n", "\r")):
                v = '"' + v.replace('"', '""') + '"'
            return v

        rows = ["Title;Duration;Link"]
        for e in self._grab_entries:
            title = (e.get("title") or "").strip() or e["id"]
            dur = fmt_hms(e.get("duration")) if e.get("duration") else ""
            rows.append(";".join((cell(title), cell(dur), cell(e["url"]))))
        try:
            with open(path, "w", encoding="utf-8-sig", newline="") as f:
                f.write("\r\n".join(rows) + "\r\n")
            self.grab_status_var.set(self.t("grab_saved", path=path))
        except OSError as e:
            self.grab_status_var.set(str(e))
    def _build_dictionary_tab(self, parent):
        root = ttk.Frame(parent)
        root.pack(fill="both", expand=True)
        root.columnconfigure(1, weight=1)
        root.rowconfigure(0, weight=1)

        left = ttk.LabelFrame(root, text=self.t("saved_profiles"))
        left.grid(row=0, column=0, sticky="ns", padx=8, pady=8)
        self.dict_listbox = tk.Listbox(left, width=26, height=18, exportselection=False)
        self.dict_listbox.pack(fill="both", expand=True, padx=6, pady=6)
        self.dict_listbox.bind("<<ListboxSelect>>", self._on_dict_profile_select)
        lb = ttk.Frame(left)
        lb.pack(fill="x", padx=6, pady=(0, 6))
        ttk.Button(lb, text=self.t("new"), command=self._dict_new).pack(side="left", padx=2)
        ttk.Button(lb, text=self.t("duplicate"), command=self._dict_duplicate).pack(side="left", padx=2)
        ttk.Button(lb, text=self.t("delete"), command=self._dict_delete).pack(side="left", padx=2)

        right = ttk.LabelFrame(root, text=self.t("edit_profile"))
        right.grid(row=0, column=1, sticky="nsew", padx=8, pady=8)
        right.columnconfigure(0, weight=1)
        right.rowconfigure(3, weight=1)
        right.rowconfigure(6, weight=1)
        ttk.Label(right, text=self.t("profile_name")).grid(row=0, column=0, sticky="w", padx=6, pady=(6, 0))
        self.dict_name_var = tk.StringVar()
        ttk.Entry(right, textvariable=self.dict_name_var).grid(row=1, column=0, sticky="ew", padx=6, pady=2)
        ph = ttk.Label(right, text=self.t("priming_help"), foreground="#666", justify="left")
        ph.grid(row=2, column=0, sticky="w", padx=6, pady=(8, 0))
        ph.configure(wraplength=620)
        self.dict_prompt_text = tk.Text(right, height=4, wrap="word")
        self.dict_prompt_text.grid(row=3, column=0, sticky="nsew", padx=6, pady=2)
        rh = ttk.Label(right, text=self.t("replacements_help"), foreground="#666", justify="left")
        rh.grid(row=5, column=0, sticky="w", padx=6, pady=(8, 0))
        rh.configure(wraplength=620)
        self.dict_repl_text = tk.Text(right, height=8, wrap="word")
        self.dict_repl_text.grid(row=6, column=0, sticky="nsew", padx=6, pady=2)
        ttk.Button(right, text=self.t("save_profile"), command=self._dict_save
                   ).grid(row=7, column=0, sticky="e", padx=6, pady=6)
        self._dict_current = None
        self._refresh_dict_listbox()

    # ======================================================================
    # Comparison tab (v0.12.0)
    # ======================================================================
    def _build_comparison_tab(self, parent):
        scroll = ScrollableFrame(parent)
        scroll.pack(fill="both", expand=True)
        root = scroll.inner
        root.columnconfigure(0, weight=1)
        root.rowconfigure(3, weight=1)

        intro = ttk.Label(root, text=self.t("cmp_intro"), foreground="#555")
        intro.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 4))
        intro.configure(wraplength=900)
        self._register_wrap(intro)

        # -- base comparison folder (optional) --
        bf = ttk.LabelFrame(root, text=self.t("cmp_base_folder_frame"))
        bf.grid(row=1, column=0, sticky="ew", padx=8, pady=4)
        bf.columnconfigure(0, weight=1)
        self.cmp_base_folder_var = tk.StringVar(value=self.cfg.get("comparison_base_folder", ""))
        ttk.Entry(bf, textvariable=self.cmp_base_folder_var).grid(
            row=0, column=0, sticky="ew", padx=6, pady=(6, 2))
        ttk.Button(bf, text=self.t("browse"), command=self._comparison_browse_base_folder
                  ).grid(row=0, column=1, padx=6, pady=(6, 2))
        hint = ttk.Label(bf, text=self.t("cmp_base_folder_hint"), foreground="#777")
        hint.grid(row=1, column=0, columnspan=2, sticky="w", padx=6, pady=(0, 6))
        hint.configure(wraplength=900)
        self._register_wrap(hint)

        # -- settings: excerpt length + light model --
        st = ttk.LabelFrame(root, text="")
        st.grid(row=2, column=0, sticky="ew", padx=8, pady=2)
        ttk.Label(st, text=self.t("cmp_excerpt_label")).grid(row=0, column=0, sticky="w", padx=6, pady=6)
        self.cmp_excerpt_var = tk.StringVar(
            value=str(self.cfg.get("comparison_excerpt_seconds", COMPARISON_EXCERPT_SECONDS_DEFAULT)))
        excerpt_spin = ttk.Spinbox(st, from_=COMPARISON_EXCERPT_SECONDS_MIN,
                                   to=COMPARISON_EXCERPT_SECONDS_MAX, width=5,
                                   textvariable=self.cmp_excerpt_var,
                                   command=self._comparison_commit_excerpt_setting)
        excerpt_spin.grid(row=0, column=1, padx=4, pady=6)
        excerpt_spin.bind("<FocusOut>", lambda e: self._comparison_commit_excerpt_setting())
        excerpt_spin.bind("<KeyRelease>", lambda e: self._comparison_refresh_excerpt_live_label())
        self.cmp_excerpt_live_var = tk.StringVar(value="")
        ttk.Label(st, textvariable=self.cmp_excerpt_live_var, foreground="#666"
                 ).grid(row=0, column=2, sticky="w", padx=(10, 6), pady=6)

        ttk.Label(st, text=self.t("cmp_model_label")).grid(row=1, column=0, sticky="w", padx=6, pady=(0, 6))
        light_models = ["tiny", "base", "small"]
        saved_model = self.cfg.get("comparison_model_cli", "tiny")
        self.cmp_model_var = tk.StringVar(value=saved_model if saved_model in light_models else "tiny")
        model_combo = ttk.Combobox(st, textvariable=self.cmp_model_var, state="readonly",
                                   width=8, values=light_models)
        model_combo.grid(row=1, column=1, sticky="w", padx=4, pady=(0, 6))
        model_combo.bind("<<ComboboxSelected>>", lambda e: self._comparison_on_model_change())

        short_note = ttk.Label(st, text=self.t("cmp_excerpt_live_line_short_note"), foreground="#777")
        short_note.grid(row=2, column=0, columnspan=3, sticky="w", padx=6, pady=(0, 6))
        self._register_wrap(short_note)
        self._comparison_refresh_excerpt_live_label()

        # -- queue --
        qf = ttk.LabelFrame(root, text=self.t("cmp_queue_frame"))
        qf.grid(row=3, column=0, sticky="nsew", padx=8, pady=4)
        qf.columnconfigure(0, weight=1)
        qf.rowconfigure(1, weight=1)
        qbtns = ttk.Frame(qf)
        qbtns.grid(row=0, column=0, sticky="ew", padx=4, pady=4)
        ttk.Button(qbtns, text=self.t("btn_add"), command=self._comparison_add_files
                  ).pack(side="left", padx=2)
        ttk.Button(qbtns, text=self.t("remove_selected"), command=self._comparison_remove_selected
                  ).pack(side="left", padx=2)
        ttk.Button(qbtns, text=self.t("move_up"), command=lambda: self._comparison_move_selected(-1)
                  ).pack(side="left", padx=2)
        ttk.Button(qbtns, text=self.t("move_down"), command=lambda: self._comparison_move_selected(1)
                  ).pack(side="left", padx=2)
        ttk.Button(qbtns, text=self.t("clear_queue"), command=self._comparison_clear_queue
                  ).pack(side="left", padx=2)

        wrap, self.comparison_tree, _cmp_vsb = make_scrollable_queue(
            qf, columns=("order", "file", "folder", "length", "status"), height=8)
        wrap.grid(row=1, column=0, sticky="nsew", padx=4, pady=(0, 4))
        self.comparison_tree.heading("order", text=self.t("col_order"))
        self.comparison_tree.heading("file", text=self.t("col_file"))
        self.comparison_tree.heading("folder", text=self.t("col_folder"))
        self.comparison_tree.heading("length", text=self.t("col_length"))
        self.comparison_tree.heading("status", text=self.t("col_status"))
        self.comparison_tree.column("order", width=40, anchor="center")
        self.comparison_tree.column("file", width=220, anchor="w")
        self.comparison_tree.column("folder", width=260, anchor="w")
        self.comparison_tree.column("length", width=70, anchor="center")
        self.comparison_tree.column("status", width=130, anchor="w")
        bind_queue_delete_key(self.comparison_tree, self._comparison_remove_selected)

        # -- check/cancel --
        actions = ttk.Frame(root)
        actions.grid(row=4, column=0, sticky="ew", padx=8, pady=(0, 4))
        self.cmp_check_btn = ttk.Button(actions, text=self.t("cmp_check_button"),
                                        command=self._start_comparison_check)
        self.cmp_check_btn.pack(side="left", padx=2)
        self.cmp_cancel_btn = ttk.Button(actions, text=self.t("cancel"),
                                         command=self._cancel_comparison_check, state="disabled")
        self.cmp_cancel_btn.pack(side="left", padx=2)

        # -- log --
        logf = ttk.LabelFrame(root, text=self.t("cmp_log_frame"))
        logf.grid(row=5, column=0, sticky="nsew", padx=8, pady=4)
        logf.columnconfigure(0, weight=1)
        self.cmp_log_text = tk.Text(logf, height=6, wrap="word", state="disabled",
                                    font=("TkFixedFont", 9))
        cmp_logsb = ttk.Scrollbar(logf, orient="vertical", command=self.cmp_log_text.yview)
        self.cmp_log_text.configure(yscrollcommand=cmp_logsb.set)
        self.cmp_log_text.grid(row=0, column=0, sticky="nsew", padx=(4, 0), pady=4)
        cmp_logsb.grid(row=0, column=1, sticky="ns", pady=4)

        # -- results --
        resf = ttk.LabelFrame(root, text=self.t("cmp_results_frame"))
        resf.grid(row=6, column=0, sticky="nsew", padx=8, pady=(4, 12))
        resf.columnconfigure(0, weight=1)

        self.cmp_no_results_label = ttk.Label(resf, text=self.t("cmp_no_results_yet"), foreground="#777")
        self.cmp_no_results_label.grid(row=0, column=0, sticky="w", padx=6, pady=6)
        self.cmp_partial_label = ttk.Label(resf, text=self.t("cmp_partial_note"), foreground="#b35c00")
        self.cmp_partial_label.grid(row=0, column=0, sticky="w", padx=6, pady=6)

        bmf = ttk.LabelFrame(resf, text=self.t("cmp_base_matches_frame"))
        self.cmp_base_matches_frame_widget = bmf
        bmf.grid(row=1, column=0, sticky="nsew", padx=6, pady=4)
        bmf.columnconfigure(0, weight=1)
        self.cmp_matches_tree = ttk.Treeview(
            bmf, columns=("file", "candidate", "confidence", "points", "tier"),
            show="headings", height=6, selectmode="extended")
        for col, key in (("file", "col_file"), ("candidate", "col_cmp_candidate"),
                         ("confidence", "col_cmp_confidence"), ("points", "col_cmp_points"),
                         ("tier", "col_cmp_tier")):
            self.cmp_matches_tree.heading(col, text=self.t(key))
        self.cmp_matches_tree.column("file", width=170, anchor="w")
        self.cmp_matches_tree.column("candidate", width=260, anchor="w")
        self.cmp_matches_tree.column("confidence", width=80, anchor="center")
        self.cmp_matches_tree.column("points", width=110, anchor="center")
        self.cmp_matches_tree.column("tier", width=190, anchor="w")
        self.cmp_matches_tree.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        matches_vsb = ttk.Scrollbar(bmf, orient="vertical", command=self.cmp_matches_tree.yview)
        self.cmp_matches_tree.configure(yscrollcommand=matches_vsb.set)
        matches_vsb.grid(row=0, column=1, sticky="ns", pady=4)
        self.cmp_matches_tree.bind("<<TreeviewSelect>>", self._comparison_on_match_select)
        self.cmp_no_matches_label = ttk.Label(bmf, text=self.t("cmp_no_matches_found"), foreground="#777")
        self.cmp_no_matches_label.grid(row=1, column=0, columnspan=2, sticky="w", padx=4, pady=(0, 2))
        ttk.Button(bmf, text=self.t("cmp_remove_selected_matches"),
                  command=self._comparison_remove_selected_matches
                  ).grid(row=2, column=0, columnspan=2, sticky="w", padx=4, pady=(0, 6))

        prevf = ttk.LabelFrame(resf, text=self.t("cmp_preview_frame"))
        prevf.grid(row=2, column=0, sticky="nsew", padx=6, pady=4)
        prevf.columnconfigure(0, weight=1)
        prevf.columnconfigure(1, weight=1)
        ttk.Label(prevf, text=self.t("cmp_preview_excerpt_label")).grid(row=0, column=0, sticky="w", padx=4)
        ttk.Label(prevf, text=self.t("cmp_preview_candidate_label")).grid(row=0, column=1, sticky="w", padx=4)
        self.cmp_preview_left = tk.Text(prevf, height=5, wrap="word", state="disabled",
                                        font=("TkDefaultFont", 9))
        self.cmp_preview_left.grid(row=1, column=0, sticky="nsew", padx=4, pady=(0, 4))
        self.cmp_preview_right = tk.Text(prevf, height=5, wrap="word", state="disabled",
                                         font=("TkDefaultFont", 9))
        self.cmp_preview_right.grid(row=1, column=1, sticky="nsew", padx=4, pady=(0, 4))
        self.cmp_preview_hint = ttk.Label(prevf, text=self.t("cmp_select_row_hint"), foreground="#777")
        self.cmp_preview_hint.grid(row=2, column=0, columnspan=2, sticky="w", padx=4, pady=(0, 6))

        # v0.12.1 (A1): the interactive keep/remove cluster UI is gone —
        # duplicates are now a read-only summary line; full detail (member
        # filenames + pairwise scores) lives only in the report.
        dupf = ttk.LabelFrame(resf, text=self.t("cmp_duplicates_frame"))
        dupf.grid(row=3, column=0, sticky="nsew", padx=6, pady=4)
        dupf.columnconfigure(0, weight=1)
        self.cmp_duplicates_summary_var = tk.StringVar(value="")
        ttk.Label(dupf, textvariable=self.cmp_duplicates_summary_var
                 ).grid(row=0, column=0, sticky="w", padx=6, pady=6)

        ttk.Button(resf, text=self.t("cmp_export_button"), command=self._comparison_export_report
                  ).grid(row=4, column=0, sticky="w", padx=6, pady=(2, 6))

        self._render_comparison_queue()
        self._render_comparison_results()

    # ---- settings handlers -------------------------------------------------
    def _comparison_refresh_excerpt_live_label(self):
        if not hasattr(self, "cmp_excerpt_live_var"):
            return
        try:
            secs = int(float(self.cmp_excerpt_var.get()))
        except (TypeError, ValueError):
            secs = COMPARISON_EXCERPT_SECONDS_DEFAULT
        secs = max(COMPARISON_EXCERPT_SECONDS_MIN, min(COMPARISON_EXCERPT_SECONDS_MAX, secs))
        total, n_points = comparison_excerpt_total_seconds(secs)
        self.cmp_excerpt_live_var.set(self.t("cmp_excerpt_live_line", total=total,
                                             minutes=f"{total / 60:.1f}", points=n_points))

    def _comparison_commit_excerpt_setting(self):
        try:
            secs = int(float(self.cmp_excerpt_var.get()))
        except (TypeError, ValueError):
            secs = COMPARISON_EXCERPT_SECONDS_DEFAULT
        secs = max(COMPARISON_EXCERPT_SECONDS_MIN, min(COMPARISON_EXCERPT_SECONDS_MAX, secs))
        self.cmp_excerpt_var.set(str(secs))
        self._comparison_refresh_excerpt_live_label()
        self.cfg["comparison_excerpt_seconds"] = secs
        self._save_config()

    def _comparison_on_model_change(self):
        self.cfg["comparison_model_cli"] = self.cmp_model_var.get()
        self._save_config()

    def _comparison_browse_base_folder(self):
        d = filedialog.askdirectory(
            title=self.t("cmp_base_folder_frame"),
            initialdir=self._existing_dir_or_home(self.cmp_base_folder_var.get()))
        if d:
            self.cmp_base_folder_var.set(d)
            self.cfg["comparison_base_folder"] = d
            self._save_config()

    # ---- queue operations ---------------------------------------------------
    def _comparison_add_files(self):
        if self.comparison_is_running:
            messagebox.showwarning(self.t("warn"), self.t("warn_queue_locked"))
            return
        paths = filedialog.askopenfilenames(
            title=self.t("select_media_title"),
            filetypes=[(self.t("media_files"), " ".join("*" + e for e in MEDIA_EXTENSIONS)),
                       (self.t("all_files"), "*.*")])
        if not paths:
            return
        existing = {it.filepath for it in self.comparison_queue_items}
        new_items = []
        for p in paths:
            if p in existing:
                continue
            it = QueueItem(p)
            self.comparison_queue_items.append(it)
            new_items.append(it)
        self._render_comparison_queue()
        if new_items:
            self._probe_media_lengths(new_items, target="comparison")

    def _comparison_remove_selected(self):
        if self.comparison_is_running:
            messagebox.showwarning(self.t("warn"), self.t("warn_queue_locked"))
            return
        ids = {int(iid) for iid in self.comparison_tree.selection()}
        if not ids:
            return
        self.comparison_queue_items = [it for it in self.comparison_queue_items
                                       if it.item_id not in ids]
        self._render_comparison_queue()

    def _comparison_clear_queue(self):
        if self.comparison_is_running:
            messagebox.showwarning(self.t("warn"), self.t("warn_queue_locked"))
            return
        self.comparison_queue_items = []
        self._render_comparison_queue()

    def _comparison_move_selected(self, direction):
        if self.comparison_is_running:
            return
        sel = self.comparison_tree.selection()
        if not sel:
            return
        moving_id = int(sel[0])
        by_id = {it.item_id: i for i, it in enumerate(self.comparison_queue_items)}
        idx = by_id.get(moving_id)
        if idx is None:
            return
        new = idx + direction
        if not (0 <= new < len(self.comparison_queue_items)):
            return
        items = self.comparison_queue_items
        items[idx], items[new] = items[new], items[idx]
        self._render_comparison_queue()
        self.comparison_tree.selection_set(str(moving_id))

    def _comparison_status_text(self, status):
        """v0.13.10: full flow, per explicit spec after real hands-on
        testing — "Transcribing..." (was "Checking...") while sampling
        runs; "Transcribed" once THIS file's own sampling is done but
        Phase 2 (a genuinely batch operation — see ST_TRANSCRIBED's own
        comment) hasn't started for the batch yet; "Comparing..." once
        it has; "Done" once Phase 2 is fully finished for the batch."""
        if status == ST_RUNNING:
            return self.t("cmp_status_running")
        if status == ST_TRANSCRIBED:
            return self.t("cmp_status_transcribed")
        if status == ST_COMPARING:
            return self.t("cmp_status_comparing")
        if status == ST_DONE:
            return self.t("cmp_status_finished")
        return {ST_PENDING: self.t("status_pending"),
                ST_ERROR: self.t("status_error"),
                ST_SKIPPED: self.t("status_skipped")}.get(status, status)

    def _render_comparison_queue(self):
        if not hasattr(self, "comparison_tree"):
            return
        def populate():
            self.comparison_tree.delete(*self.comparison_tree.get_children())
            for i, it in enumerate(self.comparison_queue_items):
                length = fmt_hms(it.duration) if it.duration else "…"
                self.comparison_tree.insert(
                    "", "end", iid=str(it.item_id),
                    values=(i + 1, it.filename, os.path.dirname(it.filepath),
                            length, self._comparison_status_text(it.status)))
        render_queue_preserving_selection(self.comparison_tree, populate)

    # ---- start / cancel / model preflight -----------------------------------
    def _comparison_check_stale_safety_net(self):
        """A3: warn before a new run silently overwrites a safety-net
        report from a previous run that didn't finish cleanly."""
        path = str(COMPARISON_SAFETY_NET_FILE)
        status = read_comparison_safety_status(path)
        if status in _COMPARISON_SAFETY_UNFINISHED:
            return messagebox.askyesno(self.t("warn"),
                                       self.t("cmp_stale_safety_net_warn", path=path))
        return True

    def _start_comparison_check(self):
        if self.comparison_is_running:
            return
        base_folder = self.cmp_base_folder_var.get().strip()
        has_base_folder = bool(base_folder) and os.path.isdir(base_folder)
        scenario3 = not self.comparison_queue_items and has_base_folder
        if not self.comparison_queue_items and not has_base_folder:
            messagebox.showerror(self.t("error"), self.t("err_no_files"))
            return
        if not self._comparison_check_stale_safety_net():
            return
        if scenario3:
            # Scenario 3 (A4): Base Folder only, no whisper/ffmpeg needed at
            # all — skip the model preflight entirely.
            self._comparison_launch_worker(None)
            return
        readiness = self._whisper_readiness()
        if readiness != "ready":
            messagebox.showerror(
                self.t("error"),
                self.t("err_whisper_broken") if readiness == "broken"
                else self.t("err_no_whisper"))
            self._open_whisper_settings()
            return
        if not self.ffmpeg_path:
            messagebox.showerror(self.t("error"), self.t("cmp_err_no_ffmpeg"))
            return
        model_cli = self.cmp_model_var.get() or "tiny"
        downloaded, _path = is_model_downloaded(model_cli)
        if downloaded:
            self._comparison_launch_worker(model_cli)
            return
        info = MODEL_INFO.get(model_cli, {})
        if not messagebox.askyesno(
                self.t("confirm"),
                self.t("cmp_model_missing_confirm", model=model_cli,
                       size=human_size(info.get("size_mb", 0)))):
            return   # item 0 / Phase 1 step 0: decline aborts the whole Check, no partial batch
        self._comparison_download_model_then_start(model_cli)

    def _comparison_download_model_then_start(self, model_cli):
        info = MODEL_INFO.get(model_cli, {})
        self._append_text(self.cmp_log_text, self.t("log_download_start", model=model_cli,
                                                     size=human_size(info.get("size_mb", 0))))
        self.cmp_check_btn.configure(state="disabled")
        stop = threading.Event()
        q = queue.Queue()
        worker = ModelDownloadWorker(self.whisper_path, model_cli, q, stop)
        worker.start()

        def done(success, error):
            if success:
                self._comparison_launch_worker(model_cli)
            else:
                self._append_text(self.cmp_log_text, f"\n[ERROR] {error}\n")
                self.cmp_check_btn.configure(state="normal")
        self._attach_stream(q, self.cmp_log_text, done)

    def _comparison_launch_worker(self, model_cli):
        for it in self.comparison_queue_items:
            it.status = ST_PENDING
            it.error_message = ""
        self._render_comparison_queue()
        self._comparison_base_matches = {}
        self._comparison_pair_results = []
        self._comparison_clusters = []
        self._comparison_id_to_name = {}
        self._comparison_ran_once = False
        self._comparison_partial = False
        self._render_comparison_results()

        prompt, _replacements = self._selected_dictionary_payload()
        lang_param = audio_lang_param(self.cfg.get("audio_lang_code", "pt"))
        base_folder = self.cmp_base_folder_var.get().strip()
        self.cfg["comparison_base_folder"] = base_folder
        if model_cli:
            self.cfg["comparison_model_cli"] = model_cli
        self._save_config()

        self.comparison_stop_flag = threading.Event()
        self.comparison_live_queue = LiveQueue(self.comparison_queue_items)
        self.comparison_worker = ComparisonWorker(
            live_queue=self.comparison_live_queue, whisper_exe=self.whisper_path,
            ffmpeg_path=self.ffmpeg_path, model_cli=model_cli or "tiny", lang_param=lang_param,
            initial_prompt=prompt, base_folder=base_folder,
            excerpt_seconds=int(self.cfg.get("comparison_excerpt_seconds",
                                             COMPARISON_EXCERPT_SECONDS_DEFAULT)),
            likely_threshold=COMPARISON_LIKELY_THRESHOLD_DEFAULT,
            possible_threshold=COMPARISON_POSSIBLE_THRESHOLD_DEFAULT,
            duration_tolerance=COMPARISON_DURATION_TOLERANCE_DEFAULT,
            strings=self.s, event_queue=self.comparison_event_queue,
            stop_flag=self.comparison_stop_flag, temp_root=str(COMPARISON_TEMP_DIR),
            base_index_cache=self._comparison_base_index_cache,
            safety_net_path=str(COMPARISON_SAFETY_NET_FILE))
        self.comparison_is_running = True
        self._clear_log(self.cmp_log_text)
        self._append_text(self.cmp_log_text,
                          self.t("log_batch_start", time=datetime.now().strftime("%H:%M:%S")))
        self._set_comparison_running_ui(True)
        self.comparison_worker.start()

    def _cancel_comparison_check(self):
        if self.comparison_is_running and self.comparison_worker:
            if messagebox.askyesno(self.t("cancel_title"), self.t("cancel_question")):
                self._append_text(self.cmp_log_text, self.t("log_canceling"))
                self.comparison_worker.cancel()

    def _set_comparison_running_ui(self, running):
        self.cmp_check_btn.configure(state="disabled" if running else "normal")
        self.cmp_cancel_btn.configure(state="normal" if running else "disabled")

    def _poll_comparison_events(self):
        try:
            while True:
                ev = self.comparison_event_queue.get_nowait()
                self._handle_comparison_event(ev)
        except queue.Empty:
            pass
        self.after(120, self._poll_comparison_events)

    def _handle_comparison_event(self, ev):
        kind = ev.get("kind")
        if kind == "log":
            self._append_text(self.cmp_log_text, ev.get("text", ""))
        elif kind == "item_status":
            item_id = ev.get("item_id")
            status = ev.get("status")
            it = next((q for q in self.comparison_queue_items if q.item_id == item_id), None)
            if it is not None:
                it.status = status
                if ev.get("error"):
                    it.error_message = ev.get("error")
                try:
                    self.comparison_tree.set(str(item_id), "status",
                                             self._comparison_status_text(status))
                except tk.TclError:
                    pass   # row may have been removed from the tree already
        elif kind == "base_index_built":
            # v0.12.1: cache the Base Folder index for the next Check click
            # in this session (App-level storage; the worker only decides
            # whether to reuse it, via the signature it was handed).
            self._comparison_base_index_cache = (
                ev.get("signature"), ev.get("candidates"), ev.get("word_index"))
        elif kind == "comparison_results":
            self._comparison_base_matches = ev.get("base_matches", {})
            self._comparison_pair_results = ev.get("pair_results", [])
            self._comparison_clusters = ev.get("clusters", [])
            self._comparison_id_to_name = ev.get("id_to_name", {})
            self._comparison_partial = ev.get("partial", False)
            self._comparison_scenario = "media" if self.comparison_queue_items else "md_only"
            self._comparison_ran_once = True
            self._render_comparison_results()
        elif kind == "batch_finished":
            self.comparison_is_running = False
            self._set_comparison_running_ui(False)
            if ev.get("env_broken"):
                messagebox.showerror(self.t("error"), self.t("err_whisper_broken"))
                self._open_whisper_settings()

    # ---- results rendering ---------------------------------------------------
    def _render_comparison_results(self):
        if not hasattr(self, "cmp_matches_tree"):
            return
        if not self._comparison_ran_once:
            self.cmp_no_results_label.grid()
            self.cmp_partial_label.grid_remove()
            self.cmp_base_matches_frame_widget.grid()
            self.cmp_no_matches_label.grid_remove()
            self.cmp_matches_tree.delete(*self.cmp_matches_tree.get_children())
            self.cmp_duplicates_summary_var.set("")
            self._comparison_clear_preview()
            return
        self.cmp_no_results_label.grid_remove()
        if self._comparison_partial:
            self.cmp_partial_label.grid()
        else:
            self.cmp_partial_label.grid_remove()

        id_to_name = self._comparison_id_to_name
        # Scenario 3 (Base Folder vs. itself) has no queue files, so the
        # "Base Folder Matches" section (which is inherently about queue
        # file vs. candidate) doesn't apply — hide it rather than show an
        # always-empty table.
        if self._comparison_scenario == "md_only":
            self.cmp_base_matches_frame_widget.grid_remove()
        else:
            self.cmp_base_matches_frame_widget.grid()

        # -- base folder matches: one row per queue file, its top candidate --
        self.cmp_matches_tree.delete(*self.cmp_matches_tree.get_children())
        tier_labels = {COMPARISON_TIER_LIKELY: self.t("cmp_tier_likely"),
                      COMPARISON_TIER_POSSIBLE: self.t("cmp_tier_possible"),
                      COMPARISON_TIER_NONE: self.t("cmp_tier_none")}
        likely_ids, any_matches = [], False
        for item_id, matches in self._comparison_base_matches.items():
            name = id_to_name.get(item_id)
            if name is None or not matches:
                continue
            any_matches = True
            rel_path, score, agreeing, tier = matches[0][0], matches[0][1], matches[0][2], matches[0][3]
            self.cmp_matches_tree.insert(
                "", "end", iid=str(item_id),
                values=(name, rel_path, f"{score * 100:.0f}%", agreeing,
                        tier_labels.get(tier, tier)))
            if tier == COMPARISON_TIER_LIKELY:
                likely_ids.append(str(item_id))
        if likely_ids:
            self.cmp_matches_tree.selection_set(likely_ids)
        if any_matches:
            self.cmp_no_matches_label.grid_remove()
        else:
            self.cmp_no_matches_label.grid()

        # -- duplicates: read-only summary (A1) — full detail is in the
        # report; the interactive keep/remove UI was removed in v0.12.1,
        # since the workflow is now "check the report, manage files
        # yourself outside the app".
        if self._comparison_clusters:
            self.cmp_duplicates_summary_var.set(
                self.t("cmp_duplicates_summary", n=len(self._comparison_clusters)))
        else:
            self.cmp_duplicates_summary_var.set(self.t("cmp_no_duplicates_found"))

        self._comparison_clear_preview()

    def _comparison_set_preview_text(self, widget, text):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text or "")
        widget.configure(state="disabled")

    def _comparison_clear_preview(self):
        if not hasattr(self, "cmp_preview_left"):
            return
        self._comparison_set_preview_text(self.cmp_preview_left, "")
        self._comparison_set_preview_text(self.cmp_preview_right, "")
        self.cmp_preview_hint.grid()

    def _comparison_on_match_select(self, _event=None):
        sel = self.cmp_matches_tree.selection()
        if not sel:
            return
        focus = self.cmp_matches_tree.focus()
        item_id = int(focus) if focus else int(sel[-1])
        matches = self._comparison_base_matches.get(item_id)
        if not matches:
            return
        _rel_path, _score, _agreeing, _tier, excerpt, window = matches[0]
        self._comparison_set_preview_text(self.cmp_preview_left, excerpt)
        self._comparison_set_preview_text(self.cmp_preview_right, window)
        self.cmp_preview_hint.grid_remove()

    def _comparison_remove_selected_matches(self):
        ids = {int(iid) for iid in self.cmp_matches_tree.selection()}
        if not ids:
            return
        self.comparison_queue_items = [it for it in self.comparison_queue_items
                                       if it.item_id not in ids]
        for item_id in ids:
            self._comparison_base_matches.pop(item_id, None)
        self._render_comparison_queue()
        self._render_comparison_results()

    def _comparison_export_report(self):
        if not self._comparison_ran_once:
            messagebox.showinfo(self.t("info"), self.t("cmp_no_results_yet"))
            return
        path = filedialog.asksaveasfilename(
            title=self.t("cmp_export_title"), defaultextension=".md",
            filetypes=[("Markdown", "*.md"), (self.t("all_files"), "*.*")])
        if not path:
            return
        # Same shared builder the worker's crash-safety net uses (A3), so
        # a manual export and the safety net can never drift apart.
        status_line = self.t("cmp_partial_note") if self._comparison_partial else None
        text = build_comparison_report_text(
            self.s, status_line, self._comparison_base_matches,
            self._comparison_pair_results, self._comparison_clusters,
            self._comparison_id_to_name)
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
        except OSError as e:
            messagebox.showerror(self.t("error"), str(e))
            return
        messagebox.showinfo(self.t("info"), self.t("cmp_export_success", path=path))

    # ======================================================================
    # Refresh / state
    # ======================================================================
    def _refresh_status_indicators(self):
        def style(label, name_key, ok):
            mark = self.t("dep_found") if ok else self.t("dep_missing")
            label.configure(text=f"{self.t(name_key)} {mark}",
                            fg=("#1a7f37" if ok else "#cf222e"))
        style(self.ind_whisper, "dep_whisper", bool(self.whisper_path))
        style(self.ind_ffmpeg, "dep_ffmpeg", bool(self.ffmpeg_path))
        # v0.13.8: this indicator now reflects whichever model is
        # actually selected (AV/YouTube tabs route through it — see the
        # "override the bypass for these 2 tabs" decision) instead of
        # always meaning "is MarkItDown specifically installed".
        active_model = self._active_model()
        active_ok = self._model_installed(active_model)
        mark = self.t("dep_found") if active_ok else self.t("dep_missing")
        label_text = f"MD Converter ({conversion_model_display_name(active_model)}) {mark}"
        color = "#1a7f37" if active_ok else "#cf222e"
        self.ind_markitdown.configure(text=label_text, fg=color)
        if hasattr(self, "yt_ind_markitdown"):
            self.yt_ind_markitdown.configure(text=label_text, fg=color)
        if hasattr(self, "md_model_line_var"):
            self._refresh_md_model_line()
        self._refresh_youtube_enabled()
        self._refresh_download_enabled()

    def _installed_tool_versions(self):
        """v0.13.6: local-only (no network) snapshot of each managed
        tool's CURRENTLY installed version, for the About dialog. Same
        resolution each tool's own Settings dialog and Check for All
        Tools Update already use, just without the "is there something
        newer" network call — this is purely "what do I have right now"."""
        return [
            ("MarkItDown", get_pip_package_version(markitdown_python(self.cfg), "markitdown")),
            ("yt-dlp", get_pip_package_version(tools_venv_python(), "yt-dlp")),
            ("youtube-transcript-api", get_pip_package_version(
                markitdown_python(self.cfg), "youtube-transcript-api")),
            ("Whisper", get_pip_package_version(
                venv_python(whisper_env_dir_from_cfg(self.cfg)), "openai-whisper")),
            ("FFmpeg", get_ffmpeg_version(self.ffmpeg_path)),
        ]

    def _refresh_audio_lang_dropdown(self):
        codes = self.cfg.get("audio_langs", list(DEFAULT_AUDIO_LANGS))
        displays = [self._audio_lang_display(c) for c in codes]
        self._audio_code_by_display = dict(zip(displays, codes))
        self.audio_lang_combo["values"] = displays
        cur = self.cfg.get("audio_lang_code", "pt")
        if cur not in codes:
            cur = codes[0] if codes else "pt"
            self.cfg["audio_lang_code"] = cur
        self.audio_lang_var.set(self._audio_lang_display(cur))

    def _refresh_model_dropdown(self):
        code = self.cfg.get("audio_lang_code", "pt")
        installed = models_for_audio_language(code, only_installed=True)
        displays = [self._model_display(c) for c in installed]
        self._model_cli_by_display = dict(zip(displays, installed))
        self.model_combo["values"] = displays
        cur = self.cfg.get("model_cli", "turbo")
        if cur not in installed:
            cur = installed[0] if installed else cur
            self.cfg["model_cli"] = cur
        if installed:
            self.model_combo.set(self._model_display(cur))
        else:
            self.model_combo.set("")
        self._refresh_model_status_label()

    def _refresh_model_status_label(self):
        installed = models_for_audio_language(
            self.cfg.get("audio_lang_code", "pt"), only_installed=True)
        if not installed:
            self.model_status_var.set(self.t("no_models_installed"))
            return
        cli = self.cfg.get("model_cli", "turbo")
        info = MODEL_INFO.get(cli, MODEL_INFO["turbo"])
        downloaded, _ = is_model_downloaded(cli)
        size = human_size(info["size_mb"])
        if downloaded:
            self.model_status_var.set(self.t("model_status") + " " +
                                      self.t("model_downloaded", size=size, vram=info["vram_gb"]))
        else:
            self.model_status_var.set(self.t("model_status") + " " +
                                      self.t("model_not_downloaded", size=size, vram=info["vram_gb"]))

    def _refresh_dictionary_dropdown(self):
        names = [self.t("none")] + sorted(self.dictionaries.keys())
        self.dict_combo["values"] = names
        sel = self.cfg.get("selected_dictionary", "")
        if sel and sel in self.dictionaries:
            self.dict_var.set(sel)
        else:
            self.dict_var.set(self.t("none"))

    def _update_clip_gate(self):
        has_ffmpeg = bool(self.ffmpeg_path)
        enabled = self.clip_enabled_var.get() and has_ffmpeg
        state = "normal" if (has_ffmpeg) else "disabled"
        try:
            self.clip_check.configure(state="normal" if has_ffmpeg else "disabled")
            entry_state = "normal" if enabled else "disabled"
            self.clip_start_entry.configure(state=entry_state)
            self.clip_end_entry.configure(state=entry_state)
            if not has_ffmpeg:
                self.clip_enabled_var.set(False)
                self.clip_hint_label.configure(text=self.t("clip_needs_ffmpeg"))
            else:
                self.clip_hint_label.configure(text=self.t("clip_hint"))
        except (AttributeError, tk.TclError):
            pass

    # ======================================================================
    # Change handlers
    # ======================================================================
    def _on_audio_lang_change(self, _event=None):
        disp = self.audio_lang_var.get()
        code = getattr(self, "_audio_code_by_display", {}).get(disp)
        if code:
            self.cfg["audio_lang_code"] = code
            self._save_config()
            self._refresh_model_dropdown()

    def _on_model_change(self, _event=None):
        disp = self.model_var.get()
        cli = getattr(self, "_model_cli_by_display", {}).get(disp)
        if cli:
            self.cfg["model_cli"] = cli
            self._save_config()
            self._refresh_model_status_label()

    def _on_task_change(self, _event=None):
        idx = self.task_combo.current()
        self.cfg["task"] = "translate" if idx == 1 else "transcribe"
        self._save_config()

    def _on_outdir_mode_change(self):
        self.cfg["output_dir_mode"] = self.outdir_mode_var.get()
        self._save_config()

    def _browse_fixed_dir(self):
        d = filedialog.askdirectory(
            title=self.t("select_output_title"),
            initialdir=self._existing_dir_or_home(self.fixed_dir_var.get()))
        if d:
            self.fixed_dir_var.set(d)
            self.cfg["fixed_output_dir"] = d
            self.outdir_mode_var.set("fixed")
            self.cfg["output_dir_mode"] = "fixed"
            self._save_config()

    def _browse_md_fixed_dir(self):
        d = filedialog.askdirectory(
            title=self.t("select_output_title"),
            initialdir=self._existing_dir_or_home(self.md_fixed_dir_var.get()))
        if d:
            self.md_fixed_dir_var.set(d)
            self.md_outdir_mode_var.set("fixed")

    # ======================================================================
    # Queue operations (transcription)
    # ======================================================================
    def _add_files(self):
        if not self._gate_finished_queue(
                "av", bool(self.queue_items), self._clear_queue,
                keep_fn=lambda: (self._reset_errored_to_pending(self.queue_items),
                                 self._render_queue())):
            return
        paths = filedialog.askopenfilenames(
            title=self.t("select_media_title"),
            filetypes=[(self.t("media_files"), " ".join("*" + e for e in MEDIA_EXTENSIONS)),
                       (self.t("all_files"), "*.*")])
        if not paths:
            return
        existing = {it.filepath for it in self.queue_items}
        candidate_paths = [p for p in paths if p not in existing]
        if paths and not candidate_paths:
            messagebox.showinfo(self.t("info"), self.t("info_all_in_queue"))
            return
        accepted_paths, overrides = self._resolve_duplicate_transcripts(candidate_paths)
        added = 0
        new_items = []
        for p in accepted_paths:
            it = QueueItem(p)
            if p in overrides:
                it.output_stem_override = overrides[p]
            if self.is_running and getattr(self, "live_queue", None) is not None:
                self.live_queue.add(it)   # locked: safe while worker reads
            else:
                self.queue_items.append(it)
            new_items.append(it)
            added += 1
        self._render_queue()
        self._update_trans_summary()
        if new_items:
            self._probe_media_lengths(new_items)
            if self.is_running:
                self._recompute_trans_total_seconds()

    def _recompute_trans_total_seconds(self):
        """Re-sum known durations across the live queue; called after a
        mid-batch add so percent/ETA reflect the new total (item 1)."""
        total, n_known, total_seconds = queue_length_summary(self.queue_items)
        self._trans_total_seconds = total_seconds

    def _resolve_duplicate_transcripts(self, paths):
        """item 16: files that already have a transcript next to them are
        silently auto-suffixed (_1, _2, ...) rather than shown a
        skip/proceed/cancel confirmation dialog. Returns (accepted_paths,
        overrides) where overrides maps filepath -> forced output stem."""
        overrides = {}
        for p in paths:
            if find_existing_transcripts(p):
                overrides[p] = next_available_suffixed_stem(p)
        return paths, overrides

    def _remove_selected(self):
        locked_selected = False
        ids_to_remove = []
        by_id = {it.item_id: it for it in self.queue_items}
        for iid in self.tree.selection():
            it = by_id.get(int(iid))
            if it is None:
                continue
            if self.is_running and it.status != ST_PENDING:
                locked_selected = True
                continue
            ids_to_remove.append(it.item_id)
        for item_id in ids_to_remove:
            if self.is_running and getattr(self, "live_queue", None) is not None:
                self.live_queue.remove(item_id)   # locked: safe while worker reads
            else:
                self.queue_items = [it for it in self.queue_items
                                    if it.item_id != item_id]
        if ids_to_remove:
            self._render_queue()
            self._update_trans_summary()
            if self.is_running:
                self._recompute_trans_total_seconds()
        if locked_selected:
            messagebox.showwarning(self.t("warn"), self.t("warn_item_locked"))

    def _clear_queue(self):
        if self.is_running:
            # Button is disabled while running; this is a defensive fallback.
            messagebox.showwarning(self.t("warn"), self.t("warn_queue_locked"))
            return
        self.queue_items = []
        self._render_queue()
        self._update_trans_summary()

    def _move_selected(self, direction):
        sel = self.tree.selection()
        if not sel:
            return
        moving_id = int(sel[0])
        if self.is_running and getattr(self, "live_queue", None) is not None:
            moved = self.live_queue.move(moving_id, direction)
            if not moved:
                target = next((it for it in self.queue_items if it.item_id == moving_id), None)
                if target is not None and target.status != ST_PENDING:
                    messagebox.showwarning(self.t("warn"), self.t("warn_item_locked"))
                return
            self._render_queue()
            self.tree.selection_set(str(moving_id))
            return
        by_id = {it.item_id: i for i, it in enumerate(self.queue_items)}
        idx = by_id.get(moving_id)
        if idx is None:
            return
        new = idx + direction
        if not (0 <= new < len(self.queue_items)):
            return
        self.queue_items[idx], self.queue_items[new] = \
            self.queue_items[new], self.queue_items[idx]
        self._render_queue()
        self.tree.selection_set(str(moving_id))

    def _status_text(self, status):
        return {ST_PENDING: self.t("status_pending"),
                ST_RUNNING: self.t("status_running"),
                ST_DONE: self.t("status_done"),
                ST_ERROR: self.t("status_error"),
                ST_SKIPPED: self.t("status_skipped")}.get(status, status)

    def _render_queue(self):
        def populate():
            self.tree.delete(*self.tree.get_children())
            for i, it in enumerate(self.queue_items):
                length = fmt_hms(it.duration) if it.duration else "…"
                self.tree.insert("", "end", iid=str(it.item_id),
                                 values=(i + 1, it.filename,
                                         os.path.dirname(it.filepath),
                                         length,
                                         self._status_text(it.status)))
        render_queue_preserving_selection(self.tree, populate)

    # ======================================================================
    # Queue operations (MD tab)
    # ======================================================================
    def _md_add_files(self):
        if self.md_is_running:
            messagebox.showwarning(self.t("warn"), self.t("warn_queue_locked"))
            return
        if not self._gate_finished_queue(
                "md", bool(self.md_queue_items), self._md_clear_queue,
                keep_fn=lambda: (self._reset_errored_to_pending(self.md_queue_items),
                                 self._render_md_queue())):
            return
        paths = filedialog.askopenfilenames(
            title=self.t("select_doc_title"),
            filetypes=[(self.t("doc_files"), " ".join("*" + e for e in MARKITDOWN_EXTENSIONS)),
                       (self.t("all_files"), "*.*")])
        existing = {it.filepath for it in self.md_queue_items}
        for p in paths:
            if p not in existing:
                it = QueueItem(p)
                try:
                    it.size_bytes = os.path.getsize(p)
                except OSError:
                    it.size_bytes = None
                self.md_queue_items.append(it)
        self._render_md_queue()
        self._update_md_summary()

    def _md_remove_selected(self):
        if self.md_is_running:
            messagebox.showwarning(self.t("warn"), self.t("warn_queue_locked"))
            return
        by_id = {it.item_id: it for it in self.md_queue_items}
        ids_to_remove = []
        for iid in self.md_tree.selection():
            it = by_id.get(int(iid))
            if it is not None:
                ids_to_remove.append(it.item_id)
        if ids_to_remove:
            self.md_queue_items = [it for it in self.md_queue_items
                                   if it.item_id not in ids_to_remove]
            self._render_md_queue()
            self._update_md_summary()

    def _md_clear_queue(self):
        if self.md_is_running:
            messagebox.showwarning(self.t("warn"), self.t("warn_queue_locked"))
            return
        self.md_queue_items = []
        self._render_md_queue()
        self._update_md_summary()

    def _md_status_text(self, status):
        return {ST_PENDING: self.t("status_pending"),
                ST_RUNNING: self.t("status_running_md"),
                ST_DONE: self.t("status_done"),
                ST_ERROR: self.t("status_error"),
                ST_SKIPPED: self.t("status_skipped")}.get(status, status)

    def _render_md_queue(self):
        def populate():
            self.md_tree.delete(*self.md_tree.get_children())
            for i, it in enumerate(self.md_queue_items):
                size = self._human_bytes(it.size_bytes) if it.size_bytes else "—"
                self.md_tree.insert("", "end", iid=str(it.item_id),
                                    values=(i + 1, it.filename,
                                            os.path.dirname(it.filepath),
                                            size,
                                            self._md_status_text(it.status)))
        render_queue_preserving_selection(self.md_tree, populate)

    # ======================================================================
    # Dictionary operations
    # ======================================================================
    def _refresh_dict_listbox(self):
        self.dict_listbox.delete(0, "end")
        for name in sorted(self.dictionaries.keys()):
            self.dict_listbox.insert("end", name)

    def _on_dict_profile_select(self, _event=None):
        sel = self.dict_listbox.curselection()
        if not sel:
            return
        name = self.dict_listbox.get(sel[0])
        prof = self.dictionaries.get(name, {})
        self._dict_current = name
        self.dict_name_var.set(name)
        self.dict_prompt_text.delete("1.0", "end")
        self.dict_prompt_text.insert("1.0", prof.get("initial_prompt") or prof.get("prompt") or "")
        self.dict_repl_text.delete("1.0", "end")
        repl = prof.get("replacements", [])
        self.dict_repl_text.insert("1.0", "\n".join(f"{a}={b}" for a, b in repl))

    def _dict_new(self):
        self._dict_current = None
        self.dict_name_var.set("")
        self.dict_prompt_text.delete("1.0", "end")
        self.dict_repl_text.delete("1.0", "end")
        self.dict_listbox.selection_clear(0, "end")

    def _dict_duplicate(self):
        sel = self.dict_listbox.curselection()
        if not sel:
            messagebox.showinfo(self.t("info"), self.t("select_to_duplicate"))
            return
        name = self.dict_listbox.get(sel[0])
        new_name = simpledialog.askstring(
            self.t("dup_title"), self.t("dup_prompt"),
            initialvalue=name + self.t("dup_suffix"), parent=self)
        if not new_name:
            return
        if new_name in self.dictionaries:
            messagebox.showerror(self.t("error"), self.t("err_dup_exists"))
            return
        self.dictionaries[new_name] = json.loads(json.dumps(self.dictionaries[name]))
        save_json(DICTIONARIES_FILE, self.dictionaries)
        self._refresh_dict_listbox()
        self._refresh_dictionary_dropdown()

    def _dict_delete(self):
        sel = self.dict_listbox.curselection()
        if not sel:
            return
        name = self.dict_listbox.get(sel[0])
        if messagebox.askyesno(self.t("confirm"), self.t("delete_question", name=name)):
            self.dictionaries.pop(name, None)
            save_json(DICTIONARIES_FILE, self.dictionaries)
            self._dict_new()
            self._refresh_dict_listbox()
            self._refresh_dictionary_dropdown()

    def _dict_save(self):
        name = self.dict_name_var.get().strip()
        if not name:
            messagebox.showerror(self.t("error"), self.t("err_no_profile_name"))
            return
        prompt = self.dict_prompt_text.get("1.0", "end").strip()
        repl = parse_replacements_text(self.dict_repl_text.get("1.0", "end"))
        if self._dict_current and self._dict_current != name:
            self.dictionaries.pop(self._dict_current, None)
        self.dictionaries[name] = {"initial_prompt": prompt, "replacements": repl}
        save_json(DICTIONARIES_FILE, self.dictionaries)
        self._dict_current = name
        self._refresh_dict_listbox()
        self._refresh_dictionary_dropdown()
        messagebox.showinfo(self.t("saved"), self.t("profile_saved_msg", name=name))

    # ======================================================================
    # Streaming helpers for dialogs
    # ======================================================================
    _LAN_STATUS_LOG_WIDGETS = ()  # filled in __init__ once the widgets exist

    def _append_text(self, widget, text):
        # item 20.4: feed the LAN status page's rolling log tail whenever
        # one of the four main per-tab activity logs is written to. Cheap
        # (bounded deque) and never touches Tk from another thread — this
        # runs on the Tk main thread same as the rest of _append_text.
        if text and widget in self._LAN_STATUS_LOG_WIDGETS:
            self._lan_log_tail.append(text)
        try:
            widget.configure(state="normal")
            widget.insert("end", text)
            widget.see("end")
            widget.configure(state="disabled")
        except tk.TclError:
            pass

    def _attach_stream(self, event_queue, log_text, on_finish):
        # v0.13.10: heartbeat for long silent gaps — a real Docling
        # install went fully quiet for minutes after pip's "Installing
        # collected packages:" line (pip doesn't print progress during
        # the actual unpack/compile step for ~100 packages including
        # torch), indistinguishable from a hang without this. Only fires
        # when genuinely nothing has arrived for a while — doesn't
        # interleave with real output.
        HEARTBEAT_SECS = 15
        state = {"last_activity": time.time()}

        def poll():
            got_output = False
            try:
                while True:
                    ev = event_queue.get_nowait()
                    got_output = True
                    k = ev.get("kind")
                    if k in ("log", "cmd_log", "md_log"):
                        self._append_text(log_text, ev.get("text", ""))
                    elif k == "dl_model_ok":
                        self._append_text(log_text, self.t("log_model_ok"))
                    elif k == "dl_finished":
                        on_finish(bool(ev.get("success")), ev.get("error", ""))
                        return
                    elif k == "cmd_finished":
                        rc = ev.get("returncode", 0)
                        on_finish(rc == 0, "" if rc == 0 else str(rc))
                        return
            except queue.Empty:
                pass
            now = time.time()
            if got_output:
                state["last_activity"] = now
            elif now - state["last_activity"] >= HEARTBEAT_SECS:
                self._append_text(log_text, self.t("log_still_working"))
                state["last_activity"] = now
            self.after(120, poll)
        poll()

    # ======================================================================
    # Item 1.7 — "Check all tools for updates" summary dialog
    # ======================================================================
    # ======================================================================
    # Item 8/14 — Settings -> General
    # ======================================================================
    # ======================================================================
    # Item 20 — Settings -> LAN Status
    # ======================================================================
    def _open_lan_status_settings(self):
        dlg = tk.Toplevel(self)
        dlg.title(self.t("lan_settings_title"))
        dlg.transient(self)
        dlg.resizable(False, False)
        if getattr(self, "_icon_img_small", None) is not None:
            try:
                dlg.iconphoto(False, self._icon_img_small)
            except tk.TclError:
                pass
        frm = ttk.Frame(dlg)
        frm.pack(fill="both", expand=True, padx=16, pady=16)

        ttk.Label(frm, text=self.t("lan_intro"), wraplength=440, foreground="#555"
                  ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

        enabled_var = tk.BooleanVar(value=bool(self.cfg.get("lan_status_enabled", False)))
        port_var = tk.StringVar(value=str(self.cfg.get("lan_status_port", 8080)))
        bind_var = tk.StringVar(value=self.cfg.get("lan_status_bind", "0.0.0.0"))
        token_enabled_var = tk.BooleanVar(
            value=bool(self.cfg.get("lan_status_token_enabled", False)))
        token_var = tk.StringVar(value=self.cfg.get("lan_status_token", ""))

        status_var = tk.StringVar(value="")
        status_lbl = ttk.Label(frm, textvariable=status_var, foreground="#8250df",
                               wraplength=440, justify="left")

        def refresh_status_label():
            if self._lan_server.running:
                status_var.set(self.t("lan_running_at", url=self._lan_reachable_url()))
            else:
                status_var.set(self.t("lan_stopped"))

        def apply_enabled_toggle():
            self.cfg["lan_status_enabled"] = bool(enabled_var.get())
            self._save_config()
            if enabled_var.get():
                ok, err = self._lan_start_server()
                if not ok:
                    messagebox.showerror(self.t("lan_settings_title"),
                                         self.t("lan_start_failed", err=err), parent=dlg)
                    enabled_var.set(False)
                    self.cfg["lan_status_enabled"] = False
                    self._save_config()
            else:
                self._lan_stop_server()
            refresh_status_label()

        ttk.Checkbutton(frm, text=self.t("lan_enable"), variable=enabled_var,
                        command=apply_enabled_toggle).grid(
                            row=1, column=0, columnspan=2, sticky="w", pady=2)

        ttk.Label(frm, text=self.t("lan_port_label")).grid(row=2, column=0, sticky="w", pady=2)
        ttk.Entry(frm, textvariable=port_var, width=8).grid(row=2, column=1, sticky="w")
        ttk.Label(frm, text=self.t("lan_bind_label")).grid(row=3, column=0, sticky="w", pady=2)
        ttk.Entry(frm, textvariable=bind_var, width=16).grid(row=3, column=1, sticky="w")

        def save_port_bind(*_a):
            try:
                p = int(port_var.get())
                if 1 <= p <= 65535:
                    self.cfg["lan_status_port"] = p
            except ValueError:
                pass
            self.cfg["lan_status_bind"] = bind_var.get().strip() or "0.0.0.0"
            self._save_config()
        port_var.trace_add("write", save_port_bind)
        bind_var.trace_add("write", save_port_bind)

        ttk.Checkbutton(frm, text=self.t("lan_token_enable"), variable=token_enabled_var,
                        command=lambda: (self.cfg.__setitem__(
                            "lan_status_token_enabled", bool(token_enabled_var.get())),
                            self._save_config())
                        ).grid(row=4, column=0, columnspan=2, sticky="w", pady=(10, 2))
        token_entry = ttk.Entry(frm, textvariable=token_var, width=28)
        token_entry.grid(row=5, column=0, columnspan=2, sticky="w")

        def gen_token():
            token_var.set(secrets.token_urlsafe(12))
            self.cfg["lan_status_token"] = token_var.get()
            self._save_config()
        if not token_var.get():
            gen_token()
        else:
            self.cfg["lan_status_token"] = token_var.get()
        ttk.Button(frm, text=self.t("lan_regen_token"), command=gen_token
                  ).grid(row=6, column=0, sticky="w", pady=(2, 10))
        token_var.trace_add("write", lambda *a: (
            self.cfg.__setitem__("lan_status_token", token_var.get()), self._save_config()))

        status_lbl.grid(row=7, column=0, columnspan=2, sticky="w", pady=(4, 4))
        ttk.Label(frm, text=self.t("lan_firewall_note"), wraplength=440, foreground="#8250df"
                  ).grid(row=8, column=0, columnspan=2, sticky="w", pady=(0, 2))
        fw_row = ttk.Frame(frm)
        fw_row.grid(row=9, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        fw_var = tk.StringVar(value=lan_firewall_command(port_var.get() or 8080))
        fw_entry = ttk.Entry(fw_row, textvariable=fw_var, width=52)
        fw_entry.pack(side="left", fill="x", expand=True)
        fw_entry.configure(state="readonly")

        refresh_status_label()
        ttk.Button(frm, text=self.t("close"), command=dlg.destroy
                  ).grid(row=10, column=0, columnspan=2, sticky="e")

    def _open_general_settings(self):
        dlg = tk.Toplevel(self)
        dlg.title(self.t("general_settings_title"))
        dlg.transient(self)
        dlg.resizable(False, False)
        if getattr(self, "_icon_img_small", None) is not None:
            try:
                dlg.iconphoto(False, self._icon_img_small)
            except tk.TclError:
                pass
        frm = ttk.Frame(dlg)
        frm.pack(fill="both", expand=True, padx=16, pady=16)

        ttk.Label(frm, text=self.t("general_batch_section"),
                  font=("TkDefaultFont", 10, "bold")).grid(
                      row=0, column=0, sticky="w", pady=(0, 6))

        warn_var = tk.BooleanVar(value=bool(self.cfg.get("batch_warn_enabled", True)))
        cap_var = tk.BooleanVar(value=bool(self.cfg.get("batch_cap_enabled", True)))

        def on_warn_toggle():
            self.cfg["batch_warn_enabled"] = bool(warn_var.get())
            self._save_config()

        def on_cap_toggle():
            self.cfg["batch_cap_enabled"] = bool(cap_var.get())
            self._save_config()

        ttk.Checkbutton(frm, text=self.t("general_warn_batch"),
                        variable=warn_var, command=on_warn_toggle
                        ).grid(row=1, column=0, sticky="w", pady=2)
        ttk.Checkbutton(frm, text=self.t("general_cap_batch"),
                        variable=cap_var, command=on_cap_toggle
                        ).grid(row=2, column=0, sticky="w", pady=(2, 12))

        ttk.Label(frm, text=self.t("general_header_lang_section"),
                  font=("TkDefaultFont", 10, "bold")).grid(
                      row=3, column=0, sticky="w", pady=(0, 6))

        header_lang_var = tk.StringVar(value=self.cfg.get("header_lang", "pt"))

        def on_header_lang_change():
            self.cfg["header_lang"] = header_lang_var.get()
            self._save_config()

        ttk.Radiobutton(frm, text=self.t("general_header_lang_pt"), value="pt",
                        variable=header_lang_var, command=on_header_lang_change
                        ).grid(row=4, column=0, sticky="w", pady=2)
        ttk.Radiobutton(frm, text=self.t("general_header_lang_en"), value="en",
                        variable=header_lang_var, command=on_header_lang_change
                        ).grid(row=5, column=0, sticky="w", pady=(2, 12))

        ttk.Button(frm, text=self.t("close"), command=dlg.destroy
                  ).grid(row=6, column=0, sticky="e", pady=(6, 0))

    def _open_check_all_updates(self):
        """v0.13.0: 'Update' here now actually updates, inline (it used
        to just open the tool's own Settings dialog, which — combined
        with that dialog's Update row not auto-checking either — made a
        single click here look like it did nothing). A tool that isn't
        installed shows 'Not installed' immediately with no network call,
        instead of silently reporting 'Up to date'."""
        dlg = tk.Toplevel(self)
        dlg.title(self.t("check_all_title"))
        dlg.transient(self)
        dlg.geometry("640x560")
        dlg.resizable(True, True)
        frm = ttk.Frame(dlg)
        frm.pack(fill="both", expand=True, padx=12, pady=12)
        frm.columnconfigure(1, weight=1)
        ttk.Label(frm, text=self.t("check_all_intro"), foreground="#555",
                  wraplength=600).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 10))

        tools = [
            dict(name="MarkItDown",
                 get_installed=lambda: get_pip_package_version(
                     markitdown_python(self.cfg), "markitdown"),
                 get_latest=lambda: check_pypi_latest_version("markitdown"),
                 do_update=lambda parent, logw, on_done, target_version=None:
                     self._update_markitdown(parent, logw, on_done=on_done,
                                             target_version=target_version,
                                             fail_hint_key="set_tools_venv_rebuild_hint")),
            dict(name="yt-dlp",
                 get_installed=lambda: get_pip_package_version(tools_venv_python(), "yt-dlp"),
                 get_latest=lambda: check_pypi_latest_version("yt-dlp"),
                 do_update=lambda parent, logw, on_done, target_version=None:
                     self._update_ytdlp(parent, logw, on_done=on_done,
                                        target_version=target_version)),
            dict(name="Whisper",
                 get_installed=lambda: get_pip_package_version(
                     venv_python(whisper_env_dir_from_cfg(self.cfg)), "openai-whisper"),
                 get_latest=lambda: check_pypi_latest_version("openai-whisper"),
                 is_installed=lambda: bool(self.whisper_path),
                 do_update=lambda parent, logw, on_done, target_version=None:
                     self._update_whisper(parent, logw, on_done=on_done,
                                          target_version=target_version)),
            dict(name="FFmpeg",
                 get_installed=lambda: self.cfg.get("ffmpeg_build_installed_at") or None,
                 get_latest=lambda: check_ffmpeg_latest_build(),
                 is_installed=lambda: bool(self.ffmpeg_path),
                 do_update=lambda parent, logw, on_done, target_version=None:
                     self._update_ffmpeg(parent, logw, on_done=on_done)),
            dict(name="Docling",
                 get_installed=lambda: get_pip_package_version(
                     docling_venv_python(), "docling"),
                 get_latest=lambda: check_pypi_latest_version("docling"),
                 is_installed=lambda: bool(self.docling_ok),
                 do_update=lambda parent, logw, on_done, target_version=None:
                     self._update_docling(parent, logw, on_done=on_done,
                                          target_version=target_version)),
            dict(name="Pandoc",
                 get_installed=lambda: self.cfg.get("pandoc_installed_version") or None,
                 get_latest=lambda: check_pandoc_latest_release(),
                 is_installed=lambda: bool(self.pandoc_path),
                 do_update=lambda parent, logw, on_done, target_version=None:
                     self._update_pandoc(parent, logw, on_done=on_done)),
        ]

        log = tk.Text(frm, height=8, wrap="word", state="disabled", font=("TkFixedFont", 9))

        def make_row(i, spec):
            get_installed = spec["get_installed"]
            get_latest = spec["get_latest"]
            do_update = spec["do_update"]
            is_installed_fn = spec.get("is_installed") or (lambda: bool(get_installed()))
            state = {"latest": None}

            ttk.Label(frm, text=spec["name"], font=("TkDefaultFont", 10, "bold")
                      ).grid(row=i, column=0, sticky="w", padx=(0, 8), pady=4)
            status_var = tk.StringVar(value=self.t("set_checking_updates"))
            status_lbl = ttk.Label(frm, textvariable=status_var)
            status_lbl.grid(row=i, column=1, sticky="w", pady=4)
            update_btn = ttk.Button(frm, text=self.t("set_update_btn"), state="disabled")
            update_btn.grid(row=i, column=2, sticky="e", pady=4)

            def recheck():
                state["latest"] = None
                if not is_installed_fn():
                    status_var.set(self.t("set_not_installed"))
                    status_lbl.configure(foreground="#cf222e")
                    update_btn.configure(state="disabled")
                    return
                status_lbl.configure(foreground="#555")
                status_var.set(self.t("set_checking_updates"))
                update_btn.configure(state="disabled")

                def done(latest, err):
                    if err:
                        status_var.set(self.t("set_update_check_failed"))
                        return
                    installed = get_installed()
                    if installed and latest and compare_versions_simple(installed, latest):
                        state["latest"] = latest
                        status_var.set(self.t("set_update_available", cur=installed, new=latest))
                        update_btn.configure(state="normal")
                    elif installed:
                        # v0.13.6: show the current version even when
                        # there's nothing to update to, instead of a bare
                        # "Up to date." with no way to tell which version
                        # that actually refers to.
                        status_var.set(self.t("set_up_to_date_v", version=installed))
                    else:
                        status_var.set(self.t("set_installed_unknown_version"))
                self._run_update_check_async(get_latest, done)

            def start_update():
                update_btn.configure(state="disabled")
                do_update(dlg, log, recheck, target_version=state.get("latest"))

            update_btn.configure(command=start_update)
            recheck()

        for i, spec in enumerate(tools, start=1):
            make_row(i, spec)

        log.grid(row=len(tools) + 1, column=0, columnspan=3, sticky="nsew", pady=(8, 8))
        frm.rowconfigure(len(tools) + 1, weight=1)
        ttk.Button(frm, text=self.t("close"), command=dlg.destroy).grid(
            row=len(tools) + 2, column=0, columnspan=3, sticky="e", pady=(4, 0))


    def _run_update_check_async(self, get_latest_fn, callback):
        """Runs get_latest_fn() (a network call) on a background thread,
        then delivers (latest, error) back on the Tk main thread."""
        def work():
            latest, err = get_latest_fn()
            self.after(0, lambda: callback(latest, err))
        threading.Thread(target=work, daemon=True).start()

    # ======================================================================
    # v0.13.0 — one shared "pip install --upgrade" flow, used by every
    # per-tool Settings dialog's Install/Update button AND by "Check for
    # All Tools Update". Previously each dialog duplicated this (and the
    # summary dialog didn't run it at all — its "Update" button just
    # opened the relevant Settings dialog instead of updating anything).
    # ======================================================================
    def _run_pip_upgrade(self, parent, log_widget, *, resolve_python_exe,
                         package_install_spec, package_metadata_name,
                         package_display, on_success, on_done=None,
                         confirm_key="set_pip_update_q", target_version=None,
                         fail_hint_key=None, extra_packages=None):
        python_exe, err = resolve_python_exe()
        if not python_exe:
            self._append_text(log_widget, self.t("install_done_fail", code=err or "python"))
            if on_done:
                on_done()
            return
        before = get_pip_package_version(python_exe, package_metadata_name)
        # v0.13.10: also snapshot the extras (youtube-transcript-api/
        # pysrt/webvtt-py alongside markitdown) — a real report showed
        # pysrt/webvtt-py genuinely installing while markitdown itself
        # stayed the same version, and the "nothing changed" warning
        # fired anyway since it only ever looked at the primary package,
        # which was confusing and simply wrong in that case (something
        # DID change, and it was the whole reason the button was
        # clicked). extra_packages here are always plain, unpinned names
        # in this app's actual usage, so they double as their own pip
        # metadata name.
        extra_names = list(extra_packages) if extra_packages else []
        extras_before = {p: get_pip_package_version(python_exe, p) for p in extra_names}
        install_spec = package_install_spec
        if target_version:
            # v0.13.2: pin to the exact version already confirmed
            # available via "Check for updates", instead of an
            # unversioned upgrade. An unversioned spec gives pip an easy
            # out: if the newest version's own dependencies conflict
            # with anything already installed, pip can just leave the
            # old version in place — it still "satisfies" the bare,
            # unversioned request — and exit 0 having changed nothing
            # (see the mammoth~=1.11.0 vs. already-installed 1.12.0
            # case). Pinning removes that escape hatch: pip either
            # resolves the exact version for real, or fails with a
            # genuine, readable conflict error instead of a silent no-op.
            install_spec = f"{package_install_spec}=={target_version}"
        cmd = build_pip_install_command(python_exe, install_spec)
        if extra_packages:
            # v0.13.5: additional packages resolved in the SAME pip
            # invocation as the main one — e.g. youtube-transcript-api
            # alongside markitdown, once markitdown's own extras stopped
            # being a safe way to pull it in on Python 3.14 (see
            # MARKITDOWN_EXTRAS_NO_YOUTUBE).
            cmd.extend(extra_packages)
        if not messagebox.askyesno(self.t("confirm"),
                                   self.t(confirm_key, name=package_display, cmd=" ".join(cmd)),
                                   parent=parent):
            if on_done:
                on_done()
            return
        self._append_text(log_widget, self.t("install_running"))
        stop = threading.Event()
        q = queue.Queue()
        worker = CommandStreamWorker(cmd, q, stop, tag="pipupd")
        worker.start()

        def done(success, error):
            if success:
                after = get_pip_package_version(python_exe, package_metadata_name)
                extras_after = {p: get_pip_package_version(python_exe, p) for p in extra_names}
                extras_changed = any(extras_before[p] != extras_after[p] for p in extra_names)
                if before and after and before == after and not extras_changed:
                    # v0.13.1: pip can legitimately exit 0 having changed
                    # nothing at all — e.g. it couldn't find a newer
                    # version compatible with some other already-pinned
                    # package in the same environment, so it silently
                    # kept what was already there. Reporting that the
                    # same way as a real upgrade is exactly what made the
                    # previous "still shows available" bug report so
                    # confusing to diagnose from the log alone.
                    self._append_text(log_widget, self.t(
                        "install_done_no_change", version=after))
                else:
                    self._append_text(log_widget, self.t(
                        "install_done_ok_versions", before=before or "?", after=after or "?"))
                    for p in extra_names:
                        if extras_before[p] != extras_after[p]:
                            self._append_text(log_widget, self.t(
                                "install_done_extra_versions", name=p,
                                before=extras_before[p] or "?", after=extras_after[p] or "?"))
                on_success(python_exe)
            else:
                self._append_text(log_widget, self.t("install_done_fail", code=error))
                if fail_hint_key:
                    # v0.13.3: a pinned version can still fail to resolve
                    # if the venv has accumulated conflicting pins from
                    # earlier installs (not just this one package's own
                    # constraint) — point at the actual fix for that.
                    self._append_text(log_widget, self.t(fail_hint_key))
            if on_done:
                on_done()
        self._attach_stream(q, log_widget, done)

    def _update_markitdown(self, parent, log_widget, on_done=None,
                           confirm_key="set_pip_update_q", target_version=None,
                           fail_hint_key=None):
        self._run_pip_upgrade(
            parent, log_widget,
            resolve_python_exe=lambda: ensure_tools_venv(
                log_cb=lambda t: self._append_text(log_widget, t)),
            package_install_spec=MARKITDOWN_INSTALL_SPEC, package_metadata_name="markitdown",
            package_display="MarkItDown", on_success=self._on_markitdown_installed,
            on_done=on_done, confirm_key=confirm_key, target_version=target_version,
            fail_hint_key=fail_hint_key,
            extra_packages=["youtube-transcript-api", "pysrt", "webvtt-py"])

    def _on_markitdown_installed(self, python_exe):
        self.cfg["markitdown_python"] = python_exe
        self._save_config()
        self._detect_dependencies()
        self._refresh_status_indicators()

    def _update_ytdlp(self, parent, log_widget, on_done=None,
                      confirm_key="set_pip_update_q", target_version=None,
                      fail_hint_key=None):
        self._run_pip_upgrade(
            parent, log_widget,
            resolve_python_exe=lambda: ensure_tools_venv(
                log_cb=lambda t: self._append_text(log_widget, t)),
            package_install_spec="yt-dlp", package_metadata_name="yt-dlp",
            package_display="yt-dlp", on_success=self._on_ytdlp_installed,
            on_done=on_done, confirm_key=confirm_key, target_version=target_version,
            fail_hint_key=fail_hint_key)

    def _on_ytdlp_installed(self, python_exe):
        self.python_exe = python_exe
        self.cfg["markitdown_python"] = python_exe
        self._save_config()
        self._detect_dependencies()
        self._refresh_status_indicators()

    def _update_docling(self, parent, log_widget, on_done=None,
                        confirm_key="set_pip_update_q", target_version=None):
        """Same _run_pip_upgrade() shared flow as MarkItDown/yt-dlp
        above, pointed at Docling's own dedicated venv instead of the
        shared tools venv."""
        self._run_pip_upgrade(
            parent, log_widget,
            resolve_python_exe=lambda: ensure_docling_venv(
                log_cb=lambda t: self._append_text(log_widget, t)),
            package_install_spec="docling", package_metadata_name="docling",
            package_display="Docling", on_success=self._on_docling_installed,
            on_done=on_done, confirm_key=confirm_key, target_version=target_version)

    def _on_docling_installed(self, python_exe):
        self.cfg["docling_env_dir"] = os.path.dirname(os.path.dirname(python_exe))
        self._save_config()
        self._detect_dependencies()
        self._refresh_status_indicators()

    def _rebuild_tools_venv(self, parent, log_widget, on_done=None):
        """v0.13.3: the escape hatch for when even an exact version pin
        can't resolve — wipes tools/venv and reinstalls MarkItDown
        + yt-dlp together into a fresh one, in a single pip invocation so
        both land on one mutually consistent set of pins.

        v0.13.4: the reinstall is now pinned to the exact latest stable
        MarkItDown version too (same reasoning as the regular Update
        flow — an unversioned install still lets pip wander/backtrack
        more than necessary). Failure and success are both now shown in
        a messagebox, not just a log line that's easy to miss.

        v0.13.5: uses MARKITDOWN_INSTALL_SPEC (not "markitdown[all]") and
        installs youtube-transcript-api alongside it explicitly — see
        that constant's comment for why."""
        if not messagebox.askyesno(
                self.t("confirm"),
                self.t("set_tools_venv_rebuild_q", path=str(TOOLS_VENV_DIR)),
                parent=parent):
            if on_done:
                on_done()
            return
        vpy, err = rebuild_tools_venv(log_cb=lambda t: self._append_text(log_widget, t))
        if not vpy:
            self._append_text(log_widget, self.t("install_done_fail", code=err or "venv"))
            messagebox.showerror(self.t("error"), err or self.t("install_done_fail", code="venv"),
                                 parent=parent)
            if on_done:
                on_done()
            return
        latest, _err = check_pypi_latest_version("markitdown")
        install_spec = f"{MARKITDOWN_INSTALL_SPEC}=={latest}" if latest else MARKITDOWN_INSTALL_SPEC
        cmd = build_pip_install_command(vpy, install_spec)
        cmd.append("yt-dlp")
        cmd.append("youtube-transcript-api")
        self._append_text(log_widget, self.t("install_running"))
        stop = threading.Event()
        q = queue.Queue()
        worker = CommandStreamWorker(cmd, q, stop, tag="pipupd")
        worker.start()

        def done(success, error):
            if success:
                self.cfg["markitdown_python"] = vpy
                self.python_exe = vpy
                self._save_config()
                self._append_text(log_widget, self.t("install_done_ok"))
                self._detect_dependencies()
                self._refresh_status_indicators()
                messagebox.showinfo(self.t("info"), self.t("set_tools_venv_rebuild_ok"),
                                    parent=parent)
            else:
                self._append_text(log_widget, self.t("install_done_fail", code=error))
                messagebox.showerror(self.t("error"),
                                     self.t("set_tools_venv_rebuild_fail"), parent=parent)
            if on_done:
                on_done()
        self._attach_stream(q, log_widget, done)

    def _update_whisper(self, parent, log_widget, on_done=None, target_version=None):
        # v0.13.1: was calling _managed_env_dir(), a local closure that
        # only exists inside _open_whisper_settings — a NameError
        # waiting to happen the moment this ran from anywhere else
        # (including Check for All Tools Update).
        env_dir = whisper_env_dir_from_cfg(self.cfg)
        vpy = venv_python(env_dir)

        def resolve():
            return (vpy, None) if os.path.exists(vpy) else (None, "not installed")
        self._run_pip_upgrade(
            parent, log_widget, resolve_python_exe=resolve,
            package_install_spec="openai-whisper", package_metadata_name="openai-whisper",
            package_display="Whisper", on_success=self._on_whisper_updated, on_done=on_done,
            target_version=target_version)

    def _on_whisper_updated(self, python_exe):
        self._whisper_readiness()
        self._refresh_status_indicators()

    def _update_ffmpeg(self, parent, log_widget, on_done=None):
        """Reuses today's install/extract worker but skips the folder
        picker for a plain 'Update' click — it reinstalls into the
        directory the current build already lives in (or the default
        app-managed folder if ffmpeg isn't installed via this app yet).
        The dedicated 'Download and install automatically' button keeps
        its own folder picker unchanged, for a fresh/relocated install."""
        dest = os.path.dirname(self.ffmpeg_path) if self.ffmpeg_path else None
        if not messagebox.askyesno(
                self.t("confirm"),
                self.t("set_ffmpeg_auto_q", dest=dest or str(FFMPEG_INSTALL_DIR)),
                parent=parent):
            if on_done:
                on_done()
            return

        def finished(ok, path):
            self._refresh_status_indicators()
            if on_done:
                on_done()
        self._start_ffmpeg_auto(log_widget, finished, dest_dir=dest)

    def _update_pandoc(self, parent, log_widget, on_done=None):
        """Same shape as _update_ffmpeg() above."""
        dest = os.path.dirname(self.pandoc_path) if getattr(self, "pandoc_path", None) else None
        if not messagebox.askyesno(
                self.t("confirm"),
                self.t("set_pandoc_auto_q", dest=dest or str(PANDOC_INSTALL_DIR)),
                parent=parent):
            if on_done:
                on_done()
            return

        def finished(ok, path):
            self._refresh_status_indicators()
            if on_done:
                on_done()
        self._start_pandoc_auto(log_widget, finished, dest_dir=dest)

    def _make_update_row(self, parent, row, *, get_installed, get_latest,
                         on_update_confirmed, is_installed=None):
        """Builds one standardized Check-for-updates + Update button pair
        (item 1.4/1.5/1.7), shared by all tool settings dialogs. Returns a
        refresh() callable the dialog should invoke again after any
        install/update/uninstall (it's already invoked once internally,
        so a fresh dialog opens in the right state without a network call).

        v0.13.0 fixes:
          - a tool that isn't installed used to fall through to "Up to
            date" (get_installed() -> None fails the comparison, so the
            else-branch fired) and still triggered get_latest()'s network
            call for nothing; now is_installed() (defaults to
            bool(get_installed()), override for tools like FFmpeg whose
            "installed" and "have a comparable version string" aren't the
            same thing) gates a "Not installed" status with no network
            call at all.
          - after a successful in-dialog update, this row used to keep
            showing the pre-update "Update available" text until the user
            clicked "Check for updates" again — refresh() (called by the
            caller's on_done) now resets it immediately instead of going
            stale.
        """
        is_installed_fn = is_installed or (lambda: bool(get_installed()))
        status_var = tk.StringVar(value="")
        status_lbl = ttk.Label(parent, textvariable=status_var, foreground="#555")
        status_lbl.grid(row=row, column=0, columnspan=3, sticky="w", padx=6, pady=(0, 4))
        state = {"latest": None}

        update_btn = ttk.Button(parent, text=self.t("set_update_btn"), state="disabled")

        def do_check():
            if not is_installed_fn():
                status_var.set(self.t("set_not_installed"))
                status_lbl.configure(foreground="#cf222e")
                update_btn.configure(state="disabled")
                return
            status_lbl.configure(foreground="#555")
            check_btn.configure(state="disabled")
            status_var.set(self.t("set_checking_updates"))
            installed = get_installed()

            def done(latest, err):
                check_btn.configure(state="normal")
                if err:
                    status_var.set(self.t("set_update_check_failed"))
                    update_btn.configure(state="disabled")
                    return
                state["latest"] = latest
                if installed and latest and compare_versions_simple(installed, latest):
                    status_var.set(self.t("set_update_available", cur=installed, new=latest))
                    update_btn.configure(state="normal")
                elif installed:
                    # v0.13.6: show the current version even when
                    # there's nothing to update to.
                    status_var.set(self.t("set_up_to_date_v", version=installed))
                    update_btn.configure(state="disabled")
                else:
                    status_var.set(self.t("set_installed_unknown_version"))
                    update_btn.configure(state="disabled")
            self._run_update_check_async(get_latest, done)

        def start_update():
            update_btn.configure(state="disabled")
            on_update_confirmed(state.get("latest"))

        check_btn = ttk.Button(parent, text=self.t("set_check_updates_btn"), command=do_check)
        check_btn.grid(row=row + 1, column=0, sticky="w", padx=6, pady=(0, 6))
        update_btn.configure(command=start_update)
        update_btn.grid(row=row + 1, column=1, sticky="w", padx=(0, 6), pady=(0, 6))

        def refresh():
            state["latest"] = None
            update_btn.configure(state="disabled")
            if not is_installed_fn():
                status_var.set(self.t("set_not_installed"))
                status_lbl.configure(foreground="#cf222e")
            else:
                status_var.set("")
                status_lbl.configure(foreground="#555")
        refresh()
        return refresh

    # ======================================================================
    # Settings: Whisper
    # ======================================================================
    def _open_whisper_settings(self, focus=None):
        dlg = tk.Toplevel(self)
        dlg.title(self.t("set_whisper_title"))
        dlg.transient(self)
        # v0.12.1 (Bug B, confirmed): a fixed, non-resizable 760x640 with
        # no scrollbar on the models list left it possible for the models
        # Treeview to render with ~0 visible rows on a different display/
        # DPI setup, even though it was fully populated. Resizable + its
        # own scrollbar (below) fixes the immediate case; the row minsize
        # (below, computed from actual font metrics) plus the real minsize
        # computed at the end of this function guarantee at least 3 model
        # rows stay visible regardless of screen size or DPI scaling.
        dlg.geometry("760x640")
        dlg.resizable(True, True)
        frm = ttk.Frame(dlg)
        frm.pack(fill="both", expand=True, padx=10, pady=10)
        frm.columnconfigure(0, weight=1)

        # status
        status_var = tk.StringVar()

        def refresh_status():
            self.whisper_path = find_whisper_path(self.cfg.get("whisper_path") or None)
            env_dir = _managed_env_dir()
            health = whisper_env_health(env_dir)
            if self.whisper_path:
                status_var.set(self.t("set_whisper_found", path=self.whisper_path))
            else:
                status_var.set(self.t("set_whisper_broken", path=env_dir) if health == "broken"
                               else self.t("set_whisper_missing"))
            if health == "broken":
                repair_btn.grid()
            else:
                repair_btn.grid_remove()
            self._refresh_status_indicators()
        ttk.Label(frm, textvariable=status_var, foreground="#444",
                  wraplength=720).grid(row=0, column=0, sticky="w", pady=(0, 6))

        irow = ttk.Frame(frm)
        irow.grid(row=1, column=0, sticky="ew", pady=4)
        irow.columnconfigure(2, weight=1)
        install_log = tk.Text(irow, height=5, wrap="word", state="disabled",
                              font=("TkFixedFont", 9))
        inst_btn = ttk.Button(irow, text=self.t("set_whisper_install"))
        inst_btn.grid(row=0, column=0, sticky="w")

        def recheck():
            typed = exe_var.get().strip()
            self.cfg["whisper_path"] = typed
            self._save_config()
            self._detect_dependencies()
            refresh_status()
            refresh_install_state()
            self._refresh_dl_whisper_check()
        ttk.Button(irow, text=self.t("set_whisper_recheck"),
                   command=recheck).grid(row=0, column=1, sticky="w", padx=(6, 0))
        remove_btn = ttk.Button(irow, text=self.t("set_whisper_remove"))
        remove_btn.grid(row=0, column=2, sticky="w", padx=(6, 0))
        # v0.12.2 (item 1): shown only when the managed venv's files exist
        # but its own interpreter won't launch (a stale base-Python
        # reference — e.g. the Python used to create it was moved or
        # reinstalled elsewhere). Hidden otherwise so the common (healthy)
        # case isn't cluttered with an action that doesn't apply.
        repair_btn = ttk.Button(irow, text=self.t("set_whisper_repair"))
        repair_btn.grid(row=0, column=3, sticky="w", padx=(6, 0))
        repair_btn.grid_remove()
        open_folder_btn = ttk.Button(
            irow, text=self.t("set_open_folder"),
            command=lambda: self._open_path(_managed_env_dir()))
        open_folder_btn.grid(row=0, column=4, sticky="w", padx=(6, 0))
        inst_hint = ttk.Label(irow, text="", foreground="#8250df", wraplength=420)
        inst_hint.grid(row=1, column=0, columnspan=5, sticky="w", padx=(0, 8), pady=(4, 0))

        def _managed_env_dir():
            # v0.13.1: delegates to the shared whisper_env_dir_from_cfg()
            # (moved to module scope) so this and Check-All-Updates can
            # never drift apart again.
            return whisper_env_dir_from_cfg(self.cfg)

        def refresh_install_state():
            g = (find_managed_whisper(_managed_env_dir())
                 or find_global_whisper(find_python_executable()))
            if g:
                inst_btn.configure(state="disabled")
                inst_hint.configure(text=self.t("set_whisper_already"), foreground="#1a7f37")
            else:
                inst_btn.configure(state="normal")
                inst_hint.configure(text="", foreground="#8250df")
            managed = find_managed_whisper(_managed_env_dir())
            remove_btn.configure(state=("normal" if managed else "disabled"))

        def remove_env():
            env_dir = _managed_env_dir()
            wp = venv_whisper(env_dir)
            target = os.path.dirname(os.path.dirname(wp)) if os.path.exists(wp) else env_dir
            if not os.path.isdir(target):
                return
            if not messagebox.askyesno(self.t("confirm"),
                                       self.t("set_whisper_remove_q", path=target),
                                       parent=dlg):
                return
            try:
                shutil.rmtree(target, ignore_errors=True)
                if self.cfg.get("whisper_path") and not os.path.exists(self.cfg["whisper_path"]):
                    self.cfg["whisper_path"] = ""
                    exe_var.set("")
                self._save_config()
                self._detect_dependencies()
                refresh_status()
                refresh_install_state()
                self._refresh_dl_whisper_check()
            except Exception as e:
                messagebox.showerror(self.t("error"), str(e), parent=dlg)
        remove_btn.configure(command=remove_env)

        def update_whisper(latest=None):
            def done():
                refresh_status()
                refresh_install_state()
                upd_refresh()
            self._update_whisper(dlg, install_log, on_done=done, target_version=latest)

        upd_refresh = self._make_update_row(
            irow, 2,
            get_installed=lambda: get_pip_package_version(
                venv_python(_managed_env_dir()), "openai-whisper"),
            get_latest=lambda: check_pypi_latest_version("openai-whisper"),
            is_installed=lambda: bool(self.whisper_path),
            on_update_confirmed=lambda latest: update_whisper(latest))

        # executable row
        exrow = ttk.LabelFrame(frm, text=self.t("set_whisper_exe"))
        exrow.grid(row=2, column=0, sticky="ew", pady=4)
        exrow.columnconfigure(0, weight=1)
        exe_var = tk.StringVar(value=self.cfg.get("whisper_path", ""))
        ttk.Entry(exrow, textvariable=exe_var).grid(row=0, column=0, sticky="ew", padx=6, pady=6)

        def browse_exe():
            p = filedialog.askopenfilename(
                title=self.t("select_whisper_title"), parent=dlg,
                initialdir=self._existing_dir_or_home(os.path.dirname(exe_var.get())))
            if p:
                exe_var.set(p)
                self.cfg["whisper_path"] = p
                self._save_config()
                refresh_status()
                refresh_install_state()
        ttk.Button(exrow, text=self.t("browse"), command=browse_exe).grid(row=0, column=1, padx=4, pady=6)

        # models manager (with a Language column)
        mf = ttk.LabelFrame(frm, text=self.t("set_models_title"))
        mf.grid(row=3, column=0, sticky="nsew", pady=4)
        mf.columnconfigure(0, weight=1)
        frm.rowconfigure(3, weight=1)
        model_tree = ttk.Treeview(mf, columns=("model", "language", "status"),
                                  show="headings", height=10, selectmode="browse")
        model_tree.heading("model", text=self.t("col_model"))
        model_tree.heading("language", text=self.t("col_language"))
        model_tree.heading("status", text=self.t("col_status"))
        model_tree.column("model", width=180, anchor="w")
        model_tree.column("language", width=120, anchor="w")
        model_tree.column("status", width=260, anchor="w")
        model_tree.grid(row=0, column=0, sticky="nsew", padx=(6, 0), pady=6)
        model_tree_vsb = ttk.Scrollbar(mf, orient="vertical", command=model_tree.yview)
        model_tree.configure(yscrollcommand=model_tree_vsb.set)
        model_tree_vsb.grid(row=0, column=1, sticky="ns", padx=(0, 6), pady=6)
        # v0.12.1 (Bug B): height=10 above is only a *requested* size — the
        # grid geometry manager can still squeeze this row smaller under
        # space pressure (a small/high-DPI screen), which is exactly what
        # happened. rowconfigure(minsize=...) is a hard floor the geometry
        # manager may not go below, computed from the system's own font
        # metrics rather than a guessed pixel count, so it stays correct
        # across different screens/DPI/font settings.
        import tkinter.font as tkfont
        _row_px = tkfont.nametofont("TkDefaultFont").metrics("linespace") + 8
        MIN_VISIBLE_MODEL_ROWS = 3
        mf.rowconfigure(0, weight=1, minsize=_row_px * (MIN_VISIBLE_MODEL_ROWS + 1))

        def fill_models():
            for iid in model_tree.get_children():
                model_tree.delete(iid)
            for cli in ALL_MODEL_CLIS:
                downloaded, _ = is_model_downloaded(cli)
                tag = self.t("installed_tag").strip() if downloaded else ""
                model_tree.insert("", "end", iid=cli,
                                  values=(cli, model_language_label(cli),
                                          (tag + "  " if tag else "")
                                          + self.t(MODEL_INFO[cli]["desc_key"])))
        fill_models()

        dl_log = tk.Text(mf, height=6, wrap="word", state="disabled", font=("TkFixedFont", 9))
        dl_log.grid(row=1, column=0, sticky="ew", padx=6, pady=(0, 6))

        def download_model():
            sel = model_tree.selection()
            if not sel:
                return
            cli = sel[0]
            readiness = self._whisper_readiness()
            if readiness != "ready":
                messagebox.showerror(
                    self.t("error"),
                    self.t("err_whisper_broken") if readiness == "broken"
                    else self.t("err_no_whisper"), parent=dlg)
                return
            info = MODEL_INFO[cli]
            self._append_text(dl_log, self.t("log_download_start",
                                             model=cli, size=human_size(info["size_mb"])))
            stop = threading.Event()
            q = queue.Queue()
            worker = ModelDownloadWorker(self.whisper_path, cli, q, stop)
            dl_btn.configure(state="disabled")
            worker.start()

            def done(success, error):
                dl_btn.configure(state="normal")
                if not success and error:
                    self._append_text(dl_log, f"\n[ERROR] {error}\n")
                fill_models()
                self._refresh_model_dropdown()
            self._attach_stream(q, dl_log, done)
        dl_btn = ttk.Button(mf, text=self.t("set_models_download"), command=download_model)
        dl_btn.grid(row=2, column=0, sticky="w", padx=6, pady=(0, 6))

        def install_whisper():
            chosen = filedialog.askdirectory(
                title=self.t("install_pick_dir"), parent=dlg,
                initialdir=(self.cfg.get("whisper_env_dir")
                            and os.path.dirname(os.path.dirname(self.cfg["whisper_env_dir"])))
                or os.path.expanduser("~"))
            if not chosen:
                return
            env_dir = resolve_whisper_env_dir(chosen)
            drive_root = env_dir
            compat = find_compatible_python()
            free = free_gb(env_dir)
            free_txt = f"{free:.1f}" if free is not None else "?"
            if not messagebox.askyesno(
                    self.t("confirm"),
                    self.t("set_whisper_install_q3",
                           gb=WHISPER_REQUIRED_GB, free=free_txt,
                           py=self._python_choice_display(compat), path=env_dir),
                    parent=dlg):
                return
            if free is not None and free < WHISPER_REQUIRED_GB:
                if not messagebox.askyesno(self.t("warn"),
                                           self.t("install_low_space",
                                                  need=WHISPER_REQUIRED_GB, free=free_txt),
                                           parent=dlg):
                    return
            if os.path.exists(venv_python(env_dir)) and not find_managed_whisper(env_dir):
                if not messagebox.askyesno(self.t("confirm"),
                                           self.t("install_partial_env", path=env_dir),
                                           parent=dlg):
                    return
                shutil.rmtree(env_dir, ignore_errors=True)
            if not compat and not winget_available():
                messagebox.showwarning(self.t("warn"),
                                       self.t("install_manual_py"), parent=dlg)
            self.cfg["whisper_env_dir"] = env_dir
            self._save_config()
            install_log.grid(row=1, column=0, columnspan=5, sticky="ew", pady=(4, 0))
            self._append_text(install_log, self.t("install_running"))
            stop = threading.Event()
            q = queue.Queue()
            worker = WhisperInstallWorker(q, stop, self.s, env_dir)
            inst_btn.configure(state="disabled")
            worker.start()

            def done(success, error):
                found = (find_managed_whisper(env_dir)
                         or find_global_whisper(find_python_executable()))
                if found and success:
                    self.cfg["whisper_path"] = found
                    exe_var.set(found)
                    self._save_config()
                self._append_text(install_log,
                                  "\n" + (self.t("install_done_ok") if (found and success)
                                          else self.t("install_done_fail", code=error)))
                if not (found and success):
                    self._append_text(install_log, "\n" + self.t("install_manual_py"))
                refresh_status()
                refresh_install_state()
                self._detect_dependencies()
                self._refresh_model_dropdown()
                self._refresh_dl_whisper_check()
            self._attach_stream(q, install_log, done)
        inst_btn.configure(command=install_whisper)
        refresh_install_state()

        def repair_whisper_env():
            # v0.12.2 (item 1): rebuild the SAME env_dir in place (no
            # folder picker, unlike a fresh install) — wipe it, then reuse
            # WhisperInstallWorker exactly as install_whisper() does; with
            # the broken venv gone, it correctly does a full rebuild
            # (its 'already exists' skip only fires when the python.exe
            # file is actually present).
            env_dir = _managed_env_dir()
            compat = find_compatible_python()
            if not messagebox.askyesno(
                    self.t("confirm"),
                    self.t("set_whisper_repair_q", path=env_dir,
                           py=self._python_choice_display(compat)),
                    parent=dlg):
                return
            try:
                shutil.rmtree(env_dir, ignore_errors=True)
            except OSError as e:
                messagebox.showerror(self.t("error"), str(e), parent=dlg)
                return
            if self.cfg.get("whisper_path") and not os.path.exists(self.cfg["whisper_path"]):
                self.cfg["whisper_path"] = ""
                exe_var.set("")
            self.cfg["whisper_env_dir"] = env_dir
            self._save_config()
            install_log.grid(row=1, column=0, columnspan=5, sticky="ew", pady=(4, 0))
            self._append_text(install_log, self.t("install_running"))
            stop = threading.Event()
            q = queue.Queue()
            worker = WhisperInstallWorker(q, stop, self.s, env_dir)
            repair_btn.configure(state="disabled")
            inst_btn.configure(state="disabled")
            worker.start()

            def done(success, error):
                found = (find_managed_whisper(env_dir)
                         or find_global_whisper(find_python_executable()))
                if found and success:
                    self.cfg["whisper_path"] = found
                    exe_var.set(found)
                    self._save_config()
                self._append_text(install_log,
                                  "\n" + (self.t("install_done_ok") if (found and success)
                                          else self.t("install_done_fail", code=error)))
                if not (found and success):
                    self._append_text(install_log, "\n" + self.t("install_manual_py"))
                refresh_status()
                refresh_install_state()
                self._detect_dependencies()
                self._refresh_model_dropdown()
                self._refresh_dl_whisper_check()
                inst_btn.configure(state="normal")
            self._attach_stream(q, install_log, done)
        repair_btn.configure(command=repair_whisper_env)

        # languages manager
        lf = ttk.LabelFrame(frm, text=self.t("set_langs_title"))
        lf.grid(row=4, column=0, sticky="ew", pady=4)
        lf.columnconfigure(0, weight=1)
        lang_list = tk.Listbox(lf, height=5, exportselection=False)
        lang_list.grid(row=0, column=0, rowspan=2, sticky="ew", padx=6, pady=6)

        def fill_langs():
            lang_list.delete(0, "end")
            for c in self.cfg.get("audio_langs", []):
                lang_list.insert("end", self._audio_lang_display(c))
        fill_langs()

        addrow = ttk.Frame(lf)
        addrow.grid(row=2, column=0, columnspan=2, sticky="ew", padx=6, pady=(0, 6))
        ttk.Label(addrow, text=self.t("set_lang_pick")).pack(side="left")
        all_lang_displays = [f"{name} ({code})" for code, name in
                             sorted(WHISPER_LANGUAGES.items(), key=lambda kv: kv[1])]
        add_var = tk.StringVar()
        add_combo = ttk.Combobox(addrow, textvariable=add_var, values=all_lang_displays,
                                 state="readonly", width=28)
        add_combo.pack(side="left", padx=6)

        def add_lang():
            disp = add_var.get()
            m = re.search(r"\(([a-z]{2,3})\)\s*$", disp)
            if not m:
                return
            code = m.group(1)
            if code not in self.cfg["audio_langs"]:
                self.cfg["audio_langs"].append(code)
                self._save_config()
                fill_langs()
                self._refresh_audio_lang_dropdown()
                self._refresh_model_dropdown()
        ttk.Button(addrow, text=self.t("set_lang_add"), command=add_lang).pack(side="left", padx=4)

        def remove_lang():
            sel = lang_list.curselection()
            if not sel:
                return
            code = self.cfg["audio_langs"][sel[0]]
            self.cfg["audio_langs"].pop(sel[0])
            if not self.cfg["audio_langs"]:
                self.cfg["audio_langs"] = ["auto"]
            if self.cfg.get("audio_lang_code") == code:
                self.cfg["audio_lang_code"] = self.cfg["audio_langs"][0]
            self._save_config()
            fill_langs()
            self._refresh_audio_lang_dropdown()
            self._refresh_model_dropdown()
        ttk.Button(lf, text=self.t("set_lang_remove"), command=remove_lang
                   ).grid(row=1, column=1, sticky="w", padx=6)

        ttk.Button(frm, text=self.t("close"), command=dlg.destroy).grid(row=5, column=0, sticky="e", pady=8)
        refresh_status()
        if focus == "models":
            try:
                model_tree.focus_set()
            except tk.TclError:
                pass
        elif focus == "langs":
            try:
                lang_list.focus_set()
            except tk.TclError:
                pass

        # v0.12.1 (Bug B): lock in the *real* minimum size, computed after
        # every widget (including the models Treeview's guaranteed-3-row
        # minsize above) has been laid out — rather than a guessed pixel
        # value, which is exactly what went wrong on a different screen/
        # DPI setup in the first place.
        dlg.update_idletasks()
        dlg.minsize(max(560, dlg.winfo_reqwidth()), max(480, dlg.winfo_reqheight()))

    # ======================================================================
    # Settings: MarkItDown
    # ======================================================================
    def _open_conversion_tool_settings(self):
        """v0.13.8: hub dialog for the 4 selectable MD conversion models —
        pick the active one, see install status, jump to that model's own
        settings dialog. Replaces direct access to _open_markitdown_settings
        from the menu (still reachable from here, and still the dialog
        every other part of the app opens for pure MarkItDown-specific
        flows like the readiness indicators' click targets).

        v0.13.9: rebuilt as one card per model (name+status on their own
        line, description on its own full-width line below, buttons on
        their own line under that) instead of a single dense 5-column
        grid row per model — the grid version was too cramped for PT
        strings (typically longer than EN) and status/description text
        could visually run together. Also now refreshes on <FocusIn>, so
        coming back from a model's own Settings dialog (a separate
        Toplevel — installing something there doesn't touch this window)
        shows current status instead of whatever it was when this dialog
        first opened."""
        dlg = tk.Toplevel(self)
        dlg.title(self.t("set_convtool_title"))
        dlg.transient(self)
        dlg.geometry("640x560")
        dlg.minsize(560, 420)
        dlg.resizable(True, True)
        outer = ttk.Frame(dlg)
        outer.pack(fill="both", expand=True, padx=12, pady=12)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(1, weight=1)

        ttk.Label(outer, text=self.t("set_convtool_intro"), foreground="#555",
                  wraplength=600, justify="left").grid(
            row=0, column=0, sticky="ew", pady=(0, 10))

        scroll = ScrollableFrame(outer)
        scroll.grid(row=1, column=0, sticky="nsew")
        cards = scroll.inner
        cards.columnconfigure(0, weight=1)

        settings_openers = {
            "markitdown": self._open_markitdown_settings,
            "docling": self._open_docling_settings,
            "pandoc": self._open_pandoc_settings,
            "pysrt_webvtt": self._open_pysrt_webvtt_settings,
        }
        rows = {}

        def make_card(i, model_id):
            card = ttk.LabelFrame(cards, text="")
            card.grid(row=i, column=0, sticky="ew", pady=(0 if i == 0 else 8, 0))
            card.columnconfigure(0, weight=1)

            head = ttk.Frame(card)
            head.pack(fill="x", padx=8, pady=(6, 2))
            ttk.Label(head, text=conversion_model_display_name(model_id),
                     font=("TkDefaultFont", 10, "bold")).pack(side="left")
            status_var = tk.StringVar()
            status_lbl = ttk.Label(head, textvariable=status_var)
            status_lbl.pack(side="left", padx=(10, 0))

            ttk.Label(card, text=self.t(f"set_convtool_desc_{model_id}"),
                     foreground="#555", wraplength=560, justify="left").pack(
                fill="x", padx=8, pady=(0, 6))

            btns = ttk.Frame(card)
            btns.pack(fill="x", padx=8, pady=(0, 8))
            select_btn = ttk.Button(btns, text=self.t("set_convtool_select"),
                                    command=lambda: choose(model_id))
            select_btn.pack(side="left")
            ttk.Button(btns, text=self.t("set_convtool_configure"),
                      command=settings_openers[model_id]).pack(side="left", padx=(6, 0))
            rows[model_id] = (status_var, status_lbl, select_btn)

        for i, model_id in enumerate(CONVERSION_MODEL_IDS):
            make_card(i, model_id)

        def refresh():
            self._detect_dependencies()
            active = self._active_model()
            for model_id, (status_var, status_lbl, select_btn) in rows.items():
                installed = self._model_installed(model_id)
                if model_id == active:
                    status_var.set(self.t("set_convtool_selected"))
                    status_lbl.configure(foreground="#1a7f37")
                    select_btn.configure(state="disabled")
                elif installed:
                    status_var.set(self.t("dep_found"))
                    status_lbl.configure(foreground="#1a7f37")
                    select_btn.configure(state="normal")
                else:
                    status_var.set(self.t("dep_missing"))
                    status_lbl.configure(foreground="#cf222e")
                    select_btn.configure(state="normal")

        def choose(model_id):
            self.cfg["conversion_model"] = model_id
            self._save_config()
            refresh()
            self._refresh_status_indicators()

        refresh()
        dlg.bind("<FocusIn>", lambda e: refresh() if e.widget is dlg else None)
        ttk.Button(outer, text=self.t("close"), command=dlg.destroy).grid(
            row=2, column=0, sticky="e", pady=(12, 0))

    def _active_model(self):
        model = self.cfg.get("conversion_model") or "markitdown"
        if model not in CONVERSION_MODEL_IDS:
            model = "markitdown"
        return model

    def _model_installed(self, model_id):
        if model_id == "markitdown":
            return bool(self.markitdown_ok)
        if model_id == "docling":
            return bool(self.docling_ok)
        if model_id == "pandoc":
            return bool(self.pandoc_path)
        if model_id == "pysrt_webvtt":
            return subtitle_libs_available(self.python_exe)
        return False

    def _open_docling_settings(self):
        dlg = tk.Toplevel(self)
        dlg.title(self.t("set_docling_title"))
        dlg.transient(self)
        dlg.geometry("680x460")
        frm = ttk.Frame(dlg)
        frm.pack(fill="both", expand=True, padx=10, pady=10)
        frm.columnconfigure(0, weight=1)
        frm.rowconfigure(3, weight=1)

        ttk.Label(frm, text=self.t("set_docling_about"), foreground="#555",
                  wraplength=640).grid(row=0, column=0, sticky="w", pady=(0, 6))
        status_var = tk.StringVar()

        def refresh_status():
            self.docling_ok = docling_is_available(docling_env_dir_from_cfg(self.cfg))
            if self.docling_ok:
                status_var.set(self.t("set_docling_found"))
            else:
                status_var.set(self.t("set_docling_missing"))
            self._refresh_status_indicators()
        ttk.Label(frm, textvariable=status_var, foreground="#444",
                  wraplength=640).grid(row=1, column=0, sticky="w", pady=4)

        btnrow = ttk.Frame(frm)
        btnrow.grid(row=2, column=0, sticky="w", pady=4)
        log = tk.Text(frm, height=10, wrap="word", state="disabled", font=("TkFixedFont", 9))
        log.grid(row=3, column=0, sticky="nsew", pady=6)

        def on_change_done():
            inst_btn.configure(state="normal")
            refresh_status()
            upd_refresh()

        def install_docling():
            inst_btn.configure(state="disabled")
            self._update_docling(dlg, log, on_done=on_change_done,
                                 confirm_key="set_generic_install_q")
        inst_btn = ttk.Button(btnrow, text=self.t("set_docling_install"), command=install_docling)
        inst_btn.pack(side="left", padx=2)
        ttk.Button(btnrow, text=self.t("set_recheck"), command=refresh_status).pack(side="left", padx=2)
        ttk.Button(btnrow, text=self.t("set_open_folder"),
                  command=lambda: self._open_path(str(DOCLING_ENV_DIR))).pack(side="left", padx=2)

        def uninstall_docling():
            if not messagebox.askyesno(self.t("confirm"),
                                       self.t("confirm_uninstall_msg", path=str(DOCLING_ENV_DIR)),
                                       parent=dlg):
                return
            shutil.rmtree(str(DOCLING_ENV_DIR), ignore_errors=True)
            refresh_status()
            upd_refresh()
        ttk.Button(btnrow, text=self.t("set_uninstall"), command=uninstall_docling).pack(side="left", padx=2)

        upd_refresh = self._make_update_row(
            frm, 4,
            get_installed=lambda: get_pip_package_version(
                docling_venv_python(), "docling"),
            get_latest=lambda: check_pypi_latest_version("docling"),
            is_installed=lambda: bool(self.docling_ok),
            on_update_confirmed=lambda latest: self._update_docling(
                dlg, log, on_done=on_change_done, target_version=latest))
        ttk.Button(frm, text=self.t("close"), command=dlg.destroy).grid(row=6, column=0, sticky="e", pady=6)
        refresh_status()
        dlg.bind("<FocusIn>", lambda e: refresh_status() if e.widget is dlg else None)

    def _open_pandoc_settings(self):
        dlg = tk.Toplevel(self)
        dlg.title(self.t("set_pandoc_title"))
        dlg.transient(self)
        dlg.geometry("680x460")
        frm = ttk.Frame(dlg)
        frm.pack(fill="both", expand=True, padx=10, pady=10)
        frm.columnconfigure(0, weight=1)
        frm.rowconfigure(3, weight=1)

        ttk.Label(frm, text=self.t("set_pandoc_about"), foreground="#555",
                  wraplength=640).grid(row=0, column=0, sticky="w", pady=(0, 6))
        status_var = tk.StringVar()

        def refresh_status():
            self.pandoc_path = find_pandoc(self.cfg.get("pandoc_path") or None)
            if self.pandoc_path:
                status_var.set(self.t("set_pandoc_found", path=self.pandoc_path))
            else:
                status_var.set(self.t("dep_missing"))
            self._refresh_status_indicators()
        ttk.Label(frm, textvariable=status_var, foreground="#444",
                  wraplength=640).grid(row=1, column=0, sticky="w", pady=4)

        row1 = ttk.Frame(frm)
        row1.grid(row=2, column=0, sticky="w", pady=4)
        log = tk.Text(frm, height=10, wrap="word", state="disabled", font=("TkFixedFont", 9))
        log.grid(row=3, column=0, sticky="nsew", pady=6)

        def on_change_done():
            auto_btn.configure(state="normal")
            refresh_status()
            upd_refresh()

        def auto_install():
            if not messagebox.askyesno(
                    self.t("confirm"),
                    self.t("set_pandoc_auto_q", dest=str(PANDOC_INSTALL_DIR)), parent=dlg):
                return
            auto_btn.configure(state="disabled")
            self._start_pandoc_auto(log, lambda ok, path: on_change_done(),
                                    dest_dir=str(PANDOC_INSTALL_DIR))
        auto_btn = ttk.Button(row1, text=self.t("set_pandoc_install"), command=auto_install)
        auto_btn.pack(side="left", padx=2)
        ttk.Button(row1, text=self.t("set_open_folder"),
                  command=lambda: self._open_path(str(PANDOC_INSTALL_DIR))).pack(side="left", padx=2)

        def uninstall_pandoc():
            target = str(PANDOC_INSTALL_DIR)
            if not os.path.isdir(target):
                return
            if not messagebox.askyesno(self.t("confirm"),
                                       self.t("confirm_uninstall_msg", path=target),
                                       parent=dlg):
                return
            shutil.rmtree(target, ignore_errors=True)
            if self.cfg.get("pandoc_path") and not os.path.exists(self.cfg["pandoc_path"]):
                self.cfg["pandoc_path"] = ""
            self.cfg["pandoc_installed_version"] = ""
            self._save_config()
            refresh_status()
            upd_refresh()
        ttk.Button(row1, text=self.t("set_uninstall"), command=uninstall_pandoc).pack(side="left", padx=2)

        upd_refresh = self._make_update_row(
            frm, 4,
            get_installed=lambda: self.cfg.get("pandoc_installed_version") or None,
            get_latest=lambda: check_pandoc_latest_release(),
            is_installed=lambda: bool(self.pandoc_path),
            on_update_confirmed=lambda latest: self._update_pandoc(dlg, log, on_done=on_change_done))
        ttk.Button(frm, text=self.t("close"), command=dlg.destroy).grid(row=5, column=0, sticky="e", pady=6)
        refresh_status()
        dlg.bind("<FocusIn>", lambda e: refresh_status() if e.widget is dlg else None)

    def _open_pysrt_webvtt_settings(self):
        """No install controls of its own — pysrt/webvtt-py are installed
        as part of the MarkItDown/tools-venv flow (see _update_markitdown's
        extra_packages). This dialog just explains that and shows status."""
        dlg = tk.Toplevel(self)
        dlg.title(self.t("set_pysrt_webvtt_title"))
        dlg.transient(self)
        dlg.geometry("480x220")
        frm = ttk.Frame(dlg)
        frm.pack(fill="both", expand=True, padx=12, pady=12)
        ttk.Label(frm, text=self.t("set_pysrt_webvtt_about"), foreground="#555",
                  wraplength=440, justify="left").pack(anchor="w", pady=(0, 10))
        status_var = tk.StringVar()
        status_lbl = ttk.Label(frm, textvariable=status_var)
        status_lbl.pack(anchor="w", pady=4)

        def refresh_status():
            ok = subtitle_libs_available(self.python_exe)
            status_var.set(self.t("set_pysrt_webvtt_status_ok") if ok
                           else self.t("set_pysrt_webvtt_status_missing"))
            status_lbl.configure(foreground="#1a7f37" if ok else "#cf222e")
        refresh_status()
        btns = ttk.Frame(frm)
        btns.pack(fill="x", pady=(10, 0))
        ttk.Button(btns, text=self.t("set_pysrt_webvtt_open_markitdown"),
                  command=self._open_markitdown_settings).pack(side="left")
        ttk.Button(btns, text=self.t("close"), command=dlg.destroy).pack(side="right")
        dlg.bind("<FocusIn>", lambda e: refresh_status() if e.widget is dlg else None)

    def _open_markitdown_settings(self):
        dlg = tk.Toplevel(self)
        dlg.title(self.t("set_markitdown_title"))
        dlg.transient(self)
        dlg.geometry("680x460")
        frm = ttk.Frame(dlg)
        frm.pack(fill="both", expand=True, padx=10, pady=10)
        frm.columnconfigure(0, weight=1)
        frm.rowconfigure(3, weight=1)

        ttk.Label(frm, text=self.t("set_markitdown_about"), foreground="#555",
                  wraplength=640).grid(row=0, column=0, sticky="w", pady=(0, 6))
        status_var = tk.StringVar()

        def refresh_status():
            readiness = self._markitdown_readiness()
            if readiness == "ready":
                status_var.set(self.t("set_markitdown_found", py=self.python_exe))
            elif readiness == "broken":
                status_var.set(self.t("set_markitdown_broken"))
            else:
                status_var.set(self.t("set_markitdown_missing"))
            self._refresh_status_indicators()
        ttk.Label(frm, textvariable=status_var, foreground="#444",
                  wraplength=640).grid(row=1, column=0, sticky="w", pady=4)

        btnrow = ttk.Frame(frm)
        btnrow.grid(row=2, column=0, sticky="w", pady=4)
        log = tk.Text(frm, height=10, wrap="word", state="disabled", font=("TkFixedFont", 9))
        log.grid(row=3, column=0, sticky="nsew", pady=6)

        def on_change_done():
            inst_btn.configure(state="normal")
            refresh_status()
            upd_refresh()

        def install_md():
            # item 1.1/1.3: install into the app-managed tools venv, and
            # pin markitdown_python to that EXACT interpreter so the probe
            # afterward can never mismatch the install target.
            inst_btn.configure(state="disabled")
            self._update_markitdown(dlg, log, on_done=on_change_done,
                                    confirm_key="set_markitdown_install_q",
                                    fail_hint_key="set_tools_venv_rebuild_hint")
        inst_btn = ttk.Button(btnrow, text=self.t("set_markitdown_install"), command=install_md)
        inst_btn.pack(side="left", padx=2)
        ttk.Button(btnrow, text=self.t("set_recheck"), command=refresh_status).pack(side="left", padx=2)
        ttk.Button(btnrow, text=self.t("set_open_folder"),
                  command=lambda: self._open_path(str(TOOLS_VENV_DIR))).pack(side="left", padx=2)

        def uninstall_md():
            if not messagebox.askyesno(self.t("confirm"),
                                       self.t("confirm_uninstall_msg", path=str(TOOLS_VENV_DIR)),
                                       parent=dlg):
                return
            vpy = tools_venv_python()
            if os.path.exists(vpy):
                subprocess.run([vpy, "-m", "pip", "uninstall", "-y", "markitdown"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               **subprocess_hidden_window_kwargs())
            refresh_status()
            upd_refresh()
        ttk.Button(btnrow, text=self.t("set_uninstall"), command=uninstall_md).pack(side="left", padx=2)

        def rebuild_env():
            # v0.13.3: escape hatch for when even an exact version pin
            # can't resolve — the venv itself has accumulated conflicting
            # pins from earlier installs, not just this one package.
            rebuild_btn.configure(state="disabled")

            def done():
                rebuild_btn.configure(state="normal")
                on_change_done()
            self._rebuild_tools_venv(dlg, log, on_done=done)
        rebuild_btn = ttk.Button(btnrow, text=self.t("set_tools_venv_rebuild"), command=rebuild_env)
        rebuild_btn.pack(side="left", padx=2)

        upd_refresh = self._make_update_row(
            frm, 4,
            get_installed=lambda: get_pip_package_version(self.python_exe, "markitdown"),
            get_latest=lambda: check_pypi_latest_version("markitdown"),
            on_update_confirmed=lambda latest: self._update_markitdown(
                dlg, log, on_done=on_change_done, target_version=latest,
                fail_hint_key="set_tools_venv_rebuild_hint"))
        ttk.Button(frm, text=self.t("close"), command=dlg.destroy).grid(row=6, column=0, sticky="e", pady=6)
        refresh_status()
        dlg.bind("<FocusIn>", lambda e: refresh_status() if e.widget is dlg else None)

    # ======================================================================
    # Settings: FFmpeg
    # ======================================================================
    def _open_ffmpeg_settings(self):
        dlg = tk.Toplevel(self)
        dlg.title(self.t("set_ffmpeg_title"))
        dlg.transient(self)
        dlg.geometry("700x500")
        frm = ttk.Frame(dlg)
        frm.pack(fill="both", expand=True, padx=10, pady=10)
        frm.columnconfigure(0, weight=1)
        frm.rowconfigure(3, weight=1)

        status_var = tk.StringVar()

        def refresh_status():
            self.ffmpeg_path = find_ffmpeg(self.cfg.get("ffmpeg_path") or None)
            if self.ffmpeg_path:
                status_var.set(self.t("set_ffmpeg_found", path=self.ffmpeg_path))
            else:
                status_var.set(self.t("set_ffmpeg_missing"))
            self._refresh_status_indicators()
            self._update_clip_gate()
        ttk.Label(frm, textvariable=status_var, foreground="#444",
                  wraplength=660).grid(row=0, column=0, sticky="w", pady=(0, 6))

        row1 = ttk.Frame(frm)
        row1.grid(row=1, column=0, sticky="w", pady=4)

        def locate():
            current = self.cfg.get("ffmpeg_path") or ""
            p = filedialog.askopenfilename(
                title=self.t("select_ffmpeg_title"), parent=dlg,
                initialdir=self._existing_dir_or_home(os.path.dirname(current)))
            if p:
                self.cfg["ffmpeg_path"] = p
                self._save_config()
                refresh_status()
        ttk.Button(row1, text=self.t("ffmpeg_locate"), command=locate).pack(side="left", padx=2)

        def open_folder():
            self.ffmpeg_path = find_ffmpeg(self.cfg.get("ffmpeg_path") or None)
            if self.ffmpeg_path:
                self._open_path(os.path.dirname(self.ffmpeg_path))
        ttk.Button(row1, text=self.t("ffmpeg_open_folder"), command=open_folder).pack(side="left", padx=2)

        def uninstall_ffmpeg():
            target = str(FFMPEG_INSTALL_DIR)
            if not os.path.isdir(target):
                return
            if not messagebox.askyesno(self.t("confirm"),
                                       self.t("confirm_uninstall_msg", path=target),
                                       parent=dlg):
                return
            shutil.rmtree(target, ignore_errors=True)
            if self.cfg.get("ffmpeg_path") and not os.path.exists(self.cfg["ffmpeg_path"]):
                self.cfg["ffmpeg_path"] = ""
            self.cfg["ffmpeg_build_installed_at"] = ""
            self._save_config()
            refresh_status()
            upd_refresh()
        ttk.Button(row1, text=self.t("set_uninstall"), command=uninstall_ffmpeg).pack(side="left", padx=2)

        row2 = ttk.Frame(frm)
        row2.grid(row=2, column=0, sticky="w", pady=4)
        log = tk.Text(frm, height=10, wrap="word", state="disabled", font=("TkFixedFont", 9))
        log.grid(row=3, column=0, sticky="nsew", pady=6)

        def auto_install():
            chosen = filedialog.askdirectory(
                title=self.t("install_pick_dir_ffmpeg"), parent=dlg,
                initialdir=os.path.expanduser("~"))
            if not chosen:
                return
            dest = resolve_ffmpeg_dir(chosen)
            if not messagebox.askyesno(self.t("confirm"),
                                       self.t("set_ffmpeg_auto_q", dest=dest), parent=dlg):
                return
            auto_btn.configure(state="disabled")

            def finished(ok, path):
                auto_btn.configure(state="normal")
                refresh_status()
                upd_refresh()
            self._start_ffmpeg_auto(log, finished, dest_dir=dest)

        def winget_install():
            cmd = ["winget", "install", "-e", "--id", "Gyan.FFmpeg",
                   "--accept-package-agreements", "--accept-source-agreements"]
            self._append_text(log, self.t("install_running"))
            stop = threading.Event()
            q = queue.Queue()
            worker = CommandStreamWorker(cmd, q, stop, tag="ffmpeg")
            worker.start()

            def done(success, error):
                self._append_text(log, self.t("install_done_ok") if success
                                  else self.t("install_done_fail", code=error))
                refresh_status()
                upd_refresh()
            self._attach_stream(q, log, done)

        auto_btn = ttk.Button(row2, text=self.t("set_ffmpeg_install_auto"), command=auto_install)
        auto_btn.pack(side="left", padx=2)
        if os.name == "nt":
            ttk.Button(row2, text=self.t("set_ffmpeg_winget"), command=winget_install).pack(side="left", padx=2)
        ttk.Button(row2, text=self.t("set_ffmpeg_open_page"),
                   command=lambda: webbrowser.open(FFMPEG_DOWNLOAD_URL)).pack(side="left", padx=2)

        def update_ffmpeg():
            def done():
                refresh_status()
                upd_refresh()
            self._update_ffmpeg(dlg, log, on_done=done)

        upd_refresh = self._make_update_row(
            frm, 4,
            get_installed=lambda: self.cfg.get("ffmpeg_build_installed_at") or None,
            get_latest=lambda: check_ffmpeg_latest_build(),
            is_installed=lambda: bool(self.ffmpeg_path),
            on_update_confirmed=lambda latest: update_ffmpeg())
        ttk.Button(frm, text=self.t("close"), command=dlg.destroy).grid(row=5, column=0, sticky="e", pady=6)
        refresh_status()

    def _start_ffmpeg_auto(self, log_text, on_finish, dest_dir=None):
        q = queue.Queue()
        install_dir = Path(dest_dir) if dest_dir else FFMPEG_INSTALL_DIR

        def work():
            try:
                install_dir.mkdir(parents=True, exist_ok=True)
                url = FFMPEG_WIN_BUILD_URL
                q.put(("log", self.t("set_ffmpeg_downloading")))
                tmp = install_dir / "ffmpeg_download.zip"
                download_file_with_cert_fallback(url, str(tmp))
                q.put(("log", self.t("set_ffmpeg_extracting")))
                exe = extract_ffmpeg_archive(str(tmp), install_dir)
                try:
                    tmp.unlink()
                except OSError:
                    pass
                if not exe:
                    raise RuntimeError("ffmpeg executable not found in archive")
                self.cfg["ffmpeg_path"] = exe
                self.cfg["ffmpeg_build_installed_at"] = datetime.utcnow().isoformat() + "Z"
                self._save_config()
                q.put(("done", exe))
            except Exception as e:
                q.put(("fail", friendly_download_error(e)))
        threading.Thread(target=work, daemon=True).start()

        def poll():
            try:
                while True:
                    k, v = q.get_nowait()
                    if k == "log":
                        self._append_text(log_text, v)
                    elif k == "done":
                        self._append_text(log_text, self.t("set_ffmpeg_done", path=v))
                        on_finish(True, v)
                        return
                    elif k == "fail":
                        self._append_text(log_text, self.t("set_ffmpeg_fail", e=v))
                        on_finish(False, v)
                        return
            except queue.Empty:
                pass
            self.after(150, poll)
        poll()

    def _start_pandoc_auto(self, log_text, on_finish, dest_dir=None):
        """Same shape as _start_ffmpeg_auto() above, with one structural
        difference: pandoc's download URL is version-tagged (no fixed
        "latest" URL like BtbN's ffmpeg builds), so the release has to be
        looked up first — done here, in the same background thread,
        rather than requiring the caller to have already checked."""
        q = queue.Queue()
        install_dir = Path(dest_dir) if dest_dir else PANDOC_INSTALL_DIR

        def work():
            try:
                tag, err = check_pandoc_latest_release()
                if not tag:
                    q.put(("no_release", err or "unknown"))
                    return
                install_dir.mkdir(parents=True, exist_ok=True)
                url = pandoc_windows_asset_url(tag)
                q.put(("log", self.t("set_pandoc_downloading", tag=tag)))
                tmp = install_dir / "pandoc_download.zip"
                download_file_with_cert_fallback(url, str(tmp))
                q.put(("log", self.t("set_pandoc_extracting")))
                exe = extract_pandoc_archive(str(tmp), install_dir)
                try:
                    tmp.unlink()
                except OSError:
                    pass
                if not exe:
                    raise RuntimeError("pandoc executable not found in archive")
                self.cfg["pandoc_path"] = exe
                self.cfg["pandoc_installed_version"] = tag
                self._save_config()
                q.put(("done", exe))
            except Exception as e:
                q.put(("fail", friendly_download_error(e)))
        threading.Thread(target=work, daemon=True).start()

        def poll():
            try:
                while True:
                    k, v = q.get_nowait()
                    if k == "log":
                        self._append_text(log_text, v)
                    elif k == "done":
                        self._append_text(log_text, self.t("set_pandoc_done", path=v))
                        on_finish(True, v)
                        return
                    elif k == "no_release":
                        self._append_text(log_text, self.t("set_pandoc_no_release", e=v))
                        on_finish(False, v)
                        return
                    elif k == "fail":
                        self._append_text(log_text, self.t("set_pandoc_fail", e=v))
                        on_finish(False, v)
                        return
            except queue.Empty:
                pass
            self.after(150, poll)
        poll()

    # ======================================================================
    # Settings: Output formats
    # ======================================================================
    def _open_output_formats(self):
        dlg = tk.Toplevel(self)
        dlg.title(self.t("output_formats_title"))
        dlg.transient(self)
        dlg.geometry("640x360")
        frm = ttk.Frame(dlg)
        frm.pack(fill="both", expand=True, padx=12, pady=12)
        frm.columnconfigure(0, weight=1)
        ttk.Label(frm, text=self.t("output_formats")).grid(row=0, column=0, sticky="w", pady=(0, 6))
        self.format_vars = {}
        for i, fmt in enumerate(OUTPUT_FORMATS):
            var = tk.BooleanVar(value=self.cfg["output_formats"].get(fmt, True))
            self.format_vars[fmt] = var

            def make_cb(f=fmt, v=var):
                def cb():
                    self.cfg["output_formats"][f] = v.get()
                    self._save_config()
                return cb
            ttk.Checkbutton(frm, text=self.t("fmt_" + fmt), variable=var,
                            command=make_cb()).grid(row=i + 1, column=0, sticky="w", pady=2)
        ttk.Button(frm, text=self.t("close"), command=dlg.destroy
                   ).grid(row=len(OUTPUT_FORMATS) + 1, column=0, sticky="e", pady=10)

    # ======================================================================
    # About
    # ======================================================================
    def _open_about(self):
        dlg = tk.Toplevel(self)
        dlg.title(self.t("about_title"))
        dlg.transient(self)
        dlg.resizable(False, False)
        frm = ttk.Frame(dlg)
        frm.pack(fill="both", expand=True, padx=24, pady=20)
        try:
            ttk.Label(frm, image=self._icon_img_large).pack(pady=(0, 8))
        except Exception:
            pass
        ttk.Label(frm, text=APP_NAME, font=("TkDefaultFont", 16, "bold")).pack()
        ttk.Label(frm, text=f"{self.t('about_version')}: {APP_VERSION}").pack(pady=(8, 0))
        ttk.Label(frm, text=f"{self.t('about_author')}: {APP_AUTHOR}").pack()
        contact_row = ttk.Frame(frm)
        contact_row.pack()
        ttk.Label(contact_row, text=f"{self.t('about_contact')}: ").pack(side="left")
        email = tk.Label(contact_row, text=APP_CONTACT, fg="#0a58ca",
                         cursor="hand2", font=("TkDefaultFont", 9, "underline"))
        email.pack(side="left")
        email.bind("<Button-1>", lambda e: self._open_contact_email())

        ttk.Separator(frm, orient="horizontal").pack(fill="x", pady=(12, 8))
        ttk.Label(frm, text=self.t("about_tools_title"),
                  font=("TkDefaultFont", 10, "bold")).pack(anchor="w")
        tools_frame = ttk.Frame(frm)
        tools_frame.pack(fill="x", pady=(4, 0))
        for i, (name, version) in enumerate(self._installed_tool_versions()):
            ttk.Label(tools_frame, text=name).grid(
                row=i, column=0, sticky="w", padx=(0, 16), pady=1)
            if version:
                ttk.Label(tools_frame, text=version, foreground="#1a7f37").grid(
                    row=i, column=1, sticky="w", pady=1)
            else:
                ttk.Label(tools_frame, text=self.t("set_not_installed"),
                          foreground="#cf222e").grid(row=i, column=1, sticky="w", pady=1)

        if self._lan_server.running:
            ttk.Label(frm, text=self.t("lan_running_at", url=self._lan_reachable_url()),
                      foreground="#8250df", wraplength=340).pack(pady=(8, 0))
        ttk.Button(frm, text=self.t("close"), command=dlg.destroy).pack(pady=(16, 0))

    def _open_contact_email(self):
        try:
            webbrowser.open("mailto:" + APP_CONTACT)
        except Exception:
            pass

    # ======================================================================
    # Open helpers
    # ======================================================================
    def _existing_dir_or_home(self, path):
        """item 11: Browse dialogs open at the folder currently shown in
        that field, falling back to the home folder only when the field is
        empty or points at a folder that no longer exists (never silently
        falls back to whatever folder Explorer last remembered)."""
        if path and os.path.isdir(path):
            return path
        return os.path.expanduser("~")

    def _open_path(self, path):
        if not path or not os.path.exists(path):
            return
        try:
            if os.name == "nt":
                os.startfile(path)  # noqa
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception:
            pass

    def _open_output_folder(self):
        for it in self.queue_items:
            if it.output_dir:
                self._open_path(it.output_dir)
                return

    def _md_open_output_folder(self):
        for it in self.md_queue_items:
            if it.output_dir:
                self._open_path(it.output_dir)
                return

    # ======================================================================
    # Transcription run
    # ======================================================================
    def _selected_keep_formats(self):
        return [f for f in OUTPUT_FORMATS if self.cfg["output_formats"].get(f, False)]

    def _selected_dictionary_payload(self):
        name = self.dict_var.get()
        if not name or name == self.t("none"):
            return "", []
        prof = self.dictionaries.get(name, {})
        return (prof.get("initial_prompt") or prof.get("prompt") or ""), prof.get("replacements", [])

    def _validate_clip(self):
        if not self.clip_enabled_var.get():
            return None, None
        if not self.ffmpeg_path:
            return None, "err_clip_needs_ffmpeg"
        start = parse_hms_to_seconds(self.clip_start_var.get())
        end = parse_hms_to_seconds(self.clip_end_var.get())
        if start is None or end is None or end <= start:
            return None, "err_clip_invalid"
        return (start, end), None

    def _start_batch(self):
        if self.is_running:
            return
        if not self.queue_items:
            messagebox.showerror(self.t("error"), self.t("err_no_files"))
            return
        readiness = self._whisper_readiness()
        if readiness != "ready":
            messagebox.showerror(
                self.t("error"),
                self.t("err_whisper_broken") if readiness == "broken"
                else self.t("err_no_whisper"))
            self._open_whisper_settings()
            return
        installed = models_for_audio_language(
            self.cfg.get("audio_lang_code", "pt"), only_installed=True)
        model = self.cfg.get("model_cli", "")
        if not installed or model not in installed:
            messagebox.showerror(self.t("error"), self.t("err_no_model_selected"))
            self._open_whisper_settings(focus="models")
            return
        keep = self._selected_keep_formats()
        if not keep:
            messagebox.showerror(self.t("error"), self.t("err_no_format"))
            self._open_output_formats()
            return
        if self.outdir_mode_var.get() == "fixed" and not self.fixed_dir_var.get().strip():
            messagebox.showerror(self.t("error"), self.t("err_no_fixed_dir"))
            return
        clip_range, clip_err = self._validate_clip()
        if clip_err:
            messagebox.showerror(self.t("error"), self.t(clip_err))
            return
        if not self.ffmpeg_path:
            if not messagebox.askyesno(self.t("warn"), self.t("ffmpeg_missing_warn")):
                return
        if not self._confirm_header_before_start():
            return

        # reset statuses
        for it in self.queue_items:
            it.status = ST_PENDING
            it.error_message = ""
            it.output_dir = None
        self._render_queue()

        prompt, replacements = self._selected_dictionary_payload()
        lang_param = audio_lang_param(self.cfg.get("audio_lang_code", "pt"))
        task = self.cfg.get("task", "transcribe")

        self.stop_flag = threading.Event()
        self.live_queue = LiveQueue(self.queue_items)
        self.worker = TranscriptionWorker(
            live_queue=self.live_queue, whisper_exe=self.whisper_path,
            ffmpeg_path=self.ffmpeg_path, lang_param=lang_param, task=task,
            model_name=model, initial_prompt=prompt, replacements=replacements,
            keep_formats=keep, output_dir_mode=self.outdir_mode_var.get(),
            fixed_output_dir=self.fixed_dir_var.get().strip(),
            clip_range=clip_range, strings=self.s,
            event_queue=self.event_queue, stop_flag=self.stop_flag,
            header_config=self._active_header_config(),
            polish=self._polish_enabled(),
            header_lang=self.cfg.get("header_lang", "pt"),
            keep_timestamps=self._keep_timestamps_enabled(),
            model_id=self._active_model(), markitdown_ok=self.markitdown_ok,
            python_exe=self.python_exe)
        self._finished["av"] = False
        self.is_running = True
        self._batch_start_time = time.time()
        self._batch_done = 0
        self._batch_errors = 0
        self._cur_duration = None
        self._batch_model = model
        total, n_known, total_seconds = queue_length_summary(self.queue_items)
        self._trans_total_seconds = total_seconds
        self._trans_done_seconds = 0.0
        self._cur_position = 0.0
        self._cur_running_id = None
        self._set_progress(self.progress, self.progress_pct_var, 0.0)
        self._set_running_ui(True)
        self._clear_log(self.log_text)
        self._append_text(self.log_text, self.t("log_batch_start",
                                                time=datetime.now().strftime("%H:%M:%S")))
        self.worker.start()

    def _cancel_batch(self):
        if self.is_running and self.worker:
            if messagebox.askyesno(self.t("cancel_title"), self.t("cancel_question")):
                self._append_text(self.log_text, self.t("log_canceling"))
                self.worker.cancel()

    def _set_running_ui(self, running):
        self.start_btn.configure(state="disabled" if running else "normal")
        self.cancel_btn.configure(state="normal" if running else "disabled")
        self.open_out_btn.configure(state="disabled" if running else "normal")
        if hasattr(self, "clear_queue_btn"):
            self.clear_queue_btn.configure(state="disabled" if running else "normal")

    def _clear_log(self, widget):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.configure(state="disabled")

    def _poll_events(self):
        try:
            while True:
                ev = self.event_queue.get_nowait()
                self._handle_event(ev)
        except queue.Empty:
            pass
        self.after(120, self._poll_events)

    def _handle_event(self, ev):
        kind = ev.get("kind")
        if kind == "log":
            self._append_text(self.log_text, ev.get("text", ""))
        elif kind == "item_status":
            item_id = ev.get("item_id")
            status = ev.get("status")
            it = next((q for q in self.queue_items if q.item_id == item_id), None)
            if it is not None:
                it.status = status
                try:
                    self.tree.set(str(item_id), "status", self._status_text(status))
                except tk.TclError:
                    pass   # row may have been removed from the tree already
            if status == ST_RUNNING:
                self._cur_running_id = item_id
                self._cur_position = 0.0
                self._cur_file_start = time.time()
                self._cur_item_duration = it.duration if it is not None else None
                self._update_trans_progress_label()
            elif status in ST_TERMINAL:
                if status == ST_DONE:
                    self._batch_done += 1
                elif status == ST_ERROR:
                    self._batch_errors += 1
                dur = getattr(self, "_cur_item_duration", None)
                if isinstance(dur, (int, float)) and dur > 0:
                    self._trans_done_seconds += float(dur)
                    if status == ST_DONE:
                        wall = time.time() - getattr(self, "_cur_file_start", time.time())
                        if wall > 0:
                            self._set_speed_factor(getattr(self, "_batch_model", ""),
                                                   wall / float(dur))
                self._cur_position = 0.0
                self._cur_item_duration = None
                self._update_trans_progress_label()
        elif kind == "duration":
            self._cur_duration = ev.get("seconds")
            if not getattr(self, "_cur_item_duration", None):
                self._cur_item_duration = ev.get("seconds")
        elif kind == "phase":
            phase = ev.get("phase")
            if phase == "preparing":
                self.progress_label_var.set(self.t("phase_preparing"))
            elif phase == "transcribing":
                self._set_progress(self.progress, self.progress_pct_var,
                                   self._current_trans_percent())
                self.progress_label_var.set(self.t("phase_transcribing_note"))
        elif kind == "progress_tick":
            pos = ev.get("seconds")
            if pos is not None:
                self._cur_position = float(pos)
            self._update_trans_progress_label()
        elif kind == "batch_finished":
            self._on_batch_finished(env_broken=ev.get("env_broken", False))

    def _current_trans_percent(self):
        total_items = len(self.queue_items)
        done_items = self._batch_done + self._batch_errors
        return compute_batch_percent(
            self._trans_done_seconds, self._cur_position,
            self._trans_total_seconds, done_items, total_items)

    def _update_trans_progress_label(self):
        pct = self._current_trans_percent()
        self._set_progress(self.progress, self.progress_pct_var, pct)
        total_items = max(1, len(self.queue_items))
        done_items = self._batch_done + self._batch_errors
        cur = current_processing_index(done_items, total_items, self.is_running)
        cumulative = self._trans_done_seconds + max(0.0, self._cur_position)
        sf, confident = self._get_speed_factor(getattr(self, "_batch_model", ""))
        # Self-correct mid-file: blend the persisted historical factor with the
        # live wall/audio ratio observed so far in the file currently running,
        # so a long single file's ETA doesn't stay frozen at a stale estimate
        # for its entire duration (the original bug: it only updated *after*
        # a file finished, so an 8h file with a 2h estimate never corrected).
        live_wall = max(0.0, time.time() - getattr(self, "_cur_file_start", time.time()))
        live_pos = max(0.0, self._cur_position)
        if live_pos > 30:   # ignore noisy ratio in the first ~30s of audio progress
            live_sf = live_wall / live_pos
            weight = min(1.0, live_pos / 600.0)   # ramps to full trust over ~10min in
            sf = (1.0 - weight) * sf + weight * live_sf
        eta_txt = "—"
        if self._trans_total_seconds and self._trans_total_seconds > 0:
            remaining = max(0.0, self._trans_total_seconds - cumulative)
            eta_txt = fmt_hms(remaining * max(0.01, sf))
            if not confident:
                eta_txt += " " + self.t("eta_low_confidence_suffix")
        line = (self.t("batch_progress", done=cur, total=total_items)
                + "   ·   " + self.t("status_cur_pos", pos=fmt_hms(self._cur_position))
                + "   ·   " + self.t("status_total_transcribed",
                                     val=fmt_hms(cumulative))
                + "   ·   " + self.t("status_eta_complete", eta=eta_txt))
        self.progress_label_var.set(line)

    def _on_batch_finished(self, env_broken=False):
        self.is_running = False
        self._finished["av"] = True
        self.worker = None
        self.live_queue = None
        self._set_progress(self.progress, self.progress_pct_var, 100.0)
        self._set_running_ui(False)
        self._append_text(self.log_text, self.t("log_batch_end",
                                                time=datetime.now().strftime("%H:%M:%S")))
        self.progress_label_var.set(self.t("batch_finished_label",
                                    done=self._batch_done, errors=self._batch_errors))
        if env_broken:
            # v0.12.4: the reactive check fired and the worker stopped
            # itself rather than repeating this on every remaining file.
            # Same actionable message + redirect as the proactive check —
            # watching the log scroll by isn't the same as being told
            # there's an actual fix available.
            messagebox.showerror(self.t("error"), self.t("err_whisper_broken"))
            self._open_whisper_settings()
        elif self._batch_errors:
            messagebox.showwarning(self.t("finished_with_errors_title"),
                                   self.t("finished_with_errors_msg",
                                          done=self._batch_done, errors=self._batch_errors))
        else:
            messagebox.showinfo(self.t("finished_title"),
                                self.t("finished_msg", done=self._batch_done))

    # ======================================================================
    # MD batch run
    # ======================================================================
    def _start_md_batch(self):
        if self.md_is_running:
            return
        if not self.md_queue_items:
            messagebox.showerror(self.t("error"), self.t("err_no_files"))
            return
        model_id = self._active_model()
        installed_models = [m for m in CONVERSION_MODEL_IDS if self._model_installed(m)]
        if not self._model_installed(model_id):
            messagebox.showerror(self.t("error"),
                                 self.t("err_model_not_ready",
                                        model=conversion_model_display_name(model_id)))
            self._open_conversion_tool_settings()
            return
        unsupported = find_unsupported_queue_items(
            [it.filepath for it in self.md_queue_items], model_id, installed_models)
        if unsupported:
            self._show_unsupported_format_dialog(model_id, unsupported)
            return
        if self.md_outdir_mode_var.get() == "fixed" and not self.md_fixed_dir_var.get().strip():
            messagebox.showerror(self.t("error"), self.t("err_no_fixed_dir"))
            return
        if not self._confirm_header_before_start():
            return
        for it in self.md_queue_items:
            it.status = ST_PENDING
            it.error_message = ""
            it.output_dir = None
        self._render_md_queue()
        self.md_stop_flag = threading.Event()
        self.md_worker = ConversionWorker(
            items=self.md_queue_items, python_exe=markitdown_python(self.cfg),
            markitdown_ok=self.markitdown_ok,
            output_dir_mode=self.md_outdir_mode_var.get(),
            fixed_output_dir=self.md_fixed_dir_var.get().strip(),
            strings=self.s, event_queue=self.md_event_queue, stop_flag=self.md_stop_flag,
            header_config=self._active_header_config(),
            ffmpeg_path=self.ffmpeg_path, polish=self._polish_enabled(),
            header_lang=self.cfg.get("header_lang", "pt"),
            keep_timestamps=self._keep_timestamps_enabled(),
            model_id=model_id, docling_ok=self.docling_ok, pandoc_path=self.pandoc_path)
        self._finished["md"] = False
        self.md_is_running = True
        self._md_done = 0
        self._md_errors = 0
        self._md_total = len(self.md_queue_items)
        self.md_start_btn.configure(state="disabled")
        self.md_cancel_btn.configure(state="normal")
        self.md_open_out_btn.configure(state="disabled")
        self._clear_log(self.md_log_text)
        self._append_text(self.md_log_text, self.t("log_batch_start",
                                                   time=datetime.now().strftime("%H:%M:%S")))
        self.md_progress.configure(value=0)
        self.md_worker.start()

    def _show_unsupported_format_dialog(self, model_id, unsupported):
        dlg = tk.Toplevel(self)
        dlg.title(self.t("md_unsupported_title"))
        dlg.transient(self)
        dlg.geometry("560x420")
        frm = ttk.Frame(dlg)
        frm.pack(fill="both", expand=True, padx=12, pady=12)
        ttk.Label(frm, text=self.t("md_unsupported_intro",
                                   model=conversion_model_display_name(model_id)),
                 wraplength=520, justify="left").pack(anchor="w", pady=(0, 8))
        text = tk.Text(frm, wrap="word", height=16)
        text.pack(fill="both", expand=True)
        for fp, alternatives in unsupported:
            names = ", ".join(conversion_model_display_name(m) for m in alternatives) \
                if alternatives else self.t("md_unsupported_none")
            text.insert("end", self.t("md_unsupported_row",
                                      name=os.path.basename(fp), models=names) + "\n")
        text.configure(state="disabled")
        ttk.Button(frm, text=self.t("close"), command=dlg.destroy).pack(anchor="e", pady=(8, 0))

    def _open_md_model_chooser(self):
        installed_models = [m for m in CONVERSION_MODEL_IDS if self._model_installed(m)]
        dlg = tk.Toplevel(self)
        dlg.title(self.t("md_model_choose_title"))
        dlg.transient(self)
        dlg.geometry("420x260")
        frm = ttk.Frame(dlg)
        frm.pack(fill="both", expand=True, padx=12, pady=12)
        ttk.Label(frm, text=self.t("md_model_choose_intro"), wraplength=380,
                 justify="left", foreground="#555").pack(anchor="w", pady=(0, 10))
        active = self._active_model()
        var = tk.StringVar(value=active)
        for model_id in CONVERSION_MODEL_IDS:
            state = "normal" if model_id in installed_models else "disabled"
            label = conversion_model_display_name(model_id)
            if model_id not in installed_models:
                label += " (" + self.t("set_not_installed") + ")"
            ttk.Radiobutton(frm, text=label, value=model_id, variable=var,
                            state=state).pack(anchor="w", pady=2)

        def apply():
            self.cfg["conversion_model"] = var.get()
            self._save_config()
            self._refresh_md_model_line()
            dlg.destroy()
        btns = ttk.Frame(frm)
        btns.pack(fill="x", pady=(10, 0))
        ttk.Button(btns, text=self.t("set_convtool_select"), command=apply).pack(side="left")
        ttk.Button(btns, text=self.t("close"), command=dlg.destroy).pack(side="right")

    def _refresh_md_model_line(self):
        model_id = self._active_model()
        ok = self._model_installed(model_id)
        mark = self.t("dep_found") if ok else self.t("dep_missing")
        self.md_model_line_var.set(self.t(
            "md_model_line", model=conversion_model_display_name(model_id), status=mark))
        self.md_model_line_lbl.configure(foreground="#1a7f37" if ok else "#cf222e")

    def _cancel_md_batch(self):
        if self.md_is_running and self.md_worker:
            if messagebox.askyesno(self.t("cancel_title"), self.t("cancel_question")):
                self._append_text(self.md_log_text, self.t("log_canceling"))
                self.md_worker.cancel()

    def _poll_md_events(self):
        try:
            while True:
                ev = self.md_event_queue.get_nowait()
                self._handle_md_event(ev)
        except queue.Empty:
            pass
        self.after(120, self._poll_md_events)

    def _handle_md_event(self, ev):
        kind = ev.get("kind")
        if kind == "md_log":
            self._append_text(self.md_log_text, ev.get("text", ""))
        elif kind == "md_item_status":
            idx = ev.get("index")
            status = ev.get("status")
            if 0 <= idx < len(self.md_queue_items):
                it = self.md_queue_items[idx]
                it.status = status
                try:
                    self.md_tree.set(str(it.item_id), "status", self._md_status_text(status))
                except tk.TclError:
                    pass
            if status == ST_RUNNING:
                self._md_cur_index = idx
                self._update_md_progress_label()
            elif status in ST_TERMINAL:
                if status == ST_DONE:
                    self._md_done += 1
                elif status == ST_ERROR:
                    self._md_errors += 1
                self._update_md_progress_label()
        elif kind == "md_batch_finished":
            self._on_md_batch_finished()

    def _update_md_progress_label(self):
        total = max(1, getattr(self, "_md_total", 1))
        done = self._md_done + self._md_errors
        pct = compute_batch_percent(0, 0, 0, done, total)
        self._set_progress(self.md_progress, self.md_progress_pct_var, pct)
        cur = current_processing_index(done, total, self.md_is_running)
        self.md_progress_label_var.set(self.t("batch_progress", done=cur, total=total))

    def _on_md_batch_finished(self):
        self.md_is_running = False
        self._finished["md"] = True
        self.md_worker = None
        self._set_progress(self.md_progress, self.md_progress_pct_var, 100.0)
        self.md_start_btn.configure(state="normal")
        self.md_cancel_btn.configure(state="disabled")
        self.md_open_out_btn.configure(state="normal")
        self._append_text(self.md_log_text, self.t("log_batch_end",
                                                   time=datetime.now().strftime("%H:%M:%S")))
        self.md_progress_label_var.set(self.t("batch_finished_label",
                                       done=self._md_done, errors=self._md_errors))
        if self._md_errors:
            messagebox.showwarning(self.t("finished_with_errors_title"),
                                   self.t("finished_with_errors_msg",
                                          done=self._md_done, errors=self._md_errors))
        else:
            messagebox.showinfo(self.t("finished_title"),
                                self.t("finished_msg", done=self._md_done))

    # ======================================================================
    # Language switch / close
    # ======================================================================
    def _switch_language(self, code):
        if code not in TRANSLATIONS or code == self.lang:
            return
        if (self.is_running or self.md_is_running or self.youtube_is_running
                or self.download_is_running or self.grabber_is_running
                or self.comparison_is_running):
            self._menu_lang_var.set(self.lang)
            messagebox.showwarning(self.t("warn"), self.t("warn_queue_locked"))
            return
        self.lang = code
        self.s = TRANSLATIONS[code]
        self.cfg["ui_language"] = code
        self._save_config()
        self.title(self.s["window_title"])
        self._build_menubar()
        self._build_ui()
        self._render_queue()
        self._render_md_queue()
        self._render_youtube_queue()
        self._render_download_queue()
        self._render_comparison_queue()
        self._render_comparison_results()
        self._update_trans_summary()
        self._update_md_summary()
        self._update_youtube_summary()
        self._update_download_summary()

    def _on_close(self):
        if (self.is_running or self.md_is_running or self.youtube_is_running
                or self.download_is_running or self.comparison_is_running):
            if not messagebox.askyesno(self.t("exit_title"), self.t("exit_question")):
                return
            if self.worker:
                self.worker.cancel()
            if self.md_worker:
                self.md_worker.cancel()
            if self.youtube_worker and self.youtube_stop_flag:
                self.youtube_stop_flag.set()
            if self.download_worker:
                self.download_worker.cancel()
            if self.grabber_worker and self.grabber_stop_flag:
                self.grabber_stop_flag.set()
            if self.comparison_worker and self.comparison_stop_flag:
                self.comparison_stop_flag.set()
        self._save_queues_state()
        self._lan_stop_server()
        self.destroy()


def main():
    app = TranscriptLabApp()
    app.mainloop()


if __name__ == "__main__":
    main()
