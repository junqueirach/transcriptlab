# Prompt — TranscriptLab v0.15.0: Podcast Download tab

## Context

TranscriptLab is a single-file Python 3.12/Tkinter Windows desktop app (portable, co-credited "Luiz Junqueira & Claude AI") for batch audio/video transcription and document-to-Markdown conversion, built for feeding a Portuguese-language lecture corpus into LLM training/RAG. Attached: `TranscriptLab_v_0_14_18.py` (current version) and its test suite.

Non-negotiable conventions already in place — follow them exactly:
- Single `.py` file. Edits via `str_replace`, one change at a time, never a large unreviewable diff.
- Compile-check after every edit: `python3 -c "import ast; ast.parse(open('file').read())"` plus an `ast.walk` name-collision scan.
- Portable config and tools live next to the `.py` file, not in the user home.
- Every user-facing string needs a matched PT-BR/EN pair in `TRANSLATIONS`.
- No automatic network call ever fires without an explicit user action (button click).
- `APP_VERSION` bumped with every release — target `0.15.0`.
- Bilingual MD metadata headers use: Título, Autor, Data, Tipo, Fonte, Duração, Qualidade.
- New config keys MUST be added to `DEFAULT_CONFIG` — a past bug silently dropped keys that existed only in the runtime config, not the default. Do not repeat this; every key below must land in both places.
- Workflow: plan → approval → implement → test → deliver. Two consecutive clean full-suite runs required before delivery. Real fixtures, not assumptions — verify empirically.
- No guessing in matching logic: ambiguous cases are skipped with a clear reason, never silently resolved by best-guess.

## Decisions locked in (confirmed by Luiz)

- Feed parsing: **feedparser**, not stdlib ElementTree.
- Tag writing: **try ffmpeg `-metadata` first**; fall back to mutagen only if ffmpeg is verified not to work cleanly for this.
- Downloaded episode format: **normalize everything to MP3**, mirroring the existing yt-dlp Download tab's behavior.
- Tab name: **"Podcast Download"**.
- Output folder: **dedicated, user-browsed setting** (`podcast_output_dir`), not shared with any other tab.
- Subscribe-mode dedup: **new `podcasts_state.json`**, not an extension of `queues_state.json`.
- **No cap on episodes resolved into the queue.** A whole-show resolve lists every episode the feed returns, full stop — no soft/hard truncation. Curation is manual, via the export/import round trip below, not an app-imposed number.
- **Export/import round trip for the queue**: Export Selected + Export All (JSON, mirrors the existing Dictionary tab's export pair), and an Import button to load a hand-edited file back in as the active queue.

## Architecture facts to respect (checked against the actual file, not assumed)

- **Three separate dependency tiers exist. Don't blur them:**
  1. Stdlib-only, runs in the main app process (`urllib.request`, `json`, `re`, `threading`, `tkinter`). The main process cannot assume any third-party pip package is installed.
  2. `TOOLS_VENV_DIR` — an isolated venv holding `markitdown`, `yt-dlp`, `youtube-transcript-api`, `pysrt`, `webvtt-py`. These are never imported into the main process; every call goes through `subprocess.run([tools_venv_python(), ...])`.
  3. Standalone binaries (`ffmpeg`/`ffprobe`) — downloaded/located separately (`FFMPEG_DOWNLOAD_URL`, `FFMPEG_WIN_BUILD_URL`), invoked via direct `subprocess.run([ffmpeg_path, ...])` from the main process. Not a pip package, not in `TOOLS_VENV_DIR`.

- **feedparser has no CLI, unlike markitdown/yt-dlp — invoke it differently.** `markitdown`/`yt-dlp` are called as `[python_exe, "-m", "markitdown", ...]` / `[python_exe, "-m", "yt_dlp", ...]` because both ship a runnable module. `feedparser` is a plain library with no `-m feedparser` entry point. The existing precedent for calling a plain library inside the tools venv is the inline form already used elsewhere: `subprocess.run([venv_python(env_dir), "-c", "import whisper"])`. Use that same inline-`-c` approach (a short Python one-liner/script string that imports feedparser, parses the feed, and prints JSON to stdout) — **do not** ship a separate `.py` helper file alongside the app; that would break the single-file distribution model. A runtime-generated temp script written to `TOOLS_DIR` and deleted after use is an acceptable variant of "inline" if the `-c` string gets unwieldy; a permanently bundled second source file is not.
- **feedparser installation reuses the existing generic pip-install helper** — the function that returns `[python_exe, "-m", "pip", "install", "--upgrade", "--no-cache-dir", package]` — rather than a bespoke install call.
- **Tag reading already exists, via ffprobe, not mutagen.** `auto_metadata_from_embedded_tags(tags)` maps ffprobe's `-show_format` JSON tags onto the 7-field header. There is no mutagen anywhere in the codebase today, and per the locked-in decision above, ffmpeg is the first choice for writing tags too — keeping read and write on the same tool. Starting shape to verify empirically:
  `ffmpeg -i in.<ext> -i cover.jpg -map 0:a -map 1:0 -codec:a libmp3lame -q:a 0 -id3v2_version 3 -metadata title="..." -metadata artist="..." -metadata album="..." -metadata date="..." -metadata comment="..." -c:v copy -metadata:s:v title="Album cover" -metadata:s:v comment="Cover (front)" out.mp3`
  (omit the `-i cover.jpg`/`-map 1:0`/video-stream flags when no artwork URL was found). Confirm this actually produces valid, correctly-tagged output before treating it as final.
- **Duration detection already exists** (ffprobe-based, referenced around the `Duração` header handling) — reuse it rather than trusting RSS `itunes:duration`, which is often missing or wrong. Treat the RSS value as a fallback hint only.
- **`Tipo` is a content-genre classifier, not a source-platform label — this was wrong in an earlier draft of this prompt.** `auto_metadata_for_youtube`/`auto_metadata_for_file` set it via `detect_content_type(haystack)`, which keyword-matches a `CONTENT_TYPES` list against the title/description text (falling back to `HEADER_UNKNOWN`). `auto_metadata_for_podcast` must call this same function against the episode's title + description — **do not** hardcode `"Podcast"` or any other fixed string into `Tipo`.
- **`Fonte` needs a priority order, not a single source — this was incomplete in an earlier draft.** For an ad hoc pasted episode link, Fonte is that link. For episodes that came from a whole-show resolve, no per-episode link was ever pasted — use, in order: (1) the RSS `<item>`'s own `<link>` if the feed provides one, (2) the enclosure URL, (3) the show-level pasted link only as a last resort.
- **`Qualidade` is not a source-file property.** Per an existing code comment, it's the value the user chose (transcription/model quality profile) and is preserved verbatim, not auto-filled from source metadata. `auto_metadata_for_podcast` must leave it untouched, same as every other source today.
- **The "Grabber" tab already implements resolve → list → pick.** `tab_grabber` ("YouTube Link Grabber") expands a playlist/channel via `PlaylistExpandWorker` into individual links, and `LinkGrabWorker` handles the grab. This is the pattern to reuse for "whole show → episode list → user picks some" — not a new UI concept.
- **Per-tab dedicated output folder is the existing pattern, not a shared one.** The Download tab has its own `download_output_dir` config key; YouTube Transcription has its own `youtube_output_dir`. Each is a plain persisted path set via a Browse button in that tab, with a `{tab}_need_output_dir` translation string ("Choose an output folder first.") enforced before the batch can start (see `dl_need_output_dir` / `yt_need_output_dir`). Podcast Download follows the exact same mechanism: `podcast_output_dir`, its own Browse widget, its own `pod_need_output_dir` validation string.
- **Export/import already has an established convention** — the Whisper Dictionary hub's `_whisper_dict_export_selected` / `_whisper_dict_export_all` / `_whisper_dict_import`: `filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON","*.json"), (self.t("all_files"),"*.*")])` writing via `json.dump(..., ensure_ascii=False, indent=2)`, and `filedialog.askopenfilename` on import with a "this doesn't look like a valid export" rejection message (`ws_dict_import_bad_file`) when the expected structure isn't found. The podcast queue export/import must follow this exact mechanism, not invent a new one.
- **Filenames must go through the existing `sanitize_filename(title, fallback="", max_len=150)` helper.** Episode titles will contain characters illegal in Windows filenames — don't write a second sanitizer.
- **Worker → UI communication must use the existing event-queue pattern**, not touch Tkinter widgets from a background thread: `self.event_queue.put({"kind": kind, **kwargs})` (see the `post()` method used by existing workers), consumed on the main thread. `PodcastResolveWorker` and `PodcastDownloadWorker` follow this exactly.
- **Downloads are sequential, one episode at a time** — same as the existing `DownloadWorker` — not parallel. Pacing/backoff constants apply between successive downloads regardless of total queue size.
- **Rate-limit/backoff precedent exists** for exactly this class of problem: `YT_DOWNLOAD_DELAY`, `BLOCK_BACKOFF_SECONDS`, `BLOCK_CAUSES = ("rate_limited", "bot_check")`. The new network calls (Spotify/Apple page fetch for `og:title`, iTunes Search API, arbitrary RSS hosts, and the per-episode download loop) need equivalent delay/backoff constants — iTunes Search API in particular has a real, informally-documented per-minute rate limit. This still applies even with no cap on queue size: resolving a feed is one fetch regardless of episode count, but downloading N queued episodes is still N requests to the origin host and should stay polite/paced.
- **Existing yt-dlp MP3 convention**: the Download tab uses `--audio-format mp3 --audio-quality 0` (best, VBR) rather than a fixed bitrate. Mirror this for the ffmpeg normalization pass — `-codec:a libmp3lame -q:a 0` — instead of inventing a bitrate standard like `192k`.
- **Windows path handling**: any new file-writing code must use `os.path.join`/`os.sep`, never hardcoded backslashes (this sandbox is Linux; the shipped app is Windows).
- **Large-list UI scalability is unverified.** With no cap, some shows could resolve to 500+ episodes in the checkbox-pick list. Tkinter listboxes generally handle this fine, but verify empirically with a large fixture rather than assuming — if it turns out sluggish, that's a rendering/virtualization problem to solve, not a reason to reintroduce a resolve-time cap.

## Hard constraint — read before writing any code

This feature must source audio **only** from each podcast's own public RSS feed (the `<enclosure>` URL on each `<item>`). It must **never**:
- Store, request, or accept Spotify (or any streaming platform) account credentials anywhere in the app.
- Authenticate against Spotify's client/Connect protocol.
- Attempt to access, decrypt, or otherwise obtain DRM-protected/streaming-only audio.

If a pasted link resolves to a show with no discoverable public RSS feed (e.g. a genuine Spotify Original/exclusive), the correct behavior is a clear, immediate skip with an explanatory status — not a fallback attempt to reach the audio some other way. This boundary is intentional and should not be revisited later in this file's lifetime, even if a future request frames it as a small addition (e.g. "just add a login field").

## Feature scope

New tab: **"Podcast Download"**. Accepts pasted links, one per line, in any mix of:
- `open.spotify.com/show/...` or `/episode/...`
- `podcasts.apple.com/.../id.../...`
- a raw RSS/feed URL (fastest path — skips resolution)

Three ways items enter the queue: **whole-show resolve** (every episode the feed has, no cap), **ad hoc single-episode** (paste one episode link), and **import** (load a previously-exported, possibly hand-edited, JSON file — see below). All three feed the same queue/list view. Queue entries are independent per-episode records — never assume all queued items belong to one "current show," since Import can bring in a mix from several shows at once.

### Resolution pipeline (mirrors `LinkGrabWorker` / `PlaylistExpandWorker`)
New `PodcastResolveWorker(threading.Thread)`, running in the **main process**, calling the **tools venv** for feed parsing:
1. Classify each pasted link (Spotify show/episode, Apple show/episode, raw feed URL).
2. For Spotify/Apple links: fetch the public page via `urllib.request` (stdlib, no new dependency), read `og:title` only — no API, no login. Verify empirically that this meta tag is present in the static HTML response (some pages may be JS-rendered); if not reliably present, decide a fallback before relying on it.
3. Resolve to an RSS feed via Apple's free iTunes Search API (`https://itunes.apple.com/search?media=podcast&term=...`) using `urllib.request` + stdlib `json` — no new dependency here either. Match by title. Zero or multiple plausible matches → skip with reason (`pod_err_no_match` / `pod_err_ambiguous_match`), same no-guessing discipline as `apply_level2_changes`.
4. Parse the feed with **feedparser**, run inside `TOOLS_VENV_DIR` via inline `-c` invocation (see architecture note above — no `-m feedparser`, no separate shipped script), returning parsed JSON on stdout. Add `feedparser` to the venv's install/health-check/rebuild flow alongside the existing packages, via the existing pip-install helper.
5. Build the **full** episode list (no truncation) with these fields per item:
   - `guid` — from the RSS `<guid>`; **if absent or empty, fall back to the enclosure URL as the identity key** for dedup/import matching.
   - `title`, `description`
   - `pubDate` — use feedparser's parsed date struct (`published_parsed`), not manual regex on the raw string; format as `YYYY-MM-DD` to match the app's existing date-formatting convention.
   - `enclosure_url`
   - `item_link` — the RSS item's own `<link>` if present (see Fonte priority order above)
   - `season`/`episode_number` if present
   - `artwork_url` — episode-level image if present, **else fall back to the show/channel-level `<itunes:image>`**
   - `itunes:duration` if present (hint only, per the duration note above)
   - the resolved feed URL and the originally pasted link (show- or episode-level)
6. **De-duplicate within the current queue by `guid`** before adding — pasting overlapping links or re-resolving the same show in one sitting must not create duplicate queue entries. This is separate from the cross-session `podcasts_state.json` dedup below.
7. Episode-link mode: match the specific episode within the feed by title/date; no confident match → skip (`pod_err_episode_not_found`).
8. No public feed found at all → skip (`pod_err_no_public_feed`) — this is the expected outcome for exclusives, not an error state to work around.
9. Apply delay/backoff between requests to the same host, mirroring `YT_DOWNLOAD_DELAY`/`BLOCK_BACKOFF_SECONDS` — new constants, e.g. `POD_RESOLVE_DELAY`, sized conservatively against iTunes Search API's rate limit.

### Download pipeline
New `PodcastDownloadWorker(threading.Thread)` (mirrors `DownloadWorker`, simpler — direct HTTP GET of the enclosure URL via `urllib.request`, no yt-dlp involved, there is no stream to select):
- Streamed download to `podcast_output_dir` (the tab's own dedicated, user-browsed folder). `pod_need_output_dir` blocks the batch if unset, mirroring `dl_need_output_dir`.
- Sequential, one episode at a time (see architecture note above).
- Filename via `sanitize_filename(...)`, e.g. `sanitize_filename(f"{show} - {date} - {episode_title}")` — confirm the exact scheme matches `DownloadWorker`'s existing convention closely enough to feel consistent.
- **Normalize to MP3** via ffmpeg (`-codec:a libmp3lame -q:a 0`) in the same pass that writes tags (see the example command above) — verify empirically that one pass handles both transcode and `-metadata`/artwork cleanly. Fall back to mutagen (placed in `TOOLS_VENV_DIR` via the same inline-`-c`/pip-install pattern as feedparser) only if the ffmpeg route doesn't pan out for tags specifically.
- Tags written: title, artist/show, album, track/episode number, date, comment (description), embedded artwork if available (including the show-level fallback from step 5 above).
- Applies the delay/backoff constants from above between successive downloads.
- **Subscribe-mode dedup**: repeat runs against the same show — including episodes re-entering the queue via a re-import — must not re-download episodes already fetched. New `podcasts_state.json`, stored next to the `.py` file like `queues_state.json` (same portable-storage convention), keyed by the same `guid`-or-enclosure-URL identity used everywhere else in this feature.

### Queue export / import
Mirrors the Whisper Dictionary hub's export/import mechanism exactly (`filedialog.asksaveasfilename`/`askopenfilename`, JSON, `ensure_ascii=False, indent=2`):
- **Export Selected**: writes only the checked/selected rows in the current queue view.
- **Export All**: writes every item currently in the queue view.
- Both write a JSON object with a schema marker (e.g. `"_transcriptlab_podcast_queue": true`, plus a `schema_version` int) and an `"episodes"` array. Each episode entry carries every field gathered during resolve (see the list in step 5 above) — the `guid` is what makes re-import and dedup reliable; do not omit it.
- **Import Queue**: `askopenfilename`, validates the schema marker, rejects with a `pod_queue_import_bad_file` message (mirroring `ws_dict_import_bad_file`) if the file doesn't match. **If the current queue already has items, confirm with the user before replacing it** (a simple yes/no messagebox is enough) — importing should never silently discard an in-progress ad hoc queue. On confirmed import, the imported episodes become the active queue. Imported items still pass through the same `podcasts_state.json` dedup check as any other queue entry before download.

### Metadata → transcription header integration
Extend the existing `auto_metadata_for_youtube`-style hook with an `auto_metadata_for_podcast(meta)` counterpart:
- Título ← episode title
- Autor ← show name
- Data ← episode pubDate (already formatted `YYYY-MM-DD` from the resolve step)
- Fonte ← per the priority order above: item link → enclosure URL → pasted show link
- Tipo ← `detect_content_type(title + " " + description)` — **not** a hardcoded value, see the architecture note above
- Duração ← **ffprobe on the downloaded (post-normalization) file** (reuse the existing duration-detection function), RSS `itunes:duration` as fallback hint only if ffprobe fails
- Qualidade ← **not touched by this function** — stays whatever the user's transcription-quality selection sets, same as every other source today

Confirm this wiring works end-to-end (download → normalize → tag → header pre-fill) before considering the feature done, not just that files download.

### UI
Tab registration follows the existing `notebook.add(self.tab_x, text=self.t("tab_x"))` pattern. Contents:
1. Output-folder row (path display + Browse button), same widget pattern as the Download/YouTube tabs' own folder pickers, backed by `podcast_output_dir`.
2. Link paste box (one per line) + log frame, same layout family as YouTube Download, for the ad hoc single-episode path and the raw-RSS-URL path.
3. A resolve → episode-list → checkbox-pick view for the whole-show path, reusing the Grabber tab's existing UI pattern (`PlaylistExpandWorker`'s output feeding a selectable list).
4. Three buttons near the queue view: **Export Selected**, **Export All**, **Import Queue** — same placement/styling convention as the Dictionary hub's equivalent buttons.

### Settings
- New tools-venv entry: `feedparser` — verify Python 3.9–3.12 compatibility and check for conflicts against the existing `markitdown[all]`-pinned `youtube-transcript-api` chain (the same class of pin conflict that caused a real incident before). Verify via an actual install in the isolated venv, not assumption. Add to the venv rebuild flow (`set_tools_venv_rebuild_*`) alongside the existing packages.
- `mutagen` is a contingency dependency only — do not add it unless the ffmpeg tag-writing verification fails.
- No episode-cap setting.
- No credential fields of any kind for this feature.

### Config — exact `DEFAULT_CONFIG` keys (name them explicitly to avoid the silent-drop bug)
- `podcast_output_dir` (str, default `""`) — mirrors `download_output_dir` / `youtube_output_dir` exactly
- `podcast_feedparser_version` (str) — tracked the same way markitdown/yt-dlp versions are tracked today; match the existing key-naming pattern exactly rather than inventing a new one
- No episode-cap key, no format-toggle key

### TRANSLATIONS
PT-BR/EN pairs for: tab label ("Podcast Download" / "Baixar Podcast" or equivalent — confirm exact PT-BR wording with Luiz), intro text, output-folder row, link box label, episode-picker labels, queue statuses, `pod_need_output_dir` ("Choose an output folder first." — mirrors `dl_need_output_dir`), export/import strings (`pod_queue_export_selected`, `pod_queue_export_all`, `pod_queue_import`, `pod_queue_import_done` — "{n} episode(s) imported.", `pod_queue_import_bad_file` — mirrors `ws_dict_import_bad_file`, a replace-confirmation string for a non-empty queue), and every skip reason using the codebase's existing `yt_err_*`-style naming convention (`pod_err_no_match`, `pod_err_ambiguous_match`, `pod_err_episode_not_found`, `pod_err_no_public_feed`, `pod_err_no_connection`). Group in a banner-commented block, same as the "YouTube tab strings" section.

### About dialog
Add `feedparser` to the tools list (and `mutagen` only if the ffmpeg tag-writing fallback ends up needed) — bundle with the already-pending fix for the missing Docling/Pandoc/pysrt/webvtt-py entries.

### Testing
- Extend the test suite (copy forward, bump version references, append new test classes before `if __name__ == "__main__"`).
- **Environment constraint**: this development sandbox's network egress is allow-listed to a fixed domain set that does not include `itunes.apple.com`, `open.spotify.com`, `podcasts.apple.com`, or arbitrary podcast-host RSS URLs. Live end-to-end resolve/download tests against a real feed cannot run inside this sandbox as written — plan for either (a) a bundled static RSS XML fixture for parse-only tests here, with the live network leg verified on Luiz's own machine, or (b) confirm which podcast host domains, if any, could be added to the allowlist.
- Cover: raw feed URL path, Apple link resolution, ambiguous-match skip, no-public-feed skip, full-feed resolve with no truncation on a large fixture (verify UI list responsiveness), in-session guid dedup on overlapping resolves, Export Selected vs Export All correctness, Import round-trip (export → trim → import → queue matches trimmed set), rejection of a non-matching file on import, the replace-confirmation prompt when importing over a non-empty queue, subscribe-mode dedup on a second run and on a re-imported queue (via `podcasts_state.json`), the guid-missing → enclosure-URL fallback, the episode-artwork → show-artwork fallback, MP3-normalization + tag correctness in one ffmpeg pass, Tipo populated via `detect_content_type` (not hardcoded), Fonte following its priority order for both ad hoc and whole-show episodes, header pre-fill correctness (all 7 fields, including confirming Qualidade is left alone), and the `pod_need_output_dir` block when no folder is set.
- Headless instantiation via `xvfb-run -a python3` before formal runs. Two consecutive clean full-suite runs required before delivery.
- Zero regressions to existing tabs/workers/config keys/TRANSLATIONS.

## Deliverable format
Plan first (numbered, blocking questions called out separately) → wait for explicit approval → surgical `str_replace` edits, compile-checked after each → tests → two clean runs → deliver. No large diffs, no unreviewable batches.
