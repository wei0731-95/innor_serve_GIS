/**
 * 搜尋機構名稱或地址。純前端 filter，不會打 API。
 */
export default function SearchBar({ value, onChange }) {
  return (
    <div className="search-bar">
      <label htmlFor="facility-search" className="visually-hidden">
        搜尋機構名稱或地址
      </label>
      <div className="search-bar__field">
        <input
          id="facility-search"
          type="search"
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder="輸入機構名稱或地址，例如：台大、北投"
          autoComplete="off"
        />
        {value && (
          <button type="button" className="search-bar__clear" onClick={() => onChange('')} aria-label="清除搜尋">
            ×
          </button>
        )}
      </div>
      <p className="search-bar__hint">可搜尋機構名稱與地址，「臺」與「台」視為相同。</p>
    </div>
  );
}
