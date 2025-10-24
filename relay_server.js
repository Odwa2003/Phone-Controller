import { WebSocketServer } from "ws";

const PORT = process.env.PORT || 8080;
const wss = new WebSocketServer({ port: PORT });

console.log(`✅ Relay server running on port ${PORT}`);

const pairs = new Map(); // pairId -> { pc, phone }

wss.on("connection", (ws) => {
  console.log("📡 New connection");

  ws.on("message", (msg) => {
    let data;
    try {
      data = JSON.parse(msg);
    } catch {
      return ws.send(JSON.stringify({ ok: false, error: "Invalid JSON" }));
    }

    const { type, role, pairId } = data;

    // 1️⃣ Registration step
    if (type === "register") {
      if (!pairId || !role) {
        return ws.send(JSON.stringify({ ok: false, error: "Missing pairId or role" }));
      }

      if (!pairs.has(pairId)) pairs.set(pairId, {});
      const entry = pairs.get(pairId);
      entry[role] = ws;
      ws.pairId = pairId;
      ws.role = role;
      console.log(`✅ Registered ${role} for pair ${pairId}`);
      ws.send(JSON.stringify({ ok: true, registered: true }));
      return;
    }

    // 2️⃣ Relay any other message from phone → PC (or PC → phone)
    if (!pairId || !pairs.has(pairId)) return;
    const entry = pairs.get(pairId);
    const target = role === "phone" ? entry.pc : entry.phone;

    if (target && target.readyState === 1) {
      target.send(JSON.stringify(data)); // send command as-is
      console.log(`➡️ Relayed '${type}' from ${role} → target`);
    } else {
      console.warn(`⚠️ Target not ready for pair ${pairId}`);
    }
  });

  ws.on("close", () => {
    if (ws.pairId && pairs.has(ws.pairId)) {
      const entry = pairs.get(ws.pairId);
      delete entry[ws.role];
      console.log(`❌ ${ws.role} disconnected for ${ws.pairId}`);
      if (!entry.pc && !entry.phone) pairs.delete(ws.pairId);
    }
  });
});
