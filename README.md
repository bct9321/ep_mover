# Episode Mover

`ep_mover.py` is a Python script to help organize episodic media files between two directories. It recursively compares file metadata (like episode codes) and moves files that don’t exist in the target directory. It supports dry-run mode, subtitle/video distinction, debug logging, and test scaffolding.

---

## 📦 Features

### ✅ Match & Move by Episode
- Parses filenames for `SXXEXX` episode codes.
- Only moves files that are **missing** in the destination (same show, episode, and type).
- Maintains full directory structure.

### 🎮 Distinguishes Video vs Subtitle
- Video extensions: `.mkv`, `.mp4`, `.avi`, etc.
- Subtitle extensions: `.sub`, `.srt`, `.ass`, etc.
- Keeps subtitle and video files separate in comparison logic.

### 🔮 Debug Mode
- Add `--debug` to log:
  - Directory traversal
  - File processing logic
  - Key mapping like `(show_name, S01E02, subtitle)`

```bash
python ep_mover.py run "/source" "/target" --debug
```

### 🔌 Interactive Prompts
- Confirm each move.
- Press `Enter` to confirm, or type `ALWAYS` to auto-confirm all remaining.

### 🪖 Safe Move Across Volumes
- Tries `os.rename()` first.
- Falls back to `shutil.copy2()` + `os.remove()`.
- Logs fallback with `--debug`.

### 🧰 Smart Filtering
- Skips:
  - Files with no SXXEXX code.
  - Files that would overwrite existing destination matches.

### 🛠️ Build Scenario Mode
- `python ep_mover.py build` creates a fake test case:
  - `expected_move - S01E01.file`  → file should move
  - `expected_stay - S01E01.file`  → file should stay (duplicate episode)
  - `destination_has - S01E01.file` → blocks source file

---

## 🚀 Usage

```bash
# Dry run comparison
python ep_mover.py run /source /target --dry-run

# Real move with confirmations
python ep_mover.py run /source /target

# With debug logs
python ep_mover.py run /source /target --debug

# Build a test scenario
python ep_mover.py build
```

---

## 🧪 Safety Checks

Before any moves:
- Confirms source/target folders exist.
- Prompts if either is empty or missing.
- Won’t proceed unless user confirms.

---

## 🔧 Key Comparison Logic

Each file is uniquely identified by:
```
(top-level folder, episode code like S01E02, file type: video/subtitle)
```
- Matching keys in destination will prevent a move.
- Files don’t need to match names, just episode code and type.

---

## 🔮 Debug Output
Enable with `--debug` to get insights like:
```
[build_files_by_key] Entering root: '/source/show_a/season_01'
  Files: ['ep - S01E01.mkv']
  => Found code='S01E01', show='show_a', type='video' => Key=('show_a', 'S01E01', 'video')
```

Also logs fallback to `copy2()` if `os.rename()` fails.

---

## 🤖 Testing
Use `test.py` to validate logic with `unittest`:

```bash
python test.py
```

- Verifies correct moves and skips
- Supports dry-run, interactive mode
- Uses temporary directories with full cleanup

---

## 🚶 Philosophy
- **Safety first**: Nothing is moved unless explicitly confirmed
- **Visibility**: Minimal logs by default, full trace with `--debug`
- **Media aware**: Built for real-world Plex folder structures

---

## 📄 License
MIT

