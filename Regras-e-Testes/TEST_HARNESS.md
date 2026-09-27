# Telinha — testes

```powershell
Set-Location 'J:\Projetos Codex\Telinha\Projeto'
.\.venv\Scripts\python.exe -m pytest -q
```

Os testes usam dados falsos e não acessam Spotify, VLC, GSMTC ou COM3. Cobrem mídia, perfis, migração sem letras, fechamento, rotação, alertas, armazenamento sem sensores e brilho de prévia.
