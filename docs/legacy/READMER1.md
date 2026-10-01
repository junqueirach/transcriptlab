# Whisper Batch Transcriber — Guia Rapido

## O que e
Uma interface grafica (GUI) em Python/Tkinter para transcrever em lote
videos/audios usando o Whisper da OpenAI, com:

- Fila de arquivos com reordenacao (selecione varias vezes, em pastas diferentes)
- Configuracao feita uma unica vez por lote (idioma, modelo, dicionario)
- Log em tempo real mostrando o Whisper trabalhando (para voce saber que nao travou)
- Barra de progresso geral + posicao atual no audio
- Dicionarios de vocabulario customizados (perfis salvos) para termos especiais
  como "Jan Val Ellam", "Revelacao Cosmica", "Sagrada Familia Cosmica", etc.
- Saida em `.txt` e `.srt` para cada arquivo (os formatos extras do Whisper,
  como `.vtt`/`.json`/`.tsv`, sao gerados e depois removidos automaticamente)
- Continua o lote mesmo se um arquivo falhar (so marca erro e segue para o proximo)
- Botao de cancelar que interrompe com seguranca apos o arquivo atual

## Como executar

1. Tenha o Python instalado no Windows (3.9 ou mais recente). Tkinter ja vem
   incluido — nao precisa instalar nada extra para a interface.
2. Tenha o Whisper instalado (no seu ambiente atual, em
   `C:\WhisperWorkspace\venv\Scripts\whisper.exe`).
3. Execute:
   ```
   python whisper_transcriber.py
   ```
4. Na aba **Transcricao**:
   - Confirme/ajuste o caminho do executavel do whisper (botao "Procurar...").
   - Escolha idioma e modelo.
   - Escolha um dicionario de vocabulario (ou "(Nenhum)").
   - Clique "+ Adicionar arquivos..." (pode repetir varias vezes, inclusive
     de pastas diferentes — os arquivos se acumulam na mesma fila).
   - Use "Mover para cima/baixo" para reordenar antes de iniciar.
   - Clique "Iniciar Transcricao em Lote".
5. Acompanhe o progresso na tabela de status e no log em tempo real.

## Dicionario de Vocabulario — como funciona de verdade

O Whisper (CLI) nao aceita um "glossario" tradicional, mas aceita um parametro
`--initial_prompt`: um texto curto que "engata" o modelo nos termos certos.
Quanto mais natural e parecido com a fala real, melhor o efeito.

Exemplo de bom prompt para o seu caso:
```
Jan Val Ellam fala sobre a Revelacao Cosmica, Sagrada Familia Cosmica,
Plano Causal e Atma.
```

Alem disso, a aba **Dicionarios de Vocabulario** permite configurar
substituicoes automaticas de pos-processamento (aplicadas no `.txt` e `.srt`
depois que o Whisper termina), no formato `errado=correto`, uma por linha.
Util para erros *consistentes* que o priming por si só não corrige
completamente. Exemplo:
```
Jan Val Elam=Jan Val Ellam
val elam=Val Ellam
```

Essas substituicoes sao simples (find/replace de texto), case-sensitive.
Use com cuidado para nao substituir trechos parecidos indesejados.

## Configuracoes salvas

Tanto o caminho do whisper quanto os perfis de dicionario sao salvos
automaticamente em:
```
%USERPROFILE%\.whisper_transcriber\config.json
%USERPROFILE%\.whisper_transcriber\dictionaries.json
```
Voce so precisa configurar uma vez por maquina; nas proximas execucoes
tudo ja vem pre-preenchido.

## Sugestoes de melhoria futura (nao implementadas ainda)

Algumas ideias que podem valer a pena se este fluxo crescer:

1. **Pre-processamento de audio**: extrair so a faixa de audio do `.mkv`/`.mp4`
   com ffmpeg antes de passar pro whisper, o que costuma acelerar bastante
   (whisper processa audio puro mais rapido que video com faixas extras).
2. **Deteccao automatica de silêncio/cortes** para pular trechos sem fala
   (ex: introducoes longas, vinhetas) e economizar tempo de processamento.
3. **Exportar o `.txt` final ja formatado para colar direto numa conversa
   com o Claude** — por exemplo, quebrando em blocos com timestamp a cada
   X minutos, o que ajuda bastante quando voce for usar o texto para estudo
   e quiser perguntar "o que ele disse por volta dos 45 minutos?".
4. **Multiplos dicionarios simultâneos** (ex.: um geral de "Revelacao Cosmica"
   + um especifico de um curso), concatenando os prompts.
5. Se um dia voce quiser rodar isso em lote *sem* abrir a janela (ex.: agendado
   de madrugada), seria simples extrair a logica do `TranscriptionWorker`
   para um script de linha de comando separado, reaproveitando os mesmos
   perfis de dicionario salvos em JSON.

Essas nao foram implementadas porque nao foram pedidas — mas o codigo atual
foi estruturado (worker separado da GUI, JSON para configuracao) de um jeito
que facilita adicionar qualquer uma delas depois, caso queira.
