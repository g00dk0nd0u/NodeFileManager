export const SHELF_LANE_GAP = 6;

export function scrollTopToReveal(scrollTop, viewportTop, viewportBottom, rowTop, rowBottom) {
  if (rowTop < viewportTop) return scrollTop - (viewportTop - rowTop);
  if (rowBottom > viewportBottom) return scrollTop + rowBottom - viewportBottom;
  return scrollTop;
}

export function measureConnectorAnchors(parentElement, childElement, childFolderId, canvasRect, screenToWorld, trail, escapeId = CSS.escape) {
  const sourceRow = parentElement?.querySelector(`.folder-item[data-id="${escapeId(childFolderId)}"]`);
  const header = childElement?.querySelector(".node-title");
  if (!sourceRow || !header) return null;
  const rowRect = sourceRow.getBoundingClientRect(), headerRect = header.getBoundingClientRect(), parentRect = parentElement.getBoundingClientRect();
  const from = { x: rowRect.right, y: rowRect.top + rowRect.height / 2 };
  const to = trail ? { x: headerRect.left, y: headerRect.top + headerRect.height / 2 } : { x: headerRect.left + headerRect.width / 2, y: headerRect.top };
  return { source: screenToWorld(from.x - canvasRect.left, from.y - canvasRect.top), target: screenToWorld(to.x - canvasRect.left, to.y - canvasRect.top), parentRight: screenToWorld(parentRect.right - canvasRect.left, 0).x };
}

export function trailRoute(source, target, parentRight) {
  const exit = { x: Math.min(target.x - 18, Math.max(source.x + 18, parentRight + 18)), y: source.y };
  const approach = { x: target.x - 18, y: target.y };
  const middle = (exit.x + approach.x) / 2;
  return [source, exit, { x: middle, y: exit.y }, { x: middle, y: approach.y }, approach, target];
}

export function shelfRoute(source, target, parentRight, parentBottom, shelfTop, laneIndex, laneCount) {
  const centeredLane = laneIndex - (laneCount - 1) / 2;
  const exitX = parentRight + 18 + laneIndex * SHELF_LANE_GAP;
  const railY = (parentBottom + shelfTop) / 2 + centeredLane * SHELF_LANE_GAP;
  return [source, { x: exitX, y: source.y }, { x: exitX, y: railY }, { x: target.x, y: railY }, { x: target.x, y: target.y - 18 }, target];
}
