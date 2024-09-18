"""Source file management."""

from os import path
from io import StringIO
from typing import NamedTuple, Dict, List, Optional, Tuple, TextIO
from itertools import accumulate

# 1-indexed (line_number, column_number) tuple representing a location
# in a source file:
LineCol = Tuple[int, int]
# A range in a source file that includes the character that the first
# `LineCol` points to, up to the character that the second `LineCol`
# points to.
LineColRange = Tuple[LineCol, LineCol]

class PackedSourceRange(NamedTuple):
    """
    A `FileEntry` put together with a `LineColRange` -- all information
    needed to find a range in source file. Note that this (unlike most
    other named tuples) might be unpacked (using Python's * operator).
    """
    file: "FileEntry"
    range: LineColRange

class FileEntry:
    """A file."""

    def __init__(self, text: str, display_name: str,
                 file_name: Optional[str] = None):
        self.display_name = display_name
        self.text = text
        self.file_name = file_name
        self.line_offsets: Optional[List[int]] = None

    @classmethod
    def real_file(cls, filename: str, display_name: str):
        """
        Construct a `FileEntry` from a real file in the OS's file
        system.
        """
        with open(filename, 'r', encoding='utf-8') as file:
            text = file.read()
        return cls(text, display_name, filename)

    def open(self) -> TextIO:
        return StringIO(self.text)

    def get_line_offsets(self) -> List[int]:
        """Make line offsets mapping."""
        # len(line_offsets) == text.count('\n') + 2
        # Reason: one '\n' creates 2 lines, 2 creates 3, etc. so +1
        # For the convenience of `get_lines`, we need a "fake" line, so
        # +1 again.
        if self.line_offsets is None:
            lines = self.text.splitlines(keepends=True)
            # No need to consider \r\n since the `text` newlines are
            # already normalized.
            lens_acc = accumulate(map(len, lines))
            # Add a zero for the first line.
            self.line_offsets = offsets = list(lens_acc)
            offsets.insert(0, 0)
            # If the original file ends with a '\n', the last empty
            # line would be stripped by `str.splitlines`, so we add
            # it back here.
            if self.text.endswith('\n'):
                offsets.append(len(self.text) + 1)
            # If not, the fake last line's offset must be +1 since we
            # need to assume there is a '\n' after last real line.
            else:
                offsets[-1] += 1
        return self.line_offsets

    def get_lines(self, l1: int, l2: int) -> List[str]:
        """
        Get line `l1` to line `l2` of `file`. Both `l1` and `l2` are
        1-indexed.
        """
        line_offsets = self.get_line_offsets()
        p1 = line_offsets[l1 - 1]  # 1-indexed -> 0-indexed
        p2 = line_offsets[l2] - 1  # exclude trailing '\n'
        assert p1 <= p2  # equal for an empty line
        source = self.text[p1:p2]
        if not source:
            # Make sure we return something even if this line is empty
            return ['']
        return source.splitlines()

class Reader:
    """A source file manager."""

    def __init__(self):
        self.real_entries: Dict[str, FileEntry] = {}
        self.fake_entries: List[FileEntry] = []

    def get_real_file(self, filename: str) -> FileEntry:
        """
        Get a `FileEntry` by its (possibly unnormalized) path on the
        real file system. The passed in `filename` will become the
        entry's display name.
        """
        # Check cache
        norm_filename = path.realpath(filename)
        entry = self.real_entries.get(norm_filename)
        if entry is None:
            # Load the file
            entry = FileEntry.real_file(norm_filename, filename)
            self.real_entries[norm_filename] = entry
        return entry

    def add_fake_file(self, text: str,
                      display_name: Optional[str] = None) -> FileEntry:
        """Add a fake file."""
        file_id = len(self.fake_entries)
        if display_name is None:
            display_name = f"<fakefile #{file_id}>"
        entry = FileEntry(text, display_name)
        self.fake_entries.append(entry)
        return entry

    def delete_real_file_cache(self, filename: str) -> None:
        """
        Delete cache of `filename` so that it can be reloaded later. If
        the file does not exist in cache, this does nothing.
        """
        norm_filename = path.realpath(filename)
        self.real_entries.pop(norm_filename, None)
