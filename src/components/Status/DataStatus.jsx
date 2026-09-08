import { API_BASE_URL } from '../../services/backendApi.js';
import { formatDateTime } from '../../utils/formatDate.js';

/**
 * 資料載入狀態相關的小元件：載入中、後端同步中、載入失敗、部分來源失敗、Header 狀態標籤。
 */

const POSSIBLE_CAUSES = [
  '後端 FastAPI 未啟動（cd backend && uvicorn app.main:app --reload）',
  'CORS 設定未包含目前網址（backend/.env 的 CORS_ORIGINS）',
  '前端 VITE_API_BASE_URL 指向錯誤的後端位址',
  '後端資料庫錯誤或網路錯誤',
];

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

function apiLabel() {
  return API_BASE_URL || `${window.location.origin}（同源）`;
}

export function LoadingNotice() {
  return (
    <div className="notice notice--loading" role="status" aria-live="polite">
      <span className="notice__spinner" aria-hidden="true" />
      正在從後端取得臺北市公共服務設施資料……
    </div>
  );
}

export function SyncingNotice({ pendingSources = [] }) {
  return (
    <div className="notice notice--info" role="status" aria-live="polite">
      <span className="notice__spinner" aria-hidden="true" />
      <div>
        後端正在同步政府開放資料，畫面會自動更新。
        {pendingSources.length > 0 && (
          <div className="notice__hint">
            尚未完成：{pendingSources.map((source) => source.sourceName).join('、')}
          </div>
        )}
      </div>
    </div>
  );
}

export function ErrorNotice({ error, onRetry }) {
  const isNetworkError = error?.kind === 'network';

  return (
    <div className="notice notice--error" role="alert">
      <h3>資料載入失敗</h3>
      {isNetworkError && (
        <p className="notice__highlight">
          目前瀏覽器無法連線至後端 API（{apiLabel()}）。請確認 FastAPI 已啟動，且 CORS_ORIGINS 包含{' '}
          {window.location.origin}。
        </p>
      )}
      <div className="notice__message">{describeError(error)}</div>
      <p>可能原因：</p>
      <ul>
        {POSSIBLE_CAUSES.map((cause) => (
          <li key={cause}>{cause}</li>
        ))}
      </ul>
      <button type="button" className="btn" onClick={onRetry}>
        重新載入
      </button>
    </div>
  );
}

export function PartialErrorNotice({ errors, onRetry }) {
  return (
    <div className="notice notice--warning" role="alert">
      <h3>部分資料來源最近一次同步失敗</h3>
      <ul>
        {errors.map((item, index) => (
          <li key={item?.sourceKey ?? index}>
            「{item.sourceName}」：{item.message}
            {item.recordCount > 0 && (
              <span className="notice__hint">
                {' '}
                目前顯示的是 {formatDateTime(item.lastSuccessAt, '先前')} 成功同步的 {item.recordCount} 筆資料。
              </span>
            )}
            {item.recordCount === 0 && <span className="notice__hint"> 此來源目前沒有資料可顯示。</span>}
          </li>
        ))}
      </ul>
      <button type="button" className="btn" onClick={onRetry}>
        重新載入
      </button>
    </div>
  );
}

export function HeaderStatus({ status, total, syncRunning = false }) {
  let label = STATUS_LABEL[status] ?? '';
  if (status === 'success') {
    label = `${STATUS_LABEL.success}：${total} 筆${syncRunning ? '（後端同步中）' : ''}`;
  }
  return <span className={`status-pill status-pill--${status}`}>{label}</span>;
}
