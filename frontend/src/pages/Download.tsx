import React from 'react';
import { ChangeLog } from '../App';
import './Download.css';

interface DownloadProps {
  changes: ChangeLog[];
  onDownload: () => void;
  onBack: () => void;
}

const Download: React.FC<DownloadProps> = ({ changes, onDownload, onBack }) => {
  return (
    <div className="download-container">
      {/* Title */}
      <h1 className="title">Download Formatted CV</h1>

      {/* Back Button (Above the Table) */}
      <button className="back-button" onClick={onBack}>
        ← Back
      </button>

      {/* Changes Table */}
      <div className="log-table-container">
        <table className="log-table">
          <thead>
            <tr>
              <th>Field</th>
              <th>Change</th>
            </tr>
          </thead>
          <tbody>
            {changes.length > 0 ? (
              changes.map((entry, index) => (
                <tr key={index}>
                  <td>{entry.field}</td>
                  <td>{entry.change}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={2} className="no-changes">No changes made yet.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Download Button (Below the Table) */}
      <div className="button-group">
        <button className="action-button" onClick={onDownload}>
          Download Formatted CV (PDF)
        </button>
      </div>
    </div>
  );
};

export default Download;
