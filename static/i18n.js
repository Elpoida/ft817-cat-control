"use strict";

const I18N = {
  en: {
    disconnected: "Disconnected", connected: "Connected", green: "Green", amber: "Amber", blue: "Blue",
    white: "White", night: "Night", settings: "Settings", quit: "Quit", tuning: "Tuning",
    memoryShortcuts: "Memory shortcuts", knob: "Main dial", dragHint: "drag / wheel", vfo: "VFO A/B",
    aEqB: "A=B", swap: "A↔B", split: "Split", lock: "Lock", clar: "Clar", tone: "Tone", apply: "Apply",
    pttHold: "PTT", latch: "Latch", tuneHold: "TUNE", power: "Power", radio: "Radio", refresh: "refresh",
    operate: "Operate", scope: "Scope", memories: "Memories", cw: "CW", console: "Console", status: "Status",
    frequency: "Frequency", mode: "Mode", band: "Band", smeter: "S-meter", txmeter: "TX meter",
    eeprom: "EEPROM", rate: "Poll rate", eepromSettings: "EEPROM settings", toneSettings: "CTCSS / DCS",
    panorama: "Panorama", span: "Span", points: "Points", start: "Start", stop: "Stop", swr: "SWR sweep",
    measure: "Measure", fromRadio: "From radio", saveCurrent: "Save current", export: "Export",
    import: "Import", cwKeyer: "CW keyer", send: "Send", live: "live typing", beacon: "Beacon",
    interval: "Interval s", repeat: "Repeat 0=∞", monitor: "Monitor", pitch: "Pitch", volume: "Volume",
    catConsole: "CAT console", read: "Read", showPolling: "show polling", clear: "Clear",
    connection: "Connection", simulator: "Simulator", model: "Model", port: "Port", baud: "Baud", stopbits: "Stop bits",
    pttLine: "PTT line", poll: "Poll ms", timeout: "Timeout ms", tot: "TOT s", eeWrite: "Enable EEPROM writes", autoConnect: "Connect automatically at startup",
    connect: "Connect", disconnect: "Disconnect", close: "Close", keyLine: "Key line", keyPort: "Key port",
    noRadio: "No radio connected", connectFirst: "Connect first", invalidFreq: "Invalid frequency",
    saved: "Saved", deleted: "Deleted", imported: "Imported", exported: "Exported",
    readRunning: "Reading memories…", readDone: "Memories read", noMemories: "No memories found",
    pttAlarm: "PTT alarm", eepromDisabled: "EEPROM writes are disabled", search: "Search",
    powerOn: "Power on", powerOff: "Power off", modelAuto: "auto model", signal: "Signal",
    confirmDelete: "Delete this memory?", empty: "empty", tx: "TX", rx: "RX", poll: "poll",
  },
  it: {
    disconnected: "Sconnesso", connected: "Connesso", green: "Verde", amber: "Ambra", blue: "Azzurro",
    white: "Bianco", night: "Notte", settings: "Impostazioni", quit: "Esci", tuning: "Sintonia",
    memoryShortcuts: "Memorie rapide", knob: "Manopola", dragHint: "trascina / rotella", vfo: "VFO A/B",
    aEqB: "A=B", swap: "A↔B", split: "Split", lock: "Lock", clar: "Clar", tone: "Tono", apply: "Applica",
    pttHold: "PTT", latch: "Aggancio", tuneHold: "TUNE", power: "Accensione", radio: "Radio", refresh: "aggiorna",
    operate: "Uso", scope: "Panoramica", memories: "Memorie", cw: "CW", console: "Console", status: "Stato",
    frequency: "Frequenza", mode: "Modo", band: "Banda", smeter: "S-meter", txmeter: "Misuratore TX",
    eeprom: "EEPROM", rate: "Ritmo polling", eepromSettings: "Impostazioni EEPROM", toneSettings: "CTCSS / DCS",
    panorama: "Panoramica", span: "Ampiezza", points: "Punti", start: "Avvia", stop: "Ferma", swr: "Misura ROS",
    measure: "Misura", fromRadio: "Dalla radio", saveCurrent: "Salva attuale", export: "Esporta",
    import: "Importa", cwKeyer: "Keyer CW", send: "Invia", live: "scrittura dal vivo", beacon: "Beacon",
    interval: "Intervallo s", repeat: "Ripetizioni 0=∞", monitor: "Monitor", pitch: "Tono", volume: "Volume",
    catConsole: "Console CAT", read: "Leggi", showPolling: "mostra polling", clear: "Pulisci",
    connection: "Connessione", simulator: "Simulatore", model: "Modello", port: "Porta", baud: "Velocità", stopbits: "Bit di stop",
    pttLine: "Linea PTT", poll: "Polling ms", timeout: "Timeout ms", tot: "TOT s", eeWrite: "Abilita scritture EEPROM", autoConnect: "Connetti automaticamente all'avvio",
    connect: "Connetti", disconnect: "Disconnetti", close: "Chiudi", keyLine: "Linea tasto", keyPort: "Porta tasto",
    noRadio: "Nessuna radio connessa", connectFirst: "Connetti prima", invalidFreq: "Frequenza non valida",
    saved: "Salvato", deleted: "Eliminato", imported: "Importato", exported: "Esportato",
    readRunning: "Lettura memorie…", readDone: "Memorie lette", noMemories: "Nessuna memoria trovata",
    pttAlarm: "Allarme PTT", eepromDisabled: "Scritture EEPROM disabilitate", search: "Cerca",
    powerOn: "Accendi", powerOff: "Spegni", modelAuto: "modello automatico", signal: "Segnale",
    confirmDelete: "Eliminare questa memoria?", empty: "vuoto", tx: "TX", rx: "RX", poll: "poll",
  },
  es: {
    disconnected: "Desconectado", connected: "Conectado", green: "Verde", amber: "Ámbar", blue: "Azul",
    white: "Blanco", night: "Noche", settings: "Ajustes", quit: "Salir", tuning: "Sintonía",
    memoryShortcuts: "Memorias rápidas", knob: "Mando", dragHint: "arrastra / rueda", vfo: "VFO A/B",
    aEqB: "A=B", swap: "A↔B", split: "Split", lock: "Bloqueo", clar: "Clar", tone: "Tono", apply: "Aplicar",
    pttHold: "PTT", latch: "Fijar", tuneHold: "TUNE", power: "Encendido", radio: "Radio", refresh: "actualizar",
    operate: "Operar", scope: "Panorama", memories: "Memorias", cw: "CW", console: "Consola", status: "Estado",
    frequency: "Frecuencia", mode: "Modo", band: "Banda", smeter: "S-meter", txmeter: "Medidor TX",
    eeprom: "EEPROM", rate: "Tasa de sondeo", eepromSettings: "Ajustes EEPROM", toneSettings: "CTCSS / DCS",
    panorama: "Panorama", span: "Span", points: "Puntos", start: "Iniciar", stop: "Parar", swr: "Barrido ROS",
    measure: "Medir", fromRadio: "Desde radio", saveCurrent: "Guardar actual", export: "Exportar",
    import: "Importar", cwKeyer: "Keyer CW", send: "Enviar", live: "escritura en vivo", beacon: "Baliza",
    interval: "Intervalo s", repeat: "Repeticiones 0=∞", monitor: "Monitor", pitch: "Tono", volume: "Volumen",
    catConsole: "Consola CAT", read: "Leer", showPolling: "mostrar sondeo", clear: "Limpiar",
    connection: "Conexión", simulator: "Simulador", model: "Modelo", port: "Puerto", baud: "Baudios", stopbits: "Bits de parada",
    pttLine: "Línea PTT", poll: "Sondeo ms", timeout: "Timeout ms", tot: "TOT s", eeWrite: "Permitir escrituras EEPROM", autoConnect: "Conectar automáticamente al inicio",
    connect: "Conectar", disconnect: "Desconectar", close: "Cerrar", keyLine: "Línea de llave", keyPort: "Puerto de llave",
  },
  fr: {
    disconnected: "Déconnecté", connected: "Connecté", green: "Vert", amber: "Ambre", blue: "Bleu",
    white: "Blanc", night: "Nuit", settings: "Réglages", quit: "Quitter", tuning: "Accord",
    memoryShortcuts: "Mémoires rapides", knob: "Bouton", dragHint: "glisser / molette", vfo: "VFO A/B",
    aEqB: "A=B", swap: "A↔B", split: "Split", lock: "Verrou", clar: "Clar", tone: "Tonalité", apply: "Appliquer",
    pttHold: "PTT", latch: "Maintien", tuneHold: "TUNE", power: "Marche", radio: "Radio", refresh: "actualiser",
    operate: "Utiliser", scope: "Panorama", memories: "Mémoires", cw: "CW", console: "Console", status: "État",
    frequency: "Fréquence", mode: "Mode", band: "Bande", smeter: "S-mètre", txmeter: "Mesure TX",
    eeprom: "EEPROM", rate: "Taux de scrutation", eepromSettings: "Réglages EEPROM", toneSettings: "CTCSS / DCS",
    panorama: "Panorama", span: "Étendue", points: "Points", start: "Démarrer", stop: "Arrêter", swr: "Balayage ROS",
    measure: "Mesurer", fromRadio: "Depuis radio", saveCurrent: "Enregistrer", export: "Exporter",
    import: "Importer", cwKeyer: "Manipulateur CW", send: "Envoyer", live: "frappe en direct", beacon: "Balise",
    interval: "Intervalle s", repeat: "Répétitions 0=∞", monitor: "Moniteur", pitch: "Tonalité", volume: "Volume",
    catConsole: "Console CAT", read: "Lire", showPolling: "afficher scrutation", clear: "Effacer",
    connection: "Connexion", simulator: "Simulateur", model: "Modèle", port: "Port", baud: "Débit", stopbits: "Bits d'arrêt",
    pttLine: "Ligne PTT", poll: "Scrutation ms", timeout: "Timeout ms", tot: "TOT s", eeWrite: "Autoriser écritures EEPROM", autoConnect: "Connexion automatique au démarrage",
    connect: "Connecter", disconnect: "Déconnecter", close: "Fermer", keyLine: "Ligne de manipulation", keyPort: "Port de manipulation",
  },
  ja: {
    disconnected: "未接続", connected: "接続中", green: "緑", amber: "琥珀", blue: "青", white: "白", night: "夜間",
    settings: "設定", quit: "終了", tuning: "同調", memoryShortcuts: "メモリー", knob: "ダイヤル",
    dragHint: "ドラッグ／ホイール", vfo: "VFO A/B", aEqB: "A=B", swap: "A↔B", split: "スプリット",
    lock: "ロック", clar: "クラリファイア", tone: "トーン", apply: "適用", pttHold: "PTT", latch: "ラッチ",
    tuneHold: "TUNE", power: "電源", radio: "無線機", refresh: "更新", operate: "操作", scope: "パノラマ",
    memories: "メモリー", cw: "CW", console: "コンソール", status: "状態", frequency: "周波数", mode: "モード",
    band: "バンド", smeter: "Sメーター", txmeter: "TXメーター", eeprom: "EEPROM", rate: "ポーリング",
    eepromSettings: "EEPROM設定", toneSettings: "CTCSS / DCS", panorama: "パノラマ", span: "範囲",
    points: "点数", start: "開始", stop: "停止", swr: "SWRスイープ", measure: "測定", fromRadio: "無線機から",
    saveCurrent: "現在を保存", export: "エクスポート", import: "インポート", cwKeyer: "CWキーヤー",
    send: "送信", live: "ライブ入力", beacon: "ビーコン", interval: "間隔 s", repeat: "回数 0=∞",
    monitor: "モニター", pitch: "音程", volume: "音量", catConsole: "CATコンソール", read: "読み出し",
    showPolling: "ポーリング表示", clear: "消去", connection: "接続", simulator: "シミュレーター", model: "モデル",
    port: "ポート", baud: "ボーレート", stopbits: "ストップビット", pttLine: "PTTライン",
    poll: "ポーリング ms", timeout: "タイムアウト ms", tot: "TOT s", eeWrite: "EEPROM書き込みを有効化", autoConnect: "起動時に自動接続",
    connect: "接続", disconnect: "切断", close: "閉じる", keyLine: "キーライン", keyPort: "キーポート",
  },
  ru: {
    disconnected: "Отключено", connected: "Подключено", green: "Зелёный", amber: "Янтарный", blue: "Синий",
    white: "Белый", night: "Ночь", settings: "Настройки", quit: "Выход", tuning: "Настройка",
    memoryShortcuts: "Памяти", knob: "Валкодер", dragHint: "тяните / колесо", vfo: "VFO A/B", aEqB: "A=B",
    swap: "A↔B", split: "Split", lock: "Блокировка", clar: "Clar", tone: "Тон", apply: "Применить",
    pttHold: "PTT", latch: "Фиксация", tuneHold: "TUNE", power: "Питание", radio: "Радио", refresh: "обновить",
    operate: "Работа", scope: "Панорама", memories: "Памяти", cw: "CW", console: "Консоль", status: "Состояние",
    frequency: "Частота", mode: "Режим", band: "Диапазон", smeter: "S-метр", txmeter: "Измеритель TX",
    eeprom: "EEPROM", rate: "Опрос", eepromSettings: "Настройки EEPROM", toneSettings: "CTCSS / DCS",
    panorama: "Панорама", span: "Полоса", points: "Точки", start: "Старт", stop: "Стоп", swr: "КСВ",
    measure: "Измерить", fromRadio: "Из радио", saveCurrent: "Сохранить", export: "Экспорт",
    import: "Импорт", cwKeyer: "CW ключ", send: "Передать", live: "набор вживую", beacon: "Маяк",
    interval: "Интервал с", repeat: "Повторы 0=∞", monitor: "Монитор", pitch: "Тон", volume: "Громкость",
    catConsole: "Консоль CAT", read: "Чтение", showPolling: "показывать опрос", clear: "Очистить",
    connection: "Подключение", simulator: "Симулятор", model: "Модель", port: "Порт", baud: "Скорость", stopbits: "Стоп-биты",
    pttLine: "Линия PTT", poll: "Опрос мс", timeout: "Тайм-аут мс", tot: "TOT с", eeWrite: "Разрешить запись EEPROM", autoConnect: "Подключаться при запуске",
    connect: "Подключить", disconnect: "Отключить", close: "Закрыть", keyLine: "Линия ключа", keyPort: "Порт ключа",
  },
};

const LANG_NAMES = { it: "Italiano", en: "English", es: "Español", fr: "Français", ja: "日本語", ru: "Русский" };
let LANG = "en";

function setLang(lang) {
  LANG = I18N[lang] ? lang : "en";
  document.documentElement.lang = LANG;
  applyI18n();
}

function t(key, ...args) {
  const table = I18N[LANG] || I18N.en;
  let text = table[key] ?? I18N.en[key] ?? key;
  for (const arg of args) text = text.replace("{}", arg);
  return text;
}

function applyI18n(root = document) {
  for (const el of root.querySelectorAll("[data-i18n]")) {
    const key = el.getAttribute("data-i18n");
    const text = t(key);
    if (el.tagName === "OPTION" || el.children.length === 0) el.textContent = text;
    else el.textContent = text;
  }
  for (const el of root.querySelectorAll("[data-i18n-title]")) {
    el.title = t(el.getAttribute("data-i18n-title"));
  }
  const sel = document.getElementById("langSel");
  if (sel && sel.value !== LANG) sel.value = LANG;
}

