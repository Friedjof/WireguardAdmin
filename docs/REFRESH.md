# WebSocket Status Refresh Configuration

Das Status-Refresh-System kann auf verschiedene Weise konfiguriert werden:

## Konfigurationsmöglichkeiten (nach Priorität)

### 1. Environment Variable (Server-Level)
```bash
# Docker Compose / Environment
WS_REFRESH_INTERVAL_MS=3000  # 3 Sekunden

# Docker Run
docker run -e WS_REFRESH_INTERVAL_MS=3000 vpn-manager
```

### 2. URL Parameter (Benutzer-Level)
```
http://localhost:5000/?refresh=2
http://localhost:5000/peers/1?refresh=10
```
**Hinweis**: URL-Parameter werden in Sekunden angegeben, automatisch in Millisekunden umgewandelt.

### 3. JavaScript API (Runtime)
```javascript
// Intervall zur Laufzeit ändern
window.statusRefresh.setInterval(8000);  // 8 Sekunden

// System stoppen/starten
window.statusRefresh.stop();
window.statusRefresh.start();

// Manueller Refresh
window.statusRefresh.triggerRefresh();
```

### 4. Standard-Werte
- **Default**: 5000ms (5 Sekunden)
- **Minimum**: 1000ms (1 Sekunde) empfohlen
- **Maximum**: Unbegrenzt

## Beispiele

### Schnelle Updates für Entwicklung
```bash
WS_REFRESH_INTERVAL_MS=1000  # 1 Sekunde
```

### Langsamere Updates für Produktion
```bash
WS_REFRESH_INTERVAL_MS=10000  # 10 Sekunden
```

### Benutzer-spezifische Anpassung
```
# Für Live-Monitoring
http://vpn-manager.example.com/?refresh=2

# Für normale Nutzung  
http://vpn-manager.example.com/?refresh=15
```

## Browser-Konsole Debugging

```javascript
// Aktuelles Intervall anzeigen
console.log(window.statusRefresh.refreshInterval);

// Status anzeigen
console.log('Active:', window.statusRefresh.isActive);

// Sofortiger Test
window.statusRefresh.triggerRefresh();
```