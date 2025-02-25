import React, { useEffect, useState, useRef } from "react";

const WebSocketComponent = () => {
  const [messages, setMessages] = useState({});
  const [connectionStatus, setConnectionStatus] = useState("disconnected");
  const socketRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  
  const connectWebSocket = () => {
    // Close existing connection if any
    if (socketRef.current) {
      socketRef.current.close();
    }
    
    // Clear any pending reconnection attempts
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }
    
    setConnectionStatus("connecting");
    
    socketRef.current = new WebSocket("wss://binance-live.onrender.com/ws/binance/");
    
    socketRef.current.onopen = () => {
      console.log("🟢 WebSocket connected");
      setConnectionStatus("connected");
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
      } catch (error) {
        console.error("Error parsing WebSocket message:", error);
      }
    };
    
    socketRef.current.onerror = (error) => {
      console.error("🔴 WebSocket Error:", error);
      setConnectionStatus("error");
    };
    
    socketRef.current.onclose = (event) => {
      console.log(`🔴 WebSocket disconnected: ${event.code} ${event.reason}`);
      setConnectionStatus("disconnected");
      
      // Attempt to reconnect with exponential backoff
      const reconnectDelay = Math.min(30000, 1000 * Math.pow(2, Math.floor(Math.random() * 5)));
      console.log(`Attempting to reconnect in ${reconnectDelay/1000} seconds...`);
      
      reconnectTimeoutRef.current = setTimeout(connectWebSocket, reconnectDelay);
    };
  };
  
  useEffect(() => {
    connectWebSocket();
    
    return () => {
      if (socketRef.current) {
        socketRef.current.close();
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
    };
  }, []);
  
  const formatDecimal = (value) => (value ? parseFloat(value).toFixed(2) : "0.00");
  
  const getStatusColor = () => {
    switch(connectionStatus) {
      case "connected": return "green";
      case "connecting": return "orange";
      case "disconnected": return "red";
      case "error": return "darkred";
      default: return "gray";
    }
  };

  return (
    <div style={{ padding: "20px", fontFamily: "Arial, sans-serif" }}>
      <h1 style={{ textAlign: "center" }}>Live Binance Data</h1>
      <div style={{ 
        textAlign: "center", 
        marginBottom: "20px", 
        padding: "10px", 
        backgroundColor: getStatusColor(), 
        color: "white", 
        borderRadius: "5px" 
      }}>
        WebSocket Status: {connectionStatus.toUpperCase()}
        {connectionStatus === "disconnected" && (
          <button 
            onClick={connectWebSocket}
            style={{ marginLeft: "10px", padding: "5px 10px" }}
          >
            Reconnect Now
          </button>
        )}
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
          {Object.entries(messages).length > 0 ? (
            Object.entries(messages).map(([symbol, msg], index) => (
              <tr key={index} style={{ textAlign: "center" }}>
                <td style={{ padding: "10px", border: "1px solid black" }}>{index + 1}</td>
                <td style={{ padding: "10px", border: "1px solid black" }}>{symbol}</td>
                <td style={{ padding: "10px", border: "1px solid black" }}>
                  {msg.timestamp ? new Date(msg.timestamp).toLocaleString() : "-"}
                </td>
                <td style={{ padding: "10px", border: "1px solid black" }}>{formatDecimal(msg.open)}</td>
                <td style={{ padding: "10px", border: "1px solid black" }}>{formatDecimal(msg.high)}</td>
                <td style={{ padding: "10px", border: "1px solid black" }}>{formatDecimal(msg.low)}</td>
                <td style={{ padding: "10px", border: "1px solid black" }}>{formatDecimal(msg.close)}</td>
                <td style={{ padding: "10px", border: "1px solid black" }}>{formatDecimal(msg.volume)}</td>
              </tr>
            ))
          ) : (
            <tr>
              <td colSpan="8" style={{ textAlign: "center", padding: "20px" }}>
                {connectionStatus === "connected" ? "Waiting for data..." : "Connect to see live data"}
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
};

export default WebSocketComponent;
