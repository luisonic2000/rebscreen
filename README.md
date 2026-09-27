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

## Desenvolvimento

Antes de abrir um Pull Request, rode os testes:

```powershell
.\.venv\Scripts\python -m pytest -q
```

O GitHub executa essa mesma validação em cada Pull Request e em cada envio para `main`.

## Distribuição

O executável não é versionado no repositório. Para publicar uma versão, crie e envie uma tag no formato `vX.Y.Z` depois de mesclar o código testado em `main`. O GitHub Actions testa, compila o pacote Windows e anexa o ZIP à Release correspondente.
