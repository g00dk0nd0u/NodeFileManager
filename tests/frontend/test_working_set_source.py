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

    def test_moved_visible_branch_reconciles_path_derived_identities(self):
        app = (ROOT / "frontend/js/app.js").read_text(encoding="utf-8")
        self.assertIn("reconcileMovedFolder(id,result.item)", app)
        self.assertIn("async reconcileMovedFolder(oldFolderId,movedItem)", self.canvas)
        self.assertIn("folderId:item.id", self.canvas)
        self.assertIn("await this.reconcileVisibleDescendants(root)", self.canvas)
        self.assertIn("folderId:current.id", self.canvas)

    def test_normal_parent_connection_clears_compact_parent(self):
        open_parent = self.canvas[self.canvas.index("async openParent"):self.canvas.index("\n  revealPanel")]
        reattach = self.canvas[self.canvas.index("\n  reattach(panelId"):self.canvas.index("\n  cleanupSets()")]
        self.assertIn("delete child.compactParent", open_parent)
        self.assertIn("delete root.compactParent", reattach)

    def test_refresh_prunes_external_deleted_materialized_branch_first(self):
        refresh = self.canvas[self.canvas.index("async refresh(folderId"):self.canvas.index("async applyRename")]
        self.assertIn("available=new Set(contents.folders.map", refresh)
        self.assertIn("this.removeBranch(child.panelInstanceId)", refresh)
        self.assertLess(refresh.index("this.removeBranch(child.panelInstanceId)"), refresh.index("await this.refreshBranch(child)"))
        self.assertIn("if(node.visualParentPanelId){this.removeBranch", refresh)

    def test_folder_rename_reconciles_visible_descendant_identities(self):
        rename = self.canvas[self.canvas.index("async applyRename"):self.canvas.index("async reconcileVisibleDescendants")]
        self.assertIn("reconcileFolderIdentity(oldId,item,false)", rename)
        self.assertIn("await this.reconcileVisibleDescendants(root)", rename)
        self.assertIn("folderId:item.id", rename)


if __name__ == "__main__":
    unittest.main()
