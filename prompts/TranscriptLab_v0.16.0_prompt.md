# TranscriptLab v0.16.0 — implementation prompt

Attached: `TranscriptLab_v_0_15_6.py` (24,633 lines, single-file Python 3.12 / Tkinter Windows app, `APP_VERSION = "0.15.6"`). You are the primary implementer. Deliver `TranscriptLab_v_0_16_0.py`.

## 0. Workflow rules (non-negotiable)

1. Before any code: read the file and verify every claim below against the real source (function names, line anchors, config keys, TRANSLATIONS keys). Report discrepancies before planning.
2. Work in three phases. For each phase: present a brief numbered plan → wait for "Continue" → implement. Blocking questions go before the plan, never inside it.
3. Copy the upload to `/home/claude/work/` and edit only that working file via `str_replace`. `ast.parse` compile-check after every edit.
4. Bump `APP_VERSION` to `0.16.0` at Phase 1; do not bump again.
5. Every new user-facing string: matched PT-BR + EN pair in `TRANSLATIONS`. Run the existing translation-parity test after each phase.
6. Test gate per phase: two consecutive clean full test-suite runs under `xvfb-run`. Tests use portable config next to the .py, so each test must delete config and force language in `setUp` — do not rely on HOME swapping. Check that new tests exercise the new code path, not stale in-memory state.
7. Worker/UI contract: all background work in `threading.Thread` subclasses that communicate only through `event_queue.put()` / `post()`; workers never touch Tk widgets. No network calls without explicit user action.
8. Windows path logic tested on Linux must be built with `os.path.join` / `os.sep`, never literal backslashes.
9. Verify any external library version / API against live docs (pip metadata, GitHub README), not from memory.
10. Response style: no preamble, minimal markdown, short numbered plans, on failure show only the relevant log and a one-line fix.

## Phase 1 — Comparison tab (`_build_comparison_tab`, ~L20786; `ComparisonWorker`, ~L13847)

### 1.1 "Clean All" button
- `_comparison_clear_queue` (~L21037) stays as is (queue only), consistent with other tabs.
- Add a "Clean All" button immediately to the right of the "Export Report..." button (`cmp_export_button`). Handler `_comparison_clean_all`:
  - clears the queue (reuse `_comparison_clear_queue`),
  - clears match list / pair results / both previews (`_comparison_clear_preview`), status line, stored `comparison_results` data, the base-index cache, and removes the stale safety-net file if present (see `_comparison_check_stale_safety_net`),
  - keeps both folder paths and sampling settings untouched,
  - disabled while a comparison is running; re-enabled when the worker posts its final event.
- New strings: `cmp_clean_all_button`, and a confirmation if the tab currently holds results (`cmp_clean_all_confirm`).

### 1.2 Comparison Folder 2
- Rename visible label `cmp_base_folder_frame` → "Comparison Folder 1 (optional)" / "Pasta de Comparação 1 (opcional)". Keep config key `comparison_base_folder` unchanged (label change only, no migration).
- Add a second LabelFrame directly below: "Comparison Folder 2 (optional)", var `cmp_folder2_var`, config key `comparison_folder_2` (default `""`), persisted on change exactly like folder 1. Browse handler `_comparison_browse_folder2` mirrors `_comparison_browse_base_folder` (~L20994). Renumber `root.rowconfigure` / grid rows; confirm the row with `weight=1` still points at the results area.
- `_comparison_launch_worker` (~L21164) builds the folder list and passes it; update every `ComparisonWorker(...)` call site and any test constructing the worker.
- `ComparisonWorker.__init__`: replace `base_folder` with `base_folders` (list of 0–2 normalized, existing, deduplicated folder paths). Normalize with `os.path.normcase(os.path.abspath(...))` before dedup so the same folder typed twice collapses to one.
- Scenario detection in `run()` (update the docstring):
  - Queue + ≥1 folder: Phase 2a matches each queued file against the union of all `.md` files from both folders, one match list; Phase 2b unchanged.
  - Queue only: unchanged.
  - Empty queue + both folders (distinct): cross-pairs only — every MD in F1 vs every MD in F2, no within-folder pairs.
  - Empty queue + exactly one folder (or both set to the same path): existing Scenario 3 (all-pairs within that folder).
  - Nothing set: existing "nothing to do" message.
- Base-index cache (`base_index_cache`) keyed by the tuple of normalized folder paths so a folder change invalidates it. Cross-pair results reuse the existing pair-result structure; report (`build_comparison_report_text`, ~L10714) shows which folder each file came from (prefix or a "Folder 1 / Folder 2" column) and the status line names the scenario.
- Safety-net file: include both folder paths in the stale-check metadata.
- Edge cases to handle explicitly: folder path no longer exists (warn, treat as unset); folder contains zero `.md`; F1 ⊂ F2 overlap by file path (dedup in the union).

### 1.3 Tests (Phase 1)
Scenario detection unit tests for all five branches; dedup of identical folders; Clean All resets every state attribute and button states; translation parity; existing comparison tests unchanged.

## Phase 2 — Podcast tab: transcribe audio after download

Mirror the Download tab's v0.9.0 feature (`_transcribe_after` in `DownloadWorker`, ~L12750; settings helpers `_dl_whisper_is_valid` / `_refresh_dl_whisper_check` / `_open_dl_whisper_settings`, ~L18125–18136; config keys `download_transcribe`, `download_whisper_*`).

### 2.1 UI (`_build_podcast_tab`, ~L18600 area)
- Checkbox "Transcribe audio after download" / "Transcrever o áudio após o download" (`pod_transcribe_after`), plus the same companion controls the YouTube/Download tabs expose: "Define Whisper settings…" button + validity indicator, include header, polish for MD, keep time markers in MD, polish level selector. Verify in the source which of these the Download tab actually exposes and replicate exactly; do not invent controls it lacks.
- New config keys: `podcast_transcribe`, `podcast_whisper_defined`, `podcast_whisper_model`, `podcast_whisper_lang`, `podcast_whisper_dictionary`, plus `podcast_include_header`, `podcast_polish`, `podcast_keep_time_markers`, `podcast_polish_level` (use the exact same value shapes as the `download_*` / YouTube equivalents). Add defaults to `DEFAULT_CONFIG`.
- Output formats: `whisper_transcribe_file` (~L9946) takes `keep_formats`; pass the same global output-format selection the Download tab passes (menu `menu_output_formats`), so the MD plus whatever other formats the user keeps are produced.
- Summary note equivalent of `dl_summary_transcribe_note`.
- Start button blocked with the same "Whisper settings not defined" message the Download tab uses.

### 2.2 Worker behavior
- Sequence: `PodcastDownloadWorker` (~L12525) downloads the whole queue first; only after the last download completes it runs a transcription pass over the successfully downloaded, ffmpeg-normalized MP3s (the final tagged file, not the raw download), in queue order. Cancel during the download phase: no transcription pass (episodes stay MP3-only, log says so). Cancel during the transcription phase: finish nothing further, leave already-written MDs, log which episodes were not transcribed.
- Factor the transcription-after-download logic out of `DownloadWorker._transcribe_after` into a module-level helper (or mixin) reused by both workers rather than copy-pasting. Keep the Download tab's behavior byte-identical; add a regression test that the Download path still calls through.
- Output: MD written next to the MP3 in the podcast output folder, same stem. The existing "markdown companion header" is no longer written as a separate file: its metadata (`auto_metadata_for_podcast`, ~L11851, `resolve_podcast_fonte`) is merged into the transcript MD header built by the shared `md_header` config. If transcription is disabled, keep writing the companion header exactly as today.
- Progress/status events: reuse the Download tab's event names or add `pod_transcribe_*` events; Stop/Cancel must abort a running Whisper subprocess cleanly (same stop_flag pattern). Clear/Start/Stop button states as in `_pod_clear_queue_btn` handling (~L18935/18964).

### 2.3 Tests (Phase 2)
Config defaults present; settings validity gate; companion header replaced by full MD when enabled and preserved when disabled; transcription starts only after queue drain (mock Whisper); shared helper used by both workers; translation parity.

## Phase 3 — New "Live Transcription" tab

Placed between "A/V Transcription" (`tab_main`) and "MD Conversion" (`tab_md`) in `notebook.add` order (~L16199). Windows only: on other OSes the tab renders with all controls disabled and an explanatory label (`live_unsupported_os`).

### 3.1 Dependency: pyaudiowpatch (WASAPI loopback)
- Verify current version and API on PyPI/GitHub before use. Install into the shared tools venv (same venv as MarkItDown / yt-dlp / feedparser). Add it to the tools collection with the same three operations every other tool has: detection indicator in the tools/settings dialog, install, upgrade. Follow the feedparser wiring exactly (and the v0.15.x bug: make sure the indicator is wired to the correct settings dialog).
- Capture runs as a separate subprocess (`python -c` or a generated script, consistent with the existing `-c`/`-m` invocation pattern) so a PortAudio crash cannot take down the Tk process. The script:
  - opens the default output device's WASAPI loopback (`get_default_wasapi_loopback`) at the device-native rate/channels; when `--mic` is passed also opens the default microphone as a second independent stream at its own native rate (WASAPI shared mode does not allow forcing a rate, and loopback and mic rates usually differ),
  - writes each stream to its own fixed 60-second WAV chunk (`chunk_000001.loop.wav`, `chunk_000001.mic.wav`) using stdlib `wave` only; write to a `.tmp` name and rename atomically on completion. No numpy/scipy/audioop (audioop is deprecated in 3.12 and removed in 3.13),
  - computes per-chunk RMS with the `array` module; a chunk is marked silent only when every stream of that index is below threshold, in which case the WAVs are deleted and a `chunk_000001.silent` marker is written so timeline offsets stay correct,
  - stops on a `STOP` sentinel file or SIGTERM, flushing the final partial chunk.
- Mixing and resampling happen in the worker, not the capture script: for each index, ffmpeg merges `.loop.wav` + `.mic.wav` (`amix`, normalize off) into one 16 kHz mono `chunk_000001.wav`; without mic, the loopback WAV is used directly (Whisper's own ffmpeg loader resamples). Reuse the app's ffmpeg path resolution.
- Default output device changing mid-session (e.g. plugging headphones) is out of scope: document in the tab intro text that the device in use at Start is captured for the whole session.
- Document in the plan why 60 s: the openai-whisper CLI reloads the model per invocation, so longer chunks amortize load time; this is the "lighter, not live" trade-off the owner chose. Transcription is allowed to fall behind capture (backlog); chunks are cached on disk and the status area shows the backlog count. The Whisper settings dialog for this tab should default to a light model (`base` or `small`) and show a hint that `medium` will build a large backlog on CPU.

### 3.2 UI
- Title entry (`live_title_label`): used as the output filename stem after `sanitize_filename`-style cleaning (reuse the app's existing filename sanitizer); if empty, `live_YYYY-MM-DD_HHMM`.
- Output folder picker (config `live_output_folder`).
- Checkbox "Capture Mic" (config `live_capture_mic`, default off).
- Own Whisper settings: "Define Whisper settings…" + validity indicator, config `live_whisper_defined` (False), `live_whisper_model` (""), `live_whisper_lang` ("pt"), `live_whisper_dictionary` (""); plus include header, polish for MD, keep time markers, polish level (`live_include_header`, `live_polish`, `live_keep_time_markers`, `live_polish_level`) with the same defaults as the Download tab's counterparts. Start is blocked while settings are undefined, pyaudiowpatch is not installed, or the output folder is unset.
- Buttons: Start, Stop, and "Schedule Stop" with a mode selector: clock time (HH:MM; if already past today, next day) or duration since Start (HH:MM:SS). The schedule can be set or changed before and during a session; it is checked on the Tk thread with `after` and simply triggers the same Stop handler. Show an elapsed label and, when scheduled, a countdown. Validate input (reject 00:00:00 duration, malformed times).
- Status area: elapsed time, chunks captured, chunks transcribed, last transcribed line preview.

### 3.3 Worker: `LiveTranscriptionWorker(threading.Thread)`
- Launches the capture subprocess, then loops: poll the temp dir for completed chunks in sequence order, transcribe each with `whisper_transcribe_file` (~L9946) using the live tab's settings, parse segments with `parse_whisper_segment_line` (~L11069), add the chunk offset `(index × 60 s)` to every timestamp, and build `initial_prompt` as: dictionary priming (the same priming the other tabs pass — verify how they build it) followed by the last ~200 characters of the previous chunk's text, truncated to stay under Whisper's ~224-token prompt budget (priming has priority, tail is cut first).
- Partial safety net: after each chunk, append the raw timestamped text to `<stem>.partial.md` in the output folder (fsync). A chunk whose Whisper run fails is logged and skipped (its offset is preserved); it does not abort the session. On Stop, build the final MD: header (shared `md_header` config + live metadata: title, start/end time, duration, mic on/off), time markers according to the same rule the other tabs apply when polishing, Level 1 polish, optional Level 2 Claude API polish; write `<stem>.md`, then delete the partial file. If the app crashes, the partial file survives; on next start, if a `*.partial.md` exists in the live output folder, offer to finalize it (header + polish) — reuse the comparison safety-net dialog pattern.
- Stop sequence (manual or scheduled): write STOP sentinel immediately so recording ends at that moment → wait for capture exit (timeout then terminate) → transcribe the remaining backlog with a visible "finishing N chunks" progress → finalize → post `live_done`. A second press of Stop during the backlog phase ("Stop now") skips the untranscribed chunks, finalizes with what exists, and notes the gap in the MD. A running Whisper subprocess is never killed mid-chunk except on "Stop now" or app close.
- Audio is discarded after transcription (temp dir removed on finalize).
- Errors: no loopback device / pyaudiowpatch missing / Whisper invalid → clear message via existing error dialog helpers, tab returns to idle.
- App close while recording: prompt, then perform the Stop sequence before exiting.

### 3.4 Tests (Phase 3)
Capture script generation (argument handling, chunk naming); offset arithmetic across chunks including silent markers; partial file appended after each chunk and removed on finalize; finalize produces header + markers + polish output (mock Whisper with canned segment output); scheduled stop both modes; OS gate disables tab on non-Windows; tool install/upgrade wiring for pyaudiowpatch; translation parity.

## Cross-cutting impact checklist (verify each, report findings)

- `DEFAULT_CONFIG` additions and config load/migration path for all new keys.
- `TRANSLATIONS` parity test covers all `cmp_*`, `pod_*`, `live_*` additions.
- Notebook tab order and any code that indexes tabs by position.
- Any "is a worker running?" global guard (see the pattern at ~L16980/18826) must include the new live worker and the podcast transcription pass.
- Window geometry / scroll wrap registration (`_register_wrap`, `_on_window_configure`) for the new tab.
- Tools dialog: new tool row, indicator, install, upgrade, version display.
- Settings dialog reuse: inspect `_open_dl_whisper_settings` (~L18136). If it is already a reusable dialog, parameterize it by config prefix (`download_`, `podcast_`, `live_`); if it is tightly coupled to Download-tab state, extract the minimal shared dialog first and keep the Download tab's behavior byte-identical. Do not create a third copy.
- Level 2 polish uses the global Claude API key/model settings; the new tabs must read them the same way the Download tab does and degrade to Level 1 with a logged message when no key is set (verify that is the current behavior).
- Changelog/version string and any "what's new" text.

## Delivery
Final file `TranscriptLab_v_0_16_0.py` in `/mnt/user-data/outputs/`, plus a short summary listing: new config keys, new TRANSLATIONS keys, new/changed functions and classes, and the two clean test-run outputs.
