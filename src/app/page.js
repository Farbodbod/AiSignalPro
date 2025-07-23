'use client';
import { useState, useEffect } from 'react';

// Utility function to format prices (UPDATED)
const formatPrice = (price) => {
    if (price === null || price === undefined) return 'N/A';
    const options = {
        minimumFractionDigits: 2,
        // If price is less than $10, show 4 decimal places for precision
        maximumFractionDigits: price < 10 ? 4 : 2,
    };
    return price.toLocaleString('en-US', options);
};

// ... (The rest of the file and all components remain unchanged) ...
const formatLargeNumber = (num) => { /* ... */ };
function SystemStatus() { /* ... */ }
function MarketOverview() { /* ... */ }
function PriceTicker() { /* ... */ }
export default function Home() { /* ... */ }
