import React from 'react';
import { useExport } from '../../hooks/useExport';

interface ExportButtonProps {
  sessionId: string;
}

export const ExportButton: React.FC<ExportButtonProps> = ({ sessionId }) => {
  const { handleExport, isExporting, error } = useExport(sessionId);

  return (
    <div className="fixed top-6 right-6 z-50">
      <button
        onClick={handleExport}
        disabled={isExporting}
        aria-label={isExporting ? '正在下載資料' : '下載標註資料'}
        aria-disabled={isExporting}
        className="px-6 py-3 bg-gradient-to-r from-[#667eea] to-[#764ba2] text-white rounded-full font-semibold shadow-lg hover:shadow-xl hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center gap-2"
      >
        {isExporting ? (
          <>
            <span className="animate-spin">⏳</span>
            <span>下載中...</span>
          </>
        ) : (
          <>
            <span>📥</span>
            <span>下載資料</span>
          </>
        )}
      </button>

      {error && (
        <div className="mt-2 px-4 py-2 bg-red-50 border border-red-200 rounded-lg text-red-600 text-sm max-w-xs">
          {error}
        </div>
      )}
    </div>
  );
};
