"""Unit tests for reader.py"""

import os

from acaciamc.test import TestSuite

test_dir = os.path.dirname(__file__)
dummy_file = os.path.join(test_dir, "data", "dummy.txt")

DUMMY_CONTENT = 'This\nis\na dummy\nfile for\ntest/test_reader.py\n'
DUMMY_LINE_OFFSETS = [0, 5, 8, 16, 25, 45, 46]
SOURCE_LINES = (
    (1, 1, ["This"]),
    (3, 3, ["a dummy"]),
    (2, 5, ["is", "a dummy", "file for", "test/test_reader.py"]),
    (6, 6, [""]),
)

class ReaderTests(TestSuite):
    name = "reader"

    def setup(self):
        self.file_entry = self.owner.reader.get_real_file(dummy_file)

    def test_real_file(self):
        with self.file_entry.open() as file:
            self.assert_true(file.read() == DUMMY_CONTENT,
                             "wrong file content")
        fe2 = self.owner.reader.get_real_file(dummy_file)
        self.assert_true(self.file_entry is fe2, "cache did not hit")

    def test_fake_file(self):
        fe = self.owner.reader.add_fake_file(DUMMY_CONTENT)
        with fe.open() as file:
            self.assert_true(file.read() == DUMMY_CONTENT,
                             "wrong file content")

    def test_line_offsets(self):
        line_offsets = self.file_entry.get_line_offsets()
        self.assert_true(line_offsets == DUMMY_LINE_OFFSETS,
                         "wrong line offsets")
        self.assert_true(line_offsets is self.file_entry.get_line_offsets(),
                         "cache did not hit")

    def test_get_lines(self):
        for l1, l2, contents in SOURCE_LINES:
            self.assert_true(self.file_entry.get_lines(l1, l2) == contents,
                             "wrong get_lines() result")
