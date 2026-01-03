import { Server } from "socket.io";
import { ngrok } from "@ngrok/ngrok";

const PORT = process.env.PORT || 3000;

const io = new Server(PORT, {
  cors: { origin: "*" }
});

console.log(`Socket.IO escuchando en puerto ${PORT}`);

io.on("connection", socket => {
  console.log("Cliente conectado");

  socket.on("cmd", msg => {
    console.log("CMD:", msg);

    if (msg.cmd === "ping") {
      socket.emit("event", {
        event: "pong",
        payload: { time: Date.now() }
      });
    }
  });
});

// Iniciar ngrok para acceso remoto
async function startNgrok() {
  try {
    const url = await ngrok.connect({
      addr: PORT,
      proto: "tcp"
    });
    console.log(`
╔════════════════════════════════════════╗
║  Socket.IO Servidor en ejecución      ║
╠════════════════════════════════════════╣
║  URL LOCAL:  http://localhost:${PORT}     ║
║  URL PÚBLICA: ${url.url()}           ║
╚════════════════════════════════════════╝
    `);
  } catch (err) {
    console.error("Error iniciando ngrok:", err.message);
    console.log("\n⚠️  Para usar ngrok, necesitas token de autenticación:");
    console.log("   1. Regístrate en https://ngrok.com");
    console.log("   2. Obtén tu token en https://dashboard.ngrok.com/auth/your-authtoken");
    console.log("   3. Configura el token: ngrok config add-authtoken <TOKEN>");
    console.log("\nMientras, el servidor Socket.IO sigue funcionando localmente.");
  }
}

startNgrok();
