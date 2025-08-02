'use client';
import React, { useState, useEffect, useCallback } from 'react';
import {
    TbLayoutDashboard, TbTarget, TbArrowsRandom, TbMessageCircle, TbChartInfographic, TbHeartRateMonitor,
    TbSun, TbMoon, TbDeviceDesktopAnalytics, TbBrain, TbStatusChange, TbFilter, TbChevronDown,
    TbTrendingUp, TbTrendingDown, TbChartCandle, TbChartLine, TbRulerMeasure, TbListDetails, TbWaveSine, TbUsers
} from "react-icons/tb";

// ---------------------------------------------------------------- //
// ----------------------- CONFIG & UTILS ------------------------- //
// ---------------------------------------------------------------- //

// !! مهم: این آدرس را با آدرس نهایی بک‌اند خود در Railway یا هر هاست دیگری جایگزین کنید
const API_BASE_URL = 'https://aisignalpro-production.up.railway.app';

// Helper for dynamic class names based on sentiment
const sentimentColor = (sentiment, type = 'text') => {
    const sentimentStr = String(sentiment).toLowerCase();
    const map = {
        bullish: { text: 'text-green-400', bg: 'bg-green-500/10', border: 'border-green-500/50' },
        buy: { text: 'text-green-400', bg: 'bg-green-500/10', border: 'border-green-500/50' },
        up: { text: 'text-green-400', bg: 'bg-green-500/10', border: 'border-green-500/50' },
        bearish: { text: 'text-red-400', bg: 'bg-red-500/10', border: 'border-red-500/50' },
        sell: { text: 'text-red-400', bg: 'bg-red-500/10', border: 'border-red-500/50' },
        down: { text: 'text-red-400', bg: 'bg-red-500/10', border: 'border-red-500/50' },
        neutral: { text: 'text-yellow-400', bg: 'bg-yellow-500/10', border: 'border-yellow-500/50' },
        hold: { text: 'text-yellow-400', bg: 'bg-yellow-500/10', border: 'border-yellow-500/50' },
    };
    return map[sentimentStr]?.[type] || 'text-gray-400';
};

// Helper to format numbers nicely
const formatNumber = (num, digits = 2) => {
    if (typeof num !== 'number') return num;
    return num.toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits });
};


// ---------------------------------------------------------------- //
// --------------------- CORE UI COMPONENTS ----------------------- //
// ---------------------------------------------------------------- //

const Header = () => ( <header className="flex justify-between items-center p-4 border-b border-yellow-500/30 sticky top-0 bg-gray-900/70 backdrop-blur-xl z-20"> <div className="flex items-center gap-3"> <TbBrain className="text-yellow-400 text-3xl drop-shadow-[0_0_8px_rgba(250,204,21,0.5)]" /> <h1 className="text-xl md:text-2xl font-bold bg-gradient-to-r from-yellow-400 to-orange-400 bg-clip-text text-transparent">Ai Signal Pro</h1> </div> <div><button className="p-2 rounded-full bg-white/10 border border-yellow-500/30 text-yellow-500 text-xl"><TbSun /></button></div> </header> );
const Footer = () => ( <footer className="fixed bottom-0 left-0 right-0 p-2 bg-gray-900/80 backdrop-blur-xl border-t border-yellow-500/30 z-20"> <div className="flex justify-around text-gray-400"> <button className="flex flex-col items-center text-yellow-500 font-bold text-xs"><TbLayoutDashboard className="text-xl mb-1"/>Dashboard</button> <button className="flex flex-col items-center hover:text-yellow-500 text-xs"><TbTarget className="text-xl mb-1"/>Signals</button> <button className="flex flex-col items-center hover:text-yellow-500 text-xs"><TbArrowsRandom className="text-xl mb-1"/>Trades</button> <button className="flex flex-col items-center hover:text-yellow-500 text-xs"><TbChartInfographic className="text-xl mb-1"/>Analysis</button> </div> </footer> );
const AnalysisCard = ({ icon, title, children }) => ( <div className="bg-black/20 rounded-lg p-4 border border-gray-700/50 h-full"> <h4 className="text-md font-bold text-yellow-400 flex items-center gap-2 mb-3 border-b border-gray-700/50 pb-2"> {icon} {title} </h4> <div className="space-y-3 text-sm"> {children} </div> </div> );


// ---------------------------------------------------------------- //
// ----------------- LIVE DASHBOARD WIDGETS ----------------------- //
// ---------------------------------------------------------------- //

const SystemStatus = () => {
    const [services, setServices] = useState([]);
    useEffect(() => {
        fetch(`${API_BASE_URL}/api/status/`)
            .then(res => res.json())
            .then(data => setServices(data))
            .catch(err => console.error("Failed to fetch system status:", err));
    }, []);

    const StatusIndicator = ({ status }) => (<span className={`w-2.5 h-2.5 rounded-full ${status === 'online' ? 'bg-green-400 animate-pulse' : 'bg-red-500'}`}></span>);
    
    return (
        <section className="bg-gray-800/30 backdrop-blur-lg rounded-xl p-4 border border-yellow-500/20">
             <h3 className="text-yellow-500 font-bold text-lg mb-3 flex items-center gap-2"><TbStatusChange/> System Status</h3>
             {services.length > 0 ? (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-center">
                    {services.map((ex) => (
                        <div key={ex.name} className="bg-black/20 p-2 rounded-md flex items-center justify-center gap-2" title={`Ping: ${ex.ping}`}>
                            <StatusIndicator status={ex.status} />
                            <p className="text-sm font-semibold text-gray-300">{ex.name}</p>
                        </div>
                    ))}
                </div>
             ) : (<p className="text-gray-400 text-center text-xs">Loading status...</p>)}
        </section>
    );
};

const MarketOverview = () => {
    const [marketData, setMarketData] = useState({});
    useEffect(() => {
        fetch(`${API_BASE_URL}/api/market-overview/`)
            .then(res => res.json())
            .then(data => setMarketData(data))
            .catch(err => console.error("Failed to fetch market overview:", err));
    }, []);

    const dataPoints = [
        { label: 'Market Cap', value: marketData.market_cap ? `$${(marketData.market_cap / 1e12).toFixed(2)}T` : '...' },
        { label: 'Volume 24h', value: marketData.volume_24h ? `$${(marketData.volume_24h / 1e9).toFixed(2)}B` : '...' },
        { label: 'BTC Dominance', value: marketData.btc_dominance ? `${marketData.btc_dominance.toFixed(1)}%` : '...' },
        { label: 'Fear & Greed', value: marketData.fear_and_greed || '...' },
    ];
    
    return (
        <section className="bg-gray-800/30 backdrop-blur-lg rounded-xl p-4 border border-yellow-500/20">
            <h3 className="text-yellow-500 font-bold text-lg mb-3 flex items-center gap-2"><TbChartInfographic/> Market Overview</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {dataPoints.map(item => (
                    <div key={item.label}>
                        <p className="text-xs text-gray-400">{item.label}</p>
                        <p className="font-bold text-lg text-white">{item.value}</p>
                    </div>
                ))}
            </div>
        </section>
    );
};

// ... PriceTicker, Signals, ActiveTrades ...
// (برای اختصار، فرض می‌شود کد این کامپوننت‌ها مشابه قبل است ولی با fetch به API متصل شده‌اند)


// ---------------------------------------------------------------- //
// ----------------- THE NEW LIVE ANALYSIS ENGINE ----------------- //
// ---------------------------------------------------------------- //

const DetailedAnalysisEngine = () => {
    const [symbol, setSymbol] = useState('BTC'); // Default to 'BTC' without '/USDT'
    const [timeframe, setTimeframe] = useState('1h');
    const [loading, setLoading] = useState(true);
    const [analysisData, setAnalysisData] = useState(null); // Will hold the full API response
    const [error, setError] = useState(null);

    const fetchAnalysis = useCallback(() => {
        setLoading(true);
        setError(null);
        setAnalysisData(null);
        fetch(`${API_BASE_URL}/api/get-composite-signal/?symbol=${symbol}`)
            .then(res => {
                if (!res.ok) throw new Error(`Network response was not ok: ${res.statusText}`);
                return res.json();
            })
            .then(data => {
                if (data.status === 'NO_DATA' || data.status === 'ERROR') {
                   throw new Error(data.message || 'No data available for this symbol.');
                }
                // We need the detailed analysis, which is inside `full_analysis_details`
                setAnalysisData(data.full_analysis_details);
            })
            .catch(err => {
                console.error("Failed to fetch detailed analysis:", err);
                setError(err.message);
            })
            .finally(() => {
                setLoading(false);
            });
    }, [symbol]);

    useEffect(() => {
        fetchAnalysis();
    }, [fetchAnalysis]);

    // This is the data for the currently selected timeframe
    const currentTfData = analysisData ? analysisData[timeframe] : null;

    return (
        <section className="bg-gray-800/30 backdrop-blur-lg rounded-xl p-4 border border-yellow-500/20 col-span-1 lg:col-span-3">
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-4 gap-4">
                <h3 className="text-yellow-500 font-bold text-lg flex items-center gap-2 shrink-0"><TbHeartRateMonitor/> Detailed Analysis Engine</h3>
                <div className="flex items-center gap-2 bg-black/20 p-2 rounded-lg border border-gray-700/50 w-full md:w-auto">
                    <select value={symbol} onChange={(e) => setSymbol(e.target.value)} className="bg-transparent text-white font-bold focus:outline-none">
                        <option value="BTC">BTC</option> <option value="ETH">ETH</option>
                        <option value="XRP">XRP</option> <option value="SOL">SOL</option>
                        <option value="DOGE">DOGE</option>
                    </select>
                    <select value={timeframe} onChange={(e) => setTimeframe(e.target.value)} className="bg-transparent text-gray-300 focus:outline-none">
                        <option value="5m">5m</option><option value="15m">15m</option>
                        <option value="1h">1h</option><option value="4h">4h</option>
                    </select>
                    <button onClick={fetchAnalysis} className="bg-yellow-500/20 text-yellow-400 text-xs font-bold py-1 px-3 rounded hover:bg-yellow-500/30">Analyze</button>
                </div>
            </div>

            {loading ? <p className="text-center text-gray-400 py-20">Analyzing {symbol}...</p> :
             error ? <p className="text-center text-red-500 py-20">Error: {error}</p> :
             !currentTfData ? <p className="text-center text-gray-500 py-20">No analysis data available for {timeframe}. Select another timeframe or symbol.</p> :
            (
                <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
                    {/* Column 1 & 2: Main Analysis */}
                    <div className="xl:col-span-2 space-y-4">
                         {/* Trend Analysis Card */}
                        <AnalysisCard icon={<TbTrendingUp/>} title="Trend Analysis">
                             <div className="grid grid-cols-2 md:grid-cols-3 gap-2 text-center">
                                <div className={`p-2 rounded-md border ${sentimentColor(currentTfData.trend?.signal, 'border')} ${sentimentColor(currentTfData.trend?.signal, 'bg')}`}>
                                    <p className="text-xs text-gray-400">Trend Signal</p>
                                    <p className={`font-bold ${sentimentColor(currentTfData.trend?.signal)}`}>{currentTfData.trend?.signal || 'N/A'}</p>
                                </div>
                                <div className="p-2 rounded-md bg-black/20">
                                    <p className="text-xs text-gray-400">ADX</p>
                                    <p className="font-bold text-white">{formatNumber(currentTfData.trend?.adx)}</p>
                                </div>
                                 <div className="p-2 rounded-md bg-black/20">
                                    <p className="text-xs text-gray-400">Slope Angle</p>
                                    <p className="font-bold text-white">{formatNumber(currentTfData.trend?.slope)}°</p>
                                </div>
                            </div>
                        </AnalysisCard>
                        
                        {/* Indicator Analysis Card */}
                        <AnalysisCard icon={<TbChartLine/>} title="Key Indicators">
                            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                                {Object.entries(currentTfData.indicators || {}).slice(0, 8).map(([key, value]) => (
                                    <div key={key} className="bg-gray-900/50 p-2 rounded-md">
                                        <p className="text-xs text-gray-400 uppercase">{key}</p>
                                        <p className="font-mono font-bold text-white">{formatNumber(value, 4)}</p>
                                    </div>
                                ))}
                            </div>
                        </AnalysisCard>
                        
                        {/* Divergence Card */}
                        <AnalysisCard icon={<TbWaveSine/>} title="Divergence Detection">
                            {Object.values(currentTfData.divergence || {}).flat().length > 0 ? (
                                <div className="space-y-2">
                                    {Object.entries(currentTfData.divergence).map(([indicator, divs]) => (
                                        divs.length > 0 && <div key={indicator}>
                                            <h5 className="font-bold text-yellow-500 capitalize">{indicator} Divergences:</h5>
                                            {divs.map((div, i) => (
                                                <p key={i} className={sentimentColor(div.type)}>{div.type.replace('_', ' ')}</p>
                                            ))}
                                        </div>
                                    ))}
                                </div>
                            ) : <p className="text-gray-400">No significant divergence detected.</p>}
                        </AnalysisCard>
                    </div>

                    {/* Column 3: Patterns & Structure */}
                    <div className="space-y-4">
                        {/* Candlestick Patterns Card */}
                        <AnalysisCard icon={<TbChartCandle/>} title="Candlestick Patterns">
                             {currentTfData.patterns?.length > 0 ? (
                                <div className="space-y-2">
                                    {currentTfData.patterns.map((p, i) => (
                                        <div key={i} className={`p-2 rounded-md border ${sentimentColor(p, 'border')} ${sentimentColor(p, 'bg')}`}>
                                            <p className={`font-semibold ${sentimentColor(p)}`}>{p}</p>
                                        </div>
                                    ))}
                                </div>
                            ) : <p className="text-gray-400">No high-quality patterns identified.</p>}
                        </AnalysisCard>

                        {/* Market Structure Card */}
                        <AnalysisCard icon={<TbRulerMeasure/>} title="Market Structure">
                            <div className="space-y-2">
                                <p><strong>Market Phase: </strong><span className="text-yellow-400">{currentTfData.market_structure?.market_phase}</span></p>
                                <p><strong>Predicted Next Leg: </strong><span className={sentimentColor(currentTfData.market_structure?.predicted_next_leg_direction)}>{currentTfData.market_structure?.predicted_next_leg_direction || 'N/A'}</span></p>
                                <p><strong>Pivots Found: </strong>{currentTfData.market_structure?.pivots?.length || 0}</p>
                                <p><strong>Anomalies: </strong>{currentTfData.market_structure?.anomalies?.length || 0}</p>
                            </div>
                        </AnalysisCard>
                    </div>
                </div>
            )
            }
        </section>
    );
};

// ---------------------- MAIN HOME COMPONENT --------------------- //
export default function Home() {
    return (
        <div className="bg-black text-gray-200 min-h-screen">
            <div className="fixed top-0 left-0 w-full h-full bg-gradient-to-br from-gray-900 via-black to-gray-800 -z-10"/>
            <Header />
            <main className="p-4 grid grid-cols-1 lg:grid-cols-3 gap-6 pb-20">
                <div className="lg:col-span-3 space-y-6">
                    <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
                        <SystemStatus />
                        <MarketOverview />
                    </div>
                     <DetailedAnalysisEngine />
                </div>
            </main>
            <Footer />
        </div>
    )
}
