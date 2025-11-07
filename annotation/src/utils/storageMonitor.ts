/**
 * localStorage Quota Monitoring Utilities
 *
 * Monitors localStorage usage and warns users when approaching quota limits.
 * Helps prevent QuotaExceededError and data loss.
 */

const QUOTA_WARNING_THRESHOLD = 0.75; // 75%
const STORAGE_LIMIT = 5 * 1024 * 1024; // 5MB estimate (typical browser limit)

export interface StorageQuota {
  used: number;
  available: number;
  percentage: number;
  warningNeeded: boolean;
}

/**
 * Calculate current localStorage usage and available space
 *
 * @returns Storage quota information
 */
export function checkStorageQuota(): StorageQuota {
  let used = 0;

  // Calculate used storage by summing all key-value pairs
  for (const key in localStorage) {
    if (Object.prototype.hasOwnProperty.call(localStorage, key)) {
      // Count both key and value length (UTF-16 encoding)
      used += (localStorage[key].length + key.length) * 2; // 2 bytes per char
    }
  }

  const percentage = used / STORAGE_LIMIT;

  return {
    used,
    available: STORAGE_LIMIT - used,
    percentage,
    warningNeeded: percentage >= QUOTA_WARNING_THRESHOLD,
  };
}

/**
 * Show quota warning dialog if threshold exceeded
 */
export function showQuotaWarning(): void {
  const quota = checkStorageQuota();

  if (quota.warningNeeded) {
    const usedMB = (quota.used / (1024 * 1024)).toFixed(2);
    const percentUsed = (quota.percentage * 100).toFixed(1);

    alert(
      `⚠️ 儲存空間警告\n\n` +
      `已使用 ${usedMB} MB (${percentUsed}%)\n` +
      `建議匯出資料後清除舊對話`
    );
  }
}

/**
 * Format bytes to human-readable string
 *
 * @param bytes - Number of bytes
 * @returns Formatted string (e.g., "1.23 MB")
 */
export function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 Bytes';

  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));

  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`;
}
