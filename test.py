import os
import stat
import unittest
import tempfile
import shutil
from unittest.mock import patch

# Import everything you need from ep_mover
from ep_mover import (
    move_missing_files,
    build_files_by_key,
    all_files,
    write_file,
    get_episode_code,
    get_top_level_show,
    classify_file
)

class ExtendedCoverageTests(unittest.TestCase):
    """
    Additional tests that address coverage gaps, using ep_mover.py functions.
    """

    def setUp(self):
        # Create temporary directories for source and target
        self.source_dir = tempfile.mkdtemp()
        self.target_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.source_dir, ignore_errors=True)
        shutil.rmtree(self.target_dir, ignore_errors=True)

    def test_multiple_source_files_same_episode_code(self):
        """
        If multiple files in the source have the same (show, code, type),
        only the first is moved (based on default or tag logic).
        """
        os.makedirs(os.path.join(self.source_dir, "show_x"), exist_ok=True)
        write_file(os.path.join(self.source_dir, "show_x", "first - S01E01.file"), "Content1")
        write_file(os.path.join(self.source_dir, "show_x", "second - S01E01.file"), "Content2")

        move_missing_files(self.source_dir, self.target_dir, dry_run=False, interactive=False)
        target_files = build_files_by_key(self.target_dir)

        # Key = ("show_x", "S01E01", "video")
        # Now build_files_by_key() returns a single path (string), not a list.
        moved_file = target_files[("show_x", "S01E01", "video")]
        self.assertIn("first - S01E01.file", moved_file, "Expected the first file to be moved.")
        self.assertTrue(
            os.path.exists(os.path.join(self.source_dir, "show_x", "second - S01E01.file")),
            "Second file remains in source."
        )

    def test_multiple_target_files_same_episode_code(self):
        """
        If the target already has multiple files for the same (show, code, type),
        we skip the source file.
        """
        os.makedirs(os.path.join(self.target_dir, "show_x"), exist_ok=True)
        write_file(os.path.join(self.target_dir, "show_x", "already1 - S01E02.file"), "T content 1")
        write_file(os.path.join(self.target_dir, "show_x", "already2 - S01E02.file"), "T content 2")

        os.makedirs(os.path.join(self.source_dir, "show_x"), exist_ok=True)
        write_file(os.path.join(self.source_dir, "show_x", "source - S01E02.file"), "S content")

        move_missing_files(self.source_dir, self.target_dir, dry_run=False, interactive=False)
        self.assertTrue(
            os.path.exists(os.path.join(self.source_dir, "show_x", "source - S01E02.file")),
            "Source file remains because target has S01E02 already."
        )

    def test_mixed_file_formats_same_episode(self):
        """
        If the target has S01E01.mp4, the source's S01E01.mkv is considered the same type (video).
        """
        os.makedirs(os.path.join(self.target_dir, "show_x"), exist_ok=True)
        write_file(os.path.join(self.target_dir, "show_x", "existing - S01E01.mp4"), "T mp4")

        os.makedirs(os.path.join(self.source_dir, "show_x"), exist_ok=True)
        write_file(os.path.join(self.source_dir, "show_x", "maybe - S01E01.mkv"), "S mkv")

        move_missing_files(self.source_dir, self.target_dir, dry_run=False, interactive=False)
        self.assertTrue(
            os.path.exists(os.path.join(self.source_dir, "show_x", "maybe - S01E01.mkv")),
            "Should remain in source, since target had show_x/S01E01 video already."
        )

    def test_no_episode_code(self):
        """
        A file with no SXXEXX pattern is ignored.
        """
        write_file(os.path.join(self.source_dir, "random.file"), "No code here")

        move_missing_files(self.source_dir, self.target_dir, dry_run=False, interactive=False)
        self.assertTrue(
            os.path.exists(os.path.join(self.source_dir, "random.file")),
            "No code => not moved."
        )
        self.assertFalse(
            os.path.exists(os.path.join(self.target_dir, "random.file")),
            "Should not appear in target."
        )

    def test_top_level_missing_folder(self):
        """
        If a file is directly in source_dir (no top-level folder), we label it "NO_TOP_LEVEL".
        If the target doesn't have that key, we move it to target root.
        """
        write_file(os.path.join(self.source_dir, "should_move - S01E01.file"), "Root content")

        move_missing_files(self.source_dir, self.target_dir, dry_run=False, interactive=False)
        self.assertTrue(
            os.path.exists(os.path.join(self.target_dir, "should_move - S01E01.file")),
            "File from root => moved to target root if no match."
        )

    @patch("builtins.input", side_effect=["", "ALWAYS"])
    def test_interactive_behavior(self, mock_input):
        """
        Mock user input: first press Enter => confirm first file,
        second type "ALWAYS" => confirm all subsequent.
        """
        os.makedirs(os.path.join(self.source_dir, "show_x"), exist_ok=True)
        write_file(os.path.join(self.source_dir, "show_x", "should_move1 - S01E01.file"), "File content 1")
        write_file(os.path.join(self.source_dir, "show_x", "should_move2 - S01E01.sub"), "Subtitle content 2")

        move_missing_files(self.source_dir, self.target_dir, dry_run=False, interactive=True)

        self.assertTrue(
            os.path.exists(os.path.join(self.target_dir, "show_x", "should_move1 - S01E01.file"))
        )
        self.assertTrue(
            os.path.exists(os.path.join(self.target_dir, "show_x", "should_move2 - S01E01.sub"))
        )

    def test_filename_collision(self):
        """
        If the script tries to move a file and the exact same filename already exists in target,
        we skip the move.
        """
        os.makedirs(os.path.join(self.source_dir, "show_x"), exist_ok=True)
        os.makedirs(os.path.join(self.target_dir, "show_x"), exist_ok=True)

        src_file = os.path.join(self.source_dir, "show_x", "collision - S01E01.file")
        dst_file = os.path.join(self.target_dir, "show_x", "collision - S01E01.file")

        write_file(src_file, "Source content")
        write_file(dst_file, "Destination content")

        move_missing_files(self.source_dir, self.target_dir, dry_run=False, interactive=False)
        self.assertTrue(os.path.exists(src_file), "Source remains.")
        self.assertTrue(os.path.exists(dst_file), "Destination remains; skip due to collision.")

    def test_extended_episode_number(self):
        """
        Test that S01E100 or S01E1000 are recognized as valid episode codes.
        """
        os.makedirs(os.path.join(self.source_dir, "show_ext"), exist_ok=True)
        write_file(os.path.join(self.source_dir, "show_ext", "long - S01E100.file"), "Extended code 100")
        write_file(os.path.join(self.source_dir, "show_ext", "longer - S01E1000.file"), "Extended code 1000")

        move_missing_files(self.source_dir, self.target_dir, dry_run=False, interactive=False)
        # Check that both moved
        self.assertTrue(os.path.exists(os.path.join(self.target_dir, "show_ext", "long - S01E100.file")),
                        "S01E100 file should have moved.")
        self.assertTrue(os.path.exists(os.path.join(self.target_dir, "show_ext", "longer - S01E1000.file")),
                        "S01E1000 file should have moved.")

    @unittest.skip("Performance or large-scale test - unskip if needed.")
    def test_large_number_of_files(self):
        """
        Stress test with a large number of files.
        """
        show_dir = os.path.join(self.source_dir, "show_mass")
        os.makedirs(show_dir, exist_ok=True)
        for i in range(500):
            code = f"S01E{(i % 999) + 1:02d}"
            fname = f"mass_{i} - {code}.file"
            write_file(os.path.join(show_dir, fname), "content")
        move_missing_files(self.source_dir, self.target_dir, dry_run=False, interactive=False)

if __name__ == "__main__":
    unittest.main()
