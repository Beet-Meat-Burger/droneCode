# Complete Algorithm and Formula Reference

## Table of Contents
1. [Physics Models](#physics-models)
2. [Casualty Calculation](#casualty-calculation)
3. [Risk-Aware Routing](#risk-aware-routing)
4. [Curved Route Optimization](#curved-route-optimization)
5. [Long Leg Breaking](#long-leg-breaking)
6. [Route Scoring](#route-scoring)

---

## Physics Models

### 1. Terminal Velocity Calculation

**Physics:** When a drone falls from altitude $h$, it reaches terminal velocity $v_t$ where drag force equals gravitational force.

$$v_t = \sqrt{\frac{2mg}{ρ AC_d}}$$

Where:
- $m$ = drone mass (kg)
- $g$ = gravitational acceleration (9.81 m/s²)
- $ρ$ = air density (1.225 kg/m³ at sea level)
- $A$ = drag cross-section area (m²)
- $C_d$ = drag coefficient (≈ 0.25 for drone)

**Approximation used in code:**
$$v_t(h) = \sqrt{2gh} \times (1 - e^{-h/h_c})$$

Where $h_c$ ≈ 500 m is characteristic height for drag effects.

**Implementation:** `kimDroneGoon/simulation.py` → `calculate_impact_velocity(altitude_ft)`

---

### 2. Kinetic Energy at Impact

Once impact velocity is known:

$$KE = \frac{1}{2}mv_t^2$$

Where:
- $m$ = drone mass (kg)
- $v_t$ = terminal velocity (m/s)

**Typical values:**
- At 100 ft: KE ≈ 1,500 J (low energy)
- At 250 ft: KE ≈ 8,000 J (medium energy)
- At 500 ft: KE ≈ 20,000 J (high energy)

**Implementation:** `altitude_analysis.py` → kinetic energy calculation

---

### 3. Death Probability Model

Empirical model based on impact force analysis:

$$P(\text{death} | KE) = \begin{cases}
0.05 & \text{if } KE < 500 \text{ J} \\
0.05 + 0.45 \times \frac{KE - 500}{500} & \text{if } 500 \leq KE < 1000 \\
0.50 + 0.45 \times \frac{KE - 1000}{5000} & \text{if } KE \geq 1000 \\
\text{capped at } 0.95
\end{cases}$$

**Rationale:**
- Below 500 J: Limited lethal force, ~5% fatality rate (blunt trauma)
- 500-1000 J: Non-linear increase, injury to fatality transition zone
- Above 1000 J: Approaching maximum lethality, ~95% fatality rate

**Key insight:** Flying 100 m lower reduces KE by ~40%, reducing death probability by ~80%

**Implementation:** `altitude_analysis.py` → death probability calculation

---

## Casualty Calculation

### Population-to-Casualty Mapping

**Assumptions:**
1. Each 100m × 100m grid cell has population uniformly distributed
2. Impact footprint = circular disc with radius $r$ = altitude (1:1 rule)
3. People within impact zone experience collision force

### Impact Area Calculation

For a drone at altitude $h$, impact creates a circular damage zone:

$$A_{impact} = \pi r^2 = \pi \left(h \times \frac{\text{FT_TO_METERS}}{1}\right)^2$$

**Example:**
- At 100 ft (30.5 m): Impact area ≈ 2,920 m²
- At 250 ft (76.2 m): Impact area ≈ 18,200 m²
- At 500 ft (152.4 m): Impact area ≈ 72,800 m²

**Formula in code:**
```python
altMeters = altitude_ft * 0.3048
lethal_radius = altMeters * LETHAL_RADIUS_MULT  # 1.0
impact_area_m2 = math.pi * (lethal_radius ** 2)
```

### Casualty Probability

Given:
- Population density in cell: $\rho$ (people per 100m cell)
- Impact area: $A$ (m²)
- Death probability: $P_d$ (from kinetic energy)

**Expected people in impact zone:**
$$E[\text{people}] = \rho \times \frac{A}{10,000}$$

**Probability at least one person hit** (Poisson approximation):
$$P(\text{hit}) = 1 - e^{-\lambda} \approx \min(1, \lambda)$$

where $\lambda = E[\text{people}]$

**Final casualty probability:**
$$P(\text{casualty}) = P(\text{hit}) \times P(\text{death})$$

### Casualty Exposure (Path Integral)

For a path segment from waypoint A to B:

$$\text{Casualty Exposure} = \int_{\text{path}} \rho(s) \times P(\text{death | alt}) \times ds$$

Where:
- $s$ = distance along path
- $\rho(s)$ = population density at position $s$
- $\text{ds}$ = infinitesimal path segment

**Discretized version** (in code):
```python
total_exposure = 0
for segment in waypoint_path:
    for point in segment.sample(n=20):
        density = get_density(point)
        death_prob = get_death_prob(altitude)
        exposure += density * death_prob * segment_length
```

**Implementation:** `curved_route_optimizer.py` → `compute_path_casualty_exposure()`

---

## Risk-Aware Routing

### Altitude Selection Strategy

For each waypoint, choose altitude based on local population density:

$$\text{altitude} = \arg\min_h \left[ \text{Casualty Exposure}(h) + \text{Cost}(h) \right]$$

**Multi-Strategy Approach:**

#### Strategy 1: Low Altitude Everywhere
$$h_i = 100 \text{ ft} \quad \forall i$$
- **Pro:** Minimum energy cost
- **Con:** High risk over dense areas

#### Strategy 2: High Altitude Everywhere
$$h_i = 500 \text{ ft} \quad \forall i$$
- **Pro:** Reduced injury zone, better energy safety margin
- **Con:** Higher kinetic energy, very high density penalty

#### Strategy 3: Mixed (Adaptive)
$$h_i = \begin{cases}
100 \text{ ft} & \text{if } \rho_i < 50 \text{ ppl/cell} \\
250 \text{ ft} & \text{if } 50 \leq \rho_i < 200 \\
500 \text{ ft} & \text{if } \rho_i \geq 200
\end{cases}$$

- **Pro:** Balance between energy and risk
- **Con:** Manual thresholds needed

#### Strategy 4: Optimal (Per-Waypoint)
$$h_i = \arg\min_h \left[ C(\rho_i, h) \right]$$

Where cost function:
$$C(\rho, h) = \alpha \times \text{Casualty}(\rho, h) + \beta \times \text{Energy}(h)$$

- $\alpha$ = weight for casualty minimization (default: 1.0)
- $\beta$ = weight for energy efficiency (default: 0.001)

**Implementation:** `risk_aware_routing.py` → `optimal_altitude_for_waypoint()` and `velocity_scaled_cost()`

---

## Curved Route Optimization

### Problem Statement

Given a direct waypoint path, find a curved alternative that:
- Avoids high-population areas
- Stays within acceptable accuracy tolerance
- Minimizes detour distance

### Casualty Exposure Comparison

**Direct Path:**
$$E_{\text{direct}} = \int_{\text{direct}} \rho(s) \times P_d \times ds$$

**Curved Path:**
$$E_{\text{curved}} = \int_{\text{curved}} \rho(s) \times P_d \times ds$$

### Curve Generation Algorithm

1. **Identify High-Density Region(s)** along direct path
   - Sample points every 100m along straight line
   - Find all points with $\rho > \rho_{\text{threshold}}$

2. **Generate Curve Control Points**
   - For each high-density region, compute offset perpendicular to path
   - Offset magnitude: $\text{offset} = \text{curve\_factor} \times \text{max\_density\_in\_region}$
   - Create 2-3 control points on alternating sides

3. **Smooth Interpolation**
   - Use cubic spline or Bézier curves to connect:
     - Original waypoint A
     - Curve control points
     - Original waypoint B

4. **Distance Penalty Calculation**
   
   $$\text{distance\_ratio} = \frac{L_{\text{curved}}}{L_{\text{direct}}}$$
   
   - If ratio < 1.05 (5% detour): Acceptable, use curved path
   - If ratio > 1.20 (20% detour): Too long, stick with direct

### Implementation Details

**File:** `curved_route_optimizer.py`

**Key Methods:**
- `generate_curved_waypoint()` - Create single curve point
- `generate_multi_curved_path()` - Full path with curves
- `evaluate_curve_efficiency()` - Compare direct vs curved

**Formula for curve control point:**
$$P_{\text{control}} = P_{\text{direct}} + \vec{n} \times w(\rho, d_{\text{perp}})$$

Where:
- $P_{\text{direct}}$ = point on direct path
- $\vec{n}$ = perpendicular unit vector to path
- $w$ = weighting function based on density and perpendicular distance
- $d_{\text{perp}}$ = perpendicular distance from original path

---

## Long Leg Breaking

### Problem

Battery/regulatory constraints limit leg length to $L_{\max}$ (typically 10 km).

### Detection

For each consecutive waypoint pair $(P_i, P_{i+1})$:

$$L = \sqrt{(x_{i+1} - x_i)^2 + (y_{i+1} - y_i)^2}$$

If $L > L_{\max}$, break it up.

### Insertion Strategy

Number of intermediate waypoints needed:
$$n_{\text{intermediate}} = \left\lceil \frac{L}{L_{\max}} \right\rceil - 1$$

### Waypoint Selection Criteria

For $n_{\text{intermediate}}$ waypoints, find positions that minimize:

$$\text{Risk} = \sum_{j=1}^{n} \rho(P_j)$$

**Algorithm:**
1. Sample 100 points along line
2. Sort by population density
3. Select lowest $n_{\text{intermediate}}$ points
4. Order them by position along line (to insert near lowest-pop points)

### Insertion Points Calculation

Using parametric form along line:

$$P(t) = P_i + t(P_{i+1} - P_i), \quad t \in [0, 1]$$

For each selected point, find $t$ value and convert back to lat/lng coordinates.

**Implementation:** `long_leg_breaker.py` → `break_long_legs()`

---

## Route Scoring

### Multi-Factor Score

$$\text{Score} = B - C$$

Where:
- $B$ = benefits (cargo, distance)
- $C$ = costs (time, risk)

### Benefit Calculation

$$B = (\text{payload\_kg} + 1) \times \text{distance\_km} \times 2$$

The "+1" ensures empty flights have positive score.

### Cost Calculation

**Time Cost:**
$$C_{\text{time}} = \text{flight\_time\_minutes}$$

Based on distance and speed:
$$\text{flight\_time} = \frac{\text{distance\_km}}{\text{speed\_kmh}} \times 60 + \text{hover\_time}$$

**Risk Cost:**
$$C_{\text{risk}} = \text{risk\_coefficient} \times 1$$

Risk coefficient per location:
$$\text{risk\_coeff} = \rho \times A_{\text{impact}} / 10000$$

Where $A_{\text{impact}}$ depends on altitude.

### Final Score

$$\text{Final\_Score} = B - (C_{\text{time}} + C_{\text{risk}})$$

Higher scores = better (safer + more efficient)

**Implementation:** `test.py` → `ratePath()`

---

## Quality Assurance Formulas

### Route Validation Checklist

1. **Coordinate Validity**
   - Latitude: $22.0 \leq \text{lat} \leq 22.5$
   - Longitude: $114.0 \leq \text{lng} \leq 114.3$

2. **Altitude Validity**
   - Minimum: 50 ft (regulatory)
   - Maximum: 500 ft (safety)

3. **Leg Distance Validity**
   - Maximum: 10 km (battery/regulatory)
   - All legs checked via Haversine formula:
     $$d = 2R \arcsin\left(\sqrt{\sin^2\left(\frac{\Delta\phi}{2}\right) + \cos(\phi_1)\cos(\phi_2)\sin^2\left(\frac{\Delta\lambda}{2}\right)}\right)$$

4. **Path Distance Validity**
   - Total: ≤ drone's max range (typically 15-25 km)

---

## Data Column Definitions

### altitude_summary.csv
- `altitude_ft`: Flight altitude (feet)
- `avg_velocity_mps`: Terminal velocity at impact (m/s)
- `avg_kinetic_energy_j`: Kinetic energy at impact (Joules)
- `avg_death_probability`: Fractionalprobability of death given impact
- `casualty_probability`: Probability at least one casualty occurs
- `total_casualties`: Expected number of deaths per 10,000 impacts

### density_casualty_model.csv
- `population_density`: People per 100m cell
- `altitude_ft`: Flight altitude
- `casualty_probability`: Joint probability of hit AND death
- `expected_casualties_per_1000_impacts`: Scaled metric for planning

### drone_mission_waypoints.csv
- `waypoint_id`: Sequential identifier
- `latitude`: WGS84 latitude
- `longitude`: WGS84 longitude
- `altitude_ft`: Recommended altitude
- `type`: ORIGINAL | INSERTED (for leg breakers)

---

## References

- **Terminal Velocity:** Assumes Re > 1000 (turbulent regime)
- **Death Probability:** Based on blunt trauma literature (impact force analysis)
- **Population Density:** WorldPop 2020 UNICEF-adjusted grid (100m resolution)
- **Drag Model:** Simplified for sphere/cylinder hybrid at typical drone altitudes

