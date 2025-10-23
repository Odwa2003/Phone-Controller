// relay_server.js
import { WebSocketServer } from "ws";

const PORT = process.env.PORT || 8080;
const wss = new WebSocketServer({ port: PORT });

console.log(`✅ Relay server running on port ${PORT}`);

const pairs = new Map(); // { pairId: { pc: ws, phone: ws } }

wss.on("connection", (ws) => {
  console.log("New connection");

  ws.on("message", (msg) => {
    let data;
    try {
      data = JSON.parse(msg);
    } catch {
      return ws.send(JSON.stringify({ ok: false, error: "Invalid JSON" }));
    }

    const { role, pairId, payload } = data;

    // 1️⃣ Register a connection
    if (data.type === "register") {
      if (!pairId || !role) {
        return ws.send(JSON.stringify({ ok: false, error: "Missing pairId or role" }));
      }

      if (!pairs.has(pairId)) pairs.set(pairId, {});
      const entry = pairs.get(pairId);
      entry[role] = ws;
      ws.pairId = pairId;
      ws.role = role;
      console.log(`Registered ${role} for ${pairId}`);
      ws.send(JSON.stringify({ ok: true, registered: true }));
      return;
    }

    // 2️⃣ Relay messages between PC and phone
    if (data.type === "relay") {
      const entry = pairs.get(pairId);
      if (!entry) return;
      const target = role === "pc" ? entry.phone : entry.pc;
      if (target && target.readyState === 1) {
        target.send(JSON.stringify(payload));
      }
      return;
    }
  });

  ws.on("close", () => {
    if (ws.pairId && pairs.has(ws.pairId)) {
      const entry = pairs.get(ws.pairId);
      delete entry[ws.role];
      console.log(`${ws.role} for ${ws.pairId} disconnected`);
      if (!entry.pc && !entry.phone) pairs.delete(ws.pairId);
    }
  });
});
