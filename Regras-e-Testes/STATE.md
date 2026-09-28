# Rebscreen 0.2-beta — estado

- A branch de trabalho é `main`. Nenhum commit, push, tag ou Release foi criado nesta rodada.
- Temas: Rebel (padrão), Painel Técnico e Cassette Futurism, cada um renderizado pelo quadro compartilhado 320×480.
- Idiomas: inglês padrão, português do Brasil, espanhol, italiano, russo e chinês simplificado. A escolha é salva em `%LOCALAPPDATA%\Rebscreen\settings.json`.
- O seletor do README dá acesso às descrições nos seis idiomas. A descrição curta About do GitHub permanece um texto estático e não foi alterada remotamente.
- `Como resolver` gera um TXT UTF-8 no idioma escolhido quando sensores, mídia, USB serial, telemetria de processos ou bandeja opcional não estão disponíveis.
- CPU, GPU e RAM continuam sendo dados de demonstração identificados; seus alertas permanecem desativados. Sensores de disco dependem das fontes locais configuradas.
- A suíte completa passou com 98 testes e um aviso de depreciação Pillow em `screen_transport.py` (`Image.getdata`). Sem build, acesso a COM ou validação física nesta rodada.
- Quatro arquivos de telemetria/testes previamente modificados pelo Codex e dois itens não rastreados foram preservados sem alteração.