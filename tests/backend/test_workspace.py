import json
import tempfile
import unittest
from pathlib import Path

from backend.workspace.store import WorkspaceStore


class WorkspaceStoreTest(unittest.TestCase):
    def test_missing_state_has_v2_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            state = WorkspaceStore(Path(directory) / "missing.json").load()
        self.assertEqual(2, state["version"])
        self.assertEqual({}, state["workingSets"])

    def test_v1_parent_is_migrated_to_visual_parent(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workspace.json"
            path.write_text(json.dumps({"version": 1, "nodes": {"folder-a": {"path": "/a", "parentId": "folder-p"}}}))
            state = WorkspaceStore(path).load()
        node = state["nodes"]["folder-a"]
        self.assertEqual("folder-a", node["folderId"])
        self.assertEqual("folder-a", node["panelInstanceId"])
        self.assertEqual("folder-p", node["visualParentPanelId"])
        self.assertIsNone(node["fsParentFolderId"])
        self.assertIn(node["workingSetId"], state["workingSets"])

    def test_v2_instances_of_same_folder_in_different_sets_survive(self):
        state = {"version": 2, "workingSets": {"a": {}, "b": {}}, "nodes": {
            "panel-a": {"panelInstanceId": "panel-a", "folderId": "folder", "workingSetId": "a"},
            "panel-b": {"panelInstanceId": "panel-b", "folderId": "folder", "workingSetId": "b"},
        }}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workspace.json"; path.write_text(json.dumps(state))
            restored = WorkspaceStore(path).load()
        self.assertEqual({"panel-a", "panel-b"}, set(restored["nodes"]))


if __name__ == "__main__":
    unittest.main()
