"""Small, dependency-free translation catalogs for Rebscreen."""
from __future__ import annotations

import re


DEFAULT_LANGUAGE = "en"
LANGUAGES = ("en", "pt-BR", "es", "it", "ru", "zh-CN")
LANGUAGE_NAMES = {
    "en": "English",
    "pt-BR": "Português (Brasil)",
    "es": "Español",
    "it": "Italiano",
    "ru": "Русский",
    "zh-CN": "简体中文",
}

_MESSAGES: dict[str, tuple[str, ...]] = {
    "language.label": ("Language", "Idioma", "Idioma", "Lingua", "Язык", "语言"),
    "app.subtitle": ("Local preview and display controls", "Prévia local e controles da tela", "Vista previa y controles locales", "Anteprima e controlli locali", "Локальный просмотр и управление дисплеем", "本地预览和显示控制"),
    "page.monitor": ("Monitor", "Monitor", "Monitor", "Monitor", "Монитор", "监控"),
    "page.player": ("Player", "Player", "Reproductor", "Lettore", "Плеер", "播放器"),
    "page.processes": ("Processes", "Processos", "Procesos", "Processi", "Процессы", "进程"),
    "page.caption": ("Page {current} of 3 — {name}", "Página {current} de 3 — {name}", "Página {current} de 3 — {name}", "Pagina {current} di 3 — {name}", "Страница {current} из 3 — {name}", "第 {current}/3 页 — {name}"),
    "orientation.label": ("Preview orientation", "Orientação da prévia", "Orientación de vista previa", "Orientamento anteprima", "Ориентация просмотра", "预览方向"),
    "orientation.vertical": ("Vertical", "Vertical", "Vertical", "Verticale", "Вертикальная", "竖屏"),
    "orientation.horizontal": ("Horizontal", "Horizontal", "Horizontal", "Orizzontale", "Горизонтальная", "横屏"),
    "orientation.inverted": ("Upside down", "De cabeça para baixo", "Boca abajo", "Capovolta", "Перевернутая", "倒置"),
    "action.toggle_theme": ("Toggle light/dark", "Alternar claro/escuro", "Cambiar claro/oscuro", "Alterna chiaro/scuro", "Сменить светлую/темную тему", "切换浅色/深色"),
    "action.save": ("Save settings", "Salvar configuração", "Guardar configuración", "Salva impostazioni", "Сохранить настройки", "保存设置"),
    "status.saved": ("Settings saved.", "Configuração salva.", "Configuración guardada.", "Impostazioni salvate.", "Настройки сохранены.", "设置已保存。"),
    "tab.overview": ("Overview", "Resumo", "Resumen", "Panoramica", "Обзор", "概览"),
    "tab.appearance": ("Appearance", "Aparência", "Apariencia", "Aspetto", "Внешний вид", "外观"),
    "tab.alerts": ("Alerts", "Alertas", "Alertas", "Avvisi", "Оповещения", "提醒"),
    "tab.display": ("USB display", "Tela USB", "Pantalla USB", "Display USB", "USB-дисплей", "USB 显示屏"),
    "state.title": ("Status", "Estado", "Estado", "Stato", "Состояние", "状态"),
    "state.sensor_checking": ("Checking disk sensors…", "Verificando sensores de disco…", "Buscando sensores de disco…", "Controllo sensori disco…", "Проверка датчиков диска…", "正在检查磁盘传感器…"),
    "state.media_checking": ("Checking media…", "Verificando mídia…", "Buscando medios…", "Controllo contenuti…", "Проверка мультимедиа…", "正在检查媒体…"),
    "state.display_checking": ("Checking compatible display…", "Procurando tela compatível…", "Buscando pantalla compatible…", "Ricerca display compatibile…", "Поиск совместимого дисплея…", "正在查找兼容显示屏…"),
    "state.display_auto": ("The display updates automatically when connected.", "A tela é atualizada automaticamente quando estiver conectada.", "La pantalla se actualiza automáticamente al conectarla.", "Il display si aggiorna automaticamente quando è collegato.", "При подключении дисплей обновляется автоматически.", "连接后显示屏会自动更新。"),
    "appearance.title": ("Appearance", "Aparência", "Apariencia", "Aspetto", "Внешний вид", "外观"),
    "appearance.accent": ("Accent color", "Cor de destaque", "Color de énfasis", "Colore accento", "Цвет акцента", "强调色"),
    "appearance.panel_theme": ("Panel theme", "Tema do painel", "Tema del panel", "Tema del pannello", "Тема панели", "面板主题"),
    "appearance.apply_theme": ("Apply theme and layout", "Aplicar tema e layout", "Aplicar tema y diseño", "Applica tema e layout", "Применить тему и макет", "应用主题和布局"),
    "appearance.telemetry_style": ("Telemetry view", "Visual da telemetria", "Vista de telemetría", "Vista telemetria", "Вид телеметрии", "遥测视图"),
    "appearance.cards": ("Cards", "Cartões", "Tarjetas", "Schede", "Карточки", "卡片"),
    "appearance.graph": ("Graph", "Gráfico", "Gráfico", "Grafico", "График", "图表"),
    "appearance.apply": ("Apply view", "Aplicar visual", "Aplicar vista", "Applica vista", "Применить вид", "应用视图"),
    "layout.edit": ("Edit preview layout", "Editar layout da prévia", "Editar diseño de vista previa", "Modifica layout anteprima", "Изменить макет просмотра", "编辑预览布局"),
    "layout.instruction": ("Select and drag an item to edit it.", "Clique em um item da prévia para editar.", "Selecciona y arrastra un elemento para editarlo.", "Seleziona e trascina un elemento per modificarlo.", "Выберите и перетащите элемент для редактирования.", "选择并拖动项目以进行编辑。"),
    "layout.edit_off": ("Editing is off.", "Edição desligada.", "Edición desactivada.", "Modifica disattivata.", "Редактирование выключено.", "编辑已关闭。"),
    "layout.profile_saved": ("Drag items; the {profile} profile saves automatically.", "Arraste os itens; o perfil {profile} é salvo automaticamente.", "Arrastra elementos; el perfil {profile} se guarda automáticamente.", "Trascina gli elementi; il profilo {profile} viene salvato automaticamente.", "Перетаскивайте элементы; профиль {profile} сохраняется автоматически.", "拖动项目；{profile} 配置会自动保存。"),
    "fonts.custom": ("Use custom fonts", "Usar fontes personalizadas", "Usar fuentes personalizadas", "Usa caratteri personalizzati", "Использовать пользовательские шрифты", "使用自定义字体"),
    "layout.font_size": ("Font size", "Tamanho da fonte", "Tamaño de fuente", "Dimensione carattere", "Размер шрифта", "字体大小"),
    "layout.selected": ("Selected item: {item}", "Item selecionado: {item}", "Elemento seleccionado: {item}", "Elemento selezionato: {item}", "Выбранный элемент: {item}", "已选项目：{item}"),
    "color.text": ("Text color", "Cor do texto", "Color del texto", "Colore testo", "Цвет текста", "文字颜色"),
    "color.accent": ("Accent/line color", "Cor de destaque/linha", "Color de énfasis/línea", "Colore accento/linea", "Цвет акцента/линии", "强调色/线条颜色"),
    "color.background": ("Background color", "Cor de fundo", "Color de fondo", "Colore sfondo", "Цвет фона", "背景颜色"),
    "color.alert": ("Alert color", "Cor de alerta", "Color de alerta", "Colore avviso", "Цвет предупреждения", "警报颜色"),
    "color.transparent": ("Transparent background", "Fundo transparente", "Fondo transparente", "Sfondo trasparente", "Прозрачный фон", "透明背景"),
    "color.reset": ("Reset item colors", "Restaurar cores do item", "Restablecer colores del elemento", "Reimposta colori elemento", "Сбросить цвета элемента", "重置项目颜色"),
    "layout.reset": ("Reset item", "Restaurar item", "Restablecer elemento", "Reimposta elemento", "Сбросить элемент", "重置项目"),
    "layout.move_up": ("Move up", "Subir", "Subir", "Sposta su", "Переместить вверх", "上移"),
    "layout.move_down": ("Move down", "Descer", "Bajar", "Sposta giù", "Переместить вниз", "下移"),
    "layout.resize": ("Resize", "+ Tamanho", "Cambiar tamaño", "Ridimensiona", "Изменить размер", "调整大小"),
    "layout.restore": ("Restore layout", "Restaurar layout", "Restablecer diseño", "Ripristina layout", "Восстановить макет", "恢复布局"),
    "appearance.font_scale": ("Font scale", "Escala de fonte", "Escala de fuente", "Scala carattere", "Масштаб шрифта", "字体缩放"),
    "rotation.title": ("Page rotation", "Rotação de páginas", "Rotación de páginas", "Rotazione pagine", "Смена страниц", "页面轮换"),
    "rotation.toggle": ("Rotate pages automatically", "Alternar páginas", "Cambiar páginas automáticamente", "Ruota pagine automaticamente", "Автоматически переключать страницы", "自动轮换页面"),
    "rotation.hint": ("Manual navigation is always available.", "A navegação manual continua disponível.", "La navegación manual siempre está disponible.", "La navigazione manuale è sempre disponibile.", "Ручная навигация всегда доступна.", "始终可以手动切换。"),
    "alerts.title": ("Alerts", "Alertas", "Alertas", "Avvisi", "Оповещения", "提醒"),
    "alerts.ram": ("RAM usage", "Uso de RAM", "Uso de RAM", "Uso RAM", "Использование ОЗУ", "内存使用率"),
    "metric.cpu": ("CPU", "CPU", "CPU", "CPU", "ЦП", "CPU"),
    "metric.gpu": ("GPU", "GPU", "GPU", "GPU", "ГП", "GPU"),
    "metric.ram": ("RAM", "RAM", "RAM", "RAM", "ОЗУ", "内存"),
    "metric.disks": ("Disks", "Discos", "Discos", "Dischi", "Диски", "磁盘"),
    "alerts.restore": ("Restore recommended limits", "Restaurar recomendações", "Restaurar límites recomendados", "Ripristina limiti consigliati", "Восстановить рекомендуемые пределы", "恢复建议阈值"),
    "alerts.recommended": ("Recommended: CPU 85 °C · GPU 82 °C · disks 60 °C", "Recomendado: CPU 85 °C · GPU 82 °C · discos 60 °C", "Recomendado: CPU 85 °C · GPU 82 °C · discos 60 °C", "Consigliato: CPU 85 °C · GPU 82 °C · dischi 60 °C", "Рекомендуется: ЦП 85 °C · ГП 82 °C · диски 60 °C", "建议值：CPU 85 °C · GPU 82 °C · 磁盘 60 °C"),
    "display.port": ("Port", "Porta", "Puerto", "Porta", "Порт", "端口"),
    "display.brightness": ("Display brightness", "Brilho da tela", "Brillo de pantalla", "Luminosità display", "Яркость дисплея", "显示屏亮度"),
    "display.check_port": ("Check port", "Verificar porta", "Comprobar puerto", "Verifica porta", "Проверить порт", "检查端口"),
    "display.send_preview": ("Send this preview", "Enviar esta prévia", "Enviar esta vista previa", "Invia questa anteprima", "Отправить этот просмотр", "发送此预览"),
    "display.calibrate": ("Send color calibration", "Enviar calibração de cores", "Enviar calibración de color", "Invia calibrazione colori", "Отправить цветовую калибровку", "发送颜色校准"),
    "display.auto_send": ("Automatic USB updates", "Atualização automática USB", "Actualización USB automática", "Aggiornamento USB automatico", "Автообновление USB", "自动 USB 更新"),
    "display.interval": ("USB interval (seconds)", "Cadência USB (segundos)", "Intervalo USB (segundos)", "Intervallo USB (secondi)", "Интервал USB (секунды)", "USB 间隔（秒）"),
    "display.auto_hint": ("Off by default. First sync is slow; changed regions may update every second.", "Desligada por padrão. A primeira sincronização é lenta; regiões alteradas podem atualizar a cada segundo.", "Desactivada de forma predeterminada. La primera sincronización es lenta; las regiones modificadas pueden actualizarse cada segundo.", "Disattivato per impostazione predefinita. La prima sincronizzazione è lenta; le aree modificate possono aggiornarsi ogni secondo.", "По умолчанию выключено. Первая синхронизация выполняется медленно; измененные области могут обновляться каждую секунду.", "默认关闭。首次同步较慢；变化区域可每秒更新。"),
    "media.title": ("Media", "Mídia", "Contenido", "Contenuti", "Мультимедиа", "媒体"),
    "media.start_player": ("Start Spotify or another supported player.", "Inicie o Spotify ou outro player compatível.", "Inicia Spotify u otro reproductor compatible.", "Avvia Spotify o un altro lettore supportato.", "Запустите Spotify или другой поддерживаемый плеер.", "启动 Spotify 或其他受支持的播放器。"),
    "media.diagnostics": ("Media diagnostics", "Diagnóstico de mídia", "Diagnóstico de medios", "Diagnostica contenuti", "Диагностика мультимедиа", "媒体诊断"),
    "media.refresh": ("Refresh media now", "Atualizar mídia agora", "Actualizar medios ahora", "Aggiorna contenuti", "Обновить мультимедиа", "立即刷新媒体"),
    "media.background_hint": ("Media checks run in the background; navigation stays manual.", "A mídia é verificada em segundo plano; a navegação continua manual.", "La búsqueda de medios ocurre en segundo plano; la navegación sigue siendo manual.", "La ricerca dei contenuti avviene in background; la navigazione resta manuale.", "Мультимедиа проверяется в фоне; навигация остается ручной.", "媒体检查在后台进行；页面仍可手动切换。"),
    "theme.rebel": ("Rebel", "Rebel", "Rebel", "Rebel", "Rebel", "Rebel"),
    "theme.technical": ("Technical Panel", "Painel Técnico", "Panel técnico", "Pannello tecnico", "Техническая панель", "技术面板"),
    "theme.cassette": ("Cassette Futurism", "Cassette Futurism", "Futurismo de casete", "Futurismo a cassette", "Кассетный футуризм", "磁带未来主义"),
    "theme.applied": ("{theme} theme and layout applied.", "Tema e layout {theme} aplicados.", "Tema y diseño {theme} aplicados.", "Tema e layout {theme} applicati.", "Тема и макет «{theme}» применены.", "已应用 {theme} 主题和布局。"),
    "screen.processes": ("PROCESSES", "PROCESSOS", "PROCESOS", "PROCESSI", "ПРОЦЕССЫ", "进程"),
    "screen.disk_health": ("HEALTH", "SAÚDE", "SALUD", "SALUTE", "ЗДОРОВЬЕ", "健康"),
    "screen.temperature": ("TEMP.", "TEMP.", "TEMP.", "TEMP.", "ТЕМП.", "温度"),
    "screen.signal": ("SIGNAL", "SINAL", "SEÑAL", "SEGNALE", "СИГНАЛ", "信号"),
    "screen.link": ("LINK", "LINK", "ENLACE", "COLLEGAMENTO", "КАНАЛ", "链路"),
    "screen.download": ("DOWNLOAD", "DOWNLOAD", "DESCARGA", "DOWNLOAD", "ЗАГРУЗКА", "下载"),
    "screen.upload": ("UPLOAD", "UPLOAD", "SUBIDA", "CARICAMENTO", "ОТПРАВКА", "上传"),
    "screen.not_available": ("N/A", "INDISPONÍVEL", "NO DISPONIBLE", "NON DISPONIBILE", "НЕДОСТУПНО", "不可用"),
    "screen.demo_data_short": ("DEMO DATA", "DADOS DEMO", "DATOS DEMO", "DATI DEMO", "ДЕМО-ДАННЫЕ", "演示数据"),
    "screen.demo_notice": ("DEMO: {items}", "DEMO: {items}", "DEMO: {items}", "DEMO: {items}", "ДЕМО: {items}", "演示：{items}"),
    "screen.top_processes": ("TOP 10 // CPU   RAM   DISK   NETWORK", "TOP 10 // CPU   RAM   DISCO   REDE", "TOP 10 // CPU   RAM   DISCO   RED", "TOP 10 // CPU   RAM   DISCO   RETE", "ТОП 10 // ЦП   ОЗУ   ДИСК   СЕТЬ", "前 10 // CPU   内存   磁盘   网络"),
    "screen.collecting": ("COLLECTING PROCESSES…", "COLETANDO PROCESSOS…", "RECOPILANDO PROCESOS…", "RACCOLTA PROCESSI…", "СБОР ПРОЦЕССОВ…", "正在收集进程…"),
    "screen.process_order": ("SORT: CPU / RAM / DISK / NETWORK", "ORDEM: CPU / RAM / DISCO / REDE", "ORDEN: CPU / RAM / DISCO / RED", "ORDINE: CPU / RAM / DISCO / RETE", "СОРТИРОВКА: ЦП / ОЗУ / ДИСК / СЕТЬ", "排序：CPU / 内存 / 磁盘 / 网络"),
    "screen.monitor": ("MONITOR", "MONITOR", "MONITOR", "MONITOR", "МОНИТОР", "监控"),
    "screen.player": ("NOW PLAYING", "TOCANDO AGORA", "REPRODUCIENDO", "IN RIPRODUZIONE", "СЕЙЧАС ИГРАЕТ", "正在播放"),
    "screen.no_cover": ("NO COVER", "SEM CAPA", "SIN CARÁTULA", "SENZA COPERTINA", "НЕТ ОБЛОЖКИ", "无封面"),
    "screen.source_unknown": ("Unknown source", "Fonte não identificada", "Fuente desconocida", "Fonte sconosciuta", "Неизвестный источник", "未知来源"),
    "screen.demo": ("DEMO", "DEMO", "DEMO", "DEMO", "ДЕМО", "演示"),
    "screen.ram_in_use": ("IN USE", "EM USO", "EN USO", "IN USO", "ИСПОЛЬЗУЕТСЯ", "使用中"),
    "screen.disk_usage_temp": ("DISKS // USAGE + TEMPERATURE", "DISCOS // USO + TEMPERATURA", "DISCOS // USO + TEMPERATURA", "DISCHI // USO + TEMPERATURA", "ДИСКИ // НАГРУЗКА + ТЕМПЕРАТУРА", "磁盘 // 使用率 + 温度"),
    "screen.history_labels": ("USAGE / SYSTEM TEMP / DISK TEMP", "USO / TEMP SISTEMA / TEMP DISCOS", "USO / TEMP. SISTEMA / TEMP. DISCOS", "USO / TEMP. SISTEMA / TEMP. DISCHI", "НАГРУЗКА / ТЕМП. СИСТЕМЫ / ДИСКА", "使用率 / 系统温度 / 磁盘温度"),
    "screen.stable": ("SYSTEM STABLE // ALERTS STANDBY", "SISTEMA ESTÁVEL // ALERTAS EM ESPERA", "SISTEMA ESTABLE // ALERTAS EN ESPERA", "SISTEMA STABILE // AVVISI IN ATTESA", "СИСТЕМА СТАБИЛЬНА // ОЖИДАНИЕ", "系统稳定 // 提醒待命"),
    "screen.no_disks": ("NO DISKS DETECTED", "NENHUM DISCO DETECTADO", "NO SE DETECTARON DISCOS", "NESSUN DISCO RILEVATO", "ДИСКИ НЕ ОБНАРУЖЕНЫ", "未检测到磁盘"),
    "screen.no_volume": ("NO VOLUME", "SEM UNIDADE", "SIN UNIDAD", "NESSUNA UNITÀ", "НЕТ ТОМОВ", "无卷"),
    "screen.cpu_history": ("CPU // LAST 60 SECONDS", "CPU // ÚLTIMOS 60 SEGUNDOS", "CPU // ÚLTIMOS 60 SEGUNDOS", "CPU // ULTIMI 60 SECONDI", "ЦП // ПОСЛЕДНИЕ 60 СЕКУНД", "CPU // 最近 60 秒"),
    "screen.last_60": ("LAST 60 SECONDS", "ÚLTIMOS 60 SEGUNDOS", "ÚLTIMOS 60 SEGUNDOS", "ULTIMI 60 SECONDI", "ПОСЛЕДНИЕ 60 СЕКУНД", "最近 60 秒"),
    "screen.now": ("NOW", "AGORA", "AHORA", "ORA", "СЕЙЧАС", "现在"),
    "screen.alert_monitoring": ("ALERTS: monitoring active", "ALERTAS: monitoramento ativo", "ALERTAS: monitorización activa", "AVVISI: monitoraggio attivo", "ОПОВЕЩЕНИЯ: МОНИТОРИНГ АКТИВЕН", "提醒：监控已启用"),
    "screen.monitor_pc": ("PC MONITOR", "MONITOR DO PC", "MONITOR DEL PC", "MONITOR PC", "МОНИТОР ПК", "电脑监控"),
    "screen.demo_data": ("Demonstration data", "Dados de demonstração", "Datos de demostración", "Dati dimostrativi", "Демонстрационные данные", "演示数据"),
    "screen.storage": ("STORAGE", "ARMAZENAMENTO", "ALMACENAMIENTO", "ARCHIVIAZIONE", "ХРАНИЛИЩЕ", "存储"),
    "screen.next_page_hint": ("Use Next page to check the cycle.", "Use Próxima página para conferir o ciclo.", "Usa Página siguiente para comprobar el ciclo.", "Usa Pagina successiva per verificare il ciclo.", "Нажмите «Следующая страница», чтобы проверить цикл.", "使用“下一页”查看轮换。"),
    "screen.telemetry": ("TELEMETRY", "TELEMETRIA", "TELEMETRÍA", "TELEMETRIA", "ТЕЛЕМЕТРИЯ", "遥测"),
    "screen.no_media": ("NO ACTIVE MEDIA", "NENHUMA MÍDIA ATIVA", "NO HAY MEDIOS ACTIVOS", "NESSUN CONTENUTO ATTIVO", "НЕТ АКТИВНОГО МЕДИА", "没有活动媒体"),
    "screen.playing_now": ("PLAYING NOW", "TOCANDO AGORA", "REPRODUZINDO AGORA", "IN RIPRODUZIONE", "СЕЙЧАС ИГРАЕТ", "正在播放"),
    "status.sensor_unavailable": ("Sensors unavailable: {reason}", "Sensores indisponíveis: {reason}", "Sensores no disponibles: {reason}", "Sensori non disponibili: {reason}", "Датчики недоступны: {reason}", "传感器不可用：{reason}"),
    "status.theme_applied": ("{theme} theme and layout applied.", "Tema e layout {theme} aplicados.", "Tema y diseño {theme} aplicados.", "Tema e layout {theme} applicati.", "Тема и макет «{theme}» применены.", "已应用 {theme} 主题和布局。"),
    "status.auto_usb_on": ("Automatic USB updates enabled.", "Atualização automática USB ativada.", "Actualización USB automática activada.", "Aggiornamento USB automatico attivato.", "Автообновление USB включено.", "自动 USB 更新已启用。"),
    "status.auto_usb_off": ("Automatic USB updates disabled.", "Atualização automática USB desligada.", "Actualización USB automática desactivada.", "Aggiornamento USB automatico disattivato.", "Автообновление USB выключено.", "自动 USB 更新已关闭。"),
    "status.usb_busy": ("A USB operation is already running.", "Uma operação USB já está em andamento.", "Ya hay una operación USB en curso.", "È già in corso un'operazione USB.", "Операция USB уже выполняется.", "USB 操作正在进行。"),
    "status.checking_port": ("Checking port in the background.", "Verificando porta em segundo plano.", "Comprobando el puerto en segundo plano.", "Controllo porta in background.", "Проверка порта в фоновом режиме.", "正在后台检查端口。"),
    "status.sending_preview": ("Sending preview in the background.", "Enviando prévia em segundo plano.", "Enviando vista previa en segundo plano.", "Invio anteprima in background.", "Отправка изображения в фоновом режиме.", "正在后台发送预览。"),
    "status.sending_test": ("Sending test frame in the background.", "Enviando quadro de teste em segundo plano.", "Enviando cuadro de prueba en segundo plano.", "Invio fotogramma di prova in background.", "Отправка тестового кадра в фоновом режиме.", "正在后台发送测试帧。"),
    "status.orientation_blocked": ("Physical send is disabled for this orientation.", "Envio físico bloqueado para esta orientação.", "Envío físico bloqueado para esta orientación.", "Invio fisico bloccato per questo orientamento.", "Физическая отправка для этой ориентации отключена.", "此方向已禁用实体屏幕发送。"),
    "status.brightness": ("Frame brightness: {value}%", "Brilho do quadro: {value}%", "Brillo del cuadro: {value}%", "Luminosità fotogramma: {value}%", "Яркость кадра: {value}%", "画面亮度：{value}%"),
    "status.display_sent": ("Preview sent successfully.", "Prévia enviada com sucesso.", "Vista previa enviada correctamente.", "Anteprima inviata.", "Предпросмотр отправлен.", "预览已发送。"),
    "status.media_none": ("No active media session. {reason}", "Nenhuma sessão de mídia ativa. {reason}", "No hay una sesión multimedia activa. {reason}", "Nessuna sessione multimediale attiva. {reason}", "Нет активного медиасеанса. {reason}", "没有活动媒体会话。{reason}"),
    "status.media_failed": ("Media check failed in background: {reason}", "Falha na verificação de mídia em segundo plano: {reason}", "Falló la búsqueda de medios en segundo plano: {reason}", "Ricerca contenuti non riuscita in background: {reason}", "Ошибка фоновой проверки мультимедиа: {reason}", "后台媒体检查失败：{reason}"),
    "status.demo_components": ("{items}: demonstration values; alerts are off.", "{items}: valores de demonstração; alertas desativados.", "{items}: valores de demostración; alertas desactivadas.", "{items}: valori dimostrativi; avvisi disattivati.", "{items}: демонстрационные значения; оповещения выключены.", "{items}：演示数据；提醒已关闭。"),
    "status.live_sources": ("Live values from configured sources.", "Leituras publicadas pelas fontes configuradas.", "Lecturas de las fuentes configuradas.", "Letture dalle fonti configurate.", "Данные из настроенных источников.", "来自已配置数据源的实时数据。"),
    "alert.temperature": ("{name} ALERT: {value} °C · limit {limit} °C", "ALERTA {name}: {value} °C • limite {limit} °C", "ALERTA {name}: {value} °C · límite {limit} °C", "AVVISO {name}: {value} °C · limite {limit} °C", "ОПОВЕЩЕНИЕ {name}: {value} °C · предел {limit} °C", "{name} 警报：{value} °C · 阈值 {limit} °C"),
    "alert.ram": ("RAM ALERT: {value}% used · limit {limit}%", "ALERTA RAM: {value}% em uso · limite {limit}%", "ALERTA RAM: {value}% en uso · límite {limit}%", "AVVISO RAM: {value}% in uso · limite {limit}%", "ОПОВЕЩЕНИЕ ОЗУ: занято {value}% · предел {limit}%", "内存警报：已用 {value}% · 阈值 {limit}%"),
    "media.playing": ("playing", "tocando", "reproduciendo", "in riproduzione", "воспроизводится", "正在播放"),
    "media.paused": ("paused", "pausado", "en pausa", "in pausa", "на паузе", "已暂停"),
    "media.stopped": ("stopped", "parado", "detenido", "fermato", "остановлено", "已停止"),
    "media.closed": ("closed", "fechado", "cerrado", "chiuso", "закрыто", "已关闭"),
    "media.status_active": ("Media: {source} / {state} / {title}", "Mídia: {source} / {state} / {title}", "Medios: {source} / {state} / {title}", "Contenuti: {source} / {state} / {title}", "Медиа: {source} / {state} / {title}", "媒体：{source} / {state} / {title}"),
    "media.status_none": ("No active media session. {reason}", "Nenhuma sessão de mídia ativa. {reason}", "No hay una sesión multimedia activa. {reason}", "Nessuna sessione multimediale attiva. {reason}", "Нет активного медиасеанса. {reason}", "没有活动媒体会话。{reason}"),
    "media.diagnostics_heading": ("Media diagnostics:", "Diagnóstico de mídia:", "Diagnóstico de medios:", "Diagnostica contenuti:", "Диагностика мультимедиа:", "媒体诊断："),
    "media.no_windows_session": ("No session published by Windows.", "Nenhuma sessão publicada pelo Windows.", "Windows no publicó ninguna sesión.", "Nessuna sessione pubblicata da Windows.", "Windows не опубликовала сеансы.", "Windows 未发布会话。"),
    "media.vlc_title_fallback": ("VLC window-title fallback; playback state, progress, and cover are unavailable.", "Fallback pelo título da janela VLC; estado, progresso e capa indisponíveis.", "Alternativa por título de ventana de VLC; estado, progreso y carátula no disponibles.", "Fallback dal titolo della finestra VLC; stato, avanzamento e copertina non disponibili.", "Резервные данные по заголовку VLC; состояние, время и обложка недоступны.", "使用 VLC 窗口标题作为备用信息；播放状态、进度和封面不可用。"),
    "media.timeout_reason": ("Windows media service did not respond in 4 seconds. Retry after restarting the player or service.", "O serviço de mídia do Windows não respondeu em 4 s. Tente novamente após reiniciar o player ou o serviço.", "El servicio multimedia de Windows no respondió en 4 s. Inténtalo tras reiniciar el reproductor o el servicio.", "Il servizio multimediale di Windows non ha risposto in 4 s. Riprova dopo aver riavviato il lettore o il servizio.", "Служба мультимедиа Windows не ответила за 4 с. Повторите попытку после перезапуска плеера или службы.", "Windows 媒体服务在 4 秒内无响应。请重启播放器或服务后重试。"),
    "media.timeout_diagnostic": ("GSMTC request exceeded 4 seconds.", "A solicitação GSMTC excedeu 4 segundos.", "La solicitud GSMTC superó los 4 segundos.", "La richiesta GSMTC ha superato 4 secondi.", "Запрос GSMTC превысил 4 секунды.", "GSMTC 请求超过 4 秒。"),
    "media.no_fallback": ("No window-title fallback was found.", "Nenhum fallback por título de janela foi encontrado.", "No se encontró alternativa por título de ventana.", "Nessun fallback dal titolo della finestra.", "Резервный заголовок окна не найден.", "未找到窗口标题备用信息。"),
    "editor.off": ("Editing is off.", "Edição desligada.", "Edición desactivada.", "Modifica disattivata.", "Редактирование выключено.", "编辑已关闭。"),
    "editor.selected": ("Selected item: {item}", "Item selecionado: {item}", "Elemento seleccionado: {item}", "Elemento selezionato: {item}", "Выбранный элемент: {item}", "已选项目：{item}"),
    "tray.open": ("Open Rebscreen", "Abrir Rebscreen", "Abrir Rebscreen", "Apri Rebscreen", "Открыть Rebscreen", "打开 Rebscreen"),
    "tray.exit": ("Exit Rebscreen", "Encerrar Rebscreen", "Salir de Rebscreen", "Esci da Rebscreen", "Закрыть Rebscreen", "退出 Rebscreen"),
    "help.button": ("How to fix", "Como resolver", "Cómo resolverlo", "Come risolvere", "Как исправить", "如何解决"),
    "help.title": ("Rebscreen help", "Ajuda do Rebscreen", "Guía para resolver problemas de Rebscreen", "Guida per Rebscreen", "Справка Rebscreen", "Rebscreen 帮助"),
    "help.intro": ("The sections below describe unavailable optional features detected during startup.", "As seções abaixo descrevem recursos opcionais indisponíveis detectados na inicialização.", "Las secciones siguientes describen funciones opcionales no disponibles detectadas al iniciar.", "Le sezioni seguenti descrivono le funzioni opzionali non disponibili rilevate all'avvio.", "Ниже описаны недоступные дополнительные функции, обнаруженные при запуске.", "以下部分说明启动时检测到的不可用可选功能。"),
    "help.sensors": ("Disk sensors: install or start Libre Hardware Monitor and enable its local web server on port 8085. Disk capacity remains available without temperature sensors.", "Sensores de disco: instale ou inicie o Libre Hardware Monitor e ative o servidor web local na porta 8085. A capacidade dos discos continua disponível sem sensores de temperatura.", "Sensores de disco: instala o inicia Libre Hardware Monitor y activa el servidor web local en el puerto 8085. La capacidad de los discos sigue disponible sin sensores de temperatura.", "Sensori disco: installa o avvia Libre Hardware Monitor e attiva il server web locale sulla porta 8085. La capacità dei dischi resta disponibile senza sensori di temperatura.", "Датчики дисков: установите или запустите Libre Hardware Monitor и включите локальный веб-сервер на порту 8085. Информация о емкости дисков доступна и без датчиков температуры.", "磁盘传感器：安装或启动 Libre Hardware Monitor，并在 8085 端口启用本地 Web 服务器。即使没有温度传感器，磁盘容量信息仍可用。"),
    "help.media": ("Windows media session support: install the application's declared WinRT media packages, then restart Rebscreen and the player.", "Suporte a sessões de mídia do Windows: instale os pacotes WinRT declarados pelo aplicativo e reinicie o Rebscreen e o player.", "Compatibilidad con sesiones multimedia de Windows: instala los paquetes WinRT declarados por la aplicación y reinicia Rebscreen y el reproductor.", "Supporto sessioni multimediali Windows: installa i pacchetti WinRT dichiarati dall'applicazione, poi riavvia Rebscreen e il lettore.", "Поддержка медиасеансов Windows: установите объявленные приложением пакеты WinRT, затем перезапустите Rebscreen и плеер.", "Windows 媒体会话支持：安装应用声明的 WinRT 软件包，然后重启 Rebscreen 和播放器。"),
    "help.serial": ("USB serial support: install pyserial from the project requirements and reconnect the compatible display.", "Suporte serial USB: instale pyserial pelos requisitos do projeto e reconecte a tela compatível.", "Compatibilidad serie USB: instala pyserial desde los requisitos del proyecto y vuelve a conectar la pantalla compatible.", "Supporto seriale USB: installa pyserial dai requisiti del progetto e ricollega il display compatibile.", "Поддержка USB-порта: установите pyserial из зависимостей проекта и переподключите совместимый дисплей.", "USB 串口支持：从项目依赖中安装 pyserial，然后重新连接兼容显示屏。"),
    "help.processes": ("Process and network details: install psutil from the project requirements. Other Rebscreen features remain available without it.", "Detalhes de processos e rede: instale psutil pelos requisitos do projeto. Os demais recursos do Rebscreen continuam disponíveis sem ele.", "Detalles de procesos y red: instala psutil desde los requisitos del proyecto. Las demás funciones siguen disponibles.", "Dettagli di processi e rete: installa psutil dai requisiti del progetto. Le altre funzioni restano disponibili.", "Сведения о процессах и сети: установите psutil из зависимостей проекта. Остальные функции Rebscreen доступны и без него.", "进程和网络信息：从项目依赖中安装 psutil。没有它时，Rebscreen 的其他功能仍可使用。"),
    "help.none": ("No missing optional dependencies were detected.", "Nenhuma dependência opcional ausente foi detectada.", "No se detectaron dependencias opcionales ausentes.", "Non sono state rilevate dipendenze opzionali mancanti.", "Отсутствующие дополнительные зависимости не обнаружены.", "未检测到缺失的可选依赖项。"),
    "help.open_failed": ("Could not open the help file at {path}: {reason}", "Não foi possível abrir o arquivo de ajuda em {path}: {reason}", "No se pudo abrir el archivo de ayuda en {path}: {reason}", "Impossibile aprire il file di aiuto in {path}: {reason}", "Не удалось открыть файл справки {path}: {reason}", "无法打开帮助文件 {path}：{reason}"),
    "sensor.unavailable": ("{name}: unavailable", "{name}: indisponível", "{name}: no disponible", "{name}: non disponibile", "{name}: недоступен", "{name}: 不可用"),
    "runtime.sensor.rest": ("Libre Hardware Monitor: local REST connected.", "Libre Hardware Monitor: REST local conectado.", "Libre Hardware Monitor: REST local conectado.", "Libre Hardware Monitor: REST locale connesso.", "Libre Hardware Monitor: локальный REST подключен.", "Libre Hardware Monitor：本地 REST 已连接。"),
    "runtime.sensor.unavailable": ("Libre Hardware Monitor is unavailable.", "Libre Hardware Monitor está indisponível.", "Libre Hardware Monitor no está disponible.", "Libre Hardware Monitor non è disponibile.", "Libre Hardware Monitor недоступен.", "Libre Hardware Monitor 不可用。"),
    "runtime.sensor.rest_unavailable": ("Libre Hardware Monitor local REST is unavailable.", "O REST local do Libre Hardware Monitor está indisponível.", "El REST local de Libre Hardware Monitor no está disponible.", "Il REST locale di Libre Hardware Monitor non è disponibile.", "Локальный REST Libre Hardware Monitor недоступен.", "Libre Hardware Monitor 本地 REST 不可用。"),
    "runtime.sensor.enable_rest": ("Libre Hardware Monitor is installed. Enable Options > Web Server > Run web server (port 8085).", "Libre Hardware Monitor está instalado. Ative Options > Web Server > Run web server (porta 8085).", "Libre Hardware Monitor está instalado. Activa Options > Web Server > Run web server (puerto 8085).", "Libre Hardware Monitor è installato. Attiva Options > Web Server > Run web server (porta 8085).", "Libre Hardware Monitor установлен. Включите Options > Web Server > Run web server (порт 8085).", "Libre Hardware Monitor 已安装。请启用 Options > Web Server > Run web server（端口 8085）。"),
    "runtime.media.binding_missing": ("GSMTC binding is missing. Requires Python 3.9+ with winrt-Windows.Media.Control.", "A integração GSMTC está ausente. Requer Python 3.9+ com winrt-Windows.Media.Control.", "Falta la integración GSMTC. Requiere Python 3.9+ con winrt-Windows.Media.Control.", "L'integrazione GSMTC non è disponibile. Richiede Python 3.9+ con winrt-Windows.Media.Control.", "Отсутствует привязка GSMTC. Требуется Python 3.9+ с winrt-Windows.Media.Control.", "缺少 GSMTC 绑定。需要 Python 3.9+ 和 winrt-Windows.Media.Control。"),
    "runtime.media.ready": ("GSMTC is ready through {binding}.", "GSMTC está pronto via {binding}.", "GSMTC está listo mediante {binding}.", "GSMTC è pronto tramite {binding}.", "GSMTC готов через {binding}.", "GSMTC 已通过 {binding} 就绪。"),
    "runtime.media.no_published": ("No media session was published by Windows.", "Nenhuma sessão de mídia foi publicada pelo Windows.", "Windows no publicó ninguna sesión multimedia.", "Windows non ha pubblicato sessioni multimediali.", "Windows не опубликовала медиасеанс.", "Windows 未发布媒体会话。"),
    "runtime.media.no_playing": ("GSMTC is active, but no media is playing.", "GSMTC está ativo, mas nenhuma mídia está tocando.", "GSMTC está activo, pero no hay medios reproduciéndose.", "GSMTC è attivo, ma nessun contenuto è in riproduzione.", "GSMTC активен, но медиа не воспроизводится.", "GSMTC 已启用，但没有媒体正在播放。"),
    "runtime.media.metadata_unavailable": ("metadata unavailable", "metadados indisponíveis", "metadatos no disponibles", "metadati non disponibili", "метаданные недоступны", "元数据不可用"),
    "runtime.media.no_art": ("No image was published by Windows; using a placeholder.", "Nenhuma imagem foi publicada pelo Windows; usando placeholder.", "Windows no publicó ninguna imagen; se usa un marcador.", "Windows non ha pubblicato immagini; viene usato un segnaposto.", "Windows не опубликовала изображение; используется заполнитель.", "Windows 未发布图像；正在使用占位图。"),
    "runtime.media.art_memory": ("GSMTC cover is held in memory.", "A capa GSMTC está em memória.", "La portada GSMTC está en memoria.", "La copertina GSMTC è in memoria.", "Обложка GSMTC находится в памяти.", "GSMTC 封面保存在内存中。"),
    "runtime.media.thumbnail_unavailable": ("Thumbnail unavailable; using a placeholder.", "Miniatura indisponível; usando placeholder.", "Miniatura no disponible; se usa un marcador.", "Miniatura non disponibile; viene usato un segnaposto.", "Миниатюра недоступна; используется заполнитель.", "缩略图不可用；正在使用占位图。"),
    "runtime.media.failed": ("GSMTC failed: {reason}", "Falha GSMTC: {reason}", "Error de GSMTC: {reason}", "Errore GSMTC: {reason}", "Ошибка GSMTC: {reason}", "GSMTC 失败：{reason}"),
    "runtime.media.selected": ("Selected: {source} — playing", "Selecionado: {source} — tocando", "Seleccionado: {source} — reproduciendo", "Selezionato: {source} — in riproduzione", "Выбрано: {source} — воспроизводится", "已选择：{source} — 正在播放"),
    "runtime.media.spotify_fallback": ("GSMTC is unavailable; Spotify did not publish cover art or progress.", "GSMTC indisponível; o Spotify não publicou capa ou progresso.", "GSMTC no está disponible; Spotify no publicó portada ni progreso.", "GSMTC non è disponibile; Spotify non ha pubblicato copertina o avanzamento.", "GSMTC недоступен; Spotify не опубликовал обложку или прогресс.", "GSMTC 不可用；Spotify 未发布封面或进度。"),
    "runtime.media.vlc_fallback": ("VLC has no GSMTC image; using a placeholder.", "O VLC não tem imagem GSMTC; usando placeholder.", "VLC no tiene imagen GSMTC; se usa un marcador.", "VLC non ha immagine GSMTC; viene usato un segnaposto.", "У VLC нет изображения GSMTC; используется заполнитель.", "VLC 没有 GSMTC 图像；正在使用占位图。"),
    "runtime.serial.busy": ("{port} is in use by another program. Close the software using the display and try again.", "{port} está ocupada por outro programa. Feche o software que usa a tela e tente novamente.", "{port} está ocupado por otro programa. Cierra el software que usa la pantalla e inténtalo de nuevo.", "{port} è in uso da un altro programma. Chiudi il software che usa il display e riprova.", "{port} занято другой программой. Закройте программу, использующую дисплей, и повторите попытку.", "{port} 正被其他程序占用。请关闭正在使用显示屏的软件后重试。"),
    "runtime.serial.missing": ("The selected port is unavailable. Check the cable and COM port.", "A porta selecionada não está disponível. Confira o cabo e a porta COM.", "El puerto seleccionado no está disponible. Comprueba el cable y el puerto COM.", "La porta selezionata non è disponibile. Controlla il cavo e la porta COM.", "Выбранный порт недоступен. Проверьте кабель и COM-порт.", "所选端口不可用。请检查线缆和 COM 端口。"),
    "runtime.serial.failed": ("Could not access the port: {reason}", "Não foi possível acessar a porta: {reason}", "No se pudo acceder al puerto: {reason}", "Impossibile accedere alla porta: {reason}", "Не удалось получить доступ к порту: {reason}", "无法访问端口：{reason}"),
    "runtime.transport.preview_sent": ("Preview sent to {port}.", "Prévia enviada para {port}.", "Vista previa enviada a {port}.", "Anteprima inviata a {port}.", "Предпросмотр отправлен на {port}.", "预览已发送到 {port}。"),
    "runtime.transport.test_sent": ("Test sent: 320 × 480 on {port}.", "Teste enviado: 320 × 480 em {port}.", "Prueba enviada: 320 × 480 en {port}.", "Test inviato: 320 × 480 su {port}.", "Тест отправлен: 320 × 480 на {port}.", "测试已发送：320 × 480，端口 {port}。"),
    "runtime.transport.port_ready": ("{port} is available. Sending remains manual and off.", "{port} está disponível. O envio continua manual e desligado.", "{port} está disponible. El envío sigue siendo manual y está desactivado.", "{port} è disponibile. L'invio resta manuale e disattivato.", "{port} доступен. Отправка остается ручной и выключенной.", "{port} 可用。发送仍为手动且关闭。"),
    "status.auto_sending": ("Display update queued in the background.", "Atualização da tela em segundo plano.", "Actualización de pantalla en segundo plano.", "Aggiornamento display in background.", "Обновление дисплея выполняется в фоне.", "显示屏正在后台更新。"),
    "media.none_label": ("No active media", "Nenhuma mídia ativa", "Sin medios activos", "Nessun contenuto attivo", "Нет активного медиа", "没有活动媒体"),
}

CATALOGS: dict[str, dict[str, str]] = {
    language: {key: row[index] for key, row in _MESSAGES.items()}
    for index, language in enumerate(LANGUAGES)
}


def normalize_language(language: object) -> str:
    return language if isinstance(language, str) and language in CATALOGS else DEFAULT_LANGUAGE


def translate(language: str, key: str, **values: object) -> str:
    selected = CATALOGS.get(normalize_language(language), CATALOGS[DEFAULT_LANGUAGE])
    message = selected.get(key, CATALOGS[DEFAULT_LANGUAGE].get(key, key))
    return message.format(**values)


def localize_sensor_status(language: str, status: str) -> str:
    """Translate known local sensor-provider statuses without changing provider state."""
    normalized = (status or "").casefold()
    if "(rest local) indispon" in normalized:
        return translate(language, "runtime.sensor.rest_unavailable")
    if "aberto/instalado" in normalized and "porta 8085" in normalized:
        return translate(language, "runtime.sensor.enable_rest")
    if normalized == "libre hardware monitor indisponível" or normalized == "libre hardware monitor unavailable":
        return translate(language, "runtime.sensor.unavailable")
    if normalized == "libre hardware monitor (rest local)":
        return translate(language, "runtime.sensor.rest")
    return status


def localize_media_runtime_message(language: str, message: str) -> str:
    """Translate provider-owned GSMTC diagnostics while retaining unknown errors."""
    value = message or ""
    known = {
        "Binding GSMTC ausente (requer Python 3.9+ com winrt-Windows.Media.Control)": "runtime.media.binding_missing",
        "GSMTC ativo; nenhuma sessão publicada pelo Windows": "runtime.media.no_published",
        "Nenhuma sessão publicada pelo Windows.": "runtime.media.no_published",
        "GSMTC ativo; nenhuma sessão em reprodução": "runtime.media.no_playing",
        "Sem imagem publicada pelo Windows; usando placeholder.": "runtime.media.no_art",
        "Capa GSMTC em memória.": "runtime.media.art_memory",
        "Thumbnail indisponível; usando placeholder.": "runtime.media.thumbnail_unavailable",
        "GSMTC indisponível; Spotify não publicou capa/progresso.": "runtime.media.spotify_fallback",
        "VLC sem imagem GSMTC; usando placeholder.": "runtime.media.vlc_fallback",
    }
    if value in known:
        return translate(language, known[value])
    if value in ("GSMTC via winrt", "GSMTC via winsdk"):
        return translate(language, "runtime.media.ready", binding=value.rsplit(" ", 1)[-1])
    if value.startswith("Falha GSMTC: "):
        return translate(language, "runtime.media.failed", reason=value.removeprefix("Falha GSMTC: "))
    if value.startswith("Selecionado: ") and value.endswith(" — tocando"):
        return translate(language, "runtime.media.selected", source=value[12:-10])
    if value.endswith(" (metadados indisponíveis)"):
        return value.removesuffix(" (metadados indisponíveis)") + " (" + translate(language, "runtime.media.metadata_unavailable") + ")"
    return value


def localize_transport_status(language: str, status: str) -> str:
    """Translate success text produced by the serial worker without reopening it."""
    preview = re.fullmatch(r"Prévia enviada para (.+)\.", status or "")
    if preview:
        return translate(language, "runtime.transport.preview_sent", port=preview.group(1))
    test = re.fullmatch(r"Teste enviado: 320 × 480 em (.+)\.", status or "")
    if test:
        return translate(language, "runtime.transport.test_sent", port=test.group(1))
    ready = re.fullmatch(r"(.+) disponível\. Envio continua manual e desligado\.", status or "")
    if ready:
        return translate(language, "runtime.transport.port_ready", port=ready.group(1))
    return status
