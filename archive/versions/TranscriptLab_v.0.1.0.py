#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Whisper Batch Transcriber - GUI
=================================
Transcreve videos/audios em lote usando OpenAI Whisper (CLI),
com suporte a dicionario de vocabulario customizado (initial_prompt)
e substituicao de termos no pos-processamento.

Gera saida em .txt e .srt para cada arquivo.

Requisitos:
    - Python 3.9+ (Tkinter ja vem incluso na instalacao padrao do Python no Windows)
    - Whisper instalado (https://github.com/openai/whisper) em algum venv/PATH

Autor: gerado com apoio do Claude (Anthropic)
"""

import os
import sys
import json
import queue
import threading
import subprocess
import re
from pathlib import Path
from datetime import datetime

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

# --------------------------------------------------------------------------
# Configuracao / Persistencia
# --------------------------------------------------------------------------

CONFIG_DIR = Path.home() / ".whisper_transcriber"
CONFIG_FILE = CONFIG_DIR / "config.json"
DICTIONARIES_FILE = CONFIG_DIR / "dictionaries.json"

DEFAULT_WHISPER_PATHS = [
    r"C:\WhisperWorkspace\venv\Scripts\whisper.exe",
]

LANGUAGES = {
    "Portugues (PT-BR)": "Portuguese",
    "Ingles (EN)": "English",
    "Espanhol (ES)": "Spanish",
}

MODELS = {
    "Turbo  (melhor precisao, otima velocidade)": "turbo",
    "Medium (excelente p/ PT-BR)": "medium",
    "Small  (mais leve e rapido)": "small",
    "Large  (maxima precisao, mais lento)": "large",
}

MEDIA_EXTENSIONS = (".mkv", ".mp4", ".mp3", ".wav", ".m4a", ".webm", ".avi", ".mov")

STATUS_PENDING = "Pendente"
STATUS_RUNNING = "Transcrevendo..."
STATUS_DONE = "Concluido"
STATUS_ERROR = "Erro"
STATUS_SKIPPED = "Cancelado"


def ensure_config_dir():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


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


def find_default_whisper_path():
    """Try the known default path, then fall back to PATH lookup."""
    for p in DEFAULT_WHISPER_PATHS:
        if os.path.exists(p):
            return p
    # try PATH
    from shutil import which
    found = which("whisper") or which("whisper.exe")
    return found or DEFAULT_WHISPER_PATHS[0]


# --------------------------------------------------------------------------
# Modelo de item da fila
# --------------------------------------------------------------------------

class QueueItem:
    def __init__(self, filepath):
        self.filepath = filepath
        self.filename = os.path.basename(filepath)
        self.status = STATUS_PENDING
        self.error_message = ""
        self.output_txt = None
        self.output_srt = None


# --------------------------------------------------------------------------
# Worker de transcricao (roda em thread separada)
# --------------------------------------------------------------------------

class TranscriptionWorker(threading.Thread):
    """
    Executa a fila de transcricoes em uma thread de background,
    enviando eventos para a GUI atraves de uma Queue thread-safe.
    """

    def __init__(self, items, whisper_exe, lang_param, model_name,
                 initial_prompt, replacements, output_dir_mode,
                 fixed_output_dir, event_queue, stop_flag):
        super().__init__(daemon=True)
        self.items = items
        self.whisper_exe = whisper_exe
        self.lang_param = lang_param
        self.model_name = model_name
        self.initial_prompt = initial_prompt
        self.replacements = replacements  # list of (find, replace)
        self.output_dir_mode = output_dir_mode  # "same_folder" or "fixed"
        self.fixed_output_dir = fixed_output_dir
        self.event_queue = event_queue
        self.stop_flag = stop_flag  # threading.Event for cancellation
        self.current_process = None

    def post(self, kind, **kwargs):
        self.event_queue.put({"kind": kind, **kwargs})

    def run(self):
        for idx, item in enumerate(self.items):
            if self.stop_flag.is_set():
                item.status = STATUS_SKIPPED
                self.post("item_status", index=idx, status=STATUS_SKIPPED)
                continue

            self.post("item_status", index=idx, status=STATUS_RUNNING)
            self.post("log", text=f"\n{'=' * 70}\n[{idx + 1}/{len(self.items)}] Iniciando: {item.filename}\n{'=' * 70}\n")

            try:
                self._transcribe_one(item, idx)
                if self.stop_flag.is_set():
                    item.status = STATUS_SKIPPED
                    self.post("item_status", index=idx, status=STATUS_SKIPPED)
                else:
                    item.status = STATUS_DONE
                    self.post("item_status", index=idx, status=STATUS_DONE)
                    self.post("log", text=f"\n[OK] Concluido: {item.filename}\n")
            except Exception as e:
                item.status = STATUS_ERROR
                item.error_message = str(e)
                self.post("item_status", index=idx, status=STATUS_ERROR, error=str(e))
                self.post("log", text=f"\n[ERRO] Falha em {item.filename}: {e}\n")

        self.post("batch_finished")

    def _resolve_output_dir(self, item):
        if self.output_dir_mode == "fixed" and self.fixed_output_dir:
            return self.fixed_output_dir
        return os.path.dirname(item.filepath)

    def _transcribe_one(self, item, idx):
        out_dir = self._resolve_output_dir(item)
        os.makedirs(out_dir, exist_ok=True)

        cmd = [
            self.whisper_exe,
            item.filepath,
            "--model", self.model_name,
            "--language", self.lang_param,
            "--fp16", "False",
            "--output_dir", out_dir,
            "--output_format", "all",  # gera txt, srt, vtt, json, tsv
            "--verbose", "True",
        ]
        if self.initial_prompt:
            cmd.extend(["--initial_prompt", self.initial_prompt])

        self.post("log", text=f"Comando: {' '.join(cmd)}\n\n")

        # shell=False + lista de argumentos: forma correta e segura no Windows.
        # Evita o problema de shell=True ignorar os demais argumentos da lista.
        creationflags = 0
        if os.name == "nt":
            creationflags = subprocess.CREATE_NO_WINDOW

        self.current_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            creationflags=creationflags,
        )

        for line in self.current_process.stdout:
            if self.stop_flag.is_set():
                self.current_process.terminate()
                break
            self.post("log", text=line)
            # Tenta extrair timestamp de progresso tipo [00:12:34.560 --> 00:12:38.920]
            self._maybe_report_progress(idx, line)

        self.current_process.wait()

        if not self.stop_flag.is_set() and self.current_process.returncode != 0:
            raise RuntimeError(
                f"whisper saiu com codigo {self.current_process.returncode}. "
                f"Verifique o caminho do executavel e os logs acima."
            )

        if self.stop_flag.is_set():
            return

        # Pos-processamento: aplica dicionario de substituicao no .txt e .srt
        base = os.path.splitext(os.path.basename(item.filepath))[0]
        txt_path = os.path.join(out_dir, base + ".txt")
        srt_path = os.path.join(out_dir, base + ".srt")

        if self.replacements:
            self._apply_replacements(txt_path)
            self._apply_replacements(srt_path)

        item.output_txt = txt_path if os.path.exists(txt_path) else None
        item.output_srt = srt_path if os.path.exists(srt_path) else None

        # --output_format all tambem gera .vtt, .json e .tsv como subproduto.
        # O usuario pediu apenas .txt e .srt, entao removemos os extras para
        # nao poluir a pasta de saida.
        for extra_ext in (".vtt", ".json", ".tsv"):
            extra_path = os.path.join(out_dir, base + extra_ext)
            if os.path.exists(extra_path):
                try:
                    os.remove(extra_path)
                except OSError:
                    pass  # nao critico, ignora silenciosamente

    TIME_RE = re.compile(r"\[(\d+):(\d+)\.(\d+)\s*-->\s*(\d+):(\d+)\.(\d+)\]")

    def _maybe_report_progress(self, idx, line):
        m = self.TIME_RE.search(line)
        if m:
            mm, ss, _ = int(m.group(4)), int(m.group(5)), m.group(6)
            current_seconds = mm * 60 + ss
            self.post("progress_tick", index=idx, seconds=current_seconds)

    def _apply_replacements(self, path):
        if not path or not os.path.exists(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            for find, replace in self.replacements:
                if not find:
                    # Guarda de seguranca: find vazio corromperia o arquivo todo.
                    continue
                # Substituicao simples, case-sensitive, palavra a palavra
                content = content.replace(find, replace)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
        except OSError as e:
            self.post("log", text=f"[AVISO] Nao foi possivel aplicar dicionario em {path}: {e}\n")

    def cancel(self):
        self.stop_flag.set()
        if self.current_process and self.current_process.poll() is None:
            try:
                self.current_process.terminate()
            except OSError:
                pass


# --------------------------------------------------------------------------
# GUI Principal
# --------------------------------------------------------------------------

class WhisperTranscriberApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Whisper Batch Transcriber")
        self.geometry("980x820")
        self.minsize(860, 680)

        ensure_config_dir()
        self.config_data = load_json(CONFIG_FILE, {})
        self.dictionaries = load_json(DICTIONARIES_FILE, {})

        self.queue_items = []  # list[QueueItem]
        self.event_queue = queue.Queue()
        self.worker = None
        self.stop_flag = threading.Event()
        self.is_running = False

        self._build_ui()
        self._load_saved_settings()
        self.after(150, self._poll_events)

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---------------------------------------------------------------- UI ---

    def _build_ui(self):
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=8, pady=8)

        self.tab_main = ttk.Frame(notebook)
        self.tab_dict = ttk.Frame(notebook)
        notebook.add(self.tab_main, text="Transcricao")
        notebook.add(self.tab_dict, text="Dicionarios de Vocabulario")

        self._build_main_tab(self.tab_main)
        self._build_dict_tab(self.tab_dict)

    # --- Aba principal -------------------------------------------------

    def _build_main_tab(self, parent):
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(3, weight=1)

        # --- Configuracao do Whisper ---
        cfg_frame = ttk.LabelFrame(parent, text="Configuracao do Whisper")
        cfg_frame.grid(row=0, column=0, sticky="ew", padx=4, pady=4)
        cfg_frame.columnconfigure(1, weight=1)

        ttk.Label(cfg_frame, text="Executavel do whisper:").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        self.whisper_path_var = tk.StringVar()
        ttk.Entry(cfg_frame, textvariable=self.whisper_path_var).grid(row=0, column=1, sticky="ew", padx=4, pady=4)
        ttk.Button(cfg_frame, text="Procurar...", command=self._browse_whisper_exe).grid(row=0, column=2, padx=4, pady=4)

        ttk.Label(cfg_frame, text="Idioma do audio:").grid(row=1, column=0, sticky="w", padx=4, pady=4)
        self.lang_var = tk.StringVar(value=list(LANGUAGES.keys())[0])
        ttk.Combobox(cfg_frame, textvariable=self.lang_var, values=list(LANGUAGES.keys()),
                     state="readonly").grid(row=1, column=1, sticky="w", padx=4, pady=4)

        ttk.Label(cfg_frame, text="Modelo de IA:").grid(row=1, column=2, sticky="e", padx=4, pady=4)
        self.model_var = tk.StringVar(value=list(MODELS.keys())[0])
        ttk.Combobox(cfg_frame, textvariable=self.model_var, values=list(MODELS.keys()),
                     state="readonly", width=32).grid(row=1, column=3, sticky="w", padx=4, pady=4)

        ttk.Label(cfg_frame, text="Dicionario de vocabulario:").grid(row=2, column=0, sticky="w", padx=4, pady=4)
        self.dict_var = tk.StringVar(value="(Nenhum)")
        self.dict_combo = ttk.Combobox(cfg_frame, textvariable=self.dict_var, state="readonly")
        self.dict_combo.grid(row=2, column=1, sticky="w", padx=4, pady=4)
        self._refresh_dict_combo()

        ttk.Label(cfg_frame, text="Pasta de saida:").grid(row=3, column=0, sticky="w", padx=4, pady=4)
        self.output_mode_var = tk.StringVar(value="same_folder")
        out_frame = ttk.Frame(cfg_frame)
        out_frame.grid(row=3, column=1, columnspan=3, sticky="ew", padx=4, pady=4)
        ttk.Radiobutton(out_frame, text="Mesma pasta de cada video", variable=self.output_mode_var,
                        value="same_folder", command=self._toggle_output_dir).pack(side="left")
        ttk.Radiobutton(out_frame, text="Pasta fixa:", variable=self.output_mode_var,
                        value="fixed", command=self._toggle_output_dir).pack(side="left", padx=(12, 4))
        self.fixed_output_var = tk.StringVar()
        self.fixed_output_entry = ttk.Entry(out_frame, textvariable=self.fixed_output_var, state="disabled", width=40)
        self.fixed_output_entry.pack(side="left", padx=4)
        self.fixed_output_btn = ttk.Button(out_frame, text="Procurar...", command=self._browse_output_dir, state="disabled")
        self.fixed_output_btn.pack(side="left")

        # --- Fila de arquivos ---
        queue_frame = ttk.LabelFrame(parent, text="Fila de Transcricao")
        queue_frame.grid(row=1, column=0, sticky="ew", padx=4, pady=4)

        btn_row = ttk.Frame(queue_frame)
        btn_row.pack(fill="x", padx=4, pady=4)
        ttk.Button(btn_row, text="+ Adicionar arquivos...", command=self._add_files).pack(side="left", padx=2)
        ttk.Button(btn_row, text="Remover selecionado", command=self._remove_selected).pack(side="left", padx=2)
        ttk.Button(btn_row, text="Limpar fila", command=self._clear_queue).pack(side="left", padx=2)
        ttk.Button(btn_row, text="Mover para cima", command=lambda: self._move_selected(-1)).pack(side="left", padx=(20, 2))
        ttk.Button(btn_row, text="Mover para baixo", command=lambda: self._move_selected(1)).pack(side="left", padx=2)

        columns = ("ordem", "arquivo", "pasta", "status")
        self.tree = ttk.Treeview(queue_frame, columns=columns, show="headings", height=8, selectmode="extended")
        self.tree.heading("ordem", text="#")
        self.tree.heading("arquivo", text="Arquivo")
        self.tree.heading("pasta", text="Pasta")
        self.tree.heading("status", text="Status")
        self.tree.column("ordem", width=36, anchor="center")
        self.tree.column("arquivo", width=280)
        self.tree.column("pasta", width=340)
        self.tree.column("status", width=140, anchor="center")
        self.tree.pack(fill="x", padx=4, pady=(0, 4))

        # --- Controles de execucao ---
        run_frame = ttk.Frame(parent)
        run_frame.grid(row=2, column=0, sticky="ew", padx=4, pady=4)
        self.start_btn = ttk.Button(run_frame, text="Iniciar Transcricao em Lote", command=self._start_batch)
        self.start_btn.pack(side="left", padx=4)
        self.cancel_btn = ttk.Button(run_frame, text="Cancelar", command=self._cancel_batch, state="disabled")
        self.cancel_btn.pack(side="left", padx=4)

        self.overall_progress = ttk.Progressbar(run_frame, mode="determinate", length=300)
        self.overall_progress.pack(side="left", padx=12)
        self.overall_label = ttk.Label(run_frame, text="Aguardando inicio...")
        self.overall_label.pack(side="left", padx=4)

        # --- Log em tempo real ---
        log_frame = ttk.LabelFrame(parent, text="Atividade do Whisper (saida em tempo real)")
        log_frame.grid(row=3, column=0, sticky="nsew", padx=4, pady=4)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.log_text = tk.Text(log_frame, wrap="word", state="disabled", bg="#0d1117", fg="#c9d1d9",
                                insertbackground="#c9d1d9", font=("Consolas", 9))
        log_scroll = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scroll.set)
        self.log_text.grid(row=0, column=0, sticky="nsew")
        log_scroll.grid(row=0, column=1, sticky="ns")

    # --- Aba de dicionarios --------------------------------------------

    def _build_dict_tab(self, parent):
        parent.columnconfigure(0, weight=1, minsize=240)
        parent.columnconfigure(1, weight=2)
        parent.rowconfigure(1, weight=1)

        ttk.Label(parent, text="Perfis salvos:").grid(row=0, column=0, sticky="w", padx=8, pady=(8, 2))

        list_frame = ttk.Frame(parent)
        list_frame.grid(row=1, column=0, sticky="nsew", padx=8, pady=4)
        list_frame.rowconfigure(0, weight=1)
        list_frame.columnconfigure(0, weight=1)
        self.dict_listbox = tk.Listbox(list_frame, exportselection=False, width=24)
        self.dict_listbox.grid(row=0, column=0, sticky="nsew")
        list_scroll = ttk.Scrollbar(list_frame, command=self.dict_listbox.yview)
        self.dict_listbox.configure(yscrollcommand=list_scroll.set)
        list_scroll.grid(row=0, column=1, sticky="ns")

        btns = ttk.Frame(parent)
        btns.grid(row=2, column=0, sticky="ew", padx=8, pady=4)
        btns.columnconfigure((0, 1, 2), weight=1)
        ttk.Button(btns, text="Novo", command=self._new_dictionary).grid(row=0, column=0, sticky="ew", padx=2)
        ttk.Button(btns, text="Duplicar", command=self._duplicate_dictionary).grid(row=0, column=1, sticky="ew", padx=2)
        ttk.Button(btns, text="Excluir", command=self._delete_dictionary).grid(row=0, column=2, sticky="ew", padx=2)

        edit_frame = ttk.LabelFrame(parent, text="Editar Perfil")
        edit_frame.grid(row=0, column=1, rowspan=3, sticky="nsew", padx=8, pady=8)
        edit_frame.columnconfigure(0, weight=1)
        edit_frame.rowconfigure(2, weight=1)
        edit_frame.rowconfigure(5, weight=1)

        ttk.Label(edit_frame, text="Nome do perfil:").grid(row=0, column=0, sticky="w", padx=6, pady=(6, 0))
        self.dict_name_var = tk.StringVar()
        ttk.Entry(edit_frame, textvariable=self.dict_name_var).grid(row=1, column=0, sticky="ew", padx=6, pady=2)

        ttk.Label(
            edit_frame,
            text=("Texto de priming (--initial_prompt):\n"
                  "Escreva uma frase curta contendo os termos/nomes especiais "
                  "exatamente como devem aparecer. Ex: 'Jan Val Ellam fala sobre "
                  "a Revelacao Cosmica, Sagrada Familia Cosmica, Plano Causal e Atma.'")
        ).grid(row=2, column=0, sticky="nw", padx=6, pady=(8, 0))
        self.dict_prompt_text = tk.Text(edit_frame, height=6, wrap="word")
        self.dict_prompt_text.grid(row=3, column=0, sticky="nsew", padx=6, pady=4)

        ttk.Label(
            edit_frame,
            text=("Substituicoes pos-transcricao (uma por linha, formato: errado=correto):\n"
                  "Ex: 'val elam=Val Ellam'")
        ).grid(row=4, column=0, sticky="nw", padx=6, pady=(8, 0))
        self.dict_replacements_text = tk.Text(edit_frame, height=8, wrap="word")
        self.dict_replacements_text.grid(row=5, column=0, sticky="nsew", padx=6, pady=4)

        save_row = ttk.Frame(edit_frame)
        save_row.grid(row=6, column=0, sticky="ew", padx=6, pady=6)
        ttk.Button(save_row, text="Salvar Perfil", command=self._save_current_dictionary).pack(side="left")

        self._current_dict_name = None
        self._refresh_dict_listbox()

    # ---------------------------------------------------------- handlers ---

    def _browse_whisper_exe(self):
        path = filedialog.askopenfilename(
            title="Selecione o executavel do whisper",
            filetypes=[("Executavel", "*.exe"), ("Todos os arquivos", "*.*")] if os.name == "nt" else [("Todos os arquivos", "*.*")],
        )
        if path:
            self.whisper_path_var.set(path)

    def _toggle_output_dir(self):
        if self.output_mode_var.get() == "fixed":
            self.fixed_output_entry.configure(state="normal")
            self.fixed_output_btn.configure(state="normal")
        else:
            self.fixed_output_entry.configure(state="disabled")
            self.fixed_output_btn.configure(state="disabled")

    def _browse_output_dir(self):
        path = filedialog.askdirectory(title="Selecione a pasta de saida")
        if path:
            self.fixed_output_var.set(path)

    def _add_files(self):
        paths = filedialog.askopenfilenames(
            title="Selecione um ou mais arquivos de midia (pode repetir em pastas diferentes)",
            filetypes=[
                ("Arquivos de midia", " ".join("*" + e for e in MEDIA_EXTENSIONS)),
                ("Todos os arquivos", "*.*"),
            ],
        )
        if not paths:
            return
        existing = {item.filepath for item in self.queue_items}
        added = 0
        for p in paths:
            if p not in existing:
                self.queue_items.append(QueueItem(p))
                added += 1
        self._refresh_tree()
        if added == 0:
            messagebox.showinfo("Aviso", "Todos os arquivos selecionados ja estao na fila.")

    def _selected_indices(self):
        sel = self.tree.selection()
        return sorted(self.tree.index(s) for s in sel)

    def _remove_selected(self):
        if self.is_running:
            messagebox.showwarning("Aviso", "Nao e possivel editar a fila durante a transcricao.")
            return
        indices = self._selected_indices()
        for i in reversed(indices):
            del self.queue_items[i]
        self._refresh_tree()

    def _clear_queue(self):
        if self.is_running:
            messagebox.showwarning("Aviso", "Nao e possivel editar a fila durante a transcricao.")
            return
        self.queue_items.clear()
        self._refresh_tree()

    def _move_selected(self, direction):
        if self.is_running:
            return
        indices = self._selected_indices()
        if not indices:
            return
        if direction < 0:
            order = indices
        else:
            order = reversed(indices)
        for i in order:
            j = i + direction
            if 0 <= j < len(self.queue_items):
                self.queue_items[i], self.queue_items[j] = self.queue_items[j], self.queue_items[i]
        self._refresh_tree()
        # reselect moved items
        new_indices = [min(max(i + direction, 0), len(self.queue_items) - 1) for i in indices]
        self.tree.selection_set([self.tree.get_children()[i] for i in new_indices])

    def _refresh_tree(self):
        self.tree.delete(*self.tree.get_children())
        for idx, item in enumerate(self.queue_items, 1):
            self.tree.insert("", "end", values=(idx, item.filename, os.path.dirname(item.filepath), item.status))

    def _refresh_dict_combo(self):
        names = ["(Nenhum)"] + sorted(self.dictionaries.keys())
        self.dict_combo.configure(values=names)
        if self.dict_var.get() not in names:
            self.dict_var.set("(Nenhum)")

    # --- Dicionario tab handlers ---

    def _refresh_dict_listbox(self):
        self.dict_listbox.delete(0, "end")
        for name in sorted(self.dictionaries.keys()):
            self.dict_listbox.insert("end", name)

    def _on_dict_select(self, event):
        sel = self.dict_listbox.curselection()
        if not sel:
            return
        name = self.dict_listbox.get(sel[0])
        self._load_dictionary_into_editor(name)

    def _load_dictionary_into_editor(self, name):
        data = self.dictionaries.get(name, {})
        self._current_dict_name = name
        self.dict_name_var.set(name)
        self.dict_prompt_text.delete("1.0", "end")
        self.dict_prompt_text.insert("1.0", data.get("prompt", ""))
        self.dict_replacements_text.delete("1.0", "end")
        repl_lines = [f"{f}={t}" for f, t in data.get("replacements", [])]
        self.dict_replacements_text.insert("1.0", "\n".join(repl_lines))

    def _new_dictionary(self):
        self._current_dict_name = None
        self.dict_name_var.set("")
        self.dict_prompt_text.delete("1.0", "end")
        self.dict_replacements_text.delete("1.0", "end")

    def _duplicate_dictionary(self):
        sel = self.dict_listbox.curselection()
        if not sel:
            messagebox.showinfo("Aviso", "Selecione um perfil para duplicar.")
            return
        name = self.dict_listbox.get(sel[0])
        new_name = simpledialog.askstring("Duplicar Perfil", "Nome do novo perfil:", initialvalue=name + " (copia)")
        if not new_name:
            return
        if new_name in self.dictionaries:
            messagebox.showerror("Erro", "Ja existe um perfil com esse nome.")
            return
        self.dictionaries[new_name] = json.loads(json.dumps(self.dictionaries[name]))
        save_json(DICTIONARIES_FILE, self.dictionaries)
        self._refresh_dict_listbox()
        self._refresh_dict_combo()

    def _delete_dictionary(self):
        sel = self.dict_listbox.curselection()
        if not sel:
            return
        name = self.dict_listbox.get(sel[0])
        if messagebox.askyesno("Confirmar", f"Excluir o perfil '{name}'?"):
            del self.dictionaries[name]
            save_json(DICTIONARIES_FILE, self.dictionaries)
            self._refresh_dict_listbox()
            self._refresh_dict_combo()
            self._new_dictionary()

    def _save_current_dictionary(self):
        name = self.dict_name_var.get().strip()
        if not name:
            messagebox.showerror("Erro", "De um nome ao perfil antes de salvar.")
            return
        prompt = self.dict_prompt_text.get("1.0", "end").strip()
        raw_lines = self.dict_replacements_text.get("1.0", "end").strip().splitlines()
        replacements = []
        for line in raw_lines:
            line = line.strip()
            if not line or "=" not in line:
                continue
            find, _, replace = line.partition("=")
            find = find.strip()
            replace = replace.strip()
            if not find:
                # Uma string de busca vazia corromperia o arquivo inteiro
                # (str.replace("", x) insere x entre cada caractere). Ignorada.
                continue
            replacements.append([find, replace])

        # Se o nome mudou em relacao ao perfil que estava sendo editado, remove o antigo
        if self._current_dict_name and self._current_dict_name != name:
            self.dictionaries.pop(self._current_dict_name, None)

        self.dictionaries[name] = {"prompt": prompt, "replacements": replacements}
        save_json(DICTIONARIES_FILE, self.dictionaries)
        self._current_dict_name = name
        self._refresh_dict_listbox()
        self._refresh_dict_combo()
        self.dict_var.set(name)
        messagebox.showinfo("Salvo", f"Perfil '{name}' salvo com sucesso.")

    # ---------------------------------------------------------- execucao ---

    def _validate_before_start(self):
        if not self.queue_items:
            messagebox.showerror("Erro", "Adicione pelo menos um arquivo a fila.")
            return False
        whisper_path = self.whisper_path_var.get().strip()
        if not whisper_path:
            messagebox.showerror("Erro", "Informe o caminho do executavel do whisper.")
            return False
        if whisper_path not in ("whisper", "whisper.exe") and not os.path.exists(whisper_path):
            if not messagebox.askyesno(
                "Aviso",
                f"O caminho '{whisper_path}' nao foi encontrado no disco.\n"
                "Deseja tentar executar mesmo assim (ex: caso esteja no PATH do sistema)?"
            ):
                return False
        if self.output_mode_var.get() == "fixed" and not self.fixed_output_var.get().strip():
            messagebox.showerror("Erro", "Selecione a pasta de saida fixa ou troque para 'mesma pasta de cada video'.")
            return False
        return True

    def _start_batch(self):
        if self.is_running:
            return
        if not self._validate_before_start():
            return

        self._save_current_settings()

        for item in self.queue_items:
            item.status = STATUS_PENDING
            item.error_message = ""
        self._refresh_tree()

        lang_param = LANGUAGES[self.lang_var.get()]
        model_name = MODELS[self.model_var.get()]

        dict_name = self.dict_var.get()
        prompt = ""
        replacements = []
        if dict_name and dict_name != "(Nenhum)":
            d = self.dictionaries.get(dict_name, {})
            prompt = d.get("prompt", "")
            replacements = [tuple(p) for p in d.get("replacements", [])]

        output_dir_mode = self.output_mode_var.get()
        fixed_output_dir = self.fixed_output_var.get().strip()

        self.stop_flag = threading.Event()
        self.event_queue = queue.Queue()
        self.worker = TranscriptionWorker(
            items=self.queue_items,
            whisper_exe=self.whisper_path_var.get().strip(),
            lang_param=lang_param,
            model_name=model_name,
            initial_prompt=prompt,
            replacements=replacements,
            output_dir_mode=output_dir_mode,
            fixed_output_dir=fixed_output_dir,
            event_queue=self.event_queue,
            stop_flag=self.stop_flag,
        )

        self.is_running = True
        self.start_btn.configure(state="disabled")
        self.cancel_btn.configure(state="normal")
        self.overall_progress.configure(value=0, maximum=max(len(self.queue_items), 1))
        self.overall_label.configure(text=f"Processando 0/{len(self.queue_items)}...")
        self._clear_log()
        self._log(f"Lote iniciado em {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

        self.worker.start()
        self.after(150, self._poll_events)

    def _cancel_batch(self):
        if self.worker and self.is_running:
            if messagebox.askyesno("Cancelar", "Cancelar o lote? O arquivo atual sera interrompido."):
                self._do_cancel()

    def _cancel_batch_for_test(self):
        """Direct cancel without confirmation dialog. Used by automated tests only."""
        if self.worker and self.is_running:
            self._do_cancel()

    def _do_cancel(self):
        self._log("\n[CANCELANDO] Interrompendo apos o arquivo atual...\n")
        self.worker.cancel()
        self.cancel_btn.configure(state="disabled")

    def _on_batch_finished(self):
        self.is_running = False
        self.start_btn.configure(state="normal")
        self.cancel_btn.configure(state="disabled")
        done = sum(1 for i in self.queue_items if i.status == STATUS_DONE)
        errors = sum(1 for i in self.queue_items if i.status == STATUS_ERROR)
        self.overall_label.configure(text=f"Finalizado: {done} concluido(s), {errors} erro(s)")
        self._log(f"\nLote finalizado em {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        if errors:
            messagebox.showwarning("Concluido com erros", f"{done} arquivo(s) concluidos, {errors} com erro. Veja o log para detalhes.")
        else:
            messagebox.showinfo("Concluido", f"Todos os {done} arquivo(s) foram transcritos com sucesso.")

    # ------------------------------------------------------ eventos/log ---

    def _poll_events(self):
        try:
            while True:
                evt = self.event_queue.get_nowait()
                self._handle_event(evt)
        except queue.Empty:
            pass

        if self.is_running:
            self.after(150, self._poll_events)

    def _handle_event(self, evt):
        kind = evt["kind"]
        if kind == "log":
            self._log(evt["text"])
        elif kind == "item_status":
            idx = evt["index"]
            status = evt["status"]
            self.queue_items[idx].status = status
            self._refresh_tree()
            if status in (STATUS_DONE, STATUS_ERROR, STATUS_SKIPPED):
                completed = sum(
                    1 for i in self.queue_items
                    if i.status in (STATUS_DONE, STATUS_ERROR, STATUS_SKIPPED)
                )
                self.overall_progress.configure(value=completed)
                self.overall_label.configure(text=f"Processando {completed}/{len(self.queue_items)}...")
        elif kind == "progress_tick":
            idx = evt["index"]
            mins = evt["seconds"] // 60
            secs = evt["seconds"] % 60
            self.overall_label.configure(
                text=f"Processando {idx + 1}/{len(self.queue_items)}  |  posicao no audio: {mins:02d}:{secs:02d}"
            )
        elif kind == "batch_finished":
            self._on_batch_finished()

    def _log(self, text):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", text)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _clear_log(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    # -------------------------------------------------------- settings ---

    def _load_saved_settings(self):
        whisper_path = self.config_data.get("whisper_path") or find_default_whisper_path()
        self.whisper_path_var.set(whisper_path)
        self.lang_var.set(self.config_data.get("lang", list(LANGUAGES.keys())[0]))
        self.model_var.set(self.config_data.get("model", list(MODELS.keys())[0]))
        self.dict_var.set(self.config_data.get("dictionary", "(Nenhum)"))
        self.output_mode_var.set(self.config_data.get("output_mode", "same_folder"))
        self.fixed_output_var.set(self.config_data.get("fixed_output_dir", ""))
        self._toggle_output_dir()
        self._refresh_dict_combo()

    def _save_current_settings(self):
        self.config_data.update({
            "whisper_path": self.whisper_path_var.get().strip(),
            "lang": self.lang_var.get(),
            "model": self.model_var.get(),
            "dictionary": self.dict_var.get(),
            "output_mode": self.output_mode_var.get(),
            "fixed_output_dir": self.fixed_output_var.get().strip(),
        })
        save_json(CONFIG_FILE, self.config_data)

    def _on_close(self):
        if self.is_running:
            if not messagebox.askyesno("Sair", "Uma transcricao esta em andamento. Sair mesmo assim?"):
                return
            if self.worker:
                self.worker.cancel()
        self._save_current_settings()
        self.destroy()


def main():
    app = WhisperTranscriberApp()
    app.mainloop()


if __name__ == "__main__":
    main()
