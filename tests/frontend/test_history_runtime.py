import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[2]


def run_node(script):
    result = subprocess.run(["node", "--input-type=module", "--eval", script], cwd=ROOT, check=True, capture_output=True, text=True)
    return json.loads(result.stdout)


class HistoryRuntimeTest(unittest.TestCase):
    def test_async_history_is_bounded_clears_redo_and_retains_failed_entries(self):
        result = run_node(r'''
import { HistoryManager } from "./frontend/js/history/history-manager.js";
const history=new HistoryManager({limit:2});let value=0;
const command=(label,amount)=>({label,async redo(){value+=amount;},async undo(){value-=amount;}});
await history.execute(command("one",1));await history.execute(command("two",2));await history.execute(command("three",3));
await history.undo();const afterUndo={value,undo:history.undoStack.map(x=>x.label),redo:history.redoStack.map(x=>x.label)};
await history.execute(command("four",4));const afterNew={value,redo:history.redoStack.length};
history.record({label:"failure",async undo(){throw new Error("expected");},async redo(){}});try{await history.undo();}catch{}
const failedStillPresent=history.undoStack.at(-1).label==="failure";history.clear();
process.stdout.write(JSON.stringify({afterUndo,afterNew,failedStillPresent,cleared:{undo:history.undoStack.length,redo:history.redoStack.length,canUndo:history.canUndo,canRedo:history.canRedo}}));
''')
        self.assertEqual({"value": 3, "undo": ["two"], "redo": ["three"]}, result["afterUndo"])
        self.assertEqual({"value": 7, "redo": 0}, result["afterNew"])
        self.assertTrue(result["failedStillPresent"])
        self.assertEqual({"undo": 0, "redo": 0, "canUndo": False, "canRedo": False}, result["cleared"])

    def test_workspace_operations_share_chronological_history_and_restore_identity(self):
        result = run_node(r'''
import { HistoryManager } from "./frontend/js/history/history-manager.js";
import { FolderCanvas } from "./frontend/js/canvas/canvas.js";
const history=new HistoryManager(),canvas=Object.create(FolderCanvas.prototype);
Object.assign(canvas,{history,nodes:new Map(),workingSets:new Map(),elements:new Map(),setElements:new Map(),selected:null,selectedItem:null,viewport:{x:0,y:0,zoom:1},canvas:{clientWidth:900,clientHeight:600},actions:{},loadChildren:async()=>({folders:[],files:[]}),render(){},changed(){},clearSelection(){this.selected=null;this.selectedItem=null;},reflowHierarchy(){}});
await canvas.addRoot({id:"root",name:"Root",path:"/root"});const root=[...canvas.nodes.values()][0],rootPanelId=root.panelInstanceId,workingSetId=root.workingSetId;
await canvas.openChild(rootPanelId,{id:"child",name:"Child",path:"/root/child"});const child=[...canvas.nodes.values()].find(n=>n.folderId==="child"),childPanelId=child.panelInstanceId;
canvas.isolate(childPanelId);canvas.reattach(childPanelId);canvas.closeNode(childPanelId);
const labels=history.undoStack.map(entry=>entry.label);await history.undo();const restored=canvas.nodes.get(childPanelId);await history.redo();const closedAgain=!canvas.nodes.has(childPanelId);await history.undo();canvas.isolate(childPanelId);
process.stdout.write(JSON.stringify({labels,rootPanelId,workingSetId,restored:{panelInstanceId:restored.panelInstanceId,workingSetId:restored.workingSetId,visualParentPanelId:restored.visualParentPanelId,fsParentFolderId:restored.fsParentFolderId,x:restored.x,y:restored.y},closedAgain,redoCleared:history.redoStack.length===0}));
''')
        self.assertEqual(["Add root Folder Panel", "Open child Folder Panel", "Isolate", "Reattach", "Close Folder Panel branch"], result["labels"])
        self.assertEqual(result["rootPanelId"], result["restored"]["visualParentPanelId"])
        self.assertEqual(result["workingSetId"], result["restored"]["workingSetId"])
        self.assertEqual("root", result["restored"]["fsParentFolderId"])
        self.assertTrue(result["closedAgain"])
        self.assertTrue(result["redoCleared"])

    def test_working_set_drag_records_once_and_undo_restores_coordinates(self):
        result = run_node(r'''
import { HistoryManager } from "./frontend/js/history/history-manager.js";import { FolderCanvas } from "./frontend/js/canvas/canvas.js";
const history=new HistoryManager(),node={panelInstanceId:"panel",workingSetId:"set",x:10,y:20},element={setPointerCapture(){},hasPointerCapture(){return false;}};
const canvas=Object.create(FolderCanvas.prototype);Object.assign(canvas,{history,nodes:new Map([["panel",node]]),workingSets:new Map([["set",{workingSetId:"set"}]]),dragSession:null,clearFilesystemFeedback(){},canvas:{dataset:{}},render(){},changed(){},updatePositions(){},renderSets(){},renderEdges(){}});
canvas.startSetDrag({button:0,stopPropagation(){},pointerId:1,currentTarget:element,clientX:0,clientY:0},"set");node.x=110;node.y=220;canvas.dragSession.dragging=true;canvas.finishDrag(true);await history.undo();
process.stdout.write(JSON.stringify({entries:history.redoStack.length,x:canvas.nodes.get("panel").x,y:canvas.nodes.get("panel").y}));
''')
        self.assertEqual({"entries": 1, "x": 10, "y": 20}, result)

    def test_keyboard_shortcuts_and_editable_targets(self):
        result = run_node(r'''
import { historyShortcut } from "./frontend/js/history/history-manager.js";
const plain={closest(){return null;}},input={closest(){return this;}};
const event=(key,extra={},target=plain)=>({key,ctrlKey:false,metaKey:false,shiftKey:false,altKey:false,target,...extra});
process.stdout.write(JSON.stringify([historyShortcut(event("z",{ctrlKey:true}),"Win32"),historyShortcut(event("Z",{ctrlKey:true,shiftKey:true}),"Win32"),historyShortcut(event("y",{ctrlKey:true}),"Win32"),historyShortcut(event("z",{metaKey:true}),"MacIntel"),historyShortcut(event("z",{metaKey:true,shiftKey:true}),"MacIntel"),historyShortcut(event("z",{ctrlKey:true},input),"Win32")]));
''')
        self.assertEqual(["undo", "redo", "redo", "undo", "redo", None], result)

    def test_phase_three_records_supported_filesystem_operations_and_keeps_external_invalidation(self):
        app = (ROOT / "frontend/js/app.js").read_text(encoding="utf-8")
        self.assertIn('recordFilesystemOperation(history,{label:`Rename ${item.name}`', app)
        self.assertIn('label:`${copy?"Copy":"Move"} ${result.item.name}`', app)
        self.assertIn('label:`Create Folder ${name}`', app)
        self.assertNotIn("if(copy)history.clear();", app)
        self.assertIn("const before=filesystemFingerprint();", app)
        self.assertIn("if(filesystemFingerprint()!==before)history.clear();", app)
        self.assertIn('canvas.commitWorkspaceEdit("Open search result Folder Panel",before)', app)
        self.assertIn("if(canvas.nodes.size>count)", app)

    def test_filesystem_success_advances_history_despite_reconciliation_failure(self):
        result = run_node(r'''
import { HistoryManager } from "./frontend/js/history/history-manager.js";
import { recordFilesystemOperation } from "./frontend/js/history/filesystem-history.js";
const history=new HistoryManager(),errors=[],directions=[];
const entry=recordFilesystemOperation(history,{label:"Rename",token:"opaque",initialId:"old",replay:async(_token,direction)=>{directions.push(direction);return{item:{id:direction==="undo"?"old":"new"}};},reconcile:async()=>{throw new Error("ui failed");},reportError:error=>errors.push(error.message)});
await entry.reconcileInitial({item:{id:"new"}});const afterInitial={undo:history.undoStack.length,redo:history.redoStack.length};
await history.undo();const afterUndo={undo:history.undoStack.length,redo:history.redoStack.length};
await history.redo();const afterRedo={undo:history.undoStack.length,redo:history.redoStack.length};
process.stdout.write(JSON.stringify({afterInitial,afterUndo,afterRedo,directions,errors}));
''')
        self.assertEqual({"undo": 1, "redo": 0}, result["afterInitial"])
        self.assertEqual({"undo": 0, "redo": 1}, result["afterUndo"])
        self.assertEqual({"undo": 1, "redo": 0}, result["afterRedo"])
        self.assertEqual(["undo", "redo"], result["directions"])
        self.assertEqual(["ui failed"] * 3, result["errors"])

    def test_filesystem_backend_conflict_keeps_mixed_history_order(self):
        result = run_node(r'''
import { HistoryManager } from "./frontend/js/history/history-manager.js";
import { recordFilesystemOperation } from "./frontend/js/history/filesystem-history.js";
const history=new HistoryManager();history.record({label:"Close Panel",async undo(){},async redo(){}});
recordFilesystemOperation(history,{label:"Move",token:"opaque",initialId:"old",replay:async()=>{throw new Error("conflict");},reconcile:async()=>{},reportError(){}});
history.record({label:"Isolate",async undo(){},async redo(){}});await history.undo();try{await history.undo();}catch{}
process.stdout.write(JSON.stringify({undo:history.undoStack.map(x=>x.label),redo:history.redoStack.map(x=>x.label)}));
''')
        self.assertEqual(["Close Panel", "Move"], result["undo"])
        self.assertEqual(["Isolate"], result["redo"])

    def test_filesystem_redo_conflict_keeps_entry_on_redo_stack(self):
        result = run_node(r'''
import { HistoryManager } from "./frontend/js/history/history-manager.js";
import { recordFilesystemOperation } from "./frontend/js/history/filesystem-history.js";
const history=new HistoryManager();
recordFilesystemOperation(history,{label:"Copy",token:"opaque",initialId:"copy",replay:async(_token,direction)=>{if(direction==="redo")throw new Error("conflict");return{item:{id:"copy"}}},reconcile:async()=>{},reportError(){}});
await history.undo();try{await history.redo();}catch{}
process.stdout.write(JSON.stringify({undo:history.undoStack.map(x=>x.label),redo:history.redoStack.map(x=>x.label)}));
''')
        self.assertEqual([], result["undo"])
        self.assertEqual(["Copy"], result["redo"])

    def test_workspace_and_all_supported_filesystem_entries_are_chronological(self):
        result = run_node(r'''
import { HistoryManager } from "./frontend/js/history/history-manager.js";
import { recordFilesystemOperation } from "./frontend/js/history/filesystem-history.js";
const history=new HistoryManager(),order=[];
const workspace=label=>history.record({label,async undo(){order.push(`undo:${label}`)},async redo(){order.push(`redo:${label}`)}});
const filesystem=label=>recordFilesystemOperation(history,{label,token:label,initialId:label,replay:async(_token,direction)=>{order.push(`${direction}:${label}`);return{item:{id:label}}},reconcile:async()=>{},reportError(){}});
workspace("Close Panel");filesystem("Create Folder");filesystem("Rename");filesystem("Move");filesystem("Copy");workspace("Isolate");
for(let index=0;index<6;index++)await history.undo();for(let index=0;index<6;index++)await history.redo();
process.stdout.write(JSON.stringify({order,undo:history.undoStack.map(entry=>entry.label)}));
''')
        self.assertEqual(["undo:Isolate", "undo:Copy", "undo:Move", "undo:Rename", "undo:Create Folder", "undo:Close Panel",
                          "redo:Close Panel", "redo:Create Folder", "redo:Rename", "redo:Move", "redo:Copy", "redo:Isolate"], result["order"])
        self.assertEqual(["Close Panel", "Create Folder", "Rename", "Move", "Copy", "Isolate"], result["undo"])


if __name__ == "__main__":
    unittest.main()
