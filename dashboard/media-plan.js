export function mediaSummary(value) {
  const intro = value.album || '';
  const multi = value.album2 || intro;
  if (value.engine === 'intro') return `Introduction : 1 vidéo · ${intro}`;
  if (value.engine === 'intro+multi') return `Introduction : 1 vidéo · ${intro} → ${value.count} média(s) · ${multi} (${Number(value.count) + 1} au total)`;
  return `${value.count} média(s) · ${multi}`;
}
