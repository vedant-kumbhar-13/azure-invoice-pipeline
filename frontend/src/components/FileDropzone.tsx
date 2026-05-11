import { useCallback, useState, useRef } from 'react';
import { useDropzone } from 'react-dropzone';
import type { FileRejection } from 'react-dropzone';
import { UploadCloud, XCircle, FileIcon as FilePdf, Image as FileImage, Loader2, X, Files } from 'lucide-react';
import { Button } from './ui/button';

interface FileDropzoneProps {
  onUpload: (file: File) => void;
  onBulkUpload?: (files: File[]) => void;
  isUploading: boolean;
  mode?: 'single' | 'bulk';
}

const MAX_BULK_FILES = 20;

export const FileDropzone: React.FC<FileDropzoneProps> = ({
  onUpload,
  onBulkUpload,
  isUploading,
  mode = 'single',
}) => {
  const [fileError, setFileError] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  // BUG-FIX: Prevent multiple submissions — once clicked, lock until parent navigates away
  const uploadSubmitted = useRef(false);

  const onDrop = useCallback((acceptedFiles: File[], rejectedFiles: FileRejection[]) => {
    setFileError(null);
    
    if (rejectedFiles.length > 0) {
      const error = rejectedFiles[0].errors[0];
      if (error.code === 'file-too-large') {
        setFileError('File exceeds the 20MB limit.');
      } else if (error.code === 'file-invalid-type') {
        setFileError('Invalid file type. Please upload a PDF, JPG, or PNG.');
      } else if (error.code === 'too-many-files') {
        setFileError(`Max ${MAX_BULK_FILES} files per batch.`);
      } else {
        setFileError(error.message);
      }
      // In bulk mode, still keep accepted files even if some were rejected
      if (mode === 'bulk' && acceptedFiles.length > 0) {
        setSelectedFiles((prev) => {
          const combined = [...prev, ...acceptedFiles];
          return combined.slice(0, MAX_BULK_FILES);
        });
      }
      return;
    }

    if (mode === 'bulk') {
      setSelectedFiles((prev) => {
        const combined = [...prev, ...acceptedFiles];
        if (combined.length > MAX_BULK_FILES) {
          setFileError(`Max ${MAX_BULK_FILES} files. ${combined.length - MAX_BULK_FILES} file(s) dropped.`);
          return combined.slice(0, MAX_BULK_FILES);
        }
        return combined;
      });
    } else {
      if (acceptedFiles.length > 0) {
        setSelectedFile(acceptedFiles[0]);
      }
    }
  }, [mode]);

  const { getRootProps, getInputProps, isDragActive, open } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'image/jpeg': ['.jpeg', '.jpg'],
      'image/png': ['.png']
    },
    maxSize: 20 * 1024 * 1024,
    multiple: mode === 'bulk',
    maxFiles: mode === 'bulk' ? MAX_BULK_FILES : 1,
    disabled: isUploading,
    noClick: true, // we handle click via the Browse Files button
  });

  const handleUploadSubmit = () => {
    // BUG-FIX: Guard against double-click / React re-render re-trigger
    if (mode === 'bulk') {
      if (selectedFiles.length > 0 && !uploadSubmitted.current && !isUploading && onBulkUpload) {
        uploadSubmitted.current = true;
        onBulkUpload(selectedFiles);
      }
    } else {
      if (selectedFile && !uploadSubmitted.current && !isUploading) {
        uploadSubmitted.current = true;
        onUpload(selectedFile);
      }
    }
  };

  const handleClear = () => {
    setSelectedFile(null);
    setSelectedFiles([]);
    setFileError(null);
    uploadSubmitted.current = false;
  };

  const removeFile = (index: number) => {
    setSelectedFiles((prev) => prev.filter((_, i) => i !== index));
    setFileError(null);
  };

  const totalSize = mode === 'bulk'
    ? selectedFiles.reduce((sum, f) => sum + f.size, 0)
    : selectedFile?.size || 0;

  const isPDF = selectedFile?.type === 'application/pdf';

  const hasFiles = mode === 'bulk' ? selectedFiles.length > 0 : !!selectedFile;

  return (
    <div className="w-full">
      {!hasFiles ? (
        <div
          {...getRootProps()}
          className={`relative border-2 rounded-2xl p-10 text-center transition-colors duration-200 flex flex-col items-center justify-center min-h-[320px] shadow-sm
            ${isDragActive ? 'border-blue-400 bg-blue-50 border-solid' : 'border-ink-300 bg-ink-50 border-dashed'}
            ${fileError ? 'border-red-400 bg-red-50' : ''}
          `}
        >
          <input {...getInputProps()} />
          {mode === 'bulk' ? (
            <Files className={`h-12 w-12 mb-5 transition-colors ${isDragActive ? 'text-blue-500' : 'text-ink-400'} ${fileError ? 'text-red-400' : ''}`} />
          ) : (
            <UploadCloud className={`h-12 w-12 mb-5 transition-colors ${isDragActive ? 'text-blue-500' : 'text-ink-400'} ${fileError ? 'text-red-400' : ''}`} />
          )}
          
          <h3 className="text-xl font-medium text-ink-700 tracking-tight">
            {isDragActive
              ? 'Release to upload'
              : mode === 'bulk'
                ? 'Drop up to 20 invoices here'
                : 'Drop your invoice here'}
          </h3>
          <p className="text-sm text-ink-500 mt-1 font-medium">
            PDF, JPG, PNG up to 20MB{mode === 'bulk' ? ' each' : ''}
          </p>
          
          {!isDragActive && (
            <div className="flex items-center w-48 mt-6 mb-6">
              <div className="flex-1 border-t border-ink-300"></div>
              <span className="px-3 text-xs font-bold uppercase text-ink-400 tracking-wider">OR</span>
              <div className="flex-1 border-t border-ink-300"></div>
            </div>
          )}

          {!isDragActive && (
            <Button 
               variant="outline" 
               type="button" 
               onClick={open} 
               className="bg-white hover:bg-ink-50 text-ink-700 border-ink-300 shadow-sm font-semibold px-6"
            >
               Browse Files
            </Button>
          )}
          
          {fileError && (
            <div className="absolute bottom-4 flex items-center text-red-600 bg-red-100 px-4 py-2 flex-row rounded-lg border border-red-200 shadow-sm animate-in zoom-in fade-in">
              <XCircle className="h-4 w-4 mr-2 shrink-0" />
              <span className="text-xs font-bold">{fileError}</span>
            </div>
          )}
        </div>
      ) : mode === 'bulk' ? (
        /* ── Bulk mode: file list ── */
        <div className="border border-ink-200 rounded-2xl bg-white shadow-sm flex flex-col relative overflow-hidden">
          
          {/* Uploading Top progress strip animated */}
          {isUploading && (
             <div className="absolute top-0 left-0 right-0 h-1.5 bg-ink-100 overflow-hidden z-10">
                <div className="h-full bg-blue-500 w-[50%] animate-[slide_1.5s_ease-in-out_infinite] rounded-full"></div>
             </div>
          )}

          {/* Header */}
          <div className="px-6 pt-6 pb-4 border-b border-ink-100">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2.5 bg-blue-50 rounded-xl text-blue-600">
                  <Files className="w-5 h-5" />
                </div>
                <div>
                  <h4 className="font-bold text-ink-900 text-base tracking-tight">
                    {selectedFiles.length} file{selectedFiles.length !== 1 ? 's' : ''} selected
                  </h4>
                  <p className="text-xs font-semibold text-ink-400 mt-0.5">
                    {(totalSize / 1024 / 1024).toFixed(2)} MB total
                  </p>
                </div>
              </div>
              {!isUploading && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleClear}
                  className="text-ink-400 hover:text-ink-700 text-xs font-bold"
                >
                  Clear All
                </Button>
              )}
            </div>
          </div>

          {/* File list */}
          <div className="max-h-[280px] overflow-y-auto divide-y divide-ink-50">
            {selectedFiles.map((file, idx) => {
              const filePDF = file.type === 'application/pdf';
              return (
                <div
                  key={`${file.name}-${idx}`}
                  className="flex items-center justify-between px-6 py-3 hover:bg-ink-50/50 transition-colors group animate-in fade-in duration-200"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <div className={`p-1.5 rounded-lg ${filePDF ? 'bg-red-50 text-red-500' : 'bg-blue-50 text-blue-500'}`}>
                      {filePDF ? <FilePdf className="h-4 w-4" /> : <FileImage className="h-4 w-4" />}
                    </div>
                    <span className="text-sm font-semibold text-ink-800 truncate max-w-[200px] sm:max-w-sm" title={file.name}>
                      {file.name}
                    </span>
                  </div>
                  <div className="flex items-center gap-3 shrink-0">
                    <span className="text-xs font-semibold text-ink-400">
                      {(file.size / 1024 / 1024).toFixed(2)} MB
                    </span>
                    {!isUploading && (
                      <button
                        onClick={() => removeFile(idx)}
                        className="p-1 rounded-md text-ink-300 hover:text-red-500 hover:bg-red-50 transition-colors opacity-0 group-hover:opacity-100"
                      >
                        <X className="h-3.5 w-3.5" />
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Add more + upload button */}
          <div className="flex flex-col sm:flex-row gap-3 p-6 pt-4 border-t border-ink-100">
            {!isUploading && selectedFiles.length < MAX_BULK_FILES && (
              <Button
                variant="ghost"
                className="flex-1 text-ink-500 hover:text-ink-900 hover:bg-ink-100 font-bold"
                onClick={open}
              >
                + Add More Files
              </Button>
            )}
            <Button
              className="flex-1 bg-blue-600 hover:bg-blue-700 text-white shadow-md font-bold"
              onClick={handleUploadSubmit}
              disabled={isUploading || uploadSubmitted.current || selectedFiles.length === 0}
            >
              {isUploading ? (
                <span className="flex items-center gap-2">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Uploading {selectedFiles.length} Files...
                </span>
              ) : (
                `Upload ${selectedFiles.length} File${selectedFiles.length !== 1 ? 's' : ''}`
              )}
            </Button>
          </div>

          {fileError && (
            <div className="mx-6 mb-4 flex items-center text-amber-700 bg-amber-50 px-4 py-2 rounded-lg border border-amber-200 shadow-sm">
              <XCircle className="h-4 w-4 mr-2 shrink-0" />
              <span className="text-xs font-bold">{fileError}</span>
            </div>
          )}
        </div>
      ) : (
        /* ── Single mode: original file preview ── */
        <div className="border border-ink-200 rounded-2xl p-8 bg-white shadow-sm flex flex-col min-h-[320px] relative overflow-hidden">
          
          {/* Uploading Top progress strip animated */}
          {isUploading && (
             <div className="absolute top-0 left-0 right-0 h-1.5 bg-ink-100 overflow-hidden">
                <div className="h-full bg-blue-500 w-[50%] animate-[slide_1.5s_ease-in-out_infinite] rounded-full"></div>
             </div>
          )}

          <div className="flex-1 flex flex-col items-center justify-center fade-in animate-in duration-300 mt-2">
            <div className={`p-5 rounded-full mb-5 ring-4 ${isPDF ? 'bg-red-50 text-red-500 ring-red-50/50' : 'bg-blue-50 text-blue-500 ring-blue-50/50'}`}>
              {isPDF ? <FilePdf className="h-10 w-10" /> : <FileImage className="h-10 w-10" />}
            </div>
            <h4 className="font-bold text-ink-900 text-lg max-w-sm truncate text-center mb-1 tracking-tight" title={selectedFile!.name}>
              {selectedFile!.name}
            </h4>
            <p className="text-sm font-semibold text-ink-400">
              {(selectedFile!.size / 1024 / 1024).toFixed(2)} MB
            </p>

            {isUploading && (
               <div className="flex items-center justify-center gap-2 mt-6 animate-pulse">
                  <Loader2 className="h-5 w-5 text-blue-600 animate-spin" />
                  <span className="text-sm font-bold text-blue-700 tracking-tight">Uploading & Processing...</span>
               </div>
            )}
          </div>
          
          <div className="flex flex-col sm:flex-row gap-3 mt-8 pt-6 border-t border-ink-100">
            <Button 
              variant="ghost"
              className="flex-1 text-ink-500 hover:text-ink-900 hover:bg-ink-100 font-bold" 
              onClick={handleClear}
              disabled={isUploading}
            >
              Change File
            </Button>
            <Button 
              className="flex-1 bg-blue-600 hover:bg-blue-700 text-white shadow-md font-bold" 
              onClick={handleUploadSubmit}
              disabled={isUploading || uploadSubmitted.current}
            >
              Upload & Process
            </Button>
          </div>
        </div>
      )}
      
      <style>{`
        @keyframes slide {
          0% { transform: translateX(-100%); }
          100% { transform: translateX(200%); }
        }
      `}</style>
    </div>
  );
};