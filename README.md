# Cross-Platform Dictionary Application — Production Release (v1.0.0)

A high-performance, resilient, and cross-platform English Dictionary application built in pure Python and Flet. Designed to run seamlessly across **Windows**, **macOS**, **Linux**, **Web**, **Android**, and **iOS**.

---

## 1. System Architecture Overview

The application is structured into two decoupled packages:
* **`dict_core`**: Pure Python headless domain engine with zero GUI dependencies.
* **`dict_client_flet`**: Modern, reactive desktop and mobile presentation layer powered by Flet.

```
                                  User Query
                                      │
                                      ▼
                      ┌───────────────────────────────┐
                      │    Tier 1: SQLite Cache       │ < 0.1 ms (Instant)
                      └───────────────┬───────────────┘
                                      │ (Miss)
                                      ▼
                      ┌───────────────────────────────┐
                      │    Tier 2: Offline Lexicon    │ < 0.05 ms (Instant)
                      └───────────────┬───────────────┘
                                      │ (Miss)
                                      ▼
                      ┌───────────────────────────────┐
                      │  Tier 3: Free Dictionary API  │ 200 - 800 ms (Online)
                      └───────────────┬───────────────┘
                                      │ (Timeout / Failure)
                                      ▼
                      ┌───────────────────────────────┐
                      │  Tier 4: Wiktionary REST API  │ 300 - 900 ms (Fallback)
                      └───────────────┬───────────────┘
                                      │
                                      ▼
                      ┌───────────────────────────────┐
                      │    Sense Ranking Engine       │ Sorts by Definition Quality
                      └───────────────┬───────────────┘
                                      │
                                      ▼
                      ┌───────────────────────────────┐
                      │    Audio & Cache Storage      │ SHA-256 Binary Audio & SQLite
                      └───────────────┬───────────────┘
                                      │
                                      ▼
                      ┌───────────────────────────────┐
                      │     Reactive Flet Client      │ Desktop & Mobile UI
                      └───────────────────────────────┘
```

---

## 2. Key Features

1. **4-Tier Resilient Lookup Pipeline**:
   - **Tier 1 (Cache)**: Local SQLite cache indexed by term ($O(1)$ fast lookup).
   - **Tier 2 (Offline Lexicon)**: Built-in local dictionary database delivering instantaneous lookups when offline.
   - **Tier 3 (Primary API)**: High-detail dictionary definitions from Free Dictionary API.
   - **Tier 4 (Fallback API)**: Automated failover to Wiktionary REST API when the primary API times out or fails.
2. **Deterministic Sense Ranking Engine**:
   - Scores and ranks word senses based on grammatical completeness, example sentence availability, and frequency heuristics.
3. **Cross-Platform Audio Playback & Caching**:
   - SHA-256 hashed binary audio disk caching with atomic write protection and automatic corrupted-file self-healing.
   - Multi-driver playback engine: Linux (`paplay`, `aplay`, `ffplay`), macOS (`afplay`), Windows (`winsound`, PowerShell, `wmplayer`), and Flet UI player.
4. **Reactive Flet UI**:
   - Responsive layout adapting between desktop (NavigationRail) and mobile (NavigationBar).
   - Instant Dark Mode / Light Mode switching with high-contrast accessibility tokens.
   - Separate, independent Search, Favorites, and Search History tabs with full lifecycle restoration.
5. **Headless CLI & REPL**:
   - Comprehensive command-line interface for quick terminal definitions, history logs, and favorites inspection.

---

## 3. Installation & Quickstart

### Prerequisites
* **Python**: 3.10, 3.11, or 3.12
* **Operating System**: Windows 10/11, macOS, or Linux

### Setup Environment
```bash
# 1. Extract package
unzip dictionary_project_part7_production.zip -d dictionary_project
cd dictionary_project

# 2. Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate       # On Windows: .\venv\Scripts\Activate.ps1

# 3. Install dependencies
pip install -r requirements.txt
```

---

## 4. Running the Application

### **Option A: Graphical Desktop App (Flet UI)**
```bash
# Direct launcher:
python run_gui.py

# Or via package module:
python -m dict_client_flet.main

# On Windows:
run_app.bat

# On Linux / macOS:
./run_app.sh
```

### **Option B: Command-Line Interface (CLI)**
```bash
# Look up a word:
python run_cli.py lookup serendipity
python -m dict_core lookup resilience

# Start interactive dictionary REPL:
python run_cli.py interactive

# View search history:
python run_cli.py history

# View saved vocabulary:
python run_cli.py favorites

# Run performance benchmarks:
python run_cli.py benchmark
```

---

## 5. Running Automated Tests

The automated test suite contains **164 tests** verifying models, providers, caching, audio, rankings, state management, and production packaging.

```bash
# Run the complete test suite:
python3 -m unittest discover -s tests -p "test_*.py" -v

# Run specific subsystem test suites:
python3 -m unittest tests/test_production_packaging.py -v   # Packaging & CLI
python3 -m unittest tests/test_part6_integration_e2e.py -v   # End-to-end integration
python3 -m unittest tests/test_audio_service.py -v          # Binary audio caching
python3 -m unittest tests/test_sense_ranker.py -v           # Sense ranking engine
python3 -m unittest tests/test_app_state.py -v              # UI state & navigation
python3 -m unittest tests/test_offline_provider.py -v       # Offline lexicon
```

---

## 6. Building Distribution Packages

An automated verification and build script is provided to validate all assets and build distributable Python wheels (`.whl`) and source archives (`.tar.gz`):

```bash
python3 build_distribution.py
```

Built packages are output to `dist/`:
* `dist/dictionary_app-1.0.0-py3-none-any.whl`
* `dist/dictionary_app-1.0.0.tar.gz`

To install the built wheel into any Python environment:
```bash
pip install dist/dictionary_app-1.0.0-py3-none-any.whl
```
Once installed, the CLI and GUI commands are available system-wide:
```bash
dict-cli lookup serendipity
dict-gui
```

---

## 7. Environment Configuration Variables

| Variable | Default | Description |
| :--- | :--- | :--- |
| `DICT_APP_STORAGE` | OS Standard | Base storage folder for SQLite cache, database, and audio files. |
| `DICT_INTERACTIVE_TIMEOUT` | `2.5` | Timeout in seconds for interactive user lookups before fallback. |
| `DICT_CACHE_TTL_DAYS` | `30` | Number of days before cached definitions expire. |
| `DICT_LIVE_TESTS` | `0` | Set to `1` to run optional live internet API integration tests. |
