'use client';

import { useState, useRef, useEffect } from 'react';
import AudioUploader from '@/components/AudioUploader';
import AudioRecorder from '@/components/AudioRecorder';
import PaymentPlans from '@/components/PaymentPlans';
import IndustriesSidebar from '@/components/IndustriesSidebar';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  getPredictionCount, 
  incrementPredictionCount, 
  hasReachedFreeLimit, 
  getRemainingFreePredictions,
  getFormattedTimeUntilReset
} from '@/utils/predictionTracker';

export default function Home() {
  const [activeTab, setActiveTab] = useState('upload');
  const [isProcessing, setIsProcessing] = useState(false);
  const [caption, setCaption] = useState('');
  const [error, setError] = useState('');
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [showPaymentPlans, setShowPaymentPlans] = useState(false);
  const [predictionCount, setPredictionCount] = useState(0);
  const [remainingPredictions, setRemainingPredictions] = useState(5);
  const [timeUntilReset, setTimeUntilReset] = useState<string | null>(null);
  const [selectedIndustry, setSelectedIndustry] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement>(null);
  const resultsRef = useRef<HTMLDivElement>(null);
  const processingRef = useRef<HTMLDivElement>(null);
  const audioSectionRef = useRef<HTMLDivElement>(null);
  const [apiStatus, setApiStatus] = useState<string>('Loading...');

  // Initialize prediction count on component mount
  useEffect(() => {
    setPredictionCount(getPredictionCount());
    setRemainingPredictions(getRemainingFreePredictions());
    setTimeUntilReset(getFormattedTimeUntilReset());
    
    // Set up an interval to update the time until reset
    const intervalId = setInterval(() => {
      setTimeUntilReset(getFormattedTimeUntilReset());
      setRemainingPredictions(getRemainingFreePredictions());
    }, 60000); // Update every minute
    
    return () => clearInterval(intervalId);
  }, []);

  // Scroll to processing section when processing starts
  useEffect(() => {
    if (isProcessing && processingRef.current) {
      processingRef.current.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }, [isProcessing]);

  // Scroll to results when caption is available
  useEffect(() => {
    if (caption && resultsRef.current) {
      resultsRef.current.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }, [caption]);

  useEffect(() => {
    // Test the API endpoint
    fetch('/api')
      .then(res => res.json())
      .then(data => {
        setApiStatus(JSON.stringify(data, null, 2));
      })
      .catch(err => {
        setApiStatus('Error: ' + err.message);
      });
  }, []);

  const handleAudioProcessing = async (file: File) => {
    try {
      setIsProcessing(true);
      setError('');
      setCaption('');

      // Check if user has reached free limit
      if (hasReachedFreeLimit()) {
        setShowPaymentPlans(true);
        setIsProcessing(false);
        return;
      }

      const formData = new FormData();
      formData.append('audio_file', file);
      formData.append('industry', selectedIndustry || 'general');

      console.log('Sending request to API...');
      const response = await fetch('/api', {
        method: 'POST',
        body: formData,
      });

      console.log('Response status:', response.status);
      if (!response.ok) {
        const errorText = await response.text();
        console.error('Error response:', errorText);
        let errorMessage = 'Failed to process audio';
        try {
          const errorJson = JSON.parse(errorText);
          errorMessage = errorJson.error || errorMessage;
        } catch (e) {
          // If not JSON, use the raw error text
          errorMessage = errorText || errorMessage;
        }
        throw new Error(errorMessage);
      }

      const data = await response.json();
      console.log('Response data:', data);

      if (!data.caption) {
        throw new Error('No caption received from server');
      }

      // Increment prediction count
      const newCount = incrementPredictionCount();
      setPredictionCount(newCount);
      setRemainingPredictions(getRemainingFreePredictions());
      
      // Check if user has reached the free prediction limit after this prediction
      if (hasReachedFreeLimit()) {
        // Show payment plans after a short delay
        setTimeout(() => {
          setShowPaymentPlans(true);
        }, 2000);
      }

      setCaption(data.caption);
      setIsProcessing(false);
    } catch (err) {
      console.error('Error:', err);
      setError(err instanceof Error ? err.message : 'An error occurred');
      setIsProcessing(false);
    }
  };

  const handleSelectPlan = (plan: string) => {
    // Redirect to the appropriate Flutterwave payment link based on the plan
    let paymentUrl = '';
    
    switch (plan.toLowerCase()) {
      case 'starter':
        paymentUrl = 'https://flutterwave.com/pay/v9zx3y80bktn';
        break;
      case 'premium':
        paymentUrl = 'https://flutterwave.com/pay/ewaabagcbbre';
        break;
      case 'professional':
        paymentUrl = 'https://flutterwave.com/pay/bpbqtr7joi9c';
        break;
      default:
        console.error('Unknown plan selected:', plan);
        return;
    }
    
    // Close the payment plans modal
    setShowPaymentPlans(false);
    
    // Redirect to the payment page
    window.open(paymentUrl, '_blank');
    
    // In a real implementation, you would:
    // 1. Track the user's selection
    // 2. Handle the payment callback
    // 3. Update the user's subscription status
    // 4. Reset the prediction count or set a higher limit based on the plan
  };

  const handleSelectIndustry = (industryId: string) => {
    setSelectedIndustry(industryId);
    
    // Scroll to the audio section when an industry is selected
    if (audioSectionRef.current) {
      audioSectionRef.current.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  };

  return (
    <main className="min-h-screen bg-gradient-to-br from-indigo-900 via-purple-900 to-violet-900 py-12 px-4 sm:px-6 lg:px-8 relative overflow-hidden">
      {/* Animated background elements */}
      <div className="absolute inset-0 overflow-hidden">
        <div className="absolute -top-1/2 -left-1/2 w-full h-full bg-gradient-to-r from-indigo-500/20 to-purple-500/20 rounded-full blur-3xl transform rotate-45" />
        <div className="absolute -bottom-1/2 -right-1/2 w-full h-full bg-gradient-to-r from-violet-500/20 to-purple-500/20 rounded-full blur-3xl transform -rotate-45" />
      </div>

      <div className="max-w-6xl mx-auto relative z-10">
        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8 }}
          className="text-center mb-12"
        >
          <h1 className="text-5xl font-bold text-white mb-4 bg-clip-text text-transparent bg-gradient-to-r from-indigo-200 to-purple-200">
            Toun Audio Classifier
          </h1>
          <p className="text-xl text-indigo-100">
            Transform your audio into meaningful captions with AI
          </p>
          
          {/* Free predictions counter */}
          <div className="mt-4 inline-block bg-white/10 backdrop-blur-sm rounded-lg px-4 py-2">
            <p className="text-indigo-100">
              <span className="font-medium">{remainingPredictions}</span> free predictions remaining
              {timeUntilReset && remainingPredictions === 0 && (
                <span className="block text-sm mt-1">
                  Resets in: <span className="font-medium">{timeUntilReset}</span>
                </span>
              )}
            </p>
          </div>
        </motion.div>

        <div className="flex flex-col md:flex-row gap-6">
          {/* Industries Dropdown */}
          <div className="md:w-64 flex-shrink-0">
            <IndustriesSidebar 
              selectedIndustry={selectedIndustry} 
              onSelectIndustry={handleSelectIndustry} 
            />
          </div>

          {/* Main Content */}
          <motion.div 
            ref={audioSectionRef}
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.5, delay: 0.2 }}
            className="flex-grow bg-white/10 backdrop-blur-lg rounded-2xl shadow-2xl overflow-hidden border border-white/20"
          >
            <div className="p-6">
              <div className="flex space-x-4 mb-8">
                <motion.button
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                  onClick={() => setActiveTab('upload')}
                  className={`px-6 py-3 rounded-xl font-medium transition-all duration-200 ${
                    activeTab === 'upload'
                      ? 'bg-gradient-to-r from-indigo-500 to-purple-500 text-white shadow-lg'
                      : 'bg-white/10 text-indigo-100 hover:bg-white/20'
                  }`}
                >
                  Upload Audio
                </motion.button>
                <motion.button
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                  onClick={() => setActiveTab('record')}
                  className={`px-6 py-3 rounded-xl font-medium transition-all duration-200 ${
                    activeTab === 'record'
                      ? 'bg-gradient-to-r from-indigo-500 to-purple-500 text-white shadow-lg'
                      : 'bg-white/10 text-indigo-100 hover:bg-white/20'
                  }`}
                >
                  Record Audio
                </motion.button>
              </div>

              <AnimatePresence mode="wait">
                <motion.div
                  key={activeTab}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -20 }}
                  transition={{ duration: 0.3 }}
                >
                  {activeTab === 'upload' ? (
                    <AudioUploader onAudioProcessed={handleAudioProcessing} />
                  ) : (
                    <AudioRecorder onAudioProcessed={handleAudioProcessing} />
                  )}
                </motion.div>
              </AnimatePresence>

              {audioUrl && (
                <motion.div 
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="mt-8"
                >
                  <h3 className="text-lg font-medium text-indigo-100 mb-4">Preview</h3>
                  <audio
                    ref={audioRef}
                    src={audioUrl}
                    controls
                    className="w-full rounded-xl shadow-lg bg-white/10 backdrop-blur-sm"
                  />
                </motion.div>
              )}

              {isProcessing && (
                <motion.div 
                  ref={processingRef}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="mt-8 flex items-center justify-center"
                >
                  <div className="relative">
                    <div className="w-12 h-12 rounded-full border-4 border-indigo-500/20 border-t-indigo-500 animate-spin" />
                    <div className="absolute inset-0 flex items-center justify-center">
                      <div className="w-6 h-6 rounded-full bg-gradient-to-r from-indigo-500 to-purple-500 animate-pulse" />
                    </div>
                  </div>
                  <span className="ml-4 text-indigo-100">Processing audio...</span>
                </motion.div>
              )}

              {error && (
                <motion.div 
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="mt-8 p-4 bg-red-500/20 border border-red-500/30 rounded-xl backdrop-blur-sm"
                >
                  <p className="text-red-200">{error}</p>
                </motion.div>
              )}

              {caption && (
                <motion.div 
                  ref={resultsRef}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="mt-8"
                >
                  <h3 className="text-lg font-medium text-indigo-100 mb-4">Prediction:</h3>
                  <div className="p-6 bg-gradient-to-r from-indigo-500/20 to-purple-500/20 border border-white/20 rounded-xl backdrop-blur-sm">
                    <p className="text-indigo-100 leading-relaxed">{caption}</p>
                  </div>
                </motion.div>
              )}
            </div>
          </motion.div>
        </div>
      </div>
      
      {/* Payment Plans Modal */}
      <PaymentPlans 
        isOpen={showPaymentPlans} 
        onClose={() => setShowPaymentPlans(false)} 
        onSelectPlan={handleSelectPlan} 
      />
    </main>
  );
} 