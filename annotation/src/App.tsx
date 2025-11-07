import { useState } from 'react';
import { SingleChatPage } from './pages/SingleChatPage';
import { ErrorBoundary } from './components/ErrorBoundary';

function App() {
  const [sessionId] = useState(() => {
    const id = crypto.randomUUID();
    return id;
  });

  return (
    <ErrorBoundary>
      <SingleChatPage sessionId={sessionId} />
    </ErrorBoundary>
  );
}

export default App;
