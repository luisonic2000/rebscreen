# Rebscreen — testes

```powershell
Set-Location 'J:\Projetos Codex\Rebscreen\Finais\github-rebscreen-beta'
py -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\pip install -r requirements-dev.txt
```

Um arquivo de teste:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_media_runtime.py -q
```

Suíte completa:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Os testes não devem acessar Spotify, VLC, GSMTC, Libre Hardware Monitor ou COM3. O próximo passo amplia o laboratório controlado com provedores falsos para mídia, sensores e serial, mas ainda testando os caminhos reais do Rebscreen.
