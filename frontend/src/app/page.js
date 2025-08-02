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
                <div><p className="text-xs text-gray-400">Market Cap</p><p className="font-bold text-lg text-white">${(overview.market_cap / 1e12).toFixed(2)}T</p></div>
                <div><p className="text-xs text-gray-400">Volume 24h</p><p className="font-bold text-lg text-white">${(overview.volume_24h / 1e9).toFixed(2)}B</p></div>
                <div><p className="text-xs text-gray-400">BTC Dominance</p><p className="font-bold text-lg text-white">{Number(overview.btc_dominance).toFixed(1)}%</p></div>
                <div><p className="text-xs text-gray-400">Fear & Greed</p><p className="font-bold text-lg text-white">{overview.fear_and_greed || 'N/A'}</p></div>
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

const AnalysisConclusion = ({ data }) => {
    let conclusion = { text: 'N/A', color: 'text-gray-400', Icon: TbMinus };
    
    if(data?.trend?.signal) {
        const signal = data.trend.signal.toLowerCase();
        if(signal.includes('uptrend')) conclusion = { text: 'Bullish Trend', color: 'text-green-400', Icon: TbArrowUpRight };
        else if (signal.includes('downtrend')) conclusion = { text: 'Bearish Trend', color: 'text-red-400', Icon: TbArrowDownLeft };
        else conclusion = { text: 'Neutral Trend', color: 'text-yellow-400', Icon: TbMinus };
    }
    else if(data?.market_structure?.predicted_next_leg_direction) {
        const direction = data.market_structure.predicted_next_leg_direction;
        if(direction === 'up') conclusion = { text: 'Expecting Upward Move', color: 'text-green-400', Icon: TbArrowUpRight };
        else if (direction === 'down') conclusion = { text: 'Expecting Downward Move', color: 'text-red-400', Icon: TbArrowDownLeft };
    }

    return (
        <div className="bg-black/30 p-2 rounded-md mt-2 flex items-center justify-between">
            <span className="text-xs text-gray-400">Conclusion:</span>
            <div className={`flex items-center gap-1 font-bold text-sm ${conclusion.color}`}>
                <conclusion.Icon />
                <span>{conclusion.text}</span>
            </div>
        </div>
    );
};

const AnalysisDetailCard = ({ title, data }) => {
    if (!data || Object.keys(data).length === 0) return <div className="bg-black/20 p-3 rounded-lg"><h4 className="text-sm font-bold text-yellow-500 mb-2">{title}</h4><p className="text-xs text-gray-500">No data available.</p></div>;
    const formatKey = (key) => key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    
    const renderValue = (key, value) => {
        if (typeof value === 'boolean') return value ? 'Yes' : 'No';
        if (typeof value === 'number') return value.toFixed(2);
        if (Array.isArray(value)) return value.length > 0 ? value.join(', ') : 'N/A';
        if (typeof value === 'object' && value !== null) {
            if (key === 'divergence') {
                return Object.entries(value)
                    .map(([ind, divs]) => Array.isArray(divs) && divs.length > 0 ? `${ind.toUpperCase()}: ${divs.map(d => d.type).join(', ')}` : null)
                    .filter(Boolean).join(' | ') || 'None Found';
            }
            return JSON.stringify(value);
        }
        return value || 'N/A';
    };

    return (
        <div className="bg-black/20 p-3 rounded-lg">
            <h4 className="text-sm font-bold text-yellow-500 mb-2 border-b border-yellow-500/20 pb-1">{title}</h4>
            <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
                {Object.entries(data).map(([key, value]) => (
                    <React.Fragment key={key}>
                        <dt className="text-gray-400">{formatKey(key)}</dt>
                        <dd className="text-white font-mono text-right break-words">{renderValue(key, value)}</dd>
                    </React.Fragment>
                ))}
            </dl>
        </div>
    );
};

const SignalCard = ({ signal }) => { /* ... (Same as last complete version) ... */ };
const Signals = ({ signalData, loading, error, onRefresh, symbol }) => ( /* ... (Same as last complete version) ... */ );
const ActiveTrades = () => { /* ... (Same as last complete version) ... */ };

const DetailedAnalysis = ({ analysisData, onAnalysisRequest, isLoading, currentSymbol, setCurrentSymbol }) => {
    const [selectedTf, setSelectedTf] = useState('1h');
    const timeframes = ['5m', '15m', '1h', '4h'];
    const symbols = ['BTC', 'ETH', 'XRP', 'SOL', 'DOGE'];
    const currentAnalysis = analysisData?.full_analysis_details?.[selectedTf];
    
    const handleSymbolChange = (symbol) => {
        setCurrentSymbol(symbol);
        onAnalysisRequest(symbol);
    }
    
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
                        <AnalysisConclusion data={currentAnalysis} />
                        <AnalysisDetailCard title="Trend Analysis" data={currentAnalysis.trend} />
                        <AnalysisDetailCard title="Market Structure" data={currentAnalysis.market_structure} />
                        <AnalysisDetailCard title="Indicators" data={currentAnalysis.indicators} />
                        <AnalysisDetailCard title="Divergence" data={currentAnalysis.divergence} />
                        <AnalysisDetailCard title="Candlestick Patterns" data={{Identified: currentAnalysis.patterns}} />
                    </div>
                ) : <p className="text-gray-500 text-center py-4">Analysis data not available for {selectedTf}.</p>}
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
        // No need to setCurrentSymbol here, it's handled by the caller
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
    }, [fetchSignal, currentSymbol]);

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
                <DetailedAnalysis analysisData={signalData} onAnalysisRequest={fetchSignal} isLoading={loading} currentSymbol={currentSymbol} setCurrentSymbol={setCurrentSymbol} />
            </main>
            <Footer />
        </div>
    )
}
