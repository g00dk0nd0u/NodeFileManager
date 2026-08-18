import unittest
from pathlib import Path


ROOT = Path(__file__).parents[2]


class WorkingSetSourceInvariantTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.canvas = (ROOT / "frontend/js/canvas/canvas.js").read_text(encoding="utf-8")
        cls.node = (ROOT / "frontend/js/canvas/node.js").read_text(encoding="utf-8")

    def test_panel_drag_freezes_source_bounds_and_has_distinct_release_intents(self):
        self.assertIn("frozenRect:setElement.getBoundingClientRect()", self.canvas)
        self.assertIn('type:"filesystem"', self.canvas)
        self.assertIn('type:"isolate"', self.canvas)
        self.assertIn('type:"reattach"', self.canvas)

    def test_isolate_sets_compact_real_parent(self):
        self.assertIn("root.compactParent={id:parent.folderId", self.canvas)
        self.assertIn("root.fsParentFolderId=parent.folderId", self.canvas)

    def test_reattach_matches_direct_parent_folder_identity(self):
        self.assertIn("n.folderId===root.fsParentFolderId", self.canvas)
        self.assertNotIn("parent.name===root", self.canvas)

    def test_second_sibling_reflows_entire_local_family(self):
        self.assertIn("if(children.length===1)", self.canvas)
        self.assertIn("children.forEach((child,index)=>this.moveBranchTo", self.canvas)

    def test_panel_header_does_not_mix_native_and_pointer_drag(self):
        self.assertNotIn('class="node-title" draggable="true"', self.node)
        self.assertNotIn("prompt(\"Panel action", self.node)

    def test_isolate_and_reattach_relationships_are_persisted(self):
        serialization = self.canvas[self.canvas.index("serialize(){"):]
        self.assertIn("visualParentPanelId", self.canvas)
        self.assertIn("workingSetId", serialization)
        self.assertNotIn("fsParentFolderId,...saved", serialization)


if __name__ == "__main__":
    unittest.main()
