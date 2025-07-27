'use client';
import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { TbBrain } from "react-icons/tb";

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
        const intervalId = setInterval(fetchMarketData, 60000);
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
        const intervalId = setInterval(fetchPrices, 15000);
        return () => clearInterval(intervalId);
    }, []);
    const coinsToRender = useMemo(() => ['BTC', 'ETH', 'XRP', 'SOL', 'DOGE'], []);
    return (
        <section>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
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

const SignalCard = ({ signal }) => {
    const colors = {
        BUY: { border: 'border-green-500/50', text: 'text-green-400', bg: 'bg-green-500/10' },
        SELL: { border: 'border-red-500/50', text: 'text-red-400', bg: 'bg-red-500/10' },
        HOLD: { border: 'border-yellow-500/50', text: 'text-yellow-400', bg: 'bg-yellow-500/10' }
    };
    const color = colors[signal.signal_type] || colors.HOLD;

    return (
        <div className={`rounded-xl p-4 border ${color.border} ${color.bg} space-y-3`}>
            <div className="flex justify-between items-center pb-3 border-b border-gray-700/50">
                <span className="font-bold text-xl text-white">{signal.symbol}</span>
                <span className={`font-bold text-xl ${color.text}`}>{signal.signal_type}</span>
                <span className="text-sm text-gray-400">{signal.timeframe}</span>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-x-4 gap-y-3 text-sm">
                <div><p className="text-gray-400">Entry Zone</p><p className="font-mono text-white">{signal.entry_zone?.map(formatPrice).join(' - ')}</p></div>
                <div className="text-right"><p className="text-gray-400">Stop-Loss</p><p className="font-mono text-red-400">${formatPrice(signal.stop_loss)}</p></div>
                <div className="text-right"><p className="text-gray-400">R/R Ratio</p><p className="font-mono text-white">{signal.risk_reward_ratio} R</p></div>
                <div className="md:col-span-3"><p className="text-gray-400">Targets</p><div className="flex flex-wrap gap-x-3">{signal.targets?.map(t => <span key={t} className="text-green-400 font-mono">${formatPrice(t)}</span>)}</div></div>
            </div>
            <div className="pt-3 border-t border-gray-700/50 text-xs space-y-1">
                <p className="text-gray-400">Reasons: <span className="text-gray-200">{signal.signal_reasons?.join(', ')}</span></p>
            </div>
            <div className="pt-3 mt-3 border-t border-gray-700/50 flex justify-between items-center">
                <div className="text-xs text-gray-400">System Confidence: <span className="font-bold text-white">{signal.system_confidence_percent}%</span> | AI: <span className="font-bold text-white">{signal.ai_confidence_percent}%</span></div>
                <button className="bg-yellow-500 text-black text-sm font-bold py-2 px-4 rounded-lg hover:bg-yellow-400">Enter Trade</button>
            </div>
        </div>
    );
};

const Signals = () => {
    const [signal, setSignal] = useState(null);
    const [loading, setLoading] = useState(true);

    const fetchSignal = useCallback(async () => {
        setLoading(true);
        try {
            const response = await fetch('https://aisignalpro-production.up.railway.app/api/get-composite-signal/');
            const data = await response.json();
            if (response.ok) {
                setSignal(data);
            } else {
                throw new Error(data.error || "Failed to fetch signal");
            }
        } catch (error) {
            console.error("Failed to fetch signal:", error);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchSignal();
    }, [fetchSignal]);

    return (
        <section className="bg-gray-800/30 backdrop-blur-lg rounded-xl p-4 border border-yellow-500/20">
            <div className="flex justify-between items-center mb-3">
                <h3 className="text-yellow-500 font-bold text-lg">Live Signal</h3>
                <button onClick={fetchSignal} disabled={loading} className="bg-gray-700/50 text-yellow-400 text-xs font-bold py-1 px-3 rounded hover:bg-gray-700 disabled:opacity-50">
                    {loading ? 'Analyzing...' : 'Refresh Signal'}
                </button>
            </div>
            {/* کانتینر برای اسکرول داخلی */}
            <div className="space-y-4 max-h-[30rem] overflow-y-auto pr-2">
                {loading && <div className="h-64 bg-gray-700/50 rounded-lg animate-pulse flex items-center justify-center"><p>🧠 Analyzing Market...</p></div>}
                {!loading && signal && <SignalCard signal={signal} />}
                {!loading && !signal && <p className="text-center text-gray-400">No signal available right now.</p>}
            </div>
        </section>
    );
};

const ActiveTradeCard = ({ trade }) => {
    return (
        <div className="bg-gray-900/50 rounded-lg p-3 border border-yellow-500/30 space-y-3">
            <div className="flex justify-between items-center">
                <div><span className="font-bold text-lg text-white">{trade.symbol}</span><span className={`text-xs ml-2 font-bold ${trade.direction === 'long' ? 'text-green-400' : 'text-red-400'}`}>{trade.direction.toUpperCase()}</span></div>
                <div className="text-right"><span className="text-sm text-gray-400">Status: {capitalize(trade.status)}</span></div>
            </div>
            <div className="text-xs grid grid-cols-2 gap-2">
                <p className="text-gray-400">Entry Price: <span className="font-mono text-white">${formatPrice(trade.entry_price)}</span></p>
                <p className="text-gray-400">Entry Time: <span className="font-mono text-white">{new Date(trade.entry_time).toLocaleTimeString()}</span></p>
                <p className="text-gray-400">Stop Loss: <span className="font-mono text-red-400">${formatPrice(trade.stop_loss)}</span></p>
                <p className="text-gray-400">Targets: <span className="font-mono text-green-400">{trade.targets?.map(formatPrice).join(', ')}</span></p>
            </div>
        </div>
    );
};

const ActiveTrades = () => {
    const [trades, setTrades] = useState([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchTrades = async () => {
            try {
                const response = await fetch('https://aisignalpro-production.up.railway.app/api/trades/open/');
                 if (!response.ok) throw new Error("Network response was not ok");
                const data = await response.json();
                setTrades(data);
            } catch (error) {
                console.error("Failed to fetch active trades:", error);
            } finally {
                setLoading(false);
            }
        };
        fetchTrades();
        const intervalId = setInterval(fetchTrades, 20000);
        return () => clearInterval(intervalId);
    }, []);

    return (
        <section className="bg-gray-800/30 backdrop-blur-lg rounded-xl p-4 border border-yellow-500/20">
            <h3 className="text-yellow-500 font-bold text-lg mb-3">Active Trades</h3>
            {loading && <div className="h-24 bg-gray-700/50 rounded-lg animate-pulse"></div>}
            {/* کانتینر برای اسکرول داخلی */}
            <div className="space-y-4 max-h-96 overflow-y-auto pr-2">
                {!loading && trades.length === 0 && <p className="text-center text-sm text-gray-400">No active trades.</p>}
                {!loading && trades.map((trade) => <ActiveTradeCard key={trade.id} trade={trade} />)}
            </div>
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
// Main Page Component
// ===================================================================
export default function Home() {
    return (
        <div className="bg-black text-gray-200 min-h-screen">
            <div className="absolute top-0 left-0 w-full h-full bg-gradient-to-br from-gray-900 via-black to-gray-800 -z-10"/>
            <header className="flex justify-between items-center p-4 border-b border-yellow-500/30 sticky top-0 bg-gray-900/70 backdrop-blur-xl z-10">
                <div className="flex items-center gap-3">
                    <TbBrain className="text-yellow-400 text-3xl drop-shadow-[0_0_8px_rgba(250,204,21,0.5)]" />
                    <h1 className="text-xl md:text-2xl font-bold bg-gradient-to-r from-yellow-400 to-orange-400 bg-clip-text text-transparent drop-shadow-[0_0_5px_rgba(255,165,0,0.8)]">
                        Ai Signal Pro
                    </h1>
                </div>
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
