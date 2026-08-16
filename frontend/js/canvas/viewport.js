export function applyViewport(world, edges, viewport) {
  const transform = `translate(${viewport.x}px, ${viewport.y}px) scale(${viewport.zoom})`;
  world.style.transform = transform;
  edges.style.transform = transform;
}
