export function childPositions(parent, count) {
  const spacing = 220;
  const start = parent.x - ((count - 1) * spacing) / 2;
  return Array.from({ length: count }, (_, index) => ({ x: start + index * spacing, y: parent.y + 130 }));
}
