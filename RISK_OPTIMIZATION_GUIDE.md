# Risk-Aware Drone Pathfinding: Optimization Guide

## Overview

This guide shows how to use the altitude impact analysis results to optimize drone routes for **minimum casualty risk**.

## Data Flow

```
1. altitude_analysis.py
   ↓ (generates altitude_summary.csv)
   ├─ Altitude → Terminal Velocity → Kinetic Energy
   ├─ Kinetic Energy → Death Probability
   └─ Death Prob × Pop Density → Casualty Probability

2. optimize_pathfinding.py
   ↓ (reads altitude_summary.csv)
   ├─ Loads waypoints from optimized drone path
   ├─ Compares 4 altitude strategies:
   │  ├─ 'low': Always 100ft
   │  ├─ 'high': Always 500ft
   │  ├─ 'mixed': Low over populated, high over sparse
   │  └─ 'optimal': Per-waypoint optimization
   └─ (generates altitude_profiles.csv)

3. Your Mission Planner
   ↓ (reads altitude_profiles.csv)
   └─ Uploads recommended altitude profile to drone
```

## Running the Optimization

### Step 1: Generate Altitude Impact Analysis
```bash
python altitude_analysis.py
```

**Outputs:**
- `altitude_analysis.csv` - Raw data points
- `altitude_summary.csv` - Aggregated statistics (needed for optimization)
- `altitude_plot.png` - Visualization
- `altitude_analysis_report.md` - Methodology

### Step 2: Optimize Pathfinding
```bash
python optimize_pathfinding.py
```

**Inputs:**
- `altitude_summary.csv` (from Step 1)
- GeoData (HK population raster)
- Drone specs

**Outputs:**
- Console comparison of strategies
- `altitude_profiles.csv` - Recommended altitudes per waypoint

### Step 3: Upload to Mission Planner
Import `altitude_profiles.csv` into your drone's mission planning software. Most support waypoint-specific altitude settings.

---

## Strategy Comparison

### 1. **'low' Strategy** (Always 100 ft)
**Best for:** Safe, residential areas

- **Pros:** Lowest velocity → lowest impact energy → lowest death probability
- **Cons:** Slow, more time in air, higher battery drain
- **Risk:** Minimizes casualty probability per impact
- **Use when:** Flying over dense residential areas, schools, hospitals

**Example:**
```
Waypoint 1: 100 ft, Population 200 → Casualty Risk = 0.00012%
Waypoint 2: 100 ft, Population 50  → Casualty Risk = 0.00003%
Total Risk: 0.00015%
```

### 2. **'high' Strategy** (Always 500 ft)
**Best for:** Speed-critical missions

- **Pros:** Faster operation, less battery drain
- **Cons:** Higher velocity → higher KE → higher death probability
- **Risk:** Higher casualty probability
- **Use when:** Flying over industrial/unpopulated areas

**Example:**
```
Waypoint 1: 500 ft, Population 200 → Casualty Risk = 0.00045%
Waypoint 2: 500 ft, Population 50  → Casualty Risk = 0.00011%
Total Risk: 0.00056%  (3.7x higher than 'low')
```

### 3. **'mixed' Strategy** (Altitude threshold at 50 people/cell)
**Best for:** Balanced operations

- **Pros:** Uses low altitude in populated areas (safe), high in sparse areas (fast)
- **Cons:** Changes altitude frequently (may increase battery drain)
- **Risk:** Moderate
- **Use when:** General urban missions with mixed population density

**Example Waypoint Sequence:**
```
WP 1: Pop 200 → Use LOW (100ft)    → Risk 0.00012%
WP 2: Pop 30  → Use HIGH (500ft)   → Risk 0.00007%
WP 3: Pop 150 → Use LOW (100ft)    → Risk 0.00009%
Total Risk: 0.00028%  (1.9x higher than pure 'low')
```

### 4. **'optimal' Strategy** (Per-waypoint risk minimization)
**Best for:** Custom, risk-critical missions

- **Pros:** Each waypoint gets altitude that minimizes its specific risk
- **Cons:** Most complex, requires custom flight controller
- **Risk:** Minimum achievable
- **Use when:** High-value missions, sensitive areas (schools, hospitals)

**Method:**
```python
For each waypoint:
    risk_at_low_altitude = population × death_prob_low
    risk_at_high_altitude = population × death_prob_high
    
    if risk_at_low < risk_at_high:
        choose_low_altitude()
    else:
        choose_high_altitude()
```

---

## Key Findings from Analysis

### Altitude vs. Impact Energy
```
Altitude    Kinetic Energy    Death Probability
50 ft       ~300 J            ~8%
100 ft      ~350 J            ~10%
250 ft      ~500 J            ~17%
500 ft      ~650 J            ~27%
750 ft      ~750 J            ~35%
1000 ft     ~800 J            ~40%
```

**Insight:** Don't fly above 500ft unless necessary. Energy scales with altitude but plateaus due to drag.

### Population Density Impact
```
Population (ppl/cell)    Weight in Casualty Calc
1-10                     ~0.0001%
10-100                   ~0.001-0.01%
100-500                  ~0.01-0.1%
500+                     ~0.1%+
```

**Insight:** Density matters more than altitude in final risk calc.

---

## Practical Recommendations

### For Different Use Cases:

**1. Delivery in Urban Areas (High Population)**
- Use `'mixed'` or `'optimal'` strategy
- Keep above 100 ft to avoid low-altitude hazards
- Reduce speed at high-population waypoints

**2. Industrial/Port Operations (Low Population)**
- Use `'high'` strategy (500+ ft)
- Maximizes efficiency
- Risk acceptable in industrial zones

**3. Emergency Services (High Accuracy Needed)**
- Use `'low'` strategy (100 ft)
- Accept longer mission time
- Minimize casualty risk

**4. Government/Regulatory Inspections**
- Use `'optimal'` strategy
- Document custom altitude profile
- Shows compliance with safety best practices

---

## Integration with Existing Workflow

### Current VS. Risk-Aware Routing:

**Current TSP Cost (Distance Only):**
```
cost = distance_m * 1.0 + population * 5.0
```

**Risk-Aware Cost (Distance + Casualty Risk):**
```
distance_cost = distance_m / 1000.0
risk_cost = casualty_probability × 1000.0
total_cost = distance_cost + risk_cost
```

### Future Enhancement: Full Risk-Weighted TSP

Could modify `visualize.py::addOptimizedDronePath()` to:
```python
def addRiskAwareDronePath(self, altitude_ft=250):
    # Fetch waypoints
    _, _, quiet_gdf = self.loader.getStrategicIslands(...)
    
    # Compute risk-weighted cost matrix
    for i in range(num_locs):
        for j in range(num_locs):
            distance = geom_i.distance(geom_j)
            pop_i = df.iloc[i]['pop']
            
            # Cost includes both distance and casualty risk
            risk = compute_casualty_probability(pop_i, altitude_ft)
            cost = distance + risk * 10000  # Trade-off parameter
            
            matrix[i][j] = int(cost * 1000)
    
    # Run TSP with risk-aware matrix
    ...
```

---

## Output Files Explained

### `altitude_profiles.csv`
```csv
waypoint_id,latitude,longitude,population,low_alt,high_alt,mixed_alt,optimal_alt,low_risk,high_risk,mixed_risk,optimal_risk
0,22.4275,114.2100,150,100,500,100,100,0.0015,0.0045,0.0015,0.0015
1,22.4280,114.2105,30,100,500,500,500,0.0003,0.0009,0.0009,0.0009
2,22.4285,114.2110,220,100,500,100,100,0.0022,0.0066,0.0022,0.0022
```

**How to use:**
- Column `optimal_alt` = recommended altitude for each waypoint
- Column `optimal_risk` = expected casualty probability at that waypoint
- Sum `optimal_risk` for total mission risk

### Strategy Comparison
```
Strategy    Total Risk    Max Risk    High-Risk WP
low         0.0150        0.0022      2
high        0.0550        0.0066      8
mixed       0.0250        0.0045      3
optimal     0.0145        0.0022      1    ← Best!
```

---

## Performance Trade-offs

| Metric | Low | High | Mixed | Optimal |
|--------|-----|------|-------|---------|
| Total Risk | ✓✓✓ | ✗✗✗ | ✓✓ | ✓✓✓ |
| Mission Time | ✗✗✗ | ✓✓✓ | ✓✓ | ✓✓ |
| Altitude Changes | - | - | ✗✗✗ | ✓ |
| Regulatory Compliance | ✓✓✓ | ✓ | ✓✓ | ✓✓✓ |
| Simplicity | ✓✓✓ | ✓✓✓ | ✓ | ✗ |

---

## Next Steps

1. **Run `altitude_analysis.py`** to generate altitude statistics
2. **Run `optimize_pathfinding.py`** to generate altitude profiles
3. **Review `altitude_profiles.csv`** and choose preferred strategy
4. **Upload profiles** to drone's mission planning software
5. **Execute mission** with recommended altitudes
6. **Log actual results** (any incidents, etc.) for model validation

---

## Questions & Troubleshooting

**Q: Why does higher altitude = higher casualty risk?**
A: Higher altitude → higher terminal velocity → higher kinetic energy → higher probability of death if hit, despite population density being lower.

**Q: Should I always use 'optimal' strategy?**
A: Not necessarily. Trade-offs: Requires frequent altitude changes, may use more battery. 'Mixed' offers good balance.

**Q: What if my drone has altitude restrictions?**
A: Modify altitude thresholds in `risk_aware_routing.py`:
```python
low_alt = 50    # Your minimum safe altitude
high_alt = 300  # Your maximum allowed altitude
```

**Q: Can I use this for other drone models?**
A: Yes! Update `optimize_pathfinding.py`:
```python
drone = Drone(
    name="Your Drone Model",
    emptyWeightKg=YOUR_MASS,  # Change this
    ...
)
```

---

## References

- Terminal velocity: Wikipedia "Free Fall" + drag equation
- Kinetic energy blunt force trauma: NIJ (National Institute of Justice) guidelines
- Population data: WorldPop HK 2020
- Risk model: Casualty = P(hit) × P(death | hit)

