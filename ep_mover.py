#!/usr/bin/env python3
"""
ep_mover.py

This script compares two directories of TV episode files based on a composite key:
(top-level show folder, SXXEXX code, file type). If the destination has a file
for that same key, we now compare preference scores (based on tags_config.json).
If the source file is higher-scored, we overwrite the target's file; otherwise we skip.

By default, it prints minimal logs:
  - MOVE: <src> => <dest>
  - DRY-RUN: <src> => <dest>
  - SKIP: <src> => <reason>

Use --debug to see additional [DEBUG] logs.

Modes:
    - run: Move (or dry-run) files
    - build: Create a fake scenario for manual testing
"""

import os
import re
import shutil
import argparse
import sys
import json

# -------------------------------------------------
# Configuration: Minimal vs. Debug Logging
# -------------------------------------------------
DEBUG = False  # Will be set to True if --debug is passed

def debug_log(msg):
    """
    Prints debug messages only if DEBUG is True.
    """
    if DEBUG:
        print(f"[DEBUG] {msg}")

# -------------------------------------------------
# Load Tags Config
# -------------------------------------------------
def load_tags_config(config_path="tags_config.json"):
    """
    Loads a JSON file containing custom tags and their scores.
    Example structure:
      {
        "tags": [
          { "match": "4k",    "score": 30 },
          { "match": "1080p", "score": 20 },
          { "match": "720p",  "score": 10 }
        ]
      }
    """
    if not os.path.isfile(config_path):
        debug_log(f"No tags_config found at '{config_path}'. Using empty tags list.")
        return []
    with open(config_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("tags", [])

def compute_file_score(filename, tags):
    """
    Scans the filename for each tag's 'match' string (case-insensitive).
    If found, adds 'score' to total. Returns the sum of all matched tags.
    """
    lower_name = filename.lower()
    total_score = 0
    for entry in tags:
        match_str = entry.get("match", "").lower()
        score_val = entry.get("score", 0)
        if match_str and match_str in lower_name:
            total_score += score_val
    return total_score

# -------------------------------------------------
# Pre-check to Avoid Common Mistakes
# -------------------------------------------------
def check_directory_validity(path, role):
    """
    Ensures 'path' exists and warns if it's empty.
    role = "source" or "destination" (for user-friendly messages).

    Returns True if the user wants to proceed, False if they want to abort.
    """
    if not os.path.isdir(path):
        print(f"WARNING: The {role} directory '{path}' does not exist or is not a directory.")
        user = input("Continue anyway? (y/N): ")
        if user.strip().lower() != 'y':
            return False
        return True

    # Count subfolders/files
    item_count = 0
    for root, dirs, files in os.walk(path):
        item_count += len(files) + len(dirs)
    if item_count == 0:
        print(f"WARNING: The {role} directory '{path}' exists but is empty.")
        user = input("Continue anyway? (y/N): ")
        if user.strip().lower() != 'y':
            return False
    return True

# -------------------------------------------------
# Helper Functions
# -------------------------------------------------
def write_file(path, content):
    """
    Creates all necessary parent directories and writes the given content to the file at 'path'.
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)

def all_files(directory):
    """
    Recursively collects all file paths in the directory tree.
    """
    result = {}
    for root, dirs, files in os.walk(directory):
        for file in files:
            result[os.path.join(root, file)] = True
    return result

# -------------------------------------------------
# Classification & Uniqueness Key
# -------------------------------------------------
VIDEO_EXTENSIONS = {'.mkv', '.mp4', '.avi', '.mov', '.wmv', '.flv', '.mpeg', '.mpg'}
SUBTITLE_EXTENSIONS = {'.sub', '.srt', '.ass', '.ssa'}

def classify_file(filename):
    """
    Classifies a file as "video" or "subtitle" based on its file extension.
    """
    ext = os.path.splitext(filename)[1].lower()
    if ext in SUBTITLE_EXTENSIONS:
        return "subtitle"
    return "video"

def get_episode_code(filename):
    """
    Extracts the SXXEXX pattern from 'filename' (case-insensitive).
    Supports up to 4 digits in the E-part (S01E100, S01E1000).
    Returns uppercase code (e.g. "S01E100") or None if not found.
    """
    match = re.search(r'S\d{2}E\d{2,4}', filename, re.IGNORECASE)
    return match.group(0).upper() if match else None

def get_top_level_show(path, base_dir):
    """
    Returns the top-level folder name for 'path' relative to 'base_dir'.
    If there's no subfolder, returns "NO_TOP_LEVEL".
    """
    rel_path = os.path.relpath(path, base_dir)
    parts = rel_path.split(os.sep)
    return parts[0] if len(parts) > 1 else "NO_TOP_LEVEL"

# -------------------------------------------------
# Build dictionary with preference scoring
# -------------------------------------------------
def build_files_by_key(directory, tags_config=None):
    """
    Recursively walks 'directory' and builds a dictionary mapping:
      (top_show, episode_code, file_type) -> (score, path).

    If multiple files match the same key, picks the higher-scored file (based on tags).
    """
    if tags_config is None:
        tags_config = []

    debug_log(f"[build_files_by_key] Starting for directory: {directory}")
    files_dict = {}

    for root, dirs, files in os.walk(directory):
        debug_log(f"[build_files_by_key] Entering root: '{root}'")
        debug_log(f"  Subdirectories: {dirs}")
        debug_log(f"  Files: {files} (count: {len(files)})")

        for file in files:
            debug_log(f"    [FILE] Examining '{file}' in '{root}'")
            code = get_episode_code(file)
            if code:
                ftype = classify_file(file)
                full_path = os.path.join(root, file)
                top_show = get_top_level_show(full_path, directory)
                key = (top_show, code, ftype)

                # Compute file's score from tags
                score = compute_file_score(file, tags_config)
                debug_log(f"      => Found code='{code}', show='{top_show}', type='{ftype}', score={score}")

                # If there's already a file for this key, pick the higher-scored one
                if key not in files_dict:
                    files_dict[key] = (score, full_path)
                else:
                    existing_score, existing_path = files_dict[key]
                    if score > existing_score:
                        files_dict[key] = (score, full_path)
            else:
                debug_log(f"      => No SXXEXX code in '{file}', ignoring.")

    debug_log("[build_files_by_key] Finished building dictionary.\n")
    return files_dict  # returns { key: (score, path) }

# -------------------------------------------------
# Interactive Confirmation & Fallback Move
# -------------------------------------------------
ALWAYS_MODE = False

def confirm_action(src, dest, interactive=True):
    """
    Prompts the user to confirm moving a file from 'src' to 'dest'.
    If interactive is False or ALWAYS_MODE is True, returns True immediately.
    """
    global ALWAYS_MODE
    if not interactive or ALWAYS_MODE:
        return True
    prompt = (f"Move '{src}' to '{dest}'?\n"
              f"(Press Enter to confirm, type 'ALWAYS' to confirm all, or any other input to skip): ")
    response = input(prompt)
    if response.strip().upper() == "ALWAYS":
        ALWAYS_MODE = True
        return True
    return response.strip() == ""

def safe_move(src, dst):
    """
    Attempts os.rename(src, dst). If that fails (cross-volume), falls back to copy2 + remove.
    """
    debug_log(f"safe_move() rename '{src}' -> '{dst}'")
    try:
        os.rename(src, dst)
    except OSError as e:
        debug_log(f"safe_move() rename failed: {e}, fallback to copy+remove.")
        parent_dir = os.path.dirname(dst)
        if not os.path.exists(parent_dir):
            debug_log(f"Re-creating parent directory: {parent_dir}")
            os.makedirs(parent_dir, exist_ok=True)
        shutil.copy2(src, dst)
        os.remove(src)

# -------------------------------------------------
# Output Logging for Move/Skip
# -------------------------------------------------
def log_move(src, dest, dry_run=False):
    """
    Logs a single line for a move or dry-run action:
      DRY-RUN: <src> => <dest>
      MOVE: <src> => <dest>
    """
    if dry_run:
        print(f"DRY-RUN: {src} => {dest}")
    else:
        print(f"MOVE: {src} => {dest}")

def log_skip(src, reason):
    """
    Logs a single line for a skip action:
      SKIP: <src> => {reason}
    """
    print(f"SKIP: {src} => {reason}")

# -------------------------------------------------
# Main Move Logic
# -------------------------------------------------
def move_missing_files(source_dir, target_dir, dry_run=False, interactive=True):
    """
    For each file in source_dir that has a recognized SXXEXX code, compare it with any
    existing file in the target for that same (top_show, code, file_type).
      - If target doesn't have it, move source.
      - If target does have it, compare scores:
        * If source > target, remove target and move source
        * Else skip source
    """
    # Load tags config
    tags = load_tags_config()

    debug_log(f"Building dictionary for source: {source_dir}")
    src_files = build_files_by_key(source_dir, tags_config=tags)  # { key: (score, path) }
    debug_log(f"Building dictionary for target: {target_dir}")
    tgt_files = build_files_by_key(target_dir, tags_config=tags)  # { key: (score, path) }

    for key, (src_score, src_path) in src_files.items():
        debug_log(f"\nChecking key {key} => (score={src_score}, path={src_path})")

        if key not in tgt_files:
            # No file in target => move the source
            rel_path = os.path.relpath(src_path, source_dir)
            dest_full_path = os.path.join(target_dir, rel_path)
            debug_log(f"  => Key not in target, preparing to move '{src_path}' to '{dest_full_path}'")

            if os.path.exists(dest_full_path):
                debug_log(f"  => Collision: {dest_full_path} already exists; skipping.")
                log_skip(src_path, "collision in target")
                continue
            if not confirm_action(src_path, dest_full_path, interactive):
                debug_log(f"  => User canceled {src_path}")
                log_skip(src_path, "user canceled")
                continue
            log_move(src_path, dest_full_path, dry_run=dry_run)
            if not dry_run:
                safe_move(src_path, dest_full_path)
                # Mark it as present
                tgt_files[key] = (src_score, dest_full_path)
        else:
            # Compare scores
            existing_tgt_score, existing_tgt_path = tgt_files[key]
            debug_log(f"  => Key {key} found in target => comparing scores: src={src_score} vs tgt={existing_tgt_score}")
            if src_score > existing_tgt_score:
                # Overwrite target
                debug_log(f"  => Source is higher scored => replacing target '{existing_tgt_path}'")
                # Remove existing target file
                if not dry_run:
                    if os.path.exists(existing_tgt_path):
                        os.remove(existing_tgt_path)

                # Move the source file in
                rel_path = os.path.relpath(src_path, source_dir)
                dest_full_path = os.path.join(target_dir, rel_path)
                if not confirm_action(src_path, dest_full_path, interactive):
                    debug_log(f"  => User canceled {src_path}")
                    log_skip(src_path, "user canceled (overwrite aborted)")
                    continue
                log_move(src_path, dest_full_path, dry_run=dry_run)
                if not dry_run:
                    safe_move(src_path, dest_full_path)
                    tgt_files[key] = (src_score, dest_full_path)
            else:
                debug_log(f"  => Target is higher or equal => skipping {src_path}")
                log_skip(src_path, "lower-scored than target")

# -------------------------------------------------
# Build Mode
# -------------------------------------------------
def build_fake_scenario():
    """
    Creates a fake scenario with more intuitive naming, now using .mkv for videos and .ass for subs:
      - "expected_move - SXXEXX [TAG].mkv" => no match in target => moves
      - "expected_stay - SXXEXX [TAG].mkv" => match in target => stays
      - "destination_has - SXXEXX [TAG].mkv" => in target, blocks source

    Includes episodes like S01E100 and S01E1000 for extended tests.
    Demonstrates 720p, 1080p, 2160p in filenames for tag-based scoring.
    """

    import os
    import shutil

    base_dir = os.path.join(os.getcwd(), "fake_scenario")
    if os.path.exists(base_dir):
        shutil.rmtree(base_dir)

    source_dir = os.path.join(base_dir, "shows")
    dest_dir = os.path.join(base_dir, "shows2")

    # Create subfolders in source
    os.makedirs(os.path.join(source_dir, "show_a", "season_01"), exist_ok=True)
    os.makedirs(os.path.join(source_dir, "show_a", "season_02"), exist_ok=True)
    os.makedirs(os.path.join(source_dir, "show_b", "season_01"), exist_ok=True)
    os.makedirs(os.path.join(source_dir, "show_b", "season_02"), exist_ok=True)
    os.makedirs(os.path.join(source_dir, "show_c", "season_01"), exist_ok=True)
    os.makedirs(os.path.join(source_dir, "show_x", "season_01"), exist_ok=True)
    os.makedirs(os.path.join(source_dir, "show_y", "season_01"), exist_ok=True)

    # show_a - Season 01
    write_file(
        os.path.join(source_dir, "show_a", "season_01", "expected_stay - S01E01 [720p].mkv"),
        "Video content A S01E01 (blocked by target's S01E01) => 720p"
    )
    write_file(
        os.path.join(source_dir, "show_a", "season_01", "expected_move - S01E01 [1080p].ass"),
        "Subtitle content A S01E01 => 1080p"
    )
    write_file(
        os.path.join(source_dir, "show_a", "season_01", "expected_move - S01E02 [2160p].mkv"),
        "Video content A S01E02 => 4k"
    )
    # Extended episodes
    write_file(
        os.path.join(source_dir, "show_a", "season_01", "expected_move - S01E100 [2160p].mkv"),
        "Video content A S01E100 => 4k"
    )
    write_file(
        os.path.join(source_dir, "show_a", "season_01", "expected_move - S01E1000 [1080p].mkv"),
        "Video content A S01E1000 => 1080p"
    )

    # show_a - Season 02
    write_file(
        os.path.join(source_dir, "show_a", "season_02", "expected_move - S01E04 [720p].mkv"),
        "Extra video content A S01E04 => 720p"
    )

    # show_b
    write_file(
        os.path.join(source_dir, "show_b", "season_01", "expected_stay - S01E05 [1080p].mkv"),
        "Video B S01E05 => 1080p (blocked by target S01E05)"
    )
    write_file(
        os.path.join(source_dir, "show_b", "season_02", "expected_stay - S02E01 [720p].mkv"),
        "Video B S02E01 => 720p (blocked by target S02E01)"
    )
    write_file(
        os.path.join(source_dir, "show_b", "season_02", "expected_move - S02E02 [1080p].ass"),
        "Subtitle B S02E02 => 1080p"
    )

    # show_c
    write_file(
        os.path.join(source_dir, "show_c", "season_01", "expected_move - S01E01 [2160p].mkv"),
        "Unique video content C S01E01 => 4k"
    )

    # show_x
    write_file(
        os.path.join(source_dir, "show_x", "season_01", "expected_stay - S01E01 [720p].mkv"),
        "X S01E01 => 720p (blocked by target S01E01)"
    )

    # show_y
    write_file(
        os.path.join(source_dir, "show_y", "season_01", "expected_move - S01E01 [1080p].mkv"),
        "Y S01E01 => 1080p"
    )

    # Create subfolders in destination
    os.makedirs(os.path.join(dest_dir, "show_a", "season_01"), exist_ok=True)
    os.makedirs(os.path.join(dest_dir, "show_b", "season_01"), exist_ok=True)
    os.makedirs(os.path.join(dest_dir, "show_b", "season_02"), exist_ok=True)
    os.makedirs(os.path.join(dest_dir, "show_d", "season_01"), exist_ok=True)
    os.makedirs(os.path.join(dest_dir, "show_x", "season_01"), exist_ok=True)

    # Destination existing
    write_file(
        os.path.join(dest_dir, "show_a", "season_01", "destination_has - S01E01 [720p].mkv"),
        "Video A S01E01 => 720p blocking the source's S01E01"
    )
    write_file(
        os.path.join(dest_dir, "show_b", "season_01", "destination_has - S01E05 [1080p].mkv"),
        "Video B S01E05 => 1080p blocking the source's S01E05"
    )
    write_file(
        os.path.join(dest_dir, "show_b", "season_02", "destination_has - S02E01 [720p].mkv"),
        "Video B S02E01 => 720p blocking the source's S02E01"
    )
    write_file(
        os.path.join(dest_dir, "show_d", "season_01", "uniqueD - S01E01.mkv"),
        "Unique video D S01E01 => not matched by anything in source"
    )
    write_file(
        os.path.join(dest_dir, "show_x", "season_01", "destination_has - S01E01 [720p].mkv"),
        "X S01E01 => 720p existing in target"
    )

    # Add a lower-scored target file for S01E02 so we can see if the source's 2160p overwrites it
    write_file(
        os.path.join(dest_dir, "show_a", "season_01", "destination_has - S01E02 [1080p].mkv"),
        "Video A S01E02 => 1080p, so source S01E02 [2160p].mkv can overwrite it if higher-scored"
    )

    print("Fake scenario built successfully with .mkv and .ass filenames, plus resolution tags!")
    print(f"Source Directory: {source_dir}")
    print(f"Destination Directory: {dest_dir}")
    print("\nFor example, run:")
    print(f"  python {os.path.basename(__file__)} run \"{source_dir}\" \"{dest_dir}\" [--dry-run]")

# -------------------------------------------------
# Main CLI
# -------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Recursively move files based on (top-level show, SXXEXX code, file type) uniqueness and tag-based scoring."
    )
    subparsers = parser.add_subparsers(dest='command', help='Sub-command help')

    run_parser = subparsers.add_parser('run', help='Run file move operation')
    run_parser.add_argument('source_dir', help='Path to the source directory (searched recursively)')
    run_parser.add_argument('target_dir', help='Path to the destination directory (files will be moved here, preserving subfolder structure)')
    run_parser.add_argument('--dry-run', action='store_true', help='Perform a dry run without moving any files')
    run_parser.add_argument('--debug', action='store_true', help='Enable debug/verbose logs')

    build_parser = subparsers.add_parser('build', help='Build a more complex scenario for manual testing')

    args = parser.parse_args()
    if args.command == 'run':
        global DEBUG
        DEBUG = args.debug  # Set the global debug flag

        # Pre-check source directory
        if not check_directory_validity(args.source_dir, "source"):
            print("Aborting due to invalid or empty source directory.")
            sys.exit(1)
        # Pre-check target directory
        if not check_directory_validity(args.target_dir, "destination"):
            print("Aborting due to invalid or empty target directory.")
            sys.exit(1)

        print(f"Processing files from {args.source_dir} to {args.target_dir}...")
        move_missing_files(args.source_dir, args.target_dir, dry_run=args.dry_run, interactive=True)
        print("\nOperation complete.")
    elif args.command == 'build':
        build_fake_scenario()
    else:
        parser.print_help()

if __name__ == '__main__':
    main()
