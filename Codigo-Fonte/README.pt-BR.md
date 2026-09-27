# Rebscreen

Painel local para Windows com Monitor, Player e tela USB compatível opcional.

## Executar do código

```powershell
py -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\python app.py
```

O tema padrão de primeira instalação é **Rebel**. Preferências existentes em `%LOCALAPPDATA%\Rebscreen` não são substituídas.

Temperatura e SMART reais exigem Libre Hardware Monitor com `Options > Web Server > Run web server` ativo (porta 8085). O aplicativo abre sem ele e mostra `Indisponível` para sensores não publicados.
