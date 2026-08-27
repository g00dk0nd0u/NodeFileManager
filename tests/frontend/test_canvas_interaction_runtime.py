import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[2]


def run_node(script):
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


class CanvasInteractionRuntimeTest(unittest.TestCase):
    def test_filesystem_feedback_reuses_identity_and_cleans_up(self):
        result = run_node(r'''
import { FolderCanvas } from "./frontend/js/canvas/canvas.js";
let creates=0, removes=0;
globalThis.document={createElement(){creates++;return{remove(){removes++;}}}};
const classes={add(){},remove(){}};
const first={classList:classes,append(label){this.label=label;}}, second={classList:classes,append(label){this.label=label;}};
const canvas=Object.create(FolderCanvas.prototype);
const intent=(element,id,target,name)=>({type:"filesystem",targetElement:element,destinationId:id,destinationTarget:target,destinationName:name});
canvas.renderFilesystemFeedback(intent(first,"folder-a","panel-region","A"));
const original=canvas.filesystemFeedback.label;
canvas.renderFilesystemFeedback(intent(first,"folder-a","panel-region","A"));
const reused=canvas.filesystemFeedback.label===original;
canvas.renderFilesystemFeedback(intent(first,"folder-b","child-row","B"));
const replacedSameElement=canvas.filesystemFeedback.label!==original;
canvas.renderFilesystemFeedback(intent(second,"folder-c","child-row","C"));
canvas.renderFilesystemFeedback({type:"reattach"});
process.stdout.write(JSON.stringify({creates,removes,reused,replacedSameElement,cleared:canvas.filesystemFeedback===null}));
''')
        self.assertEqual(3, result["creates"])
        self.assertEqual(3, result["removes"])
        self.assertTrue(result["reused"])
        self.assertTrue(result["replacedSameElement"])
        self.assertTrue(result["cleared"])

    def test_compact_parent_preserves_child_and_syncs_positions_before_edges(self):
        result = run_node(r'''
import { FolderCanvas } from "./frontend/js/canvas/canvas.js";
const child={panelInstanceId:"child-panel",folderId:"child-folder",workingSetId:"set",x:500,y:100,renderedWidth:330,renderedHeight:200,visualParentPanelId:null,compactParent:{id:"parent-folder",name:"Parent"}};
const canvas=Object.create(FolderCanvas.prototype);canvas.nodes=new Map([[child.panelInstanceId,child]]);canvas.elements=new Map();
canvas.panelForFolder=FolderCanvas.prototype.panelForFolder;canvas.loadNode=async parent=>{parent.folders=[{id:"child-folder"}];parent.files=[];parent.childrenLoaded=true;};
canvas.render=function(){this.updatePositions();this.renderEdges();};let order=[];canvas.updatePositions=()=>order.push("positions");canvas.renderEdges=()=>order.push("edges");canvas.changed=()=>{};
await canvas.openParent(child.panelInstanceId);
process.stdout.write(JSON.stringify({sameChild:canvas.nodes.get("child-panel")===child,count:canvas.nodes.size,parentFolder:canvas.nodes.get(child.visualParentPanelId).folderId,order,children:canvas.directChildren(child.visualParentPanelId).map(n=>n.panelInstanceId)}));
''')
        self.assertTrue(result["sameChild"])
        self.assertEqual(2, result["count"])
        self.assertEqual("parent-folder", result["parentFolder"])
        self.assertEqual(["positions", "edges"], result["order"])
        self.assertEqual(["child-panel"], result["children"])

    def test_shelf_lanes_are_distinct_deterministic_and_trail_is_stable(self):
        result = run_node(r'''
import { shelfRoute, trailRoute } from "./frontend/js/canvas/edge-routing.js";
const source={x:300,y:120},target={x:200,y:500};
const routes=[0,1,2,3].map(index=>shelfRoute(source,{...target,x:200+index*350},330,300,370,index,4));
process.stdout.write(JSON.stringify({routes,repeat:shelfRoute(source,target,330,300,370,0,4),trail:trailRoute(source,{x:700,y:140},330)}));
''')
        routes = result["routes"]
        self.assertEqual(routes[0], result["repeat"])
        self.assertEqual(4, len({json.dumps(route) for route in routes}))
        self.assertEqual(sorted(route[1]["x"] for route in routes), [route[1]["x"] for route in routes])
        self.assertEqual(4, len({route[2]["y"] for route in routes}))
        self.assertEqual(
            [{"x": 300, "y": 120}, {"x": 348, "y": 120}, {"x": 515, "y": 120}, {"x": 515, "y": 140}, {"x": 682, "y": 140}, {"x": 700, "y": 140}],
            result["trail"],
        )


if __name__ == "__main__":
    unittest.main()
