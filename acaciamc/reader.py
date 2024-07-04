"""Source file management."""

from os import path
from io import StringIO
from typing import NamedTuple, Dict, List, Optional, Tuple, TextIO
from itertools import accumulate

class SourceLocation(NamedTuple):
    """
    A location in a source file.
    Line and col numbers are 1-indexed.
    """

    file: "FileEntry"
    pos: Tuple[int, int]  # line, col

    def to_str(self) -> str:
        line, col = self.pos
        return f"{self.file.display_name}:{line}:{col}"

    def to_range(self, x: int) -> "SourceRange":
        """
        Get a `SourceRange` starting at `self` with `x` length.
        Note that this does not take care of line breaks.
        """
        ln, col = self.pos
        return SourceRange(self, SourceLocation(self.file, (ln, col + x)))

class SourceRange(NamedTuple):
    """
    A range in a source file that begins before the character `begin`
    points to and ends before the character `end` points to.
    """

    begin: SourceLocation
    end: SourceLocation
    # assert begin.file is end.file

    @property
    def file(self) -> "FileEntry":
        return self.begin.file

    def to_str(self) -> str:
        if self.begin == self.end:
            return self.begin.to_str()
        ln1, col1 = self.begin.pos
        ln2, col2 = self.end.pos
        filename = self.file.display_name
        if ln1 == ln2:
            return f'{filename}:{ln1}:{col1}-{col2}'
        return f'{filename}:{ln1}:{col1}-{ln2}:{col2}'

    def get_lines(self) -> List[str]:
        """Get the lines where `self` is in source."""
        file = self.file
        line_offsets = file.get_line_offsets()
        ln1, _ = self.begin.pos
        ln2, _ = self.end.pos
        p1 = line_offsets[ln1 - 1]  # 1-indexed -> 0-indexed
        p2 = line_offsets[ln2] - 1  # exclude trailing '\n'
        assert p1 <= p2  # equal for an empty line
        source = file.text[p1:p2]
        if not source:
            # Make sure we return *something* even if this line is empty
            return ['']
        return source.splitlines()

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
        # For convenience of `SourceRange.get_lines`, we need a "fake"
        # line, so +1 again.
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

    def get_location(self, pos: Tuple[int, int]) -> SourceLocation:
        """
        Convert a (line number, column number) tuple to a SourceLocation
        in this file.
        """
        return SourceLocation(self, pos)

    def get_range(self, begin: Tuple[int, int], end: Tuple[int, int]) \
            -> SourceRange:
        """
        Convert two (line number, column number) pairs into a
        SourceRange in this file.
        """
        loc1 = self.get_location(begin)
        loc2 = self.get_location(end)
        return SourceRange(loc1, loc2)

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
