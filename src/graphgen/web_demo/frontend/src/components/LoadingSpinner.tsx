import React from 'react';
import './LoadingSpinner.css';

export function LoadingSpinner() {
  return (
    <div className="loading-spinner">
      <div className="spinner"></div>
      <p>Processing... This may take a few minutes</p>
    </div>
  );
}
