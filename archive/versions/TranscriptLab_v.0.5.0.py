#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Whisper Batch Transcriber - GUI
=================================
Transcreve videos/audios em lote usando OpenAI Whisper (CLI), com:
  - Interface bilingue (Portugues / English), trocavel na hora.
  - Dicionarios de vocabulario (initial_prompt + substituicoes pos-processo).
  - Barra de progresso por arquivo baseada na duracao real do audio (ffmpeg).
  - Escolha de quais formatos de saida manter (txt, srt, vtt, json, tsv).
  - Status do modelo + download sob demanda; status do ffmpeg.

Requisitos:
    - Python 3.9+ (Tkinter ja vem incluso na instalacao padrao do Python no Windows)
    - Whisper instalado (https://github.com/openai/whisper) em algum venv/PATH
    - ffmpeg recomendado (mas o app roda sem ele; so perde o % exato da barra)

Autor: gerado com apoio do Claude (Anthropic)
"""

import os
import re
import sys
import json
import time
import queue
import shutil
import threading
import subprocess
import webbrowser
from pathlib import Path
from datetime import datetime

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

# ==========================================================================
# Configuracao / Persistencia
# ==========================================================================

CONFIG_DIR = Path.home() / ".whisper_transcriber"
CONFIG_FILE = CONFIG_DIR / "config.json"
DICTIONARIES_FILE = CONFIG_DIR / "dictionaries.json"

DEFAULT_WHISPER_PATHS = [
    r"C:\WhisperWorkspace\venv\Scripts\whisper.exe",
]

# --- Idiomas da INTERFACE (nomes nativos, iguais nos dois idiomas) ---------
UI_LANGUAGES = [("pt", "Português"), ("en", "English")]

# --- Idiomas do AUDIO ------------------------------------------------------
# (key interna, parametro --language do whisper | None = auto-detectar)
AUDIO_LANGUAGES = [
    ("auto", None),
    ("portuguese", "Portuguese"),
    ("english", "English"),
    ("spanish", "Spanish"),
]
AUDIO_LANG_PARAM = {key: param for key, param in AUDIO_LANGUAGES}

# --- Tarefas ---------------------------------------------------------------
TASK_KEYS = ["transcribe", "translate"]  # --task transcribe | translate

# --- Formatos de saida do Whisper ------------------------------------------
OUTPUT_FORMATS = ["txt", "srt", "vtt", "json", "tsv"]
# Formatos textuais aos quais as substituicoes do dicionario PODEM ser
# aplicadas. JSON e deixado intacto de proposito (estrutura/escape).
TEXT_REPLACE_FORMATS = ["txt", "srt", "vtt", "tsv"]

# Catalogo de modelos. (cli_name, english_only, size_mb, vram_gb, desc_key)
# english_only=True => variante .en, usada so quando o audio for Ingles.
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

MEDIA_EXTENSIONS = (".mkv", ".mp4", ".mp3", ".wav", ".m4a", ".webm", ".avi", ".mov", ".flac", ".ogg")

# Estados internos (estaveis); o texto exibido e traduzido na hora.
ST_PENDING = "pending"
ST_RUNNING = "running"
ST_DONE = "done"
ST_ERROR = "error"
ST_SKIPPED = "skipped"
ST_TERMINAL = (ST_DONE, ST_ERROR, ST_SKIPPED)

FFMPEG_DOWNLOAD_URL = "https://ffmpeg.org/download.html"

# ==========================================================================
# Tabela de traducoes
# ==========================================================================

TRANSLATIONS = {
    "pt": {
        "window_title": "Whisper Batch Transcriber",
        # Abas
        "tab_transcription": "Transcrição",
        "tab_dictionary": "Dicionário de Vocabulário",
        # Config
        "cfg_frame": "Configuração do Whisper",
        "whisper_exe": "Executável do whisper:",
        "browse": "Procurar...",
        "ui_language": "Idioma da interface:",
        "audio_language": "Idioma do áudio:",
        "ai_model": "Modelo de IA:",
        "task": "Tarefa:",
        "vocab_dict": "Dicionário de vocabulário:",
        "none": "(Nenhum)",
        "model_status": "Status do modelo:",
        "check_download_model": "Verificar / Baixar Modelo",
        "ffmpeg_label": "FFmpeg:",
        "ffmpeg_found": "✓ Encontrado",
        "ffmpeg_not_found": "✗ Não encontrado (a transcrição pode falhar; o % da barra fica indisponível)",
        "ffmpeg_open_folder": "Abrir pasta",
        "ffmpeg_locate": "Localizar...",
        "ffmpeg_download": "Baixar",
        "output_folder": "Pasta de saída:",
        "same_folder": "Mesma pasta de cada vídeo",
        "fixed_folder": "Pasta fixa:",
        # Tarefas
        "task_transcribe": "Transcrever (mesmo idioma)",
        "task_translate": "Traduzir para Inglês",
        # Idiomas de audio
        "audlang_auto": "Detectar automaticamente",
        "audlang_portuguese": "Português (PT-BR)",
        "audlang_english": "Inglês (EN)",
        "audlang_spanish": "Espanhol (ES)",
        # Descricoes de modelo
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
        # Status do modelo
        "model_downloaded": "✓ Já baixado no cache  ({size}, ~{vram} GB VRAM recomendado)",
        "model_not_downloaded": "✗ NÃO baixado ainda  ({size} para baixar, ~{vram} GB VRAM recomendado)",
        # Formatos de saida
        "output_formats": "Formatos de saída (marque o que deseja manter):",
        "fmt_txt": "TXT — texto puro, sem marcação de tempo. Ideal para ler/estudar.",
        "fmt_srt": "SRT — legenda com tempos. Use em players de vídeo (YouTube, VLC).",
        "fmt_vtt": "VTT — legenda para web (HTML5). Semelhante ao SRT.",
        "fmt_json": "JSON — dados completos (tempos por palavra/segmento) para uso técnico.",
        "fmt_tsv": "TSV — tabela (início, fim, texto) para abrir em Excel/planilhas.",
        # Fila
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
        # Status (exibidos)
        "status_pending": "Pendente",
        "status_running": "Transcrevendo...",
        "status_done": "Concluído",
        "status_error": "Erro",
        "status_skipped": "Cancelado",
        # Execucao
        "start_batch": "Iniciar Transcrição em Lote",
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
        "log_batch_start": "Lote iniciado em {time}\n",
        "log_batch_end": "\nLote finalizado em {time}\n",
        "log_canceling": "\n[CANCELANDO] Interrompendo após o arquivo atual...\n",
        "log_file_start": "\n{sep}\n[{i}/{n}] Iniciando: {name}\n{sep}\n",
        "log_probing": "Analisando duração do áudio com ffmpeg...\n",
        "log_duration_ok": "Duração detectada: {dur}\n",
        "log_duration_fail": "Não foi possível detectar a duração (ffmpeg ausente ou formato não lido); a barra mostrará apenas atividade.\n",
        "log_cmd": "Comando: {cmd}\n\n",
        "log_file_done": "\n[OK] Concluído: {name}\n",
        "log_file_error": "\n[ERRO] Falha em {name}: {e}\n",
        "log_dict_warn": "[AVISO] Não foi possível aplicar dicionário em {path}: {e}\n",
        "log_download_start": "Iniciando download do modelo '{model}' ({size})...\n",
        "log_download_dest": "Destino: {dest}\n\n",
        "log_model_ok": "\n[OK] Modelo confirmado no cache local.\n",
        # Dialogs / mensagens
        "warn": "Aviso",
        "error": "Erro",
        "info": "Informação",
        "confirm": "Confirmar",
        "saved": "Salvo",
        "err_no_files": "Adicione pelo menos um arquivo à fila.",
        "err_no_whisper": "Informe o caminho do executável do whisper.",
        "err_no_format": "Selecione pelo menos um formato de saída.",
        "err_no_fixed_dir": "Selecione a pasta de saída fixa ou troque para 'mesma pasta de cada vídeo'.",
        "warn_path_not_found": "O caminho '{path}' não foi encontrado no disco.\nDeseja tentar executar mesmo assim (ex: caso esteja no PATH do sistema)?",
        "warn_queue_locked": "Não é possível editar a fila durante a transcrição.",
        "warn_lang_locked": "Não é possível trocar o idioma da interface durante uma transcrição. Cancele ou aguarde terminar.",
        "info_all_in_queue": "Todos os arquivos selecionados já estão na fila.",
        "select_media_title": "Selecione um ou mais arquivos de mídia (pode repetir em pastas diferentes)",
        "media_files": "Arquivos de mídia",
        "all_files": "Todos os arquivos",
        "select_whisper_title": "Selecione o executável do whisper",
        "select_ffmpeg_title": "Selecione o executável do ffmpeg",
        "executable": "Executável",
        "select_output_title": "Selecione a pasta de saída",
        "cancel_title": "Cancelar",
        "cancel_question": "Cancelar o lote? O arquivo atual será interrompido.",
        "exit_title": "Sair",
        "exit_question": "Uma transcrição está em andamento. Sair mesmo assim?",
        "model_available_title": "Modelo já disponível",
        "model_available_msg": "O modelo '{model}' já está baixado em:\n{path}\n\nNão é necessário baixar novamente.",
        "download_model_title": "Baixar modelo",
        "download_model_msg": "O modelo '{model}' ainda não está no seu computador.\n\nTamanho aproximado: {size}\nSerá baixado uma única vez e guardado em:\n{dest}\n\nIsso pode demorar dependendo da sua internet. Deseja baixar agora?",
        "download_done_title": "Download concluído",
        "download_done_msg": "Modelo baixado com sucesso e pronto para uso.",
        "download_error_title": "Erro no download",
        "download_error_msg": "Não foi possível baixar o modelo.\n\n{error}\n\nVerifique sua conexão com a internet e tente novamente. Veja o log para mais detalhes.",
        "downloading_status": "Baixando modelo... veja o progresso no log abaixo.",
        "finished_with_errors_title": "Concluído com erros",
        "finished_with_errors_msg": "{done} arquivo(s) concluídos, {errors} com erro. Veja o log para detalhes.",
        "finished_title": "Concluído",
        "finished_msg": "Todos os {done} arquivo(s) foram transcritos com sucesso.",
        "ffmpeg_missing_warn": "ffmpeg não foi encontrado. O Whisper precisa dele para ler a maioria dos formatos de áudio/vídeo, então a transcrição pode falhar. Você pode continuar mesmo assim (arquivos .wav às vezes funcionam sem ffmpeg).\n\nDeseja continuar?",
        # Dicionarios
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
        # Recorte de intervalo
        "clip_frame": "Transcrever apenas um trecho (opcional)",
        "clip_enable": "Transcrever somente de um ponto a outro do vídeo/áudio",
        "clip_start": "Início:",
        "clip_end": "Fim:",
        "clip_hint": "Formato H:MM:SS (ex.: 0:05:00 = 5 minutos). Deixe a caixa desmarcada para processar o arquivo inteiro.",
        "clip_needs_ffmpeg": "Este recurso precisa do ffmpeg (usado para cortar o trecho antes de transcrever). Localize o ffmpeg acima para habilitá-lo.",
        "err_clip_invalid": "Verifique os campos de início/fim do trecho. Use o formato H:MM:SS e garanta que o fim seja depois do início.",
        "err_clip_needs_ffmpeg": "O recorte de trecho está marcado, mas o ffmpeg não foi encontrado. Localize o ffmpeg ou desmarque essa opção.",
        # Fase "preparando" (antes do primeiro segmento aparecer)
        "phase_preparing": "Carregando modelo e preparando o áudio... isso pode levar alguns minutos (a barra ficará completa quando a transcrição real começar).",
        "phase_transcribing_note": "Transcrevendo...",
        # Rede de seguranca (transcricao parcial)
        "partial_output_note": "Um arquivo '*.partial.txt' está sendo salvo continuamente nesta pasta como rede de segurança, caso o processo seja interrompido.",
    },
    "en": {
        "window_title": "Whisper Batch Transcriber",
        "tab_transcription": "Transcription",
        "tab_dictionary": "Vocabulary Dictionary",
        "cfg_frame": "Whisper Configuration",
        "whisper_exe": "Whisper executable:",
        "browse": "Browse...",
        "ui_language": "Interface language:",
        "audio_language": "Audio language:",
        "ai_model": "AI model:",
        "task": "Task:",
        "vocab_dict": "Vocabulary dictionary:",
        "none": "(None)",
        "model_status": "Model status:",
        "check_download_model": "Check / Download Model",
        "ffmpeg_label": "FFmpeg:",
        "ffmpeg_found": "✓ Found",
        "ffmpeg_not_found": "✗ Not found (transcription may fail; the % bar is unavailable)",
        "ffmpeg_open_folder": "Open folder",
        "ffmpeg_locate": "Locate...",
        "ffmpeg_download": "Download",
        "output_folder": "Output folder:",
        "same_folder": "Same folder as each video",
        "fixed_folder": "Fixed folder:",
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
        "fmt_txt": "TXT — plain text, no timestamps. Best for reading/studying.",
        "fmt_srt": "SRT — subtitles with timing. Use in video players (YouTube, VLC).",
        "fmt_vtt": "VTT — web subtitles (HTML5). Similar to SRT.",
        "fmt_json": "JSON — full data (per-word/segment timing) for technical use.",
        "fmt_tsv": "TSV — table (start, end, text) to open in Excel/spreadsheets.",
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
        "status_done": "Done",
        "status_error": "Error",
        "status_skipped": "Canceled",
        "start_batch": "Start Batch Transcription",
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
        "log_batch_start": "Batch started at {time}\n",
        "log_batch_end": "\nBatch finished at {time}\n",
        "log_canceling": "\n[CANCELING] Stopping after the current file...\n",
        "log_file_start": "\n{sep}\n[{i}/{n}] Starting: {name}\n{sep}\n",
        "log_probing": "Probing audio duration with ffmpeg...\n",
        "log_duration_ok": "Detected duration: {dur}\n",
        "log_duration_fail": "Could not detect duration (ffmpeg missing or format unreadable); the bar will show activity only.\n",
        "log_cmd": "Command: {cmd}\n\n",
        "log_file_done": "\n[OK] Finished: {name}\n",
        "log_file_error": "\n[ERROR] Failed on {name}: {e}\n",
        "log_dict_warn": "[WARNING] Could not apply dictionary to {path}: {e}\n",
        "log_download_start": "Starting download of model '{model}' ({size})...\n",
        "log_download_dest": "Destination: {dest}\n\n",
        "log_model_ok": "\n[OK] Model confirmed in local cache.\n",
        "warn": "Warning",
        "error": "Error",
        "info": "Information",
        "confirm": "Confirm",
        "saved": "Saved",
        "err_no_files": "Add at least one file to the queue.",
        "err_no_whisper": "Provide the path to the whisper executable.",
        "err_no_format": "Select at least one output format.",
        "err_no_fixed_dir": "Select the fixed output folder or switch to 'same folder as each video'.",
        "warn_path_not_found": "The path '{path}' was not found on disk.\nDo you want to try running it anyway (e.g. if it's on the system PATH)?",
        "warn_queue_locked": "The queue cannot be edited during transcription.",
        "warn_lang_locked": "The interface language cannot be changed during a transcription. Cancel or wait for it to finish.",
        "info_all_in_queue": "All selected files are already in the queue.",
        "select_media_title": "Select one or more media files (you can repeat across folders)",
        "media_files": "Media files",
        "all_files": "All files",
        "select_whisper_title": "Select the whisper executable",
        "select_ffmpeg_title": "Select the ffmpeg executable",
        "executable": "Executable",
        "select_output_title": "Select the output folder",
        "cancel_title": "Cancel",
        "cancel_question": "Cancel the batch? The current file will be interrupted.",
        "exit_title": "Exit",
        "exit_question": "A transcription is in progress. Exit anyway?",
        "model_available_title": "Model already available",
        "model_available_msg": "The model '{model}' is already downloaded at:\n{path}\n\nNo need to download again.",
        "download_model_title": "Download model",
        "download_model_msg": "The model '{model}' is not on your computer yet.\n\nApproximate size: {size}\nIt will be downloaded once and stored in:\n{dest}\n\nThis may take a while depending on your internet. Download now?",
        "download_done_title": "Download complete",
        "download_done_msg": "Model downloaded successfully and ready to use.",
        "download_error_title": "Download error",
        "download_error_msg": "Could not download the model.\n\n{error}\n\nCheck your internet connection and try again. See the log for details.",
        "downloading_status": "Downloading model... see progress in the log below.",
        "finished_with_errors_title": "Finished with errors",
        "finished_with_errors_msg": "{done} file(s) finished, {errors} with error. See the log for details.",
        "finished_title": "Finished",
        "finished_msg": "All {done} file(s) were transcribed successfully.",
        "ffmpeg_missing_warn": "ffmpeg was not found. Whisper needs it to read most audio/video formats, so transcription may fail. You can continue anyway (.wav files sometimes work without ffmpeg).\n\nContinue?",
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
        # Time-range clipping
        "clip_frame": "Transcribe only part of the file (optional)",
        "clip_enable": "Transcribe only from one point to another in the video/audio",
        "clip_start": "Start:",
        "clip_end": "End:",
        "clip_hint": "Format H:MM:SS (e.g. 0:05:00 = 5 minutes). Leave unchecked to process the whole file.",
        "clip_needs_ffmpeg": "This feature needs ffmpeg (used to cut the segment before transcribing). Locate ffmpeg above to enable it.",
        "err_clip_invalid": "Check the start/end fields. Use the H:MM:SS format and make sure the end is after the start.",
        "err_clip_needs_ffmpeg": "Time-range clipping is checked, but ffmpeg was not found. Locate ffmpeg or uncheck this option.",
        # "Preparing" phase (before the first segment appears)
        "phase_preparing": "Loading the model and preparing the audio... this can take a few minutes (the bar will fill in once real transcription starts).",
        "phase_transcribing_note": "Transcribing...",
        # Crash-safety net (partial transcript)
        "partial_output_note": "A '*.partial.txt' file is being saved continuously in this folder as a safety net in case the process is interrupted.",
    },
}


# ==========================================================================
# Helpers de configuracao / utilidades puras (testaveis sem GUI)
# ==========================================================================

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
    for p in DEFAULT_WHISPER_PATHS:
        if os.path.exists(p):
            return p
    found = shutil.which("whisper") or shutil.which("whisper.exe")
    return found or DEFAULT_WHISPER_PATHS[0]


def find_ffmpeg(saved_path=None):
    """
    Localiza o ffmpeg sem nunca lancar excecao. Ordem:
    caminho salvo valido -> PATH do sistema -> None.
    A ausencia de ffmpeg NAO impede o app de rodar.
    """
    if saved_path and os.path.exists(saved_path):
        return saved_path
    found = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
    return found  # pode ser None


def subprocess_hidden_window_kwargs():
    """
    Argumentos de Popen/run para esconder a janela de console no Windows SEM
    usar CREATE_NO_WINDOW.

    IMPORTANTE: o Whisper inicia o ffmpeg como processo-filho e le o audio
    decodificado por um pipe. Com CREATE_NO_WINDOW (sem console) e handles
    redirecionados, esse ffmpeg-neto herda handles quebrados e a leitura trava
    (deadlock, 0% de CPU). STARTUPINFO + SW_HIDE esconde a janela sem causar
    isso.
    """
    if os.name != "nt":
        return {"creationflags": 0, "startupinfo": None}
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE
    return {"creationflags": 0, "startupinfo": startupinfo}


def subprocess_child_env():
    """
    Ambiente para o processo-filho (whisper.exe):
    - PYTHONUNBUFFERED=1: saida em tempo real no pipe (sem buffer de ~8 KB).
    - PYTHONIOENCODING=utf-8: forca o Whisper a escrever em UTF-8. No Windows,
      ao imprimir para um pipe, o padrao seria cp1252, gerando mojibake no log
      (ex.: "Ola" -> "Ol?"). Os arquivos .txt/.srt no disco ja sao gravados em
      UTF-8 pelo Whisper; isto so alinha o LOG ao vivo.
    """
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def whisper_cache_dir():
    return os.path.join(str(Path.home()), ".cache", "whisper")


def model_file_name(cli_name):
    if cli_name == "turbo":
        return "large-v3-turbo.pt"
    return f"{cli_name}.pt"


def is_model_downloaded(cli_name, cache_dir=None):
    cache_dir = cache_dir or whisper_cache_dir()
    path = os.path.join(cache_dir, model_file_name(cli_name))
    return os.path.exists(path), path


def models_for_audio_language(audio_lang_key):
    """CLIs validos: variantes .en so quando o audio for Ingles."""
    is_english = (audio_lang_key == "english")
    return [cli for cli in ALL_MODEL_CLIS
            if not (MODEL_INFO[cli]["english_only"] and not is_english)]


def human_size(size_mb):
    return f"{size_mb} MB" if size_mb < 1000 else f"{size_mb / 1000:.1f} GB"


def fmt_hms(seconds):
    """Segundos -> 'H:MM:SS' (com hora) ou 'MM:SS'."""
    if seconds is None or seconds < 0:
        return "--:--"
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


# Timestamp do whisper verbose: aceita MM:SS.mmm e HH:MM:SS.mmm (>= 1h).
# Captura o tempo de INICIO do segmento (primeiro carimbo da linha).
_WHISPER_TIME_RE = re.compile(
    r"\[(\d{1,2}):(\d{2})(?::(\d{2}))?[.,]\d{1,3}\s*-->"
)


def parse_whisper_position_seconds(line):
    """
    Extrai a posicao (em segundos) de uma linha de progresso do whisper.
    Funciona tanto para [MM:SS.mmm --> ...] quanto para [HH:MM:SS.mmm --> ...].
    Retorna int de segundos ou None.
    """
    m = _WHISPER_TIME_RE.search(line)
    if not m:
        return None
    a, b, c = m.group(1), m.group(2), m.group(3)
    if c is not None:  # HH:MM:SS
        return int(a) * 3600 + int(b) * 60 + int(c)
    return int(a) * 60 + int(b)  # MM:SS


_FFMPEG_DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d{2}):(\d{2})\.(\d+)")


def parse_ffmpeg_duration_seconds(text):
    m = _FFMPEG_DURATION_RE.search(text or "")
    if not m:
        return None
    h, mm, ss, frac = m.group(1), m.group(2), m.group(3), m.group(4)
    total = int(h) * 3600 + int(mm) * 60 + int(ss)
    # Arredonda fracao centesimal
    try:
        total += round(float("0." + frac))
    except ValueError:
        pass
    return total


def ffmpeg_probe_duration(ffmpeg_path, media_path, timeout=25):
    """
    Retorna a duracao (segundos) do arquivo via ffmpeg, ou None.
    Nunca lanca excecao; e seguro chamar mesmo sem ffmpeg.
    """
    if not ffmpeg_path or not os.path.exists(media_path):
        return None
    try:
        proc = subprocess.run(
            [ffmpeg_path, "-i", media_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # ffmpeg imprime Duration no stderr
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=subprocess_child_env(),
            **subprocess_hidden_window_kwargs(),
        )
        return parse_ffmpeg_duration_seconds(proc.stdout)
    except Exception:
        return None


def parse_replacements_text(raw):
    """Converte o texto do editor (errado=correto por linha) em lista [find, replace]."""
    replacements = []
    for line in (raw or "").splitlines():
        line = line.strip()
        if not line or "=" not in line:
            continue
        find, _, replace = line.partition("=")
        find = find.strip()
        replace = replace.strip()
        if not find:
            # find vazio corromperia o arquivo (str.replace("", x)). Ignora.
            continue
        replacements.append([find, replace])
    return replacements


# --------------------------------------------------------------------------
# Recorte de intervalo (HH:MM:SS) + deslocamento de timestamps na saida
# --------------------------------------------------------------------------

_HMS_INPUT_RE = re.compile(r"^\s*(?:(\d+):)?(\d{1,2}):(\d{1,2})(?:[.,](\d{1,3}))?\s*$")


def parse_hms_to_seconds(text):
    """
    Converte texto digitado pelo usuario em segundos (float).
    Aceita 'SS', 'MM:SS', 'HH:MM:SS', com ou sem fracao decimal (.mmm).
    Retorna None se o texto estiver vazio ou em formato invalido.
    """
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
    """Formata segundos como 'H:MM:SS' para preencher os campos de entrada."""
    if seconds is None:
        return ""
    seconds = max(0, int(round(seconds)))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}"


def build_ffmpeg_clip_command(ffmpeg_path, src_path, dst_path, start_seconds, end_seconds):
    """
    Monta o comando ffmpeg que recorta [start_seconds, end_seconds) de src_path
    para dst_path, copiando os streams sem reprocessar audio (rapido, nao
    degrada qualidade). -ss ANTES de -i acelera o seek (nao decodifica o
    trecho descartado). Usamos -to (tempo absoluto), nao -t (duracao), para
    evitar erro de calculo de duracao negativa/zero por engano do chamador.
    """
    duration = max(0.0, end_seconds - start_seconds)
    return [
        ffmpeg_path,
        "-y",
        "-ss", f"{start_seconds:.3f}",
        "-i", src_path,
        "-t", f"{duration:.3f}",
        "-c", "copy",
        dst_path,
    ]


def shift_srt_vtt_timestamps(content, offset_seconds, is_vtt=False):
    """
    Soma offset_seconds a cada timestamp de um conteudo SRT ou VTT.
    SRT usa virgula nos milissegundos (00:00:01,500); VTT usa ponto
    (00:00:01.500). Preserva o separador original de cada arquivo.
    """
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
    """
    Whisper TSV: colunas 'start'\t'end'\t'text', tempos em MILISSEGUNDOS
    inteiros. Soma o offset (convertido para ms) nas duas primeiras colunas
    de cada linha de dados; preserva o cabecalho intacto.
    """
    offset_ms = int(round(offset_seconds * 1000))
    lines = content.splitlines(keepends=False)
    if not lines:
        return content
    out = [lines[0]]  # cabecalho: start\tend\ttext
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
    """
    Whisper JSON: chave 'segments' (lista), cada uma com 'start'/'end' (segundos,
    float) e opcionalmente 'words' com 'start'/'end' tambem. Soma o offset em
    todos os pontos encontrados. Retorna o JSON re-serializado (mesmo encoding,
    UTF-8, sem escapar acentos).
    """
    try:
        data = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return content  # nao foi possivel interpretar; deixa intacto

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
    """
    Le path, soma offset_seconds aos timestamps de acordo com o formato, e
    regrava. Formatos sem timestamp (txt) sao ignorados. Nunca lanca excecao
    para fora; falhas de leitura/parsing deixam o arquivo como esta.
    """
    if offset_seconds == 0 or fmt == "txt" or not path or not os.path.exists(path):
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
# Modelo de item da fila
# ==========================================================================

class QueueItem:
    def __init__(self, filepath):
        self.filepath = filepath
        self.filename = os.path.basename(filepath)
        self.status = ST_PENDING
        self.error_message = ""
        self.output_dir = None
        self.output_txt = None
        self.output_srt = None


# Linha de log verbose do Whisper: "[HH:MM:SS.mmm --> HH:MM:SS.mmm] texto" ou
# "[MM:SS.mmm --> MM:SS.mmm] texto" (sem horas, abaixo de 1h). Confirmado
# contra whisper/transcribe.py (format_timestamp, decimal_marker=".").
_WHISPER_SEGMENT_LINE_RE = re.compile(
    r"^\[(\d{1,2}):(\d{2})(?::(\d{2}))?\.\d{1,3}\s*-->\s*"
    r"(\d{1,2}):(\d{2})(?::(\d{2}))?\.\d{1,3}\]\s*(.*)$"
)


def parse_whisper_segment_line(line):
    """
    Extrai (start_seconds, end_seconds, text) de uma linha de segmento verbose
    do whisper, ou None se a linha nao for um segmento (ex.: mensagens como
    'Detecting language...'). Usado pelo escritor de transcricao parcial.
    """
    m = _WHISPER_SEGMENT_LINE_RE.match(line.strip())
    if not m:
        return None
    sh, sm, ss, eh, em, es, text = m.groups()

    def _to_seconds(h, mm, ss):
        if ss is not None:  # HH:MM:SS
            return int(h) * 3600 + int(mm) * 60 + int(ss)
        return int(h) * 60 + int(mm)  # MM:SS

    start = _to_seconds(sh, sm, ss)
    end = _to_seconds(eh, em, es)
    return start, end, text


class PartialTranscriptWriter:
    """
    Grava um '<nome>.partial.txt' incrementalmente, segmento a segmento, a
    medida que o whisper os imprime no log verbose.

    Motivo: o proprio Whisper so escreve seus arquivos finais (.txt/.srt/...)
    quando o processo termina (sucesso OU erro). Numa palestra de 2h, se o
    processo travar, for cancelado, ou o app/computador fechar no meio, NADA
    seria salvo. Este arquivo .partial.txt e independente disso: cada linha
    e gravada e sincronizada em disco assim que aquele trecho e transcrito,
    entao o pior caso e perder so o ultimo segmento (poucos segundos de
    audio), nunca o trabalho inteiro.

    Nao substitui os arquivos finais do Whisper (que continuam sendo gerados
    normalmente ao final); e uma rede de seguranca complementar. E apagado
    automaticamente quando a transcricao termina com sucesso, pois deixa de
    ser necessario uma vez que o .txt definitivo existe.
    """

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
        """Remove o arquivo parcial (chamado quando a transcricao final teve sucesso)."""
        self.close()
        try:
            if os.path.exists(self.path):
                os.remove(self.path)
        except OSError:
            pass


# ==========================================================================
# Worker: download de modelo
# ==========================================================================

class ModelDownloadWorker(threading.Thread):
    """
    Forca o download de um modelo do Whisper rodando-o sobre 1s de silencio.
    O unico efeito colateral e o modelo ir para o cache.
    """

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

            cmd = [
                self.whisper_exe, wav_path,
                "--model", self.model_name,
                "--language", "English",
                "--fp16", "False",
                "--output_dir", tmp_dir,
                "--output_format", "txt",
                "--verbose", "True",
            ]
            self.post("log", text=f"Comando: {' '.join(cmd)}\n\n")

            self.current_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                env=subprocess_child_env(),
                **subprocess_hidden_window_kwargs(),
            )
            for line in self.current_process.stdout:
                if self.stop_flag.is_set():
                    self.current_process.terminate()
                    break
                self.post("log", text=line)
            self.current_process.wait()

            if self.stop_flag.is_set():
                self.post("dl_finished", success=False, error="Cancelado.")
                return
            if self.current_process.returncode != 0:
                self.post("dl_finished", success=False,
                          error=f"whisper saiu com codigo {self.current_process.returncode}.")
                return

            downloaded, _ = is_model_downloaded(self.model_name)
            if downloaded:
                self.post("dl_model_ok")
                self.post("dl_finished", success=True)
            else:
                self.post("dl_finished", success=False,
                          error="O comando terminou mas o modelo nao foi encontrado no cache.")
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


# ==========================================================================
# Worker: transcricao em lote
# ==========================================================================

class TranscriptionWorker(threading.Thread):
    def __init__(self, items, whisper_exe, ffmpeg_path, lang_param, task,
                 model_name, initial_prompt, replacements, keep_formats,
                 output_dir_mode, fixed_output_dir, clip_range, strings,
                 event_queue, stop_flag):
        super().__init__(daemon=True)
        self.items = items
        self.whisper_exe = whisper_exe
        self.ffmpeg_path = ffmpeg_path
        self.lang_param = lang_param            # None = auto
        self.task = task                        # transcribe | translate
        self.model_name = model_name
        self.initial_prompt = initial_prompt
        self.replacements = replacements        # list of (find, replace)
        self.keep_formats = keep_formats        # set of formats to keep
        self.output_dir_mode = output_dir_mode  # same_folder | fixed
        self.fixed_output_dir = fixed_output_dir
        self.clip_range = clip_range            # (start_seconds, end_seconds) or None
        self.s = strings                        # dict de strings localizadas p/ log
        self.event_queue = event_queue
        self.stop_flag = stop_flag
        self.current_process = None

    def post(self, kind, **kwargs):
        self.event_queue.put({"kind": kind, **kwargs})

    def run(self):
        total = len(self.items)
        for idx, item in enumerate(self.items):
            if self.stop_flag.is_set():
                item.status = ST_SKIPPED
                self.post("item_status", index=idx, status=ST_SKIPPED)
                continue

            self.post("item_status", index=idx, status=ST_RUNNING)
            sep = "=" * 70
            self.post("log", text=self.s["log_file_start"].format(
                sep=sep, i=idx + 1, n=total, name=item.filename))

            # --- Probe de duracao (nao bloqueia; tolera ausencia de ffmpeg) ---
            self.post("log", text=self.s["log_probing"])
            full_duration = ffmpeg_probe_duration(self.ffmpeg_path, item.filepath)
            if full_duration:
                self.post("log", text=self.s["log_duration_ok"].format(dur=fmt_hms(full_duration)))
            else:
                self.post("log", text=self.s["log_duration_fail"])

            # Se houver recorte de intervalo, a duracao que importa para a
            # barra/whisper e a do TRECHO, nao do video inteiro.
            offset_seconds = 0.0
            effective_duration = full_duration
            if self.clip_range:
                start_s, end_s = self.clip_range
                if full_duration:
                    end_s = min(end_s, full_duration)
                offset_seconds = start_s
                effective_duration = max(0.0, end_s - start_s)
            self.post("duration", index=idx, seconds=effective_duration)

            try:
                self._transcribe_one(item, idx, offset_seconds)
                if self.stop_flag.is_set():
                    item.status = ST_SKIPPED
                    self.post("item_status", index=idx, status=ST_SKIPPED)
                else:
                    item.status = ST_DONE
                    self.post("item_status", index=idx, status=ST_DONE)
                    self.post("log", text=self.s["log_file_done"].format(name=item.filename))
            except Exception as e:
                item.status = ST_ERROR
                item.error_message = str(e)
                self.post("item_status", index=idx, status=ST_ERROR, error=str(e))
                self.post("log", text=self.s["log_file_error"].format(name=item.filename, e=e))

        self.post("batch_finished")

    def _resolve_output_dir(self, item):
        if self.output_dir_mode == "fixed" and self.fixed_output_dir:
            return self.fixed_output_dir
        return os.path.dirname(item.filepath)

    def _prepare_clip_if_needed(self, item, idx, tmp_dir):
        """
        Se um intervalo foi solicitado, recorta-o com ffmpeg para um arquivo
        temporario e retorna esse caminho. ffmpeg e OBRIGATORIO para este
        recurso especifico (precisamos cortar antes de chamar o whisper);
        sem ffmpeg, levanta um erro claro em vez de transcrever o video
        inteiro por engano. Sem recorte solicitado, retorna o arquivo original.
        """
        if not self.clip_range:
            return item.filepath
        if not (self.ffmpeg_path and os.path.exists(self.ffmpeg_path)):
            raise RuntimeError(
                "Recorte de intervalo solicitado, mas o ffmpeg nao foi encontrado. "
                "Este recurso depende do ffmpeg para cortar o trecho antes de "
                "transcrever. Localize o ffmpeg na aba principal e tente novamente."
            )
        start_s, end_s = self.clip_range
        ext = os.path.splitext(item.filepath)[1] or ".mkv"
        clip_path = os.path.join(tmp_dir, f"clip_{idx}{ext}")
        cmd = build_ffmpeg_clip_command(self.ffmpeg_path, item.filepath, clip_path, start_s, end_s)
        self.post("log", text=self.s["log_cmd"].format(cmd=" ".join(cmd)))
        proc = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            encoding="utf-8", errors="replace", env=subprocess_child_env(),
            **subprocess_hidden_window_kwargs(),
        )
        if proc.returncode != 0 or not os.path.exists(clip_path):
            raise RuntimeError(
                f"Falha ao recortar o intervalo com ffmpeg (codigo {proc.returncode}). "
                f"Saida do ffmpeg:\n{proc.stdout}"
            )
        return clip_path

    def _transcribe_one(self, item, idx, offset_seconds):
        out_dir = self._resolve_output_dir(item)
        os.makedirs(out_dir, exist_ok=True)
        item.output_dir = out_dir

        base = os.path.splitext(os.path.basename(item.filepath))[0]
        partial_path = os.path.join(out_dir, base + ".partial.txt")
        partial = PartialTranscriptWriter(partial_path)
        partial.open()

        import tempfile
        tmp_dir = tempfile.mkdtemp(prefix="whisper_clip_")
        try:
            input_path = self._prepare_clip_if_needed(item, idx, tmp_dir)

            cmd = [
                self.whisper_exe, input_path,
                "--model", self.model_name,
                "--task", self.task,
                "--fp16", "False",
                "--output_dir", out_dir,
                "--output_format", "all",  # gera tudo; removemos depois o nao-marcado
                "--verbose", "True",
            ]
            if self.lang_param:  # None = auto-detect (omitimos --language)
                cmd.extend(["--language", self.lang_param])
            if self.initial_prompt:
                cmd.extend(["--initial_prompt", self.initial_prompt])

            self.post("log", text=self.s["log_cmd"].format(cmd=" ".join(cmd)))
            self.post("phase", index=idx, phase="preparing")

            self.current_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                env=subprocess_child_env(),
                **subprocess_hidden_window_kwargs(),
            )

            saw_first_segment = False
            for line in self.current_process.stdout:
                if self.stop_flag.is_set():
                    self.current_process.terminate()
                    break
                self.post("log", text=line)

                seg = parse_whisper_segment_line(line)
                if seg is not None:
                    if not saw_first_segment:
                        saw_first_segment = True
                        self.post("phase", index=idx, phase="transcribing")
                    seg_start, seg_end, seg_text = seg
                    partial.write_segment(seg_text.strip())
                    self.post("progress_tick", index=idx, seconds=seg_start)

            self.current_process.wait()

            if not self.stop_flag.is_set() and self.current_process.returncode != 0:
                raise RuntimeError(
                    f"whisper saiu com codigo {self.current_process.returncode}. "
                    f"Verifique o caminho do executavel e os logs acima."
                )
            if self.stop_flag.is_set():
                return

            def fpath(ext):
                return os.path.join(out_dir, base + "." + ext)

            # Se usamos um recorte temporario, o whisper nomeou a saida a
            # partir do nome do ARQUIVO TEMPORARIO (ex.: clip_0.txt), nao do
            # arquivo original. Renomeia para o nome esperado (base do video).
            if self.clip_range:
                clip_base = os.path.splitext(os.path.basename(input_path))[0]
                if clip_base != base:
                    for ext in OUTPUT_FORMATS:
                        src = os.path.join(out_dir, clip_base + "." + ext)
                        if os.path.exists(src):
                            dst = fpath(ext)
                            try:
                                if os.path.exists(dst):
                                    os.remove(dst)
                                os.replace(src, dst)
                            except OSError:
                                pass

            # Remove formatos NAO marcados.
            for ext in OUTPUT_FORMATS:
                if ext not in self.keep_formats:
                    p = fpath(ext)
                    if os.path.exists(p):
                        try:
                            os.remove(p)
                        except OSError:
                            pass

            # Desloca os timestamps de volta para a linha do tempo do video
            # original, caso um recorte tenha sido usado. TXT nao tem
            # timestamp e e ignorado pela funcao.
            if self.clip_range and offset_seconds:
                for ext in OUTPUT_FORMATS:
                    if ext in self.keep_formats:
                        shift_output_timestamps(fpath(ext), ext, offset_seconds)

            # Aplica substituicoes nos formatos textuais mantidos (json fica intacto).
            if self.replacements:
                for ext in TEXT_REPLACE_FORMATS:
                    if ext in self.keep_formats:
                        self._apply_replacements(fpath(ext))

            txt_p, srt_p = fpath("txt"), fpath("srt")
            item.output_txt = txt_p if os.path.exists(txt_p) else None
            item.output_srt = srt_p if os.path.exists(srt_p) else None

            # Sucesso: o .partial.txt deixou de ser necessario (o .txt
            # definitivo, completo e ja com dicionario aplicado, existe).
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


# ==========================================================================
# GUI principal
# ==========================================================================

class WhisperTranscriberApp(tk.Tk):
    def __init__(self):
        super().__init__()

        ensure_config_dir()
        self.config_data = load_json(CONFIG_FILE, {})
        self.dictionaries = load_json(DICTIONARIES_FILE, {})

        # Estado nao-widget (sobrevive a reconstrucao da UI)
        self.queue_items = []
        self.event_queue = queue.Queue()
        self.worker = None
        self.stop_flag = threading.Event()
        self.is_running = False

        # Canonico (independe do idioma exibido).
        # Padrao = ingles quando nao ha configuracao salva ainda (1a execucao).
        self.ui_lang = self.config_data.get("ui_lang", "en")
        if self.ui_lang not in ("pt", "en"):
            self.ui_lang = "en"

        # Progresso do arquivo atual
        self._cur_index = -1
        self._cur_total = None       # segundos (ou None)
        self._cur_pos = 0
        self._cur_start = None       # time.monotonic()
        self._cur_phase = None       # None | "preparing" | "transcribing"
        self._pending_duration = None
        self._bar_indeterminate = False
        self._batch_total = 0
        self._batch_done = 0

        self.geometry("1000x880")
        self.minsize(900, 760)

        # Variaveis Tk (criadas uma unica vez; sobrevivem ao rebuild da UI)
        self._init_state_vars()
        self._load_state_from_config()

        # ffmpeg
        self.ffmpeg_path = find_ffmpeg(self.config_data.get("ffmpeg_path"))

        # Constroi a UI pela primeira vez
        self._build_ui()
        self._render_all()

        self.after(150, self._poll_events)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ----------------------------------------------------------- i18n ---

    def t(self, key, **fmt):
        s = TRANSLATIONS[self.ui_lang].get(key, TRANSLATIONS["pt"].get(key, key))
        if fmt:
            try:
                return s.format(**fmt)
            except (KeyError, IndexError):
                return s
        return s

    def _worker_strings(self):
        keys = ["log_file_start", "log_probing", "log_duration_ok",
                "log_duration_fail", "log_cmd", "log_file_done",
                "log_file_error", "log_dict_warn"]
        return {k: self.t(k) for k in keys}

    # -------------------------------------------------- state variables ---

    def _init_state_vars(self):
        self.whisper_path_var = tk.StringVar()
        self.ui_lang_var = tk.StringVar()        # nome nativo exibido
        self.audio_lang_var = tk.StringVar()     # display traduzido
        self.model_var = tk.StringVar()          # display traduzido
        self.task_var = tk.StringVar()           # display traduzido
        self.dict_var = tk.StringVar()           # nome do perfil ou none
        self.model_status_var = tk.StringVar(value="")
        self.ffmpeg_status_var = tk.StringVar(value="")
        self.output_mode_var = tk.StringVar(value="same_folder")
        self.fixed_output_var = tk.StringVar()

        # Selecoes canonicas (independem do idioma)
        self.selected_audio_lang_key = "portuguese"
        self.selected_task_key = "transcribe"
        self.selected_model_cli = "turbo"
        self.selected_dict_name = None  # None = (Nenhum)

        # Formatos de saida (BooleanVar por formato)
        self.format_vars = {fmt: tk.BooleanVar(value=True) for fmt in OUTPUT_FORMATS}

        # Editor de dicionario
        self.dict_name_var = tk.StringVar()
        self._current_dict_name = None

        # Recorte de intervalo (transcrever so um trecho)
        self.clip_enabled_var = tk.BooleanVar(value=False)
        self.clip_start_var = tk.StringVar(value="")
        self.clip_end_var = tk.StringVar(value="")

    def _load_state_from_config(self):
        c = self.config_data
        self.whisper_path_var.set(c.get("whisper_path") or find_default_whisper_path())
        self.output_mode_var.set(c.get("output_mode", "same_folder"))
        self.fixed_output_var.set(c.get("fixed_output_dir", ""))

        # Idioma do audio (migra display antigo se preciso)
        akey = c.get("audio_lang_key")
        if akey not in AUDIO_LANG_PARAM:
            akey = self._migrate_old_audio_lang(c.get("lang"))
        self.selected_audio_lang_key = akey

        # Tarefa
        tkey = c.get("task")
        self.selected_task_key = tkey if tkey in TASK_KEYS else "transcribe"

        # Modelo (migra display antigo se preciso)
        mcli = c.get("model_cli")
        if mcli not in MODEL_INFO:
            mcli = self._migrate_old_model(c.get("model"))
        self.selected_model_cli = mcli

        # Dicionario selecionado
        dsel = c.get("dictionary_name", "__sentinel__")
        if dsel == "__sentinel__":
            old = c.get("dictionary")
            dsel = None if (old in (None, "(Nenhum)", "(None)")) else old
        if dsel is not None and dsel not in self.dictionaries:
            dsel = None
        self.selected_dict_name = dsel

        # Formatos
        fmts = c.get("output_formats")
        if isinstance(fmts, dict):
            for fmt in OUTPUT_FORMATS:
                self.format_vars[fmt].set(bool(fmts.get(fmt, True)))

    @staticmethod
    def _migrate_old_audio_lang(old):
        s = (old or "").lower()
        if "portug" in s:
            return "portuguese"
        if "ingl" in s or "english" in s:
            return "english"
        if "espan" in s or "spanish" in s:
            return "spanish"
        return "portuguese"

    @staticmethod
    def _migrate_old_model(old):
        s = (old or "").lower()
        for cli in sorted(ALL_MODEL_CLIS, key=len, reverse=True):
            if re.search(r"\b" + re.escape(cli) + r"\b", s):
                return cli
        return "turbo"

    # ----------------------------------------------------- mapas i18n ---

    def _audio_lang_display(self, key):
        return self.t("audlang_" + key)

    def _audio_lang_choices(self):
        return [(key, self._audio_lang_display(key)) for key, _ in AUDIO_LANGUAGES]

    def _task_display(self, key):
        return self.t("task_" + key)

    def _model_display(self, cli):
        return f"{cli}  —  {self.t(MODEL_INFO[cli]['desc_key'])}"

    def _dict_none_label(self):
        return self.t("none")

    # ============================================================= UI ===

    def _build_ui(self):
        self._notebook = ttk.Notebook(self)
        self._notebook.pack(fill="both", expand=True, padx=8, pady=8)

        self.tab_main = ttk.Frame(self._notebook)
        self.tab_dict = ttk.Frame(self._notebook)
        self._notebook.add(self.tab_main, text=self.t("tab_transcription"))
        self._notebook.add(self.tab_dict, text=self.t("tab_dictionary"))

        self._dict_wrap_labels = []  # labels que se reembrulham no resize

        self._build_main_tab(self.tab_main)
        self._build_dict_tab(self.tab_dict)

    def _rebuild_ui(self):
        """Reconstroi a UI no idioma atual, preservando o estado."""
        # Preserva conteudo de widgets de texto (nao sao Variables)
        log_content = ""
        try:
            log_content = self.log_text.get("1.0", "end-1c")
        except Exception:
            pass
        prompt_content, repl_content = "", ""
        try:
            prompt_content = self.dict_prompt_text.get("1.0", "end-1c")
            repl_content = self.dict_replacements_text.get("1.0", "end-1c")
        except Exception:
            pass

        self._notebook.destroy()
        self._build_ui()
        self._render_all()

        # Restaura conteudo de texto
        if log_content:
            self.log_text.configure(state="normal")
            self.log_text.insert("1.0", log_content)
            self.log_text.see("end")
            self.log_text.configure(state="disabled")
        self.dict_prompt_text.delete("1.0", "end")
        self.dict_prompt_text.insert("1.0", prompt_content)
        self.dict_replacements_text.delete("1.0", "end")
        self.dict_replacements_text.insert("1.0", repl_content)

    # --- Aba principal -------------------------------------------------

    def _build_main_tab(self, parent):
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(5, weight=1)

        cfg = ttk.LabelFrame(parent, text=self.t("cfg_frame"))
        cfg.grid(row=0, column=0, sticky="ew", padx=4, pady=4)
        cfg.columnconfigure(1, weight=1)
        cfg.columnconfigure(3, weight=1)

        # Linha 0: executavel + idioma da interface
        ttk.Label(cfg, text=self.t("whisper_exe")).grid(row=0, column=0, sticky="w", padx=4, pady=4)
        ttk.Entry(cfg, textvariable=self.whisper_path_var).grid(row=0, column=1, sticky="ew", padx=4, pady=4)
        ttk.Button(cfg, text=self.t("browse"), command=self._browse_whisper_exe).grid(row=0, column=2, padx=4, pady=4)

        ui_box = ttk.Frame(cfg)
        ui_box.grid(row=0, column=3, sticky="e", padx=4, pady=4)
        ttk.Label(ui_box, text=self.t("ui_language")).pack(side="left", padx=(0, 4))
        self.ui_lang_combo = ttk.Combobox(ui_box, textvariable=self.ui_lang_var,
                                           state="readonly", width=12,
                                           values=[name for _, name in UI_LANGUAGES])
        self.ui_lang_combo.pack(side="left")
        self.ui_lang_combo.bind("<<ComboboxSelected>>", self._on_ui_language_changed)

        # Linha 1: idioma do audio + modelo
        ttk.Label(cfg, text=self.t("audio_language")).grid(row=1, column=0, sticky="w", padx=4, pady=4)
        self.audio_lang_combo = ttk.Combobox(cfg, textvariable=self.audio_lang_var, state="readonly", width=26)
        self.audio_lang_combo.grid(row=1, column=1, sticky="w", padx=4, pady=4)
        self.audio_lang_combo.bind("<<ComboboxSelected>>", self._on_audio_language_changed)

        ttk.Label(cfg, text=self.t("ai_model")).grid(row=1, column=2, sticky="e", padx=4, pady=4)
        self.model_combo = ttk.Combobox(cfg, textvariable=self.model_var, state="readonly", width=40)
        self.model_combo.grid(row=1, column=3, sticky="ew", padx=4, pady=4)
        self.model_combo.bind("<<ComboboxSelected>>", self._on_model_changed)

        # Linha 2: tarefa + dicionario
        ttk.Label(cfg, text=self.t("task")).grid(row=2, column=0, sticky="w", padx=4, pady=4)
        self.task_combo = ttk.Combobox(cfg, textvariable=self.task_var, state="readonly", width=26,
                                        values=[self._task_display(k) for k in TASK_KEYS])
        self.task_combo.grid(row=2, column=1, sticky="w", padx=4, pady=4)
        self.task_combo.bind("<<ComboboxSelected>>", self._on_task_changed)

        ttk.Label(cfg, text=self.t("vocab_dict")).grid(row=2, column=2, sticky="e", padx=4, pady=4)
        self.dict_combo = ttk.Combobox(cfg, textvariable=self.dict_var, state="readonly", width=40)
        self.dict_combo.grid(row=2, column=3, sticky="ew", padx=4, pady=4)
        self.dict_combo.bind("<<ComboboxSelected>>", self._on_dict_combo_changed)

        # Linha 3: status do modelo + botao
        msr = ttk.Frame(cfg)
        msr.grid(row=3, column=0, columnspan=4, sticky="ew", padx=4, pady=(0, 4))
        ttk.Label(msr, text=self.t("model_status")).pack(side="left")
        ttk.Label(msr, textvariable=self.model_status_var).pack(side="left", padx=(6, 12))
        self.check_model_btn = ttk.Button(msr, text=self.t("check_download_model"),
                                          command=self._check_or_download_model)
        self.check_model_btn.pack(side="left")

        # Linha 4: status do ffmpeg
        fsr = ttk.Frame(cfg)
        fsr.grid(row=4, column=0, columnspan=4, sticky="ew", padx=4, pady=(0, 4))
        ttk.Label(fsr, text=self.t("ffmpeg_label")).pack(side="left")
        ttk.Label(fsr, textvariable=self.ffmpeg_status_var).pack(side="left", padx=(6, 12))
        self.ffmpeg_openfolder_btn = ttk.Button(fsr, text=self.t("ffmpeg_open_folder"),
                                                 command=self._open_ffmpeg_folder)
        self.ffmpeg_locate_btn = ttk.Button(fsr, text=self.t("ffmpeg_locate"), command=self._locate_ffmpeg)
        self.ffmpeg_download_btn = ttk.Button(fsr, text=self.t("ffmpeg_download"),
                                              command=lambda: webbrowser.open(FFMPEG_DOWNLOAD_URL))
        self.ffmpeg_openfolder_btn.pack(side="left", padx=2)
        self.ffmpeg_locate_btn.pack(side="left", padx=2)
        self.ffmpeg_download_btn.pack(side="left", padx=2)

        # Linha 5: pasta de saida
        ttk.Label(cfg, text=self.t("output_folder")).grid(row=5, column=0, sticky="w", padx=4, pady=4)
        out_frame = ttk.Frame(cfg)
        out_frame.grid(row=5, column=1, columnspan=3, sticky="ew", padx=4, pady=4)
        ttk.Radiobutton(out_frame, text=self.t("same_folder"), variable=self.output_mode_var,
                        value="same_folder", command=self._toggle_output_dir).pack(side="left")
        ttk.Radiobutton(out_frame, text=self.t("fixed_folder"), variable=self.output_mode_var,
                        value="fixed", command=self._toggle_output_dir).pack(side="left", padx=(12, 4))
        self.fixed_output_entry = ttk.Entry(out_frame, textvariable=self.fixed_output_var, state="disabled", width=40)
        self.fixed_output_entry.pack(side="left", padx=4)
        self.fixed_output_btn = ttk.Button(out_frame, text=self.t("browse"),
                                           command=self._browse_output_dir, state="disabled")
        self.fixed_output_btn.pack(side="left")

        # --- Formatos de saida ---
        fmt_frame = ttk.LabelFrame(parent, text=self.t("output_formats"))
        fmt_frame.grid(row=1, column=0, sticky="ew", padx=4, pady=4)
        fmt_frame.columnconfigure(0, weight=1)
        for i, fmt in enumerate(OUTPUT_FORMATS):
            ttk.Checkbutton(fmt_frame, text=self.t("fmt_" + fmt),
                            variable=self.format_vars[fmt]).grid(row=i, column=0, sticky="w", padx=8, pady=1)

        # --- Recorte de intervalo (transcrever so um trecho) ---
        clip_frame = ttk.LabelFrame(parent, text=self.t("clip_frame"))
        clip_frame.grid(row=2, column=0, sticky="ew", padx=4, pady=4)
        clip_frame.columnconfigure(0, weight=1)

        self.clip_enable_chk = ttk.Checkbutton(
            clip_frame, text=self.t("clip_enable"), variable=self.clip_enabled_var,
            command=self._on_clip_enabled_toggle)
        self.clip_enable_chk.grid(row=0, column=0, sticky="w", padx=8, pady=(6, 2), columnspan=4)

        ttk.Label(clip_frame, text=self.t("clip_start")).grid(row=1, column=0, sticky="e", padx=(8, 2), pady=2)
        self.clip_start_entry = ttk.Entry(clip_frame, textvariable=self.clip_start_var, width=12)
        self.clip_start_entry.grid(row=1, column=1, sticky="w", padx=(0, 16), pady=2)
        ttk.Label(clip_frame, text=self.t("clip_end")).grid(row=1, column=2, sticky="e", padx=(8, 2), pady=2)
        self.clip_end_entry = ttk.Entry(clip_frame, textvariable=self.clip_end_var, width=12)
        self.clip_end_entry.grid(row=1, column=3, sticky="w", padx=(0, 8), pady=2)

        clip_hint = ttk.Label(clip_frame, text=self.t("clip_hint"), justify="left", foreground="#555555")
        clip_hint.grid(row=2, column=0, columnspan=4, sticky="ew", padx=8, pady=(0, 2))
        self._clip_wrap_labels = [clip_hint]

        self.clip_ffmpeg_warn = ttk.Label(clip_frame, text=self.t("clip_needs_ffmpeg"),
                                          justify="left", foreground="#a33")
        self.clip_ffmpeg_warn.grid(row=3, column=0, columnspan=4, sticky="ew", padx=8, pady=(0, 6))
        self._clip_wrap_labels.append(self.clip_ffmpeg_warn)
        clip_frame.bind("<Configure>", self._on_clip_frame_configure)

        # --- Fila de arquivos ---
        qf = ttk.LabelFrame(parent, text=self.t("queue_frame"))
        qf.grid(row=3, column=0, sticky="ew", padx=4, pady=4)

        br = ttk.Frame(qf)
        br.pack(fill="x", padx=4, pady=4)
        ttk.Button(br, text=self.t("add_files"), command=self._add_files).pack(side="left", padx=2)
        ttk.Button(br, text=self.t("remove_selected"), command=self._remove_selected).pack(side="left", padx=2)
        ttk.Button(br, text=self.t("clear_queue"), command=self._clear_queue).pack(side="left", padx=2)
        ttk.Button(br, text=self.t("move_up"), command=lambda: self._move_selected(-1)).pack(side="left", padx=(20, 2))
        ttk.Button(br, text=self.t("move_down"), command=lambda: self._move_selected(1)).pack(side="left", padx=2)

        columns = ("ordem", "arquivo", "pasta", "status")
        self.tree = ttk.Treeview(qf, columns=columns, show="headings", height=8, selectmode="extended")
        self.tree.heading("ordem", text=self.t("col_order"))
        self.tree.heading("arquivo", text=self.t("col_file"))
        self.tree.heading("pasta", text=self.t("col_folder"))
        self.tree.heading("status", text=self.t("col_status"))
        self.tree.column("ordem", width=36, anchor="center")
        self.tree.column("arquivo", width=300)
        self.tree.column("pasta", width=320)
        self.tree.column("status", width=140, anchor="center")
        self.tree.pack(fill="x", padx=4, pady=(0, 4))
        self.tree.bind("<Double-1>", self._on_tree_double_click)

        # --- Controles de execucao ---
        rf = ttk.Frame(parent)
        rf.grid(row=4, column=0, sticky="ew", padx=4, pady=4)
        self.start_btn = ttk.Button(rf, text=self.t("start_batch"), command=self._start_batch)
        self.start_btn.pack(side="left", padx=4)
        self.cancel_btn = ttk.Button(rf, text=self.t("cancel"), command=self._cancel_batch, state="disabled")
        self.cancel_btn.pack(side="left", padx=4)
        self.open_out_btn = ttk.Button(rf, text=self.t("open_output_folder"),
                                       command=self._open_last_output_folder, state="disabled")
        self.open_out_btn.pack(side="left", padx=4)

        self.file_progress = ttk.Progressbar(rf, mode="determinate", length=260, maximum=1, value=0)
        self.file_progress.pack(side="left", padx=12)
        self.status_label = ttk.Label(rf, text=self.t("waiting_start"))
        self.status_label.pack(side="left", padx=4)

        # --- Log ---
        lf = ttk.LabelFrame(parent, text=self.t("log_frame"))
        lf.grid(row=5, column=0, sticky="nsew", padx=4, pady=4)
        lf.columnconfigure(0, weight=1)
        lf.rowconfigure(0, weight=1)
        self.log_text = tk.Text(lf, wrap="word", state="disabled", bg="#0d1117", fg="#c9d1d9",
                                insertbackground="#c9d1d9", font=("Consolas", 9))
        ls = ttk.Scrollbar(lf, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=ls.set)
        self.log_text.grid(row=0, column=0, sticky="nsew")
        ls.grid(row=0, column=1, sticky="ns")

    # --- Aba de dicionarios (redesenhada) ------------------------------

    def _build_dict_tab(self, parent):
        parent.columnconfigure(0, weight=0, minsize=220)
        parent.columnconfigure(1, weight=1)
        parent.rowconfigure(1, weight=1)

        ttk.Label(parent, text=self.t("saved_profiles")).grid(row=0, column=0, sticky="w", padx=8, pady=(8, 2))

        list_frame = ttk.Frame(parent)
        list_frame.grid(row=1, column=0, sticky="nsew", padx=8, pady=4)
        list_frame.rowconfigure(0, weight=1)
        list_frame.columnconfigure(0, weight=1)
        self.dict_listbox = tk.Listbox(list_frame, exportselection=False, width=24)
        self.dict_listbox.grid(row=0, column=0, sticky="nsew")
        lscroll = ttk.Scrollbar(list_frame, command=self.dict_listbox.yview)
        self.dict_listbox.configure(yscrollcommand=lscroll.set)
        lscroll.grid(row=0, column=1, sticky="ns")
        self.dict_listbox.bind("<<ListboxSelect>>", self._on_dict_select)  # (bug antigo: nao era ligado)

        btns = ttk.Frame(parent)
        btns.grid(row=2, column=0, sticky="ew", padx=8, pady=4)
        btns.columnconfigure((0, 1, 2), weight=1)
        ttk.Button(btns, text=self.t("new"), command=self._new_dictionary).grid(row=0, column=0, sticky="ew", padx=2)
        ttk.Button(btns, text=self.t("duplicate"), command=self._duplicate_dictionary).grid(row=0, column=1, sticky="ew", padx=2)
        ttk.Button(btns, text=self.t("delete"), command=self._delete_dictionary).grid(row=0, column=2, sticky="ew", padx=2)

        edit = ttk.LabelFrame(parent, text=self.t("edit_profile"))
        edit.grid(row=0, column=1, rowspan=3, sticky="nsew", padx=8, pady=8)
        edit.columnconfigure(0, weight=1)
        # As duas caixas de texto (linhas 3 e 6) recebem o peso para crescer
        edit.rowconfigure(3, weight=1)
        edit.rowconfigure(6, weight=1)

        ttk.Label(edit, text=self.t("profile_name")).grid(row=0, column=0, sticky="w", padx=8, pady=(8, 0))
        ttk.Entry(edit, textvariable=self.dict_name_var).grid(row=1, column=0, sticky="ew", padx=8, pady=2)

        help1 = ttk.Label(edit, text=self.t("priming_help"), justify="left")
        help1.grid(row=2, column=0, sticky="ew", padx=8, pady=(10, 2))
        self._dict_wrap_labels.append(help1)
        self.dict_prompt_text = tk.Text(edit, height=5, wrap="word")
        self.dict_prompt_text.grid(row=3, column=0, sticky="nsew", padx=8, pady=(0, 4))

        help2 = ttk.Label(edit, text=self.t("replacements_help"), justify="left")
        help2.grid(row=4, column=0, sticky="ew", padx=8, pady=(10, 2))
        self._dict_wrap_labels.append(help2)
        ttk.Frame(edit, height=2).grid(row=5, column=0)  # espacador minimo
        self.dict_replacements_text = tk.Text(edit, height=8, wrap="word")
        self.dict_replacements_text.grid(row=6, column=0, sticky="nsew", padx=8, pady=(0, 4))

        sr = ttk.Frame(edit)
        sr.grid(row=7, column=0, sticky="ew", padx=8, pady=8)
        ttk.Button(sr, text=self.t("save_profile"), command=self._save_current_dictionary).pack(side="left")

        # Reembrulha os textos de ajuda conforme a largura disponivel
        edit.bind("<Configure>", self._on_edit_frame_configure)

    def _on_edit_frame_configure(self, event):
        wrap = max(220, event.width - 28)
        for lbl in getattr(self, "_dict_wrap_labels", []):
            try:
                lbl.configure(wraplength=wrap)
            except Exception:
                pass

    def _on_clip_frame_configure(self, event):
        wrap = max(260, event.width - 20)
        for lbl in getattr(self, "_clip_wrap_labels", []):
            try:
                lbl.configure(wraplength=wrap)
            except Exception:
                pass

    # ===================================================== render/refresh ===

    def _render_all(self):
        """Sincroniza todos os widgets a partir do estado canonico/idioma atual."""
        # idioma interface
        native = dict(UI_LANGUAGES).get(self.ui_lang, "Português")
        self.ui_lang_var.set(native)
        # idioma audio
        self.audio_lang_combo.configure(values=[d for _, d in self._audio_lang_choices()])
        self.audio_lang_var.set(self._audio_lang_display(self.selected_audio_lang_key))
        # tarefa
        self.task_combo.configure(values=[self._task_display(k) for k in TASK_KEYS])
        self.task_var.set(self._task_display(self.selected_task_key))
        # modelos
        self._render_model_combo()
        # dicionarios
        self._refresh_dict_combo()
        self._refresh_dict_listbox()
        # ffmpeg + saida + fila
        self._refresh_ffmpeg_status()
        self._refresh_clip_availability()
        self._toggle_output_dir()
        self._refresh_tree()
        self._update_status_label()
        self._set_running_ui_state(self.is_running)

    def _render_model_combo(self):
        clis = models_for_audio_language(self.selected_audio_lang_key)
        if self.selected_model_cli not in clis:
            self.selected_model_cli = "turbo" if "turbo" in clis else clis[0]
        self._model_display_to_cli = {self._model_display(c): c for c in clis}
        self.model_combo.configure(values=list(self._model_display_to_cli.keys()))
        self.model_var.set(self._model_display(self.selected_model_cli))
        self._update_model_status()

    def _refresh_dict_combo(self):
        none_label = self._dict_none_label()
        names = [none_label] + sorted(self.dictionaries.keys())
        self.dict_combo.configure(values=names)
        if self.selected_dict_name and self.selected_dict_name in self.dictionaries:
            self.dict_var.set(self.selected_dict_name)
        else:
            self.selected_dict_name = None
            self.dict_var.set(none_label)

    def _refresh_dict_listbox(self):
        self.dict_listbox.delete(0, "end")
        for name in sorted(self.dictionaries.keys()):
            self.dict_listbox.insert("end", name)

    def _refresh_ffmpeg_status(self):
        if self.ffmpeg_path and os.path.exists(self.ffmpeg_path):
            self.ffmpeg_status_var.set(self.t("ffmpeg_found") + f"  ({self.ffmpeg_path})")
            self.ffmpeg_openfolder_btn.configure(state="normal")
        else:
            self.ffmpeg_status_var.set(self.t("ffmpeg_not_found"))
            self.ffmpeg_openfolder_btn.configure(state="disabled")

    def _refresh_tree(self):
        self.tree.delete(*self.tree.get_children())
        for idx, item in enumerate(self.queue_items, 1):
            self.tree.insert("", "end", values=(
                idx, item.filename, os.path.dirname(item.filepath),
                self.t("status_" + item.status)))

    # ----------------------------------------------- handlers: idioma ---

    def _on_ui_language_changed(self, event=None):
        chosen_native = self.ui_lang_var.get()
        new_lang = next((code for code, name in UI_LANGUAGES if name == chosen_native), self.ui_lang)
        if new_lang == self.ui_lang:
            return
        if self.is_running:
            # Bloqueado durante a transcricao: reverte a selecao e avisa.
            self.ui_lang_var.set(dict(UI_LANGUAGES).get(self.ui_lang))
            messagebox.showwarning(self.t("warn"), self.t("warn_lang_locked"))
            return
        self.ui_lang = new_lang
        self._rebuild_ui()

    def _on_audio_language_changed(self, event=None):
        disp = self.audio_lang_var.get()
        key = next((k for k, d in self._audio_lang_choices() if d == disp), self.selected_audio_lang_key)
        self.selected_audio_lang_key = key
        self._render_model_combo()

    def _on_task_changed(self, event=None):
        disp = self.task_var.get()
        self.selected_task_key = next((k for k in TASK_KEYS if self._task_display(k) == disp),
                                      self.selected_task_key)

    def _on_model_changed(self, event=None):
        disp = self.model_var.get()
        cli = getattr(self, "_model_display_to_cli", {}).get(disp)
        if cli:
            self.selected_model_cli = cli
        self._update_model_status()

    def _on_dict_combo_changed(self, event=None):
        disp = self.dict_var.get()
        if disp == self._dict_none_label():
            self.selected_dict_name = None
        elif disp in self.dictionaries:
            self.selected_dict_name = disp

    # ----------------------------------------------- handlers: ffmpeg ---

    def _open_ffmpeg_folder(self):
        if not (self.ffmpeg_path and os.path.exists(self.ffmpeg_path)):
            return
        folder = os.path.dirname(self.ffmpeg_path)
        self._open_folder(folder)

    def _locate_ffmpeg(self):
        ftypes = [(self.t("executable"), "*.exe"), (self.t("all_files"), "*.*")] if os.name == "nt" \
            else [(self.t("all_files"), "*.*")]
        path = filedialog.askopenfilename(title=self.t("select_ffmpeg_title"), filetypes=ftypes)
        if path:
            self.ffmpeg_path = path
            self.config_data["ffmpeg_path"] = path
            save_json(CONFIG_FILE, self.config_data)
            self._refresh_ffmpeg_status()
            self._refresh_clip_availability()

    def _open_folder(self, folder):
        try:
            if os.name == "nt":
                os.startfile(folder)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", folder])
            else:
                subprocess.Popen(["xdg-open", folder])
        except Exception:
            pass

    # ----------------------------------------------- handlers: gerais ---

    def _browse_whisper_exe(self):
        ftypes = [(self.t("executable"), "*.exe"), (self.t("all_files"), "*.*")] if os.name == "nt" \
            else [(self.t("all_files"), "*.*")]
        path = filedialog.askopenfilename(title=self.t("select_whisper_title"), filetypes=ftypes)
        if path:
            self.whisper_path_var.set(path)

    def _update_model_status(self):
        cli = self.selected_model_cli
        info = MODEL_INFO.get(cli)
        if not info:
            self.model_status_var.set("")
            return
        downloaded, _ = is_model_downloaded(cli)
        size_txt = human_size(info["size_mb"])
        key = "model_downloaded" if downloaded else "model_not_downloaded"
        self.model_status_var.set(self.t(key, size=size_txt, vram=info["vram_gb"]))

    def _check_or_download_model(self):
        cli = self.selected_model_cli
        downloaded, path = is_model_downloaded(cli)
        if downloaded:
            messagebox.showinfo(self.t("model_available_title"),
                                self.t("model_available_msg", model=cli, path=path))
            return
        whisper_path = self.whisper_path_var.get().strip()
        if not whisper_path:
            messagebox.showerror(self.t("error"), self.t("err_no_whisper"))
            return
        info = MODEL_INFO[cli]
        size_txt = human_size(info["size_mb"])
        if not messagebox.askyesno(self.t("download_model_title"),
                                   self.t("download_model_msg", model=cli, size=size_txt,
                                          dest=whisper_cache_dir())):
            return

        self.check_model_btn.configure(state="disabled")
        self.model_status_var.set(self.t("downloading_status"))
        self._clear_log()
        self._log(self.t("log_download_start", model=cli, size=size_txt))
        self._log(self.t("log_download_dest", dest=whisper_cache_dir()))

        dq = queue.Queue()
        ds = threading.Event()
        downloader = ModelDownloadWorker(whisper_path, cli, dq, ds)
        downloader.start()
        self._poll_download_events(downloader, dq)

    def _poll_download_events(self, downloader, event_queue):
        try:
            while True:
                evt = event_queue.get_nowait()
                kind = evt["kind"]
                if kind == "log":
                    self._log(evt["text"])
                elif kind == "dl_model_ok":
                    self._log(self.t("log_model_ok"))
                elif kind == "dl_finished":
                    self.check_model_btn.configure(state="normal")
                    self._update_model_status()
                    if evt.get("success"):
                        messagebox.showinfo(self.t("download_done_title"), self.t("download_done_msg"))
                    else:
                        messagebox.showerror(self.t("download_error_title"),
                                             self.t("download_error_msg", error=evt.get("error", "")))
                    return
        except queue.Empty:
            pass
        self.after(150, lambda: self._poll_download_events(downloader, event_queue))

    def _toggle_output_dir(self):
        if self.output_mode_var.get() == "fixed":
            self.fixed_output_entry.configure(state="normal")
            self.fixed_output_btn.configure(state="normal")
        else:
            self.fixed_output_entry.configure(state="disabled")
            self.fixed_output_btn.configure(state="disabled")

    # --- Recorte de intervalo (transcrever so um trecho) ---

    def _ffmpeg_available(self):
        return bool(self.ffmpeg_path and os.path.exists(self.ffmpeg_path))

    def _refresh_clip_availability(self):
        """
        Habilita/desabilita a caixa de recorte conforme a disponibilidade do
        ffmpeg (este recurso especifico depende dele para cortar o trecho).
        Se o ffmpeg desaparecer enquanto a opcao estava marcada, desmarca-a
        para evitar iniciar um lote que vai falhar de forma confusa.
        """
        available = self._ffmpeg_available()
        if not available and self.clip_enabled_var.get():
            self.clip_enabled_var.set(False)
        self.clip_enable_chk.configure(state="normal" if available else "disabled")
        self.clip_ffmpeg_warn.grid() if not available else self.clip_ffmpeg_warn.grid_remove()
        self._on_clip_enabled_toggle()

    def _on_clip_enabled_toggle(self):
        on = self.clip_enabled_var.get() and self._ffmpeg_available()
        state = "normal" if on else "disabled"
        self.clip_start_entry.configure(state=state)
        self.clip_end_entry.configure(state=state)

    def _get_validated_clip_range(self):
        """
        Le e valida os campos de inicio/fim do recorte.
        Retorna (start_seconds, end_seconds) ou None se a opcao nao estiver
        marcada. Retorna False (sentinela) se marcada mas invalida.
        """
        if not self.clip_enabled_var.get():
            return None
        start = parse_hms_to_seconds(self.clip_start_var.get())
        end = parse_hms_to_seconds(self.clip_end_var.get())
        if start is None or end is None or end <= start:
            return False
        return (start, end)

    def _browse_output_dir(self):
        path = filedialog.askdirectory(title=self.t("select_output_title"))
        if path:
            self.fixed_output_var.set(path)

    def _add_files(self):
        paths = filedialog.askopenfilenames(
            title=self.t("select_media_title"),
            filetypes=[
                (self.t("media_files"), " ".join("*" + e for e in MEDIA_EXTENSIONS)),
                (self.t("all_files"), "*.*"),
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
            messagebox.showinfo(self.t("warn"), self.t("info_all_in_queue"))

    def _selected_indices(self):
        return sorted(self.tree.index(s) for s in self.tree.selection())

    def _remove_selected(self):
        if self.is_running:
            messagebox.showwarning(self.t("warn"), self.t("warn_queue_locked"))
            return
        for i in reversed(self._selected_indices()):
            del self.queue_items[i]
        self._refresh_tree()

    def _clear_queue(self):
        if self.is_running:
            messagebox.showwarning(self.t("warn"), self.t("warn_queue_locked"))
            return
        self.queue_items.clear()
        self._refresh_tree()

    def _move_selected(self, direction):
        if self.is_running:
            return
        indices = self._selected_indices()
        if not indices:
            return
        order = indices if direction < 0 else list(reversed(indices))
        for i in order:
            j = i + direction
            if 0 <= j < len(self.queue_items):
                self.queue_items[i], self.queue_items[j] = self.queue_items[j], self.queue_items[i]
        self._refresh_tree()
        new_indices = [min(max(i + direction, 0), len(self.queue_items) - 1) for i in indices]
        children = self.tree.get_children()
        if children:
            self.tree.selection_set([children[i] for i in new_indices])

    def _on_tree_double_click(self, event):
        sel = self._selected_indices()
        if not sel:
            return
        item = self.queue_items[sel[0]]
        folder = item.output_dir or os.path.dirname(item.filepath)
        if folder and os.path.isdir(folder):
            self._open_folder(folder)

    # --- Dicionario: handlers ---

    def _on_dict_select(self, event=None):
        sel = self.dict_listbox.curselection()
        if not sel:
            return
        self._load_dictionary_into_editor(self.dict_listbox.get(sel[0]))

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
            messagebox.showinfo(self.t("warn"), self.t("select_to_duplicate"))
            return
        name = self.dict_listbox.get(sel[0])
        new_name = simpledialog.askstring(self.t("dup_title"), self.t("dup_prompt"),
                                          initialvalue=name + self.t("dup_suffix"))
        if not new_name:
            return
        if new_name in self.dictionaries:
            messagebox.showerror(self.t("error"), self.t("err_dup_exists"))
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
        if messagebox.askyesno(self.t("confirm"), self.t("delete_question", name=name)):
            self.dictionaries.pop(name, None)
            if self.selected_dict_name == name:
                self.selected_dict_name = None
            save_json(DICTIONARIES_FILE, self.dictionaries)
            self._refresh_dict_listbox()
            self._refresh_dict_combo()
            self._new_dictionary()

    def _save_current_dictionary(self):
        name = self.dict_name_var.get().strip()
        if not name:
            messagebox.showerror(self.t("error"), self.t("err_no_profile_name"))
            return
        prompt = self.dict_prompt_text.get("1.0", "end").strip()
        replacements = parse_replacements_text(self.dict_replacements_text.get("1.0", "end"))
        if self._current_dict_name and self._current_dict_name != name:
            self.dictionaries.pop(self._current_dict_name, None)
        self.dictionaries[name] = {"prompt": prompt, "replacements": replacements}
        save_json(DICTIONARIES_FILE, self.dictionaries)
        self._current_dict_name = name
        self.selected_dict_name = name
        self._refresh_dict_listbox()
        self._refresh_dict_combo()
        self.dict_var.set(name)
        messagebox.showinfo(self.t("saved"), self.t("profile_saved_msg", name=name))

    # ----------------------------------------------------- execucao ---

    def _validate_before_start(self):
        if not self.queue_items:
            messagebox.showerror(self.t("error"), self.t("err_no_files"))
            return False
        whisper_path = self.whisper_path_var.get().strip()
        if not whisper_path:
            messagebox.showerror(self.t("error"), self.t("err_no_whisper"))
            return False
        if whisper_path not in ("whisper", "whisper.exe") and not os.path.exists(whisper_path):
            if not messagebox.askyesno(self.t("warn"), self.t("warn_path_not_found", path=whisper_path)):
                return False
        if not any(self.format_vars[f].get() for f in OUTPUT_FORMATS):
            messagebox.showerror(self.t("error"), self.t("err_no_format"))
            return False
        if self.output_mode_var.get() == "fixed" and not self.fixed_output_var.get().strip():
            messagebox.showerror(self.t("error"), self.t("err_no_fixed_dir"))
            return False
        # ffmpeg ausente: avisa mas NAO bloqueia (exceto se o recorte de
        # intervalo estiver marcado, que DEPENDE do ffmpeg).
        if self.clip_enabled_var.get() and not self._ffmpeg_available():
            messagebox.showerror(self.t("error"), self.t("err_clip_needs_ffmpeg"))
            return False
        if not (self.ffmpeg_path and os.path.exists(self.ffmpeg_path)):
            if not messagebox.askyesno(self.t("warn"), self.t("ffmpeg_missing_warn")):
                return False
        clip = self._get_validated_clip_range()
        if clip is False:
            messagebox.showerror(self.t("error"), self.t("err_clip_invalid"))
            return False
        return True

    def _start_batch(self):
        if self.is_running or not self._validate_before_start():
            return

        self._save_current_settings()

        for item in self.queue_items:
            item.status = ST_PENDING
            item.error_message = ""
        self._refresh_tree()

        lang_param = AUDIO_LANG_PARAM[self.selected_audio_lang_key]
        model_name = self.selected_model_cli
        task = self.selected_task_key

        prompt, replacements = "", []
        if self.selected_dict_name and self.selected_dict_name in self.dictionaries:
            d = self.dictionaries[self.selected_dict_name]
            prompt = d.get("prompt", "")
            replacements = [tuple(p) for p in d.get("replacements", [])]

        keep_formats = {f for f in OUTPUT_FORMATS if self.format_vars[f].get()}
        clip_range = self._get_validated_clip_range() or None  # False/None -> None (validated already)

        self.stop_flag = threading.Event()
        self.event_queue = queue.Queue()
        self.worker = TranscriptionWorker(
            items=self.queue_items,
            whisper_exe=self.whisper_path_var.get().strip(),
            ffmpeg_path=self.ffmpeg_path,
            lang_param=lang_param,
            task=task,
            model_name=model_name,
            initial_prompt=prompt,
            replacements=replacements,
            keep_formats=keep_formats,
            output_dir_mode=self.output_mode_var.get(),
            fixed_output_dir=self.fixed_output_var.get().strip(),
            clip_range=clip_range,
            strings=self._worker_strings(),
            event_queue=self.event_queue,
            stop_flag=self.stop_flag,
        )

        self.is_running = True
        self._batch_total = len(self.queue_items)
        self._batch_done = 0
        self._cur_index = -1
        self._set_running_ui_state(True)
        self._reset_file_progress()
        self._update_status_label()
        self._clear_log()
        self._log(self.t("log_batch_start", time=datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

        self.worker.start()
        self.after(150, self._poll_events)

    def _set_running_ui_state(self, running):
        self.start_btn.configure(state="disabled" if running else "normal")
        self.cancel_btn.configure(state="normal" if running else "disabled")
        # Trava a troca de idioma da interface durante a execucao
        self.ui_lang_combo.configure(state="disabled" if running else "readonly")
        # Botao "abrir pasta" habilita quando ha algo concluido
        any_done = any(i.status == ST_DONE for i in self.queue_items)
        self.open_out_btn.configure(state="normal" if (any_done and not running) else
                                    ("normal" if any_done else "disabled"))

    def _cancel_batch(self):
        if self.worker and self.is_running:
            if messagebox.askyesno(self.t("cancel_title"), self.t("cancel_question")):
                self._do_cancel()

    def _cancel_batch_for_test(self):
        if self.worker and self.is_running:
            self._do_cancel()

    def _do_cancel(self):
        self._log(self.t("log_canceling"))
        self.worker.cancel()
        self.cancel_btn.configure(state="disabled")

    def _on_batch_finished(self):
        self.is_running = False
        self._stop_indeterminate()
        self._set_running_ui_state(False)
        done = sum(1 for i in self.queue_items if i.status == ST_DONE)
        errors = sum(1 for i in self.queue_items if i.status == ST_ERROR)
        self.status_label.configure(text=self.t("batch_finished_label", done=done, errors=errors))
        self._log(self.t("log_batch_end", time=datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        self.open_out_btn.configure(state="normal" if done else "disabled")
        if errors:
            messagebox.showwarning(self.t("finished_with_errors_title"),
                                   self.t("finished_with_errors_msg", done=done, errors=errors))
        else:
            messagebox.showinfo(self.t("finished_title"), self.t("finished_msg", done=done))

    def _open_last_output_folder(self):
        folder = None
        for item in self.queue_items:
            if item.status == ST_DONE and (item.output_dir or item.filepath):
                folder = item.output_dir or os.path.dirname(item.filepath)
        if folder and os.path.isdir(folder):
            self._open_folder(folder)

    # ----------------------------------------- progresso (barra/label) ---

    def _reset_file_progress(self):
        self._stop_indeterminate()
        self._cur_total = None
        self._cur_pos = 0
        self._cur_phase = None  # None | "preparing" | "transcribing"
        self.file_progress.configure(mode="determinate", maximum=1, value=0)

    def _stop_indeterminate(self):
        if self._bar_indeterminate:
            try:
                self.file_progress.stop()
            except Exception:
                pass
            self._bar_indeterminate = False

    def _set_bar_determinate(self, total_seconds):
        self._stop_indeterminate()
        self._cur_total = total_seconds
        self.file_progress.configure(mode="determinate", maximum=max(total_seconds, 1), value=0)

    def _set_bar_indeterminate(self):
        self._cur_total = None
        self.file_progress.configure(mode="indeterminate")
        if not self._bar_indeterminate:
            try:
                self.file_progress.start(60)
            except Exception:
                pass
            self._bar_indeterminate = True

    def _update_status_label(self):
        if not self.is_running:
            if self._batch_total == 0:
                self.status_label.configure(text=self.t("waiting_start"))
            return
        parts = [self.t("batch_progress", done=self._batch_done, total=self._batch_total)]
        if self._cur_index >= 0:
            if self._cur_phase == "preparing":
                # Fase de carregamento do modelo / preparo do audio: AINDA
                # nenhum segmento foi transcrito. Mostramos uma mensagem
                # explicita em vez de 0% ou uma barra parada, para o usuario
                # entender que o app esta trabalhando e nao congelado.
                parts.append(self.t("phase_preparing"))
            elif self._cur_total:
                pct = int(min(100, max(0, (self._cur_pos / self._cur_total) * 100)))
                parts.append(f"{pct}%")
                parts.append(f"{fmt_hms(self._cur_pos)} / {fmt_hms(self._cur_total)}")
                if self._cur_start and self._cur_pos > 0:
                    elapsed = time.monotonic() - self._cur_start
                    eta = elapsed * (self._cur_total - self._cur_pos) / self._cur_pos
                    parts.append(self.t("elapsed", elapsed=fmt_hms(elapsed)))
                    parts.append(self.t("eta", eta=fmt_hms(eta)))
            else:
                parts.append(self.t("position", pos=fmt_hms(self._cur_pos)))
                if self._cur_start:
                    elapsed = time.monotonic() - self._cur_start
                    parts.append(self.t("elapsed", elapsed=fmt_hms(elapsed)))
        self.status_label.configure(text="  •  ".join(parts))

    # ------------------------------------------------- eventos/log ---

    def _poll_events(self):
        try:
            while True:
                self._handle_event(self.event_queue.get_nowait())
        except queue.Empty:
            pass
        if self.is_running:
            self.after(150, self._poll_events)

    def _handle_event(self, evt):
        kind = evt["kind"]
        if kind == "log":
            self._log(evt["text"])
        elif kind == "item_status":
            idx, status = evt["index"], evt["status"]
            self.queue_items[idx].status = status
            self._refresh_tree()
            if status == ST_RUNNING:
                self._cur_index = idx
                self._cur_start = time.monotonic()
                self._reset_file_progress()
                self._set_bar_indeterminate()  # ate sabermos a duracao/fase
            elif status in ST_TERMINAL:
                self._batch_done = sum(1 for i in self.queue_items if i.status in ST_TERMINAL)
                self._reset_file_progress()
                self._cur_index = -1
            self._update_status_label()
        elif kind == "duration":
            # Guarda a duracao, mas NAO decide ainda o modo da barra: enquanto
            # estivermos na fase "preparing" (antes do 1o segmento), a barra
            # permanece indeterminada com a mensagem explicativa, mesmo que a
            # duracao total ja seja conhecida.
            if evt["index"] == self._cur_index:
                self._pending_duration = evt.get("seconds")
                if self._cur_phase == "transcribing":
                    self._apply_pending_duration()
                self._update_status_label()
        elif kind == "phase":
            if evt["index"] == self._cur_index:
                self._cur_phase = evt["phase"]
                if self._cur_phase == "preparing":
                    self._set_bar_indeterminate()
                elif self._cur_phase == "transcribing":
                    self._apply_pending_duration()
                self._update_status_label()
        elif kind == "progress_tick":
            if evt["index"] == self._cur_index:
                self._cur_pos = evt["seconds"]
                if self._cur_total:
                    self.file_progress.configure(value=min(self._cur_pos, self._cur_total))
                self._update_status_label()
        elif kind == "batch_finished":
            self._on_batch_finished()

    def _apply_pending_duration(self):
        dur = getattr(self, "_pending_duration", None)
        if dur:
            self._set_bar_determinate(dur)
        else:
            self._set_bar_indeterminate()

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

    def _save_current_settings(self):
        self.config_data.update({
            "whisper_path": self.whisper_path_var.get().strip(),
            "ffmpeg_path": self.ffmpeg_path or "",
            "ui_lang": self.ui_lang,
            "audio_lang_key": self.selected_audio_lang_key,
            "task": self.selected_task_key,
            "model_cli": self.selected_model_cli,
            "dictionary_name": self.selected_dict_name,
            "output_mode": self.output_mode_var.get(),
            "fixed_output_dir": self.fixed_output_var.get().strip(),
            "output_formats": {f: self.format_vars[f].get() for f in OUTPUT_FORMATS},
        })
        save_json(CONFIG_FILE, self.config_data)

    def _on_close(self):
        if self.is_running:
            if not messagebox.askyesno(self.t("exit_title"), self.t("exit_question")):
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
