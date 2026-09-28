# Rebscreen

**Version:** 0.2-beta
**Language / Idioma / Idioma / Lingua / Язык / 语言:** [English](#english) · [Português (Brasil)](#português-brasil) · [Español](#español) · [Italiano](#italiano) · [Русский](#русский) · [简体中文](#简体中文)

The GitHub repository description is a single static field. Use the links above to read the project description in your preferred language.

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

Create the environment and install the application and development dependencies:

```powershell
py -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\pip install -r requirements-dev.txt
```

Run one test file:

```powershell
.\.venv\Scripts\python -m pytest tests\test_media_runtime.py -q
```

Run the complete test suite before opening a Pull Request:

```powershell
.\.venv\Scripts\python -m pytest -q
```

GitHub runs the same checks for every Pull Request and every push to `main`.

The interface supports English, Brazilian Portuguese, Spanish, Italian, Russian, and Simplified Chinese. Rebel and Technical Panel remain available, with Cassette Futurism as an additional visual theme.

### Releases

Executable files are not versioned in this repository. After merging tested code into `main`, create and push a tag in the `vX.Y.Z` format to publish a release. GitHub Actions runs the tests, builds the Windows package, and attaches its ZIP file to the corresponding GitHub Release.

---

## Português (Brasil)

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

Crie o ambiente e instale as dependências do aplicativo e de desenvolvimento:

```powershell
py -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\pip install -r requirements-dev.txt
```

Para rodar apenas um arquivo de teste:

```powershell
.\.venv\Scripts\python -m pytest tests\test_media_runtime.py -q
```

Antes de abrir um Pull Request, rode toda a suíte:

```powershell
.\.venv\Scripts\python -m pytest -q
```

O GitHub executa essa mesma validação em cada Pull Request e em cada envio para `main`.

O programa oferece inglês, português do Brasil, espanhol, italiano, russo e chinês simplificado. Rebel e Painel Técnico continuam disponíveis, junto ao novo tema Cassette Futurism.

### Distribuição

O executável não é versionado neste repositório. Depois de mesclar código testado em `main`, crie e envie uma tag no formato `vX.Y.Z` para publicar uma versão. O GitHub Actions roda os testes, compila o pacote para Windows e anexa o ZIP à Release correspondente.

## Español

Rebscreen es un panel local para Windows que muestra información del sistema y de reproducción multimedia, con soporte opcional para una pantalla USB compatible. La interfaz se puede usar en inglés, portugués de Brasil, español, italiano, ruso y chino simplificado.

Incluye los temas Rebel y Panel técnico, además de Cassette Futurism. Los datos de temperatura y salud de los discos requieren Libre Hardware Monitor con el servidor web local habilitado en el puerto `8085`. Algunas métricas de CPU, GPU y RAM siguen siendo demostrativas y se identifican como tales.

Para ejecutar desde el código fuente, sigue los pasos de instalación de Python indicados en la sección en inglés o portugués de esta página.

## Italiano

Rebscreen è un pannello locale per Windows che mostra informazioni sul sistema e sulla riproduzione multimediale, con supporto opzionale per un display USB compatibile. L'interfaccia è disponibile in inglese, portoghese brasiliano, spagnolo, italiano, russo e cinese semplificato.

Include i temi Rebel e Pannello tecnico, oltre a Cassette Futurism. Le letture reali di temperatura e stato dei dischi richiedono Libre Hardware Monitor con il server web locale attivo sulla porta `8085`. Alcune metriche di CPU, GPU e RAM sono ancora dimostrative e vengono indicate come tali.

Per eseguire il codice sorgente, segui i passaggi di installazione Python nella sezione inglese o portoghese di questa pagina.

## Русский

Rebscreen — локальная панель для Windows с данными о системе и воспроизведении мультимедиа, а также с поддержкой совместимого USB-дисплея. Интерфейс доступен на английском, бразильском португальском, испанском, итальянском, русском и упрощенном китайском языках.

Доступны темы Rebel и «Техническая панель», а также Cassette Futurism. Для получения реальной температуры и состояния дисков требуется Libre Hardware Monitor с локальным веб-сервером на порту `8085`. Некоторые показатели ЦП, ГП и ОЗУ пока демонстрационные и отмечаются соответствующим образом.

Инструкции по запуску исходного кода на Python приведены в английском и португальском разделах этой страницы.

## 简体中文

Rebscreen 是一款适用于 Windows 的本地面板，可显示系统和媒体播放信息，并可选支持兼容的 USB 显示屏。界面支持英语、巴西葡萄牙语、西班牙语、意大利语、俄语和简体中文。

软件保留 Rebel 和技术面板主题，并新增磁带未来主义主题。要获取真实的磁盘温度和健康状态，需要在 `8085` 端口启用 Libre Hardware Monitor 本地 Web 服务器。部分 CPU、GPU 和内存指标仍为演示数据，并会明确标注。

Python 源码运行步骤请参阅本页的英文或葡萄牙语部分。
