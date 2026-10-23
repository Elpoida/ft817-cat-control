# Clean-room notes

## Target

- Supplied artifact: `FT817CAT-Setup-1.3.0.exe` (local path withheld)
- SHA-256: `DAC28F8A5A86B05BC63A850C1E9F7396761A74DAFEBF79ED58F08DBD90B8DA3A`
- It is an unsigned Inno Setup 6.7.0 installer whose payload is a PyInstaller
  Python 3.12 application (`FT817CAT.exe`) plus `static/` web assets.
- Reported product: FT-817/818 CAT Control 1.3.0.

## Method

1. **Packaging identification only.** The installer and the PyInstaller archive
   were unpacked to reach the application layer. No installer or application
   code was executed as part of the extraction.
2. **Behavioural observation.** The recovered Python modules were run locally in
   simulator mode for the sole purpose of observing the HTTP API, state shape,
   command semantics, CAT frames and EEPROM behaviour. This is black-box
   behavioural evidence, not a source donation.
3. **Protocol facts.** CAT opcodes, BCD frequency encoding, EEPROM fields, the
   FT-817/818 band differences and CHIRP-style memory layout were cross-checked
   against public information: the Yaesu CAT documentation, the Hamlib
   `rigs/yaesu/ft817.c` driver and the CHIRP `ft817.py`/`ft818.py` layout
   descriptions. These are functional protocol facts.
4. **Independent implementation.** All source in this repository was written
   fresh. Module boundaries follow the observed architecture because that is the
   documented behaviour, but functions, data structures, UI markup, styles and
   test code are original. No original source text, comments, HTML, CSS or
   JavaScript were copied.
5. **Verification.** Unit tests exercise the clean-room protocol, memory,
   simulator, rig-thread and HTTP layers. The web panel was smoke-tested in a
   headless browser against the clean-room server.

## Deliberate exclusions

- The original is a paid program with an Ed25519 licence-code scheme and a
  15-minute demo timer. This repository contains no verification keys, no code
  generation, no licence file parsing and no timer. It is unrestricted.
- No attempt was made to reproduce the original installer, executable, artwork,
  dedicated browser-window integration or single-instance plumbing.
- No original binary or extracted asset is redistributed here.

## Evidence and unknowns

Observed on the studied build (simulator):

- API envelope and endpoints, state field names/values, `cmd` operation names.
- CAT frame layout, ACK byte, EEPROM read/write framing, polling cadence.
- Band records at `0x7D + index*26`, memory bitmap/base addresses, memory
  record decoding, model detection from EEPROM `0x59`.
- Power/AGC/IPO/ATT/NAR/antenna bit placement, PTT watchdog and TUNE restore
  semantics.

Inherited protocol limits that remain true in this implementation:

- Shift, offset, tone, clarifier and lock cannot be read back from the radio;
  the panel shows the last value sent from this client.
- The radio does not push changes; the panel polls.
- WFM can be read but not set over CAT; the FT-817 has one tone for TX and RX.
- EEPROM writes are inherently risky and are opt-in.

Not established here:

- Behaviour on real FT-817/818 hardware remains unverified. Automatic model
  detection, the `0xBD` SWR scale,
  EEPROM write effects and ACK timing need field verification.
- Exact parity of the original's panorama cadence, SWR quality, CW monitor audio
  and every translated string.
- Any hidden vendor/service behaviour beyond the observed local application.
