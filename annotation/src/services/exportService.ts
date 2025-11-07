import { storageService } from './storageService';
import { ExportedData } from '../types/export';

export class ExportService {
  /**
   * Aggregates data from all chatbots and generates ExportedData structure
   */
  generateExportData(sessionId: string): ExportedData | null {
    const session = storageService.loadSession(sessionId);
    if (!session) {
      return null;
    }

    const totalMessages = session.chatbots.reduce(
      (sum, bot) => sum + bot.messages.length,
      0
    );

    const exportData: ExportedData = {
      sessionId: session.sessionId,
      exportTimestamp: new Date().toISOString(),
      selectedChatbotId: session.selection.selectedChatbotId,
      chatbots: session.chatbots.map(bot => ({
        chatId: bot.chatId,
        displayName: bot.displayName,
        messages: bot.messages,
        config: bot.config,
      })),
      metadata: {
        exportVersion: '1.0.0',
        sessionCreatedAt: session.metadata.createdAt,
        sessionUpdatedAt: session.metadata.updatedAt,
        totalMessages,
      },
    };

    return exportData;
  }

  /**
   * Validates export data structure
   */
  validateExportData(data: ExportedData): { valid: boolean; errors: string[] } {
    const errors: string[] = [];

    if (!data.sessionId) {
      errors.push('Missing sessionId');
    }

    if (!data.exportTimestamp) {
      errors.push('Missing exportTimestamp');
    }

    if (!Array.isArray(data.chatbots) || data.chatbots.length === 0) {
      errors.push('chatbots array is empty or invalid');
    }

    if (data.selectedChatbotId !== null) {
      const chatbotExists = data.chatbots.some(
        bot => bot.chatId === data.selectedChatbotId
      );
      if (!chatbotExists) {
        errors.push('selectedChatbotId does not match any chatbot');
      }
    }

    const actualTotal = data.chatbots.reduce(
      (sum, bot) => sum + bot.messages.length,
      0
    );
    if (actualTotal !== data.metadata.totalMessages) {
      errors.push('totalMessages count mismatch');
    }

    return {
      valid: errors.length === 0,
      errors,
    };
  }

  /**
   * Creates a downloadable JSON file
   */
  downloadJSON(data: ExportedData): void {
    const json = JSON.stringify(data, null, 2);
    const blob = new Blob([json], { type: 'application/json' });
    const url = URL.createObjectURL(blob);

    const timestamp = Date.now();
    const filename = `chatbot-annotation-${timestamp}.json`;

    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    link.click();

    // Cleanup
    URL.revokeObjectURL(url);
  }

  /**
   * Main export function with validation
   */
  async exportSession(sessionId: string): Promise<{ success: boolean; error?: string }> {
    try {
      const data = this.generateExportData(sessionId);

      if (!data) {
        return { success: false, error: 'Session not found' };
      }

      const validation = this.validateExportData(data);
      if (!validation.valid) {
        return {
          success: false,
          error: `Validation failed: ${validation.errors.join(', ')}`,
        };
      }

      this.downloadJSON(data);
      return { success: true };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Export failed',
      };
    }
  }
}

export const exportService = new ExportService();
