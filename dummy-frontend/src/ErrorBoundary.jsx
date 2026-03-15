import { Component } from 'react'

class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, message: '' }
  }

  static getDerivedStateFromError(error) {
    return {
      hasError: true,
      message: error?.message || 'Something went wrong while rendering the itinerary.',
    }
  }

  componentDidCatch(error, info) {
    console.error('Itinerary render failed', error, info)
  }

  handleRetry = () => {
    this.setState({ hasError: false, message: '' })
    this.props.onRetry?.()
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="glass-panel error-toast" role="alert">
          <strong>Unable to show this itinerary.</strong>
          <p>{this.state.message}</p>
          <button className="generate-btn" onClick={this.handleRetry}>
            Retry
          </button>
        </div>
      )
    }

    return this.props.children
  }
}

export default ErrorBoundary
