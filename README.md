# Historische Anzeigetafel Regattastecke Berlin-Grünau – Serial Control 

This project provides a serial interface for controlling the historical LED matrix display at the regatta course in Berlin-Grünau. The display consists of **8 lines with exactly 30 characters each**. It is controlled via a **serial connection at 38400 baud**.

## Contents

- `regatta.py` – Python source code with GUI
- `regatta.exe` – precompiled standalone Windows executable

## Features

- GUI with 8×30 input fields
- automatic cursor jump after each character input
- manual "Send" button to transmit all content
- sends data using the original historical serial protocol
- optional animation mode (ASCII frames from a file)
- character encoding: **ISO-8859-1** (supports ÄÖÜ, §$%&, etc.)

## Display Technical Details

- Communication via USB-to-Serial adapter
- Protocol format:
  - Start byte: `0x01`
  - Brightness identifier, full brightness is set by 0xFF
  - exactly 30 bytes per line including spaces
- No STX/ETX possible! (legacy matrix controller does not support them)
- Character set: **ISO-8859-1** (not UTF-8!)

## Requirements (for `regatta.py`)

- Python 3.9+
- tkinter (included in standard Python installation)
- pyserial

To install `pyserial`:
```bash
pip install pyserial
```

## Usage

### Sending Content to the Display

1. Run `regatta.py`
2. Enter characters in each field (cursor moves automatically)
3. Lines are padded or wrapped based on overflow behavior
4. Click “Send” to transmit the content to the serial port

### Using the EXE

`regatta.exe` is a compiled version of the script and can be run on any Windows machine without Python.

## Animation Mode (experimental)

An ASCII animation mode reads `.txt` files formatted like this:

```txt
#MODE:LOOP
#LOOPS:unlimited
#FPS:2

```
- Each frame must be 8 lines of 30 characters
- Only ISO-8859-1 compatible characters are supported
- FPS controls animation speed
- LOOPS can be a number or `unlimited`


## Compatibility Notes

- The display does not support UTF-8
- Umlauts like `ä`, `ö`, `ü` work correctly if sent as `0xE4`, `0xF6`, `0xFC` (ISO-8859-1)
- Accented letters like `é`, `è` are not supported
- Control characters like STX/ETX are not required

## License

This project is licensed under the **GNU Affero General Public License v3.0**.

This means:
- You may use, modify and distribute the software freely.
- **If you make changes or run this software as a service (e.g., a web interface), you must also release your modified source code.**
- **Commercial use is only allowed if the full source code (including modifications) is also published under the same license.**

Full license text: [GNU AGPL v3.0](https://www.gnu.org/licenses/agpl-3.0.html)

© 2025 Jacob Koglin
---

**Developed to preserve and enable the use of historical display technology at the Berlin-Grünau Regatta course**
