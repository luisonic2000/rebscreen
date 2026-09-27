# Rebscreen

## English

Rebscreen is a local Windows panel for system monitoring, media playback information, and an optional compatible USB display.

### Run from source

```powershell
py -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\python app.py
```

The default theme for a new installation is **Rebel**. Existing preferences in `%LOCALAPPDATA%\Rebscreen` are preserved.

Real temperature and SMART readings require Libre Hardware Monitor with `Options > Web Server > Run web server` enabled on port `8085`. The app still opens without it and shows `Unavailable` for sensors that are not published.

### Development

Run the test suite before opening a Pull Request:

```powershell
.\.venv\Scripts\python -m pytest -q
```

GitHub runs the same checks for every Pull Request and every push to `main`.

### Releases

Executable files are not versioned in this repository. After merging tested code into `main`, create and push a tag in the `vX.Y.Z` format to publish a release. GitHub Actions runs the tests, builds the Windows package, and attaches its ZIP file to the corresponding GitHub Release.

---

## Português

Rebscreen é um painel local para Windows com monitoramento do sistema, informações de reprodução de mídia e suporte opcional a uma tela USB compatível.

### Executar do código-fonte

```powershell
py -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\python app.py
```

O tema padrão de uma nova instalação é **Rebel**. Preferências existentes em `%LOCALAPPDATA%\Rebscreen` são preservadas.

Temperatura e SMART reais exigem o Libre Hardware Monitor com `Options > Web Server > Run web server` ativado na porta `8085`. O aplicativo continua abrindo sem ele e mostra `Indisponível` para sensores que não foram publicados.

### Desenvolvimento

Antes de abrir um Pull Request, rode os testes:

```powershell
.\.venv\Scripts\python -m pytest -q
```

O GitHub executa essa mesma validação em cada Pull Request e em cada envio para `main`.

### Distribuição

O executável não é versionado neste repositório. Depois de mesclar código testado em `main`, crie e envie uma tag no formato `vX.Y.Z` para publicar uma versão. O GitHub Actions roda os testes, compila o pacote para Windows e anexa o ZIP à Release correspondente.
