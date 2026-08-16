export function renderEdges(group, nodes) {
  group.replaceChildren();
  for (const node of nodes.values()) {
    if (!node.parentId || !nodes.has(node.parentId)) continue;
    const parent = nodes.get(node.parentId);
    const siblings = [...nodes.values()].filter((item) => item.parentId === node.parentId);
    if (siblings.length < 2) continue;
    const x1 = parent.x + 120, y1 = parent.y + (parent.renderedHeight || 54), x2 = node.x + 120, y2 = node.y;
    const middle = (y1 + y2) / 2;
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("d", `M ${x1} ${y1} C ${x1} ${middle}, ${x2} ${middle}, ${x2} ${y2}`);
    group.append(path);
  }
}
