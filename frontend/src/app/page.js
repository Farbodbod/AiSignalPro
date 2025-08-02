'use client';
import React, { useState, useEffect, useCallback } from 'react';
import { 
    TbLayoutDashboard, TbTarget, TbArrowsRandom, TbChartInfographic, TbBrain, 
    TbRefresh, TbChevronDown, TbChevronUp, TbClockHour4, TbDeviceDesktopAnalytics,
    TbArrowUpRight, TbArrowDownLeft, TbMinus
} from "react-icons/tb";

// =================================================================
//  Components
// =================================================================

const Header = ({ symbol, price, change }) => (
    <header className="flex justify-between items-center p-4 border-b border-yellow-500/30 sticky top-0 bg-gray-900/70 backdrop-blur-xl z-10">
        <div className="flex items-center gap-3">
            <TbBrain className="text-yellow-400 text-3xl drop-shadow-[0_0_8px_rgba(250,204,21,0.5)]" />
            <h1 className="text-xl md:text-2xl font-bold bg-gradient-to-r from-yellow-400 to-orange-400 bg-clip-text text-transparent drop-shadow-[0_0_5px_rgba(255,165,0,0.8)]">
                Ai Signal Pro
            </h1>
        </div>
        {price && (
            <div className="text-right">
                <p className="font-bold text-lg text-white">{symbol}/USDT</p>
                <p className={`font-mono text-sm ${change >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    ${price.toLocaleString('en-US')} ({change >= 0 ? '+' : ''}{change.toFixed(2)}%)
                </p>
            </div>
        )}
    </header>
);

const Footer = () => (
    <footer className="fixed bottom-0 left-0 right-0 p-2 bg-gray-900/80 backdrop-blur-xl border-t border-yellow-500/30 z-10">
        <div className="flex justify-around text-gray-400">
            <button className="flex flex-col items-center text-yellow-500 font-bold text-xs"><TbLayoutDashboard className="text-xl mb-1"/>Dashboard</button>
            <button className="flex flex-col items-center hover:text-yellow-500 text-xs"><TbTarget className="text-xl mb-1"/>Signals</button>
            <button className="flex flex-col items-center hover:text-yellow-500 text-xs"><TbArrowsRandom className="text-xl mb-1"/>Trades</button>
            <button className="flex flex-col items-center hover:text-yellow-500 text-xs"><TbChartInfographic className="text-xl mb-1"/>Analysis</button>
        </div>
    </footer>
);

const SystemStatus = () => {
    const [status, setStatus] = useState([]);
    useEffect(() => {
        const fetchStatus = async () => {
            try {
                const response = await fetch('https://aisignalpro-production.up.railway.app/api/status/');
                if (response.ok) setStatus(await response.json());
            } catch (e) { console.error("Failed to fetch system status"); }
        };
        fetchStatus();
    }, []);

    const StatusIndicator = ({ status }) => (<span className={`w-2 h-2 rounded-full ${status === 'online' ? 'bg-green-400 animate-pulse' : 'bg-red-500'}`}></span>);
    return (
        <section className="bg-gray-800/30 backdrop-blur-lg rounded-xl p-4 border border-yellow-500/20">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-center">
                {status.length > 0 ? status.map((ex) => (
                    <div key={ex.name} className="bg-black/20 p-2 rounded-md">
                        <div className="flex items-center justify-center gap-2">
                            <StatusIndicator status={ex.status} />
                            <p className="text-sm font-semibold text-gray-300">{ex.name}</p>
                        </div>
                    </div>
                )) : <p className="text-xs text-gray-500 col-span-4">Loading status...</p>}
            </div>
        </section>
    );
};

const MarketOverview = () => {
    const [overview, setOverview] = useState({});
    useEffect(() => {
        const fetchOverview = async () => {
            try {
                const response = await fetch('https://aisignalpro-production.up.railway.app/api/market-overview/');
                if(response.ok) setOverview(await response.json());
            } catch (e) { console.error("Failed to fetch market overview"); }
        };
        fetchOverview();
    }, []);
    return(
        <section className="bg-gray-800/30 backdrop-blur-lg rounded-xl p-4 border border-yellow-500/20">
             <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div><p className="text-xs text-gray-400">Market Cap</p><p className="font-bold text-lg text-white">{overview.market_cap ? `$${(overview.market_cap / 1e12).toFixed(2)}T` : '...'}</p></div>
                <div><p className="text-xs text-gray-400">Volume 24h</p><p className="font-bold text-lg text-white">{overview.volume_24h ? `$${(overview.volume_24h / 1e9).toFixed(2)}B` : '...'}</p></div>
                <div><p className="text-xs text-gray-400">BTC Dominance</p><p className="font-bold text-lg text-white">{overview.btc_dominance ? `${Number(overview.btc_dominance).toFixed(1)}%` : '...'}</p></div>
                <div><p className="text-xs text-gray-400">Fear & Greed</p><p className="font-bold text-lg text-white">{overview.fear_and_greed || '...'}</p></div>
            </div>
        </section>
    );
};

const PriceTicker = ({ onBtcPriceUpdate }) => {
    const [prices, setPrices] = useState([]);
    useEffect(() => {
        const fetchPrices = async () => {
            try {
                const response = await fetch('https://aisignalpro-production.up.railway.app/api/price-ticker/');
                if (response.ok) {
                    const data = await response.json();
                    if (Array.isArray(data)) {
                        setPrices(data);
                        const btc = data.find(p => p.symbol === 'BTC');
                        if (btc) {
                            onBtcPriceUpdate({ price: btc.price, change: btc.change_24h });
                        }
                    }
                }
            } catch (error) { console.error("Failed to fetch prices:", error); }
        };
        fetchPrices();
        const interval = setInterval(fetchPrices, 15000);
        return () => clearInterval(interval);
    }, [onBtcPriceUpdate]);

    return (
        <section className="bg-gray-800/30 backdrop-blur-lg rounded-xl p-4 border border-yellow-500/20">
            <h3 className="text-yellow-500 font-bold text-lg mb-3 flex items-center gap-2"><TbDeviceDesktopAnalytics/> Live Prices</h3>
            {prices.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                    {prices.map(p => (
                        <div key={p.symbol} className="flex justify-between items-center bg-black/20 p-2 rounded-md">
                            <div>
                                <p className="font-bold text-yellow-400">{p.symbol}/USDT</p>
                                <p className="text-xs text-gray-500 capitalize">{p.source}</p>
                            </div>
                            <div className="text-right">
                                <p className="font-semibold font-mono text-white">${p.price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: p.price < 100 ? 4 : 2 })}</p>
                                <p className={`text-sm font-bold ${p.change_24h >= 0 ? 'text-green-400' : 'text-red-400'}`}>{p.change_24h >= 0 ? '+' : ''}{Number(p.change_24h).toFixed(2)}%</p>
                            </div>
                        </div>
                    ))}
                </div>
            ) : (<p className="text-gray-500 text-center py-4">Loading prices...</p>)}
        </section>
    );
};

const AnalysisConclusion = ({ analysis }) => {
    let conclusion = { text: 'N/A', color: 'text-gray-400', Icon: TbMinus };
    if (!analysis) return null;
    
    const rsiDivs = analysis.divergence?.rsi || [];
    const macdDivs = analysis.divergence?.macd || [];
    if (rsiDivs.some(d => d.type.includes('bullish')) || macdDivs.some(d => d.type.includes('bullish'))) {
        conclusion = { text: 'Bullish Divergence', color: 'text-green-400', Icon: TbArrowUpRight };
    } else if (rsiDivs.some(d => d.type.includes('bearish')) || macdDivs.some(d => d.type.includes('bearish'))) {
        conclusion = { text: 'Bearish Divergence', color: 'text-red-400', Icon: TbArrowDownLeft };
    } else if (analysis.trend?.signal) {
        const signal = analysis.trend.signal.toLowerCase();
        if(signal.includes('uptrend')) conclusion = { text: 'Bullish Trend', color: 'text-green-400', Icon: TbArrowUpRight };
        else if (signal.includes('downtrend')) conclusion = { text: 'Bearish Trend', color: 'text-red-400', Icon: TbArrowDownLeft };
        else conclusion = { text: 'Neutral Trend', color: 'text-yellow-400', Icon: TbMinus };
    }

    return (
        <div className="bg-black/30 p-2 rounded-md mt-2 flex items-center justify-between">
            <span className="text-xs text-gray-400 font-bold">Conclusion:</span>
            <div className={`flex items-center gap-1 font-bold text-sm ${conclusion.color}`}>
                <conclusion.Icon />
                <span>{conclusion.text}</span>
            </div>
        </div>
    );
};

const AnalysisDetailCard = ({ title, data }) => {
    if (!data || Object.keys(data).length === 0) return null;
    const formatKey = (key) => key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    
    const renderValue = (key, value) => {
        let text = 'N/A';
        let color = 'text-white';
        if (value === null || value === undefined) return <span className={color}>{text}</span>;

        if (typeof value === 'boolean') { text = value ? 'Yes' : 'No'; color = value ? 'text-green-400' : 'text-red-400'; }
        else if (typeof value === 'number') { text = value.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 4}); }
        else if (Array.isArray(value)) { text = value.length > 0 ? value.join(', ') : 'None'; }
        else if (typeof value === 'object') {
            if (key.toLowerCase().includes('divergence')) {
                const divs = Object.entries(value).map(([ind, arr]) => Array.isArray(arr) && arr.length > 0 ? `${ind.toUpperCase()}: ${arr.map(d=>d.type).join(', ')}` : null).filter(Boolean);
                text = divs.length > 0 ? divs.join(' | ') : 'None Found';
            } else { text = JSON.stringify(value); }
        } else { text = value; }

        if (typeof text === 'string' && (text.toLowerCase().includes('up') || text.toLowerCase().includes('bullish'))) color = 'text-green-400';
        if (typeof text === 'string' && (text.toLowerCase().includes('down') || text.toLowerCase().includes('bearish'))) color = 'text-red-400';
        
        return <span className={`font-mono ${color}`}>{text}</span>;
    };

    return (
        <div className="bg-black/20 p-3 rounded-lg">
            <h4 className="text-sm font-bold text-yellow-500 mb-2 border-b border-yellow-500/20 pb-1">{title}</h4>
            <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
                {Object.entries(data).map(([key, value]) => (
                    <React.Fragment key={key}>
                        <dt className="text-gray-400">{formatKey(key)}</dt>
                        <dd className="text-right break-all">{renderValue(key, value)}</dd>
                    </React.Fragment>
                ))}
            </dl>
        </div>
    );
};

const SignalCard = ({ signal }) => {
    if (!signal) return null;
    const isSuccess = signal.signal_type && signal.signal_type !== 'HOLD';
    const signalType = isSuccess ? signal.signal_type : signal.scores?.rule_based_signal || 'HOLD';
    const colors = {
        BUY: { border: 'border-green-500/50', text: 'text-green-400', bg: 'bg-green-500/10' },
        SELL: { border: 'border-red-500/50', text: 'text-red-400', bg: 'bg-red-500/10' },
        HOLD: { border: 'border-yellow-500/50', text: 'text-yellow-400', bg: 'bg-yellow-500/10' },
    };
    const color = colors[signalType];
    const Metric = ({ label, value, className = '' }) => (<div><p className="text-xs text-gray-400">{label}</p><p className={`font-mono font-bold text-base text-white ${className}`}>{value || 'N/A'}</p></div>);
    
    return (
        <div className={`rounded-xl p-4 border ${color.border} ${color.bg} space-y-4`}>
            <div className="flex justify-between items-center pb-3 border-b border-gray-700/50">
                <span className="font-bold text-2xl text-white">{signal.symbol || 'BTC'}/USDT</span>
                <span className={`font-bold text-2xl ${color.text}`}>{signalType}</span>
                <span className="text-sm text-gray-400">{signal.timeframe || 'Multi-TF'}</span>
            </div>
            {isSuccess ? (
                <>
                    <div className="grid grid-cols-2 gap-x-4 gap-y-3 pt-2 text-sm">
                        <Metric label="Entry Zone" value={signal.entry_zone?.map(p => p.toFixed(2)).join(' - ')} />
                        <Metric label="Stop-Loss" value={signal.stop_loss?.toFixed(2)} className="text-red-400" />
                        <Metric label="Risk/Reward" value={`${signal.risk_reward_ratio}R`} />
                        <Metric label="Strategy" value={signal.strategy_name} className="text-cyan-400" />
                    </div>
                    <div><p className="text-gray-400 text-sm">Targets</p><div className="flex flex-wrap gap-x-4">{signal.targets.map(t => <p key={t} className="text-green-400 font-mono font-bold text-base">{t.toFixed(2)}</p>)}</div></div>
                    <div className="pt-3 mt-3 border-t border-gray-700/50 text-xs text-gray-300 italic">
                        <p><span className="font-bold not-italic text-yellow-500">🤖 AI Analysis: </span>{signal.explanation_fa}</p>
                    </div>
                    <div className="flex justify-between items-center text-xs text-gray-500">
                        <span>Issued: {new Date(signal.issued_at).toLocaleTimeString()}</span>
                        <div className="flex items-center gap-1"><TbClockHour4/><span>Valid Until: {new Date(signal.valid_until).toLocaleTimeString()}</span></div>
                    </div>
                </>
            ) : (
                <div className="text-center py-4">
                    <p className="text-lg font-bold text-yellow-400">MARKET NEUTRAL</p>
                    <p className="text-sm text-gray-400 mt-1">{signal.message}</p>
                    <div className="flex justify-around mt-4 text-sm">
                        <Metric label="Buy Score" value={signal.scores?.buy_score} className="text-green-400" />
                        <Metric label="Sell Score" value={signal.scores?.sell_score} className="text-red-400" />
                        <Metric label="AI Signal" value={signal.scores?.ai_signal} className="text-purple-400" />
                    </div>
                </div>
            )}
        </div>
    );
};

const Signals = ({ signalData, loading, error, onRefresh, symbol }) => (
    <section className="bg-gray-800/30 backdrop-blur-lg rounded-xl p-4 border border-yellow-500/20">
        <div className="flex justify-between items-center mb-3">
            <h3 className="text-yellow-500 font-bold text-lg flex items-center gap-2"><TbTarget/> Live Signal for {symbol}/USDT</h3>
            <button onClick={onRefresh} disabled={loading} className="bg-gray-700/50 text-yellow-400 text-xs font-bold py-1 px-3 rounded hover:bg-gray-700 flex items-center gap-2 disabled:opacity-50">
                <TbRefresh className={loading ? 'animate-spin' : ''}/>
                {loading ? 'Analyzing...' : 'Refresh'}
            </button>
        </div>
        <div className="space-y-4">
            {error && <p className="text-red-500 text-center">Error: {error}</p>}
            {loading && <p className="text-yellow-500 text-center py-5">🧠 Analyzing the market for {symbol}, please wait...</p>}
            {!loading && !error && <SignalCard signal={signalData} />}
        </div>
    </section>
);

const ActiveTrades = () => {
    const [trades, setTrades] = useState([]);
    const [loading, setLoading] = useState(true);
    useEffect(() => {
        const fetchTrades = async () => {
            try {
                const response = await fetch('https://aisignalpro-production.up.railway.app/api/trades/open/');
                if(response.ok) setTrades(await response.json());
            } catch (e) { console.error("Failed to fetch trades:", e); } 
            finally { setLoading(false); }
        };
        fetchTrades();
    }, []);

    return (
        <section className="bg-gray-800/30 backdrop-blur-lg rounded-xl p-4 border border-yellow-500/20">
            <h3 className="text-yellow-500 font-bold text-lg mb-3 flex items-center gap-2"><TbArrowsRandom/> Active Trades</h3>
            {loading ? <p className="text-gray-400 text-center">Loading trades...</p> : 
             trades.length > 0 ? <div className="space-y-4 h-60 overflow-y-auto pr-2">{/* Logic to display each trade card would go here */}</div> :
             <p className="text-gray-500 text-center py-4">No active trades.</p>}
        </section>
    );
};

const DetailedAnalysis = ({ analysisData, onAnalysisRequest, isLoading, currentSymbol, setCurrentSymbol }) => {
    const [selectedTf, setSelectedTf] = useState('1h');
    const timeframes = ['5m', '15m', '1h', '4h'];
    const symbols = ['BTC', 'ETH', 'XRP', 'SOL', 'DOGE'];
    const currentAnalysis = analysisData?.full_analysis_details?.[selectedTf];
    const currentPrice = currentAnalysis?.indicators?.close || 0;
    
    const supportLevels = currentAnalysis?.market_structure?.pivots?.filter(p => p[1] < currentPrice).map(p => p[1].toFixed(2)).reverse().slice(0, 5) || [];
    const resistanceLevels = currentAnalysis?.market_structure?.pivots?.filter(p => p[1] > currentPrice).map(p => p[1].toFixed(2)).slice(0, 5) || [];

    const handleSymbolChange = (symbol) => {
        setCurrentSymbol(symbol);
        onAnalysisRequest(symbol);
    };
    
    return (
         <section className="bg-gray-800/30 backdrop-blur-lg rounded-xl p-4 border border-yellow-500/20">
            <h3 className="text-yellow-500 font-bold text-lg mb-3 flex items-center gap-2"><TbChartInfographic/> Detailed Analysis Engine</h3>
            <div className="flex flex-wrap gap-2 mb-4">
                 <div className="flex-grow">
                    <select value={currentSymbol} onChange={e => handleSymbolChange(e.target.value)} className="w-full bg-black/20 p-2 rounded-md text-white border border-gray-600 focus:ring-yellow-500 focus:border-yellow-500">
                        {symbols.map(s => <option key={s} value={s}>{s}/USDT</option>)}
                    </select>
                </div>
                <div className="flex-grow flex gap-1 bg-black/20 p-1 rounded-md border border-gray-600">
                    {timeframes.map(tf => (
                        <button key={tf} onClick={() => setSelectedTf(tf)} className={`w-full text-xs font-bold py-1 px-2 rounded transition-colors ${selectedTf === tf ? 'bg-yellow-500 text-black' : 'text-gray-400 hover:bg-gray-700'}`}>
                            {tf}
                        </button>
                    ))}
                </div>
            </div>
            <div className="max-h-[40rem] overflow-y-auto pr-2">
                {isLoading ? <p className="text-center text-yellow-500 py-4">Analyzing market for {currentSymbol}...</p> :
                currentAnalysis ? (
                    <div className="space-y-3">
                        <AnalysisConclusion analysis={currentAnalysis} />
                        <AnalysisDetailCard title="Trend Analysis" data={currentAnalysis.trend} />
                        <AnalysisDetailCard title="Market Structure" data={currentAnalysis.market_structure} />
                        <AnalysisDetailCard title="Indicators" data={currentAnalysis.indicators} />
                        <AnalysisDetailCard title="Divergence" data={currentAnalysis.divergence} />
                        <AnalysisDetailCard title="Candlestick Patterns" data={{Identified: currentAnalysis.patterns}} />
                        <AnalysisDetailCard title="Support Levels (from Pivots)" data={{ Levels: supportLevels }} />
                        <AnalysisDetailCard title="Resistance Levels (from Pivots)" data={{ Levels: resistanceLevels }} />
                    </div>
                ) : <p className="text-gray-500 text-center py-4">Analysis data not available. Please refresh.</p>}
            </div>
        </section>
    );
};

// =================================================================
//  Main Page Component
// =================================================================
export default function Home() {
    const [signalData, setSignalData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [currentSymbol, setCurrentSymbol] = useState('BTC');
    const [btcPrice, setBtcPrice] = useState({ price: null, change: null });

    const fetchSignal = useCallback(async (symbol) => {
        if (!symbol) return;
        setLoading(true);
        setError(null);
        try {
            const response = await fetch(`https://aisignalpro-production.up.railway.app/api/get-composite-signal/?symbol=${symbol}`);
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            const data = await response.json();
            if (data.status === 'SUCCESS') setSignalData(data.signal);
            else if (data.status === 'NEUTRAL') setSignalData({ ...data, symbol });
            else throw new Error(data.message || 'Unknown API error');
        } catch (e) {
            setError(e.message);
        } finally {
            setLoading(false);
        }
    }, []);
    
    useEffect(() => {
        fetchSignal(currentSymbol);
    }, [currentSymbol, fetchSignal]);

    return (
        <div className="bg-black text-gray-200 min-h-screen">
            <div className="absolute top-0 left-0 w-full h-full bg-gradient-to-br from-gray-900 via-black to-gray-800 -z-10"/>
            <Header symbol={currentSymbol} price={btcPrice.price} change={btcPrice.change} />
            <main className="p-4 space-y-6 pb-20">
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    <SystemStatus />
                    <MarketOverview />
                </div>
                <PriceTicker onBtcPriceUpdate={setBtcPrice} />
                <Signals signalData={signalData} loading={loading} error={error} onRefresh={() => fetchSignal(currentSymbol)} symbol={currentSymbol} />
                <ActiveTrades />
                <DetailedAnalysis 
                    analysisData={signalData} 
                    onAnalysisRequest={fetchSignal} 
                    isLoading={loading}
                    currentSymbol={currentSymbol}
                    setCurrentSymbol={setCurrentSymbol}
                />
            </main>
            <Footer />
        </div>
    )
}
