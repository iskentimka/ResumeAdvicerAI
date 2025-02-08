import React, { useState } from 'react';
import { jsPDF } from 'jspdf';
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

  // --- Download handler using jsPDF ---
  const downloadCV = () => {
    const content = `Formatted CV:

${useLatex ? `LaTeX Code: ${latexCode}` : cvFile ? `CV File: ${cvFile.name}` : 'No CV provided.'}

Job Description:
${jobDescIsLink ? `Link: ${jobDescLink}` : jobDescription}`;

    const doc = new jsPDF();
    doc.text(content, 10, 10);
    doc.save('formatted_cv.pdf');
    addChangeLog('Download', 'Formatted CV downloaded as PDF');
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
