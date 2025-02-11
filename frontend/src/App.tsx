import React, { useState } from 'react';
import Home from './pages/Home';
import Download from './pages/Download';

export interface ChangeLog {
  field: string;
  change: string;
}

const App: React.FC = () => {
  // Page state: either "home" or "download"
  const [page, setPage] = useState<'home' | 'download'>('home');

  // --- State for CV Input ---
  const [useLatex, setUseLatex] = useState(false);
  const [cvFile, setCvFile] = useState<File | null>(null);
  const [latexCode, setLatexCode] = useState('');

  // --- State for Job Description ---
  const [jobDescIsLink, setJobDescIsLink] = useState(true);
  const [jobDescLink, setJobDescLink] = useState('');
  const [jobDescription, setJobDescription] = useState('');

  // --- State for the Changes Log ---
  const [changes, setChanges] = useState<ChangeLog[]>([]);

  const addChangeLog = (field: string, change: string) => {
    setChanges(prev => [...prev, { field, change }]);
  };

  // --- Handlers for CV Input ---
  const handleCvFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const file = e.target.files[0];
      setCvFile(file);
      addChangeLog('CV Input', `File selected: ${file.name}`);
    }
  };

  const handleLatexChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setLatexCode(e.target.value);
    addChangeLog('CV Input', 'LaTeX code updated');
  };

  // --- Handlers for Job Description ---
  const handleJobDescLinkChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setJobDescLink(e.target.value);
    addChangeLog('Job Description', 'Link updated');
  };

  const handleJobDescriptionChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setJobDescription(e.target.value);
    addChangeLog('Job Description', 'Text updated');
  };

  // --- Download handler ---
  const downloadCV = async () => {
    try {
      const formData = new FormData();
  
      // Append CV input: either LaTeX code or an uploaded file.
      if (useLatex) {
        formData.append('latex_code', latexCode);
      } else if (cvFile) {
        formData.append('cv_file', cvFile);
      }
  
      // Append Job Description input: either a link or a text description.
      if (jobDescIsLink) {
        formData.append('job_desc_link', jobDescLink);
      } else {
        formData.append('job_description', jobDescription);
      }
  
      // *** Change the URL below to match your backend ***
      const response = await fetch('http://localhost:8000/api/format-cv', {
        method: 'POST',
        body: formData,
      });
  
      if (!response.ok) {
        throw new Error('Failed to format CV on the backend.');
      }
  
      // The backend should return the PDF as a blob.
      const blob = await response.blob();
  
      // Create a temporary URL and trigger a download.
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'formatted_cv.pdf';
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
  
      addChangeLog('Download', 'Formatted CV downloaded as PDF');
    } catch (error) {
      console.error('Error downloading formatted CV:', error);
    }
  };

  return (
    <>
      {page === 'home' ? (
        <Home
          useLatex={useLatex}
          setUseLatex={setUseLatex}
          cvFile={cvFile}
          latexCode={latexCode}
          handleCvFileChange={handleCvFileChange}
          handleLatexChange={handleLatexChange}
          jobDescIsLink={jobDescIsLink}
          setJobDescIsLink={setJobDescIsLink}
          jobDescLink={jobDescLink}
          jobDescription={jobDescription}
          handleJobDescLinkChange={handleJobDescLinkChange}
          handleJobDescriptionChange={handleJobDescriptionChange}
          onFormat={() => setPage('download')}
        />
      ) : (
        <Download
          changes={changes}
          onDownload={downloadCV}
          onBack={() => setPage('home')}
        />
      )}
    </>
  );
};

export default App;
