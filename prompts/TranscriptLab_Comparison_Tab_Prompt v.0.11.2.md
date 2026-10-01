# TranscriptLab — Comparison Tab: Implementation Prompt

Paste this into a new session together with the current TranscriptLab `.py` file (v0.11.2). This document is the approved plan — the coding session should proceed phase by phase without re-asking for approval, and should only pause to ask if it hits something genuinely not covered below.

## Context

TranscriptLab is a single-file Python 3.12 / Tkinter Windows desktop app (co-credited "Luiz Junqueira & Claude AI") for batch audio/video transcription and Markdown generation, wrapping Whisper, yt-dlp, FFmpeg, MarkItDown, and youtube-transcript-api. Config and tools live next to the `.py` — never in the user home directory.

This prompt specifies a new "Comparison" tab. Purpose: before running whisper medium (slow) on a batch of files, cheaply check (a) whether each file's content already exists as a Markdown transcript somewhere in a folder the user maintains, and (b) whether two or more files in the same batch are actually the same source under different filenames.

## Working rules (apply throughout)

- Single-file surgical edits: str_replace-style changes against the existing `.py`. Do not rewrite or reformat sections you're not touching.
- Every new UI string needs both `pt` and `en` entries in `TRANSLATIONS`. This feature doesn't touch `HEADER_LABELS` (those stay Portuguese regardless of UI language).
- No new network calls. Whisper tiny reuses the existing model-install path (Settings → Whisper) — don't add new auto-download logic.
- Version bump: `APP_VERSION` "0.11.2" → "0.12.0" (new user-facing feature, so bump the minor number and reset patch to 0).
- Deliver a matching `test_vXXX.py`: headless (xvfb) GUI smoke tests for the new tab + unit tests for every new pure function (scoring, windowing, clustering, normalization), with subprocess/whisper/ffmpeg calls mocked. Zero-bug bar.
- Read-only with respect to the Base Comparison Folder: never write, rename, or delete anything inside it.
- Prefer reusing existing code over duplicating it — see the reuse map below (verified directly against the attached v0.11.2 source, line numbers included for reference).

## Reuse map (verified against the attached v0.11.2 source)

- `build_ffmpeg_clip_command(ffmpeg_path, src_path, dst_path, start_seconds, end_seconds)` (~line 5007) — cuts a clip via ffmpeg stream copy. Use for every sample-point extraction.
- `TranscriptionWorker` (~line 6159) / `whisper_transcribe_file()` (~line 4902) / `build_whisper_command()` (~line 4872) — the existing clip-then-transcribe path. Model and `--initial_prompt` are already parameters. The constructor now also takes `header_lang` and `keep_timestamps` (added since v0.10.5) — not relevant to this feature, but expect `ComparisonWorker`'s constructor to be similarly shaped.
- `MODEL_CATALOG` (~line 915) / `models_for_audio_language(lang_code, only_installed=True, cache_dir=None)` (~line 2832) — tiny is still a catalog entry (75 MB). Reuse the same install gate `_start_batch` uses, redirecting to `_open_whisper_settings(focus="models")` on failure.
- `ffmpeg_probe_duration(ffmpeg_path, media_path)` (~line 2891) — duration in seconds.
- `split_md_metadata_header(text)` (~line 4253) — returns `(header, body)`; use to drop the metadata block before comparing candidate MD content.
- `_plsh_normalize_for_compare(s)` (~line 4512) — lowercases, strips punctuation, and strips a leading `[t=MM:SS]`/`[t=H:MM:SS]` anchor. Use this (not `_norm_text()`) for candidate/excerpt normalization: split candidate MD bodies into paragraphs on blank lines, run each paragraph through this function, rejoin with spaces before the windowed scan (Phase 2a). It only strips a *leading* anchor per call, which is why per-paragraph splitting matters — a whole raw body has one anchor per paragraph, not just one at the very top. `_norm_text()`/`_strip_accents()` (used by `detect_authors`) are still the right tool for the auxiliary filename-based context in Phase 3.
- `_plsh_near_duplicate(norm_a, norm_b, threshold=0.88)` (~line 4561) — already does a length-ratio guard + `difflib.SequenceMatcher.ratio()`, used today to catch near-duplicate paragraphs inside MD polish. Its 0.88 threshold is tuned for same-quality-source-vs-itself and is too strict here — tiny-vs-reference text will legitimately score lower even on a real match. Don't reuse the threshold. Do consider pulling the guard+ratio body out into a small shared helper (e.g. `text_similarity_ratio(a, b) -> float`) that both this function and the new Comparison engine call — optional, but keeps the two in sync. It touches existing tested code, so cover it explicitly in `test_vXXX.py` if you do it.
- `QueueItem` (~line 5099), `LiveQueue` (~line 5188) (`pop_next_pending`, `add`, `remove`, `move`, `all_items`), stable `item_id` iids, `make_scrollable_queue()` (~line 6808), the `event_queue` + `self.after(120, poll)` pattern — reuse for the Comparison queue and its worker exactly as the other six tabs do.
- `detect_authors()` / `detect_content_type()` (~lines 3950/3979) — already run against filenames; surface as unscored context in the report (Phase 3).
- `is_model_downloaded(cli_name, cache_dir=None)` (~line 2812), `ModelDownloadWorker(whisper_exe, model_name, event_queue, stop_flag)` (~line 5319), `human_size(size_mb)`, `_attach_stream(event_queue, log_text, on_finish)` — the existing "force-download a model by transcribing 1s of silence" mechanism, used today by the "Add model..." picker in Whisper Settings (~line 11348). Reuse directly for the Phase 1 model pre-flight check below.
- The "Short" cutoff isn't a named constant — it's the literal `0 < duration_seconds < 600` used for YouTube metadata typing. Match that literal for consistency.
- Not to be confused with `find_existing_transcripts()` (~line 3679) — that checks for a sibling file next to the source by filename stem. This feature compares actual spoken content across files that can be anywhere, under unrelated names.

## Phase 1 — Sampling + light transcription

0. Before processing any file (once per Check click, not once per file): validate the configured light model (Phase 4) is ready.
   - `self.whisper_path` not set → existing flow: `err_no_whisper` message + `_open_whisper_settings()`, abort Check.
   - Else check `is_model_downloaded(model_cli)`. Already downloaded → go straight to step 1.
   - Not downloaded → `messagebox.askyesno`: "Model '{model}' (~{size}) isn't downloaded. Download it now?" (size via `human_size(MODEL_INFO[cli]['size_mb'])`). Decline → abort Check, no batch starts.
   - Accept → run `ModelDownloadWorker(self.whisper_path, model_cli, q, stop)` inline in a small progress dialog with a log `Text` widget, wired up with `_attach_stream()` — same pattern as the existing "Add model..." flow in Whisper Settings (~line 11348). Success → proceed automatically into step 1. Failure → show the worker's error, abort Check.
   - This satisfies the "no network calls without explicit user action" rule — the download only fires after the user clicks Yes.
1. For each queued file, probe duration via `ffmpeg_probe_duration`.
2. Sample points as % of duration: default `[15, 30, 45, 60, 75]`. If duration is under 600s (the existing Short cutoff), use `[25, 50, 75]` instead. Keep these as named constants, not inline magic numbers.
3. Each point gets a window centered on it, clamped to file bounds. Window length is Settings-configurable (Phase 4, `comparison_excerpt_seconds`, default 30s) rather than hardcoded.
4. Silence check before transcribing: `ffmpeg -i clip -af silencedetect=noise=-30dB:d=1 -f null -`, parse stderr the same way `parse_ffmpeg_duration_seconds` parses probe output. If the clip is mostly silence, shift the window forward in ~15s steps (up to 2 tries), then use it anyway. Best-effort only, not full VAD.
5. Cut each window with `build_ffmpeg_clip_command` into `TranscriptLab_Data/temp/comparison/<item_id>/point_<n>.<ext>`.
6. Transcribe each clip with the light model (default tiny — see Phase 4), passing the same `--initial_prompt` as the currently-selected vocabulary dictionary. Text output only.
7. Keep each result in memory as `(item_id, point_index) -> excerpt_text`. No MD file is produced here.
8. Delete each clip's audio right after transcribing it. Clear the whole `temp/comparison/` tree at the start of a Check run and after it finishes.

## Phase 2 — Matching engine

Runs entirely inside the worker thread (not the GUI thread) — windowed comparison against a large Base Comparison Folder can take real time, and doing it on the Tk main thread would freeze the UI. Post one `comparison_results` event with the finished data structures when done; the GUI thread only renders it.

### 2a. Against the Base Comparison Folder

1. Recursively walk the Base Comparison Folder (`os.walk`) for `*.md`. Build this index once per Check click, not once per queue file.
2. Per candidate: read it, `split_md_metadata_header()` to drop the header, split the body into paragraphs on blank lines, normalize each paragraph with `_plsh_normalize_for_compare()`, rejoin with spaces. Store `(path_relative_to_root, normalized_body)`.
3. Per excerpt (normalized the same way — treat the whole excerpt as one paragraph) × per candidate: slide a window across the candidate body sized to the excerpt's word count (±20%), stepping by about half the excerpt length, score each offset with `difflib.SequenceMatcher(None, excerpt, window).ratio()` (or the shared helper from the reuse map, if you built it), keep the best. Windowing matters — scoring the excerpt against the whole candidate body as one blob craters the ratio once the candidate is longer than the excerpt.
   - If this is too slow in practice on a large corpus, add a cheap pre-filter (e.g. shared-word count) before the full windowed pass rather than optimizing the windowing itself first.
4. Per (queue file, candidate): `aggregate_score` = mean of the best score at each sample point; `points_agreeing` = count of points scoring ≥ `point_agree_threshold` (constant, suggest 0.55 to start — well below the polish engine's 0.88, see reuse map).
5. Per queue file, keep the top 3 candidates by `aggregate_score`.
6. Tier from two constants (Settings, Phase 4): `>= likely_threshold` (suggest 0.75) → "Likely already transcribed"; `>= possible_threshold` (suggest 0.55) → "Possible match, review"; else "No match found".

### 2b. Within the queue itself (duplicate-source detection)

Last step of the same Check pass, reusing the excerpts from Phase 1 — no extra whisper calls.

1. Normalize each queue file's excerpts with `_plsh_normalize_for_compare()` (same treatment as 2a). For every unordered pair of queue files (A, B): compare all of A's normalized excerpts against all of B's (all-pairs, not index-aligned — two copies of the same source can have different intros/outros trimmed, so point 2 of A may line up with point 3 of B). Score directly with `difflib.SequenceMatcher(None, excerpt_a, excerpt_b).ratio()` — no windowing needed, both sides are already short and comparable in length.
2. Pair score = best excerpt-pair score found; `points_agreeing` = count of excerpt-pairs ≥ `point_agree_threshold` (same constant as 2a).
3. Duration guard: if A and B's durations differ by more than `duration_tolerance` (Settings, suggest 15%), don't let text overlap alone reach "likely" — require both duration proximity and text agreement. Real lectures can share a recited phrase; that alone shouldn't flag two different files as duplicates.
4. Tier the pair using the same `likely_threshold`/`possible_threshold` as 2a for v1 — don't add a second configurable pair unless testing shows the two need to diverge.
5. Cluster: treat queue files as graph nodes, an edge where a pair reaches "likely." Connected components (plain union-find or BFS) are the duplicate clusters — a cluster can have more than 2 members.
6. Runs regardless of 2a's outcome for those files. A file can have no Base Folder match and still be in a duplicate cluster with another queue file — that combination is exactly the case worth catching.

## Phase 3 — Comparison tab UI

1. New notebook tab ("Comparison" / `tab_comparison` / `_build_comparison_tab`), added the same way the existing six are.
2. Candidate queue: same `QueueItem`/`LiveQueue`/scrollable-Treeview/add-remove-move pattern as the other tabs, accepting `MEDIA_EXTENSIONS`.
3. Base Comparison Folder: `LabelFrame` with Entry + Browse (mirrors the Download tab's fixed-folder field), persisted in `self.cfg`. Scan is recursive.
4. "Check" button starts `ComparisonWorker(threading.Thread)`, same event-queue/poll/per-row-status shape as `TranscriptionWorker`. Cancel sets a `stop_flag`, checked between files/points.
5. Results, two sections:
   - Base Comparison Folder matches: Treeview `[Queue File | Best Candidate (relative path) | Confidence % | Points Agreeing | Tier]`. Likely-tier rows pre-checked. "Remove selected" removes those files from the Comparison queue only (never the Transcribe tab's queue).
   - Duplicate clusters: one block per cluster, member filenames + pairwise scores, radio "keep this one" per cluster, "Remove non-kept files" removes the rest from the Comparison queue only.
6. Selecting a result row shows the sample excerpt next to the matched slice of the candidate (or the other file, for a duplicate-cluster row) side by side.
7. Export button writes both sections to a `.md` report via save dialog — plain formatting, no metadata header (it isn't a transcript).

## Phase 4 — Settings + polish

1. Comparison excerpt length (required setting): config key `comparison_excerpt_seconds`, default **30**, valid range 15–90. This is the per-sample-point window from Phase 1. Show a live-computed read-only line next to the control, e.g. "≈150s (2.5 min) extracted per file at 5 points" (recompute as the value changes; note separately that Short files use 3 points, so proportionally less).
   - Reasoning for the default: 30s of Portuguese speech is roughly 75-90 words — enough for the windowed difflib score to be meaningful without being dominated by a couple of ASR errors, short enough to stay well clear of the budget. At 5 points that's 150s (2.5 min) of *extracted audio* per file, comfortably under the 3-5 minute ceiling with room to spare, leaning to the fast side as requested.
   - This treats "3-5 minutes" as a cap on extracted audio, not wall-clock wait time — actual wall-clock will be well below 150s, since whisper tiny transcribes much faster than real-time. If wall-clock time was actually the thing to bound, a larger default would still fit, and the real lever on wall-clock is more likely the fixed per-invocation model-load overhead of calling whisper 5 separate times per file than the audio length itself. If that overhead turns out to matter in testing, concatenating the 5 clips into one file and doing a single whisper pass per queue file — splitting the result back into per-point excerpts using the segment timestamps from `_WHISPER_SEGMENT_LINE_RE`/`parse_whisper_segment_line` — would cut it roughly 5x. Worth keeping in mind, not a v1 requirement.
2. Other settings (sample-point percentages, `likely_threshold`/`possible_threshold`, `duration_tolerance`): existing config JSON, existing dialog style, or inline in the tab — your call. Fine to leave as code constants for v1 if you judge the extra dialog isn't worth it yet — flag that choice either way.
3. Light-model choice defaults to tiny; if exposing base/small too as alternatives, store the choice as `model_cli` — Phase 1 step 0 (not a hard gate-and-redirect) handles making sure whichever one is chosen is actually installed, offering to download it inline if not.
4. Full `pt`/`en` strings for every new label, button, column header, and message.
5. `test_vXXX.py`: unit tests for windowing/scoring/clustering/normalization (pure, no mocks needed) + mocked-subprocess tests for extraction/transcription + one headless xvfb smoke test for the new tab. List which calls are mocked vs. which pure functions are tested directly.

## Assumptions in this prompt — flag anything you'd rather change

- Duplicate-cluster comparison is all-pairs across sample points, not index-aligned.
- Duration proximity is a soft gate (needs both duration and text agreement), not a hard pre-filter.
- Base-Folder and intra-queue tiers share one threshold pair for v1.
- "Remove selected" / "Remove non-kept" only ever touch the Comparison tab's own queue.
- Base Comparison Folder scan is recursive.
- "3-5 minutes per file" is read as total extracted audio (sum across sample points), not wall-clock processing time — flag if wall-clock was actually meant.
- Default excerpt length is 30s/point; the shared near-duplicate-ratio helper refactor (reuse map) is optional, not required for v1.
- Declining the inline model-download prompt aborts the whole Check run — no partial batch with a missing model.

## Deliverables

- Updated `.py` (str_replace edits only).
- `test_vXXX.py`.
- `APP_VERSION` "0.11.2" → "0.12.0".
- Short changelog note, including any function-name substitutions made if the live file has moved on further since this prompt was written.
