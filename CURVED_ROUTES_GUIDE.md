# Curved Routes for Population Avoidance

## You're Not Crazy — This Is Real Flight Planning!

Commercial aviation does this constantly. Planes don't fly in straight lines; they follow corridors that balance:
- **Distance/fuel efficiency** (shorter paths cost less)
- **Population safety** (avoid flying over cities when possible)
- **Airspace compliance** (follow established routes)

Your idea is exactly the same principle: **trade some distance for significantly reduced casualty risk**.

---

## The Math Behind Curved Routes

### Straight Path: Direct but Risky
```
Start → ─────────→ End

Problem: Flies directly over any populated areas in between
Risk: Cumulative casualty exposure along the entire path
```

### Curved Path: Longer but Safer
```
Start → ╱───────╲ → End
         (curve around homes/schools)

Benefit: Avoids high-population zones
Trade-off: Extra distance traveled
```

### Casualty Exposure Formula

Instead of looking at a single point, we integrate along the path:

$$\text{Exposure} = \int_{\text{path}} P(\text{population}) \times P(\text{death|hit}) \, ds$$

Where:
- **P(population)** = population density at point along path
- **P(death|hit)** = death probability from impact at altitude
- **ds** = infinitesimal distance segment

For curved path vs straight:
```
Straight Path:  1.0 km through city center
                Exposure = 100 × 0.25 = 25

Curved Path:    1.2 km around the city
                Exposure = 10 × 0.25 = 2.5  (90% reduction!)
```

---

## When Curved Routes Make Sense

### ✓ Worth It:
- **School/hospital zones** — Dense population, high sensitivity
- **Residential areas** — Constant population exposure
- **City centers** — Concentrated population
- **Risk-critical missions** — Government, emergency response

### ✗ Not Worth It:
- **Industrial zones** — Sparse population
- **Farmland** — Very low population
- **Open water/parks** — Essentially zero population
- **Speed-critical missions** — Time is the priority

---

## Curved Route Strategies

### 1. Simple Offset (10% curve factor)
Perpendicular offset from the straight line based on population density

```
Population Density: High
        │
Straight│  x x x x          Curved route
        │ x       x            ╱─────╲
        └─────────────────────────────
           City center
```

**How it works:**
1. Find point of maximum population along straight line
2. Calculate perpendicular vector
3. Offset by distance proportional to population density
4. Result: 1-2 extra waypoints per segment

**Implementation:**
```python
optimizer = CurvedRouteOptimizer(geo_loader, altitude_ft=250)
curved_path = optimizer.generate_multi_curved_path(
    straight_waypoints, 
    curve_factor=0.10,
    num_intermediate=3
)
```

### 2. Gradient Descent (Advanced)
Follow the "least populated" path between waypoints

**Concept:**
```python
# At each point along the path, sample population in all directions
# Move slightly toward lower-population areas
# Result: smooth curve that naturally avoids density
```

(Not implemented yet, but could be added)

### 3. Drone Corridor Concepts (Professional)
Pre-planned routes similar to airspace corridors:
- Fixed altitude to reduce air-to-ground collision risk
- Pre-approved by authorities
- Same route used for all missions (efficiency)

---

## Running the Analysis

### Step 1: Generate Analysis
```bash
python analyze_curved_routes.py
```

**Output:**
```
POPULATION AVOIDANCE ANALYSIS
========================================================================
Curve       Exposure         Distance     Risk Red.    Dist Inc.
────────────────────────────────────────────────────────────────────
STRAIGHT    0.1234           3.45 km      baseline     baseline
0.05        0.1180           3.52 km      4.4%         2.0%
0.10        0.1095           3.61 km      11.3%        4.6%        ← Good tradeoff
0.15        0.0987           3.72 km      20.0%        7.8%
0.20        0.0834           3.85 km      32.4%        11.5%

[*] CONCLUSION:
  ✓ YES, curved routing is worthwhile!
  → Recommended curve factor: 0.10
  → Risk reduction: 11.3%
  → Extra distance: 4.6%
  → Efficiency ratio: 2.46
```

### What This Means:
- **Curve factor 0.10** = 11% less casualty exposure
- **Cost:** Only 4.6% more distance (0.16 km extra)
- **Efficiency ratio 2.46** = 2.46x better risk reduction per extra distance

---

## Real-World Examples

### Example 1: Route Through Dense City
```
Straight:
- Distance: 5.0 km
- Exposure: 0.45
- Exposure/km: 0.090

Curved (factor 0.12):
- Distance: 5.3 km (+6%)
- Exposure: 0.28 (-38%)
- Exposure/km: 0.053 (-41%)

Decision: ✓ CURVED — Worth the extra 0.3 km
```

### Example 2: Route Over Industrial Zone
```
Straight:
- Distance: 8.0 km
- Exposure: 0.08 (very low population)
- Exposure/km: 0.010

Curved (factor 0.15):
- Distance: 8.6 km (+7.5%)
- Exposure: 0.07 (-12%)
- Exposure/km: 0.008 (-20%)

Decision: ✗ STRAIGHT — Not worth 0.6 km extra for 12% reduction
```

### Example 3: Route Near School
```
Straight:
- Distance: 2.0 km
- Crosses school playing field (exposure: 0.35)

Curved (factor 0.20):
- Distance: 2.3 km (+15%)
- Avoids school entirely (exposure: 0.05)
- Saving: 0.30 exposure units (-86%)

Decision: ✓ CURVED MANDATORY — Safety-critical area
```

---

## Implementation Details

### Curve Factor Interpretation
- **0.0** = Straight line (no curving)
- **0.05** = Very gentle curve (2-3% distance increase)
- **0.10** = Moderate curve (5-7% distance increase) ← Recommended default
- **0.15** = Aggressive curve (8-12% distance increase)
- **0.20** = Very aggressive curve (12-15% distance increase)

### Choosing Curve Factor:
```python
# Safety-critical mission (schools, hospitals, parks)
curve_factor = 0.15  # Accept 10%+ extra distance

# Normal urban mission
curve_factor = 0.10  # Good balance (5% extra distance)

# Speed-critical mission (emergency response)
curve_factor = 0.05  # Minimal curving (2% extra distance)

# Industrial/sparse area
curve_factor = 0.0   # No curving (straight line fastest)
```

---

## Practical Workflow

### 1. Compute Base Route
```bash
# Existing: TSP optimization finds waypoints
python path.py  # Creates basic route
```

### 2. Analyze Curved Options
```bash
python analyze_curved_routes.py

# Shows:
# - Is curved routing worth it for THIS route?
# - What's the optimal curve factor?
# - How much risk reduction?
```

### 3. Make Decision
If analysis shows `efficiency_ratio > 1.5`:
→ Use curved routes

Else:
→ Stick with straight waypoints

### 4. Implement in Mission
```python
# After getting TSP solution:
optimizer = CurvedRouteOptimizer(geo_loader, altitude_ft=250)
curved_waypoints = optimizer.generate_multi_curved_path(
    tsp_waypoints, 
    curve_factor=0.10
)

# Upload curved_waypoints to drone
upload_to_drone(curved_waypoints)
```

---

## Limitations & Future Work

### Current Limitations:
1. **Simple perpendicular offset** — Not nearest-neighbor avoidance
2. **Linear interpolation** — Could use B-splines for smoother curves
3. **2D only** — Doesn't account for altitude variance
4. **Discrete sampling** — Could use calculus optimization

### Future Enhancements:
```python
# Gradient field routing (population density flow)
curved_path = route_along_population_gradient(
    start, end, 
    pop_raster,
    algorithm='potential_field'
)

# TSP with population-weighted distances
# (truly risk-aware shortest path problem)

# 3D route optimization
# (combine horizontal curving + altitude variation)
```

---

## Integration with Existing System

### Option 1: Post-Process TSP
```
Raw TSP → Straight waypoints
         ↓
    analyze_curved_routes.py (is it worth it?)
         ↓
    (if yes) generate_multi_curved_path()
         ↓
         Curved waypoints → Upload to drone
```

### Option 2: Risk-Weighted TSP
```
TSP Cost Matrix = distance + (population × death_probability)
         ↓
    Run TSP solver (OR-Tools)
         ↓
         Naturally avoids population
         ↓
         Upload directly to drone
```

Option 2 is more elegant but requires modifying TSP cost calculation.

---

## FAQ

**Q: Why not just always use curved routes?**
A: Trade-off triangle:
- Speed/efficiency: Longer paths take more time, burn more battery
- Mission complexity: More waypoints = harder to execute
- Safety: Reduces risk but isn't zero-risk

**Q: How much extra battery for curved route?**
A: Roughly proportional to extra distance (~0.5% more battery per 5% extra distance)

**Q: Does altitude matter for curved routing?**
A: Not directly. Altitude affects casualty probability, but optimal path shape is same. Could use different curves for different altitudes.

**Q: Can I fly curved routes on my drone?**
A: Yes! Any drone that supports waypoint missions (most do). Just upload the curved waypoint list instead of straight ones.

**Q: What about wind/weather?**
A: Wind doesn't affect optimal path (it's relative to air). Can adjust curve factor for stability (smaller curves = less aggressive).

**Q: Is this legally required?**
A: No, but increasingly recommended:
- EU regulations: "minimize risk to uninvolved persons"
- FAA: Best practices for UAS operations
- Corporate liability: Curved routes show due diligence

---

## Running Your First Curved Route

```bash
# 1. Run analysis
python analyze_curved_routes.py

# 2. Check the output
# Look for: efficiency_ratio > 1.5?
# Look for: exposure_reduction_pct > 5%?

# 3a. If YES → Use the recommended curve_factor
curved_waypoints = optimizer.generate_multi_curved_path(
    tsp_waypoints, 
    curve_factor=0.10
)

# 3b. If NO → Use straight routes
curved_waypoints = tsp_waypoints

# 4. Fly it!
drone.upload_mission(curved_waypoints)
```

---

## Conclusion

**You're not crazy — you're thinking like a professional pilot.**

Curved routes are a legitimate optimization technique used in:
- Commercial aviation (flight corridors)
- Maritime shipping (shipping lanes)
- Autonomous vehicles (path planning)
- Drone delivery (Amazon Prime Air)

It's the right move for safety-critical operations. Use the tools to decide when it's worth the extra distance.

**Recommendation:** Make curved routing the default for urban missions, keep straight routes for industrial/sparse areas.

