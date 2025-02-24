import React, { useEffect, useState, useRef } from "react";

const WebSocketComponent = () => {
  const [messages, setMessages] = useState({});
  const [status, setStatus] = useState("Connecting...");
  const [error, setError] = useState(null);
  const socketRef = useRef(null);

  useEffect(() => {
    const connectWebSocket = () => {
      try {
        socketRef.current = new WebSocket("wss://binance-stream.onrender.com/ws/binance/");

        socketRef.current.onopen = () => {
          console.log("🟢 WebSocket connected");
          setStatus("Connected");
          setError(null);
        };

        socketRef.current.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            console.log("📡 Received data:", data);
            setMessages((prevMessages) => {
              const newMessages = { ...prevMessages };
              Object.entries(data).forEach(([symbol, msg]) => {
                newMessages[symbol] = msg;
              });
              return newMessages;
            });
          } catch (e) {
            console.error("Failed to parse message:", e);
            setError(`Parse error: ${e.message}`);
          }
        };

        socketRef.current.onerror = (error) => {
          console.error("🔴 WebSocket Error:", error);
          setStatus("Error");
          setError(`Connection error: ${error.message || 'Unknown error'}`);
        };

        socketRef.current.onclose = (event) => {
          console.log("🔴 WebSocket disconnected with code:", event.code);
          setStatus("Disconnected");
          // Attempt to reconnect after 5 seconds
          setTimeout(connectWebSocket, 5000);
        };
      } catch (e) {
        console.error("Failed to create WebSocket:", e);
        setStatus("Failed");
        setError(`Failed to create connection: ${e.message}`);
      }
    };

    connectWebSocket();

    return () => {
      if (socketRef.current) {
        socketRef.current.close();
      }
    };
  }, []);

  const formatDecimal = (value) => (value ? parseFloat(value).toFixed(2) : "0.00");

  return (
    <div style={{ padding: "20px", fontFamily: "Arial, sans-serif" }}>
      <h1 style={{ textAlign: "center" }}>Live Binance Data</h1>
      
      {/* Status and Debug Information */}
      <div style={{ 
        margin: "10px 0", 
        padding: "10px", 
        border: "1px solid #ccc", 
        borderRadius: "4px",
        backgroundColor: "#f8f8f8"
      }}>
        <div>
          Status: <span style={{ 
            color: status === "Connected" ? "green" : "red",
            fontWeight: "bold"
          }}>{status}</span>
        </div>
        {error && (
          <div style={{ color: "red", marginTop: "5px" }}>
            Error: {error}
          </div>
        )}
        <div style={{ marginTop: "5px", fontSize: "0.9em" }}>
          Active Symbols: {Object.keys(messages).length}
        </div>
      </div>

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
