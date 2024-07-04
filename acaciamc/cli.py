"""Command line interface of Acacia."""

from acaciamc.diagnostic import DiagnosticsManager
from acaciamc.reader import Reader
from acaciamc.postast import ASTForest
from acaciamc.ast import ASTVisualizer

def main():
    reader = Reader()
    diag = DiagnosticsManager(reader)
    entry = reader.get_real_file("test/temp.aca")
    forest = ASTForest(reader, diag, entry, mc_version=(1, 20, 10))
    visualizer = ASTVisualizer()
    if forest.succeeded:
        for module, node in forest.modules.items():
            print(f"======== Module {module!r} ========")
            print(visualizer.convert(node.ast))
