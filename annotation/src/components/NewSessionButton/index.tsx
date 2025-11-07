import React, { useState } from 'react';
import { storageService } from '../../services/storageService';

interface NewSessionButtonProps {
  onNewSession: (sessionId: string) => void;
}

export const NewSessionButton: React.FC<NewSessionButtonProps> = ({ onNewSession }) => {
  const [showConfirm, setShowConfirm] = useState(false);

  const handleNewSession = () => {
    storageService.clearAllData();
    const newSessionId = storageService.initializeNewSession();
    onNewSession(newSessionId);
    setShowConfirm(false);
  };

  return (
    <div className="fixed bottom-6 right-6 z-50">
      {showConfirm ? (
        <div
          className="bg-white p-4 rounded-lg shadow-xl border-2 border-red-500"
          role="dialog"
          aria-labelledby="confirm-dialog-title"
        >
          <p id="confirm-dialog-title" className="text-sm text-gray-700 mb-3">
            確定要開始新對話嗎？
          </p>
          <div className="flex gap-2">
            <button
              onClick={handleNewSession}
              aria-label="確定開始新對話"
              className="px-4 py-2 bg-red-500 text-white rounded-lg font-medium hover:bg-red-600 transition-colors"
            >
              確定
            </button>
            <button
              onClick={() => setShowConfirm(false)}
              aria-label="取消新對話"
              className="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg font-medium hover:bg-gray-300 transition-colors"
            >
              取消
            </button>
          </div>
        </div>
      ) : (
        <button
          onClick={() => setShowConfirm(true)}
          aria-label="開始新對話"
          className="px-6 py-3 bg-white text-gray-700 border-2 border-gray-300 rounded-full font-semibold shadow-lg hover:shadow-xl hover:border-red-500 hover:text-red-600 transition-all"
        >
          開始新對話
        </button>
      )}
    </div>
  );
};
