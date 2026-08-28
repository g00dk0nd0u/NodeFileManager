import unittest
from pathlib import Path


ROOT = Path(__file__).parents[2]


class FolderPanelMoveFeedbackTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.canvas = (ROOT / "frontend/js/canvas/canvas.js").read_text(encoding="utf-8")
        cls.node = (ROOT / "frontend/js/canvas/node.js").read_text(encoding="utf-8")
        cls.css = (ROOT / "frontend/css/canvas.css").read_text(encoding="utf-8")
        cls.intent = cls.canvas[cls.canvas.index("dragIntent(session"):cls.canvas.index("\n  continueDrag(event)")]

    def test_intent_priority_remains_filesystem_then_reattach_then_isolate(self):
        filesystem = self.intent.index('if(target)return{type:"filesystem"')
        reattach = self.intent.index('return{type:"reattach"')
        isolate = self.intent.index('return{type:"isolate"')
        self.assertLess(filesystem, reattach)
        self.assertLess(reattach, isolate)

    def test_filesystem_intent_carries_materialized_safe_destination_metadata(self):
        self.assertIn("destinationName:target.dataset.destinationName", self.intent)
        self.assertIn("destinationTarget:target.dataset.destinationTarget", self.intent)
        self.assertIn("targetElement:target", self.intent)
        self.assertIn('folder.id,folder.name,"child-row"', self.node)
        self.assertIn('node.folderId,node.name,"panel-region"', self.node)
        self.assertNotIn("destinationPath", self.canvas + self.node)

    def test_panel_region_and_child_row_use_distinct_local_blue_geometry(self):
        self.assertIn("filesystem-move-target--panel-region", self.css)
        self.assertIn("folder-item.filesystem-move-target--child-row", self.css)
        self.assertNotIn('[data-drag-intent="filesystem"] .folder-region', self.css)
        self.assertIn("MOVE \\u2192 ${intent.destinationName}", self.canvas)

    def test_feedback_is_replaced_when_intent_changes_or_target_is_left(self):
        continuation = self.canvas[self.canvas.index("continueDrag(event)"):self.canvas.index("\n  endDrag(event)")]
        renderer = self.canvas[self.canvas.index("renderFilesystemFeedback(intent)"):self.canvas.index("\n  cancelDrag(event)")]
        self.assertIn("this.renderFilesystemFeedback(s.intent)", continuation)
        self.assertIn("current.element===intent.targetElement", renderer)
        self.assertIn("current.destinationId===intent.destinationId", renderer)
        self.assertIn("current.destinationTarget===intent.destinationTarget", renderer)
        self.assertIn("current.destinationName===intent.destinationName", renderer)
        self.assertLess(renderer.index("return;this.clearFilesystemFeedback()"), renderer.index('document.createElement("span")'))
        self.assertIn('intent?.type!=="filesystem"', renderer)
        self.assertIn('classList.remove("filesystem-move-target"', renderer)

    def test_cancel_escape_pointercancel_and_blur_share_cleanup(self):
        self.assertIn('window.addEventListener("pointercancel", (event) => this.cancelDrag(event))', self.canvas)
        self.assertIn('window.addEventListener("blur", () => this.finishDrag(false))', self.canvas)
        self.assertIn('if (event.key === "Escape") this.escape(event)', self.canvas)
        self.assertIn("cancelDrag(event){if(this.dragSession?.pointerId===event.pointerId)this.finishDrag(false)", self.canvas)
        finish = self.canvas[self.canvas.index("finishDrag(save)"):self.canvas.index("\n  updatePositions")]
        self.assertIn("this.clearFilesystemFeedback()", finish)
        self.assertIn("delete this.canvas.dataset.dragIntent", finish)

    def test_reattach_and_isolate_visual_semantics_are_unchanged(self):
        self.assertIn('#canvas[data-drag-intent="isolate"] .folder-node.selected{outline-color:#d99a4d;box-shadow:0 0 0 5px #d99a4d20}', self.css)
        self.assertIn('#canvas[data-drag-intent="reattach"] .working-set{border-color:#69b88d;background:#31513f66}', self.css)
