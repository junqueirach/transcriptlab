#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TranscriptLab - GUI
===================
Batch-transcribe video/audio with OpenAI Whisper (CLI) and turn the result
into clean, AI-ready Markdown via MarkItDown.

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

APP_VERSION = "0.8.2"
APP_NAME = "TranscriptLab"
APP_AUTHOR = "Luiz Junqueira & Claude AI"
APP_CONTACT = "USEReira.ch@gmail.com"

import os
import re
import sys
import json
import time
import queue
import shutil
import zipfile
import tarfile
import threading
import subprocess
import webbrowser
import urllib.request
from pathlib import Path
from datetime import datetime

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import tkinter.font as tkfont

# ==========================================================================
# Paths / persistence
# ==========================================================================

CONFIG_DIR = Path.home() / ".whisper_transcriber"
CONFIG_FILE = CONFIG_DIR / "config.json"
DICTIONARIES_FILE = CONFIG_DIR / "dictionaries.json"
FFMPEG_INSTALL_DIR = CONFIG_DIR / "ffmpeg"

DEFAULT_WHISPER_PATHS = [
    r"C:\WhisperWorkspace\venv\Scripts\whisper.exe",
]

# App icon (64x64 PNG, base64). Film strip + document/MD motif.
APP_ICON_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAYAAACqaXHeAAABt0lEQVR4nO2bMVLDQAxF1wwn4AL4DClcMhS0"
    "tMAVUgMNFIwLaICaKyS0tBQZyhScIVyAK5iCWWaIvWtp45V2V3pNJuN1pP+tlTUexxhFUSRThZx0ePPUTZ3"
    "IFHw9XKH1oE5IVfg2GCNAC3MRvg3EiL2xBbmKNwaWu9eAnMVbxjQ4DShBvMWnZXQLlM6gASVdfYtL0z70B75"
    "fHsHBDubX4LXc9CqgxKtvGdImvgeAt4DlffXhPHZyfLRTMhygDQhlc39JFcrUt8/gteK3gBrAnQA36B6QY6Pz"
    "oRVAFQjTmSkRPweI3wLiDSDrAa/np/++N1Vr1t1dlFhnyzfwWjIDLE3VUof0QjYHpCbcEr0CNhefsUPsRDQDU"
    "hduiTYH1IuZMcZvBKZZxSL6bbBezP7MSBGyOSBVI8jngHX3+9lUbW82wDLFFmKbBGMNQVj0eQB3AtyIN4DseU"
    "AK9/whxFeAeAPYngfEIGSbaQVgT9A5oDDEG6BzAHcC3KgB3Alw0zMg5JXzXBjSJn4OcF7t0t4XdFW29gDXgZJ"
    "6gU+LtwJKMGFMw+gWyNkESO76p6mQAKkakXO1KorCww9zc3qp0AMSaAAAAABJRU5ErkJggg=="
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
                    ".avi", ".mov", ".flac", ".ogg")

# Inputs accepted in the MD File Generation tab (what MarkItDown / our cleaner
# can handle).
MARKITDOWN_EXTENSIONS = (".pdf", ".docx", ".pptx", ".xlsx", ".xls", ".csv",
                         ".json", ".xml", ".html", ".htm", ".txt", ".md",
                         ".rtf", ".epub", ".srt", ".vtt")
SUBTITLE_EXTENSIONS = (".srt", ".vtt")

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

# Speed-factor (wall/audio) defaults; self-calibrate via EMA after first run
DEFAULT_SPEED_FACTOR = 1.0
SPEED_FACTOR_ALPHA = 0.3
YT_PER_VIDEO_DEFAULT = 3.0   # near-constant transcript fetch seconds
MD_PER_FILE_DEFAULT = 0.6    # per-file conversion seconds

ST_PENDING = "pending"
ST_RUNNING = "running"
ST_DONE = "done"
ST_ERROR = "error"
ST_SKIPPED = "skipped"
ST_TERMINAL = (ST_DONE, ST_ERROR, ST_SKIPPED)

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
        "tab_transcription": "Transcrição de Vídeo",
        "tab_dictionary": "Dicionário de Vocabulário",
        "tab_md": "Geração de MD",
        # Menubar
        "menu_settings": "Configurações",
        "menu_about": "Sobre",
        "menu_whisper": "Whisper...",
        "menu_markitdown": "MarkItDown...",
        "menu_ffmpeg": "FFmpeg...",
        "menu_output_formats": "Formatos de saída...",
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
        "log_frame_md": "Atividade do MarkItDown (saída em tempo real)",
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
        "err_no_markitdown": "MarkItDown não foi encontrado. Abra Configurações → MarkItDown para instalá-lo.",
        "err_no_model_selected": "Nenhum modelo de IA instalado/selecionado. Use 'Adicionar modelo...' para baixar um.",
        "err_no_format": "Selecione pelo menos um formato de saída (Configurações → Formatos de saída).",
        "err_no_fixed_dir": "Selecione a pasta de saída fixa ou troque para 'mesma pasta de cada arquivo'.",
        "warn_path_not_found": "O caminho '{path}' não foi encontrado no disco.\nDeseja tentar executar mesmo assim (ex: caso esteja no PATH do sistema)?",
        "warn_queue_locked": "Não é possível editar a fila durante o processamento.",
        "info_all_in_queue": "Todos os arquivos selecionados já estão na fila.",
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
        "set_markitdown_found": "✓ MarkItDown encontrado (interpretador: {py}).",
        "set_markitdown_missing": "✗ MarkItDown não encontrado.",
        "set_markitdown_install": "Instalar MarkItDown (global)",
        "set_markitdown_install_q": "Instalar o MarkItDown globalmente usando pip?\n\nComando:\n{cmd}\n\nContinuar?",
        "set_recheck": "Verificar novamente",
        # Settings: FFmpeg
        "set_ffmpeg_title": "Configurações — FFmpeg",
        "set_ffmpeg_found": "✓ FFmpeg encontrado: {path}",
        "set_ffmpeg_missing": "✗ FFmpeg não encontrado.",
        "ffmpeg_locate": "Localizar...",
        "ffmpeg_open_folder": "Abrir pasta",
        "set_ffmpeg_install_auto": "Baixar e instalar automaticamente",
        "set_ffmpeg_winget": "Instalar via winget",
        "set_ffmpeg_open_page": "Abrir página de download",
        "set_ffmpeg_auto_q": "Baixar uma versão pronta do ffmpeg e instalá-la em:\n{dest}\n\nIsto baixa ~80 MB. Continuar?",
        "set_ffmpeg_downloading": "Baixando ffmpeg... aguarde.\n",
        "set_ffmpeg_extracting": "Extraindo...\n",
        "set_ffmpeg_done": "✓ FFmpeg instalado em: {path}\n",
        "set_ffmpeg_fail": "✗ Falha ao instalar o ffmpeg automaticamente: {e}\nUse 'Abrir página de download' para instalar manualmente.\n",
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
        "md_intro": "Converta documentos (PDF, DOCX, TXT, SRT, etc.) em Markdown limpo, pronto para uso com IA. Legendas (SRT/VTT) viram prosa sem marcações de tempo.",
        "md_queue_frame": "Fila de Conversão",
    },
    "en": {
        "window_title": APP_NAME,
        "tab_transcription": "Video Transcription",
        "tab_dictionary": "Vocabulary Dictionary",
        "tab_md": "MD File Generation",
        "menu_settings": "Settings",
        "menu_about": "About",
        "menu_whisper": "Whisper...",
        "menu_markitdown": "MarkItDown...",
        "menu_ffmpeg": "FFmpeg...",
        "menu_output_formats": "Output formats...",
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
        "log_frame_md": "MarkItDown Activity (real-time output)",
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
        "err_no_markitdown": "MarkItDown was not found. Open Settings → MarkItDown to install it.",
        "err_no_model_selected": "No AI model installed/selected. Use 'Add model...' to download one.",
        "err_no_format": "Select at least one output format (Settings → Output formats).",
        "err_no_fixed_dir": "Select the fixed output folder or switch to 'same folder as each file'.",
        "warn_path_not_found": "The path '{path}' was not found on disk.\nDo you want to try running it anyway (e.g. if it's on the system PATH)?",
        "warn_queue_locked": "The queue cannot be edited during processing.",
        "info_all_in_queue": "All selected files are already in the queue.",
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
        "set_markitdown_found": "✓ MarkItDown found (interpreter: {py}).",
        "set_markitdown_missing": "✗ MarkItDown not found.",
        "set_markitdown_install": "Install MarkItDown (global)",
        "set_markitdown_install_q": "Install MarkItDown globally using pip?\n\nCommand:\n{cmd}\n\nContinue?",
        "set_recheck": "Re-check",
        "set_ffmpeg_title": "Settings — FFmpeg",
        "set_ffmpeg_found": "✓ FFmpeg found: {path}",
        "set_ffmpeg_missing": "✗ FFmpeg not found.",
        "ffmpeg_locate": "Locate...",
        "ffmpeg_open_folder": "Open folder",
        "set_ffmpeg_install_auto": "Download and install automatically",
        "set_ffmpeg_winget": "Install via winget",
        "set_ffmpeg_open_page": "Open download page",
        "set_ffmpeg_auto_q": "Download a ready-made ffmpeg build and install it to:\n{dest}\n\nThis downloads ~80 MB. Continue?",
        "set_ffmpeg_downloading": "Downloading ffmpeg... please wait.\n",
        "set_ffmpeg_extracting": "Extracting...\n",
        "set_ffmpeg_done": "✓ FFmpeg installed at: {path}\n",
        "set_ffmpeg_fail": "✗ Could not auto-install ffmpeg: {e}\nUse 'Open download page' to install it manually.\n",
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
        "md_intro": "Convert documents (PDF, DOCX, TXT, SRT, etc.) into clean Markdown, ready for AI use. Subtitles (SRT/VTT) become prose with no timestamps.",
        "md_queue_frame": "Conversion Queue",
    },
}

# --- YouTube tab strings (merged in to keep the main table readable) -------
TRANSLATIONS["pt"].update({
    "tab_youtube": "Transcrição do YouTube",
    "yt_intro": "Cole um ou vários links do YouTube. O app baixa a transcrição/legenda pública de cada vídeo e gera um arquivo Markdown limpo (prosa, sem marcações de tempo), pronto para uso com IA.",
    "yt_output_info": "Este processo sempre gera o arquivo .md. Os arquivos .srt e .txt são opcionais (marque abaixo).",
    "yt_settings_note": "As opções de 'Formatos de saída' das Configurações NÃO se aplicam a esta aba.",
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
    "yt_intro": "Paste one or several YouTube links. The app downloads each video's public transcript/subtitles and produces a clean Markdown file (prose, no timestamps), ready for AI use.",
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
    "set_ytdlp_install": "Instalar / Atualizar yt-dlp",
    "set_ytdlp_install_q": "Executar:\n\n{cmd}\n\nContinuar?",
    # Feature C status / summary
    "status_cur_pos": "Posição do Vídeo Atual: {pos}",
    "status_total_transcribed": "Total Transcrito: {val}",
    "status_eta_complete": "Tempo Estimado para Concluir: {eta}",
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
    "dl_intro": "Cole links de vídeos ou de playlists do YouTube e baixe o vídeo (com escolha de "
                "resolução) ou apenas o áudio. Você é responsável por respeitar os termos do site e os direitos autorais.",
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
TRANSLATIONS["en"].update({
    "tab_download": "YouTube Download",
    "dep_ytdlp": "yt-dlp",
    "menu_ytdlp": "yt-dlp...",
    "set_ytdlp_title": "yt-dlp Settings",
    "set_ytdlp_about": "yt-dlp expands playlists and downloads YouTube video/audio. "
                       "Single-video transcript links work without it.",
    "set_ytdlp_found": "yt-dlp found and available.",
    "set_ytdlp_missing": "yt-dlp not found. Click Install.",
    "set_ytdlp_install": "Install / Update yt-dlp",
    "set_ytdlp_install_q": "Run:\n\n{cmd}\n\nContinue?",
    "status_cur_pos": "Current Video Position: {pos}",
    "status_total_transcribed": "Total Transcribed: {val}",
    "status_eta_complete": "Estimated Time to Complete: {eta}",
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


# ==========================================================================
# Config / pure utilities (testable without GUI)
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


def find_python_executable():
    """A Python interpreter usable for pip / -m markitdown. Avoids a frozen exe."""
    exe = sys.executable or ""
    if exe and os.path.basename(exe).lower().startswith("python"):
        return exe
    for name in ("python", "python3", "py"):
        w = shutil.which(name)
        if w:
            return w
    return exe or "python"


def find_whisper_path(saved_path=None):
    if saved_path and os.path.exists(saved_path):
        return saved_path
    for p in DEFAULT_WHISPER_PATHS:
        if os.path.exists(p):
            return p
    return shutil.which("whisper") or shutil.which("whisper.exe")


def whisper_is_available(saved_path=None):
    return bool(find_whisper_path(saved_path))


def find_ffmpeg(saved_path=None):
    if saved_path and os.path.exists(saved_path):
        return saved_path
    return shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")


def markitdown_python(config_data):
    """Interpreter used to run markitdown (override or the app's python)."""
    override = (config_data or {}).get("markitdown_python") or ""
    if override and os.path.exists(override):
        return override
    return find_python_executable()


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


def installed_model_clis(cache_dir=None):
    """Models actually present in the cache, in catalog order."""
    cache_dir = cache_dir or whisper_cache_dir()
    out = []
    for cli in ALL_MODEL_CLIS:
        if os.path.exists(os.path.join(cache_dir, model_file_name(cli))):
            out.append(cli)
    return out


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


def parse_replacements_text(raw):
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

def subtitle_to_prose(text, is_vtt=False, title=None):
    lines = (text or "").splitlines()
    cues = []
    cur = []

    def flush():
        if cur:
            t = " ".join(x.strip() for x in cur if x.strip())
            t = re.sub(r"\s+", " ", t).strip()
            if t:
                cues.append(t)
            cur.clear()

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
            continue
        if re.fullmatch(r"\d+", line):  # srt cue index
            continue
        cur.append(line)
    flush()

    # Drop consecutive duplicate cues (Whisper sometimes repeats a line).
    deduped = []
    for c in cues:
        if not deduped or deduped[-1] != c:
            deduped.append(c)

    # Group cues into paragraphs at sentence boundaries.
    paragraphs, buf = [], []
    for c in deduped:
        buf.append(c)
        joined = " ".join(buf)
        if re.search(r"[.!?…][\"'”’)\]]?$", c) and len(joined) >= 200:
            paragraphs.append(joined)
            buf = []
    if buf:
        paragraphs.append(" ".join(buf))

    body = "\n\n".join(re.sub(r"[ \t]+", " ", p).strip()
                       for p in paragraphs if p.strip())
    if not body.strip():
        return ""
    header = f"# {title}\n\n" if title else ""
    return header + body.strip() + "\n"


def convert_subtitle_file_to_md(src_path, dst_path, title=None):
    is_vtt = src_path.lower().endswith(".vtt")
    with open(src_path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
    prose = subtitle_to_prose(content, is_vtt=is_vtt, title=title)
    with open(dst_path, "w", encoding="utf-8") as f:
        f.write(prose)
    return dst_path


def build_markitdown_command(python_exe, src_path, dst_path):
    return [python_exe, "-m", "markitdown", src_path, "-o", dst_path]


def build_pip_install_command(python_exe, package):
    return [python_exe, "-m", "pip", "install", "--upgrade", package]


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
    if saved_path and os.path.exists(saved_path):
        return saved_path
    return shutil.which("yt-dlp") or shutil.which("yt-dlp.exe")


def ytdlp_is_available(python_exe=None):
    """Fast probe: is the 'yt_dlp' module importable? (CLI presence also counts)."""
    if find_ytdlp():
        return True
    python_exe = python_exe or find_python_executable()
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
                                 progressive=False):
    """Build a yt-dlp download command (verified flags).

    progressive=True selects single-file formats that need no ffmpeg merge
    (used as a degraded fallback when ffmpeg is unavailable)."""
    cmd = list(prefix) + [
        "--newline", "--no-warnings",
        "--progress-template",
        "download:PROG|%(progress._percent_str)s|%(progress.eta)s",
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
    out_tmpl = os.path.join(out_dir, "%(title)s.%(ext)s")
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


def update_speed_factor_ema(old, sample, alpha=SPEED_FACTOR_ALPHA):
    """EMA update of wall/audio realtime factor."""
    try:
        sample = float(sample)
    except (TypeError, ValueError):
        return old
    if sample <= 0:
        return old
    if old is None or old <= 0:
        return sample
    return (1.0 - alpha) * float(old) + alpha * sample


# --------------------------------------------------------------------------
# YouTube metadata + Markdown header (Feature E)
# --------------------------------------------------------------------------

def youtube_metadata(video_id, prefix=None, timeout=30):
    """Best-effort {video_id,title,duration,upload_date,url}. Network; mocked in tests."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    meta = {"video_id": video_id, "title": None, "duration": None,
            "upload_date": None, "url": url}
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
                if meta["title"]:
                    return meta
        except Exception:
            pass
    if not meta["title"]:
        try:
            from urllib.parse import quote
            oembed = ("https://www.youtube.com/oembed?format=json&url="
                      + quote(url, safe=""))
            with urllib.request.urlopen(oembed, timeout=15) as r:
                d = json.loads(r.read().decode("utf-8"))
                meta["title"] = d.get("title")
        except Exception:
            pass
    return meta


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


def sleep_with_jitter(stop_flag, lo, hi):
    """Cancellable randomized delay in [lo, hi] seconds."""
    import random
    target = random.uniform(lo, hi)
    end = time.time() + target
    while time.time() < end:
        if stop_flag is not None and stop_flag.is_set():
            return
        time.sleep(0.05)


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
# Queue item + partial writer + workers
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
        self.output_md = None
        # v0.8.0: length/metadata (media or YouTube)
        self.duration = None        # seconds or None
        self.video_id = None
        self.title = None           # YouTube title (verbatim)
        self.upload_date = None     # YYYYMMDD or None
        self.meta_fetched = False
        self.size_bytes = None      # MD tab


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
                   "--verbose", "True"]
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


class YouTubeWorker(threading.Thread):
    """Download YouTube transcripts and save clean MD (always) + optional SRT/TXT."""

    def __init__(self, items, preferred_code, keep_srt, keep_txt, output_dir,
                 strings, event_queue, stop_flag, ytdlp_prefix=None,
                 delay_range=YT_TRANSCRIBE_DELAY, lang="en"):
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

    def post(self, kind, **kwargs):
        self.event_queue.put({"kind": kind, **kwargs})

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
        self.post("yt_batch_finished")

    def _stop_batch_block(self, idx, total):
        for j in range(idx + 1, total):
            self.items[j].status = ST_PENDING
        self.post("yt_log", text=self.s["yt_log_batch_stopped"])
        self.post("yt_batch_blocked", message=self.s["yt_block_dialog"])
        self.post("yt_batch_finished")

    def _write_outputs(self, item, vid, res):
        out_dir = self.output_dir
        item.output_dir = out_dir
        srt_text = build_srt_from_snippets(res["snippets"])
        prose = subtitle_to_prose(srt_text, is_vtt=False, title=None)
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
        header = build_youtube_md_header(meta, self.s)
        md_path = os.path.join(out_dir, base + ".md")
        md_content = (header + "\n\n" + (prose or "")).rstrip() + "\n"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        item.output_md = md_path
        saved = [base + ".md"]
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


class DownloadWorker(threading.Thread):
    """Download media via yt-dlp (subprocess), with rate-limit protection."""

    def __init__(self, items, prefix, out_dir, *, audio_only, audio_format,
                 resolution, container, ffmpeg_location, strings, event_queue,
                 stop_flag, delay_range=YT_DOWNLOAD_DELAY, progressive=False):
        super().__init__(daemon=True)
        self.items = items
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
        self.current_process = None

    def post(self, kind, **kwargs):
        self.event_queue.put({"kind": kind, **kwargs})

    def _run_once(self, item, vid):
        """Run yt-dlp for one item; return (returncode, captured_text)."""
        url = f"https://www.youtube.com/watch?v={vid}"
        cmd = build_ytdlp_download_command(
            self.prefix, url, self.out_dir, audio_only=self.audio_only,
            audio_format=self.audio_format, resolution=self.resolution,
            container=self.container, ffmpeg_location=self.ffmpeg_location,
            single_video=True, progressive=self.progressive)
        captured = []
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
            pct = parse_ytdlp_progress_line(line)
            if pct is not None:
                self.post("dl_progress", percent=pct)
            else:
                self.post("dl_log", text=line)
        self.current_process.wait()
        return self.current_process.returncode, "".join(captured[-40:])

    def run(self):
        total = len(self.items)
        os.makedirs(self.out_dir, exist_ok=True)
        for idx, item in enumerate(self.items):
            if self.stop_flag.is_set():
                item.status = ST_SKIPPED
                self.post("dl_item_status", index=idx, status=ST_SKIPPED)
                continue
            vid = getattr(item, "video_id", None) or youtube_video_id(item.filepath)
            self.post("dl_item_status", index=idx, status=ST_RUNNING)
            self.post("dl_progress_index", index=idx)
            sep = "=" * 70
            self.post("dl_log", text=self.s["log_file_start"].format(
                sep=sep, i=idx + 1, n=total, name=item.filename))

            cause = None
            rc = -1
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
                self.post("dl_item_status", index=idx, status=ST_SKIPPED)
                break
            if rc == 0:
                item.status = ST_DONE
                item.output_dir = self.out_dir
                self.post("dl_item_status", index=idx, status=ST_DONE)
                self.post("dl_log", text=self.s["log_file_done"].format(name=vid))
            else:
                short, action = youtube_error_message(cause or "generic", self.s, raw=tail)
                item.status = ST_ERROR
                item.error_message = short
                self.post("dl_item_status", index=idx, status=ST_ERROR, error=short)
                self.post("dl_log", text=self.s["log_file_error"].format(name=vid, e=short))
                if action:
                    self.post("dl_log", text="    " + action + "\n")
                if cause in BLOCK_CAUSES:
                    for j in range(idx + 1, total):
                        self.items[j].status = ST_PENDING
                    self.post("dl_log", text=self.s["yt_log_batch_stopped"])
                    self.post("dl_batch_blocked", message=self.s["yt_block_dialog"])
                    self.post("dl_batch_finished")
                    return
            if idx < total - 1 and not self.stop_flag.is_set():
                sleep_with_jitter(self.stop_flag, *self.delay_range)
        self.post("dl_batch_finished")

    def cancel(self):
        self.stop_flag.set()
        if self.current_process and self.current_process.poll() is None:
            try:
                self.current_process.terminate()
            except OSError:
                pass


class TranscriptionWorker(threading.Thread):
    def __init__(self, items, whisper_exe, ffmpeg_path, lang_param, task,
                 model_name, initial_prompt, replacements, keep_formats,
                 output_dir_mode, fixed_output_dir, clip_range, strings,
                 event_queue, stop_flag):
        super().__init__(daemon=True)
        self.items = items
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
            self.post("log", text=self.s["log_probing"])
            full_duration = ffmpeg_probe_duration(self.ffmpeg_path, item.filepath)
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
        base = os.path.splitext(os.path.basename(item.filepath))[0]
        partial = PartialTranscriptWriter(os.path.join(out_dir, base + ".partial.txt"))
        partial.open()
        import tempfile
        tmp_dir = tempfile.mkdtemp(prefix="whisper_clip_")
        try:
            input_path = self._prepare_clip_if_needed(item, idx, tmp_dir)
            cmd = [self.whisper_exe, input_path, "--model", self.model_name,
                   "--task", self.task, "--fp16", "False",
                   "--output_dir", out_dir, "--output_format", "all",
                   "--verbose", "True"]
            if self.lang_param:
                cmd.extend(["--language", self.lang_param])
            if self.initial_prompt:
                cmd.extend(["--initial_prompt", self.initial_prompt])
            self.post("log", text=self.s["log_cmd"].format(cmd=" ".join(cmd)))
            self.post("phase", index=idx, phase="preparing")
            self.current_process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                encoding="utf-8", errors="replace", bufsize=1,
                env=subprocess_child_env(), **subprocess_hidden_window_kwargs())
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
                    f"whisper exited with code {self.current_process.returncode}.")
            if self.stop_flag.is_set():
                return

            def fpath(ext):
                return os.path.join(out_dir, base + "." + ext)

            # Clip outputs were named after the temp clip file; rename to base.
            if self.clip_range:
                clip_base = os.path.splitext(os.path.basename(input_path))[0]
                if clip_base != base:
                    for ext in WHISPER_FORMATS:
                        src = os.path.join(out_dir, clip_base + "." + ext)
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
            if "md" in self.keep_formats:
                self.post("log", text=self.s["log_md_make"])
                made = False
                for ext in ("srt", "vtt"):
                    p = fpath(ext)
                    if os.path.exists(p):
                        convert_subtitle_file_to_md(p, fpath("md"), title=base)
                        made = True
                        break
                if not made and os.path.exists(fpath("txt")):
                    with open(fpath("txt"), "r", encoding="utf-8", errors="replace") as f:
                        txt = f.read()
                    prose = "\n\n".join(s.strip() for s in re.split(r"\n\s*\n", txt) if s.strip())
                    with open(fpath("md"), "w", encoding="utf-8") as f:
                        f.write((f"# {base}\n\n" + prose).strip() + "\n")
                if self.replacements:
                    self._apply_replacements(fpath("md"))

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
    """MD File Generation tab: convert docs/subtitles to clean Markdown."""

    def __init__(self, items, python_exe, markitdown_ok, output_dir_mode,
                 fixed_output_dir, strings, event_queue, stop_flag):
        super().__init__(daemon=True)
        self.items = items
        self.python_exe = python_exe
        self.markitdown_ok = markitdown_ok
        self.output_dir_mode = output_dir_mode
        self.fixed_output_dir = fixed_output_dir
        self.s = strings
        self.event_queue = event_queue
        self.stop_flag = stop_flag
        self.current_process = None

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
        dst = os.path.join(out_dir, base + ".md")
        ext = os.path.splitext(item.filepath)[1].lower()
        if ext in SUBTITLE_EXTENSIONS:
            self.post("md_log", text=self.s["log_md_make"])
            convert_subtitle_file_to_md(item.filepath, dst, title=base)
            item.output_md = dst
            return
        if not self.markitdown_ok:
            raise RuntimeError("MarkItDown is required to convert this file type.")
        cmd = build_markitdown_command(self.python_exe, item.filepath, dst)
        self.post("md_log", text=self.s["log_md_markitdown"].format(name=item.filename))
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
        if not self.stop_flag.is_set() and self.current_process.returncode != 0:
            raise RuntimeError(f"markitdown exited with code {self.current_process.returncode}.")
        item.output_md = dst if os.path.exists(dst) else None

    def cancel(self):
        self.stop_flag.set()
        if self.current_process and self.current_process.poll() is None:
            try:
                self.current_process.terminate()
            except OSError:
                pass


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
    tree.bind("<Control-a>", _select_all)
    tree.bind("<Control-A>", _select_all)
    tree.bind("<Button-1>", _reset_anchor_click, add="+")
    tree.bind("<Down>", _reset_anchor_arrow, add="+")
    tree.bind("<Up>", _reset_anchor_arrow, add="+")
    # exposed for programmatic use / tests
    tree.ms_extend = _extend
    tree.ms_select_all = _select_all


# ==========================================================================
# Main application
# ==========================================================================

DEFAULT_CONFIG = {
    "ui_language": "en",
    "whisper_path": "",
    "ffmpeg_path": "",
    "markitdown_python": "",
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
}

_OLD_AUDIO_LANG_MAP = {"portuguese": "pt", "english": "en",
                       "spanish": "es", "auto": "auto"}


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

        # runtime state
        self.queue_items = []
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
        self.download_worker = None
        self.download_stop_flag = None
        self.download_event_queue = queue.Queue()
        self.download_is_running = False
        self._dl_done = 0
        self._dl_errors = 0
        self._dl_total = 0
        self._dl_cur_index = 0
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
        self.geometry("1024x780")
        self.minsize(720, 560)
        self._set_icon()

        self._build_menubar()
        self._build_ui()

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(120, self._poll_events)
        self.after(120, self._poll_md_events)
        self.after(120, self._poll_youtube_events)
        self.after(120, self._poll_download_events)
        self.after(150, self._poll_probe_events)

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

    def _save_config(self):
        save_json(CONFIG_FILE, self.cfg)

    def _detect_dependencies(self):
        self.whisper_path = find_whisper_path(self.cfg.get("whisper_path") or None)
        self.ffmpeg_path = find_ffmpeg(self.cfg.get("ffmpeg_path") or None)
        self.python_exe = markitdown_python(self.cfg)
        self.markitdown_ok = markitdown_is_available(self.python_exe)
        self.ytdlp_ok = ytdlp_is_available(self.python_exe)

    def _set_icon(self):
        try:
            import base64
            self._icon_img = tk.PhotoImage(data=base64.b64decode(APP_ICON_BASE64))
            self.iconphoto(True, self._icon_img)
        except Exception:
            pass

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

    def _model_display(self, cli):
        info = MODEL_INFO[cli]
        return f"{cli}  —  {self.t(info['desc_key'])}"

    # ======================================================================
    # Menubar
    # ======================================================================
    def _build_menubar(self):
        menubar = tk.Menu(self)
        settings_menu = tk.Menu(menubar, tearoff=0)
        settings_menu.add_command(label=self.t("menu_whisper"),
                                  command=self._open_whisper_settings)
        settings_menu.add_command(label=self.t("menu_markitdown"),
                                  command=self._open_markitdown_settings)
        settings_menu.add_command(label=self.t("menu_ytdlp"),
                                  command=self._open_ytdlp_settings)
        settings_menu.add_command(label=self.t("menu_ffmpeg"),
                                  command=self._open_ffmpeg_settings)
        settings_menu.add_command(label=self.t("menu_output_formats"),
                                  command=self._open_output_formats)
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
        self._style_notebook_tabs()
        self._wrap_labels = []
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=8, pady=8)

        self.tab_main = ttk.Frame(self.notebook)
        self.tab_md = ttk.Frame(self.notebook)
        self.tab_youtube = ttk.Frame(self.notebook)
        self.tab_download = ttk.Frame(self.notebook)
        self.tab_dict = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_main, text=self.t("tab_transcription"))
        self.notebook.add(self.tab_md, text=self.t("tab_md"))
        self.notebook.add(self.tab_youtube, text=self.t("tab_youtube"))
        self.notebook.add(self.tab_download, text=self.t("tab_download"))
        self.notebook.add(self.tab_dict, text=self.t("tab_dictionary"))

        self._build_transcription_tab(self.tab_main)
        self._build_md_tab(self.tab_md)
        self._build_youtube_tab(self.tab_youtube)
        self._build_download_tab(self.tab_download)
        self._build_dictionary_tab(self.tab_dict)
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
        self.ind_markitdown.bind("<Button-1>", lambda e: self._open_markitdown_settings())
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
        ttk.Button(btns, text=self.t("clear_queue"), command=self._clear_queue).pack(side="left", padx=2)
        ttk.Button(btns, text=self.t("move_up"), command=lambda: self._move_selected(-1)).pack(side="left", padx=2)
        ttk.Button(btns, text=self.t("move_down"), command=lambda: self._move_selected(1)).pack(side="left", padx=2)
        cols = ("order", "file", "folder", "length", "status")
        qwrap, self.tree, _qsb = make_scrollable_queue(qf, cols, height=11)
        qwrap.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)
        qf.rowconfigure(1, weight=1)
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
        self.progress = ttk.Progressbar(runf, mode="determinate", maximum=100)
        self.progress.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(6, 0))
        self.progress_pct_var = tk.StringVar(value="")
        self.progress_pct_label = tk.Label(runf, textvariable=self.progress_pct_var,
                                            font=("TkDefaultFont", 8, "bold"),
                                            bg="#e9e9e9", fg="#222", bd=0)
        self.progress_pct_label.place(in_=self.progress, relx=0.5, rely=0.5, anchor="center")
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
        root = ttk.Frame(parent)
        root.pack(fill="both", expand=True)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(2, weight=1)   # queue expands; log is capped

        intro = ttk.Label(root, text=self.t("md_intro"), foreground="#555")
        intro.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 2))
        intro.configure(wraplength=900)
        self._md_intro_label = intro

        # output folder
        outf = ttk.LabelFrame(root, text=self.t("output_folder"))
        outf.grid(row=1, column=0, sticky="ew", padx=8, pady=4)
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

        # queue (prominent, scrollable)
        qf = ttk.LabelFrame(root, text=self.t("md_queue_frame"))
        qf.grid(row=2, column=0, sticky="nsew", padx=8, pady=4)
        qf.columnconfigure(0, weight=1)
        qf.rowconfigure(1, weight=1)
        btns = ttk.Frame(qf)
        btns.grid(row=0, column=0, sticky="ew", padx=4, pady=4)
        ttk.Button(btns, text=self.t("add_files"), command=self._md_add_files).pack(side="left", padx=2)
        ttk.Button(btns, text=self.t("remove_selected"), command=self._md_remove_selected).pack(side="left", padx=2)
        ttk.Button(btns, text=self.t("clear_queue"), command=self._md_clear_queue).pack(side="left", padx=2)
        cols = ("order", "file", "folder", "size", "status")
        qwrap, self.md_tree, _msb = make_scrollable_queue(qf, cols, height=11)
        qwrap.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)
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
        self.md_summary_var = tk.StringVar(value="")
        ttk.Label(qf, textvariable=self.md_summary_var, foreground="#444"
                  ).grid(row=2, column=0, sticky="w", padx=6, pady=(0, 4))

        # run controls
        runf = ttk.Frame(root)
        runf.grid(row=3, column=0, sticky="ew", padx=8, pady=4)
        runf.columnconfigure(2, weight=1)
        self.md_start_btn = ttk.Button(runf, text=self.t("start_batch_md"), command=self._start_md_batch)
        self.md_start_btn.grid(row=0, column=0, padx=2)
        self.md_cancel_btn = ttk.Button(runf, text=self.t("cancel"), command=self._cancel_md_batch, state="disabled")
        self.md_cancel_btn.grid(row=0, column=1, padx=2)
        self.md_open_out_btn = ttk.Button(runf, text=self.t("open_output_folder"),
                                          command=self._md_open_output_folder, state="disabled")
        self.md_open_out_btn.grid(row=0, column=3, padx=2, sticky="e")
        self.md_progress = ttk.Progressbar(runf, mode="determinate", maximum=100)
        self.md_progress.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(6, 0))
        self.md_progress_pct_var = tk.StringVar(value="")
        self.md_progress_pct_label = tk.Label(runf, textvariable=self.md_progress_pct_var,
                                               font=("TkDefaultFont", 8, "bold"),
                                               bg="#e9e9e9", fg="#222", bd=0)
        self.md_progress_pct_label.place(in_=self.md_progress, relx=0.5, rely=0.5, anchor="center")
        self.md_progress_label_var = tk.StringVar(value=self.t("waiting_start"))
        ttk.Label(runf, textvariable=self.md_progress_label_var, foreground="#555"
                  ).grid(row=2, column=0, columnspan=4, sticky="w", pady=(2, 0))

        # log (secondary, capped)
        logf = ttk.LabelFrame(root, text=self.t("log_frame_md"))
        logf.grid(row=4, column=0, sticky="ew", padx=8, pady=4)
        logf.columnconfigure(0, weight=1)
        self.md_log_text = tk.Text(logf, height=7, wrap="word", state="disabled",
                                   font=("TkFixedFont", 9))
        logsb = ttk.Scrollbar(logf, orient="vertical", command=self.md_log_text.yview)
        self.md_log_text.configure(yscrollcommand=logsb.set)
        self.md_log_text.grid(row=0, column=0, sticky="nsew", padx=(4, 0), pady=4)
        logsb.grid(row=0, column=1, sticky="ns", pady=4)

    # ---- YouTube Transcription tab --------------------------------------
    def _build_youtube_tab(self, parent):
        root = ttk.Frame(parent)
        root.pack(fill="both", expand=True)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(4, weight=1)   # queue row expands; log is capped
        self._yt_controls = []

        # status indicators (MarkItDown + yt-dlp), clickable
        status = ttk.LabelFrame(root, text="")
        status.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 2))
        status.columnconfigure(2, weight=1)
        self.yt_ind_markitdown = tk.Label(status, text="", cursor="hand2",
                                          font=("TkDefaultFont", 10, "bold"))
        self.yt_ind_markitdown.grid(row=0, column=0, padx=8, pady=6)
        self.yt_ind_markitdown.bind("<Button-1>", lambda e: self._open_markitdown_settings())
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

        qf = ttk.LabelFrame(root, text=self.t("tab_youtube"))
        qf.grid(row=4, column=0, sticky="nsew", padx=8, pady=4)
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
        qwrap, self.yt_tree, _ysb2 = make_scrollable_queue(qf, cols, height=11)
        qwrap.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)
        self.yt_tree.heading("order", text=self.t("col_order"))
        self.yt_tree.heading("video", text=self.t("yt_col_video"))
        self.yt_tree.heading("length", text=self.t("col_length"))
        self.yt_tree.heading("status", text=self.t("col_status"))
        self.yt_tree.column("order", width=40, anchor="center", stretch=False)
        self.yt_tree.column("video", width=460)
        self.yt_tree.column("length", width=90, anchor="center", stretch=False)
        self.yt_tree.column("status", width=160, anchor="center")
        self.yt_summary_var = tk.StringVar(value="")
        ttk.Label(qf, textvariable=self.yt_summary_var, foreground="#444"
                  ).grid(row=2, column=0, sticky="w", padx=6, pady=(0, 4))

        opt = ttk.Frame(root)
        opt.grid(row=5, column=0, sticky="ew", padx=10, pady=2)
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
        info.grid(row=6, column=0, sticky="w", padx=10, pady=(2, 2))
        info.configure(wraplength=900)

        of = ttk.LabelFrame(root, text=self.t("fixed_folder"))
        of.grid(row=7, column=0, sticky="ew", padx=8, pady=4)
        of.columnconfigure(0, weight=1)
        self.yt_outdir_var = tk.StringVar(value=self.cfg.get("youtube_output_dir") or str(Path.home()))
        yt_entry = ttk.Entry(of, textvariable=self.yt_outdir_var)
        yt_entry.grid(row=0, column=0, sticky="ew", padx=6, pady=6)
        yt_browse = ttk.Button(of, text=self.t("browse"), command=self._yt_browse_outdir)
        yt_browse.grid(row=0, column=1, padx=6, pady=6)
        self._yt_controls += [yt_entry, yt_browse]

        rf = ttk.Frame(root)
        rf.grid(row=8, column=0, sticky="ew", padx=8, pady=4)
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
        self.yt_progress = ttk.Progressbar(rf, mode="determinate", maximum=100)
        self.yt_progress.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(6, 0))
        self.yt_progress_pct_var = tk.StringVar(value="")
        self.yt_progress_pct_label = tk.Label(rf, textvariable=self.yt_progress_pct_var,
                                              font=("TkDefaultFont", 8, "bold"),
                                              bg="#e9e9e9", fg="#222", bd=0)
        self.yt_progress_pct_label.place(in_=self.yt_progress, relx=0.5, rely=0.5, anchor="center")
        self.yt_progress_label_var = tk.StringVar(value=self.t("waiting_start"))
        ttk.Label(rf, textvariable=self.yt_progress_label_var, foreground="#555"
                  ).grid(row=2, column=0, columnspan=4, sticky="w", pady=(2, 0))

        lf = ttk.LabelFrame(root, text=self.t("yt_log_frame"))
        lf.grid(row=9, column=0, sticky="ew", padx=8, pady=4)
        lf.columnconfigure(0, weight=1)
        self.yt_log_text = tk.Text(lf, height=7, wrap="word", state="disabled",
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
        d = filedialog.askdirectory(title=self.t("select_output_title"))
        if d:
            self.yt_outdir_var.set(d)
            self.cfg["youtube_output_dir"] = d
            self._save_config()

    def _refresh_youtube_enabled(self):
        """Grey out the whole tab when MarkItDown is missing."""
        if not hasattr(self, "yt_ind_markitdown"):
            return
        ok = bool(self.markitdown_ok)
        mark = self.t("dep_found") if ok else self.t("dep_missing")
        self.yt_ind_markitdown.configure(text=f"{self.t('dep_markitdown')} {mark}",
                                         fg=("#1a7f37" if ok else "#cf222e"))
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
        running = self.youtube_is_running if target == "youtube" else self.download_is_running
        if running:
            messagebox.showwarning(self.t("warn"), self.t("warn_queue_locked"))
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
        idx = int(sel[0]); new = idx + direction
        if 0 <= new < len(self.youtube_queue_items):
            self.youtube_queue_items[idx], self.youtube_queue_items[new] = \
                self.youtube_queue_items[new], self.youtube_queue_items[idx]
            self._render_youtube_queue()
            self.yt_tree.selection_set(str(new))

    def _yt_remove_selected(self):
        if self.youtube_is_running:
            messagebox.showwarning(self.t("warn"), self.t("warn_queue_locked"))
            return
        for iid in self.yt_tree.selection():
            idx = int(iid)
            if 0 <= idx < len(self.youtube_queue_items):
                self.youtube_queue_items[idx] = None
        self.youtube_queue_items = [it for it in self.youtube_queue_items if it is not None]
        self._render_youtube_queue()
        self._update_youtube_summary()

    def _yt_clear_queue(self):
        if self.youtube_is_running:
            messagebox.showwarning(self.t("warn"), self.t("warn_queue_locked"))
            return
        self.youtube_queue_items = []
        self._render_youtube_queue()
        self._update_youtube_summary()

    def _yt_status_text(self, status):
        return {ST_PENDING: self.t("status_pending"),
                ST_RUNNING: self.t("status_running_yt"),
                ST_DONE: self.t("status_done"),
                ST_ERROR: self.t("status_error"),
                ST_SKIPPED: self.t("status_skipped")}.get(status, status)

    def _render_youtube_queue(self):
        if not hasattr(self, "yt_tree"):
            return
        self.yt_tree.delete(*self.yt_tree.get_children())
        for i, it in enumerate(self.youtube_queue_items):
            label = it.error_message if (it.status == ST_ERROR and it.error_message) \
                else self._yt_status_text(it.status)
            length = fmt_hms(it.duration) if it.duration else "…"
            self.yt_tree.insert("", "end", iid=str(i),
                                values=(i + 1, it.filename, length, label))

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
        if not self.markitdown_ok:
            messagebox.showerror(self.t("error"), self.t("err_no_markitdown"))
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
        for it in self.youtube_queue_items:
            it.status = ST_PENDING
            it.error_message = ""
            it.output_dir = None
        self._render_youtube_queue()
        code = self.cfg.get("youtube_pref_lang", "auto")
        preferred = None if code == "auto" else code
        prefix = ytdlp_command_prefix(self.python_exe) if self.ytdlp_ok else None
        self.youtube_stop_flag = threading.Event()
        self.youtube_worker = YouTubeWorker(
            items=self.youtube_queue_items, preferred_code=preferred,
            keep_srt=self.yt_srt_var.get(), keep_txt=self.yt_txt_var.get(),
            output_dir=out_dir, strings=self.s, event_queue=self.youtube_event_queue,
            stop_flag=self.youtube_stop_flag, ytdlp_prefix=prefix,
            delay_range=YT_TRANSCRIBE_DELAY, lang=self.lang)
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
                self.youtube_queue_items[idx].status = status
                if ev.get("error"):
                    self.youtube_queue_items[idx].error_message = ev["error"]
                self.yt_tree.set(str(idx), "status",
                                 ev.get("error") or self._yt_status_text(status))
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
        try:
            bar.configure(value=max(0.0, min(100.0, float(pct))))
        except Exception:
            pass
        if pct_var is not None:
            pct_var.set(self.t("pct_label", pct=int(round(pct))))

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

    def _enforce_caps(self, count, soft, hard):
        if count > hard:
            messagebox.showerror(self.t("cap_hard_title"),
                                 self.t("cap_hard_msg", n=count, max=hard))
            return False
        if count > soft:
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
        d = self.cfg.get("speed_factor_by_model", {})
        if not isinstance(d, dict):
            return DEFAULT_SPEED_FACTOR
        return d.get(model, DEFAULT_SPEED_FACTOR)

    def _set_speed_factor(self, model, sample):
        d = self.cfg.get("speed_factor_by_model")
        if not isinstance(d, dict):
            d = {}
            self.cfg["speed_factor_by_model"] = d
        d[model] = update_speed_factor_ema(d.get(model), sample)
        self._save_config()

    # ---- shared link ingest (single videos + playlist expansion) ---------
    def _ingest_links(self, raw, items_list, target):
        existing = {getattr(it, "video_id", None) for it in items_list}
        added = invalid = playlists = 0
        new_singles = []
        log_widget = self.yt_log_text if target == "youtube" else self.dl_log_text
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
                if not self.ytdlp_ok:
                    messagebox.showwarning(self.t("warn"),
                                           self.t("yt_need_ytdlp_playlist"))
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
    def _probe_media_lengths(self, items):
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
                    {"target": "trans", "item": it, "duration": dur})
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

    # ---- summary lines ---------------------------------------------------
    def _update_trans_summary(self):
        if not hasattr(self, "trans_summary_var"):
            return
        total, n_known, secs = queue_length_summary(self.queue_items)
        model = self.model_var.get() if hasattr(self, "model_var") else ""
        sf = self._get_speed_factor(model)
        parts = [self.t("summary_videos", n=total)]
        if secs > 0:
            parts.append(self.t("summary_total_len", dur=fmt_long_duration(secs)))
            eta = estimate_time_seconds(secs, sf)
            parts.append(self.t("summary_est_transcribe", eta="≈ " + fmt_long_duration(eta)))
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
            self.ytdlp_ok = ytdlp_is_available(self.python_exe)
            if self.ytdlp_ok:
                status_var.set(self.t("set_ytdlp_found"))
                status_lbl.configure(foreground="#1a7f37")
            else:
                status_var.set(self.t("set_ytdlp_missing"))
                status_lbl.configure(foreground="#cf222e")
            self._refresh_youtube_enabled()
            self._refresh_download_enabled()

        def do_install():
            cmd = build_pip_install_command(self.python_exe, "yt-dlp")
            if not messagebox.askyesno(self.t("confirm"),
                                       self.t("set_ytdlp_install_q",
                                              cmd=" ".join(cmd)), parent=win):
                return
            self._append_text(log, self.t("install_running"))
            install_btn.configure(state="disabled")
            recheck_btn.configure(state="disabled")
            stop = threading.Event()
            q = queue.Queue()
            worker = CommandStreamWorker(cmd, q, stop, tag="ytdlp")
            worker.start()

            def done(success, error):
                install_btn.configure(state="normal")
                recheck_btn.configure(state="normal")
                self._append_text(log, self.t("install_done_ok") if success
                                  else self.t("install_done_fail", code=error))
                refresh_status()
            self._attach_stream(q, log, done)

        btns = ttk.Frame(frm)
        btns.grid(row=3, column=0, sticky="ew")
        install_btn = ttk.Button(btns, text=self.t("set_ytdlp_install"),
                                 command=do_install)
        install_btn.pack(side="left", padx=2)
        recheck_btn = ttk.Button(btns, text=self.t("set_recheck"),
                                 command=refresh_status)
        recheck_btn.pack(side="left", padx=2)
        ttk.Button(btns, text=self.t("close"),
                   command=win.destroy).pack(side="right", padx=2)
        refresh_status()

    # ======================================================================
    # Download tab
    # ======================================================================
    def _build_download_tab(self, parent):
        root = ttk.Frame(parent)
        root.pack(fill="both", expand=True)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(4, weight=1)   # queue expands
        self._dl_controls = []

        status = ttk.LabelFrame(root, text="")
        status.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 2))
        status.columnconfigure(2, weight=1)
        self.dl_ind_ytdlp = tk.Label(status, text="", cursor="hand2",
                                     font=("TkDefaultFont", 10, "bold"))
        self.dl_ind_ytdlp.grid(row=0, column=0, padx=8, pady=6)
        self.dl_ind_ytdlp.bind("<Button-1>", lambda e: self._open_ytdlp_settings())
        self.dl_ind_ffmpeg = tk.Label(status, text="", cursor="hand2",
                                      font=("TkDefaultFont", 10, "bold"))
        self.dl_ind_ffmpeg.grid(row=0, column=1, padx=8, pady=6)
        self.dl_ind_ffmpeg.bind("<Button-1>", lambda e: self._open_ffmpeg_settings())
        ttk.Label(status, text=self.t("dep_hint"), foreground="#777"
                  ).grid(row=0, column=2, sticky="e", padx=8)

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
        b_up = ttk.Button(qbtns, text=self.t("move_up"),
                          command=lambda: self._dl_move_selected(-1))
        b_up.pack(side="left", padx=2)
        b_dn = ttk.Button(qbtns, text=self.t("move_down"),
                          command=lambda: self._dl_move_selected(1))
        b_dn.pack(side="left", padx=2)
        self._dl_controls += [b_add, b_rm, b_cl, b_up, b_dn]
        cols = ("order", "video", "length", "status")
        qwrap, self.dl_tree, _dsb = make_scrollable_queue(qf, cols, height=10)
        qwrap.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)
        self.dl_tree.heading("order", text=self.t("col_order"))
        self.dl_tree.heading("video", text=self.t("yt_col_video"))
        self.dl_tree.heading("length", text=self.t("col_length"))
        self.dl_tree.heading("status", text=self.t("col_status"))
        self.dl_tree.column("order", width=40, anchor="center", stretch=False)
        self.dl_tree.column("video", width=460)
        self.dl_tree.column("length", width=90, anchor="center", stretch=False)
        self.dl_tree.column("status", width=160, anchor="center")
        self.dl_summary_var = tk.StringVar(value="")
        ttk.Label(qf, textvariable=self.dl_summary_var, foreground="#444"
                  ).grid(row=2, column=0, sticky="w", padx=6, pady=(0, 4))

        # run controls
        rf = ttk.Frame(root)
        rf.grid(row=5, column=0, sticky="ew", padx=8, pady=4)
        rf.columnconfigure(2, weight=1)
        self.dl_start_btn = ttk.Button(rf, text=self.t("dl_start"), command=self._start_download_batch)
        self.dl_start_btn.grid(row=0, column=0, padx=2)
        self.dl_cancel_btn = ttk.Button(rf, text=self.t("cancel"),
                                        command=self._cancel_download_batch, state="disabled")
        self.dl_cancel_btn.grid(row=0, column=1, padx=2)
        self.dl_open_btn = ttk.Button(rf, text=self.t("open_output_folder"),
                                      command=self._dl_open_output, state="disabled")
        self.dl_open_btn.grid(row=0, column=3, padx=2, sticky="e")
        self.dl_progress = ttk.Progressbar(rf, mode="determinate", maximum=100)
        self.dl_progress.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(6, 0))
        self.dl_progress_pct_var = tk.StringVar(value="")
        self.dl_progress_pct_label = tk.Label(rf, textvariable=self.dl_progress_pct_var,
                                              font=("TkDefaultFont", 8, "bold"),
                                              bg="#e9e9e9", fg="#222", bd=0)
        self.dl_progress_pct_label.place(in_=self.dl_progress, relx=0.5, rely=0.5, anchor="center")
        self.dl_progress_label_var = tk.StringVar(value=self.t("waiting_start"))
        ttk.Label(rf, textvariable=self.dl_progress_label_var, foreground="#555"
                  ).grid(row=2, column=0, columnspan=4, sticky="w", pady=(2, 0))

        # log
        logf = ttk.LabelFrame(root, text=self.t("dl_log_frame"))
        logf.grid(row=6, column=0, sticky="ew", padx=8, pady=4)
        logf.columnconfigure(0, weight=1)
        self.dl_log_text = tk.Text(logf, height=7, wrap="word", state="disabled",
                                   font=("TkFixedFont", 9))
        dsb = ttk.Scrollbar(logf, orient="vertical", command=self.dl_log_text.yview)
        self.dl_log_text.configure(yscrollcommand=dsb.set)
        self.dl_log_text.grid(row=0, column=0, sticky="nsew", padx=(4, 0), pady=4)
        dsb.grid(row=0, column=1, sticky="ns", pady=4)

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
        state = "normal" if (yok and not self.download_is_running) else "disabled"
        if hasattr(self, "dl_start_btn"):
            self.dl_start_btn.configure(state=state)
        # reflect audio-only toggle on first build
        if hasattr(self, "dl_res_combo"):
            self._on_dl_opts_change()

    # ---- download queue ops ----
    def _dl_move_selected(self, direction):
        if self.download_is_running:
            messagebox.showwarning(self.t("warn"), self.t("warn_queue_locked"))
            return
        sel = self.dl_tree.selection()
        if not sel:
            return
        idx = int(sel[0]); new = idx + direction
        if 0 <= new < len(self.download_queue_items):
            self.download_queue_items[idx], self.download_queue_items[new] = \
                self.download_queue_items[new], self.download_queue_items[idx]
            self._render_download_queue()
            self.dl_tree.selection_set(str(new))

    def _dl_remove_selected(self):
        if self.download_is_running:
            messagebox.showwarning(self.t("warn"), self.t("warn_queue_locked"))
            return
        for iid in self.dl_tree.selection():
            idx = int(iid)
            if 0 <= idx < len(self.download_queue_items):
                self.download_queue_items[idx] = None
        self.download_queue_items = [it for it in self.download_queue_items if it is not None]
        self._render_download_queue()
        self._update_download_summary()

    def _dl_clear_queue(self):
        if self.download_is_running:
            messagebox.showwarning(self.t("warn"), self.t("warn_queue_locked"))
            return
        self.download_queue_items = []
        self._render_download_queue()
        self._update_download_summary()

    def _dl_status_text(self, status):
        return {ST_PENDING: self.t("status_pending"),
                ST_RUNNING: self.t("status_running_dl"),
                ST_DONE: self.t("status_done"),
                ST_ERROR: self.t("status_error"),
                ST_SKIPPED: self.t("status_skipped")}.get(status, status)

    def _render_download_queue(self):
        if not hasattr(self, "dl_tree"):
            return
        self.dl_tree.delete(*self.dl_tree.get_children())
        for i, it in enumerate(self.download_queue_items):
            label = it.error_message if (it.status == ST_ERROR and it.error_message) \
                else self._dl_status_text(it.status)
            length = fmt_hms(it.duration) if it.duration else "…"
            self.dl_tree.insert("", "end", iid=str(i),
                                values=(i + 1, it.filename, length, label))

    def _dl_browse_outdir(self):
        d = filedialog.askdirectory(title=self.t("select_output_title"))
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
        if not self.ytdlp_ok:
            messagebox.showerror(self.t("error"), self.t("dl_need_ytdlp"))
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
        self.cfg["download_output_dir"] = out_dir
        self._save_config()
        for it in self.download_queue_items:
            it.status = ST_PENDING
            it.error_message = ""
            it.output_dir = None
        self._render_download_queue()
        audio_only = bool(self.dl_audio_only_var.get())
        res = self.cfg.get("download_resolution", "best")
        prefix = ytdlp_command_prefix(self.python_exe)
        self.download_stop_flag = threading.Event()
        self.download_worker = DownloadWorker(
            items=self.download_queue_items, prefix=prefix, out_dir=out_dir,
            audio_only=audio_only, audio_format=self.cfg.get("download_audio_format", "mp3"),
            resolution=res, container=self.cfg.get("download_container", "mp4"),
            ffmpeg_location=self.ffmpeg_path, strings=self.s,
            event_queue=self.download_event_queue, stop_flag=self.download_stop_flag,
            delay_range=YT_DOWNLOAD_DELAY, progressive=progressive)
        self.download_is_running = True
        self._dl_done = 0
        self._dl_errors = 0
        self._dl_cur_index = 0
        self._dl_total = len(self.download_queue_items)
        self.dl_start_btn.configure(state="disabled")
        self.dl_cancel_btn.configure(state="normal")
        self.dl_open_btn.configure(state="disabled")
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
        elif kind == "dl_progress_index":
            self._dl_cur_index = ev.get("index", 0)
            self._update_dl_progress_label()
        elif kind == "dl_item_status":
            idx = ev.get("index")
            status = ev.get("status")
            if 0 <= idx < len(self.download_queue_items):
                self.download_queue_items[idx].status = status
                if ev.get("error"):
                    self.download_queue_items[idx].error_message = ev["error"]
                self.dl_tree.set(str(idx), "status",
                                 ev.get("error") or self._dl_status_text(status))
            if status in ST_TERMINAL:
                if status == ST_DONE:
                    self._dl_done += 1
                elif status == ST_ERROR:
                    self._dl_errors += 1
                self._update_dl_progress_label()
        elif kind == "dl_batch_blocked":
            messagebox.showwarning(self.t("yt_block_title"),
                                   ev.get("message") or self.t("yt_block_dialog"))
        elif kind == "dl_batch_finished":
            self._on_download_batch_finished()

    def _update_dl_progress_label(self):
        total = max(1, getattr(self, "_dl_total", 1))
        done = self._dl_done + self._dl_errors
        cur = current_processing_index(done, total, self.download_is_running)
        self.dl_progress_label_var.set(self.t("batch_progress", done=cur, total=total))

    def _on_download_batch_finished(self):
        self.download_is_running = False
        self.download_worker = None
        self._set_progress(self.dl_progress, self.dl_progress_pct_var, 100.0)
        self.dl_start_btn.configure(state="normal" if self.ytdlp_ok else "disabled")
        self.dl_cancel_btn.configure(state="disabled")
        self.dl_open_btn.configure(state="normal")
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

    # ---- dictionary tab --------------------------------------------------
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
    # Refresh / state
    # ======================================================================
    def _refresh_status_indicators(self):
        def style(label, name_key, ok):
            mark = self.t("dep_found") if ok else self.t("dep_missing")
            label.configure(text=f"{self.t(name_key)} {mark}",
                            fg=("#1a7f37" if ok else "#cf222e"))
        style(self.ind_whisper, "dep_whisper", bool(self.whisper_path))
        style(self.ind_markitdown, "dep_markitdown", bool(self.markitdown_ok))
        style(self.ind_ffmpeg, "dep_ffmpeg", bool(self.ffmpeg_path))
        self._refresh_youtube_enabled()
        self._refresh_download_enabled()

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
        d = filedialog.askdirectory(title=self.t("select_output_title"))
        if d:
            self.fixed_dir_var.set(d)
            self.cfg["fixed_output_dir"] = d
            self.outdir_mode_var.set("fixed")
            self.cfg["output_dir_mode"] = "fixed"
            self._save_config()

    def _browse_md_fixed_dir(self):
        d = filedialog.askdirectory(title=self.t("select_output_title"))
        if d:
            self.md_fixed_dir_var.set(d)
            self.md_outdir_mode_var.set("fixed")

    # ======================================================================
    # Queue operations (transcription)
    # ======================================================================
    def _add_files(self):
        if self.is_running:
            messagebox.showwarning(self.t("warn"), self.t("warn_queue_locked"))
            return
        paths = filedialog.askopenfilenames(
            title=self.t("select_media_title"),
            filetypes=[(self.t("media_files"), " ".join("*" + e for e in MEDIA_EXTENSIONS)),
                       (self.t("all_files"), "*.*")])
        existing = {it.filepath for it in self.queue_items}
        added = 0
        new_items = []
        for p in paths:
            if p not in existing:
                it = QueueItem(p)
                self.queue_items.append(it)
                new_items.append(it)
                added += 1
        if paths and added == 0:
            messagebox.showinfo(self.t("info"), self.t("info_all_in_queue"))
        self._render_queue()
        self._update_trans_summary()
        if new_items:
            self._probe_media_lengths(new_items)

    def _remove_selected(self):
        if self.is_running:
            messagebox.showwarning(self.t("warn"), self.t("warn_queue_locked"))
            return
        for iid in self.tree.selection():
            idx = int(iid)
            if 0 <= idx < len(self.queue_items):
                self.queue_items[idx] = None
        self.queue_items = [it for it in self.queue_items if it is not None]
        self._render_queue()
        self._update_trans_summary()

    def _clear_queue(self):
        if self.is_running:
            messagebox.showwarning(self.t("warn"), self.t("warn_queue_locked"))
            return
        self.queue_items = []
        self._render_queue()
        self._update_trans_summary()

    def _move_selected(self, direction):
        if self.is_running:
            messagebox.showwarning(self.t("warn"), self.t("warn_queue_locked"))
            return
        sel = self.tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        new = idx + direction
        if 0 <= new < len(self.queue_items):
            self.queue_items[idx], self.queue_items[new] = \
                self.queue_items[new], self.queue_items[idx]
            self._render_queue()
            self.tree.selection_set(str(new))

    def _status_text(self, status):
        return {ST_PENDING: self.t("status_pending"),
                ST_RUNNING: self.t("status_running"),
                ST_DONE: self.t("status_done"),
                ST_ERROR: self.t("status_error"),
                ST_SKIPPED: self.t("status_skipped")}.get(status, status)

    def _render_queue(self):
        self.tree.delete(*self.tree.get_children())
        for i, it in enumerate(self.queue_items):
            length = fmt_hms(it.duration) if it.duration else "…"
            self.tree.insert("", "end", iid=str(i),
                             values=(i + 1, it.filename,
                                     os.path.dirname(it.filepath),
                                     length,
                                     self._status_text(it.status)))

    # ======================================================================
    # Queue operations (MD tab)
    # ======================================================================
    def _md_add_files(self):
        if self.md_is_running:
            messagebox.showwarning(self.t("warn"), self.t("warn_queue_locked"))
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
        for iid in self.md_tree.selection():
            idx = int(iid)
            if 0 <= idx < len(self.md_queue_items):
                self.md_queue_items[idx] = None
        self.md_queue_items = [it for it in self.md_queue_items if it is not None]
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
        self.md_tree.delete(*self.md_tree.get_children())
        for i, it in enumerate(self.md_queue_items):
            size = self._human_bytes(it.size_bytes) if it.size_bytes else "—"
            self.md_tree.insert("", "end", iid=str(i),
                                values=(i + 1, it.filename,
                                        os.path.dirname(it.filepath),
                                        size,
                                        self._md_status_text(it.status)))

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
    def _append_text(self, widget, text):
        try:
            widget.configure(state="normal")
            widget.insert("end", text)
            widget.see("end")
            widget.configure(state="disabled")
        except tk.TclError:
            pass

    def _attach_stream(self, event_queue, log_text, on_finish):
        def poll():
            try:
                while True:
                    ev = event_queue.get_nowait()
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
            self.after(120, poll)
        poll()

    # ======================================================================
    # Settings: Whisper
    # ======================================================================
    def _open_whisper_settings(self, focus=None):
        dlg = tk.Toplevel(self)
        dlg.title(self.t("set_whisper_title"))
        dlg.transient(self)
        dlg.geometry("760x640")
        frm = ttk.Frame(dlg)
        frm.pack(fill="both", expand=True, padx=10, pady=10)
        frm.columnconfigure(0, weight=1)

        # status
        status_var = tk.StringVar()

        def refresh_status():
            self.whisper_path = find_whisper_path(self.cfg.get("whisper_path") or None)
            if self.whisper_path:
                status_var.set(self.t("set_whisper_found", path=self.whisper_path))
            else:
                status_var.set(self.t("set_whisper_missing"))
            self._refresh_status_indicators()
        ttk.Label(frm, textvariable=status_var, foreground="#444",
                  wraplength=720).grid(row=0, column=0, sticky="w", pady=(0, 6))

        # executable row
        exrow = ttk.LabelFrame(frm, text=self.t("set_whisper_exe"))
        exrow.grid(row=1, column=0, sticky="ew", pady=4)
        exrow.columnconfigure(0, weight=1)
        exe_var = tk.StringVar(value=self.cfg.get("whisper_path", ""))
        ttk.Entry(exrow, textvariable=exe_var).grid(row=0, column=0, sticky="ew", padx=6, pady=6)

        def browse_exe():
            p = filedialog.askopenfilename(title=self.t("select_whisper_title"), parent=dlg)
            if p:
                exe_var.set(p)
                self.cfg["whisper_path"] = p
                self._save_config()
                refresh_status()
        ttk.Button(exrow, text=self.t("browse"), command=browse_exe).grid(row=0, column=1, padx=4, pady=6)

        # models manager
        mf = ttk.LabelFrame(frm, text=self.t("set_models_title"))
        mf.grid(row=2, column=0, sticky="nsew", pady=4)
        mf.columnconfigure(0, weight=1)
        frm.rowconfigure(2, weight=1)
        model_list = tk.Listbox(mf, height=8, exportselection=False)
        model_list.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)
        mf.rowconfigure(0, weight=1)

        def fill_models():
            model_list.delete(0, "end")
            for cli in ALL_MODEL_CLIS:
                downloaded, _ = is_model_downloaded(cli)
                tag = self.t("installed_tag") if downloaded else ""
                model_list.insert("end", f"{cli}{tag}  —  {self.t(MODEL_INFO[cli]['desc_key'])}")
        fill_models()

        dl_log = tk.Text(mf, height=6, wrap="word", state="disabled", font=("TkFixedFont", 9))
        dl_log.grid(row=1, column=0, sticky="ew", padx=6, pady=(0, 6))

        def download_model():
            sel = model_list.curselection()
            if not sel:
                return
            cli = ALL_MODEL_CLIS[sel[0]]
            if not self.whisper_path:
                messagebox.showerror(self.t("error"), self.t("err_no_whisper"), parent=dlg)
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

        # install whisper
        irow = ttk.Frame(frm)
        irow.grid(row=3, column=0, sticky="ew", pady=4)
        install_log = tk.Text(irow, height=5, wrap="word", state="disabled", font=("TkFixedFont", 9))

        def install_whisper():
            py = find_python_executable()
            cmd = build_pip_install_command(py, "openai-whisper")
            if not messagebox.askyesno(self.t("confirm"),
                                       self.t("set_whisper_install_q", cmd=" ".join(cmd)),
                                       parent=dlg):
                return
            install_log.grid(row=1, column=0, sticky="ew", pady=(4, 0))
            self._append_text(install_log, self.t("install_running"))
            stop = threading.Event()
            q = queue.Queue()
            worker = CommandStreamWorker(cmd, q, stop, tag="whisper")
            inst_btn.configure(state="disabled")
            worker.start()

            def done(success, error):
                inst_btn.configure(state="normal")
                self._append_text(install_log,
                                  self.t("install_done_ok") if success
                                  else self.t("install_done_fail", code=error))
                refresh_status()
                self._refresh_model_dropdown()
            self._attach_stream(q, install_log, done)
        irow.columnconfigure(0, weight=1)
        inst_btn = ttk.Button(irow, text=self.t("set_whisper_install"), command=install_whisper)
        inst_btn.grid(row=0, column=0, sticky="w")

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
                model_list.focus_set()
            except tk.TclError:
                pass
        elif focus == "langs":
            try:
                lang_list.focus_set()
            except tk.TclError:
                pass

    # ======================================================================
    # Settings: MarkItDown
    # ======================================================================
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
            self.python_exe = markitdown_python(self.cfg)
            self.markitdown_ok = markitdown_is_available(self.python_exe)
            if self.markitdown_ok:
                status_var.set(self.t("set_markitdown_found", py=self.python_exe))
            else:
                status_var.set(self.t("set_markitdown_missing"))
            self._refresh_status_indicators()
        ttk.Label(frm, textvariable=status_var, foreground="#444",
                  wraplength=640).grid(row=1, column=0, sticky="w", pady=4)

        btnrow = ttk.Frame(frm)
        btnrow.grid(row=2, column=0, sticky="w", pady=4)
        log = tk.Text(frm, height=10, wrap="word", state="disabled", font=("TkFixedFont", 9))
        log.grid(row=3, column=0, sticky="nsew", pady=6)

        def install_md():
            py = find_python_executable()
            cmd = build_pip_install_command(py, "markitdown[all]")
            if not messagebox.askyesno(self.t("confirm"),
                                       self.t("set_markitdown_install_q", cmd=" ".join(cmd)),
                                       parent=dlg):
                return
            self._append_text(log, self.t("install_running"))
            stop = threading.Event()
            q = queue.Queue()
            worker = CommandStreamWorker(cmd, q, stop, tag="md")
            inst_btn.configure(state="disabled")
            worker.start()

            def done(success, error):
                inst_btn.configure(state="normal")
                self._append_text(log, self.t("install_done_ok") if success
                                  else self.t("install_done_fail", code=error))
                refresh_status()
            self._attach_stream(q, log, done)
        inst_btn = ttk.Button(btnrow, text=self.t("set_markitdown_install"), command=install_md)
        inst_btn.pack(side="left", padx=2)
        ttk.Button(btnrow, text=self.t("set_recheck"), command=refresh_status).pack(side="left", padx=2)
        ttk.Button(frm, text=self.t("close"), command=dlg.destroy).grid(row=4, column=0, sticky="e", pady=6)
        refresh_status()

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
            p = filedialog.askopenfilename(title=self.t("select_ffmpeg_title"), parent=dlg)
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

        row2 = ttk.Frame(frm)
        row2.grid(row=2, column=0, sticky="w", pady=4)
        log = tk.Text(frm, height=10, wrap="word", state="disabled", font=("TkFixedFont", 9))
        log.grid(row=3, column=0, sticky="nsew", pady=6)

        def auto_install():
            dest = str(FFMPEG_INSTALL_DIR)
            if not messagebox.askyesno(self.t("confirm"),
                                       self.t("set_ffmpeg_auto_q", dest=dest), parent=dlg):
                return
            auto_btn.configure(state="disabled")
            self._start_ffmpeg_auto(log, lambda ok, path: (
                auto_btn.configure(state="normal"), refresh_status()))

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
            self._attach_stream(q, log, done)

        auto_btn = ttk.Button(row2, text=self.t("set_ffmpeg_install_auto"), command=auto_install)
        auto_btn.pack(side="left", padx=2)
        if os.name == "nt":
            ttk.Button(row2, text=self.t("set_ffmpeg_winget"), command=winget_install).pack(side="left", padx=2)
        ttk.Button(row2, text=self.t("set_ffmpeg_open_page"),
                   command=lambda: webbrowser.open(FFMPEG_DOWNLOAD_URL)).pack(side="left", padx=2)
        ttk.Button(frm, text=self.t("close"), command=dlg.destroy).grid(row=4, column=0, sticky="e", pady=6)
        refresh_status()

    def _start_ffmpeg_auto(self, log_text, on_finish):
        q = queue.Queue()

        def work():
            try:
                FFMPEG_INSTALL_DIR.mkdir(parents=True, exist_ok=True)
                url = FFMPEG_WIN_BUILD_URL
                q.put(("log", self.t("set_ffmpeg_downloading")))
                tmp = FFMPEG_INSTALL_DIR / "ffmpeg_download.zip"
                urllib.request.urlretrieve(url, str(tmp))
                q.put(("log", self.t("set_ffmpeg_extracting")))
                exe = extract_ffmpeg_archive(str(tmp), FFMPEG_INSTALL_DIR)
                try:
                    tmp.unlink()
                except OSError:
                    pass
                if not exe:
                    raise RuntimeError("ffmpeg executable not found in archive")
                self.cfg["ffmpeg_path"] = exe
                self._save_config()
                q.put(("done", exe))
            except Exception as e:
                q.put(("fail", str(e)))
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
            ttk.Label(frm, image=self._icon_img).pack(pady=(0, 8))
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
        ttk.Button(frm, text=self.t("close"), command=dlg.destroy).pack(pady=(16, 0))

    def _open_contact_email(self):
        try:
            webbrowser.open("mailto:" + APP_CONTACT)
        except Exception:
            pass

    # ======================================================================
    # Open helpers
    # ======================================================================
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
        if not self.whisper_path:
            messagebox.showerror(self.t("error"), self.t("err_no_whisper"))
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
        self.worker = TranscriptionWorker(
            items=self.queue_items, whisper_exe=self.whisper_path,
            ffmpeg_path=self.ffmpeg_path, lang_param=lang_param, task=task,
            model_name=model, initial_prompt=prompt, replacements=replacements,
            keep_formats=keep, output_dir_mode=self.outdir_mode_var.get(),
            fixed_output_dir=self.fixed_dir_var.get().strip(),
            clip_range=clip_range, strings=self.s,
            event_queue=self.event_queue, stop_flag=self.stop_flag)
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
        self._cur_index = 0
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
            idx = ev.get("index")
            status = ev.get("status")
            if 0 <= idx < len(self.queue_items):
                self.queue_items[idx].status = status
                self.tree.set(str(idx), "status", self._status_text(status))
            if status == ST_RUNNING:
                self._cur_index = idx
                self._cur_position = 0.0
                self._cur_file_start = time.time()
                self._cur_item_duration = (
                    self.queue_items[idx].duration
                    if 0 <= idx < len(self.queue_items) else None)
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
            self._on_batch_finished()

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
        sf = self._get_speed_factor(getattr(self, "_batch_model", ""))
        eta_txt = "—"
        if self._trans_total_seconds and self._trans_total_seconds > 0:
            remaining = max(0.0, self._trans_total_seconds - cumulative)
            eta_txt = fmt_hms(remaining * max(0.01, sf))
        line = (self.t("batch_progress", done=cur, total=total_items)
                + "   ·   " + self.t("status_cur_pos", pos=fmt_hms(self._cur_position))
                + "   ·   " + self.t("status_total_transcribed",
                                     val=fmt_hms(cumulative))
                + "   ·   " + self.t("status_eta_complete", eta=eta_txt))
        self.progress_label_var.set(line)

    def _on_batch_finished(self):
        self.is_running = False
        self.worker = None
        self.progress.stop()
        self._set_progress(self.progress, self.progress_pct_var, 100.0)
        self._set_running_ui(False)
        self._append_text(self.log_text, self.t("log_batch_end",
                                                time=datetime.now().strftime("%H:%M:%S")))
        self.progress_label_var.set(self.t("batch_finished_label",
                                    done=self._batch_done, errors=self._batch_errors))
        if self._batch_errors:
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
        # MarkItDown required only if a non-subtitle file is queued.
        needs_md = any(os.path.splitext(it.filepath)[1].lower() not in SUBTITLE_EXTENSIONS
                       for it in self.md_queue_items)
        if needs_md and not self.markitdown_ok:
            messagebox.showerror(self.t("error"), self.t("err_no_markitdown"))
            self._open_markitdown_settings()
            return
        if self.md_outdir_mode_var.get() == "fixed" and not self.md_fixed_dir_var.get().strip():
            messagebox.showerror(self.t("error"), self.t("err_no_fixed_dir"))
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
            strings=self.s, event_queue=self.md_event_queue, stop_flag=self.md_stop_flag)
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
                self.md_queue_items[idx].status = status
                self.md_tree.set(str(idx), "status", self._md_status_text(status))
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
                or self.download_is_running):
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
        self._update_trans_summary()
        self._update_md_summary()
        self._update_youtube_summary()
        self._update_download_summary()

    def _on_close(self):
        if (self.is_running or self.md_is_running or self.youtube_is_running
                or self.download_is_running):
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
        self.destroy()


def main():
    app = TranscriptLabApp()
    app.mainloop()


if __name__ == "__main__":
    main()
