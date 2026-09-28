# Rebscreen — estado

- Fonte oficial de desenvolvimento: este repositório, na branch local `codex/test-foundation` durante esta rodada. Nenhum commit foi enviado ao GitHub.
- Temas suportados: `Rebel` (padrão) e `Painel Técnico` (alternativo).
- A prévia possui três páginas: Monitor, Player e Processos. A rotação inclui as três e configurações antigas de duas páginas são migradas.
- Telemetria: CPU, GPU e RAM ainda são amostras de demonstração, identificadas visualmente. Elas não geram alertas. Inventário, uso e sensores de discos podem usar fontes locais quando disponíveis.
- Libre Hardware Monitor: REST local `http://127.0.0.1:8085/data.json` é preferido. Se não responder, ative `Options > Web Server > Run web server` na porta 8085; WMI é apenas alternativa legada.
- `Sinal` é download e `Link` é upload, calculados por delta da interface física ativa.
- Envio USB automático é opt-in, inicia desligado e tem cadência mínima de 30 s. O protocolo e o firmware não foram modificados.
- Nesta rodada não houve build, acesso a COM3 ou teste físico. A última suíte local passou com 73 testes.
