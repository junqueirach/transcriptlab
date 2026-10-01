# TranscriptLab v0.8.0 — Implementation Brief

Paste this as the opening message of the next session. It tells you (Claude) exactly what to build, the constraints, the decisions already made, and the questions to confirm before writing code.

---

## Working agreement (follow strictly)

1. Read the current `TranscriptLab.py` (v0.7.0) first — it's the single-file app to extend. Do not rewrite from scratch; add to it and keep it a single, copy-paste-ready file.
2. Process: understand → ask the open questions below → present a short written plan → wait for my explicit "Approved" → only then write code.
3. Zero-bug standard: self-test everything headlessly under `xvfb` (the app is Tkinter). Re-run the existing v0.7.0 tests as regression. Iterate until there are no bugs, then deliver the file via the file viewer.
4. Bump `APP_VERSION` to `"0.8.0"` and confirm the About dialog shows it. Do not break any existing 0.7.0 feature.
5. Everything user-facing must be fully translated in BOTH the Portuguese and English UIs (add keys to the `TRANSLATIONS["pt"].update({...})` and `TRANSLATIONS["en"].update({...})` blocks).

## Goals of this revision

- Feature A — **Playlist expansion** (yt-dlp): pasting a YouTube playlist link fills the queue with every video, which then run through the existing transcript→Markdown pipeline.
- Feature B — **Media download** (yt-dlp): download the actual YouTube video (with a resolution choice) or audio-only.
- Feature C — **Queue & progress UX revisions** that apply to the logic of ALL tabs (Transcription, MD File Generation, and the YouTube Transcription tab).
- Feature D — **About dialog**: make the contact email a clickable mailto link.
- Feature E — **YouTube MD metadata header**: every Markdown produced by the YouTube Transcription tab begins with the video's name, duration, date, and link, then the transcription.
- Feature F — **Queue layout & scrolling (all tabs)**: every queue is scrollable and is the prominent panel; the real-time activity/log panel is secondary in size.
- Feature G — **YouTube rate-limit protection & smart error messages**: batch caps, automatic throttling, and clear per-cause failure messages so the user understands why a video failed and can adapt.

## What already exists in v0.7.0 (reuse these patterns; don't reinvent)

- A "YouTube Transcription" tab that accepts pasted single-video links, validates them (`youtube_video_id()` parses `watch?v=`, `youtu.be/`, `shorts/`, `embed/`, `live/`), queues them, and downloads transcripts via `youtube-transcript-api` into clean-prose `.md` (+ optional `.srt`/`.txt`). MD is always produced; SRT/TXT are optional checkboxes.
- Dependency handling pattern: `find_python_executable()`, `markitdown_is_available()` (a fast `importlib.util.find_spec` probe via subprocess), `CommandStreamWorker` (streams an install command's output to a dialog log), and Settings dialogs (`_open_markitdown_settings`, `_open_ffmpeg_settings`, `_open_whisper_settings`) each with a status line + Install/Re-check buttons.
- Clickable dependency indicators (✓ green / ✗ red) at the top of tabs that open the relevant Settings dialog. The YouTube tab greys out entirely when MarkItDown is missing.
- ffmpeg detection/auto-install already exists (`find_ffmpeg`, the FFmpeg settings dialog with winget/auto-download/extract), and `ffmpeg_probe_duration()` returns a media file's duration in seconds.
- Worker pattern: a `threading.Thread` posts events to a `queue.Queue`; the App polls it with `self.after(...)`; per-row status in a Treeview; batch continues on per-item failure; cancel via a `threading.Event` and (for subprocess workers) terminating the process.
- Existing progress/status code: the per-file determinate progress bar, the `batch_progress` label, and the live `position / elapsed / ETA` status string built in `_handle_event` (and the MD equivalent). `fmt_hms()` formats `H:MM:SS`.
- `ScrollableFrame`, the per-language `_build_ui()` rebuild that preserves queues, config load/save with safe defaults + migration, and a `subtitle_to_prose()` cleaner.

## New dependency: yt-dlp (verified facts)

- Install (same one-click style as the others): `python -m pip install --upgrade yt-dlp` using `find_python_executable()`.
- Detect with a fast probe: `find_spec('yt_dlp')` via subprocess (mirror `markitdown_is_available`).
- Verified working flags (yt-dlp >= 2026.06.09): `--flat-playlist`, `--print`, `-J/--dump-single-json`, `-f/--format`, `-x/--extract-audio`, `--audio-format`, `--audio-quality`, `--merge-output-format`, `--no-playlist`, `--yes-playlist`, `-o/--output`, `--newline`, `--progress-template`, `-S/--format-sort`, `--restrict-filenames`.
- Add a Settings → yt-dlp dialog (status + Install + Re-check), mirroring the MarkItDown dialog. Add a yt-dlp ✓/✗ indicator to the YouTube tab(s), clickable → that dialog.
- yt-dlp is current; install/refresh the latest at build time rather than pinning, and verify flags then.

## Feature A — Playlist expansion (detailed)

- Playlist vs single-video rule (confirmed): a PURE playlist link (`youtube.com/playlist?list=…`, no `v=`) expands into all its videos. A `watch?v=…&list=…&index=…` link adds ONLY that single video and ignores `list=` (no prompt). Logic: if `youtube_video_id(url)` returns an id, queue that one video; else if the URL is a pure `playlist?list=…`, expand it. Add a `youtube_playlist_id(url)` helper that returns the list id only for pure playlist URLs.
- Enumerate without downloading using flat extraction. Either CLI (`yt-dlp --flat-playlist -J <url>` and parse JSON `entries[].id/title/duration`) or the Python API (`YoutubeDL({'extract_flat': True, 'quiet': True, 'skip_download': True}).extract_info(url, download=False)`). Run it in a worker thread (network call); show a "fetching playlist…" note; then append one queue row per video (store `video_id` + `title` + `duration` when present).
- Reject endless auto-playlists ("Mix"/radio): list IDs starting with `RD` (and `RDMM`, `RDCLAK`, etc.). Add `is_mix_playlist(list_id)`.
- Large-playlist guard: confirm before adding more than a threshold (see open question).
- If yt-dlp is missing and a playlist link is pasted → clear message pointing to Settings → yt-dlp. Single-video transcript links must keep working with NO yt-dlp installed.
- Errors (private/unavailable/empty playlist, network/throttle) surfaced clearly, same per-row philosophy.
- After expansion, each video flows through the existing transcript→MD pipeline unchanged.

## Feature B — Media download (detailed)

- Controls:
  - Resolution dropdown: Best, 2160p (4K), 1440p, 1080p, 720p, 480p, 360p, with graceful fallback to the nearest available.
  - Audio-only toggle: when on, the resolution control disables and the app downloads audio and extracts it to a chosen audio format. When off, it downloads video+audio.
  - Container choice: mp4 or mkv, user-selectable in the tab (default mp4); used for `--merge-output-format`.
  - Output folder selector (required), Start/Cancel, per-item progress, activity log.
  - Accepts single videos and playlists (reuse the same paste box + validation + expansion).
- Format selectors (verified syntax):
  - Best video+audio: `-f "bestvideo+bestaudio/best" --merge-output-format <container>`.
  - Capped at height H: `-f "bestvideo[height<=H]+bestaudio/best[height<=H]/best" --merge-output-format <container>`.
  - Audio-only: `-f bestaudio -x --audio-format <mp3|m4a|opus|best> --audio-quality 0`.
  - Output template e.g. `-o "%(title)s [%(id)s].%(ext)s"` (consider `--restrict-filenames`).
- ffmpeg gating: merging separate video+audio streams and audio extraction REQUIRE ffmpeg (already detectable/installable). Show the ffmpeg indicator on this surface; decide behavior when ffmpeg is absent (open question).
- Progress + cancel: prefer the CLI via a subprocess worker (consistent with `CommandStreamWorker`; clean cancel by terminating the process) using `--newline --progress-template` to parse a per-file percentage. Map to the shared progress UI (Feature C).
- Error mapping: translate yt-dlp `DownloadError`/`ExtractorError` text (unavailable/private, age/geo restriction, requested format not available, network/throttle) into friendly localized per-row messages, like `map_youtube_error` does for transcripts.
- General-purpose tool integration for the user's personal study workflow; leave usage responsibility (site terms/copyright) to the user without heavy in-app disclaimers.

## Feature C — Queue & progress UX revisions (apply to ALL tabs)

These fix/extend the shared queue + progress logic. Implement once and reuse across Transcription, MD File Generation, and YouTube Transcription. Where a concept doesn't map to a tab, use the adaptation rules below.

1. Fix the current-item counter off-by-one. The "Processing X/Y" label currently shows the count of FINISHED items, so while the 4th video runs it reads "Processing 3/4". Make X the 1-based index of the item CURRENTLY being processed, so it reads "Processing 4/4". Apply to every tab's batch label.

2. Show the percentage on the progress bar. The determinate green bar shows no number — add the integer percent as visible text (a label centered over the bar, or appended to the status line, e.g. "57%"). The bar + percentage represent OVERALL batch progress:
   - Transcription & YouTube: by audio time when durations are known = transcribed_seconds ÷ total_seconds; fall back to items-done ÷ total when durations are unknown.
   - MD File Generation: by items processed ÷ total.

3. Per-row "Length" column + dynamic queue summary.
   - Add a "Length" column to the queue table showing each item's duration as `H:MM:SS` (Transcription = media duration via `ffmpeg_probe_duration`; YouTube = video duration from yt-dlp metadata). Probe ASYNCHRONOUSLY on add so the UI never blocks: insert the row immediately showing "…", fill the length when the probe returns, then refresh the summary. If unknown (ffmpeg/metadata missing or failure) show "—".
   - Add a dynamic summary line beneath the queue, recomputed on every add/remove/clear and whenever an async length resolves:
     `Total Videos: {n}   Total Length: {Xh Ym Zs}   Estimated Time to Transcribe: {Xh Ym Zs}`
   - Long-duration format helper `fmt_long_duration(seconds)` → "3h 34m 12s" (drop higher units when zero: "34m 12s", "12s").
   - "Estimated Time to Transcribe" = total known length × an empirical speed factor (see below). If no durations are known (e.g. ffmpeg missing), show "—" with a short hint.

4. Relabel the live status fields (Transcription-tab wording; adapt others). Keep the existing ordering/separators; just rename and make the values batch-level:
   - `position M:SS`  →  `Current Video Position: M:SS`
   - `elapsed H:MM:SS`  →  `Total Transcribed: H:MM:SS`  (recommended meaning: cumulative audio transcribed = sum of completed durations + current-file position; confirm — see open question)
   - `ETA H:MM:SS`  →  `Estimated Time to Complete: H:MM:SS`  (live remaining time for the WHOLE batch, not just the current file)

Speed-factor note (drives the ETAs): maintain a learned realtime factor = wall processing time ÷ audio duration, updated by EMA after each completed file and persisted per model in config (e.g. `speed_factor_by_model`). Initialize from a conservative default until the first measurement; on the user's fixed hardware the estimate self-corrects after one run. Label ETAs as approximate. For tabs without audio duration, use the analogous learned average (MD = per-file or per-MB average; YouTube transcript = near-constant per video + the politeness delay).

Per-tab adaptation:
- Transcription: full behavior above (media durations via ffmpeg).
- YouTube Transcription: Length = video duration from yt-dlp metadata (open question on when/how to fetch); "Current Video Position" isn't meaningful for a transcript fetch — show "Processing N/N" + per-video status; ETA basis = per-video average + delay.
- MD File Generation: documents have no time-length — adapt the column to file size and the summary to `Total Files / Total Size / Estimated Time to Convert` (open question to confirm); progress by item count.

## Feature D — About dialog: clickable email

- Render the contact email (`APP_CONTACT`) as a link (blue, underlined, hand cursor). On click, open the default mail client with the address pre-filled in the To: field via `webbrowser.open("mailto:" + APP_CONTACT)`.

## Feature E — YouTube MD metadata header (YouTube Transcription tab only)

Every `.md` produced by the YouTube Transcription tab must BEGIN with a metadata block, then the transcription. This replaces the current `# {video_id}` header. Required fields, in this order:

- Video Name — the exact YouTube title, verbatim, NEVER translated or altered.
- Video Duration — the video length as `H:MM:SS`.
- Date — the video's date (yt-dlp `upload_date`, `YYYYMMDD` → formatted).
- Link — the video URL.

Then a blank line, then the existing clean-prose transcript.

The header is ALWAYS inserted, even if some fields are unknown — the app fills them best-effort:
- Title / Duration / Date come from a yt-dlp full metadata extract per video (`extract_info(url, download=False)` or `yt-dlp -J <url>`), reused for the Length column in Feature C. Note: flat-playlist data usually lacks `upload_date`, so a full per-video extract is needed for Date.
- Link is always constructible from the id: `https://www.youtube.com/watch?v=<id>` (no dependency).
- If yt-dlp is unavailable or a field is missing: Duration falls back to the transcript's last snippet end time (approximate); Title may fall back to a YouTube oEmbed lookup (`https://www.youtube.com/oembed?...` returns the title) or, failing that, the video id; Date falls back to a localized "Unknown"/"Desconhecido". Do not omit a line — show the placeholder.

Formatting / labels:
- Recommended block (confirm exact layout in the open questions):
  - `Video Name: {title}`
  - `Video Duration: {H:MM:SS}`
  - `Date: {YYYY-MM-DD}`
  - `Link: {url}`
- Field LABELS follow the UI language (PT/EN); VALUES (especially the title) are verbatim and never translated.
- Apply ONLY to the YouTube tab's MD. The Whisper Transcription tab and the MD File Generation tab keep their current MD headers.

## Feature F — Queue layout & scrolling (applies to ALL tabs)

Applies to the Transcription, MD File Generation, and YouTube Transcription tabs.

- Make every queue Treeview vertically scrollable. Today the queue Treeviews have a fixed `height` and NO attached scrollbar, so once items exceed the visible rows the rest cannot be reached. Wire a visible vertical `ttk.Scrollbar` to each queue's `yview` (set `yscrollcommand`) so the full list can be scrolled.
- Rebalance vertical space so the QUEUE is the prominent panel and the real-time activity/log panel is SECONDARY (smaller). In the MD File Generation tab the current weighting is inverted — the MarkItDown Activity log expands while the queue is pinned to ~6 rows (see screenshot). Flip it: give the queue the expanding weight (or a larger minimum, ~10–12 rows) and cap the activity log to a smaller fixed height (~6–8 rows). The conversion is fast, so a smaller log is fine and won't read as a frozen app. Apply the same queue-prominent / log-secondary balance to the YouTube Transcription tab, and keep the Transcription tab's queue comfortably tall and scrollable too.
- Keep sensible minimum heights so neither panel collapses on a small window; the queue must still scroll when items exceed the visible area.
- Transcription tab caution: its content sits inside the existing `ScrollableFrame`, so a scrollable inner queue creates nested scrolling. Ensure the mouse wheel over the queue scrolls the QUEUE (bind the wheel to the tree while the pointer is inside it) and that the visible queue scrollbar always works regardless of wheel routing; verify the outer page scroll and the inner queue scroll don't fight (see open question).

## Feature G — YouTube rate-limit protection & smart error messages

Applies to the YouTube Transcription tab and the new YouTube Download tab.

Batch caps (confirmed):
- Transcription: soft-confirm when a batch exceeds 50 videos (a dialog: "Large batches may trigger YouTube rate-limiting — continue?"); hard max 150 (block Start above this and ask the user to split into smaller batches).
- Download: soft-confirm above 20; hard max 50.
- Enforce at Start; show the current count near the queue.

Automatic throttling protections (build all):
- Process sequentially (never concurrent).
- Insert a randomized human-like delay between items: transcription ~1.5–3s, download ~3–8s (delays cancellable).
- On a rate-limit / IP-block signal (HTTP 429 / RequestBlocked / IpBlocked / "Too Many Requests" / bot-check), do ONE backed-off retry (wait, then retry the same item). If it still fails, STOP the rest of the batch (don't keep hammering), leave the remaining items unprocessed, and show a prominent message explaining the IP is temporarily limited with suggested strategies (wait ~24–48h, reduce the batch, increase the delay, try later).
- Keep yt-dlp current (install/refresh latest at build; if a bot-check error appears, hint the user to update yt-dlp).

Smart, specific error messages (the user must understand WHY a video failed, to choose a strategy). Map each distinct cause to a clear localized (PT/EN) message + a suggested action. Per-video failures mark that row failed and CONTINUE the batch; rate-limit/IP-block is the BATCH-LEVEL stop above. Cover at least:
- No captions / transcript disabled → "No subtitles/transcript available." (Note: if this fires for many videos at once it may actually be an IP block — hint that possibility.)
- Members-only ("join this channel" / "members-only") → "Members-only video — requires channel membership; can't be accessed."
- Private video → "Private video."
- Unavailable / removed / invalid id → "Video unavailable, private, or removed."
- Age-restricted ("confirm your age") → "Age-restricted; can't be retrieved without sign-in."
- Region/geo-locked ("not available in your country") → "Not available in your region."
- Rate-limited / IP blocked (429 / RequestBlocked / IpBlocked) → "YouTube temporarily blocked your IP (too many requests). Wait ~24–48h, reduce the batch, or increase the delay." (triggers the batch stop.)
- Bot-check / PoToken ("sign in to confirm you're not a bot") → "YouTube's bot-check is blocking this. Update yt-dlp or try later."
- Requested format/resolution unavailable (download) → "The chosen resolution isn't available for this video — try Best or a lower resolution."
- Upcoming/live not started → "This is a live/upcoming video with no downloadable content yet."
- No connection → "No connection to YouTube."
- Fallback → surface yt-dlp's own message so the cause stays visible.

Implementation: a shared `classify_youtube_error(exc_or_text)` returning a stable cause code → localized message + suggested action, used by BOTH the transcript worker (maps youtube-transcript-api exception classes) and the download worker (parses yt-dlp `DownloadError`/`ExtractorError` text). Surface the short message in the per-row Status and the full message + suggested action in the activity log. Keep a single cause→message/action table in the PT/EN translations.

## Architecture guidance

- New pure helpers (unit-testable offline): `find_ytdlp` / `ytdlp_is_available`, `youtube_playlist_id`, `is_mix_playlist`, `build_ytdlp_flat_list_command`, `build_ytdlp_download_command(...)`, a yt-dlp progress-line parser, `fmt_long_duration`, queue-summary aggregation, the speed-factor EMA update, the corrected "current item" / percentage computations, `youtube_metadata(video_id)` (yt-dlp extract with oEmbed/transcript fallbacks), and `build_youtube_md_header(meta, lang)` (localized labels, verbatim values).
- New workers: `PlaylistExpandWorker` (thread, flat extraction → posts entries), `DownloadWorker` (subprocess streaming yt-dlp → posts progress/status, cancelable), and a small async duration-probe path for the Length column. Reuse the event-queue + `self.after` poll pattern and per-row Treeview statuses. Both YouTube workers share the rate-limit protections and the `classify_youtube_error(exc_or_text)` classifier (Feature G): the transcript worker maps youtube-transcript-api exception classes; the download worker parses yt-dlp `DownloadError`/`ExtractorError` text. Add `classify_ytdlp_error(text)` as the text-parsing half.
- New Settings → yt-dlp dialog; extend the dependency-indicator row(s).
- Factor the queue-summary + progress logic so all three tabs share it (avoid three copies).
- Add a shared `make_scrollable_queue(parent, columns)` helper returning a Treeview + wired vertical Scrollbar (and mouse-wheel routing), used by all three tabs so the scroll/layout fix isn't duplicated or missed.
- New config keys with safe defaults + migration: download resolution, audio_only, audio_format, download_output_dir, playlist-behavior default, and `speed_factor_by_model`. Don't break existing config loading.
- Add all new strings to both PT and EN translation update blocks.

## Decisions already locked (do not re-ask)

- Use yt-dlp (installed the same one-click way as Whisper/MarkItDown).
- Pasting a playlist link expands it into the queue.
- Download supports a resolution choice and an audio-only option.
- Fix "Processing X/Y" to show the current item (so 4 of 4 reads "4/4").
- Show a percentage on the progress bar.
- Add per-row Length + a dynamic bottom-of-queue summary (Total Videos / Total Length / Estimated Time to Transcribe) that updates on add/remove.
- Relabel the live status fields to: "Current Video Position", "Total Transcribed", "Estimated Time to Complete".
- Make the About email a clickable mailto link.
- YouTube MD files begin with Video Name / Video Duration / Date / Link (title verbatim, no translation), then the transcription; the header is always inserted with best-effort fallbacks when a source is missing.
- All queues (Transcription, MD File Generation, YouTube Transcription) are scrollable and are the prominent panel; the activity/log panels are smaller/secondary. The MD tab's current queue-vs-log balance is inverted and must be flipped.

## Confirmed decisions (resolved with the user during review)

These supersede the matching recommendations in "Open questions" below. Only the rate-limit caps (item 3) remain to be finalized in a follow-up.

- Download lives in a SEPARATE "YouTube Download" / "Download do YouTube" tab.
- Playlist vs single video: a pure `playlist?list=…` link expands all videos; a `watch?v=…&list=…` link adds only that one video, no prompt (Feature A).
- Audio-only format: a dropdown (mp3 / m4a / opus / best), default mp3.
- Video container: user-selectable mp4 or mkv in the Download tab, default mp4 (Feature B).
- ffmpeg missing during download: nudge to install, with a degraded progressive-only fallback if declined.
- Resolution tiers: Best / 2160 / 1440 / 1080 / 720 / 480 / 360, default Best.
- The Download tab also accepts and expands playlists (shared logic).
- "Total Transcribed" = cumulative audio transcribed.
- Progress %/bar: by audio-time where known, item-count as fallback.
- MD File Generation summary switches to Total Files / Total Size / Estimated Time to Convert, with a per-row size column.
- YouTube tab: fetch each video's duration at add time; ETA = per-video average + delay.
- ETAs are approximate and self-calibrate after the first run (conservative default factor until measured).
- YouTube MD header: localized labels (PT/EN), values verbatim; date `YYYY-MM-DD`; plain labeled lines; an extra per-video yt-dlp metadata call is acceptable, and an oEmbed title fallback is acceptable when yt-dlp is absent.
- Queue vs activity sizing: queue expands (~10–12 rows), activity log ~6–8 rows fixed.
- Transcription tab: keep the outer page scroll AND a scrollable queue, routing the mouse wheel by pointer location.

- Item 3 (rate-limit caps + protections) — FINALIZED:
  - Transcription batch: soft-confirm above 50 videos; hard max 150.
  - Download batch: soft-confirm above 20 videos; hard max 50.
  - Build the automatic protections (sequential processing; randomized human-like delays — transcription ~1.5–3s, download ~3–8s; one back-off retry on a 429/block, then auto-stop the batch and warn; keep yt-dlp current) and the smart per-cause error messages — all specified in Feature G.

## Open questions to confirm with me before coding

NOTE: all items below (1–18) are RESOLVED — see "Confirmed decisions" above, the updated Feature sections, and Feature G for the rate-limit caps + smart error messages. Nothing here remains open; the list is kept for reference/traceability.

1. Download UI placement: a separate "YouTube Download" / "Download do YouTube" tab, or a mode toggle inside the existing YouTube tab? (Recommendation: separate tab — outputs are media files, not MD.)
2. `watch?v=…&list=…` links: pop a small prompt asking "just this video" vs "the whole playlist", or a per-tab default toggle? (Recommendation: ask once per add action.)
3. Large-playlist cap: what count triggers a confirmation (e.g. 50? 100?), and a hard max?
4. Audio-only format: default and options — mp3 only, or a dropdown (mp3 / m4a / opus / best)? (Recommendation: dropdown defaulting to mp3.)
5. Video container when merging: mp4 or mkv? (Recommendation: mp4.)
6. ffmpeg missing during download: restrict to single-file progressive formats (lower max resolution, no audio extraction) with a clear note, or require ffmpeg and nudge to install? (Recommendation: nudge to install; allow a degraded progressive-only mode if declined.)
7. Resolution tiers to expose — confirm Best/2160/1440/1080/720/480/360.
8. Should the Download surface also accept and expand playlists like the transcript tab? (Recommendation: yes, shared logic.)
9. "Total Transcribed" meaning: cumulative AUDIO transcribed (recommended) vs wall-clock elapsed?
10. Overall progress %/bar basis per tab: by audio-time where known vs by item count — confirm the fallback behavior is acceptable.
11. MD File Generation tab: confirm the summary switches to Files / Size / Convert (documents have no duration), and whether a per-row size column is wanted.
12. YouTube tab: fetch each video's duration at add time for the Length column (extra metadata calls / throttling risk) vs leave Length blank until run? And confirm ETA basis = per-video average.
13. Speed factor: OK to ship "approximate, self-calibrating after the first run" ETAs with a conservative default factor until measured?
14. YouTube MD header: localized labels (PT/EN) with verbatim values (recommended) vs fixed English labels?
15. YouTube MD header: date format (`YYYY-MM-DD` recommended) and exact layout — plain labeled lines (recommended), a markdown bullet list, or YAML front-matter?
16. YouTube MD header: is an extra yt-dlp full-metadata call per video acceptable (network/throttle) to get Date/Title, or should Date be allowed to be "Unknown" when only cheap flat data exists? And when yt-dlp is absent, is an oEmbed call for the title acceptable, or just use the video id?
17. Queue vs activity sizing: confirm the default visible heights (recommendation: queue expands / ~10–12 rows, activity log ~6–8 rows fixed) per tab.
18. Transcription tab nested scroll: keep the outer `ScrollableFrame` (page scroll) AND a scrollable queue with wheel routed by pointer location (recommended), or drop the outer page scroll and let the queue own its scrollbar?

## Testing requirements

- Pure-logic unit tests (offline): playlist/video URL parsing, `is_mix_playlist`, all yt-dlp command builders, the download progress-line parser, error mapping against real yt-dlp exception types, `fmt_long_duration`, the queue-summary aggregation (totals update on add/remove), the corrected "Processing N/N" counter (running index, not done count), the percentage computation (audio-time and item-count modes), and the speed-factor EMA update + persistence. Also unit-test the Feature G classifier (`classify_youtube_error` / `classify_ytdlp_error`) for EVERY cause — real youtube-transcript-api exception types AND representative yt-dlp error strings (members-only, private, age, geo, 429/"Too Many Requests", "confirm you're not a bot", "Requested format is not available", live/upcoming, network) → correct cause code + localized message in PT and EN — plus the cap soft-confirm/hard-max enforcement and the per-video-continue vs batch-stop-on-block logic (mock a 429 mid-batch → one retry then stop, remaining items left unprocessed with the block message; delays tiny in tests).
- Worker plumbing without live YouTube (sandbox can't reach youtube.com): mock the extractor / yt-dlp; test command construction and the streaming/cancel plumbing with a harmless stand-in command; mock flat-playlist JSON; mock the async duration probe. Unit-test `build_youtube_md_header` for full metadata, each missing field → correct localized fallback, title kept verbatim (including non-ASCII/emoji), duration formatting, and that the header always precedes the prose (mock `youtube_metadata`).
- Headless xvfb GUI tests: yt-dlp Settings dialog opens/installs (mocked), indicator state + greying, control enable/disable logic (audio-only disables resolution; ffmpeg-missing behavior), queue add/validate including playlist-link recognition with extraction mocked, the new Length column + dynamic summary updating on add/remove/clear, the relabeled status strings present in PT and EN, the corrected counter and on-bar percentage, the About email firing `webbrowser.open("mailto:…")` (stub `webbrowser.open` and assert the URL), and the queue layout/scroll changes (each queue Treeview has a Scrollbar wired to its `yview`; adding more rows than visible keeps all items in the model and scrollable; the MD tab gives the queue the expanding weight while the activity log is capped).
- Regression: re-run the full v0.7.0 suite (transcription→MD, clip pipeline, MD tab, YouTube transcript worker, all GUI smoke tests) and confirm the queue/progress changes didn't break them.
- State clearly in the delivery what could NOT be tested live (real playlist enumeration and real downloads need network to YouTube) and how it was mocked.
- Mandatory: testing at the end is required. Keep testing, fixing, and re-testing iteratively until the app is fully bug-free. Do NOT deliver while any test fails or any known bug remains.

## Deliverable

A single updated `TranscriptLab.py` at v0.8.0, shared via the file viewer, plus a short changelog and the standing reminder to bump `APP_VERSION` on the next change.
