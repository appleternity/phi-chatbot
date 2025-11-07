/**
 * Error Boundary Component
 *
 * Catches React errors in component tree and displays fallback UI
 * Prevents entire app crash from component errors
 */

import { Component, ErrorInfo, ReactNode } from 'react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
    };
  }

  static getDerivedStateFromError(error: Error): Partial<State> {
    // Update state to trigger fallback UI
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    // Log error details for debugging
    console.error('Error boundary caught:', error, errorInfo);

    // Update state with error info
    this.setState({
      errorInfo,
    });

    // In production, send to error tracking service (e.g., Sentry)
    // if (import.meta.env.PROD) {
    //   logErrorToService(error, errorInfo);
    // }
  }

  private handleReload = (): void => {
    window.location.reload();
  };

  private handleClearStorage = (): void => {
    if (confirm('確定要清除所有資料嗎？這將無法復原。')) {
      localStorage.clear();
      window.location.reload();
    }
  };

  render(): ReactNode {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
          <div className="max-w-md w-full bg-white rounded-lg shadow-lg p-6">
            <div className="flex items-center justify-center w-16 h-16 mx-auto mb-4 bg-red-100 rounded-full">
              <span className="text-4xl">⚠️</span>
            </div>

            <h2 className="text-2xl font-bold text-red-600 mb-4 text-center">
              發生錯誤
            </h2>

            <p className="text-gray-700 mb-4 text-center">
              應用程式遇到錯誤。請重新整理頁面或清除瀏覽器資料。
            </p>

            {/* Error details (collapsed by default) */}
            {this.state.error && (
              <details className="mb-4">
                <summary className="cursor-pointer text-sm text-gray-600 mb-2 hover:text-gray-800">
                  顯示錯誤詳情
                </summary>
                <pre className="bg-gray-100 p-3 rounded text-xs overflow-auto max-h-40 border border-gray-300">
                  {this.state.error.message}
                  {this.state.errorInfo && (
                    <>
                      {'\n\n'}
                      {this.state.errorInfo.componentStack}
                    </>
                  )}
                </pre>
              </details>
            )}

            {/* Action buttons */}
            <div className="space-y-3">
              <button
                onClick={this.handleReload}
                className="w-full px-4 py-2 bg-gradient-to-r from-[#667eea] to-[#764ba2] text-white rounded-lg font-medium hover:opacity-90 transition-opacity"
              >
                重新整理頁面
              </button>

              <button
                onClick={this.handleClearStorage}
                className="w-full px-4 py-2 bg-white border border-gray-300 text-gray-700 rounded-lg font-medium hover:bg-gray-50 transition-colors"
              >
                清除所有資料並重新載入
              </button>
            </div>

            {/* Help text */}
            <p className="mt-4 text-xs text-gray-500 text-center">
              如果問題持續發生，請嘗試清除瀏覽器快取或聯繫技術支援。
            </p>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
