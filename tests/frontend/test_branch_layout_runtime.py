import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[2]


class BranchLayoutRuntimeTest(unittest.TestCase):
    def run_layout(self, nodes, root_id="parent"):
        script = f"""
import {{ FolderCanvas }} from "./frontend/js/canvas/canvas.js";
const canvas=Object.create(FolderCanvas.prototype);
canvas.nodes=new Map({json.dumps(nodes)}.map(node=>[node.panelInstanceId,node]));
canvas.layoutFamily({json.dumps(root_id)});
const bounds=Object.fromEntries([...canvas.nodes.keys()].map(id=>[id,canvas.branchBounds(id)]));
process.stdout.write(JSON.stringify({{nodes:Object.fromEntries(canvas.nodes),bounds}}));
"""
        result = subprocess.run(
            ["node", "--input-type=module", "--eval", script],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        return json.loads(result.stdout)

    def test_trail_places_complete_child_shelf_right_of_tall_parent(self):
        result = self.run_layout([
            {"panelInstanceId": "parent", "visualParentPanelId": None, "x": 0, "y": 0, "renderedWidth": 330, "renderedHeight": 520},
            {"panelInstanceId": "child", "visualParentPanelId": "parent", "x": 400, "y": 40, "renderedWidth": 330, "renderedHeight": 220},
            {"panelInstanceId": "grand-a", "visualParentPanelId": "child", "x": 300, "y": 350, "renderedWidth": 330, "renderedHeight": 220},
            {"panelInstanceId": "grand-b", "visualParentPanelId": "child", "x": 700, "y": 350, "renderedWidth": 330, "renderedHeight": 220},
        ])

        self.assertEqual(400, result["bounds"]["child"]["left"])
        self.assertEqual(0, result["nodes"]["child"]["y"])
        self.assertGreaterEqual(result["bounds"]["child"]["left"], 330 + 70)

    def test_nested_trail_shelves_remain_right_of_each_ancestor(self):
        result = self.run_layout([
            {"panelInstanceId": "parent", "visualParentPanelId": None, "x": 0, "y": 0, "renderedWidth": 430, "renderedHeight": 300},
            {"panelInstanceId": "child", "visualParentPanelId": "parent", "x": 500, "y": 0, "renderedWidth": 330, "renderedHeight": 240},
            {"panelInstanceId": "grand", "visualParentPanelId": "child", "x": 900, "y": 0, "renderedWidth": 330, "renderedHeight": 220},
            {"panelInstanceId": "great-a", "visualParentPanelId": "grand", "x": 800, "y": 300, "renderedWidth": 330, "renderedHeight": 180},
            {"panelInstanceId": "great-b", "visualParentPanelId": "grand", "x": 1200, "y": 300, "renderedWidth": 330, "renderedHeight": 180},
        ])

        child = result["nodes"]["child"]
        self.assertGreaterEqual(result["bounds"]["child"]["left"], 430 + 70)
        self.assertGreaterEqual(
            result["bounds"]["grand"]["left"],
            child["x"] + child["renderedWidth"] + 70,
        )


if __name__ == "__main__":
    unittest.main()
