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

Os testes não acessam Spotify, VLC, GSMTC, Libre Hardware Monitor ou COM3. O laboratório controlado usa provedores falsos para mídia, sensores e serial, porém executa os métodos reais do Rebscreen para validar: consulta de mídia lenta fora da interface, aplicação de mídia concluída, atualização da prévia e codificação de um quadro RGB565 completo.
