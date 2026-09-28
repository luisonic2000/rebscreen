# Rebscreen — próximas ondas

1. Telemetria real: substituir as amostras de CPU, GPU e RAM por leitores locais verificáveis, mantendo um estado explícito de indisponibilidade quando não houver fonte.
2. Validação manual de discos: confirmar nomes, unidades, SMART e temperaturas reais com Libre Hardware Monitor publicado localmente.
3. Interface: revisar edição de layout e gráficos no uso diário, principalmente as três páginas e os controles do painel `Tela USB`.
4. Renderização: extrair o renderizador de quadros gradualmente do `app.py`, preservando Rebel e Painel Técnico em cada mudança.
5. Antes de um executável: validar manualmente a orientação e um envio USB iniciado pelo usuário. Builds não fazem parte do ciclo normal de desenvolvimento.
