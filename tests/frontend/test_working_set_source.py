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
        self.assertIn("for(const child of children)this.layoutFamily(child.panelInstanceId)", self.canvas)
        self.assertIn("this.moveBranchTo(child.panelInstanceId,child.x+branchLeft-bound.left", self.canvas)

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
        routing = (ROOT / "frontend/js/canvas/edge-routing.js").read_text(encoding="utf-8")
        self.assertIn('folder-item[data-id="${escapeId(childFolderId)}"]', routing)
        self.assertIn('querySelector(".node-title")', routing)
        self.assertIn("getBoundingClientRect()", routing)
        self.assertIn("this.screenToWorld", edges)
        self.assertIn("canvasRect.left", routing)
        self.assertIn("from = { x: rowRect.right, y: rowRect.top + rowRect.height / 2 }", routing)
        self.assertIn("this.directChildren(parent.panelInstanceId).length===1", edges)
        self.assertIn("const to = trail ? { x: headerRect.left", routing)
        self.assertNotIn("child.x>=parent.x", edges)
        self.assertIn("this.roundedRoute(points)", edges)
        self.assertIn(" Q ${corner.x} ${corner.y}", edges)
        self.assertNotIn(" C ", edges)

    def test_working_set_has_no_continuous_bounds_transition(self):
        css = (ROOT / "frontend/css/canvas.css").read_text(encoding="utf-8")
        working_set = css[css.index(".working-set{"):css.index(".folder-node{")]
        self.assertNotIn("transition:", working_set)

    def test_working_set_label_is_visual_only_and_states_remain_distinct(self):
        css = (ROOT / "frontend/css/canvas.css").read_text(encoding="utf-8")
        self.assertIn('class="working-set-kind">Working Set</span>', self.canvas)
        self.assertIn('class="working-set-context"', self.canvas)
        label = css[css.index(".working-set-label{"):css.index(".folder-node{")]
        self.assertIn("position:absolute", label)
        self.assertIn("pointer-events:none", label)
        self.assertIn("text-overflow:ellipsis", label)
        self.assertIn(".folder-node.selected", css)
        self.assertIn(".folder-item.open", css)
        self.assertIn(".drop-target", css)

    def test_working_set_context_uses_current_materialized_visual_roots(self):
        sets = self.canvas[self.canvas.index("renderSets()") : self.canvas.index("\n  roundedRoute")]
        self.assertIn("const roots=members.filter", sets)
        self.assertIn("this.nodes.get(node.visualParentPanelId)", sets)
        self.assertIn("!parent||parent.workingSetId!==id", sets)
        self.assertIn("roots.length===1", sets)
        self.assertIn("roots[0].name", sets)
        self.assertIn('"1 root"', sets)
        self.assertIn("`${roots.length} roots`", sets)
        self.assertIn('querySelector(".working-set-context").textContent=context', sets)
        self.assertNotIn("set.name", sets)

    def test_working_set_geometry_and_edges_remain_stable(self):
        sets = self.canvas[self.canvas.index("renderSets()") : self.canvas.index("\n  roundedRoute")]
        self.assertIn("Math.min(...members.map(n => n.x)) - 42", sets)
        self.assertIn("Math.min(...members.map(n => n.y)) - 58", sets)
        self.assertIn("Math.max(...members.map(n => n.x + n.renderedWidth)) + 42", sets)
        self.assertIn("Math.max(...members.map(n => n.y + n.renderedHeight)) + 42", sets)

    def test_selected_child_marks_only_its_connector_active(self):
        edges = self.canvas[self.canvas.index("renderEdges()") : self.canvas.index("\n\n  isolate(")]
        self.assertIn('path.classList.toggle("active",child.panelInstanceId===this.selected)', edges)
        self.assertIn("#edges path.active", (ROOT / "frontend/css/canvas.css").read_text(encoding="utf-8"))

    def test_selection_renders_connectors_only_after_final_state(self):
        selection = self.canvas[self.canvas.index("\n  selectFolder(id){") : self.canvas.index("\n  updateFavoriteStates")]
        self.assertIn("selectFolder(id){this.clearSelection(false)", selection)
        self.assertEqual(selection[selection.index("selectFolder(id)") : selection.index(" selectFile")].count("this.renderEdges()"), 1)
        self.assertIn("const connectorChanged=Boolean(this.selected)", selection)
        self.assertIn("if(connectorChanged)this.renderEdges()", selection)
        self.assertIn("clearSelection(renderConnectors=true)", selection)
        self.assertIn("if(renderConnectors)this.renderEdges()", selection)

    def test_reveal_and_close_defer_connectors_to_final_render(self):
        reveal = self.canvas[self.canvas.index("revealPanel(panelId") : self.canvas.index("\n  revealNode")]
        self.assertIn("this.clearSelection(false); this.selected = panelId; this.render()", reveal)
        close = self.canvas[self.canvas.index("\n  removeBranch(panelId") : self.canvas.index("\n\n  dropFilesystem")]
        self.assertIn("removeBranch(panelId,renderConnectors=true)", close)
        self.assertIn("this.removeBranch(panelId,false)", close)
        self.assertIn("this.clearSelection(false); this.render()", close)

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

    def test_compact_parent_is_an_accessible_upstream_tab(self):
        css = (ROOT / "frontend/css/canvas.css").read_text(encoding="utf-8")
        compact_css = css[css.index(".compact-parent{"):css.index(".node-contents{")]
        self.assertIn('createIcon("up")', self.node)
        self.assertNotIn("↗", self.node)
        self.assertNotIn(".compact-parent:after", css)
        self.assertIn("position:absolute", compact_css)
        self.assertIn('handlers.parent(node.panelInstanceId)', self.node)
        self.assertIn('e.stopPropagation()', self.node)
        self.assertIn('`親フォルダーを開く: ${parentName}`', self.node)
        self.assertIn("compact.title=parentName", self.node)
        self.assertNotIn("compact.title=node.compactParent?.path", self.node)

    def test_compact_parent_switches_to_detached_chip_above_search(self):
        css = (ROOT / "frontend/css/canvas.css").read_text(encoding="utf-8")
        search_compact = css[css.index(".folder-node.search-active .compact-parent{"):]
        self.assertIn("bottom:calc(100% + var(--local-search-height,0px) + 10px)", search_compact)
        self.assertIn("border-radius:7px", search_compact)

    def test_mixed_compact_parent_is_loaded_before_family_positioning(self):
        open_parent = self.canvas[self.canvas.index("async openParent"):self.canvas.index("\n  revealPanel")]
        self.assertIn("await this.loadNode(parent)", open_parent)
        self.assertIn("parent.x=child.x-panelWidth(parent)-BRANCH_SPACING.trail", open_parent)
        self.assertIn("this.layoutFamily(parent.panelInstanceId)", open_parent)
        self.assertLess(open_parent.index("await this.loadNode(parent)"), open_parent.index("panelWidth(parent)"))
        self.assertNotIn("panelWidth(folder)", open_parent)

    def test_width_transition_reflows_parent_trail_without_every_render_dancing(self):
        render = self.canvas[self.canvas.index("\n  render()") : self.canvas.index("\n  renderSets()")]
        self.assertIn("previousWidth=node.renderedWidth", render)
        self.assertIn("previousWidth!==node.renderedWidth", render)
        self.assertIn("changedBranches.add(id)", render)
        self.assertIn("this.reflowHierarchy(panelId)", render)
        self.assertIn("if(changedBranches.size)this.updatePositions()", render)

    def test_sibling_width_transition_reflows_its_shelf(self):
        render = self.canvas[self.canvas.index("\n  render()") : self.canvas.index("\n  renderSets()")]
        self.assertIn("this.reflowHierarchy(panelId)", render)
        layout = self.canvas[self.canvas.index("layoutFamily(parentId)") : self.canvas.index("async openSearchResult")]
        self.assertIn("bounds=children.map(child=>this.branchBounds(child.panelInstanceId))", layout)
        self.assertIn("branchLeft+=bound.right-bound.left+BRANCH_SPACING.shelfX", layout)

    def test_width_transition_does_not_reflow_unrelated_working_sets(self):
        render = self.canvas[self.canvas.index("\n  render()") : self.canvas.index("\n  renderSets()")]
        self.assertNotIn("for(const set", render)
        self.assertNotIn("for(const workingSet", render)
        self.assertNotIn("this.workingSets", render)
        self.assertIn("for(const panelId of changedBranches)", render)

    def test_branch_bounds_include_every_materialized_descendant(self):
        bounds = self.canvas[self.canvas.index("branchBounds(panelId)") : self.canvas.index("\n\n  handlers()")]
        self.assertIn("...this.descendants(panelId)", bounds)
        self.assertIn("node.x+(node.renderedWidth||panelWidth(node))", bounds)
        self.assertIn("node.y+(node.renderedHeight||220)", bounds)

    def test_branch_shelf_gap_and_trail_spacing_are_centralized(self):
        layout = (ROOT / "frontend/js/canvas/layout.js").read_text(encoding="utf-8")
        self.assertIn("BRANCH_SPACING = Object.freeze({ trail: 70, shelfX: 70, shelfY: 70 })", layout)
        family = self.canvas[self.canvas.index("layoutFamily(parentId)") : self.canvas.index("async openSearchResult")]
        self.assertIn("bounds=this.branchBounds(child.panelInstanceId)", family)
        self.assertIn("child.x+desiredBranchLeft-bounds.left,parent.y", family)
        self.assertIn("(children.length-1)*BRANCH_SPACING.shelfX", family)

    def test_deep_geometry_change_bubbles_only_to_its_hierarchy_root(self):
        reflow = self.canvas[self.canvas.index("reflowHierarchy(panelId)") : self.canvas.index("async openSearchResult")]
        self.assertIn("while(root.visualParentPanelId", reflow)
        self.assertIn("this.layoutFamily(root.panelInstanceId)", reflow)
        self.assertNotIn("workingSets", reflow)
        self.assertNotIn("for(const root", reflow)

    def test_connectors_render_after_layout_positions_and_set_bounds(self):
        render = self.canvas[self.canvas.index("\n  render()") : self.canvas.index("\n  renderSets()")]
        self.assertLess(render.index("this.reflowHierarchy(panelId)"), render.index("this.updatePositions()"))
        self.assertLess(render.index("this.updatePositions()"), render.index("this.renderSets()"))
        self.assertLess(render.index("this.renderSets()"), render.index("this.renderEdges()"))

    def test_folder_rename_reconciles_visible_descendant_identities(self):
        rename = self.canvas[self.canvas.index("async applyRename"):self.canvas.index("async reconcileVisibleDescendants")]
        self.assertIn("reconcileFolderIdentity(oldId,item,false)", rename)
        self.assertIn("await this.reconcileVisibleDescendants(root)", rename)
        self.assertIn("folderId:item.id", rename)


if __name__ == "__main__":
    unittest.main()
