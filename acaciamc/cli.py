"""Command line interface of Acacia."""

from acaciamc.diagnostic import DiagnosticsManager
from acaciamc.reader import Reader
from acaciamc.tokenizer import Tokenizer
from acaciamc.parser import Parser
from acaciamc.ast import ASTVisualizer

def main():
    reader = Reader()
    diag = DiagnosticsManager(reader)
    entry = reader.get_real_file("test/temp.aca")
    with entry.open() as file:
        tokenizer = Tokenizer(file, entry, diag, (1, 19, 70))
        parser = Parser(tokenizer)
        node = None
        with diag.capture_errors():
            node = parser.module()
        if node is not None:
            print(ASTVisualizer().convert(node))
