import os
import sys
import subprocess

def run_whisper():
    # 1. Scan current directory for media files
    current_dir = os.getcwd()
    extensions = ('.mkv', '.mp4', '.mp3')
    files = [f for f in os.listdir(current_dir) if f.lower().endswith(extensions)]
    
    if not files:
        print("\n[ERRO] Nenhum arquivo .mkv, .mp4 ou .mp3 encontrado nesta pasta.")
        print("Coloque este script na mesma pasta dos seus videos/audios.\n")
        input("Pressione Enter para sair...")
        sys.exit()
        
    # 2. File Selection Menu
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print("=======================================================")
        print("          WHISPER AUTOMATIC TRANSCRIBER (PYTHON)")
        print("=======================================================")
        print("Escaneando a pasta por arquivos de midia...\n")
        for idx, file in enumerate(files, 1):
            print(f"[{idx}] {file}")
        print(f"[{len(files) + 1}] Cancelar e Sair")
        print("=======================================================")
        
        try:
            choice = int(input("Escolha o numero do arquivo para transcrever: "))
            if choice == len(files) + 1:
                sys.exit()
            if 1 <= choice <= len(files):
                selected_file = files[choice - 1]
                break
        except ValueError:
            pass

    # 3. Language Selection Menu
    languages = {"1": ("Portuguese", "Portugues"), "2": ("English", "Ingles"), "3": ("Spanish", "Espanhol")}
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print("=======================================================")
        print(f"Arquivo Selecionado: {selected_file}")
        print("=======================================================")
        print("[PASSO 1/2] Escolha o idioma do audio original:")
        print("[1] Portugues (PT-BR)")
        print("[2] Ingles (EN)")
        print("[3] Espanhol (ES)")
        print("=======================================================")
        lang_choice = input("Digite o numero da sua opcao (1-3): ").strip()
        if lang_choice in languages:
            lang_param, lang_name = languages[lang_choice]
            break

    # 4. Model Selection Menu
    models = {"1": "turbo", "2": "medium", "3": "small"}
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print("=======================================================")
        print(f"Arquivo: {selected_file}")
        print(f"Idioma:  {lang_name}")
        print("=======================================================")
        print("[PASSO 2/2] Escolha o modelo de Inteligencia Artificial:")
        print("[1] Turbo  (Melhor precisao, otima velocidade)")
        print("[2] Medium (Excelente precisao, ideal p/ PT-BR)")
        print("[3] Small  (Mais leve e rapido, precisao boa)")
        print("=======================================================")
        model_choice = input("Digite o numero da sua opcao (1-3): ").strip()
        if model_choice in models:
            whisper_model = models[model_choice]
            break

    # 5. Execution Block
    os.system('cls' if os.name == 'nt' else 'clear')
    print("=======================================================")
    print("                  Executando Whisper")
    print("=======================================================")
    print(f"Arquivo: {selected_file}")
    print(f"Idioma:  {lang_param}")
    print(f"Modelo:  {whisper_model}")
    print("\nProcessando... Por favor, aguarde.")
    print("=======================================================\n")

    # Define the absolute target path to the executable inside the virtual environment
    whisper_exe = r"C:\WhisperWorkspace\venv\Scripts\whisper.exe"
    
    # Fallback to standard command if the script path is modified in the future
    if not os.path.exists(whisper_exe):
        whisper_exe = "whisper"

    # Build the exact execution command
    cmd = [
        whisper_exe,
        selected_file,
        "--model", whisper_model,
        "--language", lang_param,
        "--fp16", "False",
        "--output_dir", current_dir
    ]
    
    # shell=True handles Windows pathing mechanics without triggering file search crashes
    subprocess.run(cmd, shell=True)
    
    print("\n=======================================================")
    print("Transcricao concluida com sucesso!")
    print("Os arquivos foram salvos nesta mesma pasta.")
    print("=======================================================")
    input("\nPressione qualquer tecla para fechar...")

if __name__ == "__main__":
    run_whisper()