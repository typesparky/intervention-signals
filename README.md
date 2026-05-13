# Intervention Signal System

Unified OSINT-powered intervention signal detection system for military/geopolitical event monitoring with prediction market integration for trading opportunities.

## Overview

This system monitors real-time RSS feeds, APIs, and OSINT data sources to detect intervention events (military conflicts, energy infrastructure disruptions, geopolitical escalations) that may create trading opportunities in prediction markets.

## Data Sources

### RSS Feeds (2 working)
- **BBC World News** - Global geopolitical coverage
- **Al Jazeera World** - Middle East and conflict coverage

### API Sources (8 total)

**Military/Geopolitical:**
- **GDELT Global Events** - Worldwide event database
- **ADS-B Exchange** - Military aircraft tracking

**OSINT Infrastructure:**
- **NASA FIRMS** - Thermal anomaly detection at energy infrastructure (refineries, pipelines, terminals)
- **ACLED** - Armed conflict data in energy-critical regions
- **AIS Maritime** - Vessel tracking through strategic chokepoints (Hormuz, Bab el-Mandeb, Suez, etc.)

## Features

### Signal Generation
- Multi-source event correlation
- Confidence scoring (0.0-1.0) with OSINT boosters
- Signal type classification:
  - military_action
  - force_deployment
  - tension_escalation
  - military_exercise
  - diplomatic_activity
  - geopolitical_event

### OSINT-Enhanced Detection
- **Thermal anomalies** at 14 critical infrastructure sites (+0.1 to +0.3 confidence)
- **Conflict fatalities** in energy-critical regions (+0.1 to +0.3 confidence)
- **Military vessels** in strategic chokepoints (+0.4 confidence)
- **Stopped tankers** at chokepoints (+0.3 confidence)

### Prediction Market Integration
- Polymarket and Manifold correlation
- Arbitrage opportunity detection
- Market relevance scoring
- Spread and liquidity analysis

## Installation

```bash
# Clone repository
git clone https://github.com/typesparky/intervention-signals.git
cd intervention-signals

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Configuration

### 1. Get API Keys

**NASA FIRMS (FREE):**
1. Register at: https://urs.earthdata.nasa.gov/
2. Add to `config/sources.yaml`:
   ```yaml
   nasa_firms:
     username: "your_email@example.com"
     password: "your_password"
   ```

**ACLED (FREE):**
1. Login at: https://acleddata.com/
2. Add to `config/sources.yaml`:
   ```yaml
   acled:
     username: "your_email@example.com"
     password: "your_password"
   ```

**AIS Maritime (PAID or Free Alternative):**
- Option A (PAID): https://www.marinetraffic.com/en/ais-api-services
- Option B (FREE): https://aisstream.io/
- Option C (FREE): https://www.vesselfinder.com/api

### 2. Update Configuration

Edit `config/sources.yaml` with your credentials:

```yaml
nasa_firms:
  username: "your_edl_email"
  password: "your_edl_password"

acled:
  username: "your_acled_email"
  password: "your_acled_password"

ais_maritime:
  api_key: "your_ais_key"  # Optional
  simulated_mode: false  # Set to true for testing
```

## Usage

### Single Scan

```bash
source venv/bin/activate
python main.py
```

### Continuous Monitoring

```bash
source venv/bin/activate
python src/orchestrator.py

# Custom interval (e.g., 10 minutes)
python src/orchestrator.py --interval 600
```

### Check Status

```bash
python src/orchestrator.py --status
```

### View Alerts

```bash
# Alerts from last 6 hours (default)
python src/orchestrator.py --alerts 6

# Alerts from last 24 hours
python src/orchestrator.py --alerts 24
```

### Cleanup Old Data

```bash
# Delete events older than 30 days
python src/orchestrator.py --cleanup 30

# Delete events older than 7 days
python src/orchestrator.py --cleanup 7
```

## Monitored Infrastructure

### NASA FIRMS (14 sites)
- Ras Tanura Refinery (Saudi Arabia)
- Jubail Industrial City (Saudi Arabia)
- Yanbu Refinery (Saudi Arabia)
- Ruwais Refinery (UAE)
- Fujairah Oil Terminal (UAE)
- Kharg Island Terminal (Iran)
- Kirkuk-Ceyhan Pipeline Corridor
- Strait of Hormuz Terminals
- Bab el-Mandeb Shipping Lane
- Skikda & Arzew Complexes (Algeria)
- East-West Pipeline (Saudi Arabia)

### ACLED Regions (3 areas)
- **Middle East** - 12 countries (Saudi Arabia, Iran, Iraq, UAE, Qatar, Kuwait, Oman, Yemen, Syria, Jordan, Lebanon, Israel)
- **North Africa** - 6 countries (Algeria, Libya, Egypt, Tunisia, Morocco, Sudan)
- **Strategic Chokepoints** - 7 countries (Yemen, Oman, Iran, Eritrea, Djibouti, Somalia, Sudan)

### AIS Chokepoints (5 critical)
- Strait of Hormuz (54km width, ~15 tankers/day)
- Bab el-Mandeb (29km width, ~5 tankers/day)
- Suez Canal (205km width, ~50 tankers/day)
- Bosphorus Strait (3.4km width, ~3 tankers/day)
- Strait of Malacca (250km width, ~30 tankers/day)

## Signal Thresholds

| Level | Confidence | Description |
|--------|-------------|-------------|
| CRITICAL | >0.9 | Immediate action required |
| HIGH | >0.7 | Significant opportunity |
| MODERATE | >0.5 | Monitor closely |
| LOW | <0.5 | Informational only |

## Authentication

### ACLED OAuth
- Access tokens expire in 24 hours
- Refresh tokens valid for 14 days
- System automatically refreshes tokens
- Uses secure OAuth 2.0 flow

### NASA FIRMS
- Uses EDL (Earthdata Login) credentials
- Credentials stored as `email:password` in config
- No token expiration (long-lived sessions)

## Architecture

```
intervention-signals/
├── src/
│   ├── base_feed_adapter.py      # Base adapter class
│   ├── rss_adapter.py             # RSS feed handling
│   ├── gdelt_adapter.py           # GDELT API
│   ├── adsb_adapter.py            # ADS-B flight tracking
│   ├── firms_adapter.py            # NASA FIRMS thermal data
│   ├── acled_adapter.py            # ACLED conflict data (OAuth)
│   ├── ais_adapter.py             # AIS maritime tracking
│   ├── event_storage.py           # SQLite database
│   ├── signal_generator.py        # Signal generation logic
│   ├── signal_analyzer.py         # OSINT analysis
│   ├── arbitrage_integrator.py    # Prediction market correlation
│   └── orchestrator.py            # Main coordinator
├── config/
│   └── sources.yaml               # Configuration file
├── data/
│   └── events.db                 # SQLite database
├── logs/
│   └── orchestrator.log           # System logs
├── output/                       # Analysis results
├── venv/                         # Python virtual environment
├── requirements.txt              # Dependencies
└── README.md                      # This file
```

## Dependencies

- feedparser>=6.0.10 - RSS feed parsing
- pyyaml>=6.0.1 - Configuration files
- requests>=2.31.0 - HTTP requests
- httpx>=0.27.0 - Async HTTP client (AIS adapter)

## Performance

- Single cycle: 30-60 seconds
- Memory usage: ~50-100 MB
- Storage: ~1 MB per 1000 events
- Token refresh: Automatic (every 24 hours for ACLED)

## Troubleshooting

### ACLED Token Expired
```
ERROR: ACLED authentication failed
Response: 401
```
Solution: Check username/password in config. System will auto-refresh on next run.

### NASA FIRMS Authentication Failed
```
ERROR: NASA FIRMS API key required
```
Solution: Register at https://urs.earthdata.nasa.gov/ and update config with `username` and `password`.

### No Events Found
- Check feed URLs are accessible
- Verify API keys are correct
- Check network connectivity
- Review keywords in config

## Security

- Credentials stored in `config/sources.yaml` (add to .gitignore!)
- ACLED uses secure OAuth 2.0 with token refresh
- No sensitive data logged to console
- Database file permissions: 600

## License

MIT License - Use freely for your monitoring needs.

## Contributing

For issues, feature requests, or questions:
- GitHub: https://github.com/typesparky/intervention-signals
- Email: For collaboration inquiries

## Disclaimer

This system is for informational and research purposes only. Always verify signals from multiple sources before making trading decisions.
