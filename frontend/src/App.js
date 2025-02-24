import React, { useEffect, useState, useRef } from "react";

const WebSocketComponent = () => {
  const [messages, setMessages] = useState({});
  const socketRef = useRef(null);

  useEffect(() => {
    socketRef.current = new WebSocket("ws://websocketapp-y72k.onrender.com/ws/binance/");
    //socketRef.current = new WebSocket("ws://127.0.0.1:8000/ws/binance/");
    // socketRef.current = new WebSocket("wss://websocketapp-y72k.onrender.com/ws/binance/");
    //socketRef.current = new WebSocket("wss://websocketapp-y72k.onrender.com:8000/ws/binance/");
    // socketRef.current = new WebSocket("ws://127.0.0.1:8000/ws/fyers/");

    socketRef.current.onopen = () => console.log("🟢 WebSocket connected");

    socketRef.current.onmessage = (event) => {
      const data = JSON.parse(event.data);
      console.log("📡 Received data:", data);

      setMessages((prevMessages) => {
        const newMessages = { ...prevMessages };
        Object.entries(data).forEach(([symbol, msg]) => {
          newMessages[symbol] = msg;
        });
        return newMessages;
      });
    };

    socketRef.current.onerror = (error) => console.error("🔴 WebSocket Error:", error);
    socketRef.current.onclose = () => console.log("🔴 WebSocket disconnected");

    return () => socketRef.current.close();
  }, []);

  const formatDecimal = (value) => (value ? parseFloat(value).toFixed(2) : "0.00");

  return (
    <div style={{ padding: "20px", fontFamily: "Arial, sans-serif" }}>
      <h1 style={{ textAlign: "center" }}>Live Binance Data</h1>
      <table style={{ width: "100%", borderCollapse: "collapse", border: "1px solid black" }}>
        <thead>
          <tr style={{ background: "#f4f4f4", textAlign: "left" }}>
            <th style={{ padding: "10px", border: "1px solid black" }}>SR. NO.</th>
            <th style={{ padding: "10px", border: "1px solid black" }}>Symbol</th>
            <th style={{ padding: "10px", border: "1px solid black" }}>Timestamp</th>
            <th style={{ padding: "10px", border: "1px solid black" }}>Open</th>
            <th style={{ padding: "10px", border: "1px solid black" }}>High</th>
            <th style={{ padding: "10px", border: "1px solid black" }}>Low</th>
            <th style={{ padding: "10px", border: "1px solid black" }}>Close</th>
            <th style={{ padding: "10px", border: "1px solid black" }}>Volume</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(messages).map(([symbol, msg], index) => (
            <tr key={index} style={{ textAlign: "center" }}>
              <td style={{ padding: "10px", border: "1px solid black" }}>{index + 1}</td>
              <td style={{ padding: "10px", border: "1px solid black" }}>{symbol}</td>
              <td style={{ padding: "10px", border: "1px solid black" }}>{new Date(msg.timestamp).toLocaleString()}</td>
              <td style={{ padding: "10px", border: "1px solid black" }}>{formatDecimal(msg.open)}</td>
              <td style={{ padding: "10px", border: "1px solid black" }}>{formatDecimal(msg.high)}</td>
              <td style={{ padding: "10px", border: "1px solid black" }}>{formatDecimal(msg.low)}</td>
              <td style={{ padding: "10px", border: "1px solid black" }}>{formatDecimal(msg.close)}</td>
              <td style={{ padding: "10px", border: "1px solid black" }}>{formatDecimal(msg.volume)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default WebSocketComponent;
