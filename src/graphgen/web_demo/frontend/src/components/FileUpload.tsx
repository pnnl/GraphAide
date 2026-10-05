import React from 'react';
import { useDropzone } from 'react-dropzone';
import './FileUpload.css';

interface Props {
  onFileUpload: (file: File) => void;
}

export function FileUpload({ onFileUpload }: Props) {
  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop: (files) => {
      if (files.length > 0) {
        const file = files[0];
        const validTypes = [
          'application/pdf',
          'text/plain',
          'application/json',
          'application/jsonlines',
        ];
        if (validTypes.includes(file.type) || file.name.endsWith('.jsonl')) {
          onFileUpload(file);
        } else {
          alert('Please upload a PDF, TXT, JSON, or JSONL file');
        }
      }
    },
  });

  return (
    <div className="file-upload">
      <div
        {...getRootProps()}
        className={`dropzone ${isDragActive ? 'active' : ''}`}
      >
        <input {...getInputProps()} />
        {isDragActive ? (
          <p>📥 Drop the file here...</p>
        ) : (
          <>
            <p>📁 Drag & drop a file here or click to browse</p>
            <small>Supported: PDF, TXT, JSON, JSONL</small>
          </>
        )}
      </div>
    </div>
  );
}
