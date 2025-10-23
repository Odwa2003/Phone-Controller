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
      
      // Close existing connection if same role is reconnecting
      if (entry[role] && entry[role].readyState === 1) {
        entry[role].close();
      }
      
      entry[role] = ws;
      ws.pairId = pairId;
      ws.role = role;
      console.log(`✅ Registered ${role} for pair ${pairId}`);
      
      // Notify both sides about pairing status
      ws.send(JSON.stringify({ 
        ok: true, 
        registered: true,
        paired: !!entry.pc && !!entry.phone
      }));
      
      // Notify the other side if both are connected
      const otherRole = role === "phone" ? "pc" : "phone";
      if (entry[otherRole] && entry[otherRole].readyState === 1) {
        entry[otherRole].send(JSON.stringify({
          type: "partner_connected",
          role: role
        }));
        console.log(`🔗 Notified ${otherRole} that ${role} connected for pair ${pairId}`);
      }
      return;
    }

    // 2️⃣ Relay messages between phone and PC
    if (!pairId || !pairs.has(pairId)) {
      console.warn(`⚠️ Unknown pairId: ${pairId}`);
      return;
    }

    const entry = pairs.get(pairId);

    // Determine target based on sender's role
    let target;
    let targetRole;
    if (role === "phone") {
      target = entry.pc;
      targetRole = "pc";
    } else if (role === "pc") {
      target = entry.phone;
      targetRole = "phone";
    } else {
      console.warn(`⚠️ Unknown role: ${role}`);
      return;
    }

    if (target && target.readyState === 1) {
      target.send(JSON.stringify(data));
      console.log(`➡️ Relayed '${type}' from ${role} → ${targetRole} for pair ${pairId}`);
    } else {
      console.warn(`⚠️ Target ${targetRole} not ready for pair ${pairId}`);
      // Notify sender that target is not available
      if (ws.readyState === 1) {
        ws.send(JSON.stringify({
          ok: false,
          error: `Target ${targetRole} not connected`
        }));
      }
    }
  });

  ws.on("close", () => {
    if (ws.pairId && ws.role && pairs.has(ws.pairId)) {
      const entry = pairs.get(ws.pairId);
      
      // Notify the other side about disconnection
      const otherRole = ws.role === "phone" ? "pc" : "phone";
      if (entry[otherRole] && entry[otherRole].readyState === 1) {
        entry[otherRole].send(JSON.stringify({
          type: "partner_disconnected",
          role: ws.role
        }));
        console.log(`🔔 Notified ${otherRole} that ${ws.role} disconnected for pair ${ws.pairId}`);
      }
      
      // Clean up
      delete entry[ws.role];
      console.log(`❌ ${ws.role} disconnected for ${ws.pairId}`);
      
      // Remove pair if both sides are disconnected
      if (!entry.pc && !entry.phone) {
        pairs.delete(ws.pairId);
        console.log(`🗑️  Removed empty pair ${ws.pairId}`);
      }
    }
  });

  ws.on("error", (error) => {
    console.error(`❌ WebSocket error for ${ws.role || 'unknown'} (${ws.pairId || 'no pair'}):`, error);
  });
});

// Clean up empty pairs periodically
setInterval(() => {
  let cleaned = 0;
  for (const [pairId, entry] of pairs.entries()) {
    if ((!entry.pc || entry.pc.readyState !== 1) && (!entry.phone || entry.phone.readyState !== 1)) {
      pairs.delete(pairId);
      cleaned++;
    }
  }
  if (cleaned > 0) {
    console.log(`🧹 Cleaned up ${cleaned} inactive pairs`);
  }
}, 60000); // Check every minute

console.log("🚀 Relay server started successfully");