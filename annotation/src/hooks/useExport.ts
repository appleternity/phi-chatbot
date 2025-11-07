import { useState, useCallback } from 'react';
import { exportService } from '../services/exportService';

export function useExport(sessionId: string) {
  const [isExporting, setIsExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleExport = useCallback(async () => {
    setIsExporting(true);
    setError(null);

    try {
      const result = await exportService.exportSession(sessionId);

      if (!result.success) {
        setError(result.error || 'Export failed');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Export failed');
    } finally {
      setIsExporting(false);
    }
  }, [sessionId]);

  return {
    handleExport,
    isExporting,
    error,
  };
}
