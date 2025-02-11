import React from 'react';
import './Home.css';

interface HomeProps {
  useLatex: boolean;
  setUseLatex: (value: boolean) => void;
  cvFile: File | null;
  latexCode: string;
  handleCvFileChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  handleLatexChange: (e: React.ChangeEvent<HTMLTextAreaElement>) => void;
  jobDescIsLink: boolean;
  setJobDescIsLink: (value: boolean) => void;
  jobDescLink: string;
  jobDescription: string;
  handleJobDescLinkChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  handleJobDescriptionChange: (e: React.ChangeEvent<HTMLTextAreaElement>) => void;
  onFormat: () => void;
}

const Home: React.FC<HomeProps> = ({
  useLatex,
  setUseLatex,
  cvFile,
  latexCode,
  handleCvFileChange,
  handleLatexChange,
  jobDescIsLink,
  setJobDescIsLink,
  jobDescLink,
  jobDescription,
  handleJobDescLinkChange,
  handleJobDescriptionChange,
  onFormat,
}) => {
  return (
    <div className="home-container">
      <h1>CV Editor App</h1>
      <div className="input-section">
        {/* CV Input Card */}
        <div className="card">
          <h2 className="input-title">CV Input</h2>
          <div className="radio-group">
            <label>
              <input
                type="radio"
                checked={!useLatex}
                onChange={() => setUseLatex(false)}
              />
              Upload File
            </label>
            <label>
              <input
                type="radio"
                checked={useLatex}
                onChange={() => setUseLatex(true)}
              />
              LaTeX Code
            </label>
          </div>
          <div className="input-group">
            {useLatex ? (
              <textarea
                value={latexCode}
                onChange={handleLatexChange}
                placeholder="Enter LaTeX code for your CV"
                rows={10}
              />
            ) : (
              <>
                <input type="file" onChange={handleCvFileChange} />
                {cvFile && <p>Selected File: {cvFile.name}</p>}
              </>
            )}
          </div>
        </div>

        {/* Job Description Card */}
        <div className="card">
          <h2 className="input-title">Job Description</h2>
          <div className="radio-group">
            <label>
              <input
                type="radio"
                checked={jobDescIsLink}
                onChange={() => setJobDescIsLink(true)}
              />
              Link
            </label>
            <label>
              <input
                type="radio"
                checked={!jobDescIsLink}
                onChange={() => setJobDescIsLink(false)}
              />
              Description Text
            </label>
          </div>
          <div className="input-group">
            {jobDescIsLink ? (
              <input
                type="text"
                value={jobDescLink}
                onChange={handleJobDescLinkChange}
                placeholder="Enter URL for the job description"
              />
            ) : (
              <textarea
                value={jobDescription}
                onChange={handleJobDescriptionChange}
                placeholder="Enter the job description text"
                rows={10}
              />
            )}
          </div>
        </div>
      </div>
      {/* Format button */}
      <button className="action-button" onClick={onFormat}>
        Format
      </button>
    </div>
  );
};

export default Home;
