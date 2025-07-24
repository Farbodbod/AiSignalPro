'use client';
import { useState, useEffect, useMemo, useCallback, useRef } from 'react';

// ===================================================================
// Helper Functions
// ===================================================================
const formatLargeNumber = (num) => {
  if (!num || num === 0) return 'N/A';
  if (num >= 1e12) return `$${(num / 1e12).toFixed(2)}T`;
  if (num >= 1e9) return `$${(num / 1e9).toFixed(2)}B`;
  return `$${(num / 1e6).toFixed(2)}M`;
};
const formatPrice = (price) => {
    if (price === null || price === undefined) return 'N/A';
    const options = { minimumFractionDigits: 2, maximumFractionDigits: price < 10 ? 4 : 2 };
    return price.toLocaleString('en-US', options);
};
const capitalize = (s) => {
    if (typeof s !== 'string' || s.length === 0) return '';
    return s.charAt(0).toUpperCase() + s.slice(1);
};

// ===================================================================
// Live Data Components
// ===================================================================
function SystemStatus() {
    const [statuses, setStatuses] = useState([]);
    const fetchStatuses = useCallback(async () => {
        try {
            const response = await fetch('https://aisignalpro-production.up.railway.app/api/status/');
            if (!response.ok) throw new Error("Network response was not ok");
            const data = await response.json();
            setStatuses(data);
        } catch (error) { console.error("Failed to fetch statuses:", error); }
    }, []);
    useEffect(() => {
        fetchStatuses();
        const intervalId = setInterval(fetchStatuses, 30000);
        return () => clearInterval(intervalId);
    }, [fetchStatuses]);
    return (
        <section>
            <div className="grid grid-cols-3 md:grid-cols-7 gap-2 text-center">
                {statuses.map((ex) => (
                    <div key={ex.name} className="bg-gray-800/30 backdrop-blur-lg rounded-lg p-2 border border-yellow-500/10">
                        <p className="text-xs font-semibold text-gray-300">{ex.name}</p>
                        <div className="flex items-center justify-center gap-2 mt-1">
                            <span className={'w-2 h-2 rounded-full ' + (ex.status === 'online' ? 'bg-green-400 animate-pulse' : 'bg-red-500')}></span>
                            <span className="text-xs text-gray-400">{ex.ping}</span>
                        </div>
                    </div>
                ))}
                <button onClick={fetchStatuses} className="bg-yellow-500/80 text-black p-2 rounded-lg text-sm font-bold flex items-center justify-center cursor-pointer hover:bg-yellow-500 col-span-3 md:col-span-1">Test All</button>
            </div>
        </section>
    );
}

function MarketOverview() {
    const [marketData, setMarketData] = useState(null);
    useEffect(() => {
        const fetchMarketData = async () => {
            try {
                const response = await fetch('https://aisignalpro-production.up.railway.app/api/market-overview/');
                if (!response.ok) throw new Error("Network response was not ok");
                const data = await response.json();
                if (data && data.market_cap && data.market_cap !== 0) { setMarketData(data); }
            } catch (error) { console.error("Failed to fetch market data:", error); }
        };
        fetchMarketData();
        const intervalId = setInterval(fetchMarketData, 30000);
        return () => clearInterval(intervalId);
    }, []);
    return (
        <section className="bg-gray-800/30 backdrop-blur-lg rounded-xl p-4 border border-yellow-500/20">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div><p className="text-xs text-gray-400">Market Cap</p><p className="font-bold text-lg text-yellow-500">{formatLargeNumber(marketData?.market_cap)}</p></div>
                <div><p className="text-xs text-gray-400">Volume 24h</p><p className="font-bold text-lg text-yellow-500">{formatLargeNumber(marketData?.volume_24h)}</p></div>
                <div><p className="text-xs text-gray-400">BTC Dominance</p><p className="font-bold text-lg text-yellow-500">{marketData ? `${Number(marketData.btc_dominance).toFixed(1)}%` : 'N/A'}</p></div>
                <div><p className="text-xs text-gray-400">Fear & Greed</p><p className="font-bold text-lg text-yellow-500">{marketData?.fear_and_greed || 'N/A'}</p></div>
            </div>
        </section>
    );
}

function PriceTicker() {
    const [livePrices, setLivePrices] = useState({});
    useEffect(() => {
        const fetchPrices = async () => {
            try {
                const response = await fetch('https://aisignalpro-production.up.railway.app/api/data/all/');
                if (!response.ok) throw new Error("Network response was not ok");
                const data = await response.json();
                if (data && typeof data === 'object') { setLivePrices(data); }
            } catch (error) { console.error("Failed to fetch live prices:", error); }
        };
        fetchPrices();
        const intervalId = setInterval(fetchPrices, 10000);
        return () => clearInterval(intervalId);
    }, []);
    const coinsToRender = useMemo(() => ['BTC', 'ETH', 'XRP', 'SOL', 'DOGE'], []);
    return (
        <section>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {coinsToRender.map(coin => {
                    const p = livePrices[coin];
                    if (!p) return (<div key={coin} className="h-16 bg-gray-700/50 rounded-lg animate-pulse"></div>);
                    const change = p.change_24h || 0;
                    const changeClass = change >= 0 ? 'text-green-400' : 'text-red-400';
                    const changePrefix = change >= 0 ? '+' : '';
                    return (
                        <div key={p.symbol} className="bg-gray-800/30 backdrop-blur-lg rounded-lg p-3 flex justify-between items-center border border-yellow-500/10">
                            <div>
                                <p className="font-bold text-white">{p.symbol || `${coin}/USDT`}</p>
                                <p className="text-xs text-gray-500">{capitalize(p.source)}</p>
                            </div>
                            <div>
                                <p className="font-semibold text-lg text-yellow-500 text-right">${formatPrice(p.price)}</p>
                                <p className={`text-xs text-right ${changeClass}`}>{changePrefix}{change.toFixed(2)}%</p>
                            </div>
                        </div>
                    );
                })}
            </div>
        </section>
    );
}

// ===================================================================
// New UI Components with Sample Data
// ===================================================================
const SignalCard = ({ signal }) => {
    const colors = { buy: { border: 'border-green-500/50', text: 'text-green-400', bg: 'bg-green-500/10' }, sell: { border: 'border-red-500/50', text: 'text-red-400', bg: 'bg-red-500/10' }};
    const color = colors[signal.type.toLowerCase()] || { border: 'border-yellow-500/50', text: 'text-yellow-400', bg: 'bg-yellow-500/10' };
    return (
        <div className={`rounded-xl p-4 border ${color.border} ${color.bg} space-y-3`}>
            <div className="flex justify-between items-center pb-3 border-b border-gray-700/50">
                <span className="font-bold text-xl text-white">{signal.symbol}</span>
                <span className={`font-bold text-xl ${color.text}`}>{signal.type.toUpperCase()}</span>
                <span className="text-sm text-gray-400">{signal.timeframe}</span>
            </div>
            <div className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
                <div><p className="text-gray-400">Entry Zone</p><p className="font-mono text-white">{signal.entry}</p></div>
                <div className="text-right"><p className="text-gray-400">Stop-Loss</p><p className="font-mono text-red-400">{signal.sl}</p></div>
                <div><p className="text-gray-400">Targets</p><div className="flex flex-wrap gap-x-3">{signal.targets.map(t => <span key={t} className="text-green-400 font-mono">{t}</span>)}</div></div>
                <div className="text-right"><p className="text-gray-400">Accuracy</p><p className="font-mono text-white">{signal.accuracy}</p></div>
                <div><p className="text-gray-400">Support</p><div className="flex flex-wrap gap-x-3">{signal.support.map(s => <span key={s} className="text-white font-mono">{s}</span>)}</div></div>
                <div className="text-right"><p className="text-gray-400">Resistance</p><div className="flex flex-wrap gap-x-3 justify-end">{signal.resistance.map(r => <span key={r} className="text-white font-mono">{r}</span>)}</div></div>
            </div>
            <div className="pt-3 border-t border-gray-700/50 text-xs space-y-1">
                <p className="text-gray-400">Reasons: <span className="text-gray-200">{signal.reasons.join(', ')}</span></p>
            </div>
            <div className="pt-3 mt-3 border-t border-gray-700/50 flex justify-between items-center">
                <div className="text-xs text-gray-400">Confidence: <span className="font-bold text-white">{signal.confidence}%</span> | AI Score: <span className="font-bold text-white">{signal.ai_score}%</span></div>
                <button className="bg-yellow-500 text-black text-sm font-bold py-2 px-4 rounded-lg hover:bg-yellow-400">Enter Trade</button>
            </div>
        </div>
    );
};

const Signals = () => {
    const sampleSignals = [ { type: 'sell', symbol: 'ETH/USDT', timeframe: '1h', entry: '3550-3560', sl: '3600', targets: ['3500','3450'], confidence: 92, ai_score: 90, reasons: ['Bearish MACD Cross', 'Resistance Level Hit'], accuracy: "81%", support: ['3510', '3480'], resistance: ['3580', '3600'] }, { type: 'buy', symbol: 'BTC/USDT', timeframe: '4h', entry: '68k-68.2k', sl: '67.5k', targets: ['69k','70k','71k'], confidence: 85, ai_score: 88, reasons: ['Bullish Engulfing', 'RSI Divergence'], accuracy: "78%", support: ['67.8k', '67.2k'], resistance: ['69.1k', '70k'] } ];
    return (
        <section className="bg-gray-800/30 backdrop-blur-lg rounded-xl p-4 border border-yellow-500/20">
            <div className="flex justify-between items-center mb-3">
                <h3 className="text-yellow-500 font-bold text-lg">Signals</h3>
                <button className="bg-gray-700/50 text-yellow-400 text-xs font-bold py-1 px-3 rounded hover:bg-gray-700">Generate Manual</button>
            </div>
            <div className="space-y-4">{sampleSignals.map((sig, i) => <SignalCard key={i} signal={sig} />)}</div>
        </section>
    );
};

const ActiveTradeCard = ({ trade }) => {
    const isLong = trade.direction === 'long';
    const isProfit = (isLong && trade.current_price > trade.entry_price) || (!isLong && trade.current_price < trade.entry_price);
    const barGradient = isProfit ? 'bg-gradient-to-r from-green-500/50 to-green-500' : 'bg-gradient-to-r from-red-500/50 to-red-500';
    const progress = Math.min(Math.abs(trade.current_price - trade.entry_price) / Math.abs(trade.targets[0] - trade.entry_price) * 100, 100);
    return(
        <div className="bg-gray-900/50 rounded-lg p-3 border border-yellow-500/30 space-y-3">
            <div className="flex justify-between items-center">
                <div><span className="font-bold text-lg text-white">{trade.symbol}</span><span className={`text-xs ml-2 font-bold ${isLong ? 'text-green-400' : 'text-red-400'}`}>{isLong ? "LONG" : "SHORT"}</span></div>
                <div className="text-right"><span className={`font-mono text-lg ${isProfit ? 'text-green-400' : 'text-red-400'}`}>{trade.pnl}</span><p className="text-xs text-gray-400">Current: {trade.current_price}</p></div>
            </div>
            <div className="relative h-6 w-full bg-black/30 rounded-lg overflow-hidden border border-gray-700">
                <div className="absolute top-0 h-full flex items-center justify-between w-full px-2 text-xs font-mono">
                    <span className="text-red-400 font-semibold">{isLong ? `SL: ${trade.sl}` : `TP: ${trade.targets[0]}`}</span>
                    <span className="text-green-400 font-semibold">{isLong ? `TP: ${trade.targets[0]}` : `SL: ${trade.sl}`}</span>
                </div>
                <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 h-4 w-0.5 bg-yellow-500"></div>
                <div className={`absolute top-0 h-full ${barGradient} ${isLong ? 'left-0' : 'right-0'}`} style={{width: `${progress}%`}}></div>
                <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 text-xs font-bold text-black bg-yellow-500 px-1 rounded-sm">Entry: {trade.entry_price}</div>
            </div>
            <div className="text-xs text-gray-300 bg-black/20 p-2 rounded-md"><p><span className="font-bold text-yellow-500">Live AI Score: {trade.ai_score}%</span> | {trade.status_text}</p></div>
        </div>
    );
};

const ActiveTrades = () => {
    const sampleTrades = [ { direction: 'long', symbol: 'BTC/USDT', entry_price: 68100, current_price: 68500, sl: 67500, targets: [69000], ai_score: 91, pnl: "+$250.00", status_text: "Trend is strong, hold position." }, { direction: 'short', symbol: 'ETH/USDT', entry_price: 3555, current_price: 3540, sl: 3600, targets: [3500], ai_score: 85, pnl: "+$75.00", status_text: "Approaching first target." }, ];
    return (
        <section className="bg-gray-800/30 backdrop-blur-lg rounded-xl p-4 border border-yellow-500/20">
            <h3 className="text-yellow-500 font-bold text-lg mb-3">Active Trades</h3>
            <div className="space-y-4">{sampleTrades.map((trade, i) => <ActiveTradeCard key={i} trade={trade} />)}</div>
        </section>
    );
};

const AiChat = () => {
    const messages = [{ sender: 'ai', text: 'Good morning! BTC is showing strong bullish divergence.' }, { sender: 'user', text: 'Give me a detailed analysis for SOL/USDT.' }];
    return (
        <section className="bg-gray-800/30 backdrop-blur-lg rounded-xl p-4 border border-yellow-500/20">
            <h3 className="text-yellow-500 font-bold text-lg mb-3">AI Chat</h3>
            <div className="space-y-3 h-48 overflow-y-auto pr-2 text-sm">{messages.map((msg, i) => <div key={i} className={`p-2 rounded-lg ${msg.sender === 'ai' ? 'bg-black/20 text-gray-300' : 'bg-yellow-500/20 text-yellow-300 text-right'}`}>{msg.text}</div>)}</div>
            <div className="mt-3 flex gap-2"><input type="text" placeholder="Ask AI..." className="flex-grow bg-black/30 border border-gray-700 rounded-lg p-2 text-sm focus:ring-yellow-500 focus:border-yellow-500"/><button className="bg-yellow-500 text-black font-bold p-2 rounded-lg">Send</button></div>
        </section>
    );
};

const ComprehensiveAnalysis = () => {
    return (
        <section className="bg-gray-800/30 backdrop-blur-lg rounded-xl p-4 border border-yellow-500/20">
            <h3 className="text-yellow-500 font-bold text-lg mb-3">Comprehensive Analysis</h3>
            <div className="flex gap-4 mb-4"><select className="flex-grow bg-black/30 border border-gray-700 rounded-lg p-2 text-sm w-1/2"><option>BTC/USDT</option></select><select className="flex-grow bg-black/30 border border-gray-700 rounded-lg p-2 text-sm w-1/2"><option>1h</option></select></div>
            <div className="text-sm text-gray-400">Analysis details will be shown here...</div>
        </section>
    );
};

const SystemHealth = () => {
    const health = [{ name: 'Analysis Engine', accuracy: '91.2%', speed: '1.2s' }, { name: 'AI Engine', accuracy: '88.5%', speed: '3.5s' }];
    return (
        <section className="bg-gray-800/30 backdrop-blur-lg rounded-xl p-4 border border-yellow-500/20">
            <h3 className="text-yellow-500 font-bold text-lg mb-3">System Health</h3>
            <div className="space-y-2 text-sm">{health.map(h => (<div key={h.name} className="flex justify-between items-center bg-black/20 p-2 rounded-md"><span className="text-gray-300">{h.name}</span><div className="text-right"><span className="font-mono text-white">{h.accuracy}</span><span className="text-xs text-gray-500 ml-2">({h.speed})</span></div></div>))}</div>
        </section>
    );
};

// ===================================================================
// کامپوننت اصلی صفحه
// ===================================================================
export default function Home() {
    return (
        <div className="bg-black text-gray-200 min-h-screen">
            <div className="absolute top-0 left-0 w-full h-full bg-gradient-to-br from-gray-900 via-black to-gray-800 -z-10"/>
            <header className="flex justify-between items-center p-4 border-b border-yellow-500/30 sticky top-0 bg-gray-900/70 backdrop-blur-xl z-10">
                <h1 className="text-xl md:text-2xl font-bold text-yellow-500 drop-shadow-[0_2px_2px_rgba(255,215,0,0.5)]">🤖 Ai Signal Pro</h1>
                <div><button className="w-8 h-8 rounded-full bg-white/10 border border-yellow-500/30 text-yellow-500">☀️</button></div>
            </header>
            <main className="p-4 space-y-6 pb-20">
                <SystemStatus />
                <MarketOverview />
                <PriceTicker />
                <Signals />
                <ActiveTrades />
                <AiChat />
                <ComprehensiveAnalysis />
                <SystemHealth />
            </main>
            <footer className="fixed bottom-0 left-0 right-0 p-2 bg-gray-900/70 backdrop-blur-xl border-t border-yellow-500/30">
                <div className="flex justify-around text-gray-400">
                    <button className="text-yellow-500 font-bold">Dashboard</button>
                    <button className="hover:text-yellow-500">Signals</button>
                    <button className="hover:text-yellow-500">Trades</button>
                    <button className="hover:text-yellow-500">Analysis</button>
                </div>
            </footer>
        </div>
    )
}
