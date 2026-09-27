# Rebscreen — estado

- Libre Hardware Monitor: REST local `http://127.0.0.1:8085/data.json` é a fonte preferida; WMI permanece só para versões antigas.
- Se LHM estiver instalado mas REST não responder: `Options > Web Server > Run web server` (porta 8085).
- Rebel mostra `Sinal` como download e `Link` como upload, calculados por delta de bytes da interface física ativa.
- Sem build, COM3 ou teste físico nesta rodada. Testes: 45 aprovados.
