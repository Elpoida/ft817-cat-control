"""Small server-side message catalogue used by error and status strings."""

from __future__ import annotations

LANGS = ("it", "en", "ja", "fr", "ru", "es")
LANG = "en"

MESSAGES = {
    "not connected": {
        "it": "non connesso", "es": "no conectado", "fr": "non connecté",
        "ja": "未接続", "ru": "нет соединения",
    },
    "command timeout": {
        "it": "tempo scaduto", "es": "tiempo agotado", "fr": "délai dépassé",
        "ja": "タイムアウト", "ru": "тайм-аут",
    },
    "no serial port selected": {
        "it": "nessuna porta seriale selezionata", "es": "ningún puerto serie seleccionado",
        "fr": "aucun port série sélectionné", "ja": "シリアルポートが選択されていません",
        "ru": "последовательный порт не выбран",
    },
    "the radio is already transmitting": {
        "it": "la radio è già in trasmissione", "es": "la radio ya está transmitiendo",
        "fr": "la radio émet déjà", "ja": "無線機はすでに送信中です",
        "ru": "радиостанция уже передаёт",
    },
    "no panorama while transmitting": {
        "it": "niente panoramica durante la trasmissione",
        "es": "sin panorama durante la transmisión", "fr": "pas de panorama pendant l'émission",
        "ja": "送信中はパノラマ不可", "ru": "панорама недоступна при передаче",
    },
    "frequency is not in an amateur band": {
        "it": "la frequenza non è in una banda radioamatoriale",
        "es": "la frecuencia no está en una banda de radioaficionado",
        "fr": "la fréquence n'est pas dans une bande amateur",
        "ja": "アマチュアバンド外の周波数です", "ru": "частота вне любительского диапазона",
    },
    "measurement interval too narrow": {
        "it": "intervallo di misura troppo stretto", "es": "intervalo de medición demasiado estrecho",
        "fr": "intervalle de mesure trop étroit", "ja": "測定範囲が狭すぎます",
        "ru": "слишком узкий интервал измерения",
    },
    "the radio does not answer EEPROM reads": {
        "it": "la radio non risponde alle letture EEPROM", "es": "la radio no responde a las lecturas EEPROM",
        "fr": "la radio ne répond pas aux lectures EEPROM", "ja": "EEPROM読み出しに応答がありません",
        "ru": "радиостанция не отвечает на чтение EEPROM",
    },
    "EEPROM writes are disabled: enable them in the connection dialog": {
        "it": "comandi via EEPROM disabilitati: attivarli nella finestra Connessione",
        "es": "escrituras EEPROM desactivadas: actívelas en la conexión",
        "fr": "écritures EEPROM désactivées : activez-les dans la connexion",
        "ja": "EEPROM書き込みが無効です。接続画面で有効にしてください",
        "ru": "запись EEPROM отключена: включите её в окне подключения",
    },
    "refusing to write EEPROM while transmitting": {
        "it": "non si scrive l'EEPROM durante la trasmissione",
        "es": "no se escribe la EEPROM durante la transmisión",
        "fr": "pas d'écriture EEPROM pendant l'émission",
        "ja": "送信中はEEPROMに書き込みません", "ru": "запись EEPROM во время передачи запрещена",
    },
    "TUNE and SWR measurement lower the power by writing EEPROM: enable EEPROM commands": {
        "it": "TUNE e misura del ROS abbassano la potenza scrivendo l'EEPROM: abilitare i comandi via EEPROM",
        "es": "TUNE y ROS reducen la potencia escribiendo la EEPROM: active los comandos EEPROM",
        "fr": "TUNE et ROS réduisent la puissance via l'EEPROM : activez les commandes EEPROM",
        "ja": "TUNEとSWR測定はEEPROM書き込みで出力を下げます。EEPROMコマンドを有効にしてください",
        "ru": "TUNE и КСВ снижают мощность через EEPROM: включите команды EEPROM",
    },
}


def set_lang(lang):
    global LANG
    if lang in LANGS:
        LANG = lang
    return LANG


def get_lang():
    return LANG


def tr(text, **kwargs):
    key = str(text)
    table = MESSAGES.get(key, {})
    translated = table.get(LANG, key)
    try:
        return translated.format(**kwargs)
    except Exception:
        return translated
