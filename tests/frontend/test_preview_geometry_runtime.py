import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[2]


class PreviewGeometryRuntimeTest(unittest.TestCase):
    @staticmethod
    def geometry(node, bounds):
        script = f'''
import {{ previewGeometry }} from "./frontend/js/canvas/layout.js";
process.stdout.write(JSON.stringify(previewGeometry({json.dumps(node)}, {json.dumps(bounds)})));
'''
        result = subprocess.run(
            ["node", "--input-type=module", "--eval", script],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        return json.loads(result.stdout)

    def test_preview_has_usable_height_and_temporarily_expands_short_working_set(self):
        geometry = self.geometry({"y": 100}, {"top": 42, "bottom": 202})
        self.assertEqual(32, geometry["top"])
        self.assertEqual(280, geometry["height"])
        self.assertEqual(454, geometry["workingSetBottom"])

    def test_preview_begins_below_header_even_for_very_short_panel(self):
        geometry = self.geometry(
            {"y": 100, "renderedHeight": 40}, {"top": 42, "bottom": 182}
        )
        self.assertEqual(32, geometry["top"])
        self.assertGreaterEqual(geometry["height"], 240)
        self.assertGreater(geometry["workingSetBottom"], 182)

    def test_compact_parent_area_is_not_used_for_preview(self):
        geometry = self.geometry(
            {"y": 100, "renderedHeight": 60, "compactParent": {"id": "parent"}},
            {"top": 42, "bottom": 202},
        )
        self.assertEqual(32, geometry["top"])
        self.assertGreaterEqual(100 + geometry["top"], 132)

    def test_existing_large_working_set_does_not_expand(self):
        geometry = self.geometry({"y": 100}, {"top": 42, "bottom": 500})
        self.assertEqual(500, geometry["workingSetBottom"])

    def test_preview_geometry_does_not_mutate_panel_layout(self):
        node = {"y": 100, "x": 80, "renderedHeight": 220, "renderedWidth": 330}
        original = node.copy()
        self.geometry(node, {"top": 42, "bottom": 362})
        self.assertEqual(original, node)

    def test_open_and_close_preserve_layout_and_branch_bounds(self):
        script = r"""
import { FolderCanvas } from "./frontend/js/canvas/canvas.js";
const canvas=Object.create(FolderCanvas.prototype);
const nodes=[
  {panelInstanceId:"root",visualParentPanelId:null,workingSetId:"set",x:10,y:20,renderedWidth:330,renderedHeight:220},
  {panelInstanceId:"child",visualParentPanelId:"root",workingSetId:"set",x:410,y:20,renderedWidth:330,renderedHeight:180}
];
canvas.nodes=new Map(nodes.map(node=>[node.panelInstanceId,node]));
canvas.updatePreview=()=>{};
canvas.changed=()=>{};
const before={nodes:structuredClone(nodes),bounds:canvas.branchBounds("root")};
canvas.preview("root",{id:"pdf",name:"manual.pdf",extension:".pdf"});
const opened={nodes:structuredClone(nodes),bounds:canvas.branchBounds("root")};
canvas.closePreview("root");
const closed={nodes:structuredClone(nodes),bounds:canvas.branchBounds("root")};
process.stdout.write(JSON.stringify({before,opened,closed}));
"""
        result = subprocess.run(
            ["node", "--input-type=module", "--eval", script],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        states = json.loads(result.stdout)
        for state in (states["opened"], states["closed"]):
            self.assertEqual(states["before"]["bounds"], state["bounds"])
            for before, after in zip(states["before"]["nodes"], state["nodes"]):
                for field in ("x", "y", "renderedWidth", "renderedHeight"):
                    self.assertEqual(before[field], after[field])

    def test_close_restores_persistent_working_set_frame(self):
        script = r"""
import { FolderCanvas } from "./frontend/js/canvas/canvas.js";
const canvas=Object.create(FolderCanvas.prototype);
const node={panelInstanceId:"root",visualParentPanelId:null,workingSetId:"set",name:"Root",x:100,y:100,renderedWidth:330,renderedHeight:60,preview:{id:"pdf"}};
canvas.nodes=new Map([["root",node]]);
canvas.workingSets=new Map([["set",{}]]);
const style={};
const setElement={style,querySelector:()=>({textContent:""})};
canvas.setElements=new Map([["set",setElement]]);
const preview={style:{}};
canvas.elements=new Map([["root",{querySelector:()=>preview}]]);
canvas.renderSets();
const openHeight=style.height;
delete node.preview;
canvas.renderSets();
process.stdout.write(JSON.stringify({openHeight,closedHeight:style.height,previewTop:preview.style.top,previewHeight:preview.style.height}));
"""
        result = subprocess.run(
            ["node", "--input-type=module", "--eval", script],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        geometry = json.loads(result.stdout)
        self.assertEqual("412px", geometry["openHeight"])
        self.assertEqual("160px", geometry["closedHeight"])
        self.assertEqual("32px", geometry["previewTop"])
        self.assertEqual("280px", geometry["previewHeight"])

    def test_preview_integration_keeps_hierarchy_and_working_set_geometry_stable(self):
        canvas = (ROOT / "frontend/js/canvas/canvas.js").read_text(encoding="utf-8")
        preview = canvas[canvas.index("  preview(panelId"):canvas.index("\n  selectFolder(")]
        self.assertNotIn("reflowHierarchy", preview)
        self.assertNotIn("renderedHeight=", preview)
        self.assertNotIn("renderEdges", preview)
        self.assertNotIn("previewResized", canvas)
        sets = canvas[canvas.index("  renderSets()") : canvas.index("\n  roundedRoute")]
        self.assertIn("n.y + n.renderedHeight", sets)
        self.assertIn("persistentMaxY", sets)
        self.assertIn("geometry.workingSetBottom", sets)

    def test_pdf_and_image_share_contained_preview_container(self):
        node = (ROOT / "frontend/js/canvas/node.js").read_text(encoding="utf-8")
        css = (ROOT / "frontend/css/canvas.css").read_text(encoding="utf-8")
        self.assertIn('preview.append(image)', node)
        self.assertIn('preview.append(frame)', node)
        self.assertIn(".node-preview img,.node-preview iframe", css)
        self.assertIn("object-fit:contain", css)
        self.assertIn("max-width:100%", css)
        self.assertIn("overflow:hidden", css[css.index(".node-preview{"):css.index(".node-preview[hidden]")])

    def test_preview_is_temporary_and_connector_routing_is_unchanged(self):
        canvas = (ROOT / "frontend/js/canvas/canvas.js").read_text(encoding="utf-8")
        serialization = canvas[canvas.index("serialize(){"):]
        self.assertIn("preview,renderedWidth,renderedHeight", serialization)
        edges = canvas[canvas.index("renderEdges()") : canvas.index("\n\n  isolate(")]
        self.assertIn("measureConnectorAnchors", edges)
        self.assertIn("trailRoute", edges)
        self.assertIn("shelfRoute", edges)


if __name__ == "__main__":
    unittest.main()
