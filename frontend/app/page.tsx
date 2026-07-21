"use client";

import React, { useState, useEffect, useRef } from "react";
import LoginPage from '@/components/LoginPage';

// --- Types ---
interface FeedbackItem {
  _id?: string;
  feedback_text: string;
  user: string;
  channel: string;
  rating: number;
  timestamp: string;
  category: string;
  sentiment: string;
  churn?: any; 
  quote: string;
  recommendation: string;
}

interface ThemeStat {
  theme_name: string;
  mention_count: number;
  representative_quote: string;
  ai_recommendation: string;
}

interface DashboardMetrics {
  raw_feedback: number;
  unique_customer_issues: number;
  duplicates_removed: number;
  noise_reduction_percent: number;
  positive_reviews: number;
  neutral_reviews: number;
  negative_reviews: number;
  high_churn_customers: number;
  themes: ThemeStat[];
}

// --- Dynamic Risk Velocity Types ---
type AggregationType = "hourly" | "daily" | "weekly";

interface VelocityPoint {
  timeLabel: string;
  count: number;
  isPeak: boolean;
  topCategories: string[];
  topQuotes: string[];
}

// --- Dataset Metadata Type ---
interface DatasetRecord {
  filename: string;
  file_size_kb: number;
  uploaded_at: string;
  rows_processed: number;
  status: string;
  format: string;
}

export default function Dashboard() {
  // --- STATE HOOKS ---
  const [user, setUser] = useState<{ name: string; email: string } | null>(null);
  const [activeTab, setActiveTab] = useState<"dashboard" | "risk-analytics" | "datasets">("dashboard");
  
  // Dashboard states
  const [feedstock, setFeedstock] = useState<FeedbackItem[]>([]);
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [selectedTheme, setSelectedTheme] = useState<string | null>(null);
  const [showOnlyChurn, setShowOnlyChurn] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Risk Velocity states
  const [aggregation, setAggregation] = useState<AggregationType>("daily");
  const [velocityPoints, setVelocityPoints] = useState<VelocityPoint[]>([]);
  const [isLoadingVelocity, setIsLoadingVelocity] = useState(false);
  const [selectedPoint, setSelectedPoint] = useState<VelocityPoint | null>(null);

  // Datasets states
  const [datasets, setDatasets] = useState<DatasetRecord[]>([]);
  const [isLoadingDatasets, setIsLoadingDatasets] = useState(false);

  useEffect(() => {
    const savedUser = localStorage.getItem('voc_user');
    const token = localStorage.getItem('voc_token');
    if (savedUser && token) {
      try {
        setUser(JSON.parse(savedUser));
      } catch (e) {
        localStorage.removeItem('voc_user');
      }
    }
  }, []);

  const handleLogout = () => {
    localStorage.removeItem('voc_token');
    localStorage.removeItem('voc_user');
    setUser(null);
  };

  const fetchDashboardData = async () => {
    try {
      const feedbackRes = await fetch("http://127.0.0.1:8000/api/feedback");
      if (feedbackRes.ok) {
        const feedbackData = await feedbackRes.json();
        setFeedstock(feedbackData || []);
      }

      const metricsRes = await fetch("http://127.0.0.1:8000/api/dashboard-metrics");
      if (metricsRes.ok) {
        const metricsData = await metricsRes.json();
        setMetrics(metricsData);
        
        if (metricsData.themes && metricsData.themes.length > 0 && !selectedTheme) {
          setSelectedTheme(metricsData.themes[0].theme_name);
        }
      }
    } catch (error) {
      console.error("Failed calculating telemetry matrix:", error);
    }
  };

  const fetchDatasets = async () => {
    setIsLoadingDatasets(true);
    try {
      const res = await fetch("http://127.0.0.1:8000/api/datasets");
      if (res.ok) {
        const data = await res.json();
        setDatasets(data || []);
      }
    } catch (error) {
      console.error("Failed fetching dataset history:", error);
    } finally {
      setIsLoadingDatasets(false);
    }
  };

  useEffect(() => {
    if (!user) return;
    fetchDashboardData();
  }, [user]);

  // Dynamic Risk Velocity Fetch
  useEffect(() => {
    if (!user || activeTab !== "risk-analytics") return;

    const fetchVelocityData = async () => {
      setIsLoadingVelocity(true);
      try {
        const res = await fetch(`http://127.0.0.1:8000/api/risk-velocity?aggregation=${aggregation}`);
        if (res.ok) {
          const data = await res.json();
          setVelocityPoints(data || []);
        }
      } catch (error) {
        console.error("Failed fetching velocity stream:", error);
      } finally {
        setIsLoadingVelocity(false);
      }
    };

    fetchVelocityData();
  }, [user, aggregation, activeTab]);

  // Dataset Tab Fetch
  useEffect(() => {
    if (!user || activeTab !== "datasets") return;
    fetchDatasets();
  }, [user, activeTab]);

  if (!user) {
    return <LoginPage onLoginSuccess={(loggedInUser) => setUser(loggedInUser)} />;
  }

  const handleFileChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    const formData = new FormData();
    formData.append("file", file);

    setIsUploading(true);
    try {
      const response = await fetch("http://127.0.0.1:8000/api/upload", {
        method: "POST",
        body: formData,
      });

      if (response.ok) {
        alert("🎉 Feedback dataset ingested and processed successfully!");
        fetchDashboardData();
        if (activeTab === "datasets") fetchDatasets();
      } else {
        const errData = await response.json().catch(() => ({}));
        alert(`❌ Ingestion Rejected: ${errData.detail || "Server processing error"}`);
      }
    } catch (error) {
      alert("❌ Critical transmission error contacting processing engine.");
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleDeleteDataset = async (filename: string) => {
    if (!confirm(`Are you sure you want to remove ${filename} from dataset history?`)) return;

    try {
      const res = await fetch(`http://127.0.0.1:8000/api/datasets/${encodeURIComponent(filename)}`, {
        method: "DELETE",
      });
      if (res.ok) {
        setDatasets(prev => prev.filter(d => d.filename !== filename));
      }
    } catch (error) {
      console.error("Failed deleting dataset:", error);
    }
  };

  const isHighChurn = (item: any): boolean => {
    if (!item || typeof item !== "object") return false;

    for (const key in item) {
      const lowerKey = key.toLowerCase();
      if (lowerKey.includes("churn") || lowerKey.includes("risk") || lowerKey.includes("switch")) {
        const val = String(item[key]).toLowerCase().trim();
        if (["high risk", "churn", "true", "yes", "1", "high", "risk"].includes(val)) {
          return true;
        }
      }
    }

    const isNegative = String(item.sentiment).toLowerCase() === "negative" || Number(item.rating) <= 2;
    if (isNegative && item.feedback_text) {
      const txt = String(item.feedback_text).toLowerCase();
      const churnKeywords = [
        "switch", "uninstall", "delete", "cancel", "stop using", 
        "moving to", "switched", "close account", "worst app", 
        "never again", "useless", "fraud", "scam", "sue", "legal"
      ];
      return churnKeywords.some(keyword => txt.includes(keyword));
    }

    return false;
  };

  const displayedFeed = showOnlyChurn 
    ? feedstock.filter(item => isHighChurn(item)) 
    : feedstock;

  const churnCustomersList = feedstock.filter(item => isHighChurn(item));
  const activeThemeData = metrics?.themes?.find(t => t.theme_name === selectedTheme);

  const renderStars = (rating: number) => {
    return "★".repeat(rating) + "☆".repeat(5 - rating);
  };

  const maxVelocityCount = Math.max(...velocityPoints.map(p => p.count), 1);

  return (
    <div className="min-h-screen bg-[#0b0c10] text-gray-400 font-sans p-6 text-xs selection:bg-blue-900 selection:text-blue-100">
      
      {/* HIDDEN INGEST ELEMENT */}
      <input 
        type="file" 
        ref={fileInputRef} 
        onChange={handleFileChange} 
        accept=".csv,.xlsx,.xls" 
        className="hidden" 
      />

      {/* HEADER */}
      <header className="flex justify-between items-center mb-6 border-b border-gray-800/60 pb-4">
        <div className="flex items-center gap-6">
          <div>
            <div className="flex items-center gap-3">
              <div className="w-7 h-7 bg-red-600 rounded flex items-center justify-center font-bold text-white text-sm">Z</div>
              <h1 className="text-xl font-bold text-white tracking-wide">Zomato VoC Copilot</h1>
              <span className="text-[9px] bg-red-950/40 text-red-500 px-2 py-0.5 rounded border border-red-900/50 uppercase tracking-widest font-bold">
                AI Analytics Live
              </span>
            </div>
            <p className="text-gray-500 text-xs mt-1">Automated voice-of-the-customer logistics optimization pipeline.</p>
          </div>

          {/* TABBED NAVIGATION MENU */}
          <nav className="flex items-center gap-1 bg-[#12141d] p-1 rounded-lg border border-gray-800/80 font-mono text-[11px]">
            <button
              onClick={() => setActiveTab("dashboard")}
              className={`px-3 py-1.5 rounded transition-all ${
                activeTab === "dashboard"
                  ? "bg-red-600 text-white font-bold"
                  : "text-gray-400 hover:text-white hover:bg-gray-800/50"
              }`}
            >
              📊 Live Feed
            </button>
            <button
              onClick={() => setActiveTab("risk-analytics")}
              className={`px-3 py-1.5 rounded transition-all ${
                activeTab === "risk-analytics"
                  ? "bg-red-600 text-white font-bold"
                  : "text-gray-400 hover:text-white hover:bg-gray-800/50"
              }`}
            >
              ⚡ Risk Velocity
            </button>
            <button
              onClick={() => setActiveTab("datasets")}
              className={`px-3 py-1.5 rounded transition-all ${
                activeTab === "datasets"
                  ? "bg-red-600 text-white font-bold"
                  : "text-gray-400 hover:text-white hover:bg-gray-800/50"
              }`}
            >
              📁 Datasets
            </button>
          </nav>
        </div>
        
        {/* RIGHT SIDE HEADER ACTIONS */}
        <div className="flex items-center gap-3">
          <div className="hidden sm:flex flex-col text-right pr-2 border-r border-gray-800/80">
            <span className="text-xs font-semibold text-gray-200">{user?.name || "Operator"}</span>
            <span className="text-[10px] text-gray-500 font-mono">{user?.email}</span>
          </div>

          <button 
            disabled={isUploading}
            className="bg-white text-black font-semibold px-4 py-2 rounded hover:bg-gray-200 transition-colors flex items-center gap-2 text-xs disabled:opacity-50"
            onClick={() => fileInputRef.current?.click()}
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12"></path></svg>
            {isUploading ? "Processing Engine..." : "Import Feed"}
          </button>

          <button 
            onClick={handleLogout}
            className="bg-[#12141d] hover:bg-red-950/40 text-gray-400 hover:text-red-400 border border-gray-800 hover:border-red-900/50 font-semibold px-3 py-2 rounded transition-all flex items-center gap-1.5 text-xs"
            title="Sign Out"
          >
            <svg className="w-3.5 h-3.5 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
            </svg>
            <span>Logout</span>
          </button>
        </div>
      </header>

      {/* --- TAB 1: MAIN DASHBOARD --- */}
      {activeTab === "dashboard" && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* SIDEBAR FEED */}
          <div className="lg:col-span-4 bg-[#12141d] border border-gray-800/80 rounded-xl flex flex-col h-[calc(100vh-120px)]">
            <div className="p-4 border-b border-gray-800/60 flex justify-between items-center bg-[#151722] rounded-t-xl">
              <div className="flex items-center gap-2">
                <div className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse"></div>
                <h2 className="text-[10px] font-bold text-gray-400 tracking-widest uppercase">Ingest Feed</h2>
              </div>
              <div className="flex items-center gap-3">
                <label className="text-[10px] flex items-center gap-1.5 cursor-pointer text-gray-500 hover:text-gray-300 transition-colors">
                  <input 
                    type="checkbox" 
                    checked={showOnlyChurn}
                    onChange={(e) => setShowOnlyChurn(e.target.checked)}
                    className="accent-red-500"
                  />
                  Churn Only
                </label>
                <span className="bg-blue-900/20 text-blue-400 border border-blue-900/50 text-[10px] px-2 py-0.5 rounded-full font-mono">
                  {displayedFeed.length} records shown
                </span>
              </div>
            </div>
            
            <div className="flex-1 overflow-y-auto p-4 space-y-4 custom-scrollbar">
              {displayedFeed.map((item, idx) => (
                <div key={idx} className="bg-[#0b0c10] border border-gray-800/60 p-4 rounded-lg hover:border-gray-600 transition-colors">
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-[9px] bg-blue-950/40 text-blue-400 border border-blue-900/50 px-2 py-0.5 rounded uppercase font-bold tracking-wider">
                      {item.channel || "Feedback"}
                    </span>
                    <span className="text-yellow-500 text-[11px] tracking-widest">{renderStars(item.rating)}</span>
                  </div>
                  <p className="text-xs text-gray-300 italic mb-3">"{item.feedback_text}"</p>
                  
                  <div className="flex justify-between items-center text-[10px] text-gray-500 font-mono pt-2 border-t border-gray-800/40">
                    <span className="truncate max-w-[100px]">User: {item.user || "Anonymous"}</span>
                    <div className="flex gap-2 items-center">
                      {isHighChurn(item) && (
                        <span className="bg-red-950/80 border border-red-500/60 text-red-400 font-bold px-1.5 py-0.5 rounded text-[8px] uppercase tracking-wider animate-pulse">
                          🚨 Churn Risk
                        </span>
                      )}
                      <span className={`font-bold px-1.5 py-0.5 rounded text-[9px] ${
                        String(item.sentiment).toLowerCase() === 'positive' ? 'text-green-400 bg-green-950/30' : 
                        String(item.sentiment).toLowerCase() === 'negative' ? 'text-red-400 bg-red-950/30' : 'text-yellow-400 bg-yellow-950/30'
                      }`}>
                        {item.sentiment}
                      </span>
                    </div>
                  </div>
                </div>
              ))}
              
              {displayedFeed.length === 0 && (
                <div className="text-center text-gray-600 italic py-8">
                  No churn signatures matched in the feed panel.
                </div>
              )}
            </div>
          </div>

          {/* METRICS & METADATA COLUMN */}
          <div className="lg:col-span-8 flex flex-col gap-4 overflow-y-auto h-[calc(100vh-120px)] pr-1 custom-scrollbar">
            
            {/* TOP 4 KPIs */}
            <div className="grid grid-cols-4 gap-4">
              <div className="bg-[#12141d] border border-gray-800/80 p-4 rounded-xl">
                <h3 className="text-[9px] text-gray-500 font-bold tracking-widest uppercase mb-1">Raw Ingest Volume</h3>
                <p className="text-2xl font-black text-gray-200">{metrics?.raw_feedback || 0}</p>
              </div>
              <div className="bg-[#12141d] border border-gray-800/80 p-4 rounded-xl">
                <h3 className="text-[9px] text-gray-500 font-bold tracking-widest uppercase mb-1">Unique Issues</h3>
                <p className="text-2xl font-black text-green-500">{metrics?.unique_customer_issues || 0}</p>
              </div>
              <div className="bg-[#12141d] border border-gray-800/80 p-4 rounded-xl">
                <h3 className="text-[9px] text-gray-500 font-bold tracking-widest uppercase mb-1">Duplicates Cut</h3>
                <p className="text-2xl font-black text-blue-500">-{metrics?.duplicates_removed || 0}</p>
              </div>
              <div className="bg-[#12141d] border border-gray-800/80 p-4 rounded-xl">
                <h3 className="text-[9px] text-gray-500 font-bold tracking-widest uppercase mb-1">Noise Reduction</h3>
                <p className="text-2xl font-black text-cyan-400">{metrics?.noise_reduction_percent || 0}%</p>
              </div>
            </div>

            {/* CHURN DETAILS & SENTIMENT DISTRIBUTIONS */}
            <div className="grid grid-cols-1 md:grid-cols-12 gap-4">
              <div 
                onClick={() => setShowOnlyChurn(!showOnlyChurn)}
                className={`border p-4 rounded-xl md:col-span-5 flex flex-col justify-between cursor-pointer transition-all ${
                  showOnlyChurn 
                    ? 'bg-red-900/40 border-red-500 shadow-[0_0_12px_rgba(239,68,68,0.3)]' 
                    : 'bg-[#1a0f14] border-red-900/30 hover:border-red-700'
                }`}
              >
                <div>
                  <div className="flex justify-between items-center mb-2">
                    <h3 className="text-[10px] text-red-400 font-bold tracking-widest uppercase flex items-center gap-1.5">
                      ⚠️ Churn Risks Flagged
                    </h3>
                    <p className="text-xl font-black text-red-500 font-mono">
                      {churnCustomersList.length}
                    </p>
                  </div>
                  
                  <div className="max-h-[110px] overflow-y-auto space-y-2 custom-scrollbar text-[10px] font-mono text-gray-300">
                    {churnCustomersList.map((c: any, i) => {
                      const feedbackText = c.feedback_text || c.text || c.complaint || c.issue || c.review || "No specific details provided.";
                      const username = c.user || c.customer || c.customer_id || c.name || `User #${i + 1}`;
                      const userRating = c.rating !== undefined ? `(${c.rating}★)` : "";

                      return (
                        <div key={i} className="bg-red-950/30 p-2 rounded border border-red-900/40 leading-relaxed">
                          <span className="text-red-400 font-bold">👤 {username} {userRating}:</span>
                          <p className="mt-1 text-gray-200 italic">"{feedbackText}"</p>
                        </div>
                      );
                    })}
                    
                    {churnCustomersList.length === 0 && (
                      <p className="text-gray-600 italic">No switching signatures detected dynamically.</p>
                    )}
                  </div>
                </div>
                <p className="text-[9px] text-red-500/70 font-mono mt-3 uppercase tracking-wider">
                  {showOnlyChurn ? "👉 Click to show all feedback" : "👉 Click card to filter main feed"}
                </p>
              </div>

              <div className="bg-[#12141d] border border-gray-800/80 p-4 rounded-xl md:col-span-7">
                <h3 className="text-[9px] text-gray-500 font-bold tracking-widest uppercase mb-3">Sentiment Breakdown</h3>
                <div className="grid grid-cols-3 gap-2 font-mono text-[11px]">
                  <div className="bg-green-950/20 border border-green-900/30 rounded p-2 flex items-center gap-1.5">
                    <div className="w-1.5 h-1.5 rounded-full bg-green-500"></div>
                    <span className="text-green-500">{metrics?.positive_reviews || 0} Pos</span>
                  </div>
                  <div className="bg-yellow-950/20 border border-yellow-900/30 rounded p-2 flex items-center gap-1.5">
                    <div className="w-1.5 h-1.5 rounded-full bg-yellow-500"></div>
                    <span className="text-yellow-500">{metrics?.neutral_reviews || 0} Neu</span>
                  </div>
                  <div className="bg-red-950/20 border border-red-900/30 rounded p-2 flex items-center gap-1.5">
                    <div className="w-1.5 h-1.5 rounded-full bg-red-500"></div>
                    <span className="text-red-500">{metrics?.negative_reviews || 0} Neg</span>
                  </div>
                </div>
              </div>
            </div>

            <div className="bg-[#12141d] border border-gray-800/80 p-4 rounded-xl">
              <h3 className="text-[10px] text-gray-400 font-bold tracking-widest uppercase mb-3 flex items-center gap-2">
                <div className="w-1 h-3 bg-red-500 rounded-full"></div>
                Discovered Theme Statistics
              </h3>
              <div className="max-h-[220px] overflow-y-auto pr-2 space-y-3 custom-scrollbar">
                {metrics?.themes?.map((theme, idx) => {
                  const percentage = metrics.unique_customer_issues > 0 
                    ? Math.round((theme.mention_count / metrics.unique_customer_issues) * 100) 
                    : 0;
                  const isSelected = selectedTheme === theme.theme_name;

                  return (
                    <div 
                      key={idx} 
                      className={`cursor-pointer group ${isSelected ? 'opacity-100' : 'opacity-50 hover:opacity-100'} transition-opacity`}
                      onClick={() => setSelectedTheme(theme.theme_name)}
                    >
                      <div className="flex justify-between text-[11px] mb-1 font-mono">
                        <span className={isSelected ? 'text-white font-bold' : 'text-gray-400'}>{theme.theme_name}</span>
                        <span className="text-gray-500">{theme.mention_count} hits ({percentage}%)</span>
                      </div>
                      <div className="w-full bg-[#0b0c10] rounded-full h-1">
                        <div 
                          className={`h-1 rounded-full transition-all duration-300 ${isSelected ? 'bg-red-500' : 'bg-gray-600 group-hover:bg-red-400'}`} 
                          style={{ width: `${percentage}%` }}
                        ></div>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>

            <div className="bg-[#12141d] border border-gray-800/80 p-4 rounded-xl">
              <h3 className="text-[10px] text-gray-400 font-bold tracking-widest uppercase mb-3 flex items-center gap-1.5">
                <span>⚡</span> AI-Synthesized Insights Pipeline
              </h3>
              
              {activeThemeData ? (
                <div className="bg-[#151722] border border-gray-800/60 rounded-lg p-4">
                  <div className="flex justify-between items-center mb-3 pb-2 border-b border-gray-800/60">
                    <h4 className="text-sm font-bold text-white">{activeThemeData.theme_name}</h4>
                    <span className="bg-blue-900/20 text-blue-400 border border-blue-900/40 text-[10px] px-2 py-0.5 rounded-full font-mono">
                      {activeThemeData.mention_count} signals
                    </span>
                  </div>
                  
                  <div className="mb-3">
                    <h5 className="text-[9px] text-yellow-500 font-bold tracking-widest uppercase mb-1">
                      💬 Core Vector Quote
                    </h5>
                    <p className="text-gray-300 italic text-[11px] border-l border-yellow-500/40 pl-3">
                      "{activeThemeData.representative_quote}"
                    </p>
                  </div>

                  <div>
                    <h5 className="text-[9px] text-red-400 font-bold tracking-widest uppercase mb-1">
                      🚀 Strategic Product Fix
                    </h5>
                    <p className="text-gray-300 text-[11px] bg-[#0b0c10] p-3 rounded border border-gray-800/40 leading-relaxed">
                      {activeThemeData.ai_recommendation}
                    </p>
                  </div>
                </div>
              ) : (
                <div className="text-center text-gray-600 italic py-4">Select a theme block above to render insights payload.</div>
              )}
            </div>

          </div>
        </div>
      )}

      {/* --- TAB 2: DYNAMIC RISK VELOCITY ANALYTICS --- */}
      {activeTab === "risk-analytics" && (
        <div className="flex flex-col gap-6">
          <div className="bg-[#12141d] border border-gray-800/80 p-4 rounded-xl flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
            <div>
              <h2 className="text-base font-bold text-white flex items-center gap-2">
                <span>📈</span> Churn Trajectory & Spike Velocity
              </h2>
              <p className="text-gray-500 text-xs">Analyze churn acceleration across custom time windows.</p>
            </div>

            <div className="flex items-center gap-2 bg-[#0b0c10] p-1 rounded-lg border border-gray-800">
              <span className="text-[10px] text-gray-500 px-2 font-mono uppercase font-bold">Aggregation:</span>
              {(["hourly", "daily", "weekly"] as AggregationType[]).map((type) => (
                <button
                  key={type}
                  onClick={() => {
                    setAggregation(type);
                    setSelectedPoint(null);
                  }}
                  className={`px-3 py-1 rounded text-xs font-mono capitalize transition-all ${
                    aggregation === type
                      ? "bg-red-600 text-white font-bold"
                      : "text-gray-400 hover:text-white"
                  }`}
                >
                  {type}
                </button>
              ))}
            </div>
          </div>

          <div className="bg-[#12141d] border border-gray-800/80 p-6 rounded-xl flex flex-col gap-6">
            <h3 className="text-[10px] text-gray-400 font-bold tracking-widest uppercase flex items-center gap-2">
              <div className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse"></div>
              {aggregation.toUpperCase()} Risk Velocity Stream
            </h3>

            {isLoadingVelocity ? (
              <div className="h-48 flex items-center justify-center text-gray-500 font-mono text-xs animate-pulse">
                ⏳ Processing Risk Velocity Data...
              </div>
            ) : velocityPoints.length === 0 ? (
              <div className="h-48 flex items-center justify-center text-gray-600 italic">
                No timeline records available for aggregation level: {aggregation}
              </div>
            ) : (
              <div className="grid grid-cols-4 md:grid-cols-5 gap-4 items-end h-48 pt-6 border-b border-gray-800/80 pb-4">
                {velocityPoints.map((point, idx) => {
                  const heightPercentage = Math.round((point.count / maxVelocityCount) * 100);
                  const isSelected = selectedPoint?.timeLabel === point.timeLabel;

                  return (
                    <div
                      key={idx}
                      onClick={() => setSelectedPoint(point)}
                      className={`flex flex-col items-center justify-end h-full cursor-pointer group transition-all`}
                    >
                      {point.isPeak && (
                        <span className="text-[8px] bg-red-950 text-red-400 border border-red-600 font-bold px-1.5 py-0.5 rounded uppercase tracking-wider mb-2 animate-bounce">
                          🔥 Peak Spike
                        </span>
                      )}

                      <span className="text-[10px] font-mono mb-1 text-gray-400 group-hover:text-white">
                        {point.count}
                      </span>

                      <div
                        className={`w-full max-w-[48px] rounded-t transition-all duration-300 ${
                          point.isPeak
                            ? "bg-red-500 group-hover:bg-red-400 shadow-[0_0_12px_rgba(239,68,68,0.5)]"
                            : isSelected
                            ? "bg-blue-500"
                            : "bg-gray-800 group-hover:bg-gray-700"
                        }`}
                        style={{ height: `${Math.max(heightPercentage, 8)}%` }}
                      ></div>

                      <span className="text-[10px] font-mono mt-2 text-gray-500 group-hover:text-gray-300">
                        {point.timeLabel}
                      </span>
                    </div>
                  );
                })}
              </div>
            )}

            <p className="text-[10px] text-gray-500 text-center italic">
              👉 Click on any bar or peak marker to inspect top categories and quotes associated with that time window.
            </p>
          </div>

          {selectedPoint ? (
            <div className="bg-[#12141d] border border-red-900/60 p-6 rounded-xl animate-fadeIn">
              <div className="flex justify-between items-center mb-4 pb-3 border-b border-gray-800/80">
                <div className="flex items-center gap-3">
                  <span className="text-lg">🎯</span>
                  <div>
                    <h3 className="text-sm font-bold text-white">
                      Time Window Spike Details: <span className="text-red-400 font-mono">{selectedPoint.timeLabel}</span>
                    </h3>
                    <p className="text-gray-500 text-xs">
                      Recorded Volume: <span className="text-white font-mono font-bold">{selectedPoint.count} incidents</span>
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => setSelectedPoint(null)}
                  className="text-gray-500 hover:text-white text-xs px-2 py-1 rounded bg-gray-800"
                >
                  ✕ Close
                </button>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <h4 className="text-[10px] text-red-400 font-bold tracking-widest uppercase mb-2">
                    🏷️ Primary Spike Drivers
                  </h4>
                  <div className="flex flex-wrap gap-2">
                    {selectedPoint.topCategories.map((cat, i) => (
                      <span key={i} className="bg-red-950/60 text-red-300 border border-red-900/80 px-2.5 py-1 rounded font-mono text-[11px]">
                        {cat}
                      </span>
                    ))}
                  </div>
                </div>

                <div>
                  <h4 className="text-[10px] text-yellow-500 font-bold tracking-widest uppercase mb-2">
                    💬 Representative Customer Vectors
                  </h4>
                  <div className="space-y-2">
                    {selectedPoint.topQuotes.map((q, i) => (
                      <div key={i} className="bg-[#0b0c10] p-2.5 rounded border border-gray-800 text-[11px] text-gray-300 italic">
                        "{q}"
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="bg-[#12141d] border border-gray-800/80 p-8 rounded-xl text-center text-gray-600 italic">
              Select a velocity window bar above to view spike markers & root-cause annotations.
            </div>
          )}
        </div>
      )}

      {/* --- TAB 3: DATASET MANAGEMENT & UPLOAD HISTORY --- */}
      {activeTab === "datasets" && (
        <div className="flex flex-col gap-6">
          
          {/* HEADER SUMMARY CARDS */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-[#12141d] border border-gray-800/80 p-5 rounded-xl">
              <h3 className="text-[9px] text-gray-500 font-bold tracking-widest uppercase mb-1">Total Uploaded Datasets</h3>
              <p className="text-2xl font-black text-white font-mono">{datasets.length}</p>
            </div>
            <div className="bg-[#12141d] border border-gray-800/80 p-5 rounded-xl">
              <h3 className="text-[9px] text-gray-500 font-bold tracking-widest uppercase mb-1">Active Database Records</h3>
              <p className="text-2xl font-black text-green-500 font-mono">{feedstock.length}</p>
            </div>
            <div className="bg-[#12141d] border border-gray-800/80 p-5 rounded-xl">
              <h3 className="text-[9px] text-gray-500 font-bold tracking-widest uppercase mb-1">Pipeline Health</h3>
              <p className="text-2xl font-black text-cyan-400 font-mono">100% Operational</p>
            </div>
          </div>

          {/* INGEST UPLOAD ZONE CARD */}
          <div 
            onClick={() => fileInputRef.current?.click()}
            className="bg-[#12141d] border-2 border-dashed border-gray-800 hover:border-red-600/60 p-8 rounded-xl text-center cursor-pointer transition-all group"
          >
            <div className="w-12 h-12 bg-red-950/40 border border-red-900/60 rounded-full flex items-center justify-center mx-auto mb-3 text-red-500 text-xl group-hover:scale-110 transition-transform">
              📁
            </div>
            <h3 className="text-sm font-bold text-white mb-1">Click to Upload New Dataset</h3>
            <p className="text-xs text-gray-500">Supports CSV, XLSX, and XLS formats up to 50MB</p>
          </div>

          {/* DATASETS HISTORY TABLE */}
          <div className="bg-[#12141d] border border-gray-800/80 rounded-xl overflow-hidden">
            <div className="p-4 border-b border-gray-800/60 flex justify-between items-center bg-[#151722]">
              <h3 className="text-xs font-bold text-white flex items-center gap-2">
                <span className="text-red-500">📄</span> Ingest History & Dataset Logs
              </h3>
              <button 
                onClick={fetchDatasets}
                className="text-[10px] font-mono bg-gray-800 hover:bg-gray-700 text-gray-300 px-2.5 py-1 rounded transition-colors"
              >
                🔄 Refresh Logs
              </button>
            </div>

            {isLoadingDatasets ? (
              <div className="p-8 text-center text-gray-500 font-mono text-xs animate-pulse">
                ⏳ Reading Dataset Logs...
              </div>
            ) : datasets.length === 0 ? (
              <div className="p-8 text-center text-gray-600 italic">
                No dataset history logged yet. Upload a CSV/Excel file to start tracking metadata.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left font-mono text-[11px]">
                  <thead className="bg-[#0b0c10] text-gray-500 border-b border-gray-800/80 uppercase tracking-wider text-[9px]">
                    <tr>
                      <th className="p-3">Filename</th>
                      <th className="p-3">Format</th>
                      <th className="p-3">Size</th>
                      <th className="p-3">Rows Processed</th>
                      <th className="p-3">Uploaded At</th>
                      <th className="p-3">Status</th>
                      <th className="p-3 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-800/40 text-gray-300">
                    {datasets.map((ds, idx) => (
                      <tr key={idx} className="hover:bg-[#151722] transition-colors">
                        <td className="p-3 font-semibold text-white flex items-center gap-2">
                          <span>📊</span> {ds.filename}
                        </td>
                        <td className="p-3">
                          <span className="bg-gray-800 text-gray-300 px-2 py-0.5 rounded text-[9px] font-bold">
                            {ds.format || "CSV"}
                          </span>
                        </td>
                        <td className="p-3">{ds.file_size_kb ? `${ds.file_size_kb} KB` : "N/A"}</td>
                        <td className="p-3 text-green-400 font-bold">{ds.rows_processed || 0}</td>
                        <td className="p-3 text-gray-400">
                          {ds.uploaded_at ? new Date(ds.uploaded_at).toLocaleString() : "Just now"}
                        </td>
                        <td className="p-3">
                          <span className="bg-green-950/60 border border-green-800/60 text-green-400 text-[9px] px-2 py-0.5 rounded uppercase font-bold">
                            {ds.status || "Processed"}
                          </span>
                        </td>
                        <td className="p-3 text-right">
                          <button
                            onClick={() => handleDeleteDataset(ds.filename)}
                            className="text-red-400 hover:text-red-300 hover:bg-red-950/50 p-1 rounded transition-colors"
                            title="Delete Dataset Record"
                          >
                            🗑️ Delete
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

        </div>
      )}

      {/* GLOBAL HIGH DENSITY SCROLLBAR ENGINE */}
      <style dangerouslySetInnerHTML={{__html: `
        .custom-scrollbar::-webkit-scrollbar {
          width: 3px;
          height: 3px;
        }
        .custom-scrollbar::-webkit-scrollbar-track {
          background: #0b0c10;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb {
          background: #232735;
          border-radius: 9px;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb:hover {
          background: #3b4257;
        }
      `}} />
    </div>
  );
}