# User Guide: Cross-Platform Dictionary Application

---

## 1. Overview

The **Cross-Platform Dictionary Application** is a high-performance, modular English dictionary application built in Python. It provides instant word lookups, phonetic transcriptions (IPA), human-recorded pronunciation audio, contextual example sentences, synonyms, antonyms, search history, and a personal vocabulary bookmarking system.

The application operates across **Windows, macOS, Linux, Android, iOS, and Web** through two decoupled packages:
* **`dict_core`**: A standalone, headless Python library containing all data models, local caching, offline lexicons, and network adapters.
* **`dict_client_flet`**: A modern graphical desktop/mobile interface powered by Flet (Flutter engine).
* **Command-Line Interface (CLI)**: A built-in terminal interface for fast queries, interactive sessions, and automated scripting.

---

## 2. Key Features

### 1. **4-Tier Intelligent Lookup Engine**
Every word query passes through an optimized 4-tier pipeline to guarantee maximum speed and offline reliability:
* **Tier 1 (Local SQLite Cache)**: Returns previously queried words in **< 0.1 ms** with zero network traffic.
* **Tier 2 (Bundled Offline Lexicon)**: Delivers instant definitions (**< 0.05 ms**) for core English vocabulary when offline.
* **Tier 3 (Free Dictionary API)**: Fetches detailed definitions, phonetic notations, and pronunciation audio streams online.
* **Tier 4 (Wiktionary REST API Fallback)**: Automatically activates if the primary API experiences downtime or network latency.

### 2. **Sense Ranking & Definition Quality**
* Definitions are automatically grouped by part of speech (*Noun, Verb, Adjective, Adverb, etc.*).
* Senses are ranked using heuristic scoring, prioritizing comprehensive meanings with verified usage examples and synonyms.

### 3. **Pronunciation Audio & Binary Caching**
* **One-Click Playback**: Click the speaker icon on any word to listen to its pronunciation.
* **Disk Caching**: Audio files are downloaded once, validated against corruption, and cached locally as SHA-256 hashed `.mp3` files for offline replay.
* **Multi-Platform Audio Drivers**: Direct playback support on Windows (PowerShell/Native), macOS (`afplay`), Linux (`paplay`, `aplay`), and the Flet UI audio driver.

### 4. **Vocabulary Lists & Search History**
* **Starred Favorites**: Save important words with a single click, add custom notes, and filter by tags for vocabulary building.
* **Search History**: Automatically logs queries chronologically, recording the timestamp, source provider, and result status.

### 5. **Clean, Responsive UI with Dark/Light Themes**
* **Adaptive Navigation**: Switches between a vertical `NavigationRail` on desktop screens and a compact bottom `NavigationBar` on mobile devices.
* **Theme Switching**: Instant toggle between Light Mode and Dark Mode.

---

## 3. Installation & Quickstart

### **Step 1: Extract and Setup Environment**
```bash
# Extract the archive
unzip dictionary_project_part7_production.zip -d dictionary_project
cd dictionary_project

# Create a virtual environment
python3 -m venv venv

# Activate the virtual environment
# On Linux / macOS:
source venv/bin/activate

# On Windows (PowerShell):
.\venv\Scripts\Activate.ps1
```

### **Step 2: Install Dependencies**
```bash
pip install -r requirements.txt
```

---

## 4. How to Use the Graphical Application (GUI)

### **Launching the GUI**
Run any of the following commands:
```bash
# Direct launcher
python run_gui.py

# Or module launcher
python -m dict_client_flet.main

# On Windows (Double-click or run):
run_app.bat

# On Linux / macOS:
./run_app.sh
```

---

### **GUI Navigation & Workflow**

```
┌─────────────────────────────────────────────────────────────┐
│ 📚 Dictionary                                           🌙  │
├───────────┬─────────────────────────────────────────────────┤
│ 🔍 Search │  [ Search a word...                          → ]│
│           │                                                 │
│ ⭐ Favs   │  SERENDIPITY  /ˌsɛr.ənˈdɪp.ɪ.ti/  🔊  ❤️        │
│           │  [Source: Free Dictionary API | Cached]         │
│ 🕒 History│                                                 │
│           │  ┌─ NOUN ─────────────────────────────────────┐ │
│           │  │ 1. The occurrence of events by chance in a │ │
│           │  │    happy or beneficial way.                │ │
│           │  │    "Finding this book was pure serendipity"│ │
│           │  │    Synonyms: chance, fluke, fortune        │ │
│           │  └────────────────────────────────────────────┘ │
└───────────┴─────────────────────────────────────────────────┘
```

#### **1. Search Screen**
* **Searching a Word**: Type any word into the top search bar and press **Enter** or click the **Arrow** button.
* **Pronunciation**: Click the **Speaker icon (`🔊`)** next to the phonetic text to listen to the audio.
* **Bookmarking**: Click the **Heart icon (`❤️`)** in the upper-right corner to save the word to your Favorites.
* **Clear Search**: Click the **`✕`** icon inside the search bar to reset the input field.

#### **2. Favorites Screen**
* View all your starred words in one place.
* Click the **Search icon** on any card to immediately view its full definition on the Search screen.
* Click the **Trash icon** to remove an item from your saved list.

#### **3. History Screen**
* Displays your recent lookups in reverse chronological order with timestamps and result indicators (`Found` vs `404`).
* Click on any past query to re-run the search instantly.
* Click **Clear History** in the upper-right corner to erase the log.

#### **4. Theme Toggle**
* Click the **Moon / Sun icon** in the top navigation bar to toggle between Dark Mode and Light Mode.

---

## 5. How to Use the Command-Line Interface (CLI)

The application includes a command-line interface for terminal workflows, headless environments, and automation.

### **Single Word Lookup**
```bash
python run_cli.py lookup serendipity
```
*Options:*
* `--audio` / `-a`: Plays the pronunciation audio through your system's speakers.
* `--force-refresh` / `-f`: Bypasses the local cache to fetch a fresh definition from online providers.

*Example Output:*
```text
============================================================
  SERENDIPITY  /ˌsɛr.ənˈdɪp.ɪ.ti/
============================================================
[Source: offline_lexicon | Cached: Yes]

  [NOUN]
    1. The occurrence of events by chance in a happy or beneficial way.
       Example: "Finding this rare book in an old shop was pure serendipity."
       Synonyms: chance, happy accident, fluke, fortune

Pronunciation Audio: https://api.dictionaryapi.dev/media/pronunciations/en/serendipity-us.mp3
```

---

### **Interactive REPL Shell**
Launch an interactive dictionary session where you can query multiple words consecutively:
```bash
python run_cli.py interactive
```
```text
============================================================
  Dictionary Interactive CLI Shell
  Type any English word to look up (or 'exit' / 'quit' to close)
============================================================

dict> lucid
...
dict> resilience
...
dict> quit
Goodbye!
```

---

### **View Search History via CLI**
```bash
# View last 20 queries:
python run_cli.py history

# Clear search history:
python run_cli.py history --clear
```

---

### **View Saved Favorites via CLI**
```bash
python run_cli.py favorites
```

---

### **Run Multi-Tier Latency Benchmark**
Measure query execution times across all 4 tiers:
```bash
python run_cli.py benchmark --words 20
```

---

## 6. Data Storage & File Locations

All persistent data (SQLite databases, search history, favorites, and binary audio files) is stored in the standard user directory for your operating system:

| Platform | Storage Location |
| :--- | :--- |
| **Windows** | `%APPDATA%\DictionaryApp\` (e.g. `C:\Users\<User>\AppData\Roaming\DictionaryApp\`) |
| **macOS** | `~/Library/Application Support/DictionaryApp/` |
| **Linux / Unix** | `~/.local/share/dictionary_app/` (or `$XDG_DATA_HOME/dictionary_app/`) |

### **Storage Contents**
* `dictionary.db`: SQLite database storing search history, user favorites, and the `word_cache` table.
* `audio_cache/`: Folder containing SHA-256 hashed `.mp3` / `.ogg` audio files.

---

## 7. Environment Variables & Configuration

You can customize the application's behavior using the following environment variables:

| Variable | Default | Description |
| :--- | :--- | :--- |
| `DICT_APP_STORAGE` | OS Default | Custom directory path for SQLite databases and audio cache files. |
| `DICT_INTERACTIVE_TIMEOUT` | `2.5` | Timeout (in seconds) for online lookups before falling back to alternative sources. |
| `DICT_CACHE_TTL_DAYS` | `30` | Number of days before cached definitions expire. |
| `DICT_DEFAULT_PROVIDER` | `free_dict_api` | Primary online provider identifier. |
| `DICT_LIVE_TESTS` | `0` | Set to `1` to enable live internet integration tests during test runs. |

---

## 8. Troubleshooting & FAQ

### **1. Audio does not play on Linux**
Ensure that a basic audio utility (`pulseaudio-utils`, `alsa-utils`, or `ffmpeg`) is available:
```bash
# Ubuntu / Debian:
sudo apt-get install pulseaudio-utils alsa-utils
```

### **2. Running without an internet connection**
The application works completely offline for core English vocabulary using its built-in offline database. Words previously searched online remain cached locally and are instantly accessible offline.

### **3. Running the test suite**
To verify all 164 automated unit and integration tests:
```bash
python3 -m unittest discover -s tests -p "test_*.py" -v
```
