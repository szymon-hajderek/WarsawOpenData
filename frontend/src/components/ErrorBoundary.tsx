import { Component, type ErrorInfo, type ReactNode } from 'react';

interface State {
  failed: boolean;
}

/** Catches a render error anywhere below and shows a short message instead of a white page. */
export default class ErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { failed: false };

  static getDerivedStateFromError(): State {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('UI error', error, info.componentStack);
  }

  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <div role="alert" style={{ padding: 24, fontFamily: 'Roboto, sans-serif' }}>
        <h1 style={{ fontSize: 20 }}>Coś poszło nie tak</h1>
        <p>Aplikacja napotkała błąd. Odśwież stronę, aby spróbować jeszcze raz.</p>
        <button type="button" onClick={() => window.location.reload()}>
          Odśwież
        </button>
      </div>
    );
  }
}
