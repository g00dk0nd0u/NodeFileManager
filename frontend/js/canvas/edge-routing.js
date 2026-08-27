export const SHELF_LANE_GAP = 6;

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
