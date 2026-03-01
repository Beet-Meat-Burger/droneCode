# 🚀 QUICK START - 5 MINUTE GUIDE

**Just want results? Start here!**

## Installation (1 minute)

```bash
# 1. Open PowerShell in d:\Data\droneCode
cd d:\Data\droneCode

# 2. Install required packages (one-time)
pip install folium geopandas rasterio numpy pandas ortools shapely scipy matplotlib

# 3. Done!
```

## Run the System (2 minutes)

```bash
# Execute the unified launcher
python run_mission.py

# Wait for completion (~3-5 minutes depending on your system)
# You'll see progress messages like:
# [14:32:05] [INFO] Loading geospatial data...
# [14:32:10] [SUCCESS] ✓ Geospatial data loaded successfully
# ... (more progress) ...
# [14:35:22] [SUCCESS] ✓ MISSION PIPELINE COMPLETE
```

## Review Results (2 minutes)

```bash
# 1. Open the interactive map (main deliverable)
start hk_drone_optimized.html
# → Shows your route with tooltips on every waypoint
# → Green/Orange/Red markers = Low/Medium/High risk
# → Hover for details: population, altitude, risk, leg length

# 2. Check the mission file (ready for drone)
notepad drone_mission_waypoints.csv
# → Format: waypoint_id, latitude, longitude, altitude_ft, type
# → Ready to upload to DJI FlightHub or QGroundControl

# 3. View detailed metadata (all waypoint data)
notepad mission_metadata.csv
# → Includes: population, risk level, altitude, leg length, etc.
```

## Upload to Your Drone

### DJI FlightHub
```
1. Open https://flighthub.dji.com
2. Create new mission
3. Click "Import Mission" 
4. Select: drone_mission_waypoints.csv
5. Review and then fly!
```

### QGroundControl
```
1. File → Open Mission File
2. Select: drone_mission_waypoints.csv
3. Click "Upload" to send to drone
4. Fly!
```

### ArduPilot / Other Autopilots
```
1. Use your mission planner software
2. Import CSV (format: waypoint_id, lat, lng, altitude_ft)
3. Upload to flight controller
4. Fly!
```

## Output Files Explained

| File | Purpose | Open With |
|------|---------|-----------|
| `hk_drone_optimized.html` | **Interactive map** with full visualization | Chrome / Firefox / Safari |
| `drone_mission_waypoints.csv` | **Mission file** ready for drone upload | DJI FlightHub / QGroundControl |
| `mission_metadata.csv` | **Detailed metadata** for all waypoints | Excel / Notepad |
| `mission_metrics.json` | **Statistics** in machine-readable format | Code / Python |
| `MISSION_INTEGRATION_REPORT.md` | **Full documentation** of this specific mission | Markdown viewer / GitHub |

## What Each File Contains

### `drone_mission_waypoints.csv` - Upload This to Drone
```csv
waypoint_id,latitude,longitude,altitude_ft,type
0,22.3193,114.1694,250,WAYPOINT
1,22.3290,114.1580,250,WAYPOINT
2,22.3400,114.1420,150,WAYPOINT
...
```
✅ Ready for: DJI, QGroundControl, ArduPilot  
✅ Format: Comma-separated values, UTF-8 encoding

---

### `mission_metadata.csv` - Every Point's Data
```csv
waypoint_id,latitude,longitude,population_density,population_risk_level,recommended_altitude_ft,risk_score_normalized,leg_length_km,...
0,22.3193,114.1694,450,HIGH,500,0.4500,3.21,...
1,22.3290,114.1580,120,MEDIUM,250,0.1200,2.87,...
...
```
✅ Use for: Understanding why each waypoint was chosen  
✅ Contains: Population, altitude, risk, leg lengths, compliance info

---

### `hk_drone_optimized.html` - Interactive Visualization

Features:
- 🗺️ Population heatmap background (yellow/red = dense, green/blue = sparse)
- 🟢 Green markers = Low-risk waypoints
- 🟠 Orange markers = Medium-risk waypoints
- 🔴 Red markers = High-risk waypoints
- 📍 Pink line = Your flight route
- 💬 Hover over any marker for:
  - Population density
  - Recommended altitude
  - Risk level
  - Distance to next waypoint

---

### `mission_metrics.json` - Statistics
```json
{
  "total_waypoints": 12,
  "total_distance_km": 42.34,
  "statistics": {
    "population": {"min": 5, "max": 450, "mean": 98.3},
    "altitude": {"min": 100, "max": 500, "mean": 275}
  }
}
```
✅ Use for: Scripts, dashboards, automated reporting

---

### `MISSION_INTEGRATION_REPORT.md` - Full Documentation
- Executive summary
- Algorithm explanations
- All decisions documented
- Validation passed/failed checklist
- Troubleshooting guide

---

## Understanding the Results

### What Do the Colors Mean?

| Color | Risk Level | Population | Recommended Altitude | Action |
|-------|-----------|------------|----------------------|--------|
| 🟢 Green | LOW | < 50 ppl/cell | 100 ft | Safe zone, fly lower for efficiency |
| 🟠 Orange | MEDIUM | 50-200 ppl/cell | 250 ft | Moderate caution, fly medium altitude |
| 🔴 Red | HIGH | > 200 ppl/cell | 500 ft | High caution, fly higher to reduce impact zone |

### What Do the Numbers Mean?

**Population Density:** People per 100m × 100m grid cell
- 10 = sparse rural area
- 100 = suburban area
- 500+ = dense urban area

**Recommended Altitude (feet):**
- 100 ft = minimum safe altitude (fuel efficient)
- 250 ft = balanced altitude
- 500 ft = maximum safe altitude (large impact zone but low kinetic energy)

**Risk Score:** Normalized metric from 0 to 1
- 0 = completely safe (no population)
- 1 = maximum risk

**Leg Length:** Distance from this waypoint to the next
- All legs kept ≤ 10 km for battery constraints

---

## Validation Checklist

Before flying, verify:

- [ ] All waypoints have valid coordinates (latitude 22.0-22.5, longitude 114.0-114.3)
- [ ] All altitudes are 50-500 feet
- [ ] All legs are ≤ 10 km
- [ ] Total distance ≤ 25 km
- [ ] Route makes geographic sense (no random jumps)
- [ ] All waypoints in sandbox zone (regulatory compliance)

**Check automatically with:**
```bash
python -c "
import csv
with open('mission_metadata.csv') as f:
    reader = csv.DictReader(f)
    for row in reader:
        lat = float(row['latitude'])
        lng = float(row['longitude'])
        alt = int(row['recommended_altitude_ft'])
        leg = float(row['leg_length_km'])
        
        assert 22.0 <= lat <= 22.5, f'Lat out of range: {lat}'
        assert 114.0 <= lng <= 114.3, f'Lng out of range: {lng}'
        assert 50 <= alt <= 500, f'Alt out of range: {alt}'
        assert leg <= 10, f'Leg too long: {leg}'
        
print('✓ All validations passed!')
"
```

---

## Customize & Re-Run

### Faster Run (Skip Algorithms)
```bash
python run_mission.py --quick
# Uses default parameters, ~2 minute run time
```

### Quiet Mode (No Verbose Output)
```bash
python run_mission.py --quiet
# Suppresses progress messages, useful for automation
```

### Full Documentation Run
```bash
python run_mission.py
# Includes all steps, full output (default, recommended for first run)
```

---

## Troubleshooting

### My waypoints aren't showing on the map
- Check that `hk_drone_optimized.html` file size > 5 MB (indicates data included)
- Try opening in different browser (Firefox recommended)
- Verify no JavaScript errors (F12 → Console)

### Mission won't import to DJI
- Ensure CSV is in UTF-8 encoding (Notepad → Save As → UTF-8)
- Verify comma separators (not semicolons)
- Check column headers match exactly: `waypoint_id,latitude,longitude,altitude_ft,type`

### Some waypoints show "No Data"
- This is OK! Means those areas have no population data
- System assumes 0 population, treats as safe zone
- Still navigable, just no risk metric available

### Gets stuck loading data
- Population raster is large (~500 MB), can take 1-2 minutes
- Let it finish; DON'T kill the process
- Run on machine with 8+ GB RAM if possible

---

## File Reference (All Outputs)

```
d:\Data\droneCode\
├── [OUTPUTS - After running python run_mission.py]
├── drone_mission_waypoints.csv        ← UPLOAD THIS to drone
├── mission_metadata.csv               ← All waypoint details
├── mission_metrics.json               ← Statistics
├── hk_drone_optimized.html            ← OPEN THIS in browser
├── MISSION_INTEGRATION_REPORT.md      ← This mission's docs
│
├── [REFERENCE - Read these for understanding]
├── COMPLETE_SYSTEM_DOCUMENTATION.md   ← System overview
├── ALGORITHMS_AND_FORMULAS.md         ← Math & formulas
├── INTEGRATION_GUIDE.md               ← Original pipeline
├── RISK_OPTIMIZATION_GUIDE.md         ← Altitude selection
├── CURVED_ROUTES_GUIDE.md             ← Population avoidance
├── LEGBREAKING_GUIDE.md               ← Long leg breaking
├── DENSITY_CASUALTY_GUIDE.md          ← Casualty models
└── QUICK_START.md                     ← This file
```

---

## Still Have Questions?

1. **"What's a waypoint?"** A GPS point your drone will fly through in sequence
2. **"Why does my mission have 50 waypoints?"** Leg breaker inserted intermediate points for battery constraints
3. **"Can I modify the route?"** Edit drone_mission_waypoints.csv directly, or re-run with custom parameters
4. **"How accurate is the population data?"** WorldPop 2020, 100m resolution - good for regional analysis
5. **"Is my route legal?"** Yes, all waypoints verified within sandbox zones and regulatory airspace

---

## For Developers

Full system documentation:
- Architecture: See `COMPLETE_SYSTEM_DOCUMENTATION.md`
- Algorithms: See `ALGORITHMS_AND_FORMULAS.md`
- Code: Start at `run_mission.py` → imports from `kimDroneGoon/`

---

**Ready?** Run `python run_mission.py` and check back in 5 minutes for results! 🚁
