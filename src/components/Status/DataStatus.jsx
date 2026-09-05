/**
 * 資料載入狀態相關的小元件：載入中、載入失敗、部分來源失敗、Header 狀態標籤。
 */

const POSSIBLE_CAUSES = ['API 無法連線', 'CSV 格式錯誤', 'CORS（瀏覽器跨來源限制）', '網路錯誤'];

const STATUS_LABEL = {
  idle: '尚未載入',
  loading: '資料載入中',
  success: '資料已載入',
  error: '資料載入失敗',
};

function describeError(error) {
  if (!error) return '未知錯誤';
  const message = error.message || String(error);
  const causeMessage = error.cause?.message;
  if (causeMessage && !message.includes(causeMessage)) {
    return `${message}（${causeMessage}）`;
  }
  return message;
}

export function LoadingNotice() {
  return (
    <div className="notice notice--loading" role="status" aria-live="polite">
      <span className="notice__spinner" aria-hidden="true" />
      正在取得臺北市公開資料……
    </div>
  );
}

export function ErrorNotice({ error, onRetry }) {
  // 瀏覽器無法區分 CORS 與一般網路錯誤（都是 fetch 直接 reject），所以一併提示
  const isNetworkError = error?.kind === 'network';

  return (
    <div className="notice notice--error" role="alert">
      <h3>資料載入失敗</h3>
      {isNetworkError && (
        <p className="notice__highlight">目前瀏覽器無法直接存取資料來源，可能受到 CORS 限制。</p>
      )}
      <div className="notice__message">{describeError(error)}</div>
      <p>可能原因：</p>
      <ul>
        {POSSIBLE_CAUSES.map((cause) => (
          <li key={cause}>{cause}</li>
        ))}
      </ul>
      {isNetworkError && import.meta.env.DEV && (
        <p className="notice__hint">
          開發模式提示：請確認 vite.config.js 的 server.proxy 與 .env.development 的
          VITE_TAIPEI_PROXY_PREFIX 設定。
        </p>
      )}
      <button type="button" className="btn" onClick={onRetry}>
        重新載入
      </button>
    </div>
  );
}

export function PartialErrorNotice({ errors, onRetry }) {
  return (
    <div className="notice notice--warning" role="alert">
      <h3>部分資料來源載入失敗</h3>
      <ul>
        {errors.map((error, index) => (
          <li key={error?.sourceKey ?? index}>{describeError(error)}</li>
        ))}
      </ul>
      <button type="button" className="btn" onClick={onRetry}>
        重新載入
      </button>
    </div>
  );
}

export function HeaderStatus({ status, total }) {
  const label = status === 'success' ? `${STATUS_LABEL.success}：${total} 筆` : STATUS_LABEL[status] ?? '';
  return <span className={`status-pill status-pill--${status}`}>{label}</span>;
}
