# Implementation prompt — TranscriptLab v0.14.1

Paste this whole document as your first message, together with the current `TranscriptLab_v_0_13_15.py` and `test_v01315.py` files attached.

---

## What TranscriptLab is

TranscriptLab is a portable, single-file Python 3.12/Tkinter Windows desktop app for batch audio/video transcription (via OpenAI Whisper), document-to-Markdown conversion (via MarkItDown/Docling/Pandoc), YouTube downloading/transcript fetching, and duplicate/comparison detection. The primary use case is building a Markdown corpus of Brazilian Portuguese lectures (Jan Val Ellam / "Revelação Cósmica" content) for LLM training, RAG, and fine-tuning. Co-credited "Luiz Junqueira & Claude AI."

**Hard constraints — do not violate these:**
- Single `.py` file. Use surgical `str_replace`-style edits — never rewrite whole sections unnecessarily.
- Portable design: all config/data files live next to the `.py` file, under a `CONFIG_DIR` constant (already defined in the file) — never under `$HOME`. This app must be movable to a different drive/folder and keep working.
- Every user-facing string exists in **both** Portuguese and English, in the `TRANSLATIONS` dict (`TRANSLATIONS["pt"][key]` / `TRANSLATIONS["en"][key]`). Adding a string in only one language is a bug.
- The current shipped version is `0.13.15` — the file's own changelog comment block will show a long run of `0.13.x` patch bumps (0.13.0 through 0.13.15), all one continuous feature arc (MD-conversion-tools integration: MarkItDown/Docling/Pandoc/pysrt-webvtt, now complete). **This delivery is a new minor version, `0.14.1`, not the next patch in that sequence — do not output `0.13.16`.** The `0.14.x` line begins a distinct new feature arc (the Dictionary system, polish levels, Claude API integration) — that's the actual reason for the minor-version bump rather than another patch. Set `APP_VERSION = "0.14.1"` exactly.
- No automatic network calls without explicit user action. The one exception in this version is described below (API key test) — it must be a button the user clicks, never triggered on dialog-open or app-start.
- Headless `xvfb-run` tests must pass before delivery. Deliver a complete pair: `TranscriptLab_v_0_14_1.py` + `test_v0141.py`. Copy the previous test file forward and extend it — don't start from scratch.
- Work incrementally. This is a large scope for one version — build and verify one piece at a time (compile-check after every edit; run the growing test suite periodically, not just once at the very end). Don't produce one giant unreviewable diff.
- Before finalizing: run the full test suite at least twice in a row from a clean state (`rm -rf` any test-generated config/data dirs between runs) to catch flaky/order-dependent tests, and do a final `py_compile` check.

## Relevant existing architecture (read the real file — this is a summary, not a substitute)

- `CONFIG_DIR` — portable config directory next to the script.
- `DICTIONARIES_FILE = CONFIG_DIR / "dictionaries.json"` — today's Whisper Dictionary storage: a flat dict `{profile_name: {"initial_prompt": str, "replacements": [[find, replace], ...]}}`, loaded into `self.dictionaries` via `load_json(DICTIONARIES_FILE, {})`.
- The current "Vocabulary Dictionary" tab (`_build_dictionary_tab`, around line 13404) is a simple two-pane editor: a listbox of profiles on the left (New/Duplicate/Delete), and on the right a profile-name field, an `initial_prompt` textarea, and a `replacements` textarea (parsed by the existing `parse_replacements_text` helper), saved via `_dict_save`.
- `polish_markdown(text, profile=...)` and friends (`polish_md_and_log`, `polish_md_text_and_log`, `polish_profile_for_model`) — the existing three-profile deterministic polish system (`"document"`, `"document-clean"`, `"prose"`). You are adding a **new, fourth axis** on top of this: a polish *level* (Off / Level 1 / Level 2), which is a different, orthogonal concept from the existing profile system — profile decides *how* to shape text for a given source; level decides *how much intelligence* gets applied. Both apply together. Do not collapse them into one concept.
- `HEADER_FIELDS`, `HEADER_LABELS` / `HEADER_LABELS_EN`, `HEADER_UNKNOWN`, `build_md_header()`, `auto_metadata_for_file()`, `resolve_header_metadata()` — the metadata header system. `"qualidade"` is currently hardcoded to `"Bruta"` in `auto_metadata_for_file`/the youtube equivalent, then flows through `resolve_header_metadata` (which respects a user override if one exists) into `build_md_header`.
- The "MD Conversion Tool" Settings hub (`_open_conversion_tool_settings`, around line 15203) — a card-per-item hub dialog with per-item "Settings / Install" buttons opening dedicated dialogs, each dialog with a `<FocusIn>` refresh binding. **Use this exact same hub pattern** for the new Dictionary tab landing view, and the same per-dialog `<FocusIn>` refresh convention for both new dialogs below.
- `CONVERSION_MODEL_IDS`, `_active_model()`, `_model_installed()` — the existing per-tool settings-menu pattern (`_open_docling_settings`, `_open_pandoc_settings`, etc.) to follow structurally for the new Claude API settings dialog.
- The Settings menu (`_build_menubar`) already lists: Whisper, MD Conversion Tool, yt-dlp, FFmpeg. Add a new entry for the Claude API dialog here, following the same `settings_menu.add_command(label=self.t("menu_X"), command=self._open_X_settings)` pattern.

## Scope of v0.14.1 — what's IN and OUT

**IN:**
1. Dictionary tab rename + restructure into a hub with explanatory text
2. Whisper Dictionary: Export/Import (both whole-file and per-profile)
3. MD Polish Dictionary: entirely new window — full CRUD, search/filter, import of the two seed files, duplicate detection, Export/Import (whole-file and per-term), a Suggestions review pane (UI only — empty state, since nothing populates it until v0.14.2), a stats strip
4. Level 1 deterministic polish rules, wired to read from the MD Polish Dictionary
5. Whisper-priming auto-curation (a generated suggestion the user can copy into a Whisper Dictionary profile — never auto-injected)
6. Quality header field wiring: "Bruta" → "Bruta harmonizada" when Level 1 runs
7. New Claude API settings dialog: key entry (masked), a real "Test Connection" button, model choice (hardcoded Sonnet/Haiku/Opus dropdown, Sonnet default)
8. "Finish by" wall-clock time added next to the three existing estimated-time displays (AV Transcription's live ETA, MD File Generation's and YouTube Transcription's pre-batch estimates) — see section 7 below

**OUT (this is v0.14.2, do not build it now):**
- The actual Level 2 polish pipeline: sending a transcript to Claude, the polish/correction/pruning prompt itself, parsing the structured JSON response, cost estimation, retry/fallback logic, dual-file + audit-log output, and the suggestion-generation that populates the Suggestions pane.
- **Important**: Level 2 must be *selectable* in the polish-level control (so the API-key infrastructure built now is genuinely usable ahead of v0.14.2), but if a user starts an actual batch with Level 2 selected, show a clear message — e.g. "Level 2 polish isn't implemented in this version yet; this batch will run at Level 1 instead" — and proceed at Level 1, rather than silently doing nothing, crashing, or claiming "Revisada 1" on output that never got LLM treatment. The Quality header must never claim a level that didn't actually run for that file.

## 1. Dictionary tab

Rename `"tab_dictionary"` string value from "Vocabulary Dictionary"/"Dicionário de Vocabulário" to **"Dictionary"/"Dicionário"** (keep the key name `tab_dictionary` unchanged — just the displayed text).

Rebuild `_build_dictionary_tab` as a hub with two cards (same visual pattern as `_open_conversion_tool_settings`'s cards): each card has a bold title, 2-3 sentences of plain-language explanation, a one-line live status, and a "Settings..." button.

**Whisper Dictionary card** — explanation should cover: this is vocabulary *hint text* fed directly to Whisper during transcription (the `--initial_prompt` mechanism), used to nudge Whisper's word choices toward domain vocabulary *while it's actively transcribing*. Status line: number of saved profiles (e.g., "3 profiles saved").

**MD Polish Dictionary card** — explanation should cover: this is a structured database of known terms, their correct spellings, predicted transcription errors, and definitions, used *after* transcription to detect and correct domain-specific errors during MD polishing (Level 1 and Level 2). Status line: term/core counts (e.g., "762 terms · 274 core").

Write real PT and EN copy for both explanations — don't leave placeholder text. Keep each explanation short enough to read in a few seconds; this is orientation, not documentation.

## 2. Whisper Dictionary — Export/Import

Add to the existing editor (the dialog opened by the hub's "Settings..." button — same widget layout as today, just now living in its own `tk.Toplevel` instead of being the whole tab):

- **Export selected profile**: file-save dialog, writes `{"initial_prompt": ..., "replacements": [...]}` for the currently-selected profile to a `.json` file the user names.
- **Export all profiles**: file-save dialog, writes the entire `self.dictionaries` dict as-is.
- **Import**: file-open dialog. Detect shape — if the loaded JSON has `initial_prompt`/`replacements` keys directly, treat it as a single profile and prompt for a name (pre-filled from the filename) before adding it to `self.dictionaries`; if it's a dict of `{name: {...}}` entries (the whole-file export shape), merge all of them in, prompting once if any name collides with an existing profile ("Overwrite / Skip / Rename" — reuse or mirror the existing duplicate-name handling already in `_dict_duplicate`/`_dict_save`).
- After any import, call `_refresh_dict_listbox()` and `_refresh_dictionary_dropdown()` (both already exist) and save via `save_json(DICTIONARIES_FILE, self.dictionaries)`.

## 3. MD Polish Dictionary — new window

### Data model

One unified table — no separate nucleo/full files. Storage: `MD_POLISH_DICT_FILE = CONFIG_DIR / "md_polish_dictionary.json"`, following the exact same `load_json`/`save_json` pattern as `DICTIONARIES_FILE`.

Shape: a dict keyed by a stable term ID (use a simple slug/uuid, not `termo` itself, since `termo` can be edited later without breaking references from the Suggestions pane in v0.14.2):

```json
{
  "term_ids": {
    "<id>": {
      "termo": "Sophia",
      "cat": "TRADICAO",
      "variantes": ["Hagia Sophia"],
      "erros_previstos": ["sofia", "so fia", "hagia sofia"],
      "risco_homofonia": true,
      "gloss": "",
      "pron": "",
      "n_obras": 0,
      "core": true
    }
  }
}
```

`cat` is free text with a combobox of existing categories for convenience (CONCEITO, ENTIDADE, TRADICAO, OBRA, LUGAR, PROJETO, ERA, LEI are the ones seen in the seed files) but must accept new values the user types — don't hardcode it as a closed enum.

### Seed file import — the two attached files define this shape exactly

Both seed files share this top-level shape:
```json
{"_uso": "<description text>", "_total": <int>, "termos": [ <term entries> ]}
```
Term entries in the seed files use the *same* field names as the internal model above (`termo`, `cat`, `variantes`, `erros_previstos`, `risco_homofonia`, `gloss`, `pron`, `n_obras`) except `risco_homofonia` is the *string* `"alto"` in the seed files where present (absent otherwise) — normalize this to the boolean `risco_homofonia: true/false` in the internal model, and there is no `core` field in the seed files at all — the import step is what decides it.

**Import logic**: an "Import lexicon JSON..." button. On load, check `_total` and the term count / field richness to distinguish which file was given — the simplest and most robust signal is field name presence: entries in the nucleo-shaped file mostly *lack* `pron` and `n_obras`; entries in the full-shaped file always have `gloss` and often have `pron`/`n_obras`. Don't hardcode filenames or exact counts (274/762) to detect the shape — those numbers will drift as Luiz's own lexicon grows. Instead: **explicitly ask the user** (a simple dialog: "Mark all imported terms as core?" Yes/No) rather than trying to silently infer core-ness from file shape. This is simpler, more robust, and puts a real decision in front of the person who actually knows which file they're loading.

**Merge behavior on import**: match existing entries by `termo` using a dedicated normalizer — `unicodedata.normalize("NFKD", s)`, filter out combining marks (category `Mn`), then `.casefold()`. **Do not reuse `_plsh_normalize_for_compare`** — that function strips punctuation and lowercases for sentence-level polish comparison, but never folds accents, so it would not actually make "Jose" and "José" compare equal. Write a small dedicated helper instead (e.g. `_normalize_term_key(s)`). If a term already exists: union the `variantes` and `erros_previstos` lists (dedupe), keep the longer/non-empty `gloss` and `pron` if the existing ones are empty, keep `core=true` if either the existing entry or the import says core, otherwise leave `core` as the existing value unless the user answered "yes" to the core-marking prompt above. If a term is new: add it fresh with a new `uuid.uuid4().hex` as its ID.

### Window layout

- Top: a search box (matches against `termo`, `variantes`, `erros_previstos` substrings, case/accent-insensitive) plus filter checkboxes: "Core only," "Homophone-risk only," and a category dropdown filter.
- Left: a `ttk.Treeview` table, columns: Termo | Categoria | Núcleo | Risco | # Variantes | # Erros — sortable by clicking column headers if reasonably easy with `ttk.Treeview`, not a hard requirement if it adds significant complexity.
- Right: detail/edit panel for the selected row — `termo` entry, `cat` combobox (editable), `core` checkbox, `risco_homofonia` checkbox, `variantes` as a simple add/remove list widget (entry + "Add" button + a listbox with a "Remove selected" button — reuse the same interaction pattern as the existing `replacements` editor if there's a clean one to borrow, otherwise keep it this simple), `erros_previstos` the same way, `gloss` as a multi-line text box, `pron` as a single-line entry, `n_obras` as a spinbox or plain integer entry.
- Save/Delete/New buttons for the currently-selected term.
- **Duplicate detection on save**: before saving, check whether any string in the term's `variantes` or `erros_previstos` already appears in *another* term's `variantes`/`erros_previstos`. If so, show a non-blocking warning ("This phrase is already registered under '<other termo>' — save anyway?") — Yes/No, don't hard-block, since legitimate overlaps can exist, but the user should see it.
- Export/Import buttons (whole-file and single-term-selected, matching the Whisper Dictionary answer above — same "detect shape, ask about collisions" pattern).
- **Suggestions pane**: a separate section (a notebook tab within this dialog, or a collapsible frame — your call on which reads cleaner) titled something like "Pending Suggestions." For v0.14.1, this reads from a `LEXICON_SUGGESTIONS_FILE = CONFIG_DIR / "lexicon_suggestions.json"` that starts out not existing / empty (`[]`). Build the full UI (list of pending suggestions with Approve/Reject buttons per entry, each approval merging into the main term table using the same merge logic as import, each rejection just removing it from the suggestions file) even though nothing will ever populate this file until v0.14.2 exists — show a clear empty-state message ("No pending suggestions — these will appear here once Level 2 polish runs and proposes new terms") rather than a blank pane.
- Stats strip (top or bottom of the dialog): total terms, core count, per-category breakdown (small text, doesn't need to be fancy), homophone-risk count, pending-suggestions count.

## 4. Level 1 deterministic rules

Add a new, explicit function, e.g. `apply_level1_rules(text, md_polish_dict) -> (text, stats)`, that runs **after** whatever `polish_markdown` profile already applies (call it with the already-profile-polished text as input, not raw text) — don't fold these four rules into `polish_markdown` itself or scatter them across call sites; keep this as one dedicated, testable function that each worker calls when the selected level is Level 1 or higher.

1. Strip raw SRT/VTT syntax artifacts that leak through MarkItDown's SRT passthrough — arrows (`-->`), cue index numbers, literal `HH:MM:SS,mmm` timestamps — when they appear in text that's about to be polished. (This closes a real gap found in v0.13.15's investigation: none of the three existing profiles do this today.)
2. Merge sentences Whisper split across a pause with no real sentence-ending punctuation between the fragments.
3. Collapse a lone stray-word fragment cue into its neighboring cue/sentence.
4. Run the MD Polish Dictionary's `erros_previstos → termo` replacement: for every term where `risco_homofonia` is false, do a case-insensitive, **word-boundary-aware** replacement of any `erros_previstos` string found in the text with `termo`. Build each pattern as `re.compile(r"\b" + re.escape(erro) + r"\b", re.IGNORECASE)` — **both the `re.escape()` and the `\b` boundaries are required**: several real entries in the seed lexicon contain regex-special characters (parentheses, periods), and without escaping, a raw `re.sub(erro, termo, text)` will silently misbehave or raise on those; without word boundaries, a short `erro` string risks matching inside an unrelated longer word. For terms where `risco_homofonia` is true, **do not replace** — instead, detect occurrences the same way (word-boundary regex match, no substitution) and record them in the returned `stats` dict under a new key, e.g. `stats["homophone_review"] = [{"found": "sofia", "possible_term": "Sophia"}, ...]`. Wire a new branch into the existing `format_polish_stats(stats, strings=None)` function (verified present, around line 6205 — it already builds a list of `parts` from `stats` dict keys the same way `stats.get("joined")`/`stats.get("page_markers")` do; add `if stats.get("homophone_review"): parts.append(...)` following that exact pattern) so this surfaces in the same log line as every other polish stat, not a separate, bolted-on notification path.

Quality header value becomes `"Bruta harmonizada"` / equivalent EN string (your call on the English wording — something like "Raw, harmonized" or "Raw harmonized" — pick something that reads naturally) whenever Level 1 successfully ran on a file. Wire this through the same `auto_metadata_for_file` → `resolve_header_metadata` → `build_md_header` chain that `"Bruta"` already flows through today — don't build a parallel mechanism.

## 5. Whisper-priming auto-curation

A button (place it in the MD Polish Dictionary window, near the stats strip is reasonable) — "Generate Whisper priming suggestion." Algorithm: take all `core: true` terms, sort by `n_obras` descending (ties broken by `termo` alphabetically for determinism), take enough terms to stay under roughly 180-200 tokens of output text (leave headroom under Whisper's ~224 token ceiling — use a simple `len(text) // 4` token estimate; there is no existing token-budget convention elsewhere in this codebase to match, this is a new, self-contained heuristic for this feature only, no need for a real tokenizer), and format them as natural, flowing priming prose (not a bare comma list — something like a sentence that mentions the terms in context), not a JSON dump.

This produces text shown in a dialog with a "Copy to clipboard" button — use the widget's own standard Tkinter `.clipboard_clear()` / `.clipboard_append()` methods; no new dependency needed for this. **Do not auto-inject it into any Whisper Dictionary profile.** The user pastes it in themselves if they want it, into whichever profile they choose, exactly like they'd paste in hand-written priming text today. This keeps a human decision in the loop for what Whisper actually receives.

## 6. Claude API settings dialog

New Settings menu entry ("Claude API..." / "API Claude..."), opening a dialog following the exact same structural pattern as `_open_docling_settings`/`_open_pandoc_settings` (status label, `<FocusIn>` refresh, Close button).

Fields:
- **API key**: a masked entry (show only the last 4 characters once saved, matching how a password field typically displays — `sk-ant-...XXXX` style; full key never displayed again after saving unless the user clicks a "Show" toggle). Store in `cfg["claude_api_key"]`. Add a clear, visible note in this dialog (both languages) that this key is stored in plain text in the app's local config folder, and that anyone with access to that folder can read it — consistent with this app's portable-by-design storage, but worth the user knowing explicitly. Don't skip this disclosure.
- **Model**: a dropdown with exactly three options, labeled clearly with what they are (balanced/cheaper-faster/most capable). Use these verified current Claude API model ID strings (confirmed directly against Anthropic's own docs at `platform.claude.com/docs/en/about-claude/models/overview` at prompt-writing time — re-verify if a meaningful amount of time has passed before you implement this, since these do change):
  - Sonnet (default): `claude-sonnet-5`
  - Haiku: `claude-haiku-4-5-20251001` (the pinned dated ID, not the bare `claude-haiku-4-5` alias — pin production usage to a fixed snapshot rather than an alias that can silently repoint to a different model later)
  - Opus: `claude-opus-5`

  Store the selected ID string directly in `cfg["claude_model"]`.
- **Test Connection** button: makes one real, minimal API call to `https://api.anthropic.com/v1/messages` using the entered key and selected model — smallest possible request (e.g. `max_tokens: 1`, a trivial single-word user message) purely to confirm the key authenticates and the model ID is valid. Show success ("✓ Connected — key is valid for <model>") or a specific failure reason (invalid key / model not found / network error / rate limited) rather than a generic error.

  **Two implementation requirements, both load-bearing, not optional:**
  1. **Use `urllib.request` from the standard library — not `requests`.** This click-handler runs in the app's own main process (it's UI code, not a subprocess), and while `requests` is confirmed present in the *shared tools venv* MarkItDown/yt-dlp run in, that's a separate Python environment reached only via subprocess — it says nothing about whether `requests` is importable in the process actually handling this button click. `urllib.request` needs no dependency check at all and is guaranteed present with any Python 3 install. Do not add the `anthropic` Python SDK as a new dependency for this version either — that decision belongs to v0.14.2, and it inherits this exact same main-process-vs-subprocess-venv consideration, worth deciding deliberately then rather than discovering mid-implementation.
  2. **Run the call on a background thread, not synchronously in the button handler.** Every other network-touching action in this app already uses a `threading.Thread` + `queue.Queue` + `self.after(...)`-polling pattern specifically to avoid freezing Tkinter's single-threaded event loop during a network round-trip (see `_attach_stream` and its callers for the established shape). Follow that same pattern here — a direct synchronous call would work fine in casual testing and freeze the whole UI on a slow connection or timeout.

  This button is the **only** network call anywhere in this version's new code — everything else must work fully offline.

## 7. "Finish by" clock time — small, standalone addition

Wherever the app already computes an estimated-time-remaining figure (in seconds), also show the wall-clock moment that estimate points to — e.g. "Finish by: Monday, 17/08/2026 at 14:55."

**Scope this precisely — verified against the real code, not assumed.** A genuine *live, self-correcting* "Estimated Time to Complete" figure exists in exactly one place today: AV Transcription's in-progress status line (`progress_label_var`, built around line 16585-16608, string key `status_eta_complete`). It already computes a raw `remaining * max(0.01, sf)` seconds figure before formatting it into `eta_txt` — use that raw seconds value, not the already-formatted string, to compute the finish time.

Two more places already compute a **pre-batch** estimate (shown before the user even clicks Start, not a live countdown) that's just as easy to extend the same way:
- MD File Generation's queue summary (`_update_md_summary`, `summary_est_convert`, raw value `total * per`)
- YouTube Transcription's queue summary (`_update_youtube_summary`, `summary_est_transcribe`, raw value `total * (per + delay)`)

**Do not** attempt to add a live in-progress ETA to YouTube Transcription, YouTube Download, or MD File Generation's *in-progress* status lines (`yt_progress_label_var`, `dl_progress_label_var`, `md_progress_label_var`) — none of them compute a live ETA today (only a "done X of Y" count), and building that from scratch (replicating AV Transcription's speed-factor self-correction logic for three different kinds of work) is a real feature, not this small addition. Leave those three as they are.

**Implementation**: a shared helper, e.g. `format_finish_by(seconds_from_now)` — computes `datetime.now() + timedelta(seconds=seconds_from_now)` and formats it as `"<weekday>, DD/MM/YYYY at HH:MM"` (24-hour clock, matching the time format already used consistently elsewhere in this file via `strftime("%H:%M:%S")`). Use DD/MM/YYYY with 24-hour time for **both** languages — this app's existing time displays are already 24-hour-clock throughout regardless of UI language, so don't introduce a US-style 12-hour/AM-PM variant just for the English UI. For the weekday name, use a small hardcoded PT/EN lookup table rather than the OS locale (Windows locale behavior has been an inconsistent source of bugs elsewhere in this app's history — don't reintroduce that risk here for a cosmetic label).

Add the "Finish by" text as a trailing segment on the same summary/status line, in its own translated string (e.g. `"finish_by": "Finish by: {when}"` / `"Terminará em: {when}"`), separated by the same `"   ·   "` divider already used between segments on these lines. Only show it when the estimate is non-zero/known (mirror whatever condition already gates showing the estimate itself at each of the three call sites — don't show "Finish by" next to a "—" or missing estimate).

## Testing expectations

- Every new function gets real unit tests, not just GUI smoke tests — especially: the merge-on-import logic (test actual merge scenarios: new term, existing term with new variant, existing term with conflicting data), the duplicate-detection logic, the `erros_previstos` replacement logic **including a test case where an `erros_previstos` string contains regex-special characters (e.g. a parenthesis) to confirm `re.escape()` is actually being applied and the call doesn't raise or misbehave**, the homophone-risk-detects-but-does-not-replace case, the Whisper-priming curation algorithm's token-budget respecting behavior, and the Quality-field wiring (a file processed at Level 1 gets "Bruta harmonizada" in its header; a file with polish off keeps "Bruta").
- The one network call (Test Connection) must be tested with the network call mocked — never make a real API call from within the test suite. Write at least one test confirming a *successful* mock response is handled correctly and one confirming a *failure* response (bad key, bad model) surfaces a clear, specific message rather than a generic error or a crash. Also test that it's dispatched via the background-thread/queue pattern (e.g. confirm the GUI thread isn't blocked — mirror however existing tests for `_attach_stream`-based flows in this suite already verify that).
- Confirm PT/EN string parity the same way it's been verified in past versions: every new key exists in both `TRANSLATIONS["pt"]` and `TRANSLATIONS["en"]`, and `{placeholder}` sets match between the two.
- Test that starting a batch with Level 2 selected in this version falls back to Level 1 with a clear message, and that the resulting file's Quality header honestly says "Bruta harmonizada," never "Revisada 1."
- Test `format_finish_by` directly (mock `datetime.now()` to a fixed value, confirm the weekday/date/time formatting is correct and deterministic), and test that each of the three call sites includes the "Finish by" segment when an estimate is known and omits it when the estimate is zero/unknown.

## Deliverable

`TranscriptLab_v_0_14_1.py` + `test_v0141.py`, both fully working, fully tested, `APP_VERSION = "0.14.1"`. Include a short changelog comment block at the top of the file (matching the style already used for every prior version in this file) summarizing what changed. Flag clearly in your final summary to Luiz: (1) if significant time has passed since this prompt was written, a quick confirmation that `claude-sonnet-5` / `claude-haiku-4-5-20251001` / `claude-opus-5` are still current model IDs (they were verified directly against Anthropic's docs at prompt-writing time, but model lineups do change), (2) any place you made a judgment call that isn't fully pinned down by this prompt, so those can be reviewed rather than silently locked in.
