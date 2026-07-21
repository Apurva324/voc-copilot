import React, { useState, useEffect } from 'react';

interface ThemeItem {
  theme_name: string;
  mention_count: number;
  representative_quote: string;
  ai_recommendation: string;
}

interface DashboardMetricsPayload {
  raw_feedback: number;
  unique_customer_issues: number;
  duplicates_removed: number;
  noise_reduction_percent: number;
  positive_reviews: number;
  neutral_reviews: number;
  negative_reviews: number;
  high_churn_customers: number;
  themes: ThemeItem[];
  recommendations: string[];
}

export default function ImpactBoard() {
  const [selectedTheme, setSelectedTheme] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [metrics, setMetrics] = useState<DashboardMetricsPayload>({
    raw_feedback: 0,
    unique_customer_issues: 0,
    duplicates_removed: 0,
    noise_reduction_percent: 0,
    positive_reviews: 0,
    neutral_reviews: 0,
    negative_reviews: 0,
    high_churn_customers: 0,
    themes: [],
    recommendations: []
  });

  const fetchDashboardMetrics = async () => {
    try {
      const response = await fetch("http://localhost:8000/api/dashboard-metrics"); 
      if (response.ok) {
        const data = await response.json();
        setMetrics(data);
        if (data.themes && data.themes.length > 0 && !selectedTheme) {
          setSelectedTheme(data.themes[0].theme_name);
        }
      }
    } catch (err) {
      console.error("Failed fetching live metrics from server cluster:", err);
    }
  };

  useEffect(() => {
    fetchDashboardMetrics();
  }, []);

  const handleDashboardFeedImport = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (!files || files.length === 0) return;
    
    const file = files[0];
    setIsUploading(true);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await fetch("http://localhost:8000/api/upload", {
        method: "POST",
        body: formData,
      });

      if (response.ok) {
        await fetchDashboardMetrics();
      } else {
        alert('Pipeline error detected: Failed processing data feed.');
      }
    } catch (error) {
      console.error("❌ Communication failure between API targets:", error);
    } finally {
      setIsUploading(false);
      event.target.value = "";
    }
  };

  const activeThemeInsight = metrics.themes?.find(t => t.theme_name === selectedTheme) || 
                             (metrics.themes?.length > 0 ? metrics.themes[0] : null);

  return (
    <div className="min-h-screen bg-[#090a0f] text-gray-100 p-8 font-sans">
      
      <header className="flex justify-between items-center mb-8 border-b border-gray-800 pb-6">
        <div>
          <div className="flex items-center gap-2">
            <div className="bg-[#e21b3c] p-2 rounded text-white font-bold text-xl">Z</div>
            <h1 className="text-xl font-bold tracking-tight">Zomato VoC Copilot <span className="text-xs bg-red-950/50 text-[#e21b3c] border border-red-900/40 px-2 py-0.5 rounded ml-2 font-mono">ZOMATO ONLY ENGINE</span></h1>
          </div>
          <p className="text-sm text-gray-400 mt-1">Automated voice-of-the-customer food-delivery logistics optimization pipeline.</p>
        </div>

        <div>
          <input
            type="file"
            id="csv-feed-uploader"
            accept=".csv"
            style={{ display: "none" }}
            onChange={handleDashboardFeedImport}
            disabled={isUploading}
          />

          <button 
            onClick={() => document.getElementById("csv-feed-uploader")?.click()}
            className="bg-white hover:bg-gray-100 text-black px-4 py-2 rounded font-medium flex items-center gap-2 transition-all disabled:opacity-50"
          >
            {isUploading ? (
              <>
                <span className="animate-spin inline-block w-4 h-4 border-2 border-black border-t-transparent rounded-full"></span>
                Processing...
              </>
            ) : (
              <>
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12"/></svg>
                Import Feed
              </>
            )}
          </button>
        </div>
      </header>

      <div className="grid grid-cols-3 gap-6">
        
        {/* LEFT COLUMN PANEL: THEME MONITOR METER LIST */}
        <div className="bg-[#0f111a] border border-gray-800 rounded-xl p-5 col-span-1">
          <div className="flex justify-between items-center mb-4 border-b border-gray-900 pb-2">
            <h2 className="text-sm font-semibold tracking-wider text-gray-400 uppercase">Theme Statistics</h2>
            <span className="text-xs font-mono bg-[#1a1d2e] text-blue-400 px-2 py-0.5 rounded border border-blue-900/30">
              {metrics.themes?.length || 0} clusters
            </span>
          </div>
          
          <div className="space-y-4 max-h-[70vh] overflow-y-auto pr-2">
            {!metrics.themes || metrics.themes.length === 0 ? (
              <p className="text-sm text-gray-500 italic text-center py-8">No active themes captured yet. Import a file stream grid to begin.</p>
            ) : (
              metrics.themes.map((theme, idx) => {
                const pct = metrics.unique_customer_issues > 0 
                  ? Math.round((theme.mention_count / metrics.unique_customer_issues) * 100) 
                  : 0;
                return (
                  <div key={idx} className="space-y-1.5 cursor-pointer group" onClick={() => setSelectedTheme(theme.theme_name)}>
                    <div className="flex justify-between text-xs font-mono">
                      <span className={selectedTheme === theme.theme_name ? "text-white font-bold" : "text-gray-400 group-hover:text-gray-300"}>
                        {theme.theme_name}
                      </span>
                      <span className="text-gray-500">{theme.mention_count} ({pct}%)</span>
                    </div>
                    <div className="w-full bg-gray-950 h-1.5 rounded-full overflow-hidden border border-gray-900">
                      <div className={`h-full transition-all duration-500 ${selectedTheme === theme.theme_name ? "bg-[#e21b3c]" : "bg-red-800/40"}`} style={{ width: `${pct}%` }}></div>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* RIGHT COMPONENTS: METRICS & INSIGHT DISPLAY SYSTEM */}
        <div className="col-span-2 space-y-6">
          
          {/* HIGH LEVEL PRODUCTION METRICS CARD GRID */}
          <div className="grid grid-cols-4 gap-4">
            <div className="bg-[#0f111a] border border-gray-800 rounded-xl p-4">
              <p className="text-[10px] uppercase tracking-wider font-semibold text-gray-500">Raw Feedback Received</p>
              <p className="text-3xl font-black font-mono mt-1 text-white">{metrics.raw_feedback}</p>
            </div>
            <div className="bg-[#0f111a] border border-gray-800 rounded-xl p-4">
              <p className="text-[10px] uppercase tracking-wider font-semibold text-gray-500">Unique Customer Issues</p>
              <p className="text-3xl font-black font-mono mt-1 text-green-400">{metrics.unique_customer_issues}</p>
            </div>
            <div className="bg-[#0f111a] border border-gray-800 rounded-xl p-4">
              <p className="text-[10px] uppercase tracking-wider font-semibold text-gray-500">Duplicates Removed</p>
              <p className="text-3xl font-black font-mono mt-1 text-blue-400">-{metrics.duplicates_removed}</p>
            </div>
            <div className="bg-[#0f111a] border border-gray-800 rounded-xl p-4">
              <p className="text-[10px] uppercase tracking-wider font-semibold text-gray-500">Noise Reduction (%)</p>
              <p className="text-3xl font-black font-mono mt-1 text-cyan-400">{metrics.noise_reduction_percent}%</p>
            </div>
          </div>

          {/* DYNAMIC RISK INDICATOR AND SENTIMENT BADGE COUNTERS */}
          <div className="grid grid-cols-2 gap-4">
            <div className="bg-red-950/20 border border-red-900/40 rounded-xl p-5 flex justify-between items-center">
              <div>
                <p className="text-xs font-bold text-gray-400 uppercase tracking-wider">⚠️ High Churn Customers</p>
                <p className="text-[11px] text-gray-500 font-mono mt-0.5">Switching risk patterns</p>
              </div>
              <p className="text-3xl font-black font-mono text-red-400">{metrics.high_churn_customers}</p>
            </div>

            <div className="bg-[#0f111a] border border-gray-800 rounded-xl p-4">
              <p className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-2">Sentiment Distribution Breakdown</p>
              <div className="flex justify-around items-center text-xs font-mono pt-1">
                <span className="bg-green-950/30 border border-green-900/20 px-2 py-1 rounded text-green-400">🟢 {metrics.positive_reviews} Pos</span>
                <span className="bg-yellow-950/30 border border-yellow-900/20 px-2 py-1 rounded text-yellow-400">🟡 {metrics.neutral_reviews} Neu</span>
                <span className="bg-red-950/30 border border-red-900/20 px-2 py-1 rounded text-red-400">🔴 {metrics.negative_reviews} Neg</span>
              </div>
            </div>
          </div>

          {/* LOWER ANALYSIS BLOCK VIEW: AI RECOMMENDATION TILES */}
          <div className="bg-[#0f111a] border border-gray-800 rounded-xl p-6">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-sm font-semibold tracking-wider text-gray-400 uppercase flex items-center gap-2">
                <svg className="w-4 h-4 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>
                AI-Synthesized Product Insights
              </h3>
              <span className="text-[10px] uppercase font-bold tracking-widest bg-red-950 text-[#e21b3c] border border-red-900/50 px-3 py-1 rounded font-mono">⚡ Copilot</span>
            </div>

            {activeThemeInsight ? (
              <div className="bg-[#141724] border border-gray-800 rounded-lg p-5 space-y-4">
                <div className="flex justify-between items-center border-b border-gray-800/80 pb-3">
                  <h4 className="text-base font-bold text-white">{activeThemeInsight.theme_name}</h4>
                  <span className="bg-blue-950/60 border border-blue-900/40 text-blue-400 px-3 py-0.5 rounded text-xs font-mono">
                    {activeThemeInsight.mention_count} mentions
                  </span>
                </div>

                <div className="space-y-1.5">
                  <p className="text-[10px] text-amber-400 font-mono font-bold uppercase tracking-wider">💬 Representative Customer Quote</p>
                  <p className="text-xs text-gray-300 italic bg-gray-950/40 px-3 py-2 border-l-2 border-amber-500 rounded">
                    "{activeThemeInsight.representative_quote}"
                  </p>
                </div>

                <div className="space-y-1.5 pt-1">
                  <p className="text-[10px] text-red-500 font-mono font-bold uppercase tracking-wider">🚀 Automated Recommendation</p>
                  <p className="text-sm text-gray-200 leading-relaxed">
                    {activeThemeInsight.ai_recommendation}
                  </p>
                </div>
              </div>
            ) : (
              <p className="text-sm text-gray-500 italic text-center py-6">Select a category token node item from the monitoring list above to view predictive solutions.</p>
            )}
          </div>

        </div>

      </div>

    </div>
  );
}