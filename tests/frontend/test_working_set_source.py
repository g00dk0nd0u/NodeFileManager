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
        self.assertIn("children.forEach((child,index)=>{this.moveBranchTo", self.canvas)

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

    def test_panel_width_model_and_measured_bounds_are_centralized(self):
        layout = (ROOT / "frontend/js/canvas/layout.js").read_text(encoding="utf-8")
        self.assertIn("PANEL_WIDTH = Object.freeze({ single: 330, mixed: 430 })", layout)
        self.assertIn("node.renderedWidth=element.offsetWidth", self.canvas)
        self.assertIn("n.x + n.renderedWidth", self.canvas)
        self.assertLess(self.canvas.index("node.renderedWidth=element.offsetWidth"), self.canvas.index("this.renderSets();this.renderEdges()"))

    def test_panel_drag_only_moves_a_whole_working_set(self):
        drag = self.canvas[self.canvas.index("\n  continueDrag(event)"):self.canvas.index("\n  endDrag(event)")]
        self.assertIn('if(s.type==="set")for', drag)
        self.assertNotIn('if(s.type==="panel")for', drag)

    def test_connector_uses_row_header_and_viewport_conversion(self):
        edges = self.canvas[self.canvas.index("renderEdges()") : self.canvas.index("\n\n  isolate(")]
        self.assertIn('folder-item[data-id="${CSS.escape(child.folderId)}"]', edges)
        self.assertIn('querySelector(".node-title")', edges)
        self.assertIn("getBoundingClientRect()", edges)
        self.assertIn("this.screenToWorld", edges)
        self.assertIn("canvasRect.left", edges)
        self.assertIn(" L ${exit.x}", edges)
        self.assertIn("directChildren.length===1", edges)
        self.assertIn("to=trail?{x:headerRect.left,y:headerRect.top+headerRect.height/2}:{x:headerRect.left+headerRect.width/2,y:headerRect.top}", edges)
        self.assertNotIn("child.x>=parent.x", edges)
        self.assertIn(" C ${trail?", edges)

    def test_working_set_has_no_continuous_bounds_transition(self):
        css = (ROOT / "frontend/css/canvas.css").read_text(encoding="utf-8")
        working_set = css[css.index(".working-set{"):css.index(".folder-node{")]
        self.assertNotIn("transition:", working_set)

    def test_local_search_is_absolutely_anchored_to_its_panel(self):
        app = (ROOT / "frontend/js/app.js").read_text(encoding="utf-8")
        local = app[app.index("canvas.actions.localSearch"):app.index("function workspaceSearch")]
        self.assertIn('stack.className="local-search-stack"', local)
        self.assertIn("panelElement.append(stack)", local)
        self.assertNotIn("canvas.world.append(stack)", local)
        self.assertNotIn("stack.style.transform", local)
        self.assertNotIn('querySelector(".node-title").append', local)

    def test_compact_parent_uses_actual_local_search_height(self):
        app = (ROOT / "frontend/js/app.js").read_text(encoding="utf-8")
        css = (ROOT / "frontend/css/canvas.css").read_text(encoding="utf-8")
        self.assertIn("stack.offsetHeight", app)
        self.assertIn('setProperty("--local-search-height"', app)
        self.assertIn('removeProperty("--local-search-height")', app)
        self.assertIn("var(--local-search-height,0px)", css)
        self.assertNotIn("205px", css)

    def test_folder_rename_reconciles_visible_descendant_identities(self):
        rename = self.canvas[self.canvas.index("async applyRename"):self.canvas.index("async reconcileVisibleDescendants")]
        self.assertIn("reconcileFolderIdentity(oldId,item,false)", rename)
        self.assertIn("await this.reconcileVisibleDescendants(root)", rename)
        self.assertIn("folderId:item.id", rename)


if __name__ == "__main__":
    unittest.main()
