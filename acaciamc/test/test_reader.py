"""Unit tests for reader.py"""

import os

from acaciamc.test import TestSuite

test_dir = os.path.dirname(__file__)
dummy_file = os.path.join(test_dir, "data", "dummy.txt")

DUMMY_CONTENT = 'This\nis\na dummy\nfile for\ntest/test_reader.py\n'
DUMMY_LINE_OFFSETS = [0, 5, 8, 16, 25, 45, 46]
RANGES = (
    ((1, 3), (1, 3), ["This"]),
    ((3, 2), (3, 6), ["a dummy"]),
    ((2, 1), (5, 1), ["is", "a dummy", "file for", "test/test_reader.py"]),
    ((6, 1), (6, 1), [""]),
)
LOCATION_AND_OFFSETS = (
    ((3, 2), 4, (3, 6)),
    ((2, 1), 2, (2, 3)),
    ((6, 1), 0, (6, 1)),
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

    def test_source_range(self):
        for pos1, pos2, contents in RANGES:
            rng = self.file_entry.get_range(pos1, pos2)
            self.assert_true(rng.get_lines() == contents,
                             "wrong get_lines() result")

    def test_source_location(self):
        for pos1, offset, pos2 in LOCATION_AND_OFFSETS:
            loc1 = self.file_entry.get_location(pos1)
            loc2 = loc1.to_range(offset).end
            self.assert_true(loc2.pos == pos2,
                             "wrong to_range() result")
