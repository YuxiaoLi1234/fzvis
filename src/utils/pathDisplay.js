export function maskDisplayPath(value) {
  if (value == null) return value;
  const text = String(value);
  return text.replace(/\/home\/[^/]+(?=\/|$)/g, '~');
}
