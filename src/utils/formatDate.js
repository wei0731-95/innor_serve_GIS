/** 日期時間顯示（臺灣慣用 24 小時制）。無效或缺少時回傳 fallback。 */
export function formatDateTime(value, fallback = '未提供') {
  if (!value) return fallback;
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return fallback;
  return date.toLocaleString('zh-TW', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  });
}

/** 多個時間取最新（忽略 null） */
export function latestDate(dates) {
  let latest = null;
  for (const date of dates) {
    if (date instanceof Date && !Number.isNaN(date.getTime()) && (!latest || date > latest)) {
      latest = date;
    }
  }
  return latest;
}
